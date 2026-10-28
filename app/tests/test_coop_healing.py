"""Real LT staff authority, cross-army support, recovery and full battle tests."""
import asyncio
from copy import deepcopy
import tempfile
import unittest
from unittest.mock import patch

from app.coop.protocol import VERSION, ProtocolError, digest, encode, validate_request
from app.coop.server import Session
from app.coop.simulation import Simulation
from app.tests import test_network_coop as network
from app.tests import test_network_playability as playability


class HealingAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.sim = Simulation(scenario='healing')
        self.addCleanup(self.sim.close)
        self.session = Session(self.sim)
        self.counter = 0

    def issue(self, team='player', action='heal', **args):
        self.counter += 1
        return self.session.command(team, network.command(self.session.packet, action,
            'heal_' + str(self.counter), **args), ('player', 'other'))

    def refresh(self):
        self.session.packet = self.session.make_packet()

    def rejected(self, code, team='player', action='heal', **args):
        self.refresh()
        before = deepcopy(self.session.packet)
        with self.assertRaisesRegex(ProtocolError, '^' + code + '$'):
            self.issue(team, action, **args)
        self.assertEqual(self.session.packet, before)
        self.assertEqual(digest(self.session.state_projection()), before['digest'])

    def test_both_cross_army_heals_xp_level_durability_and_action(self):
        for team, healer_id, target_id in (('player', 'Blue_Healer', 'Green_Captain'),
                                           ('other', 'Green_Healer', 'Blue_Captain')):
            if team == 'other':
                self.issue(action='end_phase')
            healer = self.sim.game.get_unit(healer_id)
            target = self.sim.game.get_unit(target_id)
            item = healer.items[0]
            old_wexp = healer.wexp['Staff']
            result = self.issue(team, unit=healer_id, item=item.uid, target=target_id)
            self.assertEqual(target.get_hp(), 27)
            self.assertEqual(item.data['uses'], 29)
            self.assertEqual((healer.level, healer.exp), (2, 6))
            self.assertEqual(healer.wexp['Staff'] - old_wexp, 2)
            self.assertTrue(healer.finished)
            self.assertEqual(target.team, 'other' if team == 'player' else 'player')
            self.assertIn('+11', result['result']['summary'])
            self.assertIn('LEVEL UP', result['result']['summary'])
            self.rejected('unit_unavailable', team, unit=healer_id, item=item.uid, target=target_id)

    def test_same_army_healing_after_movement_and_hp_cap(self):
        for team, healer_id, target_id, destination in (
            ('player', 'Blue_Healer', 'Blue_Captain', [6, 2]),
            ('other', 'Green_Healer', 'Green_Captain', [6, 4])):
            if team == 'other':
                self.issue(action='end_phase')
            target = self.sim.game.get_unit(target_id)
            target.set_hp(target.get_max_hp() - 1)
            self.refresh()
            self.issue(team, 'move', unit=healer_id, pos=destination)
            healer = self.sim.game.get_unit(healer_id)
            self.issue(team, unit=healer_id, item=healer.items[0].uid, target=target_id)
            self.assertEqual(target.get_hp(), target.get_max_hp())
            self.assertTrue(healer.finished)
            self.assertEqual(healer.items[0].data['uses'], 29)

    def test_owner_phase_item_range_target_and_full_hp_rejections(self):
        healer = self.sim.game.get_unit('Blue_Healer')
        staff = healer.items[0].uid
        self.rejected('wrong_phase', 'other', unit='Green_Healer', item=103, target='Blue_Captain')
        for unit in ('Green_Healer', 'Red_1', 'absent'):
            self.rejected('not_owner', unit=unit, item=staff, target='Green_Captain')
        for item in (100, 103, 99999):
            self.rejected('illegal_heal', unit=healer.nid, item=item, target='Green_Captain')
        for target in ('Red_1', 'Green_Healer', 'absent', 'Blue_Healer'):
            self.rejected('illegal_heal', unit=healer.nid, item=staff, target=target)
        from app.engine import action
        action.do(action.Teleport(self.sim.game.get_unit('Blue_Captain'), (2, 3)))
        self.rejected('illegal_heal', unit=healer.nid, item=staff, target='Blue_Captain')
        target = self.sim.game.get_unit('Green_Captain')
        target.set_hp(target.get_max_hp())
        self.rejected('illegal_heal', unit=healer.nid, item=staff, target=target.nid)

    def test_exhaustion_rank_availability_finished_and_attacked(self):
        from app.engine import skill_system
        healer = self.sim.game.get_unit('Blue_Healer')
        item = healer.items[0]
        args = dict(unit=healer.nid, item=item.uid, target='Green_Captain')
        item.data['uses'] = 0
        self.rejected('illegal_heal', **args)
        item.data['uses'] = 30
        healer.wexp['Staff'] = 0
        self.rejected('illegal_heal', **args)
        healer.wexp['Staff'] = 31
        healer.has_attacked = True
        self.rejected('illegal_heal', **args)
        healer.has_attacked = False
        with patch.object(skill_system, 'available', return_value=False):
            self.rejected('illegal_heal', **args)
        with patch.object(skill_system, 'can_select', return_value=False):
            self.rejected('unit_unselectable', **args)

    def test_dead_target_and_no_weapon_or_consumable_tunnel(self):
        from app.engine import action, item_funcs
        healer = self.sim.game.get_unit('Blue_Healer')
        target = self.sim.game.get_unit('Green_Captain')
        action.do(action.Die(target))
        self.rejected('illegal_heal', unit=healer.nid, item=healer.items[0].uid, target=target.nid)
        item = item_funcs.create_item(healer, 'Vulnerary')
        healer.add_item(item)
        healer.set_hp(8)
        self.rejected('illegal_heal', unit=healer.nid, item=item.uid, target=healer.nid)
        fighter = self.sim.game.get_unit('Blue_Captain')
        item = item_funcs.create_item(fighter, 'Heal')
        fighter.add_item(item)
        self.rejected('illegal_heal', unit=fighter.nid, item=item.uid, target=healer.nid)

    def test_mend_uses_real_rank_amount_and_durability(self):
        from app.engine import item_funcs
        healer = self.sim.game.get_unit('Blue_Healer')
        item = item_funcs.create_item(healer, 'Mend')
        healer.add_item(item)
        from app.data.database.database import DB
        required = DB.weapon_ranks.get('D').requirement
        healer.wexp['Staff'] = required - 1
        self.rejected('illegal_heal', unit=healer.nid, item=item.uid, target='Green_Captain')
        healer.wexp['Staff'] = required
        self.refresh()
        self.issue(unit=healer.nid, item=item.uid, target='Green_Captain')
        self.assertEqual(self.sim.game.get_unit('Green_Captain').get_hp(), 36)
        self.assertEqual(item.data['uses'], 19)
        self.assertEqual((healer.level, healer.exp), (2, 7))

    def test_healing_improves_survival_margin_under_real_red_ai(self):
        # First resolve a real enemy round without support.
        self.issue(action='end_phase')
        self.issue('other', 'end_phase')
        unhealed = {u['id']: u['hp'] for u in self.session.packet['state']['units']}
        self.assertLess(unhealed['Blue_Captain'], 16)
        self.assertLessEqual(unhealed['Green_Captain'], 16)
        self.sim.close()
        self.sim = Simulation(scenario='healing')
        self.addCleanup(self.sim.close)
        self.session = Session(self.sim)
        for team, healer, target in (('player', 'Blue_Healer', 'Green_Captain'),
                                     ('other', 'Green_Healer', 'Blue_Captain')):
            unit = self.sim.game.get_unit(healer)
            self.issue(team, unit=healer, item=unit.items[0].uid, target=target)
            self.issue(team, 'end_phase')
        healed = {u['id']: u['hp'] for u in self.session.packet['state']['units']}
        for nid in ('Blue_Captain', 'Green_Captain'):
            self.assertGreater(healed[nid], unhealed[nid])


def battle_action(state, team):
    """Fixture playtest tactics, only commands already exposed to humans."""
    ready = [u for u in state['units'] if u['team'] == team and not u['dead'] and not u['finished']]
    units = {u['id']: u for u in state['units']}
    enemies = [u for u in state['units'] if u['team'] == 'enemy' and not u['dead']]
    if not ready:
        return 'end_phase', {}
    # Heal before taking risks, then let the frontliners fight.
    for healer in ready:
        if healer['heals']:
            choice = min(healer['heals'], key=lambda h: (units[h['target']]['team'] == team, units[h['target']]['hp'] / units[h['target']]['max_hp']))
            return 'heal', {'unit': healer['id'], **choice}
    for unit in ready:
        if state['turn'] > 1 and unit['attacks']:
            choice = min(unit['attacks'], key=lambda a: units[a['target']]['hp'])
            return 'attack', {'unit': unit['id'], **choice}
    if state['turn'] > 1:
        for unit in ready:
            if unit['moves']:
                if 'Healer' in unit['id']:
                    wounded = [u for u in state['units'] if u['team'] in ('player', 'other') and not u['dead'] and u['hp'] < u['max_hp']]
                    destinations = [p for p in unit['moves'] if any(abs(p[0]-u['pos'][0])+abs(p[1]-u['pos'][1]) == 1 for u in wounded)]
                    if destinations:
                        return 'move', {'unit': unit['id'], 'pos': min(destinations, key=lambda p: (sum(abs(p[0]-e['pos'][0])+abs(p[1]-e['pos'][1]) for e in enemies) * -1, p))}
                else:
                    return 'move', {'unit': unit['id'], 'pos': min(unit['moves'], key=lambda p: (min(abs(p[0]-e['pos'][0])+abs(p[1]-e['pos'][1]) for e in enemies), p))}
    return 'wait', {'unit': ready[0]['id']}


class HealingNetworkTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.sim = Simulation(scenario='healing')
        self.addCleanup(self.sim.close)

    asyncSetUp = network.TransportTests.asyncSetUp
    asyncTearDown = playability.PlayabilityTests.asyncTearDown
    clients = playability.PlayabilityTests.clients
    until = playability.PlayabilityTests.until

    async def test_heal_duplicate_stale_forged_rejoin_and_subsequent_combat(self):
        from app.coop.client import Connection
        blue, green = await self.clients()
        clients = [blue, green]
        await self.until(clients, lambda: blue.model.can_act)
        initial = deepcopy(self.session.packet)
        request = blue.model.command('heal', unit='Blue_Healer', item=101, target='Green_Captain')
        blue.send(request)
        await self.until(clients, lambda: all(c.model.packet['revision'] == 1 for c in clients))
        healed = deepcopy(self.session.packet)
        self.assertEqual(blue.model.packet, green.model.packet)
        for code, bad in (('duplicate_command', request), ('stale_revision', {**request, 'id': 'stale_heal'}),
                          ('not_owner', network.command(healed, 'heal', 'stolen', unit='Green_Healer', item=103, target='Blue_Captain'))):
            blue.send(bad)
            await self.until(clients, lambda: blue.model.message == 'Rejected: ' + code)
            self.assertEqual(self.session.packet, healed)
        for extra in ({'amount': 999}, {'hp': 999}, {'exp': 999}, {'team': 'other'}):
            with self.assertRaises(ProtocolError):
                validate_request({**request, **extra})
        await asyncio.to_thread(green.close)
        await self.until((blue,), lambda: blue.model.peers == ['player'])
        green = await asyncio.to_thread(Connection, '127.0.0.1', self.port, self.session.tokens['other'])
        clients[1] = green
        self.addAsyncCleanup(asyncio.to_thread, green.close)
        await self.until(clients, lambda: blue.model.can_act)
        self.assertEqual(green.model.packet, healed)
        green.send({'v': VERSION, 'type': 'sync'})
        await asyncio.sleep(0.03)
        green.poll()
        self.assertEqual(green.model.packet, healed)
        blue.send(blue.model.command('end_phase'))
        await self.until(clients, lambda: green.model.can_act)
        green.send(green.model.command('heal', unit='Green_Healer', item=103, target='Blue_Captain'))
        await self.until(clients, lambda: self.session.revision == 3 and all(c.model.packet['revision'] == 3 for c in clients))
        self.assertEqual(blue.model.packet, green.model.packet)
        self.assertEqual(self.sim.game.get_unit('Blue_Captain').get_hp(), 27)
        green.send(green.model.command('end_phase'))
        await self.until(clients, lambda: blue.model.can_act)
        unit = self.sim.game.get_unit('Blue_Captain')
        self.assertTrue(self.sim.attacks(unit))
        blue.send(blue.model.command('attack', unit=unit.nid, **self.sim.attacks(unit)[0]))
        await self.until(clients, lambda: all(c.model.packet['revision'] == 5 for c in clients))
        self.assertEqual(blue.model.packet, green.model.packet)
        self.assertEqual(blue.model.packet, self.session.packet)

    async def test_legitimate_supported_battle_reaches_shared_victory(self):
        blue, green = await self.clients()
        clients = [blue, green]
        await self.until(clients, lambda: blue.model.can_act)
        by_team = {'player': blue, 'other': green}
        heals = []
        for _ in range(200):
            packet = self.session.packet
            if packet['state']['status'] != 'playing':
                break
            team = packet['state']['phase']
            active = by_team[team]
            await self.until(clients, lambda: active.model.can_act)
            kind, args = battle_action(packet['state'], team)
            if kind == 'heal':
                heals.append((team, args['target']))
            active.send(active.model.command(kind, **args))
            await self.until(clients, lambda: all(c.model.packet['revision'] == packet['revision'] + 1 for c in clients))
            self.assertEqual(blue.model.packet, green.model.packet)
            self.assertEqual(blue.model.packet, self.session.packet)
        self.assertEqual(self.session.packet['state']['status'], 'victory', self.session.packet['result'])
        self.assertIn(('player', 'Green_Captain'), heals)
        self.assertIn(('other', 'Blue_Captain'), heals)
        print('HEALING_VICTORY', self.session.revision, self.session.packet['state']['turn'], 'heals', len(heals))


class HealingUITests(unittest.TestCase):
    def test_selected_item_targets_heal_before_inspection_or_attack(self):
        from app.coop.view import target_choice
        unit = {'inventory': [{'uid': 7}, {'uid': 8}], 'heals': [{'item': 8, 'target': 'ally'}],
                'attacks': [{'item': 7, 'target': 'enemy'}]}
        self.assertEqual(target_choice(unit, {'id': 'ally'}, 1), ('heal', {'item': 8, 'target': 'ally'}))
        self.assertIsNone(target_choice(unit, {'id': 'ally'}, 0))
        self.assertEqual(target_choice(unit, {'id': 'enemy'}, 0)[0], 'attack')
        self.assertIsNone(target_choice(unit, {'id': 'enemy'}, 1))


class HealingProcessTests(unittest.TestCase):
    def test_three_independent_clients_cross_heal_then_fight(self):
        from utilities.smoke_network import run_smoke
        with tempfile.TemporaryDirectory(prefix='lt-healing-test-') as folder:
            result = run_smoke(folder, healing=True)
            self.assertTrue(result['healing'])
            self.assertGreaterEqual(result['snapshots_compared'], 10)
