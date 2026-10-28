"""One-PC playtest: fresh host and two independent visible clients.

Ctrl+C stops only this launcher's children. Rerun for a new session. Existing
campaign checkpoints are never opened or overwritten by this launcher.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--turn-mode', choices=('sequential', 'shared'), default='sequential')
    parser.add_argument('--scenario', choices=('training', 'healing', 'campaign'), default='campaign')
    parser.add_argument('--seed', type=int, default=0, choices=range(1024), metavar='0..1023')
    args = parser.parse_args()
    folder = ROOT / 'artifacts' / 'solo' / ('run-' + uuid.uuid4().hex)
    folder.mkdir(parents=True)
    processes, logs = [], []

    def launch(name, *options):
        log = (folder / (name + '.log')).open('w', encoding='utf-8')
        logs.append(log)
        process = subprocess.Popen([sys.executable, '-u', str(ROOT / 'run_network.py'), *options],
            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        processes.append(process)
        return process

    try:
        options = ['--turn-mode', args.turn_mode, '--scenario', args.scenario, '--seed', str(args.seed)]
        if args.turn_mode == 'sequential' and args.scenario == 'campaign':
            options += ['--checkpoint-dir', str(folder / 'checkpoints')]
        host = launch('host', 'host', '--port', '0', '--session-dir', str(folder / 'invitations'), *options)
        deadline = time.monotonic() + 40
        while not all((folder / 'invitations' / (name + '.json')).exists() for name in ('blue', 'green')):
            if host.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError('Host startup failed; inspect ' + str(folder / 'host.log'))
            time.sleep(0.05)
        for name in ('blue', 'green'):
            launch(name, 'client', '--session-file', str(folder / 'invitations' / (name + '.json')))
        print('Two visible clients launched: ' + args.turn_mode, flush=True)
        print('Private logs/invitations: ' + str(folder), flush=True)
        print('Alt+Tab between Blue and Green. E: Ready/end phase; I: details.', flush=True)
        print('Retry: Ctrl+C here, then rerun this command. Each run creates new credentials.', flush=True)
        print('Shared mode has NO saves.' if args.turn_mode == 'shared' else
              'This run uses a NEW checkpoint folder; previous runs are preserved.', flush=True)
        while host.poll() is None:
            time.sleep(0.2)
        raise RuntimeError('Host exited; inspect ' + str(folder / 'host.log'))
    except KeyboardInterrupt:
        pass
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=10)
                else:
                    process.terminate()
                process.wait(timeout=5)
        for log in logs:
            log.close()


if __name__ == '__main__':
    main()
