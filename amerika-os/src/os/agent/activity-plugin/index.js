// Amerika OS activity bridge. No prompt, argument, result or error text is read.
import net from 'node:net';
import path from 'node:path';
import os from 'node:os';

export default {
  id: 'amerika-activity',
  register(api) {
    const socket = path.join(process.env.XDG_RUNTIME_DIR || `/run/user/${os.userInfo().uid}`, 'amerika', 'agent-activity.sock');
    function publish(phase, context = {}) {
      const raw = String(context.runId || context.sessionKey || context.sessionId || 'main');
      const key = raw.replace(/[^a-zA-Z0-9:_.-]/g, '').slice(0, 128) || 'main';
      const client = net.createConnection(socket);
      client.setTimeout(500, () => client.destroy());
      client.on('error', () => client.destroy());
      client.on('connect', () => client.end(JSON.stringify({phase, key}) + '\n'));
    }
    api.on('before_agent_start', (_event, context) => publish('run-start', context));
    api.on('before_tool_call', (_event, context) => publish('tool-start', context));
    api.on('after_tool_call', (_event, context) => publish('tool-end', context));
    api.on('agent_end', (event, context) => publish(event.success === false ? 'error' : 'run-end', context));
    api.on('gateway_stop', () => publish('stopped'));
  },
};
