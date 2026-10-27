"""Reproduce current parity/save gaps without writing or loading a game save."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def audit():
    from app.coop.simulation import Simulation
    probes = []
    persistence = None
    save_findings = None
    for team, nid in (('player', 'Blue_Captain'), ('other', 'Green_Captain')):
        simulation = Simulation(seed=0)
        try:
            from app.engine import action
            from app.utilities import static_random
            if team == 'other':
                simulation.execute('player', {'action': 'end_phase'})
            unit = simulation.game.get_unit(nid)
            enemy = simulation.game.get_unit('Red_1')
            # Trusted fixture setup, never a command exposed to network peers.
            action.do(action.Teleport(unit, (9, 3)))
            static_random.set_combat_random_state(0)
            before = (unit.exp, unit.get_hp(), enemy.get_hp(), unit.items[0].data['uses'])
            choice = simulation.attacks(unit)[0]
            simulation.execute(team, {'action': 'attack', 'unit': nid, **choice})
            probes.append({'team': team, 'xp_before': before[0], 'xp_after': unit.exp,
                           'hp_before': before[1], 'hp_after': unit.get_hp(),
                           'enemy_hp_before': before[2], 'enemy_hp_after': enemy.get_hp(),
                           'uses_before': before[3], 'uses_after': unit.items[0].data['uses']})
            persistence = [{'id': u.nid, 'persistent': u.persistent, 'party': u.party}
                           for u in simulation.units if u.team in ('player', 'other')]
            state, _ = simulation.game.save()
            try:
                json.dumps(state, allow_nan=False)
                json_error = None
            except (TypeError, ValueError) as exc:
                json_error = type(exc).__name__ + ': ' + str(exc)
            save_findings = {'json_error': json_error,
                             'phase_keys': [k for k in state if 'phase' in k],
                             'rng_keys': [k for k in state if 'random' in k],
                             'keys': sorted(state)}
        finally:
            simulation.close()
    return {'format': 'campaign-readiness/v1', 'combat_seed': 0, 'combat_probes': probes,
            'human_rosters': persistence, 'engine_save_findings': save_findings,
            'scope': 'diagnostic evidence only; not a campaign save or load implementation'}


if __name__ == '__main__':
    os.chdir(ROOT)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='artifacts/campaign-readiness.json')
    args = parser.parse_args()
    report = audit()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('READINESS_AUDIT_WRITTEN', path.resolve())
