'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { M, C, D, PNG, Tools, newSession, px } = require('./helpers.js');

function paint(doc, x, y, v, l = 0, f = 0) { doc.cw(doc.layers[l].id, doc.frames[f].id)[y * doc.w + x] = v; }

test('history: undo/redo restores pixels and structure, redo is cleared by new edits', () => {
  const d = new M.Doc({ w: 8, h: 8, mode: 'rgba' });
  d.edit('a', () => paint(d, 1, 1, 0xff0000ff));
  d.edit('b', () => { paint(d, 2, 2, 0xff00ff00); d.addLayer('Top'); });
  assert.strictEqual(d.layers.length, 2); assert.strictEqual(d.undoStack.length, 2);
  assert.strictEqual(d.undo(), 'b'); assert.strictEqual(d.layers.length, 1); assert.strictEqual(px(d, 2, 2), 0);
  assert.strictEqual(px(d, 1, 1), 0xff0000ff);
  d.redo(); assert.strictEqual(d.layers.length, 2); assert.strictEqual(px(d, 2, 2), 0xff00ff00);
  d.undo(); d.edit('c', () => paint(d, 3, 3, 1)); assert.strictEqual(d.canRedo(), false);
  d.undo(); d.undo(); assert.strictEqual(px(d, 1, 1), 0); assert.strictEqual(d.canUndo(), false);
});

test('history: no-op edits leave no step, failed edits roll back completely', () => {
  const d = new M.Doc({ w: 4, h: 4 });
  d.edit('noop', () => { d.cw(d.layers[0].id, d.frames[0].id); });
  assert.strictEqual(d.undoStack.length, 0);
  assert.throws(() => d.edit('bad', () => { paint(d, 0, 0, 5); d.addFrame(); throw new Error('boom'); }), /boom/);
  assert.strictEqual(d.frames.length, 1); assert.strictEqual(d.cels.size === 0 || px(d, 0, 0) === 0, true); assert.strictEqual(d.undoStack.length, 0);
  assert.throws(() => paint(d, 0, 0, 1), /inside doc.edit/);
});

test('history: nested edits and collapseSince give ONE undo step for a whole AI turn', () => {
  const d = new M.Doc({ w: 8, h: 8 });
  const mark = d.undoStack.length;
  d.edit('one', () => paint(d, 0, 0, 1)); d.edit('two', () => { paint(d, 1, 0, 2); d.addFrame(); }); d.edit('three', () => paint(d, 2, 0, 3, 0, 1));
  assert.strictEqual(d.undoStack.length, 3);
  d.collapseSince(mark, 'AI: knight');
  assert.strictEqual(d.undoStack.length, 1); assert.strictEqual(d.undoStack[0].label, 'AI: knight');
  d.undo(); assert.strictEqual(d.frames.length, 1); assert.strictEqual(px(d, 0, 0), 0); assert.strictEqual(px(d, 1, 0), 0);
  d.redo(); assert.strictEqual(d.frames.length, 2); assert.strictEqual(px(d, 1, 0), 2); assert.strictEqual(px(d, 2, 0, 0, 1), 3);
  const n = new M.Doc({ w: 4, h: 4 }); n.edit('x', () => n.begin('inner') || n.end(true)); // begin/end nesting works
});

test('structure: layers, frames, tags follow insertions and deletions', () => {
  const d = new M.Doc({ w: 4, h: 4 });
  d.addFrame(); d.addFrame(); d.addFrame(); // 4 frames
  d.setTag({ name: 'walk', from: 1, to: 2 });
  d.addFrame(0, undefined); assert.deepStrictEqual([d.tags[0].from, d.tags[0].to], [2, 3]);
  d.removeFrame(0); assert.deepStrictEqual([d.tags[0].from, d.tags[0].to], [1, 2]);
  d.removeFrame(1); assert.deepStrictEqual([d.tags[0].from, d.tags[0].to], [1, 1]);
  d.removeFrame(1); assert.strictEqual(d.tags.length, 0);
  const l2 = d.addLayer('Eyes'); d.edit('p', () => paint(d, 1, 1, 7, 1, 0));
  d.duplicateLayer(l2.id); assert.strictEqual(d.layers.length, 3); assert.strictEqual(px(d, 1, 1, 2, 0), 7);
  d.moveLayer(l2.id, 0); assert.strictEqual(d.layers[0].name, 'Eyes');
  assert.throws(() => d.setLayer(l2.id, { blend: 'nope' }), /blend/);
  d.setLayer(l2.id, { opacity: 128, blend: 'multiply', visible: false }); assert.strictEqual(d.layerById(l2.id).opacity, 128);
  const f = d.addFrame(undefined, 0); assert.ok(f.id); assert.throws(() => { const one = new M.Doc(); one.removeFrame(0); }, /at least one/);
});

test('palette ops: indexed pixels follow reorder/remove; rgba palette edits recolour linked pixels', () => {
  const d = new M.Doc({ w: 4, h: 1, mode: 'indexed', palette: [C.pack(255, 0, 0), C.pack(0, 255, 0), C.pack(0, 0, 255)] });
  d.edit('p', () => { const b = d.cw(d.layers[0].id, d.frames[0].id); b[0] = 1; b[1] = 2; b[2] = 3; });
  d.reorderPalette([2, 1, 0]); assert.deepStrictEqual(Array.from(d.celAt(0, 0).subarray(0, 3)), [3, 2, 1]);
  d.reorderPalette([0, 1]); // drops last entry (old index 0 after reorder = red). value 1 -> now dropped? order keeps new idx 0,1
  assert.strictEqual(d.palette.length, 2); assert.strictEqual(d.celAt(0, 0)[2], 1);
  assert.strictEqual(d.celAt(0, 0)[0], 0); // pixel pointing at dropped entry became transparent
  d.undo(); assert.strictEqual(d.palette.length, 3);
  d.setPaletteColor(0, C.pack(1, 2, 3)); assert.strictEqual(d.valueToRGBA(d.celAt(0, 0)[2]), C.pack(1, 2, 3));
  const r = new M.Doc({ w: 2, h: 1, mode: 'rgba', palette: [C.pack(9, 9, 9)] }); r.edit('p', () => { r.cw(r.layers[0].id, r.frames[0].id)[0] = C.pack(9, 9, 9); });
  r.setPaletteColor(0, C.pack(200, 0, 0)); assert.strictEqual(r.celAt(0, 0)[0], C.pack(200, 0, 0));
});

test('mode conversion rgba <-> indexed keeps colours', () => {
  const pal = [C.pack(10, 20, 30), C.pack(200, 100, 50)];
  const d = new M.Doc({ w: 2, h: 1, mode: 'rgba', palette: pal });
  d.edit('p', () => { const b = d.cw(d.layers[0].id, d.frames[0].id); b[0] = pal[1]; b[1] = C.pack(12, 22, 28); });
  d.convertMode('indexed'); assert.deepStrictEqual(Array.from(d.celAt(0, 0)), [2, 1]);
  d.convertMode('rgba'); assert.deepStrictEqual(Array.from(d.celAt(0, 0)), [pal[1], pal[0]]);
  d.undo(); assert.strictEqual(d.mode, 'indexed'); d.undo(); assert.strictEqual(d.mode, 'rgba');
});

test('resize with anchors and crop', () => {
  const d = new M.Doc({ w: 4, h: 4 }); d.edit('p', () => paint(d, 0, 0, 5));
  d.resize(8, 8, 0, 0); assert.strictEqual(d.w, 8); assert.strictEqual(px(d, 0, 0), 5); assert.strictEqual(d.celAt(0, 0).length, 64);
  d.resize(6, 6, 1, 1); assert.strictEqual(px(d, 0, 0), 0); d.undo(); assert.strictEqual(d.w, 8);
  d.resize(4, 4, 0.5, 0.5); assert.strictEqual(d.w, 4);
});

test('compositing: layer order, opacity, blend modes, hidden layers', () => {
  const d = new M.Doc({ w: 1, h: 1, mode: 'rgba' }); const top = d.addLayer('top');
  d.edit('p', () => { d.cw(d.layers[0].id, d.frames[0].id)[0] = C.pack(100, 100, 100); d.cw(top.id, d.frames[0].id)[0] = C.pack(200, 50, 50); });
  assert.deepStrictEqual(Array.from(d.composite(0)), [200, 50, 50, 255]);
  d.setLayer(top.id, { opacity: 128 }); const o = d.composite(0); assert.ok(Math.abs(o[0] - 150) <= 1 && o[3] === 255);
  d.setLayer(top.id, { opacity: 255, blend: 'multiply' }); assert.strictEqual(d.composite(0)[0], Math.round(100 * 200 / 255));
  d.setLayer(top.id, { blend: 'normal', visible: false }); assert.strictEqual(d.composite(0)[0], 100);
  const e = new M.Doc({ w: 1, h: 1, mode: 'indexed', palette: [C.pack(1, 2, 3)] }); e.edit('p', () => { e.cw(e.layers[0].id, e.frames[0].id)[0] = 1; });
  assert.deepStrictEqual(Array.from(e.composite(0)), [1, 2, 3, 255]);
  const l3 = d.addLayer('x'); d.setLayer(top.id, { visible: true }); d.mergeLayerDown(top.id); assert.strictEqual(d.layers.length, 2);
});

test('native project JSON round trip (rgba and indexed)', () => {
  for (const mode of ['rgba', 'indexed']) {
    const d = new M.Doc({ w: 5, h: 3, mode, palette: C.builtin('pico8').colors }); d.name = 'rt';
    d.addFrame(); d.setTag({ name: 'a', from: 0, to: 1, dir: 'pingpong' }); const l = d.addLayer('L2'); d.setLayer(l.id, { opacity: 99, blend: 'screen', locked: true });
    d.edit('p', () => { d.cw(d.layers[0].id, d.frames[1].id)[7] = mode === 'rgba' ? C.pack(1, 2, 3) : 16; d.cw(l.id, d.frames[0].id)[0] = mode === 'rgba' ? C.pack(9, 8, 7) : 3; });
    const back = M.Doc.fromJSON(JSON.parse(JSON.stringify(d.toJSON())));
    assert.strictEqual(back.mode, mode); assert.strictEqual(back.w, 5); assert.strictEqual(back.frames.length, 2); assert.strictEqual(back.layers[1].blend, 'screen'); assert.strictEqual(back.layers[1].locked, true);
    assert.strictEqual(back.tags[0].dir, 'pingpong'); assert.strictEqual(px(back, 2, 1, 0, 1), px(d, 2, 1, 0, 1)); assert.strictEqual(px(back, 0, 0, 1, 0), px(d, 0, 0, 1, 0));
    assert.deepStrictEqual(back.palette, d.palette);
  }
  assert.throws(() => M.Doc.fromJSON({ format: 'other' }), /not an Amerika/);
});

test('session: current frame/layer stay valid when the document shrinks', () => {
  const S = newSession(4, 4); S.doc.addFrame(); S.doc.addFrame(); S.setFrame(2); S.doc.removeFrame(2); assert.strictEqual(S.fi, 1);
});
