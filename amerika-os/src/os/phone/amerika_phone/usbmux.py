"""Minimal usbmuxd client (plist protocol): list devices and open a TCP tunnel to a port on a connected iPhone."""
import plistlib
import socket
import struct

SOCKET = '/var/run/usbmuxd'


class MuxError(Exception):
    pass


def _send(sock, payload, tag):
    data = plistlib.dumps(payload)
    sock.sendall(struct.pack('<IIII', 16 + len(data), 1, 8, tag) + data)


def _recv(sock):
    head = _read(sock, 16)
    length = struct.unpack('<I', head[:4])[0]
    if length < 16 or length > 1 << 20:
        raise MuxError('bad usbmuxd packet')
    return plistlib.loads(_read(sock, length - 16))


def _read(sock, n):
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise MuxError('usbmuxd closed the connection')
        buf += chunk
    return buf


def _open(path):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(5)
    try:
        s.connect(path)
    except OSError as exc:
        s.close()
        raise MuxError(f'cannot reach usbmuxd: {exc}')
    return s


def list_devices(path=SOCKET):
    """USB-attached devices as [{'id': int, 'serial': str}]."""
    s = _open(path)
    try:
        _send(s, {'MessageType': 'ListDevices', 'ClientVersionString': 'amerika-phone', 'ProgName': 'amerika-phone'}, 1)
        reply = _recv(s)
    finally:
        s.close()
    out = []
    for dev in reply.get('DeviceList', []):
        props = dev.get('Properties', {})
        if props.get('ConnectionType', 'USB') == 'USB':
            out.append({'id': int(dev['DeviceID']), 'serial': str(props.get('SerialNumber', ''))})
    return out


def connect(device_id, port, path=SOCKET, timeout=5):
    """Socket tunnelled to `port` on the device (raises MuxError if nothing is listening)."""
    s = _open(path)
    try:
        _send(s, {'MessageType': 'Connect', 'ClientVersionString': 'amerika-phone', 'ProgName': 'amerika-phone',
                  'DeviceID': device_id, 'PortNumber': socket.htons(port)}, 2)
        reply = _recv(s)
        if reply.get('Number') != 0:
            raise MuxError(f"phone refused the connection (code {reply.get('Number')}); is the Amerika Key app open?")
        s.settimeout(timeout)
        return s
    except Exception:
        s.close()
        raise
