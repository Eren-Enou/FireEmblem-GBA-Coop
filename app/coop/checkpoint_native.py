"""Explicit native LT capture/reconstruction for the trusted chapter boundary.

All external fields are validated before allocating objects. Component code and
definitions always come from the installed trusted database, never JSON input.
"""
from copy import deepcopy
from hashlib import sha256

from app.coop import checkpoint as dto
from app.coop.campaign import OWNERS, PARTIES


def capture(simulation):
    from app.data.database.database import DB
    from app.engine.objects.item import ItemObject
    from app.engine.objects.skill import SkillObject
    from app.utilities import static_random
    from app.engine.source_type import SourceType
    game = simulation.game
    dto.check(simulation.status == 'intermission' and game.state.current() == 'free'
              and not game.state.temp_state and not game.events.event_stack,
              'checkpoint requires settled Chapter 1 intermission')
    dto.check(not game.supports.save(), 'unsupported active support state')
    dto.check(dict(game.game_vars) == {'_random_seed': static_random.r.seed,
              '_human_teams': ['player', 'other'], '_turnwheel': False, '_local_coop_demo': True},
              'unsupported custom campaign variables')
    units, items, skills = [], [], []
    for nid, owner in OWNERS.items():
        unit = game.get_unit(nid)
        dto.check(unit is not None and unit.persistent and not unit.generic and
                  unit.traveler is None and not unit.strike_partner, 'unsupported permanent unit state')
        dto.check(unit.equipped_accessory is None and not unit.notes, 'unsupported accessory/notes state')
        prefab = DB.units.get(nid)
        dto.check(unit.prefab_nid == nid and unit.name == prefab.name and unit.desc == prefab.desc
                  and unit.variant == prefab.variant and unit.portrait_nid == prefab.portrait_nid
                  and unit.affinity == prefab.affinity, 'unsupported modified character presentation/identity')
        skill_ids = []
        for info in unit._skills:
            if info.source_type in (SourceType.AURA, SourceType.TERRAIN, SourceType.REGION, SourceType.ITEM):
                continue  # Rebuilt derived state, never a permanent skill record.
            skill = info.skill_obj
            dto.check(skill.owner_nid == unit.nid and not skill.parent_skill and not skill.subskill and not skill.initiator_nid,
                      'unsupported compound skill state')
            skills.append({'uid': skill.uid, 'nid': skill.nid, 'owner': unit.nid,
                           'data': deepcopy(skill.data), 'source': info.source,
                           'source_type': info.source_type.nid})
            skill_ids.append(skill.uid)
        units.append({'id': nid, 'owner': owner, 'team': unit.team, 'party': unit.party,
                      'faction': unit.faction, 'class': unit.klass, 'level': unit.level, 'exp': unit.exp,
                      'stats': dict(unit.stats), 'growths': dict(unit.growths),
                      'growth_points': {key: str(value) for key, value in unit.growth_points.items()},
                      'wexp': {key: str(value) for key, value in unit.wexp.items()},
                      'caps': dict(unit.stat_cap_modifiers), 'hp': unit.get_hp(), 'mana': unit.get_mana(),
                      'fatigue': unit.get_fatigue(), 'guard': unit.get_guard_gauge(), 'dead': unit.dead,
                      'items': [item.uid for item in unit.items], 'skills': skill_ids,
                      'equipped': unit.equipped_weapon.uid if unit.equipped_weapon else None,
                      'fields': deepcopy(unit._fields), 'tags': sorted(unit._tags)})
    parties = []
    for party_id in PARTIES.values():
        party = game.parties[party_id]
        parties.append({'id': party_id, 'leader': party.leader_nid, 'money': party.money,
                        'bexp': party.bexp, 'convoy': [item.uid for item in party.convoy],
                        'order': list(party.party_prep_manage_sort_order)})
    all_items = [i for nid in OWNERS for i in game.get_unit(nid).items]
    all_items += [i for pid in PARTIES.values() for i in game.parties[pid].convoy]
    for item in all_items:
        dto.check(not item.parent_item and not item.subitems and not item.command_item,
                  'unsupported compound item')
        items.append({'uid': item.uid, 'nid': item.nid, 'owner': item.owner_nid,
                      'droppable': item.droppable, 'data': deepcopy(item.data)})
    mode = game.current_mode
    dto.check(not any((mode.enemy_autolevels, mode.enemy_truelevels, mode.boss_autolevels,
                      mode.boss_truelevels)), 'unsupported difficulty modifiers')
    payload = {'format': dto.FORMAT, 'compatibility': dto.compatibility(),
               'campaign': 'two_banners/1', 'boundary': 'alliance/intermission',
               'completed': list(simulation.campaign.completed), 'next': 'holding',
               'mode': {'nid': mode.nid, 'permadeath': mode.permadeath, 'growths': mode.growths,
                        'rng_mode': mode.rng_mode.value if hasattr(mode.rng_mode, 'value') else mode.rng_mode},
               'rng': {'seed': static_random.r.seed, 'combat': static_random.r.combat_random.state,
                       'growth': static_random.r.growth_random.state, 'other': static_random.r.other_random.state},
               'next_uids': {'item': ItemObject.next_uid, 'skill': SkillObject.next_uid},
               'units': units, 'items': items, 'skills': skills, 'parties': parties,
               'events': list(game.already_triggered_events),
               'records': {key: [deepcopy(record.save()[1]) for record in values]
                           for key, values in vars(game.records).items()}}
    dto.validate(payload)
    return payload


def validate_catalog(payload):
    """Check trusted references/caps before any native game is constructed."""
    from app.data.database.database import DB
    dto.validate(payload)
    for record in payload['units']:
        prefab = DB.units.get(record['id'])
        klass = DB.classes.get(record['class'])
        dto.check(prefab is not None and klass is not None, 'missing trusted character/class')
        for stat, value in record['stats'].items():
            dto.check(value <= klass.max_stats.get(stat, 30) + record['caps'][stat], 'stat exceeds native class cap')
    for record in payload['items']:
        dto.check(DB.items.get(record['nid']) is not None, 'missing trusted item')
    for record in payload['skills']:
        dto.check(DB.skills.get(record['nid']) is not None, 'missing trusted skill')


def native_number(value):
    return float(value) if any(c in value for c in '.eE') else int(value)


def restore(simulation, payload):
    """Startup only, called by the guarded constructor before listening."""
    dto.check(getattr(simulation, '_restore_startup', False), 'native restoration is startup-only')
    from app.data.database.database import DB
    from app.engine import item_funcs, records
    from app.engine.objects.unit import UnitObject
    from app.engine.objects.item import ItemObject
    from app.engine.objects.skill import SkillObject
    from app.engine.source_type import SourceType
    from app.utilities import static_random
    validate_catalog(payload)
    game = simulation.game
    # Discard only the fresh bootstrap, never an existing client's live session.
    for unit in list(game.units):
        if unit.position:
            game.leave(unit)
    game.unit_registry.clear()
    game.item_registry.clear()
    game.skill_registry.clear()
    roster = {}
    for record in payload['units']:
        # A trusted UnitPrefab initializes a native unique character without the
        # level-prefab item/skill spawning path. Attach validated instances below.
        unit = UnitObject.from_prefab(DB.units.get(record['id']), game.current_mode)
        unit.team, unit.party, unit.faction = record['team'], record['party'], record['faction']
        unit.klass, unit.level, unit.exp = record['class'], record['level'], record['exp']
        unit.stats = dict(record['stats'])
        unit.growths = dict(record['growths'])
        unit.growth_points = {key: native_number(value) for key, value in record['growth_points'].items()}
        unit.wexp = {key: native_number(value) for key, value in record['wexp'].items()}
        unit.stat_cap_modifiers = dict(record['caps'])
        unit._fields = deepcopy(record['fields'])
        unit.dead = record['dead']
        unit.position = None
        roster[unit.nid] = unit
    for record in payload['items']:
        owner = roster.get(record['owner'])
        item = item_funcs.create_item(owner, record['nid'], record['droppable'])
        dto.check(item.data.keys() == record['data'].keys(), 'trusted item state schema changed')
        item.uid, item.data = record['uid'], deepcopy(record['data'])
        game.register_item(item)
    sources = {'default': SourceType.DEFAULT, 'personal': SourceType.PERSONAL, 'klass': SourceType.KLASS}
    for record in payload['skills']:
        owner = roster[record['owner']]
        skill = item_funcs.create_skill(owner, record['nid'])
        dto.check(skill.data == {}, 'trusted passive skill state schema changed')
        skill.uid, skill.data = record['uid'], deepcopy(record['data'])
        owner.add_skill(skill, record['source'], sources[record['source_type']])
        game.register_skill(skill)
    for record in payload['units']:
        unit = roster[record['id']]
        for uid in record['items']:
            unit.add_item(game.get_item(uid))
        if record['equipped'] is not None:
            unit.equip(game.get_item(record['equipped']))
        unit.set_hp(record['hp'])
        unit.set_mana(record['mana'])
        unit.set_fatigue(record['fatigue'])
        unit.set_guard_gauge(record['guard'])
        dto.check(unit.get_hp() == record['hp'] and unit.get_mana() == record['mana'],
                  'restored HP/mana violates native limits')
        game.full_register(unit)
    for record in payload['parties']:
        party = game.parties[record['id']]
        party.leader_nid, party.money, party.bexp = record['leader'], record['money'], record['bexp']
        party.convoy = [game.get_item(uid) for uid in record['convoy']]
        party.party_prep_manage_sort_order = list(record['order'])
    # The completed board is a non-tactical intermission, not a mid-map save.
    # Use trusted nominal roster positions; no enemy or deployment data is loaded.
    boundary = deepcopy(DB.levels.get('alliance'))
    boundary.units = type(boundary.units)([p for p in boundary.units if p.nid in OWNERS])
    DB.levels.remove_key('alliance')
    DB.levels.append(boundary)
    game.sweep()
    game.already_triggered_events = list(payload['events'])
    game.level_vars['coop_victory'] = True
    simulation.campaign.completed = list(payload['completed'])
    simulation.campaign.ready.clear()
    game.load_states(['start_level_asset_loading'])
    game.start_level('alliance')
    simulation.units = list(game.units)
    simulation.settle()
    # Rebuild only whitelisted native record classes, never getattr on file data.
    types = {'kills': records.KillRecord, 'death': records.KillRecord,
             'damage': records.DamageRecord, 'healing': records.DamageRecord,
             'item_use': records.ItemRecord, 'steal': records.StealRecord,
             'combat_results': records.CombatRecord, 'turns_taken': records.Record,
             'levels': records.LevelRecord, 'exp': records.LevelRecord, 'money': records.MoneyRecord}
    game.records = records.Recordkeeper()
    for kind, values in payload['records'].items():
        native = [types[kind].restore(deepcopy(value)) for value in values]
        vars(game.records)[kind] = native
    static_random.set_seed(payload['rng']['seed'])
    for kind in ('combat', 'growth', 'other'):
        getattr(static_random.r, kind + '_random').state = payload['rng'][kind]
    ItemObject.next_uid = payload['next_uids']['item']
    SkillObject.next_uid = payload['next_uids']['skill']
    dto.check(capture(simulation) == payload, 'native restoration failed continuity verification')
    print('NATIVE_CHECKPOINT_VERIFIED ' + sha256(dto.canonical(payload)).hexdigest(), flush=True)
