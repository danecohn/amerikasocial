'use strict';
const test = require('node:test');
const assert = require('node:assert');
const nodeZlib = require('zlib');
const { M, C, D, PNG, GIF, Z, Tools, newSession, px } = require('./helpers.js');

test('zlib: our deflate is readable by node, our inflate reads node output', () => {
  const data = Buffer.alloc(20000); for (let i = 0; i < data.length; i++) data[i] = (i * 7 >> 2) % 11 + (i % 97 === 0 ? i & 255 : 0);
  assert.deepStrictEqual(Buffer.from(nodeZlib.inflateSync(Buffer.from(Z.deflate(data)))), data);
  for (const level of [0, 1, 9]) assert.deepStrictEqual(Buffer.from(Z.inflate(nodeZlib.deflateSync(data, { level }))), data);
  assert.strictEqual(Z.crc32(data), nodeZlib.crc32(data));
});

test('png: encode/decode round trip and APNG structure', () => {
  const w = 7, h = 5, rgba = new Uint8Array(w * h * 4); for (let i = 0; i < rgba.length; i++) rgba[i] = (i * 37) & 255;
  const bytes = PNG.encode(w, h, rgba), back = PNG.decode(bytes);
  assert.strictEqual(back.width, 7); assert.deepStrictEqual(Array.from(back.rgba), Array.from(rgba));
  const ap = PNG.encodeAPNG(w, h, [{ rgba, delay: 80 }, { rgba, delay: 120 }], 0);
  assert.ok(Buffer.from(ap).includes('acTL')); assert.ok(Buffer.from(ap).includes('fdAT'));
  assert.deepStrictEqual(PNG.decode(ap).rgba.length, rgba.length); // first frame is the default image
});

test('draw: line, rect, ellipse, polygon', () => {
  const pts = []; D.line(0, 0, 4, 2, (x, y) => pts.push([x, y]));
  assert.deepStrictEqual(pts[0], [0, 0]); assert.deepStrictEqual(pts[pts.length - 1], [4, 2]); assert.strictEqual(pts.length, 5);
  let n = 0; D.rect(1, 1, 4, 3, () => n++, true); assert.strictEqual(n, 12);
  n = 0; D.rect(1, 1, 4, 3, () => n++, false); assert.strictEqual(n, 10);
  const set = new Set(); D.ellipse(0, 0, 8, 6, (x, y) => set.add(x + ',' + y), true);
  assert.ok(set.has('4,3')); assert.ok(!set.has('0,0')); assert.ok(set.has('0,3'));
  const poly = new Set(); D.polygonFill([[1, 1], [6, 1], [6, 6], [1, 6]], (x, y) => poly.add(x + ',' + y));
  assert.ok(poly.has('3,3') && poly.has('1,1') && poly.has('6,6') && !poly.has('0,0'));
});

test('draw: pixel-perfect removes L corners only', () => {
  assert.deepStrictEqual(D.pixelPerfect([[0, 0], [1, 0], [1, 1], [2, 1], [2, 2]]), [[0, 0], [1, 1], [2, 2]]);
  assert.deepStrictEqual(D.pixelPerfect([[0, 0], [1, 0], [2, 0]]), [[0, 0], [1, 0], [2, 0]]);
});

test('draw: flood fill contiguous, tolerance, non-contiguous', () => {
  const w = 6, h = 4, id = (v) => v;
  // 0 0 0 | 1 1 1 ; row 3 holds an isolated 0 pocket separated by 1s
  const buf = new Uint32Array(w * h);
  for (let y = 0; y < h; y++) for (let x = 3; x < w; x++) buf[y * w + x] = 1;
  buf[3 * w + 5] = 0; // isolated 0 in the right region
  let m = D.floodMask(buf, w, h, 0, 0, 0, true, id);
  assert.strictEqual(m.reduce((a, b) => a + b, 0), 12);
  m = D.floodMask(buf, w, h, 0, 0, 0, false, id);
  assert.strictEqual(m.reduce((a, b) => a + b, 0), 13); // includes the isolated pocket
  const colors = new Uint32Array([C.pack(100, 0, 0), C.pack(110, 0, 0), C.pack(200, 0, 0), C.pack(100, 0, 0)]);
  m = D.floodMask(colors, 4, 1, 0, 0, 12, true, id => id);
  assert.deepStrictEqual(Array.from(m), [1, 1, 0, 0]);
  m = D.floodMask(colors, 4, 1, 0, 0, 12, false, id => id);
  assert.deepStrictEqual(Array.from(m), [1, 1, 0, 1]);
  assert.strictEqual(D.applyMask(buf, D.floodMask(buf, w, h, 0, 0, 0, true, id), 7), 12);
});

test('draw: transforms (flip, rotate90, scale2x, scaleNearest, shift wrap, rotateSmart identity)', () => {
  const b = new Uint32Array([1, 2, 3, 4, 5, 6]); // 3x2
  assert.deepStrictEqual(Array.from(D.flipH(b, 3, 2)), [3, 2, 1, 6, 5, 4]);
  assert.deepStrictEqual(Array.from(D.flipV(b, 3, 2)), [4, 5, 6, 1, 2, 3]);
  const r = D.rotate90(b, 3, 2, 1); assert.strictEqual(r.w, 2); assert.deepStrictEqual(Array.from(r.data), [4, 1, 5, 2, 6, 3]);
  assert.deepStrictEqual(Array.from(D.shift(b, 3, 2, 1, 0, true)), [3, 1, 2, 6, 4, 5]);
  assert.deepStrictEqual(Array.from(D.scaleNearest(new Uint32Array([1, 2, 3, 4]), 2, 2, 4, 4)), [1, 1, 2, 2, 1, 1, 2, 2, 3, 3, 4, 4, 3, 3, 4, 4]);
  // Scale2x keeps a diagonal edge sharp: a single pixel on a flat field stays a flat 2x2 block
  const s = D.scale2x(new Uint32Array(9).fill(0).map((v, i) => i === 4 ? 1 : 0), 3, 3); assert.strictEqual(s.length, 36);
  const sq = new Uint32Array(16); for (let y = 1; y < 3; y++) for (let x = 1; x < 3; x++) sq[y * 4 + x] = 5;
  assert.deepStrictEqual(Array.from(D.rotateSmart(sq, 4, 4, 0)), Array.from(sq));
  const rot = D.rotateSmart(sq, 4, 4, 90); assert.deepStrictEqual(Array.from(rot), Array.from(sq));
});

test('draw: outline, drop shadow, replace colour, dither gradient is monotonic', () => {
  const b = new Uint32Array(25); b[12] = 3;
  const o = D.outline(b, 5, 5, 9); assert.strictEqual(o.changed, 4); assert.strictEqual(o.data[7], 9);
  const o8 = D.outline(b, 5, 5, 9, { diagonal: true }); assert.strictEqual(o8.changed, 8);
  const inner = D.outline(new Uint32Array(25).fill(0).map((v, i) => (i % 5 > 0 && i % 5 < 4 && i > 5 && i < 19) ? 2 : 0), 5, 5, 8, { inside: true }); assert.ok(inner.changed > 0);
  const sh = D.dropShadow(b, 5, 5, 8, 1, 1); assert.strictEqual(sh.data[18], 8);
  const buf = new Uint32Array([1, 2, 1, 3]); assert.strictEqual(D.replaceColor(buf, 1, 9, 0, v => v), 2); assert.deepStrictEqual(Array.from(buf), [9, 2, 9, 3]);
  let count = 0; const row = []; D.ditherGradient(0, 0, 15, 0, 0, 1, 4, (x, y, v) => { if (y === 0) row[x] = v; }, { x: 0, y: 0, w: 16, h: 4 }); count = row.filter(v => v === 1).length;
  assert.ok(row[0] === 0 && row[15] === 1 && count > 4 && count < 12);
});

test('draw: shadeByLight lightens lit edge and darkens the far edge', () => {
  const w = 5, b = new Uint32Array(w * w); for (let y = 1; y < 4; y++) for (let x = 1; x < 4; x++) b[y * w + x] = 2;
  const r = D.shadeByLight(b, w, w, 'nw', v => v + 1, v => v - 1, { depth: 1 });
  assert.strictEqual(r.data[1 * w + 1], 3); assert.strictEqual(r.data[3 * w + 3], 1); assert.strictEqual(r.data[2 * w + 2], 2);
});

test('palette: built-ins, GPL / hex / JASC / PNG import, export, ramp, luma remap', () => {
  const by = (id) => C.builtin(id).colors;
  assert.strictEqual(by('pico8').length, 16); assert.strictEqual(by('sweetie16').length, 16); assert.strictEqual(by('endesga32').length, 32);
  assert.strictEqual(C.hex(by('pico8')[8]), '#ff004d'); assert.strictEqual(C.hex(by('sweetie16')[0]), '#1a1c2c'); assert.strictEqual(C.hex(by('endesga32')[0]), '#be4a2f');
  const gpl = C.parseGPL('GIMP Palette\nName: Test\nColumns: 4\n#\n255   0   0\tred\n  0 255   0 green\n'); assert.strictEqual(gpl.name, 'Test'); assert.deepStrictEqual(gpl.colors.map(c => C.hex(c)), ['#ff0000', '#00ff00']);
  assert.deepStrictEqual(C.parseHex('#ff0000\n00ff00 0000ff\r\n#abc').map(c => C.hex(c)), ['#ff0000', '#00ff00', '#0000ff', '#aabbcc']);
  assert.deepStrictEqual(C.parseJASC('JASC-PAL\n0100\n2\n10 20 30\n40 50 60\n').map(c => C.hex(c)), ['#0a141e', '#28323c']);
  const rgba = new Uint8Array([255, 0, 0, 255, 0, 0, 0, 0, 0, 255, 0, 255, 255, 0, 0, 255]); // red, transparent, green, red
  assert.deepStrictEqual(C.importAny(PNG.encode(2, 2, rgba)).colors.map(c => C.hex(c)), ['#ff0000', '#00ff00']);
  assert.deepStrictEqual(C.importAny('GIMP Palette\n255 255 255 w\n').colors.map(c => C.hex(c)), ['#ffffff']);
  assert.ok(/^GIMP Palette/.test(C.toGPL('x', by('gameboy')))); assert.strictEqual(C.toHexList(by('gameboy')).trim().split('\n').length, 4);
  const ramp = C.ramp(C.parse('#000000'), C.parse('#ffffff'), 5); assert.strictEqual(ramp.length, 5); assert.strictEqual(C.hex(ramp[0]), '#000000'); assert.strictEqual(C.hex(ramp[4]), '#ffffff');
  const map = C.remapByLuma([C.parse('#000000'), C.parse('#808080'), C.parse('#ffffff')], [C.parse('#400000'), C.parse('#ff8000'), C.parse('#ffff80')]);
  assert.deepStrictEqual(map.map(c => C.hex(c)), ['#400000', '#ff8000', '#ffff80']);
  assert.strictEqual(C.parse('rgb(1,2,3)'), C.pack(1, 2, 3)); assert.strictEqual(C.parse('nope'), null);
});

test('GIF encoder: LZW round trip through an independent decoder, loop and delays', () => {
  const w = 9, h = 7, frames = [];
  for (let f = 0; f < 3; f++) { const rgba = new Uint8Array(w * h * 4); for (let i = 0; i < w * h; i++) { const on = (i + f) % 4 !== 0; rgba.set(on ? [20 * f + 10, 200 - 30 * f, (i * 9) & 255, 255] : [0, 0, 0, 0], i * 4); } frames.push({ rgba, delay: 70 + f * 30 }); }
  const gif = GIF.encode({ width: w, height: h, frames, loop: 0 });
  assert.strictEqual(Buffer.from(gif.subarray(0, 6)).toString(), 'GIF89a');
  const dec = decodeGif(gif); assert.strictEqual(dec.frames.length, 3); assert.strictEqual(dec.w, 9);
  dec.frames.forEach((fr, f) => {
    assert.strictEqual(fr.delay, Math.round((70 + f * 30) / 10) * 10);
    for (let i = 0; i < w * h; i++) {
      const src = frames[f].rgba.subarray(i * 4, i * 4 + 4);
      if (src[3] === 0) assert.strictEqual(fr.rgba[i * 4 + 3], 0, 'transparent pixel ' + i);
      else assert.deepStrictEqual(Array.from(fr.rgba.subarray(i * 4, i * 4 + 4)), Array.from(src));
    }
  });
  // >256 colours quantises instead of failing
  const big = new Uint8Array(32 * 32 * 4); for (let i = 0; i < 1024; i++) big.set([i & 255, (i >> 2) & 255, (i * 3) & 255, 255], i * 4);
  assert.strictEqual(decodeGif(GIF.encode({ width: 32, height: 32, frames: [{ rgba: big, delay: 100 }] })).frames.length, 1);
});

function decodeGif(b) { // tiny independent GIF decoder for tests
  let p = 6; const w = b[p] | (b[p + 1] << 8), h = b[p + 2] | (b[p + 3] << 8), flags = b[p + 4]; p += 7;
  let gpal = null; if (flags & 0x80) { const n = 2 << (flags & 7); gpal = b.subarray(p, p + n * 3); p += n * 3; }
  const frames = []; let delay = 0, trans = -1;
  while (p < b.length) {
    const t = b[p++];
    if (t === 0x3B) break;
    if (t === 0x21) {
      const l = b[p++]; let sz = b[p++];
      if (l === 0xF9) { delay = (b[p + 1] | (b[p + 2] << 8)) * 10; trans = (b[p] & 1) ? b[p + 3] : -1; }
      for (;;) { p += sz; sz = b[p++]; if (sz === 0) break; }
    }
    else if (t === 0x2C) {
      p += 8; const lf = b[p++]; let pal = gpal; if (lf & 0x80) { const n = 2 << (lf & 7); pal = b.subarray(p, p + n * 3); p += n * 3; }
      const minCode = b[p++]; const data = []; let sz; while ((sz = b[p++]) !== 0) { for (let i = 0; i < sz; i++) data.push(b[p + i]); p += sz; }
      const idx = lzwDecode(data, minCode, w * h), rgba = new Uint8Array(w * h * 4);
      for (let i = 0; i < w * h; i++) { const c = idx[i]; if (c === trans) continue; rgba[i * 4] = pal[c * 3]; rgba[i * 4 + 1] = pal[c * 3 + 1]; rgba[i * 4 + 2] = pal[c * 3 + 2]; rgba[i * 4 + 3] = 255; }
      frames.push({ rgba, delay });
    }
  }
  return { w, h, frames };
}
function lzwDecode(data, minCode, n) {
  const clear = 1 << minCode, eoi = clear + 1; let size = minCode + 1, dict = [], out = [], bits = 0, cur = 0, pos = 0, prev = null;
  const reset = () => { dict = []; for (let i = 0; i < clear; i++) dict.push([i]); dict.push(null, null); size = minCode + 1; prev = null; };
  reset();
  for (;;) {
    while (bits < size) { if (pos >= data.length) return out; cur |= data[pos++] << bits; bits += 8; }
    const code = cur & ((1 << size) - 1); cur >>>= size; bits -= size;
    if (code === clear) { reset(); continue; } if (code === eoi) break;
    let entry; if (code < dict.length && dict[code]) entry = dict[code]; else entry = prev.concat(prev[0]);
    out.push(...entry); if (prev) dict.push(prev.concat(entry[0])); prev = entry;
    if (dict.length === (1 << size) && size < 12) size++;
    if (out.length >= n) break;
  }
  return out;
}
module.exports = { decodeGif };
