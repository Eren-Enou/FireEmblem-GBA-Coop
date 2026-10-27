"""Network client/model: validated snapshots only, no LT or combat simulation."""
import queue
import socket
import threading
import time
import uuid

from app.coop.progression import progression_changes

from app.coop.protocol import (MAX_FRAME, TEAMS, VERSION, ProtocolError, decode,
                               encode, fields, integer, require, string, validate_packet,
                               validate_request)


READ_TIMEOUT = 35
RESULT_TIMEOUT = 120


class Model:
    def __init__(self):
        self.team = None
        self.packet = None
        self.peers = []
        self.pending = None
        self.syncing = False
        self.message = 'Connecting'
        self.observed = []
        self.progression = []
        self.level_ups = []

    def apply(self, packet):
        require(type(packet) is dict and type(packet.get('v')) is int and packet['v'] == VERSION)
        kind = packet.get('type')
        if kind == 'welcome':
            fields(packet, ('v', 'type', 'team', 'snapshot'))
            require(self.team is None and packet['team'] in TEAMS)
            self.team = packet['team']
            return self.apply(packet['snapshot'])
        if kind == 'state':
            validate_packet(packet)
            if self.packet:
                require(packet['session'] == self.packet['session'], 'wrong_session')
                require(packet['state']['ruleset'] == self.packet['state']['ruleset'], 'ruleset_changed')
                if packet['revision'] < self.packet['revision']:
                    return
                if packet['revision'] == self.packet['revision']:
                    require(packet['digest'] == self.packet['digest'], 'conflicting_revision')
            advancing = self.packet is None or packet['revision'] > self.packet['revision']
            if self.packet and advancing:
                changes = progression_changes(self.packet['state'], packet['state'])
                self.progression = (self.progression + changes)[-8:]
                self.level_ups = (self.level_ups + [change for change in changes if 'LEVEL UP' in change])[-4:]
            self.packet = packet
            if advancing or self.syncing or (packet['result'] and packet['result']['id'] == self.pending):
                self.pending = None
            self.syncing = False
            result = packet['result']
            self.message = result['summary'] if result else 'Connected; waiting for both armies'
            if not self.observed or self.observed[-1]['revision'] != packet['revision']:
                self.observed.append(packet)
                # UI history is not a campaign save or replay journal.
                self.observed = self.observed[-128:]
        elif kind == 'peers':
            fields(packet, ('v', 'type', 'teams'))
            require(type(packet['teams']) is list and len(packet['teams']) <= 2)
            require(all(t in TEAMS for t in packet['teams']) and len(set(packet['teams'])) == len(packet['teams']))
            self.peers = packet['teams']
        elif kind == 'reject':
            fields(packet, ('v', 'type', 'id', 'code', 'revision'))
            integer(packet['revision'])
            string(packet['code'])
            require(type(packet['id']) is str and len(packet['id']) <= 64)
            if packet['id'] == self.pending:
                self.pending = None
            self.message = 'Rejected: ' + packet['code']
            if self.packet and (packet['revision'] != self.packet['revision'] or
                                packet['code'] in ('state_mismatch', 'stale_phase', 'stale_revision')):
                self.syncing = True
        elif kind == 'error':
            fields(packet, ('v', 'type', 'code'))
            string(packet['code'])
            raise ProtocolError(packet['code'])
        else:
            raise ProtocolError('unknown_server_message')

    @property
    def can_act(self):
        return bool(self.packet and set(self.peers) == set(TEAMS) and not self.pending and
                    not self.syncing and self.packet['state']['status'] == 'playing' and
                    self.packet['state']['phase'] == self.team)

    @property
    def can_ready(self):
        return bool(self.packet and set(self.peers) == set(TEAMS) and not self.pending and
                    not self.syncing and self.packet['state']['status'] == 'intermission' and
                    self.team not in self.packet['state']['campaign']['ready'])

    def command(self, action, **kwargs):
        require(self.can_ready if action == 'ready' else self.can_act, 'client_not_ready')
        packet = self.packet
        request = {'v': VERSION, 'type': 'command', 'session': packet['session'],
                   'id': uuid.uuid4().hex, 'revision': packet['revision'],
                   'phase': packet['state']['phase'], 'digest': packet['digest'],
                   'action': action, **kwargs}
        validate_request(request)
        self.pending = request['id']
        return request


class Connection:
    def __init__(self, host, port, token, tls=None):
        from app.coop.security import connect
        integer(port, 1, 65535)
        # TLS validation completes before the hello can reveal a credential.
        self.socket = connect(host, port, tls)
        self.security = self.socket.version() if tls is not None else 'loopback plaintext'
        self.stream = self.socket.makefile('rb')
        self.model = Model()
        self.inbox = queue.Queue(maxsize=128)
        self.closed = False
        self.send_lock = threading.Lock()
        self.pending_since = None
        try:
            self.send({'v': VERSION, 'type': 'hello', 'token': token})
            self.model.apply(self.read())
            require(self.model.team is not None, 'missing_welcome')
        except Exception:
            self.close()
            raise
        self.socket.settimeout(READ_TIMEOUT)
        self.thread = threading.Thread(target=self.receive, daemon=True)
        self.thread.start()

    def send(self, packet):
        with self.send_lock:
            self.socket.sendall(encode(packet))
        if packet['type'] == 'command':
            self.pending_since = time.monotonic()

    def read(self):
        line = self.stream.readline(MAX_FRAME + 1)
        if not line:
            raise ConnectionError('Host disconnected')
        return decode(line)

    def receive(self):
        try:
            while not self.closed:
                packet = self.read()
                if packet.get('type') == 'ping':
                    fields(packet, ('v', 'type', 'nonce'))
                    require(type(packet['v']) is int and packet['v'] == VERSION)
                    integer(packet['nonce'])
                    self.send({'v': VERSION, 'type': 'pong', 'nonce': packet['nonce']})
                else:
                    self.inbox.put(packet, timeout=5)
        except (OSError, ValueError, queue.Full) as exc:
            if not self.closed:
                try:
                    self.inbox.put_nowait(exc)
                except queue.Full:
                    self.closed = True
        finally:
            # The reader owns its buffered stream. Closing it from the UI thread
            # can wait on readline's lock for the full Windows socket timeout.
            self.stream.close()
            self.socket.close()

    def poll(self):
        if self.closed:
            self.close()
            self.model.peers = []
            raise ConnectionError('Connection closed; reopen the same invitation to rejoin')
        if self.model.pending and self.pending_since and time.monotonic() - self.pending_since > RESULT_TIMEOUT:
            self.close()
            raise ConnectionError('Command outcome unknown; rejoin for host state. Do not replay the action.')
        while True:
            try:
                packet = self.inbox.get_nowait()
            except queue.Empty:
                return
            if isinstance(packet, Exception):
                self.close()
                raise packet
            try:
                self.model.apply(packet)
            except ProtocolError as exc:
                if str(exc) == 'digest_mismatch':
                    self.model.syncing = True
                    self.model.message = 'State check failed; requesting authoritative resync'
                    self.send({'v': VERSION, 'type': 'sync'})
                    continue
                self.close()
                raise
            if self.model.syncing:
                self.send({'v': VERSION, 'type': 'sync'})

    def close(self):
        self.closed = True
        self.model.peers = []
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        if not hasattr(self, 'thread'):
            self.stream.close()
        self.socket.close()
