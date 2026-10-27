"""Opt-in local army ownership. No transport or presentation dependencies."""


def human_teams():
    from app.engine.game_state import game
    return tuple(game.game_vars.get('_human_teams', ('player',)))


def is_human_team(team):
    return team in human_teams()


def owns_current_phase(unit):
    from app.engine.game_state import game
    return is_human_team(unit.team) and unit.team == game.phase.get_current()


def selection_allowed(unit):
    # Existing single-player skills may override ownership. Co-op skills may
    # restrict selection, but cannot grant another army's units.
    from app.engine.game_state import game
    return '_human_teams' not in game.game_vars or owns_current_phase(unit)
