'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs'), path = require('path');
const { J, M, C, PNG, GIF, X, Tools, newSession, px } = require('./helpers.js');

function walkDoc() { // 4x4 sprite, 4 frames, a tag "walk" 1-3 pingpong-less, "idle" 0-0; frame i has a coloured square moving right
  const d = new M.Doc({ w: 4, h: 4, mode: 'rgba' });
  for (let i = 1; i < 4; i++) d.addFrame();
  d.edit('draw', () => { for (let f = 0; f < 4; f++) { const b = d.cw(d.layers[0].id, d.frames[f].id); const x0 = f === 3 ? 1 : f; b[1 * 4 + x0] = C.pack(255 - f * 40, 10 * f, 200); b[2 * 4 + x0] = C.pack(255 - f * 40, 10 * f, 200); } });
  d.setDuration(0, 200); d.setDuration(1, 100); d.setDuration(2, 100); d.setDuration(3, 150);
  d.setTag({ name: 'idle', from: 0, to: 0 }); d.setTag({ name: 'walk', from: 1, to: 3, dir: 'forward' });
  d.name = 'Hero Knight';
  return d;
}
const OUT = process.env.SPRITE_TEST_OUT;
function save(name, data) { if (OUT) { fs.mkdirSync(OUT, { recursive: true }); fs.writeFileSync(path.join(OUT, name), data); } }

test('tagFrames orders: forward, reverse, pingpong', () => {
  const d = new M.Doc({ w: 1, h: 1 }); for (let i = 0; i < 3; i++) d.addFrame();
  const t = (dir) => X.tagFrames(d, { from: 0, to: 3, dir });
  assert.deepStrictEqual(t('forward'), [0, 1, 2, 3]); assert.deepStrictEqual(t('reverse'), [3, 2, 1, 0]); assert.deepStrictEqual(t('pingpong'), [0, 1, 2, 3, 2, 1]); assert.deepStrictEqual(t('pingpong_reverse'), [3, 2, 1, 0, 1, 2]);
});

test('spritesheet: horizontal strip, Aseprite-compatible JSON array, tags, durations', () => {
  const d = walkDoc(), s = X.buildSheet(d, { name: 'Hero Knight', layout: 'horizontal' });
  assert.strictEqual(s.width, 16); assert.strictEqual(s.height, 4);
  assert.deepStrictEqual(s.json.frames.map(f => f.frame.x), [0, 4, 8, 12]);
  assert.deepStrictEqual(s.json.frames.map(f => f.duration), [200, 100, 100, 150]);
  assert.strictEqual(s.json.frames[0].filename, 'Hero_Knight 0'); assert.strictEqual(s.json.meta.image, 'Hero_Knight.png'); assert.strictEqual(s.json.meta.format, 'RGBA8888');
  assert.deepStrictEqual(s.json.meta.frameTags, [{ name: 'idle', from: 0, to: 0, direction: 'forward' }, { name: 'walk', from: 1, to: 3, direction: 'forward' }]);
  assert.deepStrictEqual(s.json.meta.size, { w: 16, h: 4 }); assert.strictEqual(s.json.meta.scale, '1');
  assert.ok(s.json.frames.every(f => f.rotated === false && f.sourceSize.w === 4 && f.spriteSourceSize.w === 4));
  // pixels of frame 2 landed at x=8..11
  assert.deepStrictEqual(Array.from(s.rgba.subarray((1 * 16 + 8 + 2) * 4, (1 * 16 + 8 + 2) * 4 + 4)), [175, 20, 200, 255]);
  save('sheet_h.png', PNG.encode(s.width, s.height, new Uint8Array(s.rgba.buffer, s.rgba.byteOffset, s.rgba.length))); save('sheet_h.json', s.jsonText);
});

test('spritesheet: grid, vertical, packed, scale, padding, spacing, inner padding, frame selection by tag', () => {
  const d = walkDoc();
  let s = X.buildSheet(d, { layout: 'grid', columns: 2 }); assert.deepStrictEqual([s.width, s.height], [8, 8]); assert.deepStrictEqual(s.json.frames.map(f => [f.frame.x, f.frame.y]), [[0, 0], [4, 0], [0, 4], [4, 4]]);
  s = X.buildSheet(d, { layout: 'vertical' }); assert.deepStrictEqual([s.width, s.height], [4, 16]);
  s = X.buildSheet(d, { layout: 'horizontal', scale: 3, padding: 2, spacing: 1 }); assert.deepStrictEqual([s.width, s.height], [4 * 12 + 3 + 4, 12 + 4]); assert.strictEqual(s.json.frames[1].frame.x, 2 + 12 + 1);
  assert.strictEqual(s.json.meta.scale, '3'); assert.strictEqual(s.json.frames[0].sourceSize.w, 12);
  s = X.buildSheet(d, { layout: 'horizontal', innerPadding: 1 }); assert.strictEqual(s.json.frames[0].frame.w, 4); assert.strictEqual(s.json.frames[0].frame.x, 1); assert.strictEqual(s.width, 24);
  s = X.buildSheet(d, { layout: 'packed' }); const rects = s.json.frames.map(f => f.frame); rects.forEach((a, i) => rects.forEach((b, j) => { if (i < j) assert.ok(a.x + a.w <= b.x || b.x + b.w <= a.x || a.y + a.h <= b.y || b.y + b.h <= a.y, 'frames overlap'); }));
  s = X.buildSheet(d, { frames: 'tag:walk' }); assert.strictEqual(s.frames.length, 3); assert.deepStrictEqual(s.json.meta.frameTags, [{ name: 'walk', from: 0, to: 2, direction: 'forward' }]);
  assert.throws(() => X.buildSheet(d, { frames: 'tag:nope' }), /no tag/);
});

test('spritesheet: auto-trim records offsets and trimmed flag', () => {
  const d = walkDoc(), s = X.buildSheet(d, { trim: true, layout: 'horizontal' });
  const f = s.json.frames[2]; assert.strictEqual(f.trimmed, true); assert.deepStrictEqual([f.frame.w, f.frame.h], [1, 2]); assert.deepStrictEqual([f.spriteSourceSize.x, f.spriteSourceSize.y], [2, 1]); assert.deepStrictEqual(f.sourceSize, { w: 4, h: 4 });
  const empty = new M.Doc({ w: 4, h: 4 }); const e = X.buildSheet(empty, { trim: true }); assert.strictEqual(e.frames[0].w, 1);
  assert.ok(/margin = Rect2\(2, 1, 3, 2\)/.test(s.tres), 'Godot margin for trimmed frame');
});

test('Godot SpriteFrames .tres and AtlasTexture snippet', () => {
  const d = walkDoc(), s = X.buildSheet(d, { name: 'hero', godotPath: 'res://art/sprites', layout: 'horizontal' }), t = s.tres;
  assert.ok(t.startsWith('[gd_resource type="SpriteFrames" load_steps=6 format=3]'), t.split('\n')[0]);
  assert.ok(t.includes('[ext_resource type="Texture2D" path="res://art/sprites/hero.png" id="1_sheet"]'));
  assert.strictEqual((t.match(/\[sub_resource type="AtlasTexture"/g) || []).length, 4);
  assert.ok(t.includes('region = Rect2(4, 0, 4, 4)')); assert.ok(t.includes('&"idle"') && t.includes('&"walk"'));
  assert.ok(/"duration": 1\.5,/.test(t) && /"speed": 10\.0/.test(t), 'durations are relative to the fastest frame (100 ms => 10 fps)');
  assert.ok(t.includes('[resource]\nanimations = ['));
  const a = s.atlas; assert.ok(a.includes('preload("res://art/sprites/hero.png")') && a.includes('Rect2(12, 0, 4, 4)') && a.includes('func frame_texture'));
  const noTags = new M.Doc({ w: 2, h: 2 }); noTags.addFrame(); assert.ok(X.buildSheet(noTags, {}).tres.includes('&"default"'));
  d.setTag({ name: 'ping', from: 0, to: 3, dir: 'pingpong' }); const p = X.buildSheet(d, {}).tres; assert.ok(p.includes('&"ping"'));
  save('hero.tres', t); save('hero.atlas.gd', a);
});

test('PNG / GIF / APNG exports through the export tool; writes only through io.write with confined relative paths', async () => {
  const S = newSession(4, 4); const d = walkDoc(); S.setDoc(d); const written = {};
  const io = { write: async (p, data) => { written[p] = data; return { path: '/proj/' + p }; } };
  let r = await Tools.run(S, 'export', { format: 'sheet', path: 'out/hero.png', scale: 2, trim: false, godot_path: 'res://x/' }, io);
  assert.deepStrictEqual(Object.keys(written).sort(), ['out/hero.atlas.gd', 'out/hero.json', 'out/hero.png', 'out/hero.tres']);
  assert.strictEqual(PNG.decode(written['out/hero.png']).width, 32); assert.strictEqual(JSON.parse(written['out/hero.json']).meta.image, 'hero.png'); assert.ok(written['out/hero.tres'].includes('res://x/hero.png'));
  assert.strictEqual(r.ok, true); assert.strictEqual(r.files.length, 4);
  await Tools.run(S, 'export', { format: 'gif', path: 'hero.gif', scale: 4, tag: 'walk' }, io); assert.strictEqual(Buffer.from(written['hero.gif'].subarray(0, 6)).toString(), 'GIF89a');
  await Tools.run(S, 'export', { format: 'apng', path: 'hero.apng' }, io); assert.ok(Buffer.from(written['hero.apng']).includes('acTL'));
  await Tools.run(S, 'export', { format: 'png', path: 'f.png', frame: 2, scale: 8 }, io); assert.strictEqual(PNG.decode(written['f.png']).width, 32);
  await Tools.run(S, 'export', { format: 'frames', path: 'fr/hero.png' }, io); assert.ok(written['fr/hero_003.png']);
  for (const bad of ['/etc/passwd', '../x.png', 'a/../../b.png', 'C:\\x.png', '']) await assert.rejects(Tools.run(S, 'export', { format: 'png', path: bad }, io), (e) => e.code === -32003 || /required/.test(e.message));
  await assert.rejects(Tools.run(S, 'export', { format: 'png', path: 'ok.png' }, null), /not available/);
  save('hero_walk.gif', written['hero.gif']); save('hero.apng', written['hero.apng']); save('frame2.png', written['f.png']); save('hero_x2.png', written['out/hero.png']); save('hero_x2.json', written['out/hero.json']);
});
