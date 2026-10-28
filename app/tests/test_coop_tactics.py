"""Native tactical query purity, accuracy, stale proposals and graphical acceptance."""
from copy import deepcopy
import tempfile
import unittest
from unittest.mock import patch

from app.coop.client import Model
from app.coop.protocol import VERSION, ProtocolError, encode, validate_packet
from app.coop.server import Session
from app.coop.simulation import Simulation
from app.coop.tactics import forecast
from app.coop.tactical_view import danger
from app.tests.test_network_coop import command


def native_state(sim):
    from app.engine.objects.item import ItemObject
    from app.engine.objects.skill import SkillObject
    game = sim.game
    return deepcopy({'units': [u.save() for u in game.units],
        'flags': [(u.nid, u.finished, u.has_moved, u.has_attacked, u.movement_left) for u in game.units],
        'items': [i.save() for i in game.item_registry.values()],
        'skills': [s.save() for s in game.skill_registry.values()],
        'rng': sim.snapshot()['rng'], 'next': [ItemObject.next_uid, SkillObject.next_uid],
        'vars': [dict(game.game_vars), dict(game.level_vars)],
        'records': {k: [r.save() for r in v] for k, v in vars(game.records).items()},
        'events': list(game.already_triggered_events), 'turn': game.turncount,
        'phase': game.phase.get_current(), 'actions': len(game.action_log.actions)})


class TacticalTests(unittest.TestCase):
    def setUp(self):
        self.sim = Simulation(scenario='campaign')
        self.addCleanup(self.sim.close)
        self.session = Session(self.sim)

    def adjacent(self, distance=1):
        from app.engine import action, item_funcs
        unit = self.sim.game.get_unit('Blue_Captain')
        target = self.sim.game.get_unit('alliance_Red_1')
        action.do(action.Teleport(target, (5+distance, 2)))
        hand = item_funcs.create_item(unit, 'Hand_Axe')
        self.sim.game.register_item(hand); action.do(action.GiveItem(unit, hand))
        self.session.packet = self.session.make_packet()
        return unit, target, unit.items[0], hand

    def test_queries_leave_full_native_state_rng_revision_and_equipment_unchanged(self):
        unit, target, iron, hand = self.adjacent()
        before = native_state(self.sim)
        packet = deepcopy(self.session.packet)
        for _ in range(3):
            self.assertEqual(self.session.state_projection(), packet['state'])
            self.assertTrue(forecast(unit, hand, target)['supported'])
        self.assertEqual(native_state(self.sim), before)
        self.assertEqual(self.session.packet, packet)
        self.assertEqual(self.session.revision, 0)
        self.assertIs(unit.get_weapon(), iron)
        self.assertLess(len(encode(packet)), 262144)

    def test_threat_native_movement_occupied_stops_and_wall_obstruction(self):
        game = self.sim.game
        red = game.get_unit('alliance_Red_1')
        threat = next(t for t in self.session.packet['state']['tactics']['threats'] if t['unit'] == red.nid)
        expected = game.path_system.get_move_selection(red, force=True, zero_move=True).normal
        expected = {p for p in expected if not game.board.get_unit(p) or p == red.position}
        self.assertEqual({tuple(p) for p in threat['moves']}, expected)
        self.assertNotIn([6, 1], threat['moves'])  # Wall, not a crossing.
        self.assertNotIn([5, 2], threat['moves'])  # Blue captain blocks traversal/stop.
        self.assertNotIn([9, 4], threat['moves'])  # Other Red: traverse allowed, stop forbidden.
        weapon = red.items[0]
        self.assertEqual(threat['weapons'][0]['current'], [list(p) for p in sorted(game.target_system.get_attackable_positions(red, weapon, force=True))])

    def test_hand_axe_native_range_availability_and_death_refresh(self):
        from app.engine import action, item_funcs
        red = self.sim.game.get_unit('alliance_Red_1')
        hand = item_funcs.create_item(red, 'Hand_Axe')
        self.sim.game.register_item(hand); action.do(action.GiveItem(red, hand))
        state = self.session.state_projection()
        threat = next(t for t in state['tactics']['threats'] if t['unit'] == red.nid)
        iron, ranged = threat['weapons']
        self.assertNotIn([7, 2], iron['current']); self.assertIn([7, 2], ranged['current'])
        self.assertEqual(ranged['range'], [1, 2])
        hand.data['uses'] = 0
        threat = next(t for t in self.session.state_projection()['tactics']['threats'] if t['unit'] == red.nid)
        self.assertEqual([w['item'] for w in threat['weapons']], [red.items[0].uid])
        action.do(action.Die(red))
        self.assertNotIn(red.nid, [t['unit'] for t in self.session.state_projection()['tactics']['threats']])

    def test_forecast_native_damage_hit_crit_and_weapon_tradeoff(self):
        from app.engine import combat_calcs
        unit, target, iron, hand = self.adjacent()
        a, b = forecast(unit, iron, target), forecast(unit, hand, target)
        self.assertEqual(a['attack']['damage'], combat_calcs.compute_damage(unit, target, iron, target.get_weapon(), 'attack', (0, 0)))
        self.assertEqual(b['attack']['hit'], combat_calcs.compute_hit(unit, target, hand, target.get_weapon(), 'attack', (0, 0)))
        self.assertEqual(a['attack']['crit'], combat_calcs.compute_crit(unit, target, iron, target.get_weapon(), 'attack', (0, 0)))
        self.assertEqual(a['attack']['damage']-b['attack']['damage'], 1)
        self.assertEqual(a['attack']['hit']-b['attack']['hit'], 15)
        self.assertTrue(a['can_counter'] and b['can_counter'])

    def test_range_two_prevents_iron_counter_and_real_hit_matches_forecast(self):
        from app.engine.utils import ltcache
        unit, target, iron, hand = self.adjacent(2)
        hand.hit.value = 1000; hand.crit.value = 0
        ltcache.alter_state()
        preview = forecast(unit, hand, target)
        self.assertFalse(preview['can_counter']); self.assertIsNone(preview['counter'])
        self.session.packet = self.session.make_packet()
        hp, own_hp = target.get_hp(), unit.get_hp()
        self.session.command('player', command(self.session.packet, 'attack', 'ranged', unit=unit.nid, item=hand.uid, target=target.nid), ('player', 'other'))
        self.assertEqual(hp-target.get_hp(), preview['attack']['damage']*preview['attack']['count'])
        self.assertEqual(unit.get_hp(), own_hp)

    def test_doubling_durability_limit_and_native_strike_results(self):
        from app.engine.utils import ltcache
        unit, target, iron, hand = self.adjacent()
        unit.stats['SPD'] = 25; unit.exp = 0
        target.stats.update(SPD=0, HP=100); target.set_hp(100)
        iron.hit.value = 1000; iron.crit.value = 0
        target.items[0].hit.value = 1000; target.items[0].crit.value = 0
        ltcache.alter_state()
        preview = forecast(unit, iron, target)
        self.assertEqual(preview['attack']['count'], 2)
        iron.data['uses'] = 1
        self.assertEqual(forecast(unit, iron, target)['attack']['count'], 1)
        iron.data['uses'] = 45
        self.session.packet = self.session.make_packet()
        hp, own_hp = target.get_hp(), unit.get_hp()
        self.session.command('player', command(self.session.packet, 'attack', 'double', unit=unit.nid, item=iron.uid, target=target.nid), ('player', 'other'))
        self.assertEqual(hp-target.get_hp(), preview['attack']['damage']*2)
        self.assertEqual(own_hp-unit.get_hp(), preview['counter']['damage']*preview['counter']['count'])
        self.assertEqual(iron.data['uses'], 43)

    def test_defensive_doubling_and_disabled_crit_use_native_rules(self):
        from app.data.database.database import DB
        from app.engine.utils import ltcache
        unit, target, iron, _ = self.adjacent()
        unit.stats['SPD'] = 0; target.stats['SPD'] = 25
        ltcache.alter_state()
        with patch.object(DB.constants.get('def_double'), 'value', True):
            self.assertEqual(forecast(unit, iron, target)['counter']['count'], 2)
        with patch.object(DB.constants.get('def_double'), 'value', False):
            self.assertEqual(forecast(unit, iron, target)['counter']['count'], 1)
        with patch.object(DB.constants.get('crit'), 'value', False):
            self.assertIsNone(forecast(unit, iron, target)['attack']['crit'])

    def test_native_forest_defense_and_avoid_change_forecast(self):
        from app.engine import action
        unit, target, iron, _ = self.adjacent()
        action.do(action.Teleport(unit, (5, 1)))
        action.do(action.Teleport(target, (4, 1)))
        forest = forecast(unit, iron, target)
        action.do(action.Teleport(target, (5, 0)))
        plain = forecast(unit, iron, target)
        self.assertEqual(plain['attack']['damage']-forest['attack']['damage'], 1)
        self.assertEqual(plain['attack']['hit']-forest['attack']['hit'], 20)

    def test_native_terrain_and_path_costs(self):
        from app.engine.movement import movement_funcs
        state = self.session.packet['state']
        forest = state['tactics']['terrain'][1][4]
        self.assertEqual((forest['name'], forest['defense'], forest['avoid']), ('Forest', 1, 20))
        unit = self.sim.game.get_unit('Blue_Healer')
        info = next(i for i in state['tactics']['units'] if i['unit'] == unit.nid)
        self.assertEqual(info['costs'][1][4], movement_funcs.get_mcost(unit, (4, 1)))
        for route in info['routes']:
            path = self.sim.game.path_system.get_path(unit, tuple(route['pos']))
            self.assertEqual(route['cost'], self.sim.game.path_system.get_path_cost(unit, path))
            self.assertEqual(route['left'], unit.movement_left-route['cost'])

    def test_unsupported_complex_forecast_and_fog_fail_closed(self):
        from app.engine import action
        unit, target, _, hand = self.adjacent()
        from app.data.database.difficulty_modes import RNGOption
        with patch.object(self.sim.game.current_mode, 'rng_mode', RNGOption.GRANDMASTER):
            unknown = forecast(unit, hand, target)
            self.assertFalse(unknown['supported'])
            self.assertIn('RNG/combat mode', unknown['note'])
        action.do(action.AddSkill(unit, 'Luna'))
        value = forecast(unit, hand, target)
        self.assertFalse(value['supported']); self.assertIsNone(value['attack'])
        self.sim.game.level_vars['_fog_of_war'] = True
        with self.assertRaisesRegex(ValueError, 'requires no fog'):
            self.session.state_projection()

    def test_tactical_protocol_bounds_references_duplicates_and_forged_requests(self):
        self.adjacent()
        original = deepcopy(self.session.packet)
        for mutate in (
            lambda p: p['state']['tactics']['threats'][0]['moves'].append([True, 0]),
            lambda p: p['state']['tactics']['forecasts'][0].update(item=99999),
            lambda p: p['state']['tactics']['forecasts'][0]['attack'].update(hit=101),
            lambda p: p['state']['tactics']['units'].append(p['state']['tactics']['units'][0]),
            lambda p: p['state']['tactics'].update(status='unavailable')):
            packet = deepcopy(original); mutate(packet)
            with self.assertRaises(ProtocolError): validate_packet(packet)
        bad = command(original, 'preview', 'forged', unit='Green_Captain')
        with self.assertRaisesRegex(ProtocolError, 'unknown_action'):
            self.session.command('player', bad, ('player', 'other'))
        self.assertEqual(self.session.packet, original)

    def test_local_propose_cancel_confirm_and_resync_revision_disconnect_invalidation(self):
        model = Model()
        model.apply({'v': VERSION, 'type': 'welcome', 'team': 'player', 'snapshot': deepcopy(self.session.packet)})
        model.apply({'v': VERSION, 'type': 'peers', 'teams': ['player', 'other']})
        unit = next(u for u in model.packet['state']['units'] if u['id'] == 'Blue_Healer')
        args = {'unit': unit['id'], 'pos': unit['moves'][0]}
        before = native_state(self.sim)
        model.propose('move', **args)
        self.assertIsNone(model.pending)
        model.cancel_decision(); self.assertIsNone(model.decision)
        model.propose('move', **args); model.apply(deepcopy(self.session.packet))
        self.assertIsNone(model.decision)
        model.propose('move', **args)
        model.apply({'v': VERSION, 'type': 'peers', 'teams': ['player']})
        self.assertIsNone(model.decision)
        model.apply({'v': VERSION, 'type': 'peers', 'teams': ['player', 'other']})
        model.propose('move', **args)
        model.decision['revision'] += 1
        with self.assertRaisesRegex(ProtocolError, 'stale_preview'): model.confirm_decision()
        model.cancel_decision(); self.assertEqual(native_state(self.sim), before)
        model.propose('move', **args)
        request = model.confirm_decision()
        self.assertFalse(model.preview_readable)
        result = self.session.command('player', request, ('player', 'other'))
        model.apply(deepcopy(result)); self.assertIsNone(model.decision)
        self.assertTrue(model.preview_readable)
        self.assertEqual(model.decision_notice, 'COMMITTED r1: move')
        self.assertEqual(self.sim.game.get_unit(unit['id']).position, tuple(args['pos']))

    def test_healer_current_position_safe_reachable_crossing_threatened(self):
        state = self.session.packet['state']
        unit = next(u for u in state['units'] if u['id'] == 'Blue_Healer')
        self.assertIn([6, 2], unit['moves'])
        self.assertFalse(danger(state, unit['pos'])[0])
        self.assertTrue(danger(state, [6, 2])[0])


class TacticalDecisionTests(unittest.TestCase):
    def test_native_ai_punishes_exposed_healer_while_allied_healing_protects_banners(self):
        outcomes = []
        for reckless in (False, True):
            sim = Simulation(scenario='campaign')
            try:
                session = Session(sim)
                def issue(team, action, **args):
                    session.command(team, command(session.packet, action, 'demo_'+str(session.revision), **args), ('player', 'other'))
                if reckless: issue('player', 'move', unit='Blue_Healer', pos=[6, 2])
                else: issue('player', 'heal', unit='Blue_Healer', item=101, target='Green_Captain')
                issue('player', 'wait', unit='Blue_Captain'); issue('player', 'end_phase')
                issue('other', 'heal', unit='Green_Healer', item=103, target='Blue_Captain')
                issue('other', 'wait', unit='Green_Captain'); issue('other', 'end_phase')
                healer = sim.game.get_unit('Blue_Healer')
                outcomes.append((healer.get_hp(), healer.dead))
                if not reckless:
                    self.assertFalse(any(sim.game.get_unit(n).dead for n in ('Blue_Captain','Green_Captain')))
            finally: sim.close()
        self.assertEqual(outcomes[0], (18, False))
        self.assertLess(outcomes[1][0], outcomes[0][0])
        print('TACTICAL_COOP_VS_RECKLESS', outcomes)

    def test_complete_graphical_tactical_campaign(self):
        from utilities.smoke_network import run_smoke
        with tempfile.TemporaryDirectory(prefix='lt-tactical-process-') as folder:
            result = run_smoke(folder, tactical=True)
            self.assertTrue(result['tactical'])
            self.assertGreater(result['snapshots_compared'], 35)


class TacticalInputTests(unittest.TestCase):
    def test_move_propose_cancel_then_explicit_confirm(self):
        import pygame
        from app.coop.view import LEFT, TOP, TILE, run
        sim = Simulation(scenario='campaign'); self.addCleanup(sim.close)
        session = Session(sim)
        model = Model()
        model.apply({'v': VERSION, 'type': 'welcome', 'team': 'player', 'snapshot': deepcopy(session.packet)})
        model.peers = ['player', 'other']
        unit = sim.game.get_unit('Blue_Captain')
        destination = [4, 1]  # Native forest: actual movement cost is checked.
        self.assertIn(destination, next(u for u in model.packet['state']['units'] if u['id'] == unit.nid)['moves'])
        click = (pygame.MOUSEBUTTONDOWN, {'button': 1, 'pos': (LEFT+4*TILE+20, TOP+TILE+20)})
        events = [click, (pygame.KEYDOWN, {'key': pygame.K_ESCAPE}), click,
                  (pygame.KEYDOWN, {'key': pygame.K_RETURN})]
        test = self
        class LocalConnection:
            security = 'Local SDL tactical acceptance'
            def __init__(self): self.model=model; self.frame=0; self.sent=[]
            def poll(self):
                self.frame += 1
                if self.frame <= 4:
                    if self.frame == 2:
                        test.assertIsNotNone(model.decision); test.assertEqual(session.revision, 0)
                    if self.frame == 3:
                        test.assertIsNone(model.decision); test.assertEqual(session.revision, 0)
                    pygame.event.post(pygame.event.Event(*events[self.frame-1]))
            def send(self, request):
                self.sent.append(request['action'])
                test.assertEqual(self.frame, 4)
                model.apply(deepcopy(session.command('player', request, ('player', 'other'))))
            def close(self): pass
        connection = LocalConnection()
        run(connection, script=[{'action': 'wait_revision', 'revision': 1}], timeout=5)
        self.assertEqual(connection.sent, ['move'])
        self.assertEqual(unit.position, tuple(destination))

    def test_attack_click_waits_for_confirmation(self):
        import pygame
        from app.coop.view import LEFT, TOP, TILE, run
        from app.engine import action
        sim = Simulation(scenario='campaign'); self.addCleanup(sim.close)
        action.do(action.Teleport(sim.game.get_unit('alliance_Red_1'), (6, 2)))
        session = Session(sim)
        model = Model()
        model.apply({'v': VERSION, 'type': 'welcome', 'team': 'player', 'snapshot': deepcopy(session.packet)})
        model.peers = ['player', 'other']
        test = self
        class LocalConnection:
            security = 'Local SDL tactical acceptance'
            def __init__(self): self.model=model; self.frame=0
            def poll(self):
                self.frame += 1
                if self.frame == 1:
                    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                        pos=(LEFT+6*TILE+20, TOP+2*TILE+20)))
                if self.frame == 2:
                    test.assertEqual(session.revision, 0); test.assertIsNotNone(model.decision)
                    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
            def send(self, request):
                test.assertEqual(request['action'], 'attack'); test.assertEqual(self.frame, 2)
                model.apply(deepcopy(session.command('player', request, ('player', 'other'))))
            def close(self): pass
        run(LocalConnection(), script=[{'action': 'wait_revision', 'revision': 1}], timeout=5)
        self.assertTrue(sim.game.get_unit('Blue_Captain').finished)
