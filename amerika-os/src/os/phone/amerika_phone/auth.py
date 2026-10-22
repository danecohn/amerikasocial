"""Host side: ask a connected iPhone to approve, verify the signature, or pair a new phone."""
import socket
import time

from . import protocol, store, usbmux


def _phone_sockets(mux_path, port, timeout):
    for dev in usbmux.list_devices(mux_path):
        try:
            yield usbmux.connect(dev['id'], port, mux_path, timeout=timeout)
        except usbmux.MuxError:
            continue


def request_approval(user, service, host, phones, mux_path=usbmux.SOCKET, port=protocol.PORT, timeout=30, notify=None):
    """True only if one registered phone returns a valid, fresh, Face-ID-backed signature for this exact request."""
    if not phones:
        return False
    nonce, ts = protocol.new_nonce(), protocol.now()
    request = {'v': protocol.VERSION, 'type': 'auth', 'host': host, 'user': user, 'service': service, 'ts': ts, 'nonce': nonce}
    deadline = time.monotonic() + timeout
    for sock in _phone_sockets(mux_path, port, 5):
        try:
            if notify:
                notify('Approve on your iPhone (Face ID)…')
            sock.settimeout(max(1, deadline - time.monotonic()))
            protocol.write_frame(sock, request)
            reply = protocol.read_frame(sock)
        except (OSError, ValueError, ConnectionError):
            continue
        finally:
            sock.close()
        if reply.get('type') != 'auth_result' or reply.get('approved') is not True or not isinstance(reply.get('sig'), str):
            continue
        if abs(protocol.now() - ts) > protocol.MAX_AGE:
            continue
        message = protocol.auth_message(host, user, service, ts, nonce)
        if any(protocol.verify(p['pubkey'], message, reply['sig']) for p in phones):
            return True
    return False


def pair(user, host, mux_path=usbmux.SOCKET, port=protocol.PORT, timeout=60, confirm=None):
    """Pair the first reachable phone. `confirm(code, name)` must return True after the user compares the six digits.
    Returns (name, pubkey_b64) or raises RuntimeError."""
    nonce, ts = protocol.new_nonce(), protocol.now()
    request = {'v': protocol.VERSION, 'type': 'pair', 'host': host, 'user': user, 'ts': ts, 'nonce': nonce}
    last = 'no iPhone is connected over USB'
    try:
        if usbmux.list_devices(mux_path):
            last = 'the Amerika Key app is not answering on the phone'
    except usbmux.MuxError as exc:
        last = str(exc)
    for sock in _phone_sockets(mux_path, port, 5):
        try:
            sock.settimeout(timeout)
            protocol.write_frame(sock, request)
            reply = protocol.read_frame(sock)
        except (OSError, ValueError, ConnectionError) as exc:
            last = f'the phone did not answer ({exc})'
            continue
        finally:
            sock.close()
        if reply.get('type') != 'pair_result' or not reply.get('approved'):
            last = 'pairing was declined on the phone'
            continue
        try:
            pub, sig = reply['pubkey'], reply['sig']
            ok = protocol.verify(pub, protocol.pair_message(host, user, ts, nonce, pub), sig)
        except (KeyError, ValueError, TypeError):
            ok = False
        if not ok:
            last = 'the phone returned an invalid pairing proof'
            continue
        name = str(reply.get('name') or 'iPhone')[:64]
        if confirm and not confirm(protocol.short_code(pub, nonce), name):
            raise RuntimeError('pairing cancelled: the codes did not match')
        return name, pub
    raise RuntimeError(last + '. Open the Amerika Key app on the phone and keep it unlocked.')
