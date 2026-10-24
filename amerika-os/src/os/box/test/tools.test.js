"use strict";
// Node tests for the AltStack Box song tools, run against BeepBox's real Song/Synth classes (headless).
//   ../tools/node/bin/node --test src/os/box/test/
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { setup, APP } = require("./harness.js");
const T = require(path.join(APP, "amerika", "theory.js"));
const A = require(path.join(APP, "amerika", "audio.js"));
const X = require(path.join(APP, "amerika", "export.js"));

const REQUIRED_TOOLS = ["song_info", "set_song_settings", "add_channel", "add_instrument", "set_instrument", "write_pattern", "write_track", "set_sequence",
	"clear", "delete", "get_song_json", "set_song_json", "render_preview", "analyze_audio", "play", "stop", "theory", "genre_preset", "generate_part", "transform_notes", "read_notes", "new_song", "undo"];

async function fails(promise, re) {
	await assert.rejects(promise, (e) => { assert.match(e.message, re); return true; });
}

test("tool definitions are well formed", () => {
	const { tools } = setup();
	const names = tools.definitions.map((d) => d.name);
	assert.equal(new Set(names).size, names.length, "duplicate tool names");
	for (const n of REQUIRED_TOOLS) assert.ok(names.includes(n), "missing tool " + n);
	for (const d of tools.definitions) {
		assert.match(d.name, /^[a-z_]+$/);
		assert.ok(d.description.length > 20, d.name);
		assert.equal(d.input_schema.type, "object");
		assert.ok(JSON.stringify(d.input_schema).length < 6000, d.name + " schema too large");
		for (const r of d.input_schema.required || []) assert.ok(d.input_schema.properties[r], d.name + " requires unknown property " + r);
	}
	const total = JSON.stringify(tools.definitions).length;
	assert.ok(total < 60000, "tool definitions too big: " + total);
});

test("canned composer session builds a valid, audible song through the tools", async () => {
	const { tools, host, B } = setup();
	const run = (n, a) => tools.run(n, a);
	await run("new_song", { layout: "empty", key: "A", scale: "minor", tempo: 150, bars: 8 });
	let info = await run("song_info", {});
	assert.equal(info.key, "A"); assert.equal(info.scale, "normal :("); assert.equal(info.tempo, 150); assert.equal(info.bars, 8);
	assert.equal(info.channels.length, 2);

	await run("add_channel", { type: "pitch", instrument: "triangle bass", octave: 2 });
	await run("add_channel", { type: "pitch", instrument: { type: "FM", volume: 70, algorithm: "1←(2 3 4)", reverb: 30 } });
	info = await run("song_info", {});
	assert.deepEqual(info.channels.map((c) => c.type), ["pitch", "pitch", "pitch", "drum"], "pitch channels come before drum channels");

	await run("write_track", { channel: 1, notes: "A4@0+1 C5@1+1 E5@2+1 C5@3+1 A4@4+2 G4@6+2 F4@8+4 E4@12+4", bars: 4 });
	await run("generate_part", { channel: 2, kind: "bass", progression: "i VI III VII", bars: 8, style: "arp" });
	await run("generate_part", { channel: 4, kind: "drums", bars: 8, template: "boss double kick", fill_every: 4 });
	await run("write_pattern", { channel: 3, pattern: 1, notes: "A3/C4/E4@0+4", bars: "1-8" });
	await run("set_instrument", { channel: 1, settings: { wave: "sawtooth", volume: 75, effects: ["chorus"], chorus: 40 } });
	await run("add_instrument", { channel: 1, instrument: "pluck" });
	await run("write_pattern", { channel: 1, pattern: 5, notes: "E5@0+2 A5@2+2", instrument: 2, bars: [5, 6, 7, 8] });
	info = await run("song_info", {});
	const lead = info.channels[0];
	assert.equal(info.patternInstruments, true, "adding a second instrument enables pattern instruments");
	assert.match(lead.instruments[0], /sawtooth/);
	assert.match(lead.instruments[1], /Picked String/);
	assert.ok(lead.notes >= 12, "lead notes " + lead.notes);
	assert.match(lead.sequence, /5x4/);
	assert.equal(info.channels[3].type, "drum");
	assert.ok(info.channels[3].notes > 40);

	// the song validates through BeepBox itself and survives a JSON round trip unchanged
	const json = (await run("get_song_json", {})).song;
	const s2 = new B.Song(); s2.fromJsonObject(JSON.parse(JSON.stringify(json)));
	assert.equal(JSON.stringify(s2.toJsonObject()), JSON.stringify(json));
	const hashSong = new B.Song(host.getSong().toBase64String());
	assert.equal(JSON.stringify(hashSong.toJsonObject()), JSON.stringify(json), "BeepBox URL hash round trip");

	const prev = await run("render_preview", {});
	assert.equal(prev.silent, false);
	assert.ok(Math.abs(prev.seconds - 12.8) < 0.05, "8 bars at 150 bpm = 12.8 s, got " + prev.seconds);
	assert.ok(prev.peakDbfs < 0.5 && prev.peakDbfs > -40, "peak " + prev.peakDbfs);
	const an = await run("analyze_audio", {});
	assert.equal(an.channels.length, 4);
	assert.ok(an.channels.every((c) => c.rmsDbfs > -100), "every channel is audible: " + JSON.stringify(an.channels));
	assert.match(an.text, /Per-channel/);

	// undo: the host keeps history (in the editor this is BeepBox's own undo)
	const before = host.history.length;
	await run("set_song_settings", { tempo: 120 });
	assert.equal(host.getSong().tempo, 120);
	await run("undo", { steps: 1 });
	assert.equal(host.getSong().tempo, 150);
	assert.equal(host.history.length, before);
});

test("note text maps to BeepBox pitches, ticks and volumes", async () => {
	const { tools, B } = setup();
	await tools.run("new_song", { layout: "empty", key: "C", bars: 2 });
	await tools.run("write_pattern", { channel: 1, pattern: 1, notes: "C4@0+1 E4/G4@1+1v67 A4@2+1f33b2 C5@3+1", bars: "1" });
	let j = (await tools.run("get_song_json", {})).song;
	const notes = j.channels[0].patterns[0].notes;
	assert.equal(notes.length, 4);
	assert.deepEqual(notes[0].pitches, [48], "C4 = MIDI 60 = BeepBox pitch 48 in key C");
	assert.deepEqual(notes[1].pitches, [52, 55]);
	assert.equal(notes[1].points[0].volume, 67);
	assert.equal(notes[2].points[0].volume, 100);
	assert.equal(notes[2].points[notes[2].points.length - 1].volume, 33);
	assert.equal(notes[2].points[notes[2].points.length - 1].pitchBend, 2);
	assert.equal(notes[0].points[0].tick, 0); assert.equal(notes[0].points[1].tick, 4, "ticks are 1/ticksPerBeat beats (4 per beat)");
	// a different key moves the base pitch
	await tools.run("set_song_settings", { key: "D" });
	await tools.run("write_pattern", { channel: 1, pattern: 1, notes: "D4@0+1" });
	j = (await tools.run("get_song_json", {})).song;
	assert.deepEqual(j.channels[0].patterns[0].notes[0].pitches, [62 - 14], "D4 = MIDI 62; key D has base pitch 14");
	assert.equal(j.channels[0].patterns[0].notes[0].points[0].tick, 0);
	// reading back gives the same text
	const rd = await tools.run("read_notes", { channel: 1, bars: 1 });
	assert.match(rd.text, /D4@0\+1/);
	// overlaps are resolved and reported, notes outside the bar are dropped with a warning
	const r = await tools.run("write_pattern", { channel: 1, pattern: 2, notes: "C4@0+2 D4@1+2 E4@9+1" });
	assert.ok(r.warnings && r.warnings.length >= 2, JSON.stringify(r.warnings));
	void B;
});

test("write_track splits across bars, ties notes and reuses identical patterns", async () => {
	const { tools } = setup();
	await tools.run("new_song", { layout: "empty", bars: 8 });
	// bar 1: a note that starts on beat 3 and runs into bar 2; bars 3 and 4 are identical; bar 5 is empty
	await tools.run("write_track", { channel: 1, notes: "C4@3+2 D4@5+1 C4@8+1 D4@9+1 C4@12+1 D4@13+1", bars: 5 });
	const j = (await tools.run("get_song_json", {})).song;
	const c = j.channels[0];
	assert.equal(c.sequence.length, 8);
	assert.equal(c.sequence[2], c.sequence[3], "identical bars share one pattern");
	assert.notEqual(c.sequence[1], c.sequence[2]);
	assert.equal(c.sequence[4], 0, "bar 5 is empty");
	const tied = c.patterns[c.sequence[1] - 1].notes[0];
	assert.equal(tied.points[0].tick, 0);
	assert.equal(tied.continuesLastPattern, true, "the continuation is tied to the previous bar");
	const rd = await tools.run("read_notes", { channel: 1, from_bar: 1, bars: 2 });
	assert.match(rd.text, /bar 1[^\n]*C4@3\+1/);
	assert.match(rd.text, /bar 2[^\n]*C4@0\+1 D4@1\+1/);
	// writing again replaces the bars and cleans up unused patterns
	await tools.run("write_track", { channel: 1, notes: "E4@0+4", bars: 8 });
	const j2 = (await tools.run("get_song_json", {})).song;
	assert.equal(j2.channels[0].sequence[0], 1);
	assert.ok(j2.channels[0].sequence.slice(1).every((x) => x === 0));
	assert.equal(j2.channels[0].patterns.length, 1, "unused patterns were cleaned up");
});

test("validation errors are specific and list the allowed values", async () => {
	const { tools } = setup();
	await tools.run("new_song", { layout: "standard", bars: 4 });
	await fails(tools.run("set_instrument", { channel: 1, settings: { wave: "wobble" } }), /unknown chip wave 'wobble'.*square/);
	await fails(tools.run("set_instrument", { channel: 1, settings: { effects: ["flanger"] } }), /unknown effect 'flanger'.*reverb/);
	await fails(tools.run("set_instrument", { channel: 1, settings: { type: "drumset" } }), /pitch-channel instrument type/);
	await fails(tools.run("add_channel", { type: "drum", instrument: "square lead" }), /drum-channel instrument type/);
	await fails(tools.run("write_pattern", { channel: 1, pattern: 1, notes: "C9@0+1" }), /outside this song's range/);
	await fails(tools.run("write_pattern", { channel: 1, pattern: 1, notes: "H4@0+1" }), /cannot read pitch|cannot read note/);
	await fails(tools.run("write_pattern", { channel: 4, pattern: 1, notes: "13@0+1" }), /drum row 13/);
	await fails(tools.run("write_pattern", { channel: 9, pattern: 1, notes: "" }), /channel 9 does not exist/);
	await fails(tools.run("set_sequence", { channel: 1, sequence: "1 99" }), /pattern 99 does not exist/);
	await fails(tools.run("set_song_settings", { tempo: 999 }), /tempo must be/);
	await fails(tools.run("set_song_settings", { scale: "klingon" }), /unknown scale/);
	await fails(tools.run("set_song_settings", { bars: 500 }), /bars must be/);
	await fails(tools.run("nonexistent", {}), /unknown tool/);
	// channel limits
	for (let i = 0; i < 7; i++) await tools.run("add_channel", { type: "pitch" });
	await fails(tools.run("add_channel", { type: "pitch" }), /too many pitch channels/);
	for (let i = 0; i < 4; i++) await tools.run("add_channel", { type: "drum" });
	await fails(tools.run("add_channel", { type: "drum" }), /too many drum channels/);
	// a failed tool leaves the song untouched
	const before = JSON.stringify((await tools.run("get_song_json", {})).song);
	await fails(tools.run("set_instrument", { channel: 1, settings: { wave: "nope" } }), /unknown/);
	assert.equal(JSON.stringify((await tools.run("get_song_json", {})).song), before);
});

test("set_song_json accepts BeepBox JSON, URL hashes and reports dropped notes", async () => {
	const a = setup();
	await a.tools.run("genre_preset", { name: "chiptune", bars: 8 });
	const json = (await a.tools.run("get_song_json", {})).song;
	const b = setup();
	const r = await b.tools.run("set_song_json", { song: json });
	assert.match(r.message, /notes kept/);
	assert.deepEqual((await b.tools.run("get_song_json", {})).song, json);
	const hash = a.host.getSong().toBase64String();
	const c = setup();
	await c.tools.run("set_song_json", { song: "#" + hash });
	assert.deepEqual((await c.tools.run("get_song_json", {})).song, json);
	await fails(c.tools.run("set_song_json", { song: "{not json" }), /not valid JSON/);
	await fails(c.tools.run("set_song_json", { song: { channels: [] } }), /non-empty/);
	await fails(c.tools.run("set_song_json", { song: { channels: [{ type: "pitch", instruments: [{ type: "chip", wave: "zzz" }] }] } }), /unknown chip wave/);
});

test("transform_notes: transpose, scale mapping, copy-on-write ranges", async () => {
	const { tools } = setup();
	await tools.run("new_song", { layout: "empty", key: "C", scale: "major", bars: 4 });
	await tools.run("write_track", { channel: 1, notes: "C4@0+1 E4@1+1 G4@2+1 B4@3+1 C4@4+1 E4@5+1 G4@6+1 B4@7+1", bars: 2 });
	await tools.run("transform_notes", { channels: [1], scale_map: { from: "major", to: "minor" } });
	let rd = (await tools.run("read_notes", { channel: 1, bars: 2 })).text;
	assert.match(rd, /C4@0\+1 D#4@1\+1 G4@2\+1 A#4@3\+1/, rd); // E->Eb, B->Bb (displayed with sharps)
	await tools.run("transform_notes", { channels: [1], octaves: 1, from_bar: 2, to_bar: 2 });
	rd = (await tools.run("read_notes", { channel: 1, bars: 2 })).text;
	assert.match(rd, /bar 1[^\n]*C4@0\+1/); assert.match(rd, /bar 2[^\n]*C5@0\+1/);
	await tools.run("transform_notes", { channels: [1], volume_scale: 0.67 });
	const j = (await tools.run("get_song_json", {})).song;
	assert.ok(j.channels[0].patterns.some((p) => p.notes.some((n) => n.points[0].volume === 67)));
});

test("clear and delete", async () => {
	const { tools } = setup();
	await tools.run("genre_preset", { name: "battle", bars: 8 });
	let info = await tools.run("song_info", {});
	const nch = info.channels.length;
	await tools.run("clear", { channel: 1, bars: "5-8" });
	info = await tools.run("song_info", {});
	assert.match(info.channels[0].sequence, /0x4$/);
	await tools.run("clear", { channel: 1 });
	assert.equal((await tools.run("song_info", {})).channels[0].notes, 0);
	await tools.run("delete", { channel: 2 });
	assert.equal((await tools.run("song_info", {})).channels.length, nch - 1);
	await fails(tools.run("delete", { channel: 1, instrument: 1 }), /at least one instrument/);
});

test("theory lookups", async () => {
	const { tools } = setup();
	await tools.run("new_song", { key: "A", scale: "minor" });
	const sc = await tools.run("theory", { action: "scale", low: "A3", high: "A4" });
	assert.equal(sc.notes, "A3 B3 C4 D4 E4 F4 G4 A4");
	const pr = await tools.run("theory", { action: "progression", progression: "i VI III VII", octave: 3 });
	assert.deepEqual(pr.chords.map((c) => c.chord), ["Am", "F", "C", "G"]);
	assert.equal(pr.chords[0].notes, "A3 C4 E4");
	const ch = await tools.run("theory", { action: "chord", symbol: "bVII" });
	assert.match(ch.notes, /^G/);
	const g = await tools.run("theory", { action: "genres" });
	for (const k of ["chiptune", "battle", "town", "dungeon", "victory", "defeat", "menu", "ambient"]) assert.ok(k in g.genres, k);
	assert.ok(Object.keys((await tools.run("theory", { action: "drum_templates" })).templates).length >= 8);
});

test("every instrument preset loads into BeepBox unchanged", () => {
	const { B } = setup();
	for (const name of Object.keys(T.INSTRUMENT_PRESETS)) {
		const ins = T.instrumentPreset(name);
		const drum = ["drumset", "noise", "spectrum"].includes(ins.type);
		const s = new B.Song();
		s.fromJsonObject({ beatsPerMinute: 120, channels: [{ type: "pitch", instruments: [T.instrumentPreset("square lead")], patterns: [{ notes: [] }], sequence: [1] }, { type: drum ? "drum" : "pitch", instruments: [ins], patterns: [{ notes: [] }], sequence: [1] }] });
		const back = s.toJsonObject().channels[1].instruments[0];
		assert.equal(back.type, ins.type, name);
		if (ins.wave) assert.equal(back.wave, ins.wave, name);
		if (ins.type === "FM") assert.equal(back.algorithm, ins.algorithm, name);
		for (const e of ins.effects) assert.ok(back.effects.includes(e), name + " keeps effect " + e);
	}
});

test("genre presets render audibly without clipping and have the expected shape", async () => {
	for (const g of Object.keys(T.GENRES)) {
		const { tools, host, B } = setup();
		await tools.run("genre_preset", { name: g });
		const info = await tools.run("song_info", {});
		assert.equal(info.tempo, T.GENRES[g].tempo, g);
		assert.equal(info.channels.some((c) => c.type === "drum"), !!T.GENRES[g].drums, g);
		assert.ok(info.channels.every((c) => c.notes > 0), g + " has an empty channel");
		const r = await A.renderSong(B, host.getSong(), { sampleRate: 32000, maxSeconds: 20 });
		const a = A.analyze(r, { tempo: false });
		assert.equal(a.silent, false, g);
		assert.equal(a.clippedSamples, 0, g + " clips");
		assert.ok(a.peakDbfs > -30, g + " too quiet: " + a.peakDbfs);
	}
});

test("drum kit rows are ordered kick < tom < snare < hat in brightness", async () => {
	const { tools, host, B } = setup();
	await tools.run("new_song", { layout: "empty", bars: 1 });
	const centroid = {};
	for (const [name, row] of Object.entries({ kick: 0, tom: 2, snare: 5, hat: 8, crash: 10 })) {
		await tools.run("write_track", { channel: 2, notes: row + "@0+0.5", bars: 1 });
		const r = await A.renderSong(B, host.getSong(), { sampleRate: 32000, solo: 1, maxSeconds: 0.6 });
		const a = A.analyze(r, { tempo: false });
		assert.equal(a.silent, false, name);
		centroid[name] = a.spectralCentroidHz;
	}
	assert.ok(centroid.kick < centroid.tom && centroid.tom < centroid.snare && centroid.snare < centroid.hat, JSON.stringify(centroid));
	assert.ok(centroid.kick < 120 && centroid.crash > 1500, JSON.stringify(centroid));
});

function dominantHz(L, sr, from, n) {
	const re = new Float64Array(n), im = new Float64Array(n);
	for (let i = 0; i < n; i++) re[i] = L[from + i] * (0.5 - 0.5 * Math.cos(2 * Math.PI * i / (n - 1)));
	const sp = A.powerSpectrum(Float32Array.from(re), sr, n);
	let best = 0, bi = 0; for (let i = 2; i < sp.power.length; i++) if (sp.power[i] > best) { best = sp.power[i]; bi = i; }
	void im; return bi * sp.binHz;
}

test("rendered pitch and tempo are musically correct", async () => {
	// A4 = 440 Hz, whatever the key
	for (const key of ["C", "D", "F#"]) {
		const { tools, host, B } = setup();
		await tools.run("new_song", { layout: "empty", key, bars: 2, tempo: 120 });
		await tools.run("set_instrument", { channel: 1, settings: { wave: "triangle", effects: ["chord type"], chord: "simultaneous", volume: 100 } });
		await tools.run("write_track", { channel: 1, notes: "A4@0+4", bars: 1 });
		const r = await A.renderSong(B, host.getSong(), { sampleRate: 44100, maxSeconds: 1.5 });
		const hz = dominantHz(r.L, 44100, 8192, 16384);
		assert.ok(Math.abs(hz - 440) < 6, key + ": expected 440 Hz, got " + hz);
	}
	// kick on every beat at 120 and 90 bpm
	for (const bpm of [120, 90, 140]) {
		const { tools, host, B } = setup();
		await tools.run("new_song", { layout: "empty", bars: 8, tempo: bpm });
		await tools.run("generate_part", { channel: 2, kind: "drums", bars: 8, template: "four on the floor" });
		await tools.run("clear", { channel: 1 });
		const r = await A.renderSong(B, host.getSong(), { sampleRate: 32000 });
		const barSeconds = 4 * 60 / bpm;
		assert.ok(Math.abs(r.seconds - 8 * barSeconds) < 0.05, "length " + r.seconds);
		const est = A.estimateBpm(A.mixToMono(r.L, r.R), 32000);
		assert.ok(Math.abs(est - bpm) / bpm < 0.07, "estimated " + est + " for " + bpm);
	}
});

test("WAV export: exact length, 16-bit PCM, not silent, loop chunk, round trip", async () => {
	const { tools, host, B } = setup();
	await tools.run("genre_preset", { name: "boss", bars: 8 });
	const out = await X.renderWav(B, host.getSong(), { sampleRate: 48000 });
	const bytes = out.wav;
	const spb = Math.ceil(60 / 150 * 4 * 48000 * 8);
	assert.ok(Math.abs(out.frames - spb) <= 2, "frames " + out.frames + " vs " + spb);
	const w = A.decodeWav(bytes);
	assert.equal(w.sampleRate, 48000); assert.equal(w.channels, 2); assert.equal(w.frames, out.frames);
	let peak = 0; for (let i = 0; i < w.frames; i++) peak = Math.max(peak, Math.abs(w.L[i]));
	assert.ok(peak > 0.05 && peak <= 1, "peak " + peak);
	// drop a copy for the Python-side check (tests/test_studio_box.py reads it with the wave module)
	if (process.env.BOX_TEST_OUT) {
		fs.mkdirSync(process.env.BOX_TEST_OUT, { recursive: true });
		fs.writeFileSync(path.join(process.env.BOX_TEST_OUT, "boss.wav"), bytes);
		fs.writeFileSync(path.join(process.env.BOX_TEST_OUT, "boss.json"), JSON.stringify({ frames: out.frames, sampleRate: 48000, expectedFrames: spb, bpm: 150, bars: 8, peak }));
	}
	const looped = A.encodeWav(w.L, w.R, 48000, { loop: { start: 1000, end: 40000 } });
	const d = A.decodeWav(looped);
	assert.deepEqual(d.loop, { start: 1000, end: 40000 });
});

test("game bundle: seamless loop, metadata, Godot import presets, optional ogg", async () => {
	const { tools, host, B } = setup();
	await tools.run("genre_preset", { name: "town", bars: 8 });
	await tools.run("set_song_settings", { intro_bars: 2, loop_bars: 6 });
	const files = {};
	const jobs = [];
	const res = await X.buildGameBundle(B, host.getSong(), { name: "Town Theme!", sampleRate: 44100, normalizeDb: -1 }, {
		write: async (rel, data) => { files[rel] = data; },
		requestOgg: async (job) => { jobs.push(job); return { ok: true }; },
		progress: () => {},
	});
	assert.equal(res.dir, "exports/Town_Theme");
	const names = Object.keys(files).sort();
	assert.deepEqual(names, ["exports/Town_Theme/README.txt", "exports/Town_Theme/Town_Theme.json", "exports/Town_Theme/Town_Theme.ogg.import", "exports/Town_Theme/Town_Theme.song.json", "exports/Town_Theme/Town_Theme.wav", "exports/Town_Theme/Town_Theme.wav.import"]);
	const meta = JSON.parse(files["exports/Town_Theme/Town_Theme.json"]);
	const spb = 60 / 100 * 4;
	assert.equal(meta.bpm, 100); assert.equal(meta.intro_bars, 2); assert.equal(meta.loop_bars, 6);
	assert.ok(Math.abs(meta.loop_start_seconds - 2 * spb) < 0.01, meta.loop_start_seconds);
	assert.ok(Math.abs(meta.length_seconds - 8 * spb) < 0.01, meta.length_seconds);
	assert.equal(meta.loop_end_samples, meta.length_samples);
	assert.equal(meta.godot.loop_offset, meta.loop_start_seconds);
	assert.equal(meta.godot.bar_beats, 4);
	const w = A.decodeWav(files["exports/Town_Theme/Town_Theme.wav"]);
	assert.deepEqual(w.loop, { start: meta.loop_start_samples, end: meta.loop_end_samples });
	assert.equal(w.frames, meta.length_samples);
	let peak = 0; for (let i = 0; i < w.frames; i++) peak = Math.max(peak, Math.abs(w.L[i]), Math.abs(w.R[i]));
	assert.ok(Math.abs(20 * Math.log10(peak) + 1) < 0.1, "normalized to -1 dBFS, got " + 20 * Math.log10(peak));
	// loop seam: the jump from the last sample of the loop to its first sample is no bigger than normal sample-to-sample motion
	const a = meta.loop_start_samples, z = meta.loop_end_samples - 1;
	const jump = Math.abs(w.L[z] - w.L[a]);
	let maxStep = 0; for (let i = a + 1; i < z; i++) maxStep = Math.max(maxStep, Math.abs(w.L[i] - w.L[i - 1]));
	assert.ok(jump <= maxStep * 3 + 0.01, "loop seam jump " + jump + " vs max step " + maxStep);
	assert.equal(jobs.length, 1); assert.equal(jobs[0].loop_start, meta.loop_start_samples);
	assert.match(files["exports/Town_Theme/Town_Theme.ogg.import"], /importer="oggvorbisstr"[\s\S]*loop=true[\s\S]*loop_offset=/);
	assert.match(files["exports/Town_Theme/Town_Theme.wav.import"], /edit\/loop_mode=2/);
	// the embedded song re-loads
	const back = new B.Song(); back.fromJsonObject(JSON.parse(files["exports/Town_Theme/Town_Theme.song.json"]));
	assert.equal(back.tempo, 100);
	// without ogg support the bundle still succeeds
	const files2 = {};
	const r2 = await X.buildGameBundle(B, host.getSong(), { name: "x", sampleRate: 44100 }, { write: async (rel, d) => { files2[rel] = d; }, progress: () => {} });
	assert.equal(r2.ogg, "not requested"); assert.ok(!Object.keys(files2).some((n) => n.endsWith(".ogg.import")));
	// silence is refused
	const empty = setup(); await empty.tools.run("new_song", { layout: "empty" });
	await assert.rejects(X.buildGameBundle(empty.B, empty.host.getSong(), { name: "e" }, { write: async () => {}, progress: () => {} }), /silence/);
});

test("rpc path confinement helper", () => {
	globalThis.window = globalThis;
	require(path.join(APP, "amerika", "rpc.js"));
	const chk = globalThis.Amerika.rpc.checkRelPath;
	assert.equal(chk("exports/a.wav"), "exports/a.wav");
	for (const bad of ["/etc/passwd", "../x", "a/../../b", "~/x", "C:\\x", ""]) assert.throws(() => chk(bad), (e) => typeof e.code === "number" && e.code <= -32000);
	assert.throws(() => chk("/x"), (e) => e.code === -32003);
});

test("system prompt teaches the constraints and stays a sensible size", () => {
	const P = require(path.join(APP, "amerika", "prompt.js"));
	for (const needle of ["10 pitch channels", "5 drum", "128 bars", "PATTERNS", "SEQUENCE", "drum kit", "arpeggio", "render_preview", "write_track", "numbered from 1"]) assert.ok(P.SYSTEM.includes(needle), needle);
	assert.ok(P.SYSTEM.length < 12000);
	assert.ok(P.QUICK_PROMPTS.length >= 6);
});

test("no network access anywhere in the shipped app", () => {
	const bad = [];
	const scan = (dir) => {
		for (const f of fs.readdirSync(dir, { withFileTypes: true })) {
			const p = path.join(dir, f.name);
			if (f.isDirectory()) { scan(p); continue; }
			if (!/\.(js|html|css)$/.test(f.name) || /vendor/.test(p)) continue;
			const text = fs.readFileSync(p, "utf8");
			for (const m of text.matchAll(/\b(fetch\(|XMLHttpRequest|WebSocket\(|EventSource\(|sendBeacon|serviceWorker|importScripts|(?:src|href)\s*=\s*["']https?:)/g)) bad.push(path.relative(APP, p) + ": " + m[0]);
			if (/cdn\.jsdelivr|googleapis|google-analytics|tinyurl|gtag/.test(text)) bad.push(path.relative(APP, p) + ": remote service");
		}
	};
	scan(APP);
	assert.deepEqual(bad, []);
	// remote hosts in the editor bundle may only appear as text/links, never as script or fetch targets
	const bundle = fs.readFileSync(path.join(APP, "beepbox_editor.min.js"), "utf8");
	assert.ok(!/serviceWorker|cdn\.jsdelivr|tinyurl|googleapis/.test(bundle), "patched bundle still references a remote service");
});

test("tmp output dir is writable (sanity for the Python wrapper)", () => {
	fs.mkdtempSync(path.join(os.tmpdir(), "box-")); assert.ok(true);
});
