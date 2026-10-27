"""Run the local Blue -> Green -> Red experiment from the repository root."""
import os
from pathlib import Path


def main(smoke=False):
    os.chdir(Path(__file__).resolve().parent)
    from app import lt_log
    lt_log.create_logger()
    from app.engine.codegen import source_generator
    source_generator.generate_all()
    from app.data.database.database import DB
    from app.data.resources.resources import RESOURCES
    from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
    from app.engine import driver, game_state, config
    from app.engine.coop_demo import LEVEL, install_demo, enable_local_control
    RESOURCES.load('default.ltproj', CURRENT_SERIALIZATION_VERSION)
    DB.load('default.ltproj', CURRENT_SERIALIZATION_VERSION)
    driver.start('Two Banners - Local Co-op', from_editor=True)
    install_demo()
    # Map combat keeps this experiment independent of class battle animations.
    previous_animation = config.SETTINGS['animation']
    config.SETTINGS['animation'] = 'Never'
    try:
        game = game_state.start_level(LEVEL)
        enable_local_control(game)
        if smoke:
            smoke_run(game, driver)
        else:
            driver.run(game)
    finally:
        config.SETTINGS['animation'] = previous_animation
        config.save_settings()


def smoke_run(game, driver):
    """Exercise the actual rendering loop through Blue, Green, Red, Blue."""
    from app.engine import engine
    output = Path('artifacts')
    output.mkdir(exist_ok=True)
    loop = driver.MainLoop(game, wait_out_frame=True)
    seen = []
    for _ in range(900):
        if not loop.run_frame():
            raise RuntimeError('Game quit before smoke check completed')
        if game.state.current() != 'free' or game.state.temp_state:
            continue
        team = game.phase.get_current()
        if seen == ['player', 'other'] and team == 'player' and game.turncount == 2:
            print('COOP_SMOKE_OK: Blue -> Green -> Red AI -> Blue turn 2', flush=True)
            engine.terminate()
            return
        if team in seen:
            continue
        seen.append(team)
        engine.save_surface(loop.surf, str(output / ('coop-' + team + '.png')))
        game.state.change('turn_change')
        game.state.change('status_endstep')
        game.state.change('ai')
    raise RuntimeError('Co-op did not finish a round within 900 rendered frames')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke', action='store_true', help='Render one round and exit')
    main(parser.parse_args().smoke)
