/* Test page for amerika-studio-webview: implements onRpc/onOpen and a self-test run on demand. */
const log = [];
amerikaStudio.onOpen = async (f) => { log.push({opened: f.name, binary: f.binary, size: f.data.length}); window.__opened = f; };
amerikaStudio.onRpc = async (method, params) => {
  if (method === 'canvas.info') return {width: 16, height: 16, frames: 1, got: params};
  if (method === 'canvas.apply_change') throw Object.assign(new Error('nope'), {code: -32001});
  if (method === 'result') return window.__result;
  if (method === 'last_open') return window.__opened || null;
  if (method === 'slow') { await new Promise((r) => setTimeout(r, 800)); return {slow: true}; }
  if (method === 'canvas.screenshot') return {images: [{mime: 'image/png', base64: 'AAAA'}]};
  throw Object.assign(new Error('unknown ' + method), {code: -32601});
};
window.selfTest = async function (externalUrl) {
  const r = {};
  r.hasToken = JSON.stringify(Object.getOwnPropertyNames(amerikaStudio)).toLowerCase().includes('token') ||
              JSON.stringify(amerikaStudio.info).toLowerCase().includes('token');
  r.status = (await amerikaStudio.request('/v1/status')).status;
  r.badPath = await amerikaStudio.request('/v1/other', {}).then(() => 'allowed', (e) => e.message);
  r.badGet = await amerikaStudio.request('/v1/messages').then(() => 'allowed', (e) => e.message);
  const ai = new amerikaStudio.AIClient({maxTokens: 50, sleep: async () => {},
    tools: [{name: 'canvas_info', description: 'info', input_schema: {type: 'object', properties: {}}}],
    run: async (name) => ({tool: name, width: 16})});
  const out = await ai.send('hello');
  r.ai = {text: out.text, calls: out.toolCalls.map((c) => c.name), usage: out.usage, messages: ai.messages.length};
  r.write = await amerikaStudio.fs.writeProject('exports/test.png', 'AAAA', {encoding: 'base64'}).then((x) => x.path.endsWith('exports/test.png'), (e) => e.message);
  r.escape = await amerikaStudio.fs.writeProject('../evil.txt', 'x').then(() => 'written', (e) => e.message);
  r.abs = await amerikaStudio.fs.writeProject('/tmp/evil.txt', 'x').then(() => 'written', (e) => e.message);
  r.read = await amerikaStudio.fs.readFile('/etc/passwd').then(() => 'read', (e) => e.message);
  r.list = (await amerikaStudio.fs.listProject('exports')).map((e) => e.path);
  r.fetchExternal = await fetch(externalUrl).then(() => 'reached', () => 'blocked');
  r.fetchLocal = await fetch('app.js').then((x) => x.text()).then((t) => (t.length > 100 ? 'ok' : 'empty'), (e) => 'err ' + e.message);
  const img = new Image();
  r.imgExternal = await new Promise((res) => { img.onload = () => res('loaded'); img.onerror = () => res('blocked'); img.src = externalUrl + '/x.png'; });
  r.localStorage = (() => { try { localStorage.setItem('k', 'v'); return localStorage.getItem('k'); } catch (e) { return 'err'; } })();
  window.__result = r;
  await amerikaStudio.window.setTitle('DONE');
};
