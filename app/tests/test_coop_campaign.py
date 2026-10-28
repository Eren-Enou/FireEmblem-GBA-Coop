"""Native live-host continuity, chapter barriers and independent clients."""
import asyncio
from copy import deepcopy
import tempfile
import unittest
from unittest.mock import patch

from app.coop.campaign import OWNERS, PARTIES
from app.coop.client import Connection, Model
from app.coop.protocol import VERSION, ProtocolError, digest, validate_packet, validate_request
from app.coop.server import Session
from app.coop.simulation import Simulation
from app.tests import test_network_coop as network
from app.tests import test_network_playability as playability
from utilities.campaign_playtest import choose


class CampaignAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.sim = Simulation(scenario='campaign')
        self.addCleanup(self.sim.close)
        self.session = Session(self.sim)
        self.number = 0

    def issue(self, team='player', action='wait', connected=('player', 'other'), **args):
        self.number += 1
        return self.session.command(team, network.command(self.session.packet, action,
            'campaign_' + str(self.number), **args), connected)

    def rejected(self, code, **args):
        before = deepcopy(self.session.packet)
        with self.assertRaisesRegex(ProtocolError, '^' + code + '$'):
            self.issue(**args)
        self.assertEqual(self.session.packet, before)
        self.assertEqual(digest(self.session.state_projection()), before['digest'])

    def chapter(self):
        for _ in range(120):
            state = self.session.packet['state']
            if state['status'] != 'playing':
                return state
            kind, args = choose(state, state['phase'])
            self.issue(state['phase'], kind, **args)
        self.fail('Campaign did not reach a chapter result')

    def continue_both(self):
        self.issue(action='ready')
        self.issue('other', 'ready')

    def test_unique_units_parties_and_explicit_ownership(self):
        game = self.sim.game
        self.assertEqual(len(game.units), 7)
        self.assertIsNot(game.parties[PARTIES['player']], game.parties[PARTIES['other']])
        for nid, owner in OWNERS.items():
            unit = game.get_unit(nid)
            self.assertTrue(unit.persistent)
            self.assertFalse(unit.generic)
            self.assertEqual(unit.party, PARTIES[owner])
            self.assertEqual(self.sim.campaign_owner(nid), owner)
            self.assertNotEqual(unit.party, unit.faction)
        self.rejected('not_owner', unit='Green_Captain')
        self.rejected('wrong_phase', team='other', unit='Green_Captain')

    def test_native_object_continuity_two_chapter_victory(self):
        game = self.sim.game
        roster = {nid: game.get_unit(nid) for nid in OWNERS}
        parties = {party: game.parties[party] for party in PARTIES.values()}
        initial = {nid: deepcopy(unit.save()) for nid, unit in roster.items()}
        first = self.chapter()
        self.assertEqual(first['status'], 'intermission')
        self.assertEqual(first['campaign']['completed'], ['alliance'])
        for nid, unit in roster.items():
            self.assertFalse(unit.dead)
            self.assertGreaterEqual(unit.level, 2)
            self.assertNotEqual(unit.wexp, initial[nid]['wexp'])
            self.assertLess(unit.items[0].data['uses'], 30 if 'Healer' in nid else 45)
        old = {nid: deepcopy(unit.save()) for nid, unit in roster.items()}
        items = {i.uid: i for u in roster.values() for i in u.items}
        item_data = {uid: deepcopy(item.data) for uid, item in items.items()}
        red = {u.nid for u in game.units if u.team == 'enemy'}
        self.continue_both()
        loaded = self.session.packet['state']
        self.assertIs(game, self.sim.game)
        self.assertEqual((loaded['width'], loaded['height']), (16, 9))
        self.assertNotEqual(first['terrain'], loaded['terrain'])
        self.assertEqual((loaded['phase'], loaded['turn']), ('player', 1))
        self.assertEqual(loaded['rng'], first['rng'])
        for party, native in parties.items():
            self.assertIs(game.parties[party], native)
        self.assertTrue(red.isdisjoint(game.unit_registry))
        self.assertEqual(sum(u.team == 'enemy' for u in game.units), 3)
        for nid, unit in roster.items():
            self.assertIs(game.get_unit(nid), unit)
            current = unit.save()
            for key in ('nid', 'prefab_nid', 'team', 'party', 'faction', 'klass', 'level', 'exp',
                        'stats', 'growths', 'growth_points', 'stat_cap_modifiers', 'wexp',
                        'items', 'skills', 'dead', '_fields', 'equipped_weapon', 'equipped_accessory'):
                self.assertEqual(current[key], old[nid][key], (nid, key))
            self.assertEqual(unit.get_hp(), unit.get_max_hp())
            self.assertFalse(unit.finished or unit.has_attacked or unit.has_moved)
            for item in unit.items:
                self.assertIs(item, items[item.uid])
                self.assertEqual(item.data, item_data[item.uid])
        self.assertEqual(len(game.unit_registry), 7)
        self.assertEqual(len(game.item_registry), 13)
        final = self.chapter()
        self.assertEqual(final['status'], 'victory')
        self.assertEqual(final['campaign']['completed'], ['alliance', 'holding'])
        self.rejected('not_intermission', action='ready')
        print('CAMPAIGN_VICTORY', self.session.revision, final['turn'])

    def test_both_ready_once_revision_stale_and_no_intermission_actions(self):
        self.rejected('not_intermission', action='ready')
        self.chapter()
        self.rejected('session_finished', action='end_phase')
        packet = self.session.packet
        stale = network.command(packet, 'ready', 'stale_ready')
        self.issue('other', 'ready')  # Readiness is independent of active phase.
        self.assertEqual(self.session.packet['state']['campaign']['ready'], ['other'])
        self.rejected('already_ready', team='other', action='ready')
        with self.assertRaisesRegex(ProtocolError, '^stale_revision$'):
            self.session.command('player', stale, ('player', 'other'))
        request = network.command(self.session.packet, 'ready', 'ready_once')
        self.session.command('player', request, ('player', 'other'))
        loaded = deepcopy(self.session.packet)
        with self.assertRaisesRegex(ProtocolError, '^duplicate_command$'):
            self.session.command('player', request, ('player', 'other'))
        self.assertEqual(self.session.packet, loaded)
        self.assertEqual(self.sim.campaign.completed, ['alliance'])

    def test_disconnect_before_second_ready_preserves_barrier(self):
        self.chapter()
        self.issue(action='ready')
        self.rejected('peer_disconnected', team='other', action='ready', connected=('other',))
        self.assertEqual(self.sim.campaign.index, 0)
        self.issue('other', 'ready')
        self.assertEqual(self.sim.campaign.index, 1)

    def test_dead_characters_persist_without_redeployment_or_equipment_duplication(self):
        from app.engine import action
        self.chapter()
        fallen = []
        for nid in ('Blue_Healer', 'Green_Healer'):
            unit = self.sim.game.get_unit(nid)
            action.do(action.Die(unit))
            fallen.append((unit, unit.items[0]))
        self.session.packet = self.session.make_packet()
        self.continue_both()
        for unit, item in fallen:
            self.assertIs(self.sim.game.get_unit(unit.nid), unit)
            self.assertTrue(unit.dead)
            self.assertIsNone(unit.position)
            self.assertIs(unit.items[0], item)
            self.assertEqual(self.sim.heals(unit), [])
        self.rejected('unit_unavailable', unit='Blue_Healer')

    def test_mana_skill_and_personal_fields_survive_native_cleanup_policy(self):
        from app.data.database.database import DB
        from app.data.database.components import ComponentData
        from app.engine.objects.skill import SkillObject
        self.chapter()
        # A trusted inert permanent skill verifies identity/data retention without
        # changing combat tactics. No external skill/serialization is accepted.
        skill = SkillObject('CampaignTest', 'Oath', '', components=ComponentData([]))
        unit = self.sim.game.get_unit('Green_Captain')
        unit.add_skill(skill)
        self.sim.game.register_skill(skill)
        skill.data['oath'] = 7
        unit.set_field('oath', 'Hill Watch')
        unit.set_mana(3)
        self.session.packet = self.session.make_packet()
        self.continue_both()
        self.assertIn(skill, unit.skills)
        self.assertIs(self.sim.game.get_skill(skill.uid), skill)
        self.assertEqual(skill.data['oath'], 7)
        self.assertEqual(unit.get_field('oath'), 'Hill Watch')
        self.assertEqual(unit.get_mana(), unit.get_max_mana() if DB.constants.value('reset_mana') else 3)

    def test_chapter_one_strength_changes_real_chapter_two_damage(self):
        from app.engine import action
        from app.tests.test_coop_progression import fight
        self.chapter()
        self.continue_both()
        unit = self.sim.game.get_unit('Blue_Captain')
        enemy = self.sim.game.get_unit('holding_Red_1')
        self.assertEqual(unit.stats['STR'], 8)
        action.do(action.Teleport(unit, (10, 3)))
        before = enemy.get_hp()
        fight(self.sim, unit, enemy, script=['hit1', 'miss2', 'end'])
        self.assertEqual(before - enemy.get_hp(), 11)  # Starting STR 7 deals 10.

    def test_shared_army_elimination_blocks_continuation(self):
        from app.engine import action
        for nid in ('Green_Captain', 'Green_Healer'):
            action.do(action.Die(self.sim.game.get_unit(nid)))
        self.session.packet = self.session.make_packet()
        result = self.issue(unit='Blue_Healer')  # Native unit_wait defeat event.
        self.assertEqual(result['state']['status'], 'defeat')
        self.rejected('not_intermission', action='ready')

    def test_tactical_team_change_does_not_transfer_campaign_owner(self):
        from app.engine import action
        unit = self.sim.game.get_unit('Blue_Captain')
        action.do(action.ChangeTeam(unit, 'other'))
        self.session.packet = self.session.make_packet()
        self.issue(action='end_phase')
        self.rejected('not_owner', team='other', unit=unit.nid)
        self.assertEqual(self.sim.campaign_owner(unit.nid), 'player')
        self.assertEqual(unit.party, PARTIES['player'])

    def test_transition_fault_publishes_terminal_last_board_not_partial_level(self):
        self.chapter()
        self.issue(action='ready')
        before = deepcopy(self.session.packet)
        with patch.object(self.sim.game, 'start_level', side_effect=RuntimeError('test transition fault')):
            with self.assertLogs(level='ERROR'):
                result = self.issue('other', 'ready')
        self.assertEqual(result['revision'], before['revision'] + 1)
        self.assertEqual(result['state']['status'], 'fault')
        self.assertEqual(result['state']['units'], [dict(u, moves=[], attacks=[], heals=[]) for u in before['state']['units']])
        self.assertEqual(result['state']['campaign'], before['state']['campaign'])
        validate_packet(result)


class CampaignNetworkTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.sim = Simulation(scenario='campaign')
        self.addCleanup(self.sim.close)

    asyncSetUp = network.TransportTests.asyncSetUp
    asyncTearDown = playability.PlayabilityTests.asyncTearDown
    clients = playability.PlayabilityTests.clients
    until = playability.PlayabilityTests.until

    async def play_chapter(self, clients):
        for _ in range(120):
            packet = self.session.packet
            state = packet['state']
            if state['status'] != 'playing':
                return
            client = clients[0] if state['phase'] == 'player' else clients[1]
            await self.until(clients, lambda: client.model.can_act)
            kind, args = choose(state, state['phase'])
            client.send(client.model.command(kind, **args))
            await self.until(clients, lambda: all(c.model.packet['revision'] == packet['revision']+1 for c in clients))
            self.assertEqual(clients[0].model.packet, self.session.packet)
            self.assertEqual(clients[1].model.packet, self.session.packet)
        self.fail('Network campaign exceeded action limit')

    async def test_full_two_client_campaign_and_intermission_rejoin(self):
        blue, green = await self.clients()
        clients = [blue, green]
        await self.play_chapter(clients)
        self.assertEqual(self.session.packet['state']['status'], 'intermission')
        blue.send(blue.model.command('ready'))
        await self.until(clients, lambda: self.session.packet['state']['campaign']['ready'] == ['player'] and not blue.model.pending)
        barrier = deepcopy(self.session.packet)
        await asyncio.to_thread(green.close)
        await self.until((blue,), lambda: blue.model.peers == ['player'])
        self.assertFalse(blue.model.can_ready)
        green = await asyncio.to_thread(Connection, '127.0.0.1', self.port, self.session.tokens['other'])
        self.addAsyncCleanup(asyncio.to_thread, green.close)
        clients[1] = green
        await self.until(clients, lambda: green.model.can_ready)
        self.assertEqual(green.model.packet, barrier)
        green.send(green.model.command('ready'))
        await self.until(clients, lambda: all(c.model.packet['state']['campaign']['chapter'] == 'holding' for c in clients))
        self.assertEqual(blue.model.packet, green.model.packet)
        await self.play_chapter(clients)
        self.assertEqual(self.session.packet['state']['status'], 'victory')

    async def test_disconnect_during_transition_rejoins_one_committed_result(self):
        blue, green = await self.clients()
        clients = [blue, green]
        await self.play_chapter(clients)
        blue.send(blue.model.command('ready'))
        await self.until(clients, lambda: not blue.model.pending and blue.model.packet['state']['campaign']['ready'] == ['player'])
        revision = self.session.revision
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
            green.send(green.model.command('ready'))
            try:
                await asyncio.wait_for(entered.wait(), 5)
                await asyncio.to_thread(green.close)
                await asyncio.sleep(0.03)
            finally:
                release.set()
            await self.until((blue,), lambda: blue.model.packet['revision'] == revision+1 and blue.model.peers == ['player'])
        rejoined = await asyncio.to_thread(Connection, '127.0.0.1', self.port, self.session.tokens['other'])
        self.addAsyncCleanup(asyncio.to_thread, rejoined.close)
        await self.until((blue, rejoined), lambda: blue.model.can_act)
        self.assertEqual(blue.model.packet, rejoined.model.packet)
        self.assertEqual(self.sim.campaign.completed, ['alliance'])
        self.assertEqual(len(self.sim.game.unit_registry), 7)


class CampaignContractTests(unittest.TestCase):
    def test_ready_has_no_client_campaign_or_army_choice(self):
        request = {'v': VERSION, 'type': 'command', 'session': 'session', 'id': 'ready',
                   'revision': 1, 'phase': 'other', 'digest': 'a'*64, 'action': 'ready'}
        validate_request(request)
        for extra in ({'chapter': 'arbitrary'}, {'team': 'other'}, {'event': 'win_game'}, {'unit': 'Blue_Captain'}):
            with self.assertRaises(ProtocolError):
                validate_request({**request, **extra})
        for version in (1, 2, 3):
            with self.assertRaisesRegex(ProtocolError, 'protocol_version'):
                validate_request({**request, 'v': version})

    def test_campaign_schema_bounds_and_client_readiness_gate(self):
        sim = Simulation(scenario='campaign')
        self.addCleanup(sim.close)
        session = Session(sim)
        for mutate in (
            lambda s: s['campaign'].update(ready=['player', 'player']),
            lambda s: s['campaign'].update(ready=['enemy']),
            lambda s: s['campaign'].update(completed=[{}]),
            lambda s: s['campaign'].update(extra='unexpected'),
            lambda s: s.update(width=65),
            lambda s: s['units'][0].update(equipped=99999),
            lambda s: s['units'][0].update(owner='enemy')):
            packet = deepcopy(session.packet)
            mutate(packet['state'])
            packet['digest'] = digest(packet['state'])
            with self.assertRaises(ProtocolError):
                validate_packet(packet)
        model = Model()
        model.apply({'v': VERSION, 'type': 'welcome', 'team': 'other', 'snapshot': session.packet})
        model.apply({'v': VERSION, 'type': 'peers', 'teams': ['player', 'other']})
        self.assertFalse(model.can_ready)
        packet = deepcopy(session.packet)
        packet['state']['status'] = 'intermission'
        packet['digest'] = digest(packet['state'])
        packet['revision'] = 1
        model.apply(packet)
        self.assertTrue(model.can_ready)  # Phase is Blue; Green may still ready.
        request = model.command('ready')
        self.assertEqual(request['action'], 'ready')
        self.assertFalse(model.can_ready)


class CampaignProcessTests(unittest.TestCase):
    def test_independent_graphical_clients_complete_both_chapters(self):
        from utilities.smoke_network import run_smoke
        with tempfile.TemporaryDirectory(prefix='lt-campaign-test-') as folder:
            result = run_smoke(folder, campaign=True)
            self.assertTrue(result['campaign'])
            self.assertEqual(result['revision'], 38)
            self.assertEqual(result['snapshots_compared'], 39)
