"""Contract, real LT authority, real TCP recovery and three-process acceptance."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.coop.client import Connection, Model
from app.coop.protocol import (MAX_FRAME, VERSION, ProtocolError, decode, digest, encode,
                               validate_packet, validate_request)
from app.coop.server import Host, Session
from app.coop.simulation import Simulation


def command(packet, action='wait', request_id='request_1', **kwargs):
    return {'v': VERSION, 'type': 'command', 'session': packet['session'], 'id': request_id,
            'revision': packet['revision'], 'phase': packet['state']['phase'],
            'digest': packet['digest'], 'action': action, **kwargs}


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.sim = Simulation()
        self.addCleanup(self.sim.close)
        self.session = Session(self.sim)
        self.number = 0

    def issue(self, team='player', action='wait', **kwargs):
        self.number += 1
        request = command(self.session.packet, action, 'request_' + str(self.number), **kwargs)
        return self.session.command(team, request, ('player', 'other'))

    def unchanged_rejection(self, code, team='player', action='wait', **kwargs):
        before = deepcopy(self.session.packet)
        with self.assertRaisesRegex(ProtocolError, '^' + code + '$'):
            self.issue(team, action, **kwargs)
        self.assertEqual(self.session.packet, before)
        self.assertEqual(digest(self.sim.snapshot()), before['digest'])

    def test_only_assigned_active_army_can_command(self):
        self.unchanged_rejection('not_owner', unit='Green_Captain')
        self.unchanged_rejection('not_owner', unit='Red_1')
        self.unchanged_rejection('not_owner', unit='nonexistent')
        self.unchanged_rejection('wrong_phase', team='other', unit='Green_Captain')

    def test_illegal_moves_and_second_movement_are_rejected(self):
        for pos in ([7, 2], [4, 3], [14, 9], [2, 3]):
            self.unchanged_rejection('illegal_move', action='move', unit='Blue_Captain', pos=pos)
        self.issue(action='move', unit='Blue_Captain', pos=[7, 3])
        self.assertEqual(self.sim.game.get_unit('Blue_Captain').position, (7, 3))
        self.unchanged_rejection('illegal_move', action='move', unit='Blue_Captain', pos=[6, 3])

    def test_real_movement_and_combat_preserve_engine_durability_and_rng(self):
        self.issue(action='move', unit='Blue_Captain', pos=[7, 3])
        self.issue(action='end_phase')
        self.issue('other', 'move', unit='Green_Captain', pos=[9, 3])
        before = deepcopy(self.session.packet['state'])
        attacker = self.sim.game.get_unit('Green_Captain')
        choice = self.sim.attacks(attacker)[0]
        result = self.issue('other', 'attack', unit=attacker.nid, **choice)
        after = result['state']
        self.assertNotEqual(before['rng']['combat'], after['rng']['combat'])
        old = {u['id']: u for u in before['units']}
        new = {u['id']: u for u in after['units']}
        self.assertLess(new['Red_1']['hp'], old['Red_1']['hp'])
        self.assertLess(new[attacker.nid]['hp'], old[attacker.nid]['hp'])
        self.assertLess(new[attacker.nid]['inventory'][0]['uses'], old[attacker.nid]['inventory'][0]['uses'])
        self.assertTrue(new[attacker.nid]['finished'])
        self.assertEqual(result['revision'], 4)

    def test_attack_rejects_wrong_inventory_allies_and_range(self):
        item = self.sim.game.get_unit('Blue_Captain').items[0].uid
        wrong_item = self.sim.game.get_unit('Blue_Guard').items[0].uid
        for uid, target in ((item, 'Green_Captain'), (item, 'Red_1'),
                            (wrong_item, 'Red_1'), (123456, 'Red_1')):
            self.unchanged_rejection('illegal_attack', action='attack', unit='Blue_Captain', item=uid, target=target)

    def test_wait_finishes_unit_once(self):
        self.issue(unit='Blue_Guard')
        self.assertTrue(self.sim.game.get_unit('Blue_Guard').finished)
        self.unchanged_rejection('unit_unavailable', unit='Blue_Guard')

    def test_red_ai_runs_on_host_and_round_increments_once(self):
        self.issue(action='end_phase')
        self.assertEqual(self.session.packet['state']['phase'], 'other')
        self.assertEqual(self.session.packet['state']['turn'], 1)
        before = deepcopy(self.session.packet['state']['units'])
        result = self.issue('other', 'end_phase')
        self.assertEqual((result['state']['phase'], result['state']['turn']), ('player', 2))
        self.assertTrue(any(old['pos'] != new['pos'] for old, new in zip(before, result['state']['units']) if old['team'] == 'enemy'))

    def test_stale_duplicate_forged_and_desynchronized_commands(self):
        old = command(self.session.packet, unit='Blue_Captain')
        self.session.command('player', old, ('player', 'other'))
        before = deepcopy(self.session.packet)
        tests = [('duplicate_command', old),
                 ('stale_revision', {**old, 'id': 'stale'}),
                 ('wrong_session', {**command(before, request_id='forged_session', unit='Blue_Guard'), 'session': 'forged'}),
                 ('state_mismatch', {**command(before, request_id='bad_digest', unit='Blue_Guard'), 'digest': '0' * 64}),
                 ('stale_phase', {**command(before, request_id='bad_phase', unit='Blue_Guard'), 'phase': 'other'})]
        for code, request in tests:
            with self.subTest(code=code), self.assertRaisesRegex(ProtocolError, '^' + code + '$'):
                self.session.command('player', request, ('player', 'other'))
        self.assertEqual(before, self.session.packet)
        self.assertEqual(before['digest'], digest(self.sim.snapshot()))

    def test_peer_disconnect_pauses_commands(self):
        request = command(self.session.packet, unit='Blue_Captain')
        with self.assertRaisesRegex(ProtocolError, 'peer_disconnected'):
            self.session.command('player', request, ('player',))
        self.assertEqual(self.session.revision, 0)

    def test_engine_fault_stops_session_without_claiming_rejection(self):
        with patch.object(self.sim, 'execute', side_effect=RuntimeError('test fault')):
            with self.assertLogs(level='ERROR'):
                packet = self.issue(unit='Blue_Captain')
        self.assertEqual(packet['state']['status'], 'fault')
        self.assertEqual(packet['revision'], 1)
        self.unchanged_rejection('session_finished', unit='Blue_Guard')

    def test_shared_victory_retains_terminal_board(self):
        from app.engine import action
        from app.events import triggers
        for unit in self.sim.units:
            if unit.team == 'enemy':
                action.do(action.Die(unit))
        self.sim.game.events.trigger(triggers.PhaseChange('player'))
        self.sim.settle()
        packet = self.session.make_packet()
        self.assertEqual(packet['state']['status'], 'victory')
        self.assertEqual(len(packet['state']['units']), 7)
        self.assertIsNotNone(self.sim.game.level)
        self.session.packet = packet
        self.unchanged_rejection('session_finished', unit='Blue_Guard')

    def test_shared_green_defeat_retains_terminal_board(self):
        from app.engine import action
        from app.events import triggers
        for unit in self.sim.units:
            if unit.team == 'other':
                action.do(action.Die(unit))
        self.sim.game.events.trigger(triggers.PhaseChange('other'))
        self.sim.settle()
        self.assertEqual(self.sim.snapshot()['status'], 'defeat')


class ContractAndModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sim = Simulation()
        try:
            cls.packet = Session(sim).packet
        finally:
            sim.close()

    def model(self):
        model = Model()
        model.apply({'v': VERSION, 'type': 'welcome', 'team': 'player', 'snapshot': deepcopy(self.packet)})
        model.apply({'v': VERSION, 'type': 'peers', 'teams': ['player', 'other']})
        return model

    def test_roundtrip_and_digest_ignore_dictionary_insertion_order(self):
        self.assertEqual(decode(encode(self.packet)), self.packet)
        state = self.packet['state']
        self.assertEqual(digest(state), digest(dict(reversed(list(state.items())))))

    def test_invalid_json_and_framing(self):
        for data in (b'not json\n', b'{"v":1,"v":1}\n', b'{"x":NaN}\n',
                     b'{"x":Infinity}\n', b'[]\n', b'{}', b'\xff\n',
                     b' ' * MAX_FRAME + b'\n', b'[' * 2000 + b']' * 2000 + b'\n'):
            with self.subTest(data_length=len(data)), self.assertRaises(ProtocolError):
                decode(data)

    def test_strict_commands_reject_spoofed_fields_bool_and_objects(self):
        base = command(self.packet, 'move', unit='Blue_Captain', pos=[3, 3])
        for changes in ({'team': 'other'}, {'v': True}, {'v': 2}, {'revision': True},
                        {'revision': -1}, {'pos': [True, 0]}, {'pos': [1.5, 0]},
                        {'pos': [0, 64]}, {'unit': {'nid': 'Blue_Captain'}}, {'action': '__reduce__'},
                        {'id': '../file'}, {'digest': 'not a hash'}):
            with self.subTest(changes=changes), self.assertRaises(ProtocolError):
                validate_request({**base, **changes})

    def test_bad_snapshot_hash_and_schema_cannot_replace_client_state(self):
        model = self.model()
        before = deepcopy(model.packet)
        invalid = deepcopy(before)
        invalid['state']['units'][0]['hp'] -= 1
        with self.assertRaisesRegex(ProtocolError, 'digest_mismatch'):
            model.apply(invalid)
        self.assertEqual(model.packet, before)
        invalid['state']['units'][0]['hp'] = 'arbitrary'
        invalid['digest'] = digest(invalid['state'])
        with self.assertRaises(ProtocolError):
            model.apply(invalid)
        self.assertEqual(model.packet, before)

    def test_revision_and_session_consistency(self):
        model = self.model()
        newer = deepcopy(model.packet)
        newer['revision'] += 1
        model.apply(newer)
        model.apply(deepcopy(self.packet))
        self.assertEqual(model.packet['revision'], 1)
        conflict = deepcopy(newer)
        conflict['state']['units'][0]['hp'] -= 1
        conflict['digest'] = digest(conflict['state'])
        with self.assertRaisesRegex(ProtocolError, 'conflicting_revision'):
            model.apply(conflict)
        with self.assertRaisesRegex(ProtocolError, 'wrong_session'):
            model.apply({**newer, 'session': 'another_session'})

    def test_client_waits_for_peer_turn_pending_and_resync(self):
        model = self.model()
        self.assertTrue(model.can_act)
        request = model.command('wait', unit='Blue_Captain')
        self.assertFalse(model.can_act)
        model.apply({'v': 1, 'type': 'reject', 'id': request['id'], 'code': 'state_mismatch', 'revision': 0})
        self.assertTrue(model.syncing)
        self.assertFalse(model.can_act)
        model.apply(deepcopy(self.packet))
        self.assertTrue(model.can_act)
        model.apply({'v': 1, 'type': 'peers', 'teams': ['player']})
        self.assertFalse(model.can_act)


class TransportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.sim = Simulation()
        self.addCleanup(self.sim.close)

    async def asyncSetUp(self):
        self.session = Session(self.sim)
        self.host = Host(self.session)
        self.server = await self.host.listen(0)
        self.port = self.server.sockets[0].getsockname()[1]
        self.writers = []

    async def asyncTearDown(self):
        for writer in self.writers:
            writer.close()
        for writer in self.writers:
            try:
                await writer.wait_closed()
            except OSError:
                pass
        self.server.close()
        await self.server.wait_closed()
        for _ in range(100):
            if not self.host.peers:
                break
            await asyncio.sleep(0.005)

    async def open(self, team=None, token=None):
        reader, writer = await asyncio.open_connection('127.0.0.1', self.port)
        self.writers.append(writer)
        if team or token:
            writer.write(encode({'v': 1, 'type': 'hello', 'token': token or self.session.tokens[team]}))
            await writer.drain()
        return reader, writer

    async def receive(self, reader, kind):
        for _ in range(20):
            data = await asyncio.wait_for(reader.readline(), 3)
            self.assertTrue(data, 'Unexpected EOF')
            packet = decode(data)
            if packet['type'] == kind:
                return packet
        self.fail('Expected packet not received: ' + kind)

    async def test_authentication_duplicate_seat_and_malformed_payloads(self):
        for token in ('wrong', '\u2603'):
            reader, _ = await self.open(token=token)
            self.assertEqual((await self.receive(reader, 'error'))['code'], 'authentication_failed')
        blue, _ = await self.open('player')
        self.assertEqual((await self.receive(blue, 'welcome'))['team'], 'player')
        duplicate, _ = await self.open('player')
        self.assertEqual((await self.receive(duplicate, 'error'))['code'], 'seat_in_use')
        for raw in (b'{"v":2,"type":"hello","token":"x"}\n', b'not_json\n',
                    b'{"v":1,"v":1}\n', b'x' * (MAX_FRAME + 1) + b'\n'):
            reader, writer = await self.open()
            writer.write(raw)
            await writer.drain()
            self.assertEqual((await self.receive(reader, 'error'))['type'], 'error')
        green, _ = await self.open('other')
        self.assertEqual((await self.receive(green, 'welcome'))['team'], 'other')
        self.assertEqual(self.session.revision, 0)

    async def test_disconnect_rejoin_and_authoritative_resync(self):
        blue, bw = await self.open('player')
        initial = (await self.receive(blue, 'welcome'))['snapshot']
        green, gw = await self.open('other')
        await self.receive(green, 'welcome')
        bw.write(encode(command(initial, unit='Blue_Captain')))
        await bw.drain()
        accepted = await self.receive(blue, 'state')
        self.assertEqual(await self.receive(green, 'state'), accepted)
        gw.close()
        await gw.wait_closed()
        while (await self.receive(blue, 'peers'))['teams'] != ['player']:
            pass
        bw.write(encode(command(accepted, request_id='paused', unit='Blue_Guard')))
        await bw.drain()
        self.assertEqual((await self.receive(blue, 'reject'))['code'], 'peer_disconnected')
        rejoined, rw = await self.open('other')
        welcome = await self.receive(rejoined, 'welcome')
        self.assertEqual(welcome['team'], 'other')
        self.assertEqual(welcome['snapshot'], accepted)
        rw.write(encode({'v': 1, 'type': 'sync'}))
        await rw.drain()
        self.assertEqual(await self.receive(rejoined, 'state'), accepted)

    async def test_fragmented_delayed_commands_duplicates_and_stale_rejection(self):
        blue, bw = await self.open('player')
        initial = (await self.receive(blue, 'welcome'))['snapshot']
        green, _ = await self.open('other')
        await self.receive(green, 'welcome')
        request = command(initial, 'move', unit='Blue_Captain', pos=[7, 3])
        payload = encode(request)
        for part in (payload[:8], payload[8:35], payload[35:]):
            bw.write(part)
            await bw.drain()
            await asyncio.sleep(0.02)
        accepted = await self.receive(blue, 'state')
        self.assertEqual(await self.receive(green, 'state'), accepted)
        for code, data in (('duplicate_command', request),
                           ('stale_revision', {**request, 'id': 'late'}),
                           ('not_owner', command(accepted, request_id='steal_green', unit='Green_Captain')),
                           ('state_mismatch', {**command(accepted, request_id='corrupt', unit='Blue_Guard'), 'digest': '0' * 64})):
            bw.write(encode(data))
            await bw.drain()
            self.assertEqual((await self.receive(blue, 'reject'))['code'], code)
        bw.write(encode({'v': 1, 'type': 'sync'}))
        await bw.drain()
        self.assertEqual(await self.receive(blue, 'state'), accepted)
        self.assertEqual(self.session.revision, 1)

    async def test_real_client_automatically_recovers_corrupt_snapshot(self):
        blue = await asyncio.to_thread(Connection, '127.0.0.1', self.port, self.session.tokens['player'])
        green = await asyncio.to_thread(Connection, '127.0.0.1', self.port, self.session.tokens['other'])

        async def until(predicate):
            for _ in range(600):
                blue.poll()
                green.poll()
                if predicate():
                    return
                await asyncio.sleep(0.005)
            self.fail('Client recovery did not reach expected state')

        try:
            await until(lambda: blue.model.can_act)
            original_send = self.host.send
            corrupted = False
            blue_states = 0

            async def one_corrupt_packet(writer, packet):
                nonlocal corrupted, blue_states
                if writer is self.host.peers.get('player') and packet['type'] == 'state':
                    blue_states += 1
                    if not corrupted:
                        corrupted = True
                        packet = deepcopy(packet)
                        packet['state']['units'][0]['hp'] -= 1
                await original_send(writer, packet)

            with patch.object(self.host, 'send', side_effect=one_corrupt_packet):
                blue.send(blue.model.command('move', unit='Blue_Captain', pos=[7, 3]))
                await until(lambda: blue.model.packet['revision'] == 1 and green.model.packet['revision'] == 1)
            self.assertTrue(corrupted)
            self.assertEqual(blue_states, 2, 'Expected corrupt packet followed by resync packet')
            self.assertEqual(blue.model.packet, green.model.packet)
            self.assertEqual(blue.model.packet, self.session.packet)
            self.assertFalse(blue.model.syncing)
            self.assertEqual(self.session.revision, 1, 'Resync must not execute another command')
        finally:
            await asyncio.to_thread(blue.close)
            await asyncio.to_thread(green.close)


class IndependentProcessTests(unittest.TestCase):
    def test_host_and_two_independent_rendering_clients(self):
        from utilities.smoke_network import run_smoke
        with tempfile.TemporaryDirectory(prefix='lt-network-test-') as folder:
            result = run_smoke(folder)
            self.assertGreaterEqual(result['snapshots_compared'], 10)
            self.assertEqual(result['revision'], result['snapshots_compared'] - 1)
            for name in ('blue', 'green'):
                self.assertTrue((Path(result['folder']) / (name + '.png')).read_bytes().startswith(b'\x89PNG'))
