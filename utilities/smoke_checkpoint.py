"""Complete shutdown/restart acceptance with independent graphical clients."""
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


class Processes:
    def __init__(self, folder):
        self.folder = folder
        self.handles = []
        self.logs = []

    def launch(self, name, *args):
        log = (self.folder / (name + '.log')).open('w', encoding='utf-8')
        self.logs.append(log)
        process = subprocess.Popen([sys.executable, '-u', str(ROOT / 'run_network.py'), *args],
            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.handles.append(process)
        return process

    def stop(self):
        for process in reversed(self.handles):
            if process.poll() is None:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                   capture_output=True, timeout=10)
                else:
                    process.terminate()
                process.wait(timeout=5)
        for log in self.logs:
            log.close()


def wait_invitations(folder, host):
    deadline = time.monotonic() + 30
    while not all((folder / (name + '.json')).exists() for name in ('blue', 'green')):
        if time.monotonic() >= deadline or host.poll() is not None:
            raise RuntimeError('Host startup failed; inspect host log')
        time.sleep(0.05)


def graphical_clients(processes, credentials, scripts):
    clients = []
    for name, team in (('blue', 'player'), ('green', 'other')):
        script = processes.folder / (name + '-script.json')
        script.write_text(json.dumps(scripts[team]), encoding='utf-8')
        clients.append(processes.launch(name, 'client', '--headless', '--session-file',
            str(credentials / (name + '.json')), '--script', str(script),
            '--report', str(processes.folder / (name + '-report.json')),
            '--screenshot', str(processes.folder / (name + '.png'))))
    for client in clients:
        client.wait(timeout=55)
        if client.returncode:
            raise RuntimeError('Graphical client failed; inspect ' + str(processes.folder))
    reports = [json.loads((processes.folder / (name + '-report.json')).read_text(encoding='utf-8'))
               for name in ('blue', 'green')]
    from app.coop.protocol import validate_packet
    for report in reports:
        for packet in report['observed']:
            validate_packet(packet)
    assert reports[0]['final'] == reports[1]['final']
    assert reports[0]['observed'] == reports[1]['observed']
    assert [p['revision'] for p in reports[0]['observed']] == list(range(len(reports[0]['observed'])))
    assert reports[0]['pid'] != reports[1]['pid']
    return reports


def credential_probes(old, fresh, old_session):
    from app.coop.client import Connection
    from app.coop.protocol import VERSION, ProtocolError
    from app.coop.security import validate_invitation
    for previous, current in zip(old, fresh):
        assert previous['token'] != current['token']
        try:
            Connection(**validate_invitation({**current, 'token': previous['token']}))
        except ProtocolError as exc:
            assert str(exc) == 'authentication_failed'
        else:
            raise AssertionError('Old credentials were accepted')
    clients = [Connection(**validate_invitation(invitation)) for invitation in fresh]
    try:
        deadline = time.monotonic() + 5
        while any(len(c.model.peers) != 2 for c in clients):
            assert time.monotonic() < deadline
            for client in clients:
                client.poll()
            time.sleep(0.005)
        packet = clients[0].model.packet
        assert packet['session'] != old_session
        clients[0].send({'v': VERSION, 'type': 'command', 'session': old_session,
            'revision': 0, 'phase': packet['state']['phase'], 'digest': packet['digest'],
            'id': 'old_session_command', 'action': 'ready'})
        while clients[0].model.message != 'Rejected: wrong_session':
            assert time.monotonic() < deadline
            for client in clients:
                client.poll()
            time.sleep(0.005)
        assert all(c.model.packet['revision'] == 0 for c in clients)
    finally:
        for client in clients:
            client.close()
    time.sleep(0.1)


def run_smoke(output, tls=False, recovery='none'):
    from utilities.campaign_playtest import plan
    scripts, _ = plan()  # Closed before either authoritative host process starts.
    folder = Path(output).resolve() / ('run-' + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    checkpoints = folder / 'checkpoints'
    options = []
    if tls:
        from utilities.create_tls_identity import create_identity
        certificate, key = create_identity(folder / 'tls')
        options = ['--tls-cert', str(certificate), '--tls-key', str(key), '--server-name', 'localhost']
    first_scripts, next_scripts = {}, {}
    for team, script in scripts.items():
        before, after = [], []
        for step in script:
            if step['action'] == 'wait_revision':
                phase = before if step['revision'] < 18 else after
            if step['action'] == 'wait_for':
                continue
            phase.append({**step, 'revision': step['revision'] - 18} if
                         step['action'] == 'wait_revision' and phase is after else step)
        first_scripts[team] = before + [{'action': 'wait_for', 'status': 'intermission'}]
        next_scripts[team] = after + [{'action': 'wait_for', 'status': 'victory'}]
    reports = []
    host_pids = []
    old = None
    for index in range(2):
        stage = folder / ('before' if index == 0 else 'after')
        stage.mkdir()
        credentials = stage / 'credentials'
        processes = Processes(stage)
        try:
            host_args = ['--scenario', 'campaign'] if index == 0 else ['--restore', str(checkpoints)]
            host = processes.launch('host', 'host', '--port', '0', '--session-dir', str(credentials),
                                    '--checkpoint-dir', str(checkpoints), *host_args, *options)
            host_pids.append(host.pid)
            wait_invitations(credentials, host)
            fresh = [json.loads((credentials / (name + '.json')).read_text(encoding='utf-8'))
                     for name in ('blue', 'green')]
            if index:
                credential_probes(old, fresh, reports[0][0]['final']['session'])
            else:
                old = fresh
            reports.append(graphical_clients(processes, credentials, first_scripts if index == 0 else next_scripts))
        finally:
            processes.stop()
        # Entire first host and both rendering clients have exited before any
        # checkpoint damage or the new host is started.
        assert all(p.poll() is not None for p in processes.handles)
        if index == 0:
            from app.coop.checkpoint import Store
            envelope, _ = Store(checkpoints).load()
            assert envelope['generation'] == 1
            assert reports[0][0]['final']['state']['campaign']['checkpoint']['status'] == 'saved'
            if recovery in ('corrupt', 'truncated'):
                path = checkpoints / 'current.json'
                raw = path.read_bytes()
                path.write_bytes(raw[:len(raw)//2] if recovery == 'truncated' else raw.replace(b'"checksum":"', b'"checksum":"bad', 1))
            elif recovery == 'interrupted':
                script = '''import os, sys
from pathlib import Path
from app.coop.checkpoint import Store
store = Store(sys.argv[1]); payload = store.load()[0]['payload']
replace = os.replace
def interrupted(source, destination):
    if Path(destination).name == 'current.json': os._exit(86)
    replace(source, destination)
os.replace = interrupted
store.save(payload)
'''
                result = subprocess.run([sys.executable, '-c', script, str(checkpoints)], cwd=ROOT,
                    capture_output=True, timeout=15,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                assert result.returncode == 86
                assert list(checkpoints.glob('.pending-*.tmp'))
    before = reports[0][0]['final']['state']
    restored = reports[1][0]['observed'][0]['state']
    old_units = {u['id']: u for u in before['units'] if u['owner']}
    new_units = {u['id']: u for u in restored['units'] if u['owner']}
    assert old_units.keys() == new_units.keys()
    for nid, unit in old_units.items():
        for key in ('owner', 'team', 'party', 'faction', 'class', 'persistent', 'level', 'exp',
                    'stats', 'hp', 'max_hp', 'wexp', 'mana', 'max_mana', 'skills', 'inventory', 'equipped', 'dead'):
            assert unit[key] == new_units[nid][key], (nid, key)
    assert before['rng'] == restored['rng']
    assert before['campaign']['completed'] == restored['campaign']['completed'] == ['alliance']
    assert restored['campaign']['ready'] == []
    assert restored['campaign']['checkpoint']['status'] == 'restored'
    final = reports[1][0]['final']
    assert final['revision'] == 20 and final['state']['status'] == 'victory'
    assert final['state']['campaign']['completed'] == ['alliance', 'holding']
    log = (folder / 'after/host.log').read_text(encoding='utf-8')
    assert 'NATIVE_CHECKPOINT_VERIFIED' in log
    if recovery in ('corrupt', 'truncated'):
        assert 'CHECKPOINT_RECOVERY current.json:' in log
    summary = {'host_pids': host_pids, 'client_pids': [[r['pid'] for r in stage] for stage in reports],
               'snapshots_compared': [len(stage[0]['observed']) for stage in reports],
               'final_revision': final['revision'], 'digest': final['digest'], 'tls': tls,
               'recovery': recovery, 'folder': str(folder)}
    (folder / 'result.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=str(ROOT / 'artifacts/checkpoint-smoke'))
    parser.add_argument('--tls', action='store_true')
    parser.add_argument('--recovery', choices=('none', 'corrupt', 'truncated', 'interrupted'), default='none')
    args = parser.parse_args()
    print('CHECKPOINT_SMOKE_OK', json.dumps(run_smoke(args.output, args.tls, args.recovery)))
