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


def run_smoke(output, tls=False, progression=False, healing=False, campaign=False):
    if sum((progression, healing, campaign)) > 1:
        raise ValueError("Choose one smoke scenario")
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
    if progression:
        blue = [{'action': 'attack', 'unit': 'Blue_Captain', 'item': 100, 'target': 'Red_1'},
                {'action': 'wait', 'unit': 'Blue_Guard'}, {'action': 'end_phase'},
                {'action': 'wait_for', 'phase': 'player', 'turn': 2},
                {'action': 'end_phase'}, {'action': 'wait_for', 'phase': 'other', 'turn': 2}]
        green = [{'action': 'wait_for', 'phase': 'other', 'turn': 1},
                 {'action': 'attack', 'unit': 'Green_Captain', 'item': 102, 'target': 'Red_2'},
                 {'action': 'wait', 'unit': 'Green_Guard'}, {'action': 'end_phase'},
                 {'action': 'wait_for', 'phase': 'other', 'turn': 2}]
    if healing:
        blue = [{'action': 'heal', 'unit': 'Blue_Healer', 'item': 101, 'target': 'Green_Captain'},
                {'action': 'wait', 'unit': 'Blue_Captain'}, {'action': 'end_phase'},
                {'action': 'wait_for', 'phase': 'player', 'turn': 2},
                {'action': 'attack_nearest', 'unit': 'Blue_Captain'},
                {'action': 'heal', 'unit': 'Blue_Healer', 'item': 101, 'target': 'Green_Captain'},
                {'action': 'end_phase'}, {'action': 'wait_for', 'phase': 'player', 'turn': 3},
                {'action': 'inspect', 'unit': 'Blue_Healer'}]
        green = [{'action': 'wait_for', 'phase': 'other', 'turn': 1},
                 {'action': 'heal', 'unit': 'Green_Healer', 'item': 103, 'target': 'Blue_Captain'},
                 {'action': 'wait', 'unit': 'Green_Captain'}, {'action': 'end_phase'},
                 {'action': 'wait_for', 'phase': 'other', 'turn': 2},
                 {'action': 'attack_nearest', 'unit': 'Green_Captain'},
                 {'action': 'heal', 'unit': 'Green_Healer', 'item': 103, 'target': 'Blue_Captain'},
                 {'action': 'end_phase'}, {'action': 'wait_for', 'phase': 'player', 'turn': 3},
                 {'action': 'inspect', 'unit': 'Green_Healer'}]
    if campaign:
        from utilities.campaign_playtest import plan
        scripts, expected_revision = plan()
        blue, green = scripts['player'], scripts['other']
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
        if progression or healing or campaign:
            options += ['--scenario', 'campaign' if campaign else 'healing' if healing else 'progression']
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
        if campaign:
            assert final['revision'] == expected_revision
            assert final['state']['status'] == 'victory'
            assert final['state']['campaign']['completed'] == ['alliance', 'holding']
            boundary = next(p for p in packets if p['state']['status'] == 'intermission')
            loaded = next(p for p in packets if p['state']['campaign']['chapter'] == 'holding')
            assert (boundary['state']['width'], loaded['state']['width']) == (13, 16)
            old = {u['id']: u for u in boundary['state']['units'] if u['owner']}
            new = {u['id']: u for u in loaded['state']['units'] if u['owner']}
            assert old.keys() == new.keys()
            for nid in old:
                for key in ('owner', 'party', 'faction', 'class', 'level', 'exp', 'stats', 'wexp', 'inventory', 'skills', 'equipped', 'dead'):
                    assert old[nid][key] == new[nid][key], (nid, key)
            assert sum(p['result']['action'] == 'ready' for p in packets if p['result']) == 2
        else:
            assert (final['state']['turn'], final['state']['phase']) == ((3, 'player') if healing else (2, 'other'))
        for team in ('player', 'other'):
            if not (progression or healing or campaign):
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
        if progression:
            for nid in ('Blue_Captain', 'Green_Captain'):
                old = next(u for u in packets[0]['state']['units'] if u['id'] == nid)
                grown = next(u for u in final['state']['units'] if u['id'] == nid)
                assert not grown['dead']
                assert grown['level'] == 2 and grown['stats']['STR'] > old['stats']['STR']
                assert grown['max_hp'] > old['max_hp']
                assert any(p['result'] and nid + ': XP' in p['result']['summary'] and 'LEVEL UP' in p['result']['summary'] for p in packets)
        if healing:
            for team in ('player', 'other'):
                uses = [i for i, p in enumerate(packets) if p['result'] and
                        p['result']['team'] == team and p['result']['action'] == 'heal']
                assert uses, 'No healing for ' + team
                cross = False
                for i in uses:
                    before = {u['id']: u for u in packets[i-1]['state']['units']}
                    after = {u['id']: u for u in packets[i]['state']['units']}
                    restored = [key for key in before if after[key]['hp'] > before[key]['hp']]
                    assert restored, 'Healing did not restore HP'
                    cross |= any(before[key]['team'] != team for key in restored)
                    healer = next(u for u in after.values() if u['team'] == team and 'Healer' in u['id'])
                    assert healer['inventory'] != before[healer['id']]['inventory']
                assert cross, 'No cross-army healing for ' + team
                assert after[healer['id']]['level'] == 2
        summary = {'host_pid': host.pid, 'client_pids': [r['pid'] for r in reports],
                   'revision': final['revision'], 'digest': final['digest'],
                   'snapshots_compared': len(packets), 'tls': tls, 'progression': progression, 'healing': healing, 'campaign': campaign, 'folder': str(folder)}
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
    parser.add_argument('--progression', action='store_true', help='Verify both armies leveling in the separate growth drill')
    parser.add_argument('--healing', action='store_true', help='Verify cross-army healing and subsequent combat')
    parser.add_argument('--campaign', action='store_true', help='Complete both original chapters with native persistent armies')
    args = parser.parse_args()
    print('NETWORK_SMOKE_OK', json.dumps(run_smoke(args.output, args.tls, args.progression, args.healing, args.campaign)))
