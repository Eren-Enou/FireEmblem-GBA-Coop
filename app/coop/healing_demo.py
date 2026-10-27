"""Original allied-support encounter; no project files or other scenarios change."""
from copy import deepcopy

LEVEL = 'coop_healing'


def install():
    from app.data.database.database import DB
    from app.data.database.factions import Faction
    from app.data.database.level_units import GenericUnit
    from app.engine.coop_demo import LEVEL as TRAINING
    from app.data.resources.resources import RESOURCES
    from app.data.resources.tiles import TileSprite
    fighter = deepcopy(DB.classes.get('Coop_Fighter'))
    fighter.nid = 'Coop_Healing_Vanguard'
    fighter.bases.update(HP=36, DEF=7)
    DB.classes.append(fighter)
    healer = deepcopy(DB.classes.get('Cleric'))
    healer.nid = 'Coop_Healing_Cleric'
    healer.map_sprite_nid = 'coop_token'
    DB.classes.append(healer)
    tilemap = deepcopy(RESOURCES.tilemaps.get(TRAINING))
    tilemap.nid = LEVEL
    layer = tilemap.layers[0]
    for pos in ((7, 4), (7, 6)):
        layer.terrain_grid[pos] = '9'
        layer.sprite_grid[pos] = TileSprite('coop_placeholder', (1, 0), layer)
    RESOURCES.tilemaps.append(tilemap)
    level = deepcopy(DB.levels.get(TRAINING))
    level.tilemap = LEVEL
    level.nid, level.name = LEVEL, 'Two Banners: Mutual Aid'
    level.units.clear()
    for nid, team, klass, pos, item in (
        ('Blue_Captain', 'player', fighter.nid, (6, 3), 'Iron_Axe'),
        ('Blue_Healer', 'player', healer.nid, (6, 4), 'Heal'),
        ('Green_Captain', 'other', fighter.nid, (6, 5), 'Iron_Axe'),
        ('Green_Healer', 'other', healer.nid, (5, 3), 'Heal'),
        ('Red_1', 'enemy', 'Coop_Fighter', (10, 3), 'Iron_Axe'),
        ('Red_2', 'enemy', 'Coop_Fighter', (10, 5), 'Iron_Axe'),
        ('Red_3', 'enemy', 'Coop_Fighter', (12, 4), 'Iron_Axe')):
        if not DB.factions.get(nid):
            DB.factions.append(Faction(nid, nid.replace('_', ' '), 'Training volunteer', 'BlankEmblem'))
        level.units.append(GenericUnit(nid=nid, variant='', level=1, klass=klass,
            faction=nid, team=team, ai='Pursue' if team == 'enemy' else 'None',
            starting_items=[[item, False]], starting_position=pos))
    DB.levels.append(level)
    for event in list(DB.events):
        if event.level_nid == TRAINING:
            clone = deepcopy(event)
            clone.level_nid = LEVEL
            DB.events.append(clone)
    return LEVEL


def initialize(game):
    from app.engine import action
    for nid in ('Blue_Captain', 'Green_Captain'):
        action.do(action.SetHP(game.get_unit(nid), 16))
    for nid in ('Blue_Healer', 'Green_Healer'):
        action.do(action.SetExp(game.get_unit(nid), 95))
