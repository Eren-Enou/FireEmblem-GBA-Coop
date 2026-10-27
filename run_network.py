"""Phase 2: loopback host and independent Blue/Green game clients."""
import argparse
import asyncio
import json
import os
from pathlib import Path


async def host(args):
    from app.coop.simulation import Simulation
    from app.coop.server import Host, Session
    simulation = Simulation(seed=args.seed)
    try:
        session = Session(simulation)
        service = Host(session)
        server = await service.listen(args.port)
        port = server.sockets[0].getsockname()[1]
        folder = Path(args.session_dir)
        folder.mkdir(parents=True, exist_ok=True)
        for team, name in (('player', 'blue'), ('other', 'green')):
            path = folder / (name + '.json')
            # Private local credentials. Never printed or transmitted in state.
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump({'host': '127.0.0.1', 'port': port, 'token': session.tokens[team]}, stream)
        print(f'HOST_READY 127.0.0.1:{port}; credential files: {folder.resolve()}', flush=True)
        async with server:
            await server.serve_forever()
    finally:
        simulation.close()


def main():
    os.chdir(Path(__file__).resolve().parent)
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    server = modes.add_parser('host', help='Start the authoritative local simulation')
    server.add_argument('--port', type=int, default=38670)
    server.add_argument('--seed', type=int, default=0)
    server.add_argument('--session-dir', default='artifacts/network')
    client = modes.add_parser('client', help='Open an independent tactical client')
    client.add_argument('--session-file', required=True)
    client.add_argument('--script', help='Optional local JSON automation steps (tests only)')
    client.add_argument('--report', help='Optional ignored test report path')
    client.add_argument('--screenshot', help='Optional ignored final rendering path')
    client.add_argument('--headless', action='store_true')
    args = parser.parse_args()
    if args.mode == 'host':
        if not 0 <= args.port <= 65535:
            parser.error('port must be between 0 and 65535')
        if not 0 <= args.seed <= 1023:
            parser.error('seed must be between 0 and 1023')
        try:
            asyncio.run(host(args))
        except KeyboardInterrupt:
            pass
    else:
        if args.headless:
            os.environ['SDL_VIDEODRIVER'] = 'dummy'
            os.environ['SDL_AUDIODRIVER'] = 'dummy'
        from app.coop.client import Connection
        from app.coop.protocol import fields, string
        from app.coop.view import run
        credentials = json.loads(Path(args.session_file).read_text(encoding='utf-8'))
        fields(credentials, ('host', 'port', 'token'))
        string(credentials['token'], 256)
        connection = Connection(**credentials)
        script = json.loads(Path(args.script).read_text(encoding='utf-8')) if args.script else None
        run(connection, script, args.report, args.screenshot)


if __name__ == '__main__':
    main()
