"""Independent co-op clients; loopback TCP or explicit verified TLS endpoints."""
import argparse
import asyncio
import json
import os
from pathlib import Path


async def host(args):
    from app.coop.security import is_loopback, server_context, validate_listener
    from app.coop.protocol import require
    context = server_context(args.tls_cert, args.tls_key) if args.tls_cert else None
    validate_listener(args.bind, context)
    advertised = args.advertise_host or args.bind
    require(advertised not in ('0.0.0.0', '::'), 'advertise_host_required')
    require(context is not None or is_loopback(advertised), 'tls_required_for_remote')
    tls = {'ca_pem': Path(args.tls_cert).read_text(encoding='utf-8'),
           'server_name': args.server_name} if context else None
    if tls:
        # Catch unusable trust anchors before emitting join invitations.
        from app.coop.security import client_context
        client_context(tls)
    from app.coop.simulation import Simulation
    from app.coop.server import Host, Session
    simulation = Simulation(seed=args.seed, scenario=args.scenario, growth_method=args.growth_method)
    try:
        session = Session(simulation)
        service = Host(session)
        server = await service.listen(args.port, args.bind, context)
        port = server.sockets[0].getsockname()[1]
        folder = Path(args.session_dir)
        folder.mkdir(parents=True, exist_ok=True)
        for team, name in (('player', 'blue'), ('other', 'green')):
            path = folder / (name + '.json')
            # Private local credentials. Never printed or transmitted in state.
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                invitation = {'host': advertised, 'port': port, 'token': session.tokens[team]}
                if tls:
                    invitation['tls'] = tls
                json.dump(invitation, stream)
        print(f'HOST_READY {args.bind}:{port}; {"TLS" if context else "loopback plaintext"}; invitation files: {folder.resolve()}', flush=True)
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
    server.add_argument('--scenario', choices=('training', 'progression', 'healing', 'campaign'), default='training')
    server.add_argument('--growth-method', choices=('Fixed', 'Random', 'Dynamic'),
                        help='Host-only player growth setting; progression drill defaults to Fixed')
    server.add_argument('--session-dir', default='artifacts/network')
    server.add_argument('--bind', default='127.0.0.1', help='Literal local IP; non-loopback requires TLS')
    server.add_argument('--advertise-host', help='Address clients can reach; required for wildcard binds')
    server.add_argument('--tls-cert', help='Host certificate PEM (also the development trust anchor)')
    server.add_argument('--tls-key', help='Private key PEM; never share this file')
    server.add_argument('--server-name', help='Expected certificate DNS name or IP')
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
        if any((args.tls_cert, args.tls_key, args.server_name)) and not all((args.tls_cert, args.tls_key, args.server_name)):
            parser.error('--tls-cert, --tls-key and --server-name must be supplied together')
        try:
            asyncio.run(host(args))
        except KeyboardInterrupt:
            pass
    else:
        if args.headless:
            os.environ['SDL_VIDEODRIVER'] = 'dummy'
            os.environ['SDL_AUDIODRIVER'] = 'dummy'
        from app.coop.client import Connection
        from app.coop.security import validate_invitation
        from app.coop.view import run
        credentials = json.loads(Path(args.session_file).read_text(encoding='utf-8'))
        connection = Connection(**validate_invitation(credentials))
        script = json.loads(Path(args.script).read_text(encoding='utf-8')) if args.script else None
        run(connection, script, args.report, args.screenshot)


if __name__ == '__main__':
    main()
