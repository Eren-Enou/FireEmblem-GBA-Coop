from unittest.mock import patch

from app.tests.engine_harness import EngineTestCase
from app.engine import action, config, human_control, skill_system
from app.engine.coop_demo import BLUE, GREEN, RED, LEVEL, install_demo, enable_local_control
from app.data.database.database import DB
from app.events import triggers


class LocalCoopTests(EngineTestCase):
    project = 'default.ltproj'

    def setUp(self):
        super().setUp()
        self.h = self.start_harness()
        install_demo()
        self.g = self.h.start_level(LEVEL)
        enable_local_control(self.g)
        self.h.run_until_state('free')

    def green_turn(self):
        self.h.end_turn()
        self.h.run_until(lambda: self.g.phase.get_current() == 'other' and
                         self.h.state == 'free' and not self.g.state.temp_state)

    def test_scenario_resources_and_alliances(self):
        self.assertEqual(len(self.g.get_all_units()), 7)
        self.assertTrue(DB.teams.is_allied('player', 'other'))
        self.assertFalse(DB.teams.is_allied('other', 'enemy'))
        for u in self.g.get_all_units():
            self.assertEqual(u.items[0].nid, 'Iron_Axe')
        for terrain in self.g.level.tilemap.layers[0].terrain.values():
            self.assertIn(terrain, DB.terrain)

    def test_ownership_even_when_skill_grants_selection(self):
        for nid in (GREEN[0], RED[0]):
            self.h.move_cursor_to(self.g.get_unit(nid).position)
            with patch.object(skill_system, 'can_select', return_value=True):
                self.h.press('SELECT')
            self.assertEqual(self.h.state, 'free')
        self.green_turn()
        self.h.move_cursor_to(self.g.get_unit(BLUE[0]).position)
        self.h.press('SELECT')
        self.assertEqual(self.h.state, 'free')
        self.h.select_unit(GREEN[0])
        self.assertEqual(self.h.state, 'move')

    def test_move_and_wait_both_armies(self):
        self.h.wait(BLUE[0], (3, 3))
        self.h.run_until_state('free')
        self.assertEqual(self.g.get_unit(BLUE[0]).position, (3, 3))
        self.assertTrue(self.g.get_unit(BLUE[0]).finished)
        self.green_turn()
        self.h.wait(GREEN[0], (5, 3))
        self.h.run_until_state('free')
        self.assertEqual(self.g.get_unit(GREEN[0]).position, (5, 3))
        self.assertTrue(self.g.get_unit(GREEN[0]).finished)
        self.assertFalse(self.g.get_unit(GREEN[1]).has_run_ai)

    def test_wall_and_enemy_are_not_reachable_and_ally_cannot_be_occupied(self):
        for nid in (BLUE[0], GREEN[0]):
            if nid in GREEN:
                self.green_turn()
            unit = self.g.get_unit(nid)
            moves = self.g.path_system.get_valid_moves(unit)
            self.assertNotIn((7, 2), moves)
            self.assertNotIn(self.g.get_unit(RED[0]).position, moves)
            # Paths may pass through allies; MoveState rejects stopping on one.
            self.h.select_unit(nid)
            self.g.cursor.set_pos(self.g.get_unit(GREEN[1]).position)
            self.h.press('SELECT')
            self.assertEqual(self.h.state, 'move')
            self.h.press('BACK')
            self.h.run_until_state('free')

    def test_illegal_move_does_not_change_position(self):
        self.h.select_unit(BLUE[0])
        unit = self.g.get_unit(BLUE[0])
        # Set the cursor directly to probe input validation beyond the UI clamp.
        self.g.cursor.set_pos((14, 9))
        self.h.press('SELECT')
        self.assertEqual(unit.position, (2, 3))
        self.assertEqual(self.h.state, 'move')

    def test_blue_and_green_use_real_combat(self):
        enemy = self.g.get_unit(RED[0])
        action.do(action.Teleport(enemy, (3, 3)))
        hp = enemy.get_hp()
        self.h.attack(BLUE[0], (2, 3))
        self.assertLess(enemy.get_hp(), hp)
        self.green_turn()
        enemy = self.g.get_unit(RED[1])
        action.do(action.Teleport(enemy, (5, 3)))
        hp = enemy.get_hp()
        uses = self.g.get_unit(GREEN[0]).items[0].data['uses']
        self.h.attack(GREEN[0], (4, 3))
        self.assertLess(enemy.get_hp(), hp)
        self.assertLess(self.g.get_unit(GREEN[0]).items[0].data['uses'], uses)

    def test_round_runs_red_ai_then_blue_turn_two(self):
        positions = {nid: self.g.get_unit(nid).position for nid in RED}
        self.green_turn()
        self.h.end_turn()
        self.h.run_until_player_turn(2)
        self.assertEqual(self.g.phase.get_current(), 'player')
        self.assertTrue(any(self.g.get_unit(nid).position != pos for nid, pos in positions.items()))
        self.assertEqual(self.g.get_unit(GREEN[0]).position, (4, 3))

    def test_autoend_checks_active_army(self):
        config.SETTINGS['autoend_turn'] = 1
        self.h.wait(BLUE[0], (2, 3))
        self.h.run_until_state('free')
        self.h.wait(BLUE[1], (2, 5))
        self.h.run_until(lambda: self.g.phase.get_current() == 'other' and
                         self.h.state == 'free' and not self.g.state.temp_state)
        # Blue's finished units must not immediately auto-end Green's phase.
        self.h.step(5)
        self.assertEqual(self.g.phase.get_current(), 'other')
        self.h.wait(GREEN[0], (4, 3))
        self.h.run_until_state('free')
        self.h.wait(GREEN[1], (4, 5))
        self.h.run_until_player_turn(2)

    def test_shared_victory(self):
        for nid in RED:
            action.do(action.Die(self.g.get_unit(nid)))
        self.g.events.trigger(triggers.PhaseChange('other'))
        self.h.run_until(lambda: bool(self.g.level_vars.get('coop_victory')))
        # EventState consumes _win_game in the same frame and performs normal
        # chapter cleanup. Observe that completion instead of the transient flag.
        self.h.run_until_state('title_start')
        self.assertEqual(self.g.memory['_prev_level_nid'], LEVEL)

    def test_ai_targets_either_human_army(self):
        enemy = self.g.get_unit(RED[0])
        action.do(action.Teleport(enemy, (5, 3)))
        controller = self.g.ai
        for nid, pos in ((BLUE[0], (5, 4)), (GREEN[0], (6, 3))):
            # Leave exactly one human in attack range, then let the existing
            # enemy AI choose its target without replacing any AI behavior.
            for i, other in enumerate(BLUE + GREEN):
                action.do(action.Teleport(self.g.get_unit(other), (i, 9)))
            action.do(action.Teleport(self.g.get_unit(nid), pos))
            controller.load_unit(enemy)
            for _ in range(100):
                if controller.think():
                    break
            self.assertEqual(controller.goal_target, pos)
            self.assertIsNotNone(controller.goal_item)

    def test_aux_cycles_only_green_units_on_green_phase(self):
        self.green_turn()
        self.h.press('AUX')
        self.assertIn(self.g.cursor.position, [self.g.get_unit(n).position for n in GREEN])

    def test_no_premature_victory(self):
        self.g.events.trigger(triggers.PhaseChange('other'))
        self.h.step(5)
        self.assertFalse(self.g.level_vars.get('coop_victory'))

    def test_green_elimination_causes_shared_defeat(self):
        for nid in GREEN:
            action.do(action.Die(self.g.get_unit(nid)))
        self.g.events.trigger(triggers.PhaseChange('other'))
        self.h.run_until(lambda: bool(self.g.level_vars.get('_lose_game')))

    def test_blue_elimination_causes_shared_defeat(self):
        for nid in BLUE:
            action.do(action.Die(self.g.get_unit(nid)))
        self.g.events.trigger(triggers.PhaseChange('player'))
        self.h.run_until(lambda: bool(self.g.level_vars.get('_lose_game')))

    def test_demo_does_not_offer_unsupported_campaign_saves(self):
        from app.engine.general_states import OptionMenuState
        options = OptionMenuState()._populate_options()[0]
        self.assertNotIn('Save', options)
        self.assertNotIn('Suspend', options)

    def test_default_control_remains_blue_only(self):
        del self.g.game_vars['_human_teams']
        self.assertTrue(human_control.is_human_team('player'))
        self.assertFalse(human_control.is_human_team('other'))
        self.assertFalse(skill_system.can_select(self.g.get_unit(GREEN[0])))
