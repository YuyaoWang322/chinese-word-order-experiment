"""Verified TLS using explicit configuration, Python defaults, then macOS CA."""
import os
from pathlib import Path
import ssl
import sys


def verified_context():
    if os.environ.get('SSL_CERT_FILE') or os.environ.get('SSL_CERT_DIR'):
        return ssl.create_default_context()
    paths = ssl.get_default_verify_paths()
    if paths.cafile or paths.capath:
        return ssl.create_default_context()
    system_ca = Path('/etc/ssl/cert.pem')
    if sys.platform == 'darwin' and system_ca.is_file():
        return ssl.create_default_context(cafile=str(system_ca))
    return ssl.create_default_context()
