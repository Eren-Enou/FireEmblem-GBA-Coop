"""Real LT progression, policy boundaries, and socket-driven level-up recovery."""
import asyncio
from contextlib import contextmanager
from copy import deepcopy
import unittest
from unittest.mock import patch

from app.coop.protocol import VERSION, ProtocolError, decode, digest, encode, validate_packet
from app.coop.simulation import Simulation
from app.tests import test_network_coop as network
from app.tests import test_network_playability as playability


@contextmanager
def combat_fixture(team, method='Fixed', exp=0, coop=True, defending=False):
    sim = Simulation(seed=0, growth_method=method)
    try:
        from app.engine import action
        from app.data.database.database import DB
        from app.utilities import static_random
        if team == 'other':
            sim.execute('player', {'action': 'end_phase'})
        unit = sim.game.get_unit('Blue_Captain' if team == 'player' else 'Green_Captain')
        enemy = sim.game.get_unit('Red_1')
        action.do(action.Teleport(unit, (9, 3)))
        action.do(action.SetExp(unit, exp))
        if not coop:
            sim.game.game_vars.pop('_human_teams')
        if defending:
            sim.game.phase.current = DB.teams.index('enemy')
        static_random.set_combat_random_state(0)
        yield sim, unit, enemy
    finally:
        sim.close()


def fight(sim, unit, enemy, defending=False, script=None):
    from app.engine.combat import interaction
    attacker, target = (enemy, unit) if defending else (unit, enemy)
    interaction.start_combat(attacker, target.position, attacker.get_weapon(),
                             skip=True, event_combat=True, script=script)
    sim.settle()


def give_skill(unit, components):
    from app.data.database.components import ComponentData
    from app.engine.objects.skill import SkillObject
    unit.add_skill(SkillObject('ProgressionTest', 'Progression test', '', components=ComponentData(components)))


class CombatProgressionTests(unittest.TestCase):
    def compare(self, **options):
        results = []
        for team in ('player', 'other'):
            with combat_fixture(team, **options) as (sim, unit, enemy):
                before = unit.exp, unit.wexp['Axe']
                fight(sim, unit, enemy, defending=options.get('defending', False), script=['hit1', 'hit2', 'end'])
                results.append((unit.exp - before[0], unit.wexp['Axe'] - before[1], unit.get_hp(), enemy.get_hp(), enemy.exp))
        self.assertEqual(results[0], results[1])
        return results[0]

    def test_equal_attack_xp_and_wexp(self):
        xp, wexp, hp, enemy_hp, red_exp = self.compare()
        self.assertEqual((xp, hp, enemy_hp, red_exp), (10, 18, 18, 0))
        self.assertGreater(wexp, 0)

    def test_defending_counter_xp_during_red_phase(self):
        xp, wexp, hp, enemy_hp, red_exp = self.compare(defending=True)
        self.assertEqual((xp, hp, enemy_hp, red_exp), (10, 18, 18, 0))
        self.assertGreater(wexp, 0)

    def test_misses_follow_existing_minimum_exp(self):
        from app.data.database.database import DB
        results = []
        for team in ('player', 'other'):
            with combat_fixture(team) as (sim, unit, enemy):
                fight(sim, unit, enemy, script=['miss1', 'miss2', 'end'])
                results.append(unit.exp)
                self.assertEqual(unit.exp, DB.constants.value('min_exp'))
                self.assertEqual(unit.get_hp(), 28)
                self.assertEqual(enemy.get_hp(), 28)
        self.assertEqual(results[0], results[1])

    def test_kill_bonus_and_counter_kill(self):
        rewards = []
        for defending in (False, True):
            for team in ('player', 'other'):
                with combat_fixture(team, defending=defending) as (sim, unit, enemy):
                    enemy.set_hp(1)
                    fight(sim, unit, enemy, defending, ['hit1', 'hit2', 'end'])
                    rewards.append(unit.exp)
                    self.assertTrue(enemy.dead or enemy.is_dying)
                    self.assertGreater(unit.exp, 10)
        self.assertEqual(len(set(rewards)), 1)

    def test_unarmed_defender_follows_blue_zero_exp_rule(self):
        for team in ('player', 'other'):
            with combat_fixture(team, defending=True) as (sim, unit, enemy):
                for item in list(unit.items):
                    unit.remove_item(item)
                fight(sim, unit, enemy, True, ['hit1', 'end'])
                self.assertEqual(unit.exp, 0)
                self.assertLess(unit.get_hp(), unit.get_max_hp())
                self.assertEqual(enemy.exp, 0)

    def test_xp_modifiers_and_fractional_weapon_xp(self):
        for team in ('player', 'other'):
            with combat_fixture(team) as (sim, unit, enemy):
                from app.engine.skill_components.base_components import ExpMultiplier, WexpMultiplier
                give_skill(unit, [ExpMultiplier(2), WexpMultiplier(0.5)])
                before = unit.wexp['Axe']
                fight(sim, unit, enemy, script=['hit1', 'hit2', 'end'])
                self.assertEqual(unit.exp, 20)
                self.assertEqual(unit.wexp['Axe'] - before, 0.5)
                packet = network.Session(sim).packet
                shown = next(u for u in packet['state']['units'] if u['id'] == unit.nid)
                self.assertEqual(shown['wexp']['Axe'], str(unit.wexp['Axe']))
                self.assertEqual(decode(encode(packet)), packet)

    def test_mana_on_hit_uses_player_queue_and_existing_cap(self):
        for team in ('player', 'other'):
            with combat_fixture(team) as (sim, unit, enemy):
                from app.engine import equations
                from app.engine.skill_components.special_components import ManaOnHit
                give_skill(unit, [ManaOnHit(15)])
                unit.current_mana = 0
                with patch.object(equations.parser, 'mana', return_value=10, create=True):
                    fight(sim, unit, enemy, script=['hit1', 'hit2', 'end'])
                    self.assertEqual(unit.get_mana(), 10)
                    self.assertFalse(sim.game.mana_instance)
                    shown = next(u for u in sim.snapshot()['units'] if u['id'] == unit.nid)
                    self.assertEqual((shown['mana'], shown['max_mana']), (10, 10))

    def test_threshold_fixed_random_dynamic_real_level_up(self):
        for method in ('Fixed', 'Random', 'Dynamic'):
            for team in ('player', 'other'):
                with self.subTest(method=method, team=team), combat_fixture(team, method, 95) as (sim, unit, enemy):
                    from app.engine import unit_funcs
                    from app.data.database.database import DB
                    DB.constants.get('enemy_leveling').value = 'Fixed' if method != 'Fixed' else 'Random'
                    self.assertEqual(unit_funcs.get_leveling_method(unit), method)
                    self.assertEqual(unit_funcs.get_leveling_method(enemy), DB.constants.value('enemy_leveling'))
                    before = dict(unit.stats)
                    points = dict(unit.growth_points)
                    expected = unit_funcs.get_next_level_up(unit, unit.get_internal_level())
                    expected_points = dict(unit.growth_points)
                    unit.growth_points = points
                    fight(sim, unit, enemy, script=['hit1', 'hit2', 'end'])
                    self.assertEqual((unit.level, unit.exp), (2, 5))
                    self.assertEqual(unit.stats, {key: value + expected[key] for key, value in before.items()})
                    self.assertEqual(unit.growth_points, expected_points)
                    self.assertTrue(any(expected.values()))
                    self.assertEqual(enemy.level, 1)
                    # Reaching the free boundary again must never apply growth twice.
                    after = deepcopy(sim.snapshot())
                    sim.settle()
                    self.assertEqual(sim.snapshot(), after)

    def test_below_threshold_does_not_level(self):
        for team in ('player', 'other'):
            with combat_fixture(team, exp=89) as (sim, unit, enemy):
                before = dict(unit.stats)
                fight(sim, unit, enemy, script=['hit1', 'hit2', 'end'])
                self.assertEqual((unit.level, unit.exp), (1, 99))
                self.assertEqual(unit.stats, before)

    def test_multiple_combat_levels_and_class_stat_caps(self):
        for team in ('player', 'other'):
            with combat_fixture(team) as (sim, unit, enemy):
                from app.data.database.database import DB
                from app.engine.skill_components.base_components import ExpMultiplier
                klass = DB.classes.get(unit.klass)
                klass.max_level = 3
                unit._tags.add('NoAutoPromote')
                unit.stats['HP'] = unit.get_stat_cap('HP')
                give_skill(unit, [ExpMultiplier(1000)])
                for expected_level in (2, 3, 3):
                    # Refresh only fixture HP; rewards/levels/stats remain LT's.
                    enemy.set_hp(enemy.get_max_hp())
                    unit.set_hp(unit.get_max_hp())
                    fight(sim, unit, enemy, script=['hit1', 'miss2', 'end'])
                    self.assertEqual((unit.level, unit.exp), (expected_level, 0))
                    self.assertEqual(unit.stats['HP'], unit.get_stat_cap('HP'))
                self.assertEqual(enemy.level, 1)
                self.assertEqual(enemy.exp, 0)

    def test_new_strength_changes_subsequent_real_combat_damage(self):
        for team in ('player', 'other'):
            with combat_fixture(team, exp=95) as (sim, unit, enemy):
                hp = enemy.get_hp()
                fight(sim, unit, enemy, script=['hit1', 'miss2', 'end'])
                first_damage = hp - enemy.get_hp()
                self.assertEqual(unit.level, 2)
                hp = enemy.get_hp()
                fight(sim, unit, enemy, script=['hit1', 'miss2', 'end'])
                self.assertEqual(hp - enemy.get_hp(), first_damage + 1)
                self.assertEqual(unit.items[0].data['uses'], 43)

    def test_exact_threshold_and_red_phase_level_up(self):
        for team in ('player', 'other'):
            with combat_fixture(team, exp=90, defending=True) as (sim, unit, enemy):
                fight(sim, unit, enemy, True, ['hit1', 'hit2', 'end'])
                self.assertEqual((unit.level, unit.exp), (2, 0))
                self.assertEqual(sim.game.phase.get_current(), 'enemy')
                self.assertEqual(unit.stats['STR'], 8)

    def test_single_player_fallback_and_nonhuman_green(self):
        from app.engine import unit_funcs
        for team in ('player', 'other'):
            with combat_fixture(team, method='Random', coop=False) as (sim, unit, enemy):
                from app.data.database.database import DB
                DB.constants.get('enemy_leveling').value = 'Fixed'
                self.assertEqual(unit_funcs.get_leveling_method(unit), 'Random' if team == 'player' else 'Fixed')
                fight(sim, unit, enemy, script=['hit1', 'hit2', 'end'])
                self.assertEqual(unit.exp, 10 if team == 'player' else 0)
                self.assertEqual(enemy.exp, 0)


class NetworkProgressionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.sim = Simulation(seed=0, scenario='progression')
        self.addCleanup(self.sim.close)

    asyncSetUp = network.TransportTests.asyncSetUp
    asyncTearDown = playability.PlayabilityTests.asyncTearDown
    clients = playability.PlayabilityTests.clients
    until = playability.PlayabilityTests.until

    async def test_both_level_resync_rejoin_and_updated_next_turn_stats(self):
        from app.coop.client import Connection
        blue, green = await self.clients()
        clients = [blue, green]
        await self.until(clients, lambda: blue.model.can_act)
        initial = deepcopy(blue.model.packet)

        async def issue(client, action, **args):
            old = self.session.revision
            request = client.model.command(action, **args)
            client.send(request)
            await self.until(clients, lambda: all(c.model.packet['revision'] == old + 1 for c in clients))
            self.assertEqual(blue.model.packet, clients[1].model.packet)
            self.assertEqual(blue.model.packet, self.session.packet)
            return request

        choice = next(u for u in initial['state']['units'] if u['id'] == 'Blue_Captain')['attacks'][0]
        accepted_request = await issue(blue, 'attack', unit='Blue_Captain', **choice)
        self.assertIn('LEVEL UP 1 -> 2', blue.model.message)
        self.assertIn('STR +1', blue.model.message)
        self.assertTrue(blue.model.progression)
        after_blue = deepcopy(self.session.packet)
        blue.send(accepted_request)
        await self.until(clients, lambda: blue.model.message == 'Rejected: duplicate_command')
        for client in clients:
            client.send({'v': VERSION, 'type': 'sync'})
        await asyncio.sleep(0.05)
        for client in clients:
            client.poll()
        self.assertEqual(self.session.packet, after_blue)
        await issue(blue, 'end_phase')
        choice = next(u for u in self.session.packet['state']['units'] if u['id'] == 'Green_Captain')['attacks'][0]
        await issue(green, 'attack', unit='Green_Captain', **choice)
        grown = deepcopy(self.session.packet)
        captains = [u for u in grown['state']['units'] if u['id'] in ('Blue_Captain', 'Green_Captain')]
        self.assertEqual([(u['level'], u['exp'], u['stats']['STR'], u['max_hp']) for u in captains], [(2, 5, 8, 41)] * 2)
        await asyncio.to_thread(green.close)
        await self.until((blue,), lambda: blue.model.peers == ['player'])
        green = await asyncio.to_thread(Connection, '127.0.0.1', self.port, self.session.tokens['other'])
        clients[1] = green
        self.addAsyncCleanup(asyncio.to_thread, green.close)
        await self.until(clients, lambda: green.model.can_act)
        self.assertEqual(green.model.packet, grown)
        await issue(green, 'end_phase')
        self.assertEqual(self.session.packet['state']['turn'], 2)
        self.assertNotEqual(self.session.packet['state']['rng']['combat'], grown['state']['rng']['combat'])
        # Existing LT damage calculation now uses the grown STR against the
        # original DEF, proving these are engine stats rather than UI values.
        from app.engine import combat_calcs
        unit = self.sim.game.get_unit('Blue_Captain')
        enemy = self.sim.game.get_unit('Red_1')
        self.assertEqual(unit.stats['STR'], 8)
        self.assertFalse(unit.dead)
        alive = [u for u in self.sim.units if u.team == 'enemy' and u.position]
        self.assertTrue(alive)
        target = alive[0]
        grown_damage = combat_calcs.compute_damage(unit, target, unit.get_weapon(), target.get_weapon(), 'attack', (0, 0))
        unit.stats['STR'] -= 1
        try:
            old_damage = combat_calcs.compute_damage(unit, target, unit.get_weapon(), target.get_weapon(), 'attack', (0, 0))
        finally:
            unit.stats['STR'] += 1
        self.assertEqual(grown_damage, old_damage + 1)
        choices = self.sim.attacks(unit)
        self.assertTrue(choices)
        old_uses = unit.get_weapon().data['uses']
        rng_before = deepcopy(self.session.packet['state']['rng'])
        await issue(blue, 'attack', unit=unit.nid, **choices[0])
        self.assertLessEqual(unit.get_weapon().data['uses'], old_uses)
        self.assertNotEqual(self.session.packet['state']['rng'], rng_before)
        self.assertTrue(unit.finished)
        self.assertEqual(blue.model.packet, green.model.packet)
        self.assertEqual(self.session.packet['state']['status'], 'playing')

    async def test_no_remote_progression_mutation_fields_or_old_protocol(self):
        blue, green = await self.clients()
        await self.until((blue, green), lambda: blue.model.can_act)
        before = deepcopy(self.session.packet)
        for changes in ({'exp': 100}, {'stats': {'STR': 99}}, {'level': 20}, {'wexp': {'Axe': '999'}}):
            bad = {**network.command(before, 'wait', unit='Blue_Captain'), **changes}
            with self.assertRaises(ProtocolError):
                self.session.command('player', bad, ('player', 'other'))
        with self.assertRaises(ProtocolError):
            validate_packet({**before, 'v': VERSION - 1})
        for path, value in (('mana', True), ('mana', 9999), ('wexp', {'Axe': 'NaN'}),
                            ('wexp', {'Axe': '1e999'}), ('wexp', {'Axe': 1.5}),
                            ('wexp', {'Axe': '-1'})):
            invalid = deepcopy(before)
            invalid['state']['units'][0][path] = value
            invalid['digest'] = digest(invalid['state'])
            with self.assertRaises(ProtocolError):
                validate_packet(invalid)
        self.assertEqual(before, self.session.packet)
        # Exercise the actual socket ingress as well as Session's validation.
        blue.send({**network.command(before, 'wait', unit='Blue_Captain'), 'exp': 100})
        for _ in range(100):
            try:
                blue.poll()
            except (OSError, ValueError):
                break
            await asyncio.sleep(0.005)
        else:
            self.fail('Forged progression payload was not disconnected')
        self.assertEqual(before, self.session.packet)


class ProgressionProcessTests(unittest.TestCase):
    def test_three_independent_processes_level_both_armies(self):
        import tempfile
        from utilities.smoke_network import run_smoke
        with tempfile.TemporaryDirectory(prefix='lt-growth-test-') as folder:
            result = run_smoke(folder, progression=True)
            self.assertEqual(result['revision'], 7)
            self.assertEqual(result['snapshots_compared'], 8)
            self.assertTrue(result['progression'])
