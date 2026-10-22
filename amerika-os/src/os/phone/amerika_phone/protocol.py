"""Wire format and signatures shared with the iPhone app (see docs/phone/README.md).

Frames are a 4-byte big-endian length followed by UTF-8 JSON. Signatures are ECDSA P-256 / SHA-256, DER encoded,
made by a Secure Enclave key that needs Face ID, over a canonical text message that names host, user, service,
time and the random nonce, so an approval can't be reused for another prompt.
"""
import base64
import hashlib
import json
import os
import struct
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

PORT = 38400
VERSION = 1
MAX_FRAME = 64 * 1024
MAX_AGE = 90  # seconds an approval stays valid


def b64(data):
    return base64.b64encode(data).decode()


def unb64(text):
    return base64.b64decode(text.encode(), validate=True)


def new_nonce():
    return b64(os.urandom(32))


def auth_message(host, user, service, ts, nonce):
    return '\n'.join(['AMERIKA-PHONE-AUTH-V1', host, user, service, str(int(ts)), nonce]).encode()


def pair_message(host, user, ts, nonce, pubkey_b64):
    return '\n'.join(['AMERIKA-PHONE-PAIR-V1', host, user, str(int(ts)), nonce, pubkey_b64]).encode()


def write_frame(sock, obj):
    data = json.dumps(obj, separators=(',', ':')).encode()
    sock.sendall(struct.pack('>I', len(data)) + data)


def read_frame(sock):
    head = _read(sock, 4)
    n = struct.unpack('>I', head)[0]
    if n == 0 or n > MAX_FRAME:
        raise ValueError('bad frame length')
    return json.loads(_read(sock, n).decode())


def _read(sock, n):
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError('connection closed')
        buf += chunk
    return buf


def load_public(pubkey_b64):
    return ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), unb64(pubkey_b64))


def verify(pubkey_b64, message, sig_b64):
    try:
        load_public(pubkey_b64).verify(unb64(sig_b64), message, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, ValueError):
        return False


def fingerprint(pubkey_b64):
    return hashlib.sha256(unb64(pubkey_b64)).hexdigest()[:16]


def short_code(pubkey_b64, nonce):
    """Six digits both sides show during pairing so the user can compare them."""
    digest = hashlib.sha256(unb64(pubkey_b64) + nonce.encode()).digest()
    return '%06d' % (int.from_bytes(digest[:4], 'big') % 1000000)


def now():
    return int(time.time())
