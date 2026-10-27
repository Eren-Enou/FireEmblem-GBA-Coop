"""TLS configuration and private, out-of-band join invitations.

Application commands remain protocol v1. Plaintext is restricted to loopback;
remote clients verify their invitation's trust anchor AND expected server name.
"""
import ipaddress
import socket
import ssl

from app.coop.protocol import fields, require, string


def is_loopback(host):
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host == 'localhost'


def server_context(certificate, private_key):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certificate, private_key)
    return context


def client_context(options):
    fields(options, ('ca_pem', 'server_name'))
    string(options['ca_pem'], 16384)
    string(options['server_name'], 253)
    context = ssl.create_default_context(cadata=options['ca_pem'])
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    # Keep the standard chain, expiry, purpose and hostname checks enabled.
    require(context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED)
    return context


def connect(host, port, tls=None):
    string(host, 253)
    require(tls is not None or is_loopback(host), 'tls_required_for_remote')
    context = client_context(tls) if tls is not None else None
    raw = socket.create_connection((host, port), timeout=10)
    try:
        # Check the actual peer too, so a changed localhost lookup cannot expose
        # a plaintext army credential to a non-loopback destination.
        require(context is not None or is_loopback(raw.getpeername()[0]), 'tls_required_for_remote')
        return context.wrap_socket(raw, server_hostname=tls['server_name']) if context else raw
    except Exception:
        raw.close()
        raise


def validate_listener(bind, context):
    # Explicit literal bind addresses avoid ambiguous hostname resolution.
    address = ipaddress.ip_address(bind)
    require(address.is_loopback or isinstance(context, ssl.SSLContext), 'tls_required_for_remote')


def validate_invitation(value):
    expected = ('host', 'port', 'token', 'tls') if type(value) is dict and 'tls' in value else ('host', 'port', 'token')
    fields(value, expected)
    from app.coop.protocol import integer
    string(value['host'], 253)
    integer(value['port'], 1, 65535)
    string(value['token'], 256)
    require('tls' in value or is_loopback(value['host']), 'tls_required_for_remote')
    if 'tls' in value:
        client_context(value['tls'])
    return value
