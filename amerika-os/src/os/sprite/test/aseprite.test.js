'use strict';
// The fixtures are crafted from the public .aseprite file format specification (docs/ase-file-specs.md); nothing from Aseprite itself is used.
const test = require('node:test');
const assert = require('node:assert');
const zlib = require('zlib');
const { J, M, C } = require('./helpers.js');
const ASE = J('aseprite');

const u8 = (v) => Buffer.from([v & 255]);
const u16 = (v) => { const b = Buffer.alloc(2); b.writeUInt16LE(v & 0xFFFF); return b; };
const s16 = (v) => { const b = Buffer.alloc(2); b.writeInt16LE(v); return b; };
const u32 = (v) => { const b = Buffer.alloc(4); b.writeUInt32LE(v >>> 0); return b; };
const str = (s) => Buffer.concat([u16(Buffer.byteLength(s)), Buffer.from(s)]);
const pad = (n) => Buffer.alloc(n);
const chunk = (type, data) => Buffer.concat([u32(6 + data.length), u16(type), data]);
const layer = (name, o = {}) => chunk(0x2004, Buffer.concat([u16(o.flags === undefined ? 3 : o.flags), u16(o.type || 0), u16(o.level || 0), u16(0), u16(0), u16(o.blend || 0), u8(o.opacity === undefined ? 255 : o.opacity), pad(3), str(name)]));
const celHead = (li, x, y, op, type) => Buffer.concat([u16(li), s16(x), s16(y), u8(op), u16(type), s16(0), pad(5)]);
const celRaw = (li, x, y, w, h, bytes, op = 255) => chunk(0x2005, Buffer.concat([celHead(li, x, y, op, 0), u16(w), u16(h), Buffer.from(bytes)]));
const celZ = (li, x, y, w, h, bytes, op = 255) => chunk(0x2005, Buffer.concat([celHead(li, x, y, op, 2), u16(w), u16(h), zlib.deflateSync(Buffer.from(bytes))]));
const celLink = (li, frame) => chunk(0x2005, Buffer.concat([celHead(li, 0, 0, 255, 1), u16(frame)]));
const tags = (list) => chunk(0x2018, Buffer.concat([u16(list.length), pad(8), ...list.map(t => Buffer.concat([u16(t.from), u16(t.to), u8(t.dir), u16(t.repeat || 0), pad(6), Buffer.from(t.rgb || [1, 2, 3]), pad(1), str(t.name)]))]));
const palette = (cols) => chunk(0x2019, Buffer.concat([u32(cols.length), u32(0), u32(cols.length - 1), pad(8), ...cols.map(c => Buffer.concat([u16(0), Buffer.from(c)]))]));
function file(w, h, depth, frames, transparent = 0) {
  const fbufs = frames.map(f => { const body = Buffer.concat(f.chunks); return Buffer.concat([u32(16 + body.length), u16(0xF1FA), u16(f.chunks.length), u16(f.dur), pad(2), u32(f.chunks.length), body]); });
  const head = Buffer.concat([u32(0), u16(0xA5E0), u16(frames.length), u16(w), u16(h), u16(depth), u32(1), u16(100), u32(0), u32(0), u8(transparent), pad(3), u16(0), u8(1), u8(1), s16(0), s16(0), u16(16), u16(16)]);
  const header = Buffer.concat([head, pad(128 - head.length)]);
  const all = Buffer.concat([header, ...fbufs]); all.writeUInt32LE(all.length, 0); return new Uint8Array(all);
}
const RED = [255, 0, 0, 255], GREEN = [0, 255, 0, 255], CLEAR = [0, 0, 0, 0];

test('aseprite: RGBA file with layers, blend, opacity, groups, compressed/raw/linked cels, tags and palette', () => {
  const body2x2 = Buffer.from([...RED, ...RED, ...RED, ...GREEN]);
  const f = file(4, 3, 32, [
    { dur: 120, chunks: [layer('Body'), layer('Glow', { blend: 1, opacity: 128 }), layer('Group', { type: 1, flags: 3 }), layer('Hidden child', { level: 1, flags: 2 }),
      palette([[10, 20, 30, 255], [40, 50, 60, 255], [70, 80, 90, 128]]), tags([{ name: 'idle', from: 0, to: 1, dir: 0 }, { name: 'walk', from: 1, to: 2, dir: 2, repeat: 3 }]),
      celZ(0, 1, 1, 2, 2, body2x2), celRaw(1, 0, 0, 1, 1, GREEN), celRaw(3, 0, 0, 1, 1, RED)] },
    { dur: 80, chunks: [celLink(0, 0)] },
    { dur: 0, chunks: [celZ(0, -1, 0, 2, 1, Buffer.from([...GREEN, ...RED]))] }
  ]);
  const { doc, info, warnings } = ASE.read(f);
  assert.deepStrictEqual([doc.w, doc.h, doc.mode, doc.frames.length, doc.layers.length], [4, 3, 'rgba', 3, 3]);
  assert.deepStrictEqual(doc.frames.map(x => x.duration), [120, 80, 100]); // 0 falls back to header speed
  assert.deepStrictEqual(doc.layers.map(l => [l.name, l.blend, l.opacity, l.visible]), [['Body', 'normal', 255, true], ['Glow', 'multiply', 128, true], ['Hidden child', 'normal', 255, false]]);
  const at = (l, fr, x, y) => C.unpack(doc.celAt(l, fr)[y * 4 + x]);
  assert.deepStrictEqual(at(0, 0, 1, 1), RED); assert.deepStrictEqual(at(0, 0, 2, 2), GREEN); assert.strictEqual(doc.celAt(0, 0)[0], 0);
  assert.deepStrictEqual(at(0, 1, 2, 2), GREEN, 'linked cel copies frame 0');
  assert.deepStrictEqual(at(0, 2, 0, 0), RED, 'negative cel x offset is clipped');
  assert.deepStrictEqual(at(1, 0, 0, 0), GREEN);
  assert.deepStrictEqual(doc.tags.map(t => [t.name, t.from, t.to, t.dir, t.repeat]), [['idle', 0, 1, 'forward', 0], ['walk', 1, 2, 'pingpong', 3]]);
  assert.deepStrictEqual(doc.palette.map(c => C.hex(c)), ['#0a141e', '#28323c', '#46505a80']);
  assert.strictEqual(info.depth, 32); assert.deepStrictEqual(warnings, []);
});

test('aseprite: indexed file keeps the palette; transparent index only applies to non-background layers', () => {
  const pal = palette([[0, 0, 0, 255], [255, 0, 0, 255], [0, 255, 0, 255], [0, 0, 255, 255]]);
  const f = file(2, 2, 8, [{ dur: 100, chunks: [layer('bg', { flags: 3 | 8 }), layer('fg'), pal, celRaw(0, 0, 0, 2, 2, [0, 1, 2, 3]), celRaw(1, 0, 0, 2, 2, [0, 1, 2, 3])] }], 0);
  const { doc } = ASE.read(f);
  assert.strictEqual(doc.mode, 'indexed'); assert.strictEqual(doc.palette.length, 4);
  assert.deepStrictEqual(Array.from(doc.celAt(0, 0)), [1, 2, 3, 4]); // background layer: index 0 is a real colour
  assert.deepStrictEqual(Array.from(doc.celAt(1, 0)), [0, 2, 3, 4]); // normal layer: index 0 transparent
  assert.deepStrictEqual(Array.from(doc.composite(0)).slice(0, 8), [0, 0, 0, 255, 255, 0, 0, 255]);
});

test('aseprite: grayscale and old palette chunk', () => {
  const old = chunk(0x0004, Buffer.concat([u16(1), u8(0), u8(2), Buffer.from([1, 2, 3, 4, 5, 6])]));
  const f = file(2, 1, 16, [{ dur: 50, chunks: [layer('g'), old, celRaw(0, 0, 0, 2, 1, [100, 255, 50, 0])] }]);
  const { doc } = ASE.read(f);
  assert.deepStrictEqual(C.unpack(doc.celAt(0, 0)[0]), [100, 100, 100, 255]); assert.strictEqual(doc.celAt(0, 0)[1], 0);
  assert.deepStrictEqual(doc.palette.slice(0, 2).map(c => C.hex(c)), ['#010203', '#040506']);
});

test('aseprite: tilemap layers and unsupported blend modes produce warnings, bad files throw', () => {
  const f = file(2, 2, 32, [{ dur: 100, chunks: [chunk(0x2004, Buffer.concat([u16(3), u16(2), u16(0), u16(0), u16(0), u16(0), u8(255), pad(3), str('tiles'), u32(0)])), layer('hsl', { blend: 14 }), celRaw(1, 0, 0, 1, 1, RED)] }]);
  const r = ASE.read(f); assert.ok(r.warnings.some(w => /tilemap/.test(w))); assert.ok(r.warnings.some(w => /blend mode 14/.test(w))); assert.strictEqual(r.doc.layers.length, 1);
  assert.throws(() => ASE.read(new Uint8Array(200)), /bad magic/);
  assert.throws(() => ASE.read(new Uint8Array(10)), /too small/);
  const good = file(1, 1, 32, [{ dur: 1, chunks: [layer('a'), celRaw(0, 0, 0, 1, 1, RED)] }]);
  assert.throws(() => ASE.read(good.subarray(0, good.length - 6)), /truncated|short|RangeError|Offset/i);
});
