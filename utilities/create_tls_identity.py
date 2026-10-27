"""Generate a short-lived development identity; OpenSSL CLI is setup-only."""
import argparse
import ipaddress
from pathlib import Path
import re
import shutil
import subprocess


def create_identity(folder, server_name='localhost', days=7, openssl=None):
    if type(days) is not int or not 1 <= days <= 30:
        raise ValueError('Certificate lifetime must be 1..30 days')
    if not isinstance(server_name, str) or not re.fullmatch(r'[A-Za-z0-9:.\-]{1,253}', server_name):
        raise ValueError('Use a DNS name or unbracketed IP address without spaces')
    try:
        ipaddress.ip_address(server_name)
        san = 'IP:' + server_name
    except ValueError:
        if ':' in server_name or server_name.startswith(('.', '-')):
            raise ValueError('Invalid DNS name')
        san = 'DNS:' + server_name
    executable = openssl or shutil.which('openssl')
    if not executable:
        raise RuntimeError('OpenSSL CLI is required for identity generation; supply --openssl PATH')
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    certificate, key = folder / 'server-cert.pem', folder / 'server-key.pem'
    if certificate.exists() or key.exists():
        raise FileExistsError('Identity already exists; reuse it or choose a new directory')
    try:
        subprocess.run([str(executable), 'req', '-x509', '-newkey', 'ec', '-pkeyopt',
                        'ec_paramgen_curve:P-256', '-sha256', '-nodes', '-days', str(days),
                        '-subj', '/CN=' + server_name, '-addext', 'subjectAltName=' + san,
                        '-addext', 'basicConstraints=critical,CA:TRUE',
                        '-addext', 'keyUsage=critical,digitalSignature,keyCertSign',
                        '-addext', 'extendedKeyUsage=serverAuth',
                        '-keyout', str(key), '-out', str(certificate)],
                       check=True, capture_output=True, timeout=30)
        key.chmod(0o600)
    except Exception:
        # Only these two newly created, explicitly named outputs are removed.
        certificate.unlink(missing_ok=True)
        key.unlink(missing_ok=True)
        raise
    return certificate, key


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', default='artifacts/tls')
    parser.add_argument('--server-name', default='localhost')
    parser.add_argument('--days', type=int, default=7)
    parser.add_argument('--openssl')
    args = parser.parse_args()
    cert, _ = create_identity(args.output_dir, args.server_name, args.days, args.openssl)
    print('TLS_IDENTITY_CREATED', cert.resolve(), '(private key stays on the host)')
