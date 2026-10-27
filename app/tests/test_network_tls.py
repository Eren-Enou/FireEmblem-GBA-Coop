"""Real TLS handshakes, identity failures before hello, and graphical processes."""
import asyncio
from copy import deepcopy
from pathlib import Path
import socket
import ssl
import tempfile
import unittest
from unittest.mock import patch

from app.coop.client import Connection
from app.coop.protocol import ProtocolError
from app.coop.security import client_context, server_context, validate_invitation, validate_listener
from app.coop.server import Host, Session
from app.coop.simulation import Simulation
from utilities.create_tls_identity import create_identity


class PolicyTests(unittest.TestCase):
    def test_remote_plaintext_rejected_before_connect(self):
        with patch('socket.create_connection') as opened:
            with self.assertRaisesRegex(ProtocolError, 'tls_required_for_remote'):
                Connection('192.0.2.1', 38670, 'never_sent')
            opened.assert_not_called()
        with patch('socket.create_connection') as opened:
            opened.return_value.getpeername.return_value = ('192.0.2.1', 38670)
            with self.assertRaisesRegex(ProtocolError, 'tls_required_for_remote'):
                Connection('localhost', 38670, 'never_sent')
            opened.return_value.close.assert_called_once()
        with self.assertRaisesRegex(ProtocolError, 'tls_required_for_remote'):
            validate_listener('0.0.0.0', None)
        with self.assertRaisesRegex(ProtocolError, 'tls_required_for_remote'):
            validate_invitation({'host': '192.0.2.1', 'port': 38670, 'token': 'never_sent'})

    def test_plaintext_loopback_invitation_still_compatible(self):
        invitation = {'host': '127.0.0.1', 'port': 38670, 'token': 'local_only'}
        self.assertEqual(validate_invitation(invitation), invitation)
        validate_listener('127.0.0.1', None)

    def test_identity_generation_refuses_overwrite_and_invalid_names(self):
        with tempfile.TemporaryDirectory() as folder:
            certificate, key = create_identity(folder)
            original = key.read_bytes()
            with self.assertRaises(FileExistsError):
                create_identity(folder)
            self.assertEqual(key.read_bytes(), original)
            for name in ('host\nsubjectAltName=DNS:evil', '/CN=evil', 'bad name', 'a;command'):
                with self.assertRaises(ValueError):
                    create_identity(Path(folder) / 'invalid', name)
            self.assertTrue(certificate.exists())


class TLSSocketTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='lt-tls-test-')
        self.addCleanup(self.folder.cleanup)
        certificate, key = create_identity(Path(self.folder.name) / 'host')
        self.pem = certificate.read_text()
        self.context = server_context(str(certificate), str(key))
        self.sim = Simulation()
        self.addCleanup(self.sim.close)

    async def asyncSetUp(self):
        self.session = Session(self.sim)
        self.host = Host(self.session)
        self.server = await self.host.listen(0, tls_context=self.context)
        self.port = self.server.sockets[0].getsockname()[1]
        self.clients = []

    async def asyncTearDown(self):
        for client in self.clients:
            await asyncio.to_thread(client.close)
        self.server.close()
        await self.server.wait_closed()
        for _ in range(100):
            if not self.host.peers:
                break
            await asyncio.sleep(0.005)

    def options(self, **changes):
        return {'ca_pem': self.pem, 'server_name': 'localhost', **changes}

    async def connect(self, team, options=None):
        client = await asyncio.to_thread(Connection, '127.0.0.1', self.port,
                                        self.session.tokens[team], options or self.options())
        self.clients.append(client)
        return client

    async def until(self, predicate):
        for _ in range(600):
            for client in self.clients:
                client.poll()
            if predicate():
                return
            await asyncio.sleep(0.005)
        self.fail('TLS clients did not converge')

    async def test_verified_tls_move_and_same_seat_rejoin(self):
        blue = await self.connect('player')
        green = await self.connect('other')
        self.assertIn(blue.security, ('TLSv1.2', 'TLSv1.3'))
        context = client_context(self.options())
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        await self.until(lambda: blue.model.can_act)
        blue.send(blue.model.command('move', unit='Blue_Captain', pos=[7, 3]))
        await self.until(lambda: blue.model.packet['revision'] == green.model.packet['revision'] == 1)
        expected = deepcopy(blue.model.packet)
        self.assertEqual(expected, green.model.packet)
        await asyncio.to_thread(green.close)
        self.clients.remove(green)
        await self.until(lambda: blue.model.peers == ['player'])
        rejoined = await self.connect('other')
        self.assertEqual(rejoined.model.team, 'other')
        self.assertEqual(rejoined.model.packet, expected)

    async def test_wrong_hostname_rejected_before_army_credential(self):
        with patch.object(Connection, 'send') as hello:
            with self.assertRaises(ssl.SSLCertVerificationError):
                await self.connect('player', self.options(server_name='wrong.example'))
            hello.assert_not_called()
        self.assertFalse(self.host.peers)
        self.assertEqual(self.session.revision, 0)

    async def test_untrusted_identity_rejected_before_army_credential(self):
        other, _ = create_identity(Path(self.folder.name) / 'other')
        with patch.object(Connection, 'send') as hello:
            with self.assertRaises(ssl.SSLCertVerificationError):
                await self.connect('player', self.options(ca_pem=other.read_text()))
            hello.assert_not_called()
        self.assertFalse(self.host.peers)

    async def test_plaintext_client_cannot_authenticate_to_tls_listener(self):
        # Send no actual capability; the TLS endpoint must reject raw JSON.
        reader, writer = await asyncio.open_connection('127.0.0.1', self.port)
        writer.write(b'{"v":1,"type":"hello","token":"not_a_real_token"}\n')
        await writer.drain()
        try:
            self.assertEqual(await asyncio.wait_for(reader.read(1), 3), b'')
        except ConnectionResetError:
            pass
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass
        self.assertFalse(self.host.peers)


class TLSProcessTests(unittest.TestCase):
    def test_host_and_two_tls_rendering_clients(self):
        from utilities.smoke_network import run_smoke
        with tempfile.TemporaryDirectory(prefix='lt-tls-process-') as folder:
            result = run_smoke(folder, tls=True)
            self.assertTrue(result['tls'])
            self.assertEqual(result['revision'], 9)
            self.assertEqual(result['snapshots_compared'], 10)
