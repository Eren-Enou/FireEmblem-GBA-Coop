"""Real native campaign, interleaved shared actions and two rendering processes."""
import argparse
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def plan(folder, defeat=False):
    from app.coop.shared_turns import SharedSimulation
    from app.coop.server import Session
    from app.coop.protocol import TEAMS
    from app.tests.test_network_coop import command
    from utilities.campaign_playtest import choose
    sim = SharedSimulation(scenario='campaign')
    scripts = {t: [{'action': 'overlay'}] for t in TEAMS}
    try:
        session = Session(sim)
        last_team = 'player'
        for index in range(180):
            packet = session.packet
            state = packet['state']
            if state['status'] in ('victory', 'defeat', 'fault'):
                break
            votes = state['campaign']['ready'] if state['status'] == 'intermission' else state['turns']['ready']
            team = 'other' if last_team == 'player' else 'player'
            if team in votes:
                team = next(t for t in TEAMS if t not in votes)
            kind, args = choose(state, team)
            if defeat:
                unit = next((u for u in state['units'] if u['team'] == team and not u['dead'] and not u['finished']), None)
                kind, args = ('wait', {'unit': unit['id']}) if unit else ('end_phase', {})
            for script in scripts.values():
                script.append({'action': 'wait_revision', 'revision': packet['revision']})
            if index == 0:
                scripts['player'] += [{'action': 'inspect', 'unit': 'Blue_Captain'},
                                      {'action': 'capture', 'path': str(folder / 'opening.png')}]
            if len(votes) == 1 and state['status'] == 'playing' and state['turn'] == 1 and state['campaign']['chapter'] == 'alliance':
                scripts[team].append({'action': 'capture', 'path': str(folder / 'one-ready.png')})
            scripts[team].append({'action': kind, **args})
            session.command(team, command(packet, kind, 'plan_' + str(index), **args), TEAMS)
            last_team = team
        assert session.packet['state']['status'] == ('defeat' if defeat else 'victory'), session.packet['result']
        for script in scripts.values():
            script.append({'action': 'wait_revision', 'revision': session.revision})
        return scripts, session.revision
    finally:
        sim.close()


def run_smoke(output='artifacts/shared-smoke', tls=False, defeat=False):
    from utilities.smoke_checkpoint import Processes, wait_invitations, graphical_clients
    folder = Path(output).resolve() / ('run-' + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    scripts, expected = plan(folder, defeat)  # Native planner closed before host startup.
    processes = Processes(folder)
    credentials = folder / 'invitations'
    try:
        options = []
        if tls:
            from utilities.create_tls_identity import create_identity
            cert, key = create_identity(folder / 'tls')
            options = ['--tls-cert', str(cert), '--tls-key', str(key), '--server-name', 'localhost']
        host = processes.launch('host', 'host', '--port', '0', '--scenario', 'campaign',
            '--turn-mode', 'shared', '--seed', '0', '--session-dir', str(credentials), *options)
        wait_invitations(credentials, host)
        reports = graphical_clients(processes, credentials, scripts)
        packets = reports[0]['observed']
        final = reports[0]['final']
        assert final['revision'] == expected and final['state']['status'] == ('defeat' if defeat else 'victory')
        if defeat:
            assert 'army eliminated' in final['state']['outcome']
        else:
            assert final['state']['campaign']['completed'] == ['alliance', 'holding']
        assert all(p['state']['turns']['mode'] == 'shared' and p['state']['phase'] == 'player' for p in packets)
        assert all(p['state']['campaign']['checkpoint']['status'] == 'disabled' for p in packets)
        results = [p['result'] for p in packets if p['result']]
        for team in (() if defeat else ('player', 'other')):
            assert any(r['team'] == team and r['action'] == 'heal' for r in results)
            assert any(r['team'] == team and r['action'] == 'attack' for r in results)
        for before, after in zip(packets, packets[1:]):
            if after['state']['turn'] > before['state']['turn']:
                assert len(before['state']['turns']['ready']) == 1
                assert after['result']['action'] == 'end_phase'
        result = {'folder': str(folder), 'host_pid': host.pid,
                  'client_pids': [r['pid'] for r in reports], 'snapshots': len(packets),
                  'revision': final['revision'], 'status': final['state']['status'], 'digest': final['digest'], 'tls': tls}
        (folder / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print('SHARED_GRAPHICAL_OK ' + json.dumps(result), flush=True)
        return result
    finally:
        processes.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='artifacts/shared-smoke')
    parser.add_argument('--tls', action='store_true')
    parser.add_argument('--defeat', action='store_true', help='Passive native defeat instead of the cooperative victory tactic')
    args = parser.parse_args()
    run_smoke(args.output, args.tls, args.defeat)
