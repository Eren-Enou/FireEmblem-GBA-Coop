"""TCP/TLS host. The event loop serializes all simulation mutation."""
import asyncio
from copy import deepcopy
import hmac
import logging
import secrets

from app.coop.progression import progression_changes

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

    def state_projection(self):
        try:
            from app.coop.tactics import project
            state = self.simulation.snapshot()
            state['tactics'] = project(self.simulation, state)
            return state
        except Exception:
            if not self.simulation.fault or not hasattr(self, 'packet'):
                raise
            # An unexpected lifecycle fault may leave no active level. Freeze
            # the last published board, never expose a half-initialized chapter.
            state = deepcopy(self.packet['state'])
            state['status'] = 'fault'
            state['tactics'].update(status='unavailable', note='Host fault; previews cleared', units=[], threats=[], forecasts=[])
            for unit in state['units']:
                for kind in ('moves', 'attacks', 'heals', 'consumables'):
                    unit[kind] = []
            return state

    def make_packet(self, result=None):
        state = self.state_projection()
        return validate_packet({'v': VERSION, 'type': 'state', 'session': self.id,
                                'revision': self.revision, 'digest': digest(state),
                                'state': state, 'result': result})

    def authenticate(self, token):
        for team, expected in self.tokens.items():
            if hmac.compare_digest(token.encode('utf-8'), expected.encode('utf-8')):
                return team
        raise ProtocolError('authentication_failed')

    def command(self, team, request, connected):
        for _ in self.command_steps(team, request, connected):
            pass
        return self.packet

    async def command_async(self, team, request, connected):
        # One thread and one lock; only network work runs between engine steps.
        for _ in self.command_steps(team, request, connected, cooperative=True):
            await asyncio.sleep(0)
        return self.packet

    def command_steps(self, team, request, connected, cooperative=False):
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
            if cooperative:
                yield from self.simulation.execute_steps(team, request)
            else:
                self.simulation.execute(team, request)
        except ProtocolError:
            raise
        except Exception:
            logging.exception('Authoritative engine fault; session stopped')
            self.simulation.fault = True
            # A partially applied command is never reported as a rejection with
            # an unchanged revision. Publish a terminal authoritative fault.
        if (not self.simulation.fault and self.simulation.status == 'intermission' and
                self.simulation.campaign.checkpoint['status'] == 'pending'):
            self.simulation.save_checkpoint()
        self.revision += 1
        after = self.state_projection()
        changes = []
        previous = {unit['id']: unit for unit in before['units']}
        for new in after['units']:
            old = previous.get(new['id'])
            if old is None:
                changes.append(new['id'] + ': joined chapter')
                continue
            if old['pos'] != new['pos'] or old['hp'] != new['hp'] or old['inventory'] != new['inventory']:
                changes.append(f"{new['id']}: HP {old['hp']} -> {new['hp']}, position {old['pos']} -> {new['pos']}, "
                               f"uses {[i['uses'] for i in old['inventory']]} -> {[i['uses'] for i in new['inventory']]}")
        growth = progression_changes(before, after)
        summary = '; '.join(growth) + '; ' if growth else ''
        if request['action'] in ('heal', 'use'):
            old_target = next(u for u in before['units'] if u['id'] == request['target'])
            new_target = next(u for u in after['units'] if u['id'] == request['target'])
            summary = (f"{request['action'].upper()} {request['unit']} -> {request['target']}: "
                       f"HP {old_target['hp']} -> {new_target['hp']} "
                       f"(+{new_target['hp']-old_target['hp']}); " + summary)
        summary += f"{team}: {request['action']}"
        if request['action'] == 'end_phase':
            summary += f"; {before['phase']} -> {after['phase']}, turn {after['turn']}"
        if changes:
            summary += '; ' + '; '.join(changes)
        if after['campaign'] and before['campaign']['chapter'] != after['campaign']['chapter']:
            summary += '; CHAPTER: ' + after['campaign']['title']
        if after['status'] == 'intermission':
            summary += '; CHAPTER COMPLETE; both commanders must Ready to continue'
            summary += '; ' + after['campaign']['checkpoint']['message']
        if after['status'] in ('victory', 'defeat'):
            summary += '; SHARED ' + after['status'].upper()
        deaths = [u['id'] for u in after['units'] if u['dead'] and not next(
            (old for old in before['units'] if old['id'] == u['id']), {'dead': True})['dead']]
        if deaths:
            summary += '; Fallen: ' + ', '.join(deaths)
        if self.simulation.fault:
            summary = 'Host resolution fault; session frozen. Restart the host after inspecting its log.'
        result = {'id': request['id'], 'team': team, 'action': request['action'], 'summary': summary[:4096]}
        self.packet = self.make_packet(result)
        return self.packet


class Host:
    def __init__(self, session, heartbeat_interval=5, heartbeat_timeout=20):
        self.session = session
        self.peers = {}
        self.lock = asyncio.Lock()
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout
        self.connections = set()
        self.admission_credit = 16.0
        self.admission_time = 0.0

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
        tasks = []
        loop = asyncio.get_running_loop()
        now = loop.time()
        self.admission_credit = min(16, self.admission_credit + (now - self.admission_time) * 2)
        self.admission_time = now
        admitted = len(self.connections) < 8 and self.admission_credit >= 1
        if admitted:
            self.admission_credit -= 1
            self.connections.add(writer)
        try:
            if not admitted:
                raise ProtocolError('admission_limit')
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
            requests = asyncio.Queue(maxsize=4)
            heartbeat = {'nonce': 0, 'waiting': None, 'sent': 0}

            async def monitor():
                while True:
                    await asyncio.sleep(self.heartbeat_interval)
                    if heartbeat['waiting'] is not None:
                        if loop.time() - heartbeat['sent'] >= self.heartbeat_timeout:
                            raise ProtocolError('heartbeat_timeout')
                    else:
                        heartbeat['nonce'] += 1
                        heartbeat['waiting'] = heartbeat['nonce']
                        heartbeat['sent'] = loop.time()
                        await self.send(writer, {'v': VERSION, 'type': 'ping',
                                                 'nonce': heartbeat['nonce']})

            async def receive():
                credit, last = 30.0, loop.time()
                while True:
                    request = await self.read(reader)
                    if request is None:
                        raise ConnectionError('peer_closed')
                    now = loop.time()
                    credit = min(30, credit + (now - last) * 10)
                    last = now
                    if credit < 1:
                        raise ProtocolError('rate_limit')
                    credit -= 1
                    if request['type'] == 'pong':
                        if request['nonce'] != heartbeat['waiting']:
                            raise ProtocolError('unexpected_pong')
                        heartbeat['waiting'] = None
                        continue
                    if requests.full():
                        raise ProtocolError('request_queue_full')
                    requests.put_nowait(request)

            async def supervise(coroutine):
                try:
                    await coroutine
                except (OSError, ValueError, asyncio.TimeoutError) as exc:
                    # Close immediately so an in-flight command may finish but
                    # cannot be followed by another command from either player.
                    if isinstance(exc, (ProtocolError, asyncio.TimeoutError)):
                        try:
                            # Queue one bounded final error, then close without
                            # yielding: a slow reader must not delay the pause.
                            writer.write(encode({'v': VERSION, 'type': 'error',
                                                 'code': str(exc) or 'timeout'}))
                        except OSError:
                            pass
                    writer.close()
                    if not requests.full():
                        requests.put_nowait(exc)

            tasks = [asyncio.create_task(supervise(receive())),
                     asyncio.create_task(supervise(monitor()))]
            while not writer.is_closing():
                request = await requests.get()
                if isinstance(request, Exception):
                    raise request
                async with self.lock:
                    if writer.is_closing():
                        break
                    if request['type'] == 'sync':
                        await self.send(writer, self.session.packet)
                        continue
                    try:
                        connected = [t for t, w in self.peers.items() if not w.is_closing()]
                        packet = await self.session.command_async(team, request, connected)
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
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            if team and self.peers.get(team) is writer:
                async with self.lock:
                    if self.peers.get(team) is writer:
                        del self.peers[team]
                        await self.peer_status()
            self.connections.discard(writer)
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), 5)
            except (OSError, asyncio.TimeoutError):
                pass

    async def listen(self, port=38670, bind='127.0.0.1', tls_context=None):
        from app.coop.security import validate_listener
        validate_listener(bind, tls_context)
        options = {'ssl': tls_context, 'ssl_handshake_timeout': 5,
                   'ssl_shutdown_timeout': 5} if tls_context else {}
        return await asyncio.start_server(self.handle, bind, port, limit=MAX_FRAME, **options)
