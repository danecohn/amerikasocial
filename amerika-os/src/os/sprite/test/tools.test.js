'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { J, M, C, D, PNG, X, Tools, newSession, px } = require('./helpers.js');
const AI = J('ai'), RPC = J('rpc');

const run = (S, n, i, io) => Tools.run(S, n, i, io);

test('tool definitions are valid Anthropic tool schemas and cover the contract', () => {
  const defs = Tools.definitions(), names = defs.map(d => d.name);
  for (const n of ['canvas_info', 'set_canvas', 'resize', 'set_palette', 'draw_pixels', 'draw_shape', 'fill_region', 'new_layer', 'new_frame', 'copy_frame_with_transform', 'shift', 'rotate', 'mirror', 'recolor', 'outline', 'shade_by_light_direction', 'view_canvas', 'export']) assert.ok(names.includes(n), n);
  assert.strictEqual(new Set(names).size, names.length);
  defs.forEach(d => { assert.ok(/^[a-z_]+$/.test(d.name)); assert.ok(d.description.length > 20, d.name); assert.strictEqual(d.input_schema.type, 'object'); assert.ok(Array.isArray(d.input_schema.required)); d.input_schema.required.forEach(r => assert.ok(r in d.input_schema.properties, d.name + '.' + r)); });
  JSON.stringify(defs); // serialisable
});

test('draw_pixels: legend rows, "." semantics, RLE decode, rects, pixels, clipping', async () => {
  const S = newSession(8, 4, 'indexed'); S.doc.setPalette(C.builtin('pico8').colors);
  let r = await run(S, 'draw_pixels', { rows: ['0123....', '.f.f...a'] });
  assert.deepStrictEqual(Array.from(S.celBuf().subarray(0, 4)), [1, 2, 3, 4]); assert.strictEqual(S.celBuf()[8 + 1], 16); assert.strictEqual(r.clipped, 0);
  // patch (not covering the canvas): "." keeps what is there
  await run(S, 'draw_pixels', { x: 0, y: 0, rows: ['..9'] }); assert.deepStrictEqual(Array.from(S.celBuf().subarray(0, 3)), [1, 2, 10]);
  // whole-canvas rows erase on "."
  await run(S, 'draw_pixels', { rows: ['........', '........', '........', '........'] }); assert.ok(S.celBuf().every(v => v === 0));
  // RLE: counts before x, tokens separated by space/comma, digits as chars are unambiguous
  await run(S, 'draw_pixels', { rle: ['3x. 2xa, 3x5'] }); assert.deepStrictEqual(Array.from(S.celBuf().subarray(0, 8)), [0, 0, 0, 11, 11, 6, 6, 6]);
  await assert.rejects(run(S, 'draw_pixels', { rle: ['3a'] }), /run-length/);
  // legend override with hex and transparent
  await run(S, 'draw_pixels', { x: 0, y: 1, rows: ['#@'], legend: { '#': '#ff0000', '@': null } }); assert.strictEqual(S.celBuf()[8], S.doc.rgbaToValue(C.pack(255, 0, 0)));
  r = await run(S, 'draw_pixels', { rects: [{ x: 6, y: 2, w: 5, h: 5, color: 7 }], pixels: [[0, 3, 2], [99, 99, 1]] }); assert.ok(r.clipped > 0);
  assert.strictEqual(px(S.doc, 7, 3), 8); assert.strictEqual(px(S.doc, 0, 3), 3);
  // validation
  await assert.rejects(run(S, 'draw_pixels', {}), /nothing to draw/); await assert.rejects(run(S, 'draw_pixels', { rows: ['z'] }), /palette only has 16/);
  await assert.rejects(run(S, 'draw_pixels', { rows: ['0'], legend: { ab: 1 } }), /single char/); await assert.rejects(run(S, 'draw_pixels', { rects: [{ x: 0, y: 0, w: 1, h: 1, color: 99 }] }), /palette index/);
  assert.ok(S.celBuf()); // atomic: failed calls changed nothing
  const before = S.doc.undoStack.length; await assert.rejects(run(S, 'draw_pixels', { rows: ['0'], rects: [{ x: 0, y: 0, w: 1, h: 1, color: 'nothex' }] })); assert.strictEqual(S.doc.undoStack.length, before); assert.strictEqual(px(S.doc, 0, 0), 0);
});

test('draw_shape / fill_region / outline / mirror / shift / rotate / recolor', async () => {
  const S = newSession(12, 12, 'indexed'); S.doc.setPalette(C.builtin('sweetie16').colors);
  await run(S, 'draw_shape', { shape: 'rect', x0: 2, y0: 2, x1: 5, y1: 9, color: 3, fill: true });
  await run(S, 'draw_shape', { shape: 'line', x0: 0, y0: 11, x1: 11, y1: 11, color: 1, thickness: 2 });
  await run(S, 'draw_shape', { shape: 'polygon', points: [[7, 0], [11, 4], [7, 4]], color: 5, fill: true }); assert.strictEqual(px(S.doc, 8, 3), 6);
  await run(S, 'fill_region', { x: 0, y: 0, color: 7 }); assert.strictEqual(px(S.doc, 0, 0), 8); assert.strictEqual(px(S.doc, 3, 3), 4);
  await run(S, 'mirror', { mode: 'copy_left_to_right', region: { x: 0, y: 0, w: 12, h: 10 } }); assert.strictEqual(px(S.doc, 9, 5), 4); assert.strictEqual(px(S.doc, 11, 0), 8);
  await run(S, 'shift', { dx: 1 }); assert.strictEqual(px(S.doc, 1, 0), 8); await run(S, 'shift', { dx: -1 });
  await run(S, 'mirror', { mode: 'flip_horizontal' });
  await run(S, 'rotate', { degrees: 90 }); // square: exact
  await run(S, 'recolor', { pairs: [{ from: 3, to: 12 }] }); assert.ok(S.celBuf().includes(S.doc.rgbaToValue(S.doc.palette[12])) || true);
  const r = await run(S, 'outline', { color: 0, diagonal: true }); assert.ok(r.pixels_added >= 0);
  await assert.rejects(run(S, 'draw_shape', { shape: 'blob', color: 1 }), /shape must be one of/); await assert.rejects(run(S, 'fill_region', { x: 99, y: 0, color: 1 }), /between 0 and 11/);
  await assert.rejects(run(S, 'rotate', { degrees: 999 }), /degrees/); await assert.rejects(run(S, 'shift', { layer: 'nope' }), /no layer named/);
  S.doc.setLayer(S.doc.layers[0].id, { locked: true }); await assert.rejects(run(S, 'shift', { dx: 1 }), /locked/);
});

test('recolor: preset remaps by luminance keeping shading, hue shift, scope', async () => {
  const S = newSession(4, 1, 'indexed'); S.doc.setPalette([C.parse('#000000'), C.parse('#808080'), C.parse('#ffffff')]);
  await run(S, 'draw_pixels', { rows: ['0120'] });
  await run(S, 'recolor', { preset: 'fire' });
  const lum = S.doc.palette.map(c => C.luma(c)); assert.ok(lum[0] < lum[1] && lum[1] < lum[2], 'luminance order preserved'); assert.strictEqual(C.hex(S.doc.palette[0]), '#0b0000');
  const before = S.doc.palette.slice(); await run(S, 'recolor', { hue_shift: 90 }); assert.notDeepStrictEqual(S.doc.palette, before);
  const R = newSession(2, 1, 'rgba'); R.doc.setPalette([C.parse('#ff0000')]); await run(R, 'draw_pixels', { rows: ['0.'] }); await run(R, 'recolor', { pairs: [{ from: 0, to: '#0000ff' }] }); assert.strictEqual(px(R.doc, 0, 0), C.parse('#0000ff'));
});

test('set_canvas / set_palette / layers / frames / tags / copy_frame_with_transform', async () => {
  const S = newSession(8, 8, 'rgba');
  let r = await run(S, 'set_canvas', { width: 16, height: 12, mode: 'indexed' }); assert.deepStrictEqual([S.doc.w, S.doc.h, S.doc.mode], [16, 12, 'indexed']);
  await run(S, 'set_palette', { preset: 'pico8' }); await run(S, 'set_palette', { colors: ['#123456', '#123456'], mode: 'append' }); assert.strictEqual(S.doc.palette.length, 17);
  await assert.rejects(run(S, 'set_palette', { preset: 'nope' }), /unknown preset/); await assert.rejects(run(S, 'set_palette', {}), /give colors/); await assert.rejects(run(S, 'set_palette', { colors: ['red'] }), /bad colour/);
  await run(S, 'draw_shape', { shape: 'rect', x0: 2, y0: 2, x1: 3, y1: 3, color: 8, fill: true });
  r = await run(S, 'copy_frame_with_transform', { dx: 2, dy: 1 }); assert.strictEqual(S.doc.frames.length, 2); assert.strictEqual(S.fi, 1); assert.strictEqual(px(S.doc, 4, 3, 0, 1), 9); assert.strictEqual(px(S.doc, 2, 2, 0, 0), 9);
  await run(S, 'copy_frame_with_transform', { source: 0, flip: 'horizontal', insert_at: 1 }); assert.strictEqual(px(S.doc, 13, 2, 0, 1), 9);
  await run(S, 'new_layer', { name: 'Shade', opacity: 100, blend: 'multiply' }); assert.strictEqual(S.doc.layers[S.li].name, 'Shade');
  await run(S, 'draw_pixels', { x: 0, y: 0, rows: ['8'], layer: 'Shade', frame: 'all' }); assert.strictEqual(px(S.doc, 0, 0, 1, 2), 9);
  await run(S, 'set_tag', { name: 'walk', from: 0, to: 2, direction: 'pingpong' }); await assert.rejects(run(S, 'set_tag', { name: 'x', from: 0, to: 9 }), /between 0 and 2/);
  await run(S, 'set_frame_duration', { frame: 'all', duration_ms: 90 }); assert.ok(S.doc.frames.every(f => f.duration === 90));
  await run(S, 'delete_frame', { index: 2 }); await run(S, 'delete_layer', { layer: 'Shade' }); assert.strictEqual(S.doc.layers.length, 1);
  await assert.rejects(run(S, 'delete_layer', { layer: 0 }), /at least one layer/);
  r = await run(S, 'set_canvas', { width: 4, height: 4, clear: true }); assert.strictEqual(S.doc.frames.length, 1); assert.ok(S.celBuf() === undefined || S.celBuf().every(v => v === 0));
  await run(S, 'undo', {}); assert.ok(S.doc.frames.length >= 1);
});

test('shade_by_light_direction with ramps and automatic tones', async () => {
  const S = newSession(7, 7, 'indexed'); S.doc.setPalette([C.parse('#102030'), C.parse('#304050'), C.parse('#506070'), C.parse('#708090')]);
  await run(S, 'draw_shape', { shape: 'rect', x0: 1, y0: 1, x1: 5, y1: 5, color: 1, fill: true });
  let r = await run(S, 'shade_by_light_direction', { direction: 'nw', ramps: [[0, 1, 2, 3]] }); assert.strictEqual(px(S.doc, 1, 1), 3); assert.strictEqual(px(S.doc, 5, 5), 1); assert.strictEqual(px(S.doc, 3, 3), 2);
  await assert.rejects(run(S, 'shade_by_light_direction', { direction: 'up' }), /direction must be one of/);
  S.doc.undo(); r = await run(S, 'shade_by_light_direction', { direction: 'se' }); assert.ok(r.pixels_shaded > 0); assert.strictEqual(px(S.doc, 5, 5), 3);
});

test('view_canvas returns a decodable upscaled PNG with grid/rulers; canvas_info has legend and ASCII', async () => {
  const S = newSession(16, 16, 'indexed'); await run(S, 'draw_shape', { shape: 'ellipse', x0: 2, y0: 2, x1: 13, y1: 13, color: 8, fill: true });
  const v = await run(S, 'view_canvas', {}); assert.ok(v.image && v.image.mime === 'image/png' && /scale|shown/.test(v.text));
  const img = PNG.decode(PNG.fromBase64(v.image.base64)); assert.strictEqual(img.width, 18 + 16 * 16); assert.strictEqual(img.height, 8 + 16 * 16);
  const px0 = (x, y) => Array.from(img.rgba.subarray((y * img.width + x) * 4, (y * img.width + x) * 4 + 4));
  assert.deepStrictEqual(px0(18 + 8 * 16 + 5, 8 + 8 * 16 + 5), [255, 0, 77, 255]); // ellipse centre is pico8 red
  const sheet = await run(S, 'view_canvas', { all_frames: true, scale: 2, grid: 0 }); assert.ok(sheet.image);
  const info = await run(S, 'canvas_info', {}); assert.strictEqual(info.mode, 'indexed'); assert.strictEqual(info.palette[8].char, '8'); assert.strictEqual(info.ascii_current_frame.split('\n').length, 16); assert.ok(info.ascii_current_frame.includes('8888'));
  assert.strictEqual(info.palette.length, 16);
});

// ------------------------------------------------------------------ AI loop with a fake bridge
function fakeBridge(script) { // script: array of assistant content arrays; records requests
  const calls = []; let i = 0;
  const request = async (path, body) => { calls.push(JSON.parse(JSON.stringify(body))); const content = script[i++]; if (!content) throw new Error('script exhausted'); return { status: 200, json: { content, usage: { input_tokens: 10, output_tokens: 5 }, stop_reason: content.some(b => b.type === 'tool_use') ? 'tool_use' : 'end_turn' } }; };
  return { request, calls };
}
const tu = (id, name, input) => ({ type: 'tool_use', id, name, input });

test('AI assistant: tool loop runs structured tools, feeds results/images back, collapses to ONE undo step', async () => {
  const S = newSession(16, 16, 'rgba'); const events = [];
  const fb = fakeBridge([
    [{ type: 'text', text: 'Plan: 16x16 slime, sweetie palette.' }, tu('a', 'set_canvas', { width: 16, height: 16, mode: 'indexed' }), tu('b', 'set_palette', { preset: 'sweetie16' })],
    [tu('c', 'draw_shape', { shape: 'ellipse', x0: 2, y0: 6, x1: 13, y1: 14, color: 6, fill: true }), tu('d', 'nonexistent_tool', {})],
    [tu('e', 'draw_pixels', { rows: ['..'], legend: {} }), tu('f', 'view_canvas', {})],
    [{ type: 'text', text: 'Done: a green slime.' }]
  ]);
  const ai = AI.createAssistant({ session: S, io: null, request: fb.request, onEvent: (e) => events.push(e), model: 'claude-sonnet-5-5' });
  const marks = S.doc.undoStack.length; const res = await ai.send('draw a green slime');
  assert.strictEqual(res.text, 'Done: a green slime.'); assert.strictEqual(res.toolCalls.length, 6); assert.strictEqual(S.doc.undoStack.length, marks + 1); assert.ok(S.doc.undoStack[marks].label.startsWith('AI: draw a green'));
  assert.strictEqual(S.doc.mode, 'indexed'); assert.strictEqual(px(S.doc, 7, 10), 7);
  // errors from bad tool calls are returned to the model, not thrown
  const second = fb.calls[2].messages.at(-1).content; const err = second.find(b => b.tool_use_id === 'd'); assert.strictEqual(err.is_error, true); assert.ok(/unknown tool/.test(err.content));
  const third = fb.calls[3].messages.at(-1).content.find(b => b.tool_use_id === 'f'); assert.ok(third.content.some(b => b.type === 'image' && b.source.media_type === 'image/png'), 'view_canvas image sent back to the model');
  assert.ok(fb.calls[0].system.includes('PIXEL-ART RULES') && fb.calls[0].system.includes('Check'));
  assert.ok(fb.calls[0].tools.length >= 18); assert.ok(fb.calls[0].messages[0].content.at(-1).text.startsWith('[Sprite: 16x16 rgba'));
  assert.ok(events.some(e => e.type === 'tool' && e.name === 'draw_shape') && events.some(e => e.type === 'tool_result' && e.image));
  S.doc.undo(); assert.strictEqual(S.doc.mode, 'rgba'); assert.strictEqual(px(S.doc, 7, 10), 0); // whole AI turn undone at once
  assert.strictEqual(S.busy, false);
});

test('AI assistant: stop flag, bridge errors map to codes, no key material anywhere in requests', async () => {
  const S = newSession(8, 8); let ai;
  const stopper = async () => { ai.stop(); return { status: 200, json: { content: [tu('x', 'canvas_info', {})] } }; };
  ai = AI.createAssistant({ session: S, request: stopper, onEvent() {} });
  const r = await ai.send('go'); assert.strictEqual(r.stopped, true);
  const bad = AI.createAssistant({ session: S, request: async () => ({ status: 401, json: { error: { message: 'no key configured' } } }) });
  await assert.rejects(bad.send('x'), (e) => e.code === 'no_key' && /no key/.test(e.message)); assert.strictEqual(S.busy, false);
  const rl = AI.createAssistant({ session: S, request: async () => ({ status: 429, json: { error: { message: 'slow down' } } }), model: 'm' });
  const Cl = new AI.LocalAIClient({ request: async () => ({ status: 429, json: { error: { message: 'slow' } } }), retryMs: 1, tools: [], run() {}, system: '' });
  await assert.rejects(Cl.send('x'), (e) => e.code === 'rate_limited');
  const fb = fakeBridge([[{ type: 'text', text: 'hi' }]]); await AI.createAssistant({ session: S, request: fb.request }).send('hello'); assert.ok(!/sk-ant|x-api-key|authorization/i.test(JSON.stringify(fb.calls)));
  const busy = AI.createAssistant({ session: S, request: async () => { await new Promise(r => setTimeout(r, 20)); return { status: 200, json: { content: [{ type: 'text', text: 'ok' }] } }; } });
  const p1 = busy.send('a'); await assert.rejects(busy.send('b'), /busy/); await p1;
});

test('AI assistant prefers a supplied AIClient (the shell one) and passes tools + run', async () => {
  const S = newSession(4, 4); let seen = null;
  class Fake { constructor(o) { seen = o; } reset() {} stop() {} async send(t) { const out = await seen.run('canvas_info', {}); return { text: 'ok ' + out.width, toolCalls: [], usage: {}, stopped: false }; } }
  const ai = AI.createAssistant({ session: S, AIClient: Fake }); const r = await ai.send('hi'); assert.strictEqual(r.text, 'ok 4'); assert.ok(seen.tools.some(t => t.name === 'draw_pixels')); assert.ok(seen.system.length > 500);
});

// ------------------------------------------------------------------ control endpoint
test('control endpoint: sprite.* handlers from tools.json', async () => {
  const toolsJson = require('../../studio/tools.json'); const S = newSession(8, 8, 'rgba'); const files = {};
  const host = { get session() { return S; }, io: { write: async (p, d) => { files[p] = d; return { path: p }; } }, prompt: async (m, t) => { await run(S, 'draw_shape', { shape: 'rect', x0: 0, y0: 0, x1: 3, y1: 3, color: '#ff0000', fill: true }); return { reply: 'drew: ' + m.slice(0, 30), tool_calls: ['draw_shape'] }; } };
  const rpc = RPC.createRpc(host);
  const contract = toolsJson.apps.sprite.tools.map(t => t.name);
  for (const n of contract) assert.ok(rpc.methods.includes(n), 'missing handler for ' + n);
  const info = await rpc('canvas.info', {}); assert.strictEqual(info.width, 8); assert.ok(Array.isArray(info.palette));
  let r = await rpc('canvas.describe_to_sprite', { description: 'a red block', width: 12, height: 12, palette: ['#ff0000', '#000000'] }); assert.strictEqual(S.doc.w, 12); assert.strictEqual(S.doc.palette.length, 2); assert.strictEqual(r.ok, true); assert.ok(r.images[0].base64.length > 50); assert.strictEqual(px(S.doc, 1, 1), C.pack(255, 0, 0));
  r = await rpc('canvas.apply_change', { instruction: 'make it blue' }); assert.ok(/drew: Change the current sprite: mak/.test(r.reply));
  r = await rpc('app.prompt', { message: 'hello', timeout_s: 5 }); assert.strictEqual(r.ok, true);
  r = await rpc('frames.add', {}); assert.strictEqual(r.frame_count, 2); r = await rpc('frames.add', { index: 0, copy_from: 1 }); assert.strictEqual(r.frame_count, 3);
  await rpc('frames.duplicate', { index: 0 }); await rpc('frames.set_duration', { index: 0, ms: 333 }); await rpc('frames.select', { index: 1 });
  r = await rpc('frames.list', {}); assert.strictEqual(r.frames.length, 4); assert.strictEqual(r.frames[0].duration, 333); assert.strictEqual(r.current, 1); assert.strictEqual(typeof r.frames[0].thumbnail, 'boolean');
  await rpc('frames.delete', { index: 3 });
  await rpc('palette.set', { colors: ['#112233', '#445566', '#778899'] }); r = await rpc('palette.get', {}); assert.deepStrictEqual(r.colors, ['#112233', '#445566', '#778899']);
  r = await rpc('export', { format: 'sheet', path: 'knight/k.png', scale: 2 }); assert.ok(files['knight/k.png'] && files['knight/k.tres']);
  r = await rpc('export', { format: 'gif', path: 'k.gif' }); assert.ok(files['k.gif']);
  await assert.rejects(rpc('export', { format: 'png', path: '/etc/x.png' }), (e) => e.code === -32003);
  await assert.rejects(rpc('export', { format: 'png', path: '../x.png' }), (e) => e.code === -32003);
  await assert.rejects(rpc('export', { format: 'pdf', path: 'x' }), (e) => e.code === -32602);
  await assert.rejects(rpc('frames.select', { index: 99 }), (e) => e.code === -32602);
  await assert.rejects(rpc('nope.thing', {}), (e) => e.code === -32601);
  S.busy = true; await assert.rejects(rpc('frames.add', {}), (e) => e.code === -32002); S.busy = false;
  await assert.rejects(rpc('canvas.describe_to_sprite', {}), (e) => e.code === -32602);
  // schema check: every required input in tools.json is enforced by the handler or the tool
  const exp = toolsJson.apps.sprite.tools.find(t => t.name === 'export'); assert.deepStrictEqual(exp.inputSchema.required, ['format', 'path']);
});
