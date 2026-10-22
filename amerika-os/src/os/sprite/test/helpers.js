'use strict';
const path = require('path');
const J = (n) => require(path.join(__dirname, '..', 'app', 'js', n + '.js'));
const M = J('model'), C = J('color'), D = J('draw'), PNG = J('png'), GIF = J('gif'), X = J('export'), Z = J('zlib');
const { Session } = J('session');
const Tools = J('tools');
function newSession(w, h, mode) { return new Session(new M.Doc({ w: w || 16, h: h || 16, mode: mode || 'rgba' })); }
function px(doc, x, y, layer, frame) { const c = doc.celAt(layer || 0, frame || 0); return c ? c[y * doc.w + x] : 0; }
module.exports = { J, M, C, D, PNG, GIF, X, Z, Session, Tools, newSession, px };
