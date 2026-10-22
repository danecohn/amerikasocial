// Test harness: loads BeepBox's real synth bundle (no DOM) into a vm context and builds a headless tool host.
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const APP = path.join(__dirname, "..", "app");

function loadBeepBox() {
	const ctx = { console, performance, Math, Date, setTimeout, Float32Array, Float64Array, Int32Array, Uint8Array, Array, JSON, Object, Error };
	ctx.window = ctx; ctx.self = ctx;
	vm.createContext(ctx);
	vm.runInContext(fs.readFileSync(path.join(APP, "beepbox_synth.min.js"), "utf8") + "\n;this.beepbox = beepbox;", ctx, { filename: "beepbox_synth.min.js" });
	return ctx.beepbox;
}

function makeHost(B, json) {
	const host = {
		song: new B.Song(), history: [], played: [], silent: true,
		getSong() { return this.song; },
		commit(song, label) { this.history.push({ label, json: JSON.stringify(this.song.toJsonObject()) }); this.song = song; },
		play(o) { this.played.push(o); }, stop() { this.played.push("stop"); },
		undo(steps) { for (let i = 0; i < steps; i++) { const h = this.history.pop(); if (!h) break; const s = new B.Song(); s.fromJsonObject(JSON.parse(h.json)); this.song = s; } },
	};
	if (json) host.song.fromJsonObject(json);
	return host;
}

function setup(json) {
	const B = loadBeepBox();
	const host = makeHost(B, json);
	const tools = require(path.join(APP, "amerika", "songtools.js")).create(B, host);
	return { B, host, tools };
}
module.exports = { loadBeepBox, makeHost, setup, APP };
