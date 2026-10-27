"""Authoritative adapter for the existing LT training map, never a second solver."""
import hashlib
import os
from pathlib import Path

from app.coop.protocol import ProtocolError


class Simulation:
    def __init__(self, seed=0, scenario="training", growth_method=None):
        if scenario not in ('training', 'progression', 'healing', 'campaign'):
            raise ValueError('Unknown trusted scenario')
        if growth_method not in (None, 'Fixed', 'Random', 'Dynamic'):
            raise ValueError('Unsupported growth method')
        self.scenario = scenario
        self.campaign = None
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
        from app.engine.codegen import source_generator
        source_generator.generate_all()
        # Engine action must be imported before state modules (upstream cycle).
        from app.engine import action, config, driver, engine, game_state, save
        from app.data.database.database import DB
        from app.data.resources.resources import RESOURCES
        from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
        from app.engine.coop_demo import LEVEL, install_demo, enable_local_control
        from app.engine.objects.item import ItemObject
        from app.engine.objects.skill import SkillObject
        self.old_settings = config.SETTINGS.copy()
        self.old_saves = save.MAKES_PHASE_SAVES, save.MAKES_PRELOAD_SAVES
        save.MAKES_PHASE_SAVES = save.MAKES_PRELOAD_SAVES = False
        config.SETTINGS.update(animation='Never', autoend_turn=0, mouse=0,
                               random_seed=seed, music_volume=0, sound_volume=0)
        RESOURCES.load('default.ltproj', CURRENT_SERIALIZATION_VERSION)
        DB.load('default.ltproj', CURRENT_SERIALIZATION_VERSION)
        driver.start('Co-op authoritative host', from_editor=True)
        install_demo()
        level_id = LEVEL
        if scenario == 'progression':
            from app.coop import progression_demo
            level_id = progression_demo.install()
        elif scenario == 'healing':
            from app.coop import healing_demo
            level_id = healing_demo.install()
        elif scenario == 'campaign':
            from app.coop import campaign
            level_id = campaign.install()
        # Preserve the same objectives/events, but keep the final board for
        # clients instead of entering local chapter/title/game-over presentation.
        for event in DB.events:
            if event.name.startswith('Shared victory'):
                event.source = 'level_var;coop_victory;True'
            elif event.name.startswith('Shared defeat'):
                event.source = 'level_var;coop_defeat;True'
        ItemObject.next_uid = SkillObject.next_uid = 100
        self.game = game_state.start_level(level_id)
        enable_local_control(self.game)
        if scenario == 'progression':
            self.game.current_mode.growths = growth_method or 'Fixed'
            progression_demo.initialize(self.game)
        elif scenario == 'healing':
            self.game.current_mode.growths = growth_method or 'Fixed'
            healing_demo.initialize(self.game)
        elif scenario == 'campaign':
            self.game.current_mode.growths = growth_method or 'Fixed'
            self.campaign = campaign.Campaign(self.game)
        elif growth_method:
            self.game.current_mode.growths = growth_method
        self.units = list(self.game.units)
        self.surface = engine.create_surface((240, 160))
        self.fault = False
        # Fingerprint code and scenario database. Clients have no local rules or
        # RNG; this identifies the exact authoritative ruleset they both view.
        hasher = hashlib.sha256()
        paths = sorted(set(Path('app/engine').rglob('*.py')) |
                       set(Path('app/coop').glob('*.py')) |
                       set(Path('default.ltproj/game_data').rglob('*.json')))
        for path in paths:
            hasher.update(path.as_posix().encode() + b'\0' + path.read_bytes())
        self.ruleset = hasher.hexdigest()
        self.settle()

    def close(self):
        from app.engine import config, save
        config.SETTINGS.clear()
        config.SETTINGS.update(self.old_settings)
        save.MAKES_PHASE_SAVES, save.MAKES_PRELOAD_SAVES = self.old_saves

    @property
    def status(self):
        if self.fault:
            return 'fault'
        if self.game.level_vars.get('coop_defeat'):
            return 'defeat'
        if self.game.level_vars.get('coop_victory'):
            if self.campaign and self.campaign.index == 0:
                return 'intermission'
            return 'victory'
        return 'playing'

    def step(self):
        from app.engine import engine
        from app.engine.sound import get_sound_thread
        for key in ('current_time', 'input_time'):
            engine.constants[key] += 33
        engine.constants['last_time'] = engine.constants['current_time'] - 33
        engine.constants['delta_t'] = 33
        self.surface, repeat = self.game.state.update(None, self.surface)
        for _ in range(200):
            if not repeat:
                break
            self.surface, repeat = self.game.state.update(None, self.surface)
        else:
            raise RuntimeError('Engine state repeat limit exceeded')
        get_sound_thread().update([])

    def settle(self):
        for _ in self.settle_steps():
            pass

    def settle_steps(self):
        for _ in range(6000):
            self.step()
            yield
            if self.game.state.current() == 'free' and not self.game.state.temp_state:
                if self.campaign:
                    self.campaign.observe_result(self.game)
                return
        raise RuntimeError('Engine did not reach a command boundary')

    def moves(self, unit):
        if not unit.position or unit.finished or unit.has_moved:
            return []
        return sorted(pos for pos in self.game.path_system.get_valid_moves(unit, witch_warp=False)
                      if pos != unit.position and not self.game.board.get_unit(pos))

    def attacks(self, unit):
        from app.engine import item_funcs, item_system, skill_system
        if not unit.position or unit.finished or unit.has_attacked:
            return []
        result = []
        for item in unit.items:
            if not (unit.can_equip(item) and item_funcs.available(unit, item) and item_system.is_weapon(unit, item)):
                continue
            for pos in sorted(self.game.target_system.get_valid_targets(unit, item)):
                target = self.game.board.get_unit(pos)
                if target and skill_system.check_enemy(unit, target):
                    result.append({'item': item.uid, 'target': target.nid})
        return result

    def heals(self, unit):
        from app.engine import item_funcs, item_system, skill_system
        if not unit.position or unit.dead or unit.is_dying or unit.finished or unit.has_attacked:
            return []
        result = []
        # Trusted, single-target staff slice; not arbitrary Use/event execution.
        for item in self.game.target_system.get_spells(unit):
            if item.nid not in ('Heal', 'Mend') or not item_funcs.is_heal(unit, item):
                continue
            if item.sequence_item or item.multi_item or item_system.num_targets(unit, item) != 1:
                continue
            for pos in sorted(self.game.target_system.get_valid_targets(unit, item)):
                target = self.game.board.get_unit(pos)
                if target and not target.dead and not target.is_dying and skill_system.check_ally(unit, target):
                    result.append({'item': item.uid, 'target': target.nid})
        return result

    def execute(self, team, command):
        for _ in self.execute_steps(team, command):
            pass

    def execute_steps(self, team, command):
        from app.engine import action, skill_system
        from app.engine.combat import interaction
        game = self.game
        if command['action'] == 'ready':
            if self.status != 'intermission' or not self.campaign:
                raise ProtocolError('not_intermission')
            try:
                self.campaign.confirm_ready(game, team)
                self.units = list(game.units)
                yield from self.settle_steps()
            except ProtocolError:
                raise
            except Exception as exc:
                self.fault = True
                raise RuntimeError('Campaign transition failed') from exc
            return
        if self.status != 'playing':
            raise ProtocolError('session_finished')
        if team != game.phase.get_current():
            raise ProtocolError('wrong_phase')
        kind = command['action']
        if kind == 'end_phase':
            game.state.change('turn_change')
            game.state.change('status_endstep')
            game.state.change('ai')
        else:
            unit = game.get_unit(command['unit'])
            if not unit or unit.team != team or (self.campaign and self.campaign_owner(unit.nid) != team):
                raise ProtocolError('not_owner')
            if not unit.position or unit.dead or unit.is_dying or unit.finished:
                raise ProtocolError('unit_unavailable')
            if not skill_system.can_select(unit):
                raise ProtocolError('unit_unselectable')
            if kind == 'move':
                pos = tuple(command['pos'])
                if pos not in self.moves(unit):
                    raise ProtocolError('illegal_move')
                path = game.path_system.get_path(unit, pos)
                if not path or game.path_system.get_path_cost(unit, path) > unit.movement_left:
                    raise ProtocolError('illegal_path')
                action.do(action.SetPreviousPosition(unit))
                unit.current_move = action.Move(unit, pos, path)
                action.do(unit.current_move)
                game.state.change('movement')
            elif kind == 'wait':
                unit.wait(actively_chosen=True)
            elif kind in ('attack', 'heal'):
                choice = {'item': command['item'], 'target': command['target']}
                legal = self.heals(unit) if kind == 'heal' else self.attacks(unit)
                if choice not in legal:
                    raise ProtocolError('illegal_heal' if kind == 'heal' else 'illegal_attack')
                item = next(i for i in unit.items if i.uid == command['item'])
                target = game.get_unit(command['target'])
                if kind == 'attack':
                    action.do(action.EquipItem(unit, item))
                game.cursor.cur_unit = unit
                game.cursor.set_pos(unit.position)
                interaction.start_combat(unit, target.position, item, skip=True)
            else:
                raise ProtocolError('unknown_action')
        try:
            yield from self.settle_steps()
        except Exception as exc:
            # Never accept more commands after a possibly partially applied
            # engine operation. There is no speculative rollback in v1.
            self.fault = True
            raise RuntimeError('Authoritative resolution failed') from exc

    def snapshot(self):
        from app.utilities import static_random
        game = self.game
        terrain = game.level.tilemap.layers[0].terrain
        units = []
        for unit in sorted(self.units, key=lambda u: u.nid):
            units.append({
                'id': unit.nid, 'name': unit.name, 'team': unit.team,
                'owner': self.campaign_owner(unit.nid), 'party': unit.party,
                'faction': unit.faction, 'class': unit.klass, 'persistent': unit.persistent,
                'skills': [skill.nid for skill in unit.skills],
                'equipped': unit.get_weapon().uid if unit.get_weapon() else None,
                'pos': list(unit.position) if unit.position else None,
                'hp': unit.get_hp(), 'max_hp': unit.get_max_hp(),
                'dead': bool(unit.dead or unit.is_dying),
                'finished': bool(unit.finished), 'moved': bool(unit.has_moved),
                'attacked': bool(unit.has_attacked), 'movement': int(unit.movement_left),
                'level': unit.level, 'exp': unit.exp, 'stats': dict(unit.stats),
                'wexp': {key: str(value) for key, value in unit.wexp.items()},
                'mana': unit.get_mana(), 'max_mana': unit.get_max_mana(),
                'inventory': [{'uid': i.uid, 'nid': i.nid, 'name': i.name,
                               'uses': i.data.get('uses')} for i in unit.items],
                'moves': [list(p) for p in self.moves(unit)] if self.status == 'playing' else [],
                'attacks': self.attacks(unit) if self.status == 'playing' else [],
                'heals': self.heals(unit) if self.status == 'playing' else []})
        width, height = game.level.tilemap.width, game.level.tilemap.height
        return {'campaign': self.campaign.projection(game) if self.campaign else None,
                'scenario': 'coop_' + self.scenario + '/v1', 'ruleset': self.ruleset,
                'width': width, 'height': height,
                'terrain': [[{'9': 'wall', '2': 'forest'}.get(terrain.get((x, y)), 'plain')
                             for x in range(width)] for y in range(height)],
                'phase': game.phase.get_current(), 'turn': game.turncount,
                'status': self.status, 'objective': game.level.objective['simple'],
                'rng': {'seed': static_random.r.seed, 'combat': static_random.r.combat_random.state,
                        'growth': static_random.r.growth_random.state, 'other': static_random.r.other_random.state},
                'units': units}

    def campaign_owner(self, nid):
        if self.campaign:
            from app.coop.campaign import OWNERS
            return OWNERS.get(nid)
        return None
