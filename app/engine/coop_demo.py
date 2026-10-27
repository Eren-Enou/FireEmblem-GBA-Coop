"""Original local hot-seat scenario, installed in memory after project loading.

The project on disk is never modified. UI, sound and item definitions still
come from the installed development project; this is not a redistributable game.
"""
from copy import deepcopy

import pygame

from app.constants import COLORKEY
from app.data.database.database import DB
from app.data.database.factions import Faction
from app.data.database.levels import LevelPrefab
from app.data.database.level_units import GenericUnit
from app.data.resources.resources import RESOURCES
from app.data.resources.tiles import TileMapPrefab, TileSet, TileSprite
from app.data.resources.map_sprites import MapSprite
from app.data.resources.default_palettes import default_palettes
from app.events.event_prefab import EventPrefab

LEVEL = 'coop_training'
BLUE = ('Blue_Captain', 'Blue_Guard')
GREEN = ('Green_Captain', 'Green_Guard')
RED = ('Red_1', 'Red_2', 'Red_3')


def install_demo():
    """Call once after loading default.ltproj, with a display available."""
    DB.teams.move_index(DB.teams.index('other'), 1)
    DB.teams.set_allies('player', ['other'])
    DB.teams.set_allies('other', ['player'])
    DB.constants.get('initiative').value = False
    DB.constants.get('turnwheel').value = False
    # Avoid unrelated sample story events and game-over conditions.
    DB.events.clear()

    tiles = TileSet('coop_placeholder')
    tiles.image = pygame.Surface((48, 16)).convert()
    for idx, color in enumerate(((98, 134, 94), (43, 56, 64), (44, 95, 62))):
        pygame.draw.rect(tiles.image, color, (idx * 16, 0, 16, 16))
        pygame.draw.rect(tiles.image, (30, 49, 42), (idx * 16, 0, 16, 16), 1)
    RESOURCES.tilesets.append(tiles)
    tilemap = TileMapPrefab(LEVEL)
    tilemap.width, tilemap.height = 15, 10
    layer = tilemap.layers[0]
    for x in range(15):
        for y in range(10):
            wall = x == 7 and y not in (3, 4, 5, 6)
            forest = (x, y) in ((5, 2), (5, 7), (9, 2), (9, 7))
            layer.terrain_grid[x, y] = '9' if wall else '2' if forest else '1'
            layer.sprite_grid[x, y] = TileSprite(tiles.nid, (1 if wall else 2 if forest else 0, 0), layer)
    RESOURCES.tilemaps.append(tilemap)

    # Original geometric tokens in LT's blue source palette. The ordinary map
    # sprite renderer recolors them for green/red and the exhausted state.
    sprite = MapSprite('coop_token')
    sprite.standing_image = pygame.Surface((192, 144)).convert()
    sprite.moving_image = pygame.Surface((192, 160)).convert()
    color = default_palettes['map_sprite_blue'][8]
    for image, fw, fh, rows, cols in ((sprite.standing_image, 64, 48, 3, 3),
                                     (sprite.moving_image, 48, 40, 4, 4)):
        image.fill(COLORKEY)
        for row in range(rows):
            for col in range(cols):
                cx, cy = col * fw + fw // 2, row * fh + fh - 12
                pygame.draw.circle(image, (64, 56, 56), (cx, cy), 7)
                pygame.draw.circle(image, color, (cx, cy), 5)
                pygame.draw.line(image, (248, 248, 248), (cx - 2, cy), (cx + 2, cy), 1)
    RESOURCES.map_sprites.append(sprite)
    klass = deepcopy(DB.classes.get('Fighter'))
    klass.nid, klass.name, klass.map_sprite_nid = 'Coop_Fighter', 'Vanguard', sprite.nid
    klass.bases.update({'HP': 28, 'STR': 7, 'SKL': 12, 'SPD': 7, 'DEF': 5, 'RES': 2})
    DB.classes.append(klass)

    level = LevelPrefab(LEVEL, 'Two Banners: Training Ground')
    level.tilemap = LEVEL
    level.party = DB.parties[0].nid
    level.objective = {'simple': 'Blue + Green: defeat all red units',
                       'win': 'Defeat all red units together',
                       'loss': 'Either army loses all its units'}
    level.music = {team + '_phase': None for team in DB.teams.keys()}
    for nid, team, pos in ((BLUE[0], 'player', (2, 3)), (BLUE[1], 'player', (2, 5)),
                           (GREEN[0], 'other', (4, 3)), (GREEN[1], 'other', (4, 5)),
                           (RED[0], 'enemy', (10, 3)), (RED[1], 'enemy', (10, 5)),
                           (RED[2], 'enemy', (12, 4))):
        DB.factions.append(Faction(nid, nid.replace('_', ' '), 'Training volunteer', 'BlankEmblem'))
        level.units.append(GenericUnit(nid=nid, variant='', level=1, klass=klass.nid,
                                      faction=nid, team=team, ai='None' if team != 'enemy' else 'Pursue',
                                      starting_items=[['Iron_Axe', False]], starting_position=pos))
    DB.levels.append(level)
    for trigger in ('combat_end', 'unit_wait', 'phase_change'):
        event = EventPrefab('Shared victory ' + trigger)
        event.level_nid, event.trigger, event.only_once = LEVEL, trigger, True
        event.condition = "not game.level_vars.get('coop_victory') and not any(u.team == 'enemy' for u in game.get_all_units())"
        event.source = 'level_var;coop_victory;True\nalert;Blue and Green win together!\nwin_game'
        DB.events.append(event)
        defeat = EventPrefab('Shared defeat ' + trigger)
        defeat.level_nid, defeat.trigger, defeat.only_once = LEVEL, trigger, True
        defeat.condition = "any(not any(u.team == t for u in game.get_all_units()) for t in ('player', 'other'))"
        defeat.source = 'lose_game'
        DB.events.append(defeat)


def enable_local_control(game):
    game.game_vars['_human_teams'] = ['player', 'other']
    game.game_vars['_turnwheel'] = False
    game.game_vars['_local_coop_demo'] = True
