"""Trusted live-session campaign; native unique units and chapter lifecycle.

No display snapshot is used to reconstruct a character. Ownership is separate
from team, story faction and native party. This is deliberately not a save DTO.
"""
from copy import deepcopy

ID = 'two_banners/1'
CHAPTERS = ('alliance', 'holding')
TITLES = ('The First Alliance', 'Holding the Line')
OWNERS = {'Blue_Captain': 'player', 'Blue_Healer': 'player',
          'Green_Captain': 'other', 'Green_Healer': 'other'}
PARTIES = {'player': 'Blue_Banner', 'other': 'Green_Banner'}
FACTIONS = {'player': 'River_Wardens', 'other': 'Hill_Watch'}


def install():
    from app.data.database.database import DB
    from app.data.database.units import UnitPrefab
    from app.data.database.parties import PartyPrefab
    from app.data.database.factions import Faction
    from app.data.database.levels import LevelPrefab
    from app.data.database.level_units import UniqueUnit, GenericUnit
    from app.data.resources.resources import RESOURCES
    from app.data.resources.tiles import TileMapPrefab, TileSprite
    from app.events.event_prefab import EventPrefab

    # Strict permadeath with equipment retained on fallen characters, identical
    # for both armies. No Blue-only casual resurrection/convoy path is entered.
    DB.constants.get('convoy_on_death').value = False
    fighter = deepcopy(DB.classes.get('Coop_Fighter'))
    fighter.nid = 'Banner_Vanguard'
    fighter.bases.update(HP=36, DEF=7)
    DB.classes.append(fighter)
    healer = deepcopy(DB.classes.get('Cleric'))
    healer.nid, healer.map_sprite_nid = 'Banner_Cleric', 'coop_token'
    DB.classes.append(healer)
    for nid, name in (('Blue_Captain', 'Aren'), ('Blue_Healer', 'Mira'),
                      ('Green_Captain', 'Tovan'), ('Green_Healer', 'Sela')):
        klass = healer if 'Healer' in nid else fighter
        bonus = DB.constants.value('unit_stats_as_bonus')
        unit = UnitPrefab(nid, name, 'An original Two Banners volunteer.', variant='',
                          klass=klass.nid,
                          bases={} if bonus else dict(klass.bases),
                          growths={} if bonus else dict(klass.growths),
                          wexp_gain=deepcopy(klass.wexp_gain),
                          starting_items=[['Heal' if 'Healer' in nid else 'Iron_Axe', False]])
        DB.units.append(unit)
    for team, party in PARTIES.items():
        leader = next(nid for nid, owner in OWNERS.items() if owner == team)
        DB.parties.append(PartyPrefab(party, party.replace('_', ' '), leader))
        DB.factions.append(Faction(FACTIONS[team], FACTIONS[team].replace('_', ' '),
                                   'Original allied banner', 'BlankEmblem'))
    for index, chapter in enumerate(CHAPTERS):
        width, height, barrier, lanes = (13, 8, 6, (2, 4)) if index == 0 else (16, 9, 8, (3, 5))
        tilemap = TileMapPrefab(chapter)
        tilemap.width, tilemap.height = width, height
        layer = tilemap.layers[0]
        for x in range(width):
            for y in range(height):
                wall = x == barrier and y not in lanes
                forest = (x, y) in ((barrier-2, lanes[0]-1), (barrier+2, lanes[1]+1))
                terrain = '9' if wall else '2' if forest else '1'
                layer.terrain_grid[x, y] = terrain
                layer.sprite_grid[x, y] = TileSprite('coop_placeholder', (1 if wall else 2 if forest else 0, 0), layer)
        RESOURCES.tilemaps.append(tilemap)
        level = LevelPrefab(chapter, TITLES[index])
        level.tilemap, level.party = chapter, PARTIES['player']
        level.music = {team + '_phase': None for team in DB.teams.keys()}
        level.objective = {'simple': 'Hold the crossings; rout Red. Both banners must survive.',
                           'win': 'Rout all Red units', 'loss': 'Either banner has no surviving deployed units'}
        positions = ((barrier-1, lanes[0]), (barrier-1, lanes[0]+1),
                     (barrier-1, lanes[1]), (barrier-2, lanes[0]))
        for (nid, team), pos in zip(OWNERS.items(), positions):
            level.units.append(UniqueUnit(nid=nid, team=team, ai='None', starting_position=pos))
        for number, pos in enumerate(((barrier+3, lanes[0]), (barrier+3, lanes[1]), (width-2, lanes[0]+1)), 1):
            level.units.append(GenericUnit(nid=f'{chapter}_Red_{number}', variant='', level=1,
                klass='Coop_Fighter', faction='Red_1', team='enemy', ai='Pursue',
                starting_items=[['Iron_Axe', False]], starting_position=pos))
        DB.levels.append(level)
        for trigger in ('combat_end', 'unit_wait', 'phase_change'):
            for result, condition in (
                ('victory', "not any(u.team == 'enemy' for u in game.get_all_units())"),
                ('defeat', "any(not any(u.team == t for u in game.get_all_units()) for t in ('player', 'other'))")):
                event = EventPrefab('Campaign ' + result + ' ' + trigger)
                event.level_nid, event.trigger, event.only_once = chapter, trigger, True
                event.condition = "not game.level_vars.get('coop_" + result + "') and " + condition
                event.source = 'level_var;coop_' + result + ';True'
                DB.events.append(event)
    return CHAPTERS[0]


class Campaign:
    def __init__(self, game):
        from app.engine import action
        self.index = 0
        self.ready = set()
        self.completed = []
        self.checkpoint = {'status': 'disabled', 'generation': 0, 'message': 'Checkpoint storage disabled'}
        game.current_mode.permadeath = True
        for team, party in PARTIES.items():
            if party not in game.parties:
                game._build_party(party)
        for nid, team in OWNERS.items():
            unit = game.get_unit(nid)
            unit.party = PARTIES[team]
            unit.faction = FACTIONS[team]
            action.do(action.SetExp(unit, 95))
            if 'Captain' in nid:
                action.do(action.SetHP(unit, 16))

    def observe_result(self, game):
        if game.level_vars.get('coop_victory') and not game.level_vars.get('coop_defeat'):
            chapter = CHAPTERS[self.index]
            if chapter not in self.completed:
                self.completed.append(chapter)

    def confirm_ready(self, game, team):
        from app.coop.protocol import ProtocolError
        if team in self.ready:
            raise ProtocolError('already_ready')
        self.ready.add(team)
        if self.ready != set(PARTIES):
            return
        # Called under the session lock, after completed LT result/event states.
        # Cleanup/initialization mutates only the existing shared singleton.
        game.clean_up()
        self.index += 1
        self.ready.clear()
        game.load_states(['start_level_asset_loading'])
        game.start_level(CHAPTERS[self.index])

    def projection(self, game):
        return {'id': ID, 'chapter': CHAPTERS[self.index], 'title': TITLES[self.index],
                'next_title': TITLES[self.index+1] if self.index+1 < len(CHAPTERS) else None,
                'completed': list(self.completed), 'ready': sorted(self.ready),
                'checkpoint': dict(self.checkpoint)}
