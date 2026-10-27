"""Launch one real host and two real rendering clients; verify their reports."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run_smoke(output, tls=False):
    folder = Path(output).resolve() / ('run-' + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    blue = [{'action': 'advance', 'unit': 'Blue_Captain'},
            {'action': 'wait', 'unit': 'Blue_Guard'}, {'action': 'end_phase'},
            {'action': 'wait_for', 'phase': 'player', 'turn': 2},
            {'action': 'attack_nearest', 'unit': 'Blue_Captain'}, {'action': 'end_phase'},
            {'action': 'wait_for', 'phase': 'other', 'turn': 2}]
    green = [{'action': 'wait_for', 'phase': 'other', 'turn': 1},
             {'action': 'attack_nearest', 'unit': 'Green_Captain'},
             {'action': 'wait', 'unit': 'Green_Guard'}, {'action': 'end_phase'},
             {'action': 'wait_for', 'phase': 'other', 'turn': 2}]
    processes, logs = [], []

    def launch(name, *args):
        log = (folder / (name + '.log')).open('w', encoding='utf-8')
        logs.append(log)
        process = subprocess.Popen([sys.executable, '-u', str(ROOT / 'run_network.py'), *args],
                                   cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        processes.append(process)
        return process

    try:
        options = []
        if tls:
            from utilities.create_tls_identity import create_identity
            certificate, key = create_identity(folder / 'tls')
            options = ['--tls-cert', str(certificate), '--tls-key', str(key), '--server-name', 'localhost']
        host = launch('host', 'host', '--port', '0', '--session-dir', str(folder / 'credentials'), *options)
        deadline = time.monotonic() + 30
        while not all((folder / 'credentials' / (name + '.json')).exists() for name in ('blue', 'green')):
            if host.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError('Host did not start; inspect ' + str(folder / 'host.log'))
            time.sleep(0.05)
        clients = []
        for name, script in (('blue', blue), ('green', green)):
            script_path = folder / (name + '-script.json')
            script_path.write_text(json.dumps(script), encoding='utf-8')
            clients.append(launch(name, 'client', '--headless', '--session-file',
                str(folder / 'credentials' / (name + '.json')), '--script', str(script_path),
                '--report', str(folder / (name + '-report.json')),
                '--screenshot', str(folder / (name + '.png'))))
        for process in clients:
            process.wait(timeout=55)
            if process.returncode:
                raise RuntimeError('Client failed; inspect logs under ' + str(folder))
        reports = [json.loads((folder / (name + '-report.json')).read_text()) for name in ('blue', 'green')]
        from app.coop.protocol import validate_packet
        assert reports[0]['pid'] != reports[1]['pid'] != host.pid
        assert [r['team'] for r in reports] == ['player', 'other']
        for report in reports:
            for packet in report['observed']:
                validate_packet(packet)
        assert reports[0]['final'] == reports[1]['final'], 'Clients ended with different authoritative results'
        histories = [{p['revision']: p for p in r['observed']} for r in reports]
        assert histories[0] == histories[1], 'Clients observed different revision histories'
        packets = reports[0]['observed']
        assert [p['revision'] for p in packets] == list(range(len(packets)))
        final = reports[0]['final']
        assert final['state']['turn'] == 2 and final['state']['phase'] == 'other'
        for team in ('player', 'other'):
            assert any(p['result'] and p['result']['team'] == team and p['result']['action'] == 'move' for p in packets)
            combats = [i for i, p in enumerate(packets) if p['result'] and
                       p['result']['team'] == team and p['result']['action'] == 'attack']
            assert combats, 'No real combat for ' + team
            for i in combats:
                old, new = packets[i-1]['state']['units'], packets[i]['state']['units']
                assert any(a['hp'] != b['hp'] for a, b in zip(old, new)), 'Combat did not change HP'
                assert any(a['inventory'] != b['inventory'] for a, b in zip(old, new)), 'Combat did not consume durability'
        ai_index = next(i for i, p in enumerate(packets) if p['result'] and
                        p['result']['team'] == 'other' and p['result']['action'] == 'end_phase')
        assert any(a != b for a, b in zip(packets[ai_index-1]['state']['units'],
                                        packets[ai_index]['state']['units']) if a['team'] == 'enemy')
        summary = {'host_pid': host.pid, 'client_pids': [r['pid'] for r in reports],
                   'revision': final['revision'], 'digest': final['digest'],
                   'snapshots_compared': len(packets), 'tls': tls, 'folder': str(folder)}
        (folder / 'result.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        return summary
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                if os.name == 'nt':
                    # The venv executable can be a redirector with a child
                    # interpreter. Stop our owned process tree, not just that
                    # launcher, before closing logs/removing a test directory.
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                   capture_output=True, timeout=10)
                else:
                    process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        for log in logs:
            log.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=str(ROOT / 'artifacts/network-smoke'))
    parser.add_argument('--tls', action='store_true', help='Use generated identity and verified TLS clients')
    args = parser.parse_args()
    print('NETWORK_SMOKE_OK', json.dumps(run_smoke(args.output, args.tls)))
