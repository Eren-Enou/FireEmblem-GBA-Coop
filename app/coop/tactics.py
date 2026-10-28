"""Read-only tactical presentation of audited native rules, never a second solver.

Attached by Session rather than Simulation: this module does not change native
campaign rules or the checkpoint compatibility manifest. No hypothetical movement,
item equip, skill creation, combat solver, event, action or RNG calls belong here.
"""
from app.coop.checkpoint import SKILLS

WEAPONS = ('Iron_Axe', 'Hand_Axe')
PASSIVES = (*SKILLS, 'Forest')


def cells(positions):
    return [list(pos) for pos in sorted(positions)]


def safe_unit(unit):
    components = {'class_skill', 'stat_change', 'avoid', 'is_terrain', 'canto'}
    return not (unit.traveler or unit.strike_partner) and all(
        s.nid in PASSIVES and all(c.nid in components for c in s.components) for s in unit.all_skills)


def safe_weapon(item):
    components = {'weapon', 'value', 'target_enemy', 'min_range', 'max_range', 'damage', 'hit',
                  'crit', 'weight', 'uses', 'uses_options', 'level_exp', 'weapon_type', 'weapon_rank'}
    return item.nid in WEAPONS and not item.multi_item and not item.sequence_item and all(
        c.nid in components for c in item.components)


def strike(unit, target, item, other, mode):
    from app.data.database.database import DB
    from app.engine import combat_calcs
    phases = combat_calcs.compute_attack_phases(unit, target, item, other, mode, (0, 0))
    count = sum(combat_calcs.compute_multiattacks(unit, target, item, mode, (p, 0)) for p in range(phases))
    if not (item.uses_options and item.uses_options.one_loss_per_combat()):
        count = min(count, item.data.get('uses', 100), item.data.get('c_uses', 100))
    return {'damage': combat_calcs.compute_damage(unit, target, item, other, mode, (0, 0)),
            'hit': combat_calcs.compute_hit(unit, target, item, other, mode, (0, 0)),
            'crit': combat_calcs.compute_crit(unit, target, item, other, mode, (0, 0)) if DB.constants.value('crit') else None,
            'count': count}


def forecast(unit, item, target):
    from app.engine import combat_calcs, item_funcs
    from app.data.database.difficulty_modes import RNGOption
    other = target.get_weapon()
    result = {'unit': unit.nid, 'item': item.uid, 'target': target.nid,
              'supported': False, 'note': 'Forecast unavailable: complex item, skill or paired combat',
              'range': [], 'advantage': 'unknown',
              'attack': None, 'counter': None, 'can_counter': None}
    # No speculative execution of arbitrary hooks. These trusted prefabs/passive
    # components have been inspected and their calculations are side-effect free.
    if not safe_weapon(item) or (other and not safe_weapon(other)) or not safe_unit(unit) or not safe_unit(target):
        return result
    if combat_calcs.game.rng_mode != RNGOption.TRUE_HIT:
        result['note'] = 'Forecast unavailable: unsupported RNG/combat mode'
        return result
    result['range'] = sorted(item_funcs.get_range(unit, item))
    counter = combat_calcs.can_counterattack(unit, item, target, other)
    result.update(supported=True, note='Displayed HIT rating; native rolls. Up to shown strikes; death stops combat.',
                  advantage=combat_calcs.compute_overall_advantage(unit, target, item, other).value,
                  attack=strike(unit, target, item, other, 'attack'), can_counter=counter,
                  counter=strike(target, unit, other, item, 'defense') if counter else None)
    return result


def terrain_info(game, pos):
    from app.data.database.database import DB
    terrain = game.get_terrain(game.tilemap, pos)
    defense = resistance = avoid = 0
    status = DB.skills.get(terrain.status) if terrain.status else None
    note = 'Base terrain bonuses; unit skills may ignore terrain'
    if status:
        supported = all(c.nid in ('stat_change', 'avoid', 'is_terrain') for c in status.components)
        if supported:
            for component in status.components:
                if component.nid == 'avoid':
                    avoid += component.value
                elif component.nid == 'stat_change':
                    values = dict(component.value)
                    defense += values.get('DEF', 0)
                    resistance += values.get('RES', 0)
        else:
            defense = resistance = avoid = None
            note = 'Complex terrain effect: numeric preview unavailable'
    return {'name': terrain.name, 'defense': defense, 'resistance': resistance, 'avoid': avoid, 'note': note}


def project(sim, state):
    from app.data.database.database import DB
    from app.engine import item_funcs
    from app.engine.movement import movement_funcs
    game = sim.game
    # The current shared projection is explicitly a no-fog contract. Refuse to
    # serve *any* board rather than leak units/paths through future fog support.
    if game.get_current_fog_info().is_active or any(game.board.fog_regions.cells()):
        raise ValueError('Co-op tactical projection requires no fog; visibility contract not implemented')
    width, height = state['width'], state['height']
    result = {'status': 'available', 'note': 'Potential reach, not AI intent; native line of sight ' +
              ('on' if DB.constants.value('line_of_sight') else 'off'),
              'hit_mode': str(game.rng_mode.value),
              'terrain': [[terrain_info(game, (x, y)) for x in range(width)] for y in range(height)],
              'units': [], 'threats': [], 'forecasts': []}
    if state['status'] != 'playing':
        result['status'] = 'unavailable'
        result['note'] = 'Tactical previews unavailable outside active battle'
        return result
    shown = {u['id']: u for u in state['units']}
    for unit in sim.units:
        if not unit.position or unit.dead or unit.is_dying:
            continue
        costs = [[movement_funcs.get_mcost(unit, (x, y)) for x in range(width)] for y in range(height)]
        routes = []
        for pos in shown[unit.nid]['moves']:
            path = game.path_system.get_path(unit, tuple(pos))
            if path:
                cost = game.path_system.get_path_cost(unit, path)
                routes.append({'pos': pos, 'cost': cost, 'left': int(unit.movement_left)-cost})
        result['units'].append({'unit': unit.nid, 'class_name': DB.classes.get(unit.klass).name,
                                'costs': costs, 'routes': routes})
        if unit.team in ('enemy', 'enemy2'):
            threat = {'unit': unit.nid, 'supported': safe_unit(unit), 'moves': [], 'weapons': []}
            if threat['supported']:
                # Same native movement/target services as BoundaryInterface, but
                # discard occupied stopping squares (traversal remains native).
                moves = game.path_system.get_move_selection(unit, force=True, zero_move=True).normal
                moves = {p for p in moves if not game.board.get_unit(p) or p == unit.position}
                threat['moves'] = cells(moves)
                for item in game.target_system.get_weapons(unit):
                    if not safe_weapon(item):
                        threat['supported'] = False
                        continue
                    if not unit.can_equip(item):
                        continue
                    # The native boundary helper accepts a single weapon here,
                    # preserving range, no-attack-after-move and LoS hooks.
                    reach = game.target_system._get_all_attackable_positions(unit, moves, [item], force=True)
                    current = game.target_system.get_attackable_positions(unit, item, force=True)
                    threat['weapons'].append({'item': item.uid, 'range': sorted(item_funcs.get_range(unit, item)),
                                              'current': cells(current), 'reach': cells(reach)})
            result['threats'].append(threat)
        for choice in shown[unit.nid]['attacks']:
            item = next(i for i in unit.items if i.uid == choice['item'])
            target = game.get_unit(choice['target'])
            result['forecasts'].append(forecast(unit, item, target))
    return result
