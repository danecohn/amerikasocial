import json
import os
import plistlib
import shutil
import socket
import struct
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src/os/phone'))
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from amerika_phone import auth, cli, pam, protocol, store, usbmux


def x963(key):
    return protocol.b64(key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))


def sign(key, msg):
    return protocol.b64(key.sign(msg, ec.ECDSA(hashes.SHA256())))


class FakePhone:
    """A stand-in for the iPhone app: a TCP server speaking the frame protocol, with switches for misbehaviour."""

    def __init__(self, key=None, **opts):
        self.key = key or ec.generate_private_key(ec.SECP256R1())
        self.opts = opts
        self.srv = socket.socket()
        self.srv.bind(('127.0.0.1', 0))
        self.srv.listen(4)
        self.port = self.srv.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            try:
                req = protocol.read_frame(c)
                protocol.write_frame(c, self._answer(req))
            except Exception:
                pass
            finally:
                c.close()

    def _answer(self, req):
        o = self.opts
        if req['type'] == 'pair':
            pub = x963(self.key)
            sig = sign(self.key, protocol.pair_message(req['host'], req['user'], req['ts'], req['nonce'], pub))
            return {'type': 'pair_result', 'approved': not o.get('decline'), 'pubkey': pub, 'sig': sig, 'name': 'Test iPhone'}
        ts = req['ts'] - o.get('skew', 0)
        nonce = 'AAAA' if o.get('wrong_nonce') else req['nonce']
        msg = protocol.auth_message(req['host'], req['user'], req['service'] if not o.get('other_service') else 'su', ts, nonce)
        return {'type': 'auth_result', 'approved': not o.get('decline'), 'sig': sign(self.key, msg)}

    def close(self):
        try:
            self.srv.shutdown(socket.SHUT_RDWR)  # wakes the accept loop so the port really stops answering
        except OSError:
            pass
        self.srv.close()


class FakeMux:
    """usbmuxd stand-in on a unix socket: lists one device and tunnels Connect to the phone's TCP port."""

    def __init__(self, devices=1, phone_port=None):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, 'usbmuxd')
        self.devices, self.phone_port = devices, phone_port
        self.srv = socket.socket(socket.AF_UNIX)
        self.srv.bind(self.path)
        self.srv.listen(8)
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(c,), daemon=True).start()

    def _handle(self, c):
        try:
            head = usbmux._read(c, 16)
            n, _, _, tag = struct.unpack('<IIII', head)
            msg = plistlib.loads(usbmux._read(c, n - 16))
            if msg['MessageType'] == 'ListDevices':
                lst = [{'DeviceID': i + 1, 'Properties': {'ConnectionType': 'USB', 'SerialNumber': 'FAKE%d' % i}} for i in range(self.devices)]
                usbmux._send(c, {'DeviceList': lst}, tag)
                return
            port = socket.ntohs(msg['PortNumber'])
            try:
                upstream = socket.create_connection(('127.0.0.1', self.phone_port), timeout=2) if port == protocol.PORT else None
            except OSError:
                upstream = None
            if upstream is None:
                usbmux._send(c, {'MessageType': 'Result', 'Number': 3}, tag)
                return
            usbmux._send(c, {'MessageType': 'Result', 'Number': 0}, tag)
            threading.Thread(target=self._pipe, args=(upstream, c), daemon=True).start()
            self._pipe(c, upstream)
        except Exception:
            pass

    @staticmethod
    def _pipe(a, b):
        try:
            while True:
                d = a.recv(4096)
                if not d:
                    break
                b.sendall(d)
        except OSError:
            pass
        finally:
            for s in (a, b):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def close(self):
        self.srv.close()
        shutil.rmtree(self.dir, ignore_errors=True)


class PhoneAuthTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.cleanup = []

    def tearDown(self):
        for c in self.cleanup:
            c.close()

    def rig(self, **opts):
        phone = FakePhone(**opts)
        mux = FakeMux(phone_port=phone.port)
        self.cleanup += [phone, mux]
        return phone, mux

    def paired(self, phone, mux):
        name, pub = auth.pair('ant', 'host', mux_path=mux.path, confirm=lambda code, n: len(code) == 6)
        store.add('ant', name, pub, self.dir)
        return store.load('ant', self.dir)

    def approve(self, phones, mux, **kw):
        return auth.request_approval('ant', 'sudo', 'host', phones, mux_path=mux.path, timeout=5, **kw)

    def test_pair_then_approve(self):
        phone, mux = self.rig()
        phones = self.paired(phone, mux)
        self.assertEqual(phones[0]['name'], 'Test iPhone')
        self.assertTrue(self.approve(phones, mux))

    def test_other_phone_key_is_rejected(self):
        phone, mux = self.rig()
        phones = self.paired(phone, mux)
        phone.key = ec.generate_private_key(ec.SECP256R1())
        self.assertFalse(self.approve(phones, mux))

    def test_declined_on_phone(self):
        phone, mux = self.rig()
        phones = self.paired(phone, mux)
        phone.opts['decline'] = True
        self.assertFalse(self.approve(phones, mux))

    def test_replay_or_other_prompt_rejected(self):
        phone, mux = self.rig()
        phones = self.paired(phone, mux)
        for opt in ('wrong_nonce', 'other_service'):
            phone.opts = {opt: True}
            self.assertFalse(self.approve(phones, mux), opt)
        phone.opts = {'skew': 3600}
        self.assertFalse(self.approve(phones, mux))

    def test_app_not_open_or_no_phone(self):
        phone, mux = self.rig()
        phones = self.paired(phone, mux)
        phone.close()
        self.assertFalse(self.approve(phones, mux))
        none = FakeMux(devices=0)
        self.cleanup.append(none)
        self.assertEqual(usbmux.list_devices(none.path), [])
        self.assertFalse(auth.request_approval('ant', 'sudo', 'h', phones, mux_path=none.path))

    def test_pairing_requires_matching_code_and_valid_proof(self):
        phone, mux = self.rig()
        with self.assertRaises(RuntimeError):
            auth.pair('ant', 'host', mux_path=mux.path, confirm=lambda c, n: False)
        phone.opts['decline'] = True
        with self.assertRaises(RuntimeError):
            auth.pair('ant', 'host', mux_path=mux.path, confirm=lambda c, n: True)

    def test_no_phones_registered(self):
        _, mux = self.rig()
        self.assertFalse(self.approve([], mux))

    def test_signature_binds_every_field(self):
        key = ec.generate_private_key(ec.SECP256R1())
        pub, sig = x963(key), sign(key, protocol.auth_message('h', 'ant', 'sudo', 1, 'n'))
        self.assertTrue(protocol.verify(pub, protocol.auth_message('h', 'ant', 'sudo', 1, 'n'), sig))
        for args in (('x', 'ant', 'sudo', 1, 'n'), ('h', 'root', 'sudo', 1, 'n'), ('h', 'ant', 'su', 1, 'n'), ('h', 'ant', 'sudo', 2, 'n'), ('h', 'ant', 'sudo', 1, 'm')):
            self.assertFalse(protocol.verify(pub, protocol.auth_message(*args), sig), args)
        self.assertFalse(protocol.verify(pub, b'x', 'not base64!!'))

    def test_frame_limits(self):
        a, b = socket.socketpair()
        a.sendall(struct.pack('>I', protocol.MAX_FRAME + 1))
        with self.assertRaises(ValueError):
            protocol.read_frame(b)


class PamTests(unittest.TestCase):
    def run_pam(self, env, phones=(), devices=1, approve=True):
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(pam.store, 'load', return_value=list(phones)), \
                mock.patch.object(pam.usbmux, 'list_devices', return_value=[{'id': 1}] * devices), \
                mock.patch.object(pam.auth, 'request_approval', return_value=approve) as ra:
            return pam.main(), ra

    def test_only_known_services_and_users(self):
        phones = [{'name': 'p', 'pubkey': 'x'}]
        self.assertEqual(self.run_pam({'PAM_USER': 'ant', 'PAM_SERVICE': 'sudo'}, phones)[0], 0)
        for env in ({'PAM_USER': 'ant', 'PAM_SERVICE': 'sshd'}, {'PAM_USER': '../etc', 'PAM_SERVICE': 'sudo'},
                    {'PAM_USER': 'ant', 'PAM_SERVICE': 'sddm'}, {'PAM_USER': 'ant', 'PAM_SERVICE': 'sudo', 'PAM_TYPE': 'account'}):
            rc, ra = self.run_pam(env, phones)
            self.assertEqual(rc, 1, env)
            ra.assert_not_called()

    def test_falls_through_without_phone_or_registration(self):
        env = {'PAM_USER': 'ant', 'PAM_SERVICE': 'sudo'}
        self.assertEqual(self.run_pam(env, [], 1)[0], 1)
        self.assertEqual(self.run_pam(env, [{'name': 'p', 'pubkey': 'x'}], 0)[0], 1)
        self.assertEqual(self.run_pam(env, [{'name': 'p', 'pubkey': 'x'}], 1, approve=False)[0], 1)


class PamFileTests(unittest.TestCase):
    SUDO = '#%PAM-1.0\n\nsession    required   pam_limits.so\n\n@include common-auth\n@include common-account\n'

    def test_enable_disable_roundtrip_is_exact(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        path = os.path.join(d, 'sudo')
        open(path, 'w').write(self.SUDO)
        self.assertTrue(cli.pam_enable(path, 'sudo', os.path.join(d, 'bk')))
        text = open(path).read()
        self.assertIn('amerika-phone-pam', text)
        self.assertLess(text.index('amerika-phone-pam'), text.index('@include common-auth'))
        self.assertFalse(cli.pam_enable(path, 'sudo', os.path.join(d, 'bk')))
        self.assertTrue(cli.pam_disable(path))
        self.assertEqual(open(path).read(), self.SUDO)
        self.assertEqual(open(os.path.join(d, 'bk/sudo.orig')).read(), self.SUDO)

    def test_refuses_file_without_auth_stack(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        path = os.path.join(d, 'x')
        open(path, 'w').write('session required pam_limits.so\n')
        with self.assertRaises(RuntimeError):
            cli.pam_enable(path, 'x', d)
        self.assertEqual(open(path).read(), 'session required pam_limits.so\n')


if __name__ == '__main__':
    unittest.main()
