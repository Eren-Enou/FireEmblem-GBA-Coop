"""Phase 3A: live failures, bounded service and complete real-engine battles."""
import asyncio
from copy import deepcopy
import time
import unittest
from unittest.mock import patch

from app.coop.client import Connection
from app.coop.protocol import VERSION, decode, encode
from app.tests import test_network_coop as baseline


class PlayabilityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from app.coop.simulation import Simulation
        # Fixed seed 1 exercises a winning tactical sequence without fixture edits.
        self.sim = Simulation(seed=1)
        self.addCleanup(self.sim.close)

    asyncSetUp = baseline.TransportTests.asyncSetUp

    async def asyncTearDown(self):
        for writer in self.writers:
            writer.close()
        for writer in self.writers:
            try:
                await asyncio.wait_for(writer.wait_closed(), 0.5)
            except (OSError, asyncio.TimeoutError):
                writer.transport.abort()
        self.server.close()
        for writer in list(self.host.connections):
            writer.close()
        await asyncio.wait_for(self.server.wait_closed(), 5)

    open = baseline.TransportTests.open
    receive = baseline.TransportTests.receive

    async def clients(self):
        blue = await asyncio.to_thread(Connection, '127.0.0.1', self.port, self.session.tokens['player'])
        green = await asyncio.to_thread(Connection, '127.0.0.1', self.port, self.session.tokens['other'])
        self.addAsyncCleanup(asyncio.to_thread, blue.close)
        self.addAsyncCleanup(asyncio.to_thread, green.close)
        return blue, green

    async def until(self, clients, predicate, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for client in clients:
                client.poll()
            if predicate():
                return
            await asyncio.sleep(0.002)
        self.fail('Timed out waiting for verified client state')

    async def test_real_clients_answer_heartbeat_and_rejoin_after_silent_peer(self):
        self.host.heartbeat_interval = 0.03
        self.host.heartbeat_timeout = 0.12
        blue, green = await self.clients()
        await self.until((blue, green), lambda: blue.model.can_act)
        await asyncio.sleep(0.35)
        blue.poll()
        green.poll()
        self.assertTrue(blue.model.can_act)
        await asyncio.to_thread(green.close)
        await self.until((blue,), lambda: blue.model.peers == ['player'])
        silent, _ = await self.open('other')
        self.assertEqual((await self.receive(silent, 'welcome'))['snapshot'], blue.model.packet)
        # This peer reads a ping but never answers it. No TCP EOF is sent.
        self.assertEqual((await self.receive(silent, 'ping'))['nonce'], 1)
        self.assertEqual((await self.receive(silent, 'error'))['code'], 'heartbeat_timeout')
        await self.until((blue,), lambda: 'other' not in self.host.peers)
        self.assertFalse(blue.model.can_act)
        self.assertEqual(self.session.revision, 0)
        joined = await asyncio.to_thread(Connection, '127.0.0.1', self.port, self.session.tokens['other'])
        try:
            await self.until((blue, joined), lambda: blue.model.can_act)
            self.assertEqual(blue.model.packet, joined.model.packet)
        finally:
            await asyncio.to_thread(joined.close)

    async def test_disconnect_during_resolution_keeps_atomic_result_and_network_alive(self):
        self.host.heartbeat_interval = 0.02
        self.host.heartbeat_timeout = 0.10
        blue, green = await self.clients()
        await self.until((blue, green), lambda: blue.model.can_act)
        entered, release = asyncio.Event(), asyncio.Event()
        original = self.sim.execute_steps

        def held_resolution(*args):
            steps = original(*args)
            yield next(steps)  # A real LT step has already run under the lock.
            entered.set()
            while not release.is_set():
                yield
            yield from steps

        with patch.object(self.sim, 'execute_steps', side_effect=held_resolution):
            try:
                blue.send(blue.model.command('end_phase'))
                await asyncio.wait_for(entered.wait(), 3)
                await asyncio.to_thread(green.close)
                await asyncio.sleep(0.25)
                self.assertFalse(self.host.peers['player'].is_closing(), 'Heartbeat must run during resolution')
                self.assertTrue(self.host.peers['other'].is_closing(), 'EOF must be detected before resolution finishes')
            finally:
                release.set()
            await self.until((blue,), lambda: blue.model.packet['revision'] == 1 and blue.model.peers == ['player'])
        self.assertEqual(blue.model.packet['state']['phase'], 'other')
        self.assertEqual(self.session.revision, 1)
        rejoined = await asyncio.to_thread(Connection, '127.0.0.1', self.port, self.session.tokens['other'])
        try:
            await self.until((blue, rejoined), lambda: rejoined.model.can_act)
            self.assertEqual(blue.model.packet, rejoined.model.packet)
        finally:
            await asyncio.to_thread(rejoined.close)

    async def test_admission_cap_and_request_flood_preserve_session(self):
        blue, green = await self.clients()
        await self.until((blue, green), lambda: blue.model.can_act)
        before = deepcopy(self.session.packet)
        for _ in range(6):
            await self.open()  # Bounded five-second pre-auth sockets.
        extra, _ = await self.open()
        self.assertEqual((await self.receive(extra, 'error'))['code'], 'admission_limit')
        # Flood a valid seat with bounded frames; it must be removed, never mutate LT.
        green.socket.sendall(encode({'v': VERSION, 'type': 'sync'}) * 40)
        await self.until((blue,), lambda: 'other' not in self.host.peers)
        self.assertEqual(before, self.session.packet)
        self.assertFalse(blue.model.can_act)

    async def test_malformed_pong_closes_only_offender(self):
        self.host.heartbeat_interval = 0.02
        blue, green = await self.clients()
        await self.until((blue, green), lambda: blue.model.can_act)
        green.send({'v': VERSION, 'type': 'pong', 'nonce': True})
        await self.until((blue,), lambda: 'other' not in self.host.peers)
        self.assertEqual(self.session.revision, 0)

    async def test_rate_limit_sequential_sync_requests(self):
        reader, writer = await self.open('player')
        await self.receive(reader, 'welcome')
        before = deepcopy(self.session.packet)
        for _ in range(100):
            writer.write(encode({'v': VERSION, 'type': 'sync'}))
            await writer.drain()
            packet = decode(await asyncio.wait_for(reader.readline(), 3))
            if packet['type'] == 'peers':
                packet = decode(await asyncio.wait_for(reader.readline(), 3))
            if packet['type'] == 'error':
                self.assertEqual(packet['code'], 'rate_limit')
                break
            self.assertEqual(packet, before)
        else:
            self.fail('Sequential sync flood was not rate limited')
        self.assertEqual(self.session.packet, before)

    async def test_client_detects_silent_host_without_tcp_eof(self):
        self.host.heartbeat_interval = 100
        with patch('app.coop.client.READ_TIMEOUT', 0.15):
            blue, green = await self.clients()
        await self.until((blue, green), lambda: blue.model.can_act)
        await asyncio.sleep(0.25)
        with self.assertRaises(TimeoutError):
            blue.poll()
        self.assertFalse(blue.model.can_act)
        self.assertEqual(self.session.revision, 0)

    async def battle(self, aggressive):
        clients = await self.clients()
        await self.until(clients, lambda: clients[0].model.can_act)
        by_team = dict(zip(('player', 'other'), clients))
        actions = []
        for _ in range(250):
            packet = clients[0].model.packet
            state = packet['state']
            if state['status'] != 'playing':
                break
            active = by_team[state['phase']]
            await self.until(clients, lambda: active.model.can_act)
            args, kind = {}, 'end_phase'
            if aggressive and state['turn'] == 1:
                ready = [u for u in state['units'] if u['team'] == active.model.team and not u['finished']]
                if ready:
                    kind, args = 'wait', {'unit': ready[0]['id']}
            elif aggressive:
                enemies = [u for u in state['units'] if u['team'] == 'enemy' and not u['dead']]
                ready = [u for u in state['units'] if u['team'] == active.model.team and not u['dead'] and not u['finished']]
                if ready:
                    attackers = [u for u in ready if u['attacks']]
                    unit = max(attackers, key=lambda u: u['hp']) if attackers else max(ready, key=lambda u: u['hp'])
                    args = {'unit': unit['id']}
                    if unit['attacks']:
                        kind = 'attack'
                        args.update(min(unit['attacks'], key=lambda a: next(e['hp'] for e in enemies if e['id'] == a['target'])))
                    elif unit['moves'] and enemies:
                        kind = 'move'
                        args['pos'] = min(unit['moves'], key=lambda p: (min(abs(p[0]-e['pos'][0])+abs(p[1]-e['pos'][1]) for e in enemies), p))
                    else:
                        kind = 'wait'
            actions.append(kind)
            active.send(active.model.command(kind, **args))
            await self.until(clients, lambda: all(c.model.packet['revision'] == packet['revision'] + 1 for c in clients))
            self.assertEqual(clients[0].model.packet, clients[1].model.packet)
            self.assertEqual(clients[0].model.packet, self.session.packet)
        else:
            self.fail('Battle did not terminate within 250 commands')
        terminal = clients[0].model.packet
        self.assertEqual(terminal['state']['status'], 'victory' if aggressive else 'defeat')
        self.assertTrue(any(u['dead'] for u in terminal['state']['units']))
        self.assertGreater(terminal['state']['turn'], 1)
        self.assertTrue(all(not c.model.can_act for c in clients))
        self.assertIn('SHARED ' + terminal['state']['status'].upper(), terminal['result']['summary'])
        clients[0].send(baseline.command(terminal, 'end_phase', 'after_finish'))
        await self.until(clients, lambda: clients[0].model.message == 'Rejected: session_finished')
        self.assertEqual(self.session.packet, terminal)
        self.assertEqual([p['revision'] for p in clients[0].model.observed], [p['revision'] for p in clients[1].model.observed])
        if aggressive:
            self.assertTrue({'move', 'attack', 'wait', 'end_phase'} <= set(actions))
        print(f"Battle {terminal['state']['status']}: {terminal['revision']} commands, turn {terminal['state']['turn']}, identical states after every action")

    async def test_complete_shared_victory_over_network(self):
        await self.battle(True)

    async def test_complete_shared_defeat_over_network(self):
        await self.battle(False)

    async def test_pending_deadline_does_not_replay_and_host_shutdown_detected(self):
        blue, green = await self.clients()
        await self.until((blue, green), lambda: blue.model.can_act)
        blue.model.command('wait', unit='Blue_Captain')  # Outcome deliberately unknown; never sent.
        blue.pending_since = time.monotonic() - 121
        started = time.monotonic()
        with self.assertRaisesRegex(ConnectionError, 'outcome unknown'):
            blue.poll()
        self.assertLess(time.monotonic() - started, 1, 'UI close must not wait for the reader timeout')
        self.assertEqual(self.session.revision, 0)
        self.host.peers['other'].close()
        for _ in range(100):
            try:
                green.poll()
            except (OSError, ValueError):
                break
            await asyncio.sleep(0.005)
        else:
            self.fail('Host-side shutdown not detected')
        self.assertFalse(green.model.can_act)
