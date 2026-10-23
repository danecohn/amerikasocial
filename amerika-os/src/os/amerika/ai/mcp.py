"""amerika-mcp: a Model Context Protocol server (stdio) that lets an AI app operate AltStack Desktop.

The AI app starts this process. It forwards tool calls to the running Amerika Shell's broker over a private Unix
socket; the shell decides what is allowed, asks the user when needed, and writes the audit log.
"""
import json
import os
import socket
import sys

from .. import __version__, common

INSTRUCTIONS = (
    'You are connected to AltStack Desktop. These tools operate the user\'s computer: windows, apps, audio, display, '
    'network, notifications, files in the home folder and (with approval) shell commands. The user sees every action '
    'in the top bar and can stop you at any time. Prefer read tools first (system_status, windows_list, apps_list), '
    'make the smallest change that does the job, and say what you did. Risky tools ask the user for approval; if '
    'an action is declined, do not retry it without being asked.')


def ask_broker(payload, timeout=130):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(str(common.CONTROL_SOCKET))
        s.sendall((json.dumps(payload) + '\n').encode())
        data = b''
        while not data.endswith(b'\n'):
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
    return json.loads(data)


def alias(name):
    """The name advertised to MCP clients. Anthropic tool names must match ^[a-zA-Z0-9_-]{1,64}$, so dots become underscores.
    The broker's registry keeps its dotted names; they are mapped back on every call."""
    return name.replace('.', '_')


def serve(client, stdin=sys.stdin, stdout=sys.stdout, broker=ask_broker):
    def send(obj):
        stdout.write(json.dumps(obj, ensure_ascii=False) + '\n')
        stdout.flush()

    aliases = {}  # advertised name -> registry name

    def load_aliases():
        resp = broker({'id': 1, 'method': 'list', 'client': client})
        tools = resp['result'] if resp.get('ok') else []
        for t in tools:
            aliases[alias(t['name'])] = t['name']
        return tools

    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            send({'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'parse error'}})
            continue
        mid, method, params = msg.get('id'), msg.get('method'), msg.get('params') or {}
        if method is None:
            continue  # a response to something we never sent
        if mid is None:
            continue  # notifications (initialized, cancelled, ...) need no answer
        try:
            if method == 'initialize':
                send({'jsonrpc': '2.0', 'id': mid, 'result': {
                    'protocolVersion': params.get('protocolVersion', '2025-06-18'),
                    'capabilities': {'tools': {'listChanged': False}},
                    'serverInfo': {'name': 'amerika-system', 'version': __version__}, 'instructions': INSTRUCTIONS}})
            elif method == 'ping':
                send({'jsonrpc': '2.0', 'id': mid, 'result': {}})
            elif method == 'tools/list':
                try:
                    tools = load_aliases()
                except OSError:
                    tools = []
                send({'jsonrpc': '2.0', 'id': mid, 'result': {'tools': [dict(t, name=alias(t['name'])) for t in tools]}})
            elif method == 'tools/call':
                name, args = params.get('name', ''), params.get('arguments') or {}
                try:
                    if not aliases:
                        load_aliases()
                    name = aliases.get(name, name)  # advertised alias -> registry name; real dotted names still work
                    resp = broker({'id': 1, 'method': 'call', 'client': client, 'tool': name, 'args': args})
                except OSError:
                    resp = {'ok': False, 'error': 'Amerika Shell is not running. Log in to the AltStack Desktop session to use these tools.'}
                if resp.get('ok'):
                    send({'jsonrpc': '2.0', 'id': mid, 'result': {'content': [{'type': 'text', 'text': json.dumps(resp['result'], ensure_ascii=False)}]}})
                else:
                    send({'jsonrpc': '2.0', 'id': mid, 'result': {'isError': True, 'content': [{'type': 'text', 'text': str(resp.get('error'))}]}})
            else:
                send({'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32601, 'message': f'method not found: {method}'}})
        except Exception as error:  # noqa: BLE001 - never die on one bad request
            send({'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32603, 'message': str(error)}})


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    client = 'unknown'
    if '--client' in argv:
        client = argv[argv.index('--client') + 1]
    serve(client)


if __name__ == '__main__':
    main()
