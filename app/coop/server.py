"""TCP/TLS host. The event loop serializes all simulation mutation."""
import asyncio
import hmac
import logging
import secrets

from app.coop.protocol import (MAX_FRAME, TEAMS, VERSION, ProtocolError, decode,
                               digest, encode, validate_packet, validate_request)


class Session:
    def __init__(self, simulation):
        self.simulation = simulation
        self.id = secrets.token_hex(16)
        self.tokens = {team: secrets.token_urlsafe(32) for team in TEAMS}
        self.revision = 0
        self.seen = {team: set() for team in TEAMS}
        self.packet = self.make_packet()

    def make_packet(self, result=None):
        state = self.simulation.snapshot()
        return validate_packet({'v': VERSION, 'type': 'state', 'session': self.id,
                                'revision': self.revision, 'digest': digest(state),
                                'state': state, 'result': result})

    def authenticate(self, token):
        for team, expected in self.tokens.items():
            if hmac.compare_digest(token.encode('utf-8'), expected.encode('utf-8')):
                return team
        raise ProtocolError('authentication_failed')

    def command(self, team, request, connected):
        validate_request(request)
        if request['type'] != 'command':
            raise ProtocolError('expected_command')
        if team not in TEAMS:
            raise ProtocolError('authentication_failed')
        if request['id'] in self.seen[team]:
            raise ProtocolError('duplicate_command')
        if len(self.seen[team]) >= 10000:
            raise ProtocolError('session_command_limit')
        self.seen[team].add(request['id'])
        if set(connected) != set(TEAMS):
            raise ProtocolError('peer_disconnected')
        if request['session'] != self.id:
            raise ProtocolError('wrong_session')
        if request['revision'] != self.revision:
            raise ProtocolError('stale_revision')
        if request['digest'] != self.packet['digest']:
            raise ProtocolError('state_mismatch')
        if request['phase'] != self.packet['state']['phase']:
            raise ProtocolError('stale_phase')
        before = self.packet['state']
        try:
            self.simulation.execute(team, request)
        except ProtocolError:
            raise
        except Exception:
            logging.exception('Authoritative engine fault; session stopped')
            self.simulation.fault = True
            # A partially applied command is never reported as a rejection with
            # an unchanged revision. Publish a terminal authoritative fault.
        self.revision += 1
        after = self.simulation.snapshot()
        changes = []
        for old, new in zip(before['units'], after['units']):
            if old['pos'] != new['pos'] or old['hp'] != new['hp'] or old['inventory'] != new['inventory']:
                changes.append(f"{new['id']}: HP {old['hp']} -> {new['hp']}, position {old['pos']} -> {new['pos']}, "
                               f"uses {[i['uses'] for i in old['inventory']]} -> {[i['uses'] for i in new['inventory']]}")
        summary = f"{team}: {request['action']}"
        if request['action'] == 'end_phase':
            summary += f"; {before['phase']} -> {after['phase']}, turn {after['turn']}"
        if changes:
            summary += '; ' + '; '.join(changes)
        if self.simulation.fault:
            summary = 'Host resolution fault; session frozen. Restart the host after inspecting its log.'
        result = {'id': request['id'], 'team': team, 'action': request['action'], 'summary': summary[:4096]}
        self.packet = self.make_packet(result)
        return self.packet


class Host:
    def __init__(self, session):
        self.session = session
        self.peers = {}
        self.lock = asyncio.Lock()

    async def send(self, writer, packet):
        writer.write(encode(packet))
        await asyncio.wait_for(writer.drain(), 5)

    async def broadcast(self, packet):
        # Called with the session lock. Each peer sees results in revision order.
        for writer in list(self.peers.values()):
            try:
                await self.send(writer, packet)
            except (OSError, asyncio.TimeoutError):
                writer.close()

    async def peer_status(self):
        await self.broadcast({'v': VERSION, 'type': 'peers', 'teams': sorted(
            team for team, writer in self.peers.items() if not writer.is_closing())})

    async def read(self, reader):
        try:
            line = await reader.readline()
        except (ValueError, asyncio.LimitOverrunError) as exc:
            raise ProtocolError('frame_too_large') from exc
        if not line:
            return None
        return validate_request(decode(line))

    async def handle(self, reader, writer):
        team = None
        try:
            hello = await asyncio.wait_for(self.read(reader), 5)
            if hello is None or hello['type'] != 'hello':
                raise ProtocolError('expected_hello')
            team = self.session.authenticate(hello['token'])
            async with self.lock:
                if team in self.peers:
                    raise ProtocolError('seat_in_use')
                self.peers[team] = writer
                await self.send(writer, {'v': VERSION, 'type': 'welcome', 'team': team,
                                         'snapshot': self.session.packet})
                await self.peer_status()
            while True:
                request = await self.read(reader)
                if request is None:
                    break
                async with self.lock:
                    if request['type'] == 'sync':
                        await self.send(writer, self.session.packet)
                        continue
                    try:
                        connected = [t for t, w in self.peers.items() if not w.is_closing()]
                        packet = self.session.command(team, request, connected)
                    except ProtocolError as exc:
                        await self.send(writer, {'v': VERSION, 'type': 'reject',
                                                 'id': request.get('id', ''), 'code': str(exc),
                                                 'revision': self.session.revision})
                    else:
                        await self.broadcast(packet)
        except (ProtocolError, asyncio.TimeoutError) as exc:
            try:
                await self.send(writer, {'v': VERSION, 'type': 'error', 'code': str(exc) or 'timeout'})
            except (OSError, asyncio.TimeoutError):
                pass
        except (OSError, ConnectionError):
            pass
        finally:
            async with self.lock:
                if team and self.peers.get(team) is writer:
                    del self.peers[team]
                    await self.peer_status()
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    async def listen(self, port=38670, bind='127.0.0.1', tls_context=None):
        from app.coop.security import validate_listener
        validate_listener(bind, tls_context)
        options = {'ssl': tls_context, 'ssl_handshake_timeout': 5,
                   'ssl_shutdown_timeout': 5} if tls_context else {}
        return await asyncio.start_server(self.handle, bind, port, limit=MAX_FRAME, **options)
