---
name: operate-desktop
description: Operate the AltStack Desktop desktop - open and close apps, arrange windows, switch virtual desktops, use the launcher, the Caster, the home view and the top bar. Use when the user asks to open, find, move, tile, minimize, close or switch things, or to change how the bar looks.
---

# Operate the desktop

Core idea: **list, choose by id, act, list again.** Ids are strings from the list tools and are not stable across restarts of an app.

## Apps
1. `amerika.apps.list {query: "files"}` returns `{id, name, description}`. Use the `id` exactly.
2. `amerika.apps.launch {id}`. Then `amerika.windows.list` to confirm a window appeared (a launch can take seconds; retry the list once after a moment, do not launch twice).
3. To close an app: `amerika.apps.close {id}` (sensitive, closes all its windows) or `amerika.windows.close {id}` for one window. Unsaved work is lost: ask the user first if the window might hold any (editors, documents, terminals with a running job).

## Windows
`amerika.windows.list` gives `id, caption, cls, x, y, w, h, active, minimized, fullscreen, desktops`, plus `screens`.
- Focus/raise: `amerika.windows.focus`. Hide: `amerika.windows.minimize`. Size: `amerika.windows.maximize`, `amerika.windows.restore`, `amerika.windows.fullscreen {id, on}`.
- Halves: `amerika.windows.tile {id, side: left|right|top|bottom}`.
- Exact geometry: `amerika.windows.move_resize {id, x, y, w, h}` in pixels; keep inside `screens`.
- Unsure which window the user means: match on `caption`/`cls`; if two match, ask.

## Virtual desktops
`amerika.desktops.list` (current + all), `amerika.desktops.switch {desktop}`, `amerika.windows.to_desktop {id, desktop}`. Numbers start at 1.

## Launcher, home, Caster, desktop style
- `amerika.shell.show_launcher` toggles the all-apps menu (Windows key).
- `amerika.ui.home` returns to the home view (the home AI app, maximized under the bar). Needs `home_mode` claude or chatgpt; read `amerika.bar.get` to see it.
- `amerika.ui.caster {op}`: toggle (default), next, prev, close. The user picks with keys; you can cycle with next/prev and close it.
- `amerika.ui.mode {mode}` switches the whole style: `claude`/`chatgpt` (home app, no dock, Caster on the Copilot key, home bar) or `off` (Classic); `revert` restores what the user had before. Sensitive: it rearranges the desktop, so say what changes and ask.
- Text size of the AI apps: `amerika.ui.text_scale {app, scale 0.8-2.0}` applies at the next start; `amerika.ui.relaunch {app}` restarts that app now and closes the chat you are in, so only after the user agrees.
- `amerika.ui.home`/`caster`/`relaunch` need a recent shell; on "does not support the ... action" tell the user to update `amerika-desktop-shell`.
- Dock: `amerika.settings.set {key: "dock_enabled", value: true|false}`. Home mode: key `home_mode` (claude, chatgpt, off). Copilot key: `copilot_app`.

## Top bar
1. `amerika.bar.get` returns `bar_layout` (null = classic), `bar_preset`, `bar_clock_format`, `bar_height`, `bar_opacity`, `home_mode`, `dock_enabled`, `copilot_app`, `ai_text_scale`.
2. `amerika.bar.set` takes any of: `preset` (classic|home), `layout` (widgets `launcher, home, ai_apps, title, pager, clock, date, ai_chip, agent_chip, status, tray, bell`; each `{id, enabled, zone left|center|right, order}`), `clock_format` (`hour24` true/false/null, `seconds`, `date` none|short|long|numeric), `height` 28-64, `opacity` 0.3-1.
3. Read `amerika.bar.get` again and tell the user what changed. Undo = send back the old values you read in step 1 (or `preset`).

## Examples
- "Open Files and put it next to the terminal": `apps.list` -> `apps.launch` -> `windows.list` -> `windows.tile left/right` -> `windows.list`.
- "Clear my screen": minimize non-essential windows one by one; list them first and tell the user which. Do not close anything.
- "Show seconds in the clock": `bar.get` -> `bar.set {clock_format: {seconds: true}}` -> `bar.get`.

## Failure handling
- "no such window (see windows.list)": the window went away; re-list.
- "unknown application id": run `apps.list` with a query; ask if several match.
- Nothing changed after an act call: the window may belong to an app that ignores the request (fullscreen games). Say so.
