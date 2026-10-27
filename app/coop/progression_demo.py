"""Original progression variant; canonical training project/map stays untouched."""
from copy import deepcopy

LEVEL = 'coop_progression'


def install():
    from app.data.database.database import DB
    from app.engine.coop_demo import LEVEL as TRAINING
    klass = deepcopy(DB.classes.get('Coop_Fighter'))
    klass.nid = 'Coop_Progression_Fighter'
    klass.bases['HP'] = 40
    DB.classes.append(klass)
    level = deepcopy(DB.levels.get(TRAINING))
    level.nid = LEVEL
    level.name = 'Two Banners: Growth Drill'
    for unit in level.units:
        if unit.team in ('player', 'other'):
            unit.klass = klass.nid
        if unit.nid == 'Blue_Captain':
            unit.starting_position = (9, 3)
        elif unit.nid == 'Green_Captain':
            unit.starting_position = (9, 5)
        elif unit.nid == 'Red_3':
            # Keep the first counterattack round inspectable for both armies.
            unit.starting_position = (14, 9)
    DB.levels.append(level)
    # Reuse the trusted training objectives for this separate level.
    for event in list(DB.events):
        if event.level_nid == TRAINING:
            clone = deepcopy(event)
            clone.level_nid = LEVEL
            DB.events.append(clone)
    return LEVEL


def initialize(game):
    from app.engine import action
    for nid in ('Blue_Captain', 'Green_Captain'):
        action.do(action.SetExp(game.get_unit(nid), 95))
