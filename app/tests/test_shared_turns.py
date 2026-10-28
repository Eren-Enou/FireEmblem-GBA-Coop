"""Native shared-round mechanics, concurrency, readiness and presentation."""
import asyncio
from collections import Counter
from copy import deepcopy
import unittest
from unittest.mock import patch

from app.coop.client import Model
from app.coop.protocol import ProtocolError, TEAMS, VERSION, encode
from app.coop.server import Session
from app.coop.shared_turns import SharedSimulation
from app.tests.test_network_coop import command
from app.tests import test_network_coop as baseline
from app.tests import test_network_playability as playability
from app.tests.test_coop_tactics import native_state


class SharedTests(unittest.TestCase):
    def setUp(self):
        self.sim = SharedSimulation(scenario='campaign')
        self.addCleanup(self.sim.close)
        self.session = Session(self.sim)
        self.number = 0

    def issue(self, team, kind='wait', **args):
        self.number += 1
        return self.session.command(team, command(self.session.packet, kind,
            'shared_' + str(self.number), **args), TEAMS)

    def reject(self, reason, team, kind='wait', **args):
        before = native_state(self.sim), deepcopy(self.session.packet)
        with self.assertRaisesRegex(ProtocolError, '^' + reason + '$'):
            self.issue(team, kind, **args)
        self.assertEqual(before, (native_state(self.sim), self.session.packet))

    def test_interleaved_native_healing_moves_ready_and_ai(self):
        game = self.sim.game
        old_red = [(u.nid, u.position, u.get_hp()) for u in game.units if u.team == 'enemy']
        self.reject('not_owner', 'player', unit='Green_Captain')
        self.reject('not_owner', 'other', unit='Blue_Captain')
        self.reject('not_owner', 'other', unit='alliance_Red_1')
        green = game.get_unit('Green_Captain')
        pos = list(self.sim.moves(green)[0])
        # Blue still has all actions when Green moves. Returning the native phase
        # pointer never refreshes Green movement or either healer's spent action.
        self.issue('other', 'move', unit=green.nid, pos=pos)
        self.assertFalse(game.get_unit('Blue_Captain').finished)
        self.reject('illegal_move', 'other', 'move', unit=green.nid, pos=pos)
        self.issue('other', 'heal', unit='Green_Healer', item=103, target='Blue_Captain')
        healer = game.get_unit('Green_Healer')
        self.assertTrue(healer.finished)
        self.assertEqual(healer.items[0].data['uses'], 29)
        self.assertGreater(healer.level, 1)  # Native ExpState crossed 95 XP.
        self.issue('other', 'end_phase')
        self.assertEqual(self.session.packet['state']['turns']['ready'], ['other'])
        self.reject('army_already_ready', 'other', unit=green.nid)
        self.assertEqual(game.turncount, 1)
        self.assertEqual(old_red, [(u.nid, u.position, u.get_hp()) for u in game.units if u.team == 'enemy'])
        self.issue('player', 'wait', unit='Blue_Captain')
        self.assertTrue(healer.finished)
        self.assertTrue(green.has_moved)
        self.issue('player', 'end_phase')
        self.assertEqual(game.turncount, 2)
        self.assertEqual(game.phase.get_current(), 'player')
        self.assertEqual(self.session.packet['state']['turns']['ready'], [])
        self.assertNotEqual(old_red, [(u.nid, u.position, u.get_hp()) for u in game.units if u.team == 'enemy'])
        for unit in game.get_all_units():
            if unit.team in TEAMS:
                self.assertFalse(unit.finished)
                self.assertFalse(unit.has_moved)
                self.assertFalse(unit.has_attacked)
        self.assertEqual(healer.items[0].data['uses'], 29)

    def test_both_cross_army_heals_and_no_repeat(self):
        for team, healer, target, item in (('other', 'Green_Healer', 'Blue_Captain', 103),
                                          ('player', 'Blue_Healer', 'Green_Captain', 101)):
            hp = self.sim.game.get_unit(target).get_hp()
            self.issue(team, 'heal', unit=healer, item=item, target=target)
            self.assertGreater(self.sim.game.get_unit(target).get_hp(), hp)
            self.reject('unit_unavailable', team, 'heal', unit=healer, item=item, target=target)
        self.assertEqual(self.sim.game.turncount, 1)

    def test_native_status_timers_upkeep_endstep_and_trigger_counts(self):
        from app.engine import action, skill_system
        from app.engine.objects.skill import SkillObject
        from app.engine.skill_components.time_components import Time, EndTime
        from app.engine.skill_components.status_components import Regeneration
        from app.data.database.components import ComponentData
        game = self.sim.game
        timers = []
        # Test-only native skill instances; production scenario prefabs unchanged.
        for nid in ('Blue_Healer', 'Green_Healer'):
            unit = game.get_unit(nid)
            action.do(action.SetHP(unit, 10))
            for component in (Time(3), EndTime(3)):
                skill = SkillObject('test_' + component.nid, 'Timer', '', components=ComponentData([component]))
                action.do(action.AddSkill(unit, skill))
                timers.append(skill)
            skill = SkillObject('test_regen', 'Regen', '', components=ComponentData([Regeneration(0.2)]))
            action.do(action.AddSkill(unit, skill))
        up, end, events = Counter(), Counter(), []
        original_up, original_end = skill_system.on_upkeep, skill_system.on_endstep
        trigger = game.events.trigger

        def upkeep(actions, playback, unit):
            up[unit.nid] += 1
            return original_up(actions, playback, unit)

        def endstep(actions, playback, unit):
            end[unit.nid] += 1
            return original_end(actions, playback, unit)

        def observe(event, *args, **kwargs):
            events.append(event.__class__.__name__)
            return trigger(event, *args, **kwargs)

        with patch.object(skill_system, 'on_upkeep', side_effect=upkeep), patch.object(
                skill_system, 'on_endstep', side_effect=endstep), patch.object(game.events, 'trigger', side_effect=observe):
            self.issue('player', 'end_phase')
            self.assertFalse(up or end)
            self.issue('other', 'end_phase')
        for nid in ('Blue_Healer', 'Green_Healer', 'Blue_Captain', 'Green_Captain',
                    'alliance_Red_1', 'alliance_Red_2', 'alliance_Red_3'):
            self.assertEqual(up[nid], 1, nid)
            self.assertEqual(end[nid], 1, nid)
        self.assertEqual([skill.data['turns'] for skill in timers], [2, 2, 2, 2])
        for nid in ('Blue_Healer', 'Green_Healer'):
            self.assertEqual(game.get_unit(nid).get_hp(), 13)
        for name in ('TurnChange', 'OtherTurnChange', 'EnemyTurnChange'):
            self.assertEqual(events.count(name), 1, name)
        self.assertEqual(events.count('PhaseChange'), 3)

    def test_stale_same_revision_never_executes_or_consumes_rng(self):
        stale = command(self.session.packet, 'heal', 'concurrent', unit='Green_Healer', item=103, target='Blue_Captain')
        self.issue('player', 'heal', unit='Blue_Healer', item=101, target='Green_Captain')
        before = native_state(self.sim)
        with self.assertRaisesRegex(ProtocolError, 'stale_revision'):
            self.session.command('other', stale, TEAMS)
        self.assertEqual(native_state(self.sim), before)

    def test_model_keeps_own_pending_until_rejection_and_resync(self):
        model = Model()
        model.apply({'v': VERSION, 'type': 'welcome', 'team': 'other', 'snapshot': self.session.packet})
        model.peers = list(TEAMS)
        self.assertTrue(model.can_act)
        request = model.command('wait', unit='Green_Captain')
        self.issue('player', unit='Blue_Captain')
        model.apply(self.session.packet)
        self.assertEqual(model.pending, request['id'])
        self.assertFalse(model.can_act)
        model.apply({'v': VERSION, 'type': 'reject', 'id': request['id'], 'code': 'stale_revision', 'revision': 1})
        self.assertIsNone(model.pending)
        self.assertTrue(model.syncing)
        self.assertIn('Resyncing', model.feedback)
        model.apply(self.session.packet)
        self.assertTrue(model.can_act)
        self.assertIn('no automatic replay', model.decision_notice)

    def test_checkpoint_and_restore_restriction_before_engine_start(self):
        for key in ('checkpoint_dir', 'restore_dir'):
            with self.assertRaisesRegex(ValueError, 'do not support checkpoints'):
                SharedSimulation(**{key: 'never-created'})
        self.reject('shared_checkpoints_disabled', 'player', 'save_checkpoint')

    def test_matching_id_from_other_army_does_not_acknowledge_pending(self):
        model = Model()
        model.apply({'v': VERSION, 'type': 'welcome', 'team': 'other', 'snapshot': self.session.packet})
        model.peers = list(TEAMS)
        request = model.command('wait', unit='Green_Captain')
        self.session.command('player', command(self.session.packet, 'wait', request['id'], unit='Blue_Captain'), TEAMS)
        model.apply(self.session.packet)
        self.assertEqual(model.pending, request['id'])

    def test_ready_in_either_order_keeps_other_army_available(self):
        self.issue('player', 'end_phase')
        model = Model()
        model.apply({'v': VERSION, 'type': 'welcome', 'team': 'other', 'snapshot': self.session.packet})
        model.peers = list(TEAMS)
        self.assertTrue(model.can_act)
        self.issue('other', unit='Green_Captain')
        self.reject('army_already_ready', 'player', unit='Blue_Captain')
        self.issue('other', 'end_phase')
        self.assertEqual(self.sim.game.turncount, 2)

    def test_terminal_reason_names_eliminated_army(self):
        from app.engine import action
        for nid in ('Green_Captain', 'Green_Healer'):
            action.do(action.Die(self.sim.game.get_unit(nid)))
        self.issue('player', unit='Blue_Captain')
        self.assertEqual(self.session.packet['state']['status'], 'defeat')
        self.assertIn('Green army eliminated', self.session.packet['state']['outcome'])
        self.reject('session_finished', 'player', 'end_phase')


class SharedTransportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.sim = SharedSimulation(scenario='campaign')
        self.addCleanup(self.sim.close)

    asyncSetUp = baseline.TransportTests.asyncSetUp
    asyncTearDown = playability.PlayabilityTests.asyncTearDown
    open = baseline.TransportTests.open
    receive = baseline.TransportTests.receive

    async def test_simultaneous_votes_reject_stale_rejoin_preserves_ready(self):
        blue, bw = await self.open('player')
        initial = (await self.receive(blue, 'welcome'))['snapshot']
        green, gw = await self.open('other')
        await self.receive(green, 'welcome')
        bw.write(encode(command(initial, 'end_phase', 'blue_vote')))
        gw.write(encode(command(initial, 'end_phase', 'green_vote')))
        await asyncio.gather(bw.drain(), gw.drain())
        accepted = await self.receive(blue, 'state')
        self.assertEqual(await self.receive(green, 'state'), accepted)
        winner = accepted['state']['turns']['ready'][0]
        loser_reader = green if winner == 'player' else blue
        self.assertEqual((await self.receive(loser_reader, 'reject'))['code'], 'stale_revision')
        self.assertEqual(self.sim.game.turncount, 1)
        gw.close()
        await gw.wait_closed()
        while (await self.receive(blue, 'peers'))['teams'] != ['player']:
            pass
        before = native_state(self.sim)
        bw.write(encode(command(accepted, 'wait', 'paused', unit='Blue_Captain')))
        await bw.drain()
        self.assertEqual((await self.receive(blue, 'reject'))['code'], 'peer_disconnected')
        self.assertEqual(before, native_state(self.sim))
        joined, jw = await self.open('other')
        self.assertEqual((await self.receive(joined, 'welcome'))['snapshot'], accepted)
        writer = jw if winner == 'player' else bw
        writer.write(encode(command(accepted, 'end_phase', 'explicit_new_vote')))
        await writer.drain()
        final = await self.receive(blue, 'state')
        self.assertEqual(await self.receive(joined, 'state'), final)
        self.assertEqual(final['state']['turn'], 2)
        self.assertEqual(final['state']['turns']['ready'], [])

    async def test_disconnect_during_ai_resolution_finishes_once_and_rejoins(self):
        from app.coop.client import Connection
        from app.tests.test_network_playability import PlayabilityTests
        self.host.heartbeat_interval = 0.1
        self.host.heartbeat_timeout = 0.4
        clients = []
        for team in TEAMS:
            client = await asyncio.to_thread(Connection, '127.0.0.1', self.port, self.session.tokens[team])
            clients.append(client)
            self.addAsyncCleanup(asyncio.to_thread, client.close)
        blue, green = clients

        async def until(predicate, group=clients):
            await PlayabilityTests.until(self, group, predicate)

        await until(lambda: all(c.model.can_act for c in clients))
        blue.send(blue.model.command('end_phase'))
        await until(lambda: all(c.model.packet['revision'] == 1 for c in clients))
        entered, release = asyncio.Event(), asyncio.Event()
        original = self.sim.execute_steps

        def held(*args):
            steps = original(*args)
            yield next(steps)
            entered.set()
            while not release.is_set():
                yield
            yield from steps

        with patch.object(self.sim, 'execute_steps', side_effect=held):
            try:
                green.send(green.model.command('end_phase'))
                await asyncio.wait_for(entered.wait(), 3)
                await asyncio.to_thread(green.close)
                await asyncio.sleep(0.25)
                self.assertFalse(self.host.peers['player'].is_closing())
                self.assertTrue(self.host.peers['other'].is_closing())
            finally:
                release.set()
            await until(lambda: blue.model.packet['revision'] == 2 and blue.model.peers == ['player'], [blue])
        joined = await asyncio.to_thread(Connection, '127.0.0.1', self.port, self.session.tokens['other'])
        try:
            await until(lambda: joined.model.can_act, [blue, joined])
            self.assertEqual(blue.model.packet, joined.model.packet)
            self.assertEqual(joined.model.packet['state']['turn'], 2)
            self.assertEqual(joined.model.packet['state']['turns']['ready'], [])
        finally:
            await asyncio.to_thread(joined.close)
