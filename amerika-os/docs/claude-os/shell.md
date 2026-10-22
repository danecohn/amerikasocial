# Claude-first shell (home mode, Caster, top bar, app menu)

This is the shell side of the Claude-first concept in `docs/CLAUDE-OS.md`. Everything here is **opt-in and reversible**: a fresh
or existing install keeps today's desktop (dock shown, no home app) until the user presses "Switch to Claude-first mode" in
Settings. The Claude and ChatGPT desktop apps are proprietary Electron apps; Amerika places, sizes, launches and supervises them
and surrounds them with its own shell. It does not modify them and cannot change their internal UI.

## What was built

| Piece | Where |
|---|---|
| Home mode, mode presets, snapshot/revert, supervisor | `src/os/amerika/shell/home.py` (pure logic) and `shell/app.py` (wiring) |
| Window rules (maximized, borderless, never minimized, Win+H) | `src/os/amerika/bridge/bridge.js` (KWin script) |
| Caster (Copilot key overlay) | `shell/caster.py` |
| Top bar layout engine and live rebuild | `shell/barlayout.py`, `shell/bar.py` |
| App menu (Windows key) | `shell/launcher.py` |
| Launch command builder, text size flag | `shell/apps.py` |
| Settings pages "Home & Caster" and "Top bar" | `settings/page_home.py`, `settings/page_topbar.py` |
| Login-time launch | `src/os/session/session-start` |
| Tests | `tests/test_claude_os.py`, `tests/rig/claude_os_*` |

## Settings keys (`~/.config/amerika-os/settings.json`)

| Key | Default | Meaning |
|---|---|---|
| `home_mode` | `off` | `claude`, `chatgpt` or `off`. Which AI app is the home view. `off` disables every window rule and the supervisor. |
| `dock_enabled` | `true` | `false`: the dock window is not created at all. `dock_pinned` is never touched, so turning it back on restores the same dock, live. |
| `copilot_app` | `claude` | What the Copilot key opens: `caster` (the chooser), `claude`, `chatgpt`, `agent`, `ask`. Claude-first mode sets `caster`. |
| `bar_layout` | `null` (classic) | List of `{id, enabled, zone: left/center/right, order}`. Widgets: `launcher, home, ai_apps, title, pager, clock, date, ai_chip, agent_chip, status, tray, bell`. |
| `bar_preset` | `classic` | `classic`, `home` or `custom` (informational). |
| `bar_clock_format` | `{hour24: null, seconds: false, date: short}` | `hour24: null` follows the older `clock_24h`. `date`: `none`, `short`, `long`, `numeric`. |
| `bar_height` | `36` | Pixels, 28 to 64. |
| `bar_opacity` | `1.0` | 0.3 to 1.0. |
| `ai_text_scale` | `{chatgpt: 1.25, claude: 1.0}` | 0.8 to 2.0, passed to the app as `--force-device-scale-factor` when Amerika launches it. |
| `home_classes` | none | Optional `{chatgpt: ["extra-class"]}`: extra window classes the home rules should treat as that app. |
| `caster_last`, `app_last_used`, `recent_apps` | | State the Caster and the app menu remember. |
| `claude_os_prompt` | `pending` after migration | `pending`, `dismissed` or `answered`: whether the one-time opt-in card has been answered. |
| `claude_first_snapshot` | absent | The values of `home_mode, dock_enabled, copilot_app, bar_layout, bar_preset` before the switch, used by Revert. |

The settings API (`org.amerika.SettingsControl`, MCP `settings` tools) accepts `home_mode`, `dock_enabled`, `bar_height` and the extended `copilot_app`.

## Home mode

* Session start: `session-start` waits for the shell's `shell-ready` file and then sends the Control action `home-start`; this is repeated
  after every shell restart. With `home_mode=off` the shell ignores it.
* Supervision (`HomeSupervisor`, in the shell): a window of the home app must exist. If it does not appear within 30 s of a launch, or
  disappears, the app is launched again after 2, 4, 8, 16, 30, 60 s (a run that stays up 60 s resets the delay). After 8 launches in a row
  that never produce a window it gives up and shows a notification (Win+H starts it again). It stops when the mode changes or the shell exits.
* Window rules (bridge.js): windows whose class (or desktop file name) is in the active home app's list are set borderless
  (`noBorder`) and maximized into the work area, i.e. below the top bar and, with the dock off, down to the screen edge. They are
  re-applied on first map, re-map, class change and geometry change; they are never minimized (Win+M, Win+Down, Win+D and the
  Overview skip them, and an un-minimize is forced). Other windows open above the home window normally and keep their frame. A
  deliberate fullscreen (F11 in the app) is left alone.
* Only the active home app's classes are matched: `com.anthropic.claude`/`claude` for Claude, `chatgpt`/`codex`/`openai-codex-electron`
  for ChatGPT (see limits below). `home_mode=off` sends `enabled: false`; the bridge then does nothing.
* Restore: when the home app changes or the mode goes to `off`, the bridge gives the former home window its title bar back
  (`release` list in the pushed config). Its size is left as it is.
* Win+H, the **Home** button of the bar, the Home entry of the app menu, and the Control action `home` bring the home window forward
  (launching it when it is not running).

## Caster

The Copilot key (KWin shortcut `Meta+Shift+F23`, action `copilot`) opens the Caster when `copilot_app=caster`: a full-screen layer-shell overlay with two cards (Claude, ChatGPT) showing the
app's own icon from its desktop entry, name, running / not running, last used, and whether it is the home app.

| Key | Action |
|---|---|
| Left / Right / Tab / Shift+Tab | move focus (wraps) |
| Enter / Space | open or raise the focused app (launches it when it is not running) |
| 1 / 2 | quick pick |
| Copilot key again | focus the other card |
| Esc, click outside | close |
| click / tap a card | choose it |

The overlay opens focused on the last choice, fades and scales in, and the focused card glows. Choosing an app records it, and when
home mode is on it becomes the home app (`home_mode` changes, the old window gets its frame back, the new one is raised). In Classic mode it only opens or raises the app.
The Control actions `caster`, `caster:next`, `caster:prev`, `caster:close` drive it from scripts and tests.

## Top bar

Settings > Top bar lists every widget with an on/off switch, a zone (left, centre, right) and Up/Down buttons, plus time format (12/24 h),
seconds, date style, height, opacity, a live preview of the bar, "Reset to default" and "Use the Home layout". The shell watches
`settings.json` and re-arranges the live bar; the rebuild is skipped when nothing the bar shows changed and deferred while a popover or tray menu is open,
so an open menu is never destroyed. The Stop button and the recording indicator always stay on the right. A date and a clock that are neighbours share one button.
The default `classic` layout is the bar as it was; the `home` preset adds the Home button, shows the clock centred, and hides the AI buttons and pager.

## App menu (Windows key)

Win (tap) and Win+Space open the launcher: search, category chips (Internet, Office, Media, Games, Develop, System, Utilities, Other),
an alphabetical app grid, a Recent strip, an "Ask Claude / Ask ChatGPT" row ordered by `home_mode` (typing and pressing the button copies the question to the clipboard and
brings the app forward), and a footer with Home (when home mode is on), Settings, Lock and Power. Typing anywhere starts a search, Down moves into the grid,
arrow keys move between apps, Enter opens the first match, Esc clears the search and then closes.

## Text size

`ai_text_scale` is applied by `apps.launch()`: the `.desktop` `Exec` line is parsed, field codes (`%U`, `%f`, ...) are removed, URIs are appended and
`--force-device-scale-factor=<scale>` is inserted after the program (an existing copy of the flag is replaced). The child is started with a
sanitised environment (the shell's `LD_PRELOAD` for layer-shell is removed). A scale of exactly 1.0 adds no flag. Desktop actions (New chat, ...) use the original GIO launch path unchanged.
Settings > Home & Caster has a slider per app with a live sample; Apply asks first because the app has to restart (the shell sends SIGTERM to the exact PIDs of that app's windows only, then launches it again).

## Switching modes and reverting

Settings > Home & Caster:
* **Claude first / ChatGPT first**: sets `home_mode`, `dock_enabled=false`, `copilot_app=caster`, bar layout preset `home`, and first stores a snapshot of the previous values.
* **Classic desktop**: `home_mode=off`, dock on, Copilot key = Claude, classic bar.
* **Revert to previous settings** (visible while a snapshot exists): restores exactly the previous values (keys that did not exist are removed again).
* The one-time card "Switch to Claude-first mode" appears on this page and on AI & Assistants until it is answered.

Deep links and actions: `amerika-settings home` (also `caster`), `amerika-settings topbar` (also `bar`); Control D-Bus actions `home`, `home-start`, `caster`, `caster:next|prev|close`, `relaunch:claude|chatgpt`
(`gdbus call --session --dest org.amerika.Shell --object-path /Control --method org.amerika.Control.Action home`).

## Recovery

* In the session: Settings > Home & Caster > "Classic desktop" (or Revert). Win+Space always opens the app menu; Win+Q closes the active window.
* If the screen is unusable: press Ctrl+Alt+F3, log in on the text console and run `amerika-settings --classic` (needs no display). It sets
  `home_mode=off`, the dock on, the Copilot key to Claude and the classic bar; then log out and in (or Ctrl+Alt+F1/F2 to go back). By hand: edit
  `~/.config/amerika-os/settings.json` and set `"home_mode": "off"` and `"dock_enabled": true`.
* The Plasma and other sessions are untouched; choose them on the login screen at any time.

## What is verified and what is not

Verified in the private KWin rig (`tests/rig/claude_os_rig.sh "sh tests/rig/claude_os_test.sh"`, fake `claude-desktop` and `chatgpt` apps with the right window classes):
home window maximized, borderless and below the bar; supervised relaunch; other windows above it; Win+H action; Caster open, move, cycle, choose; dock not created and brought back live;
bar layout, height and clock changes live without rebuilding for unrelated settings; scale flag and a clean environment in the launched command; home mode off restores the frame and stops supervising.
Screenshots: `dist/claude-os/`.

Not verified here:
* The real Claude and ChatGPT apps under these window rules. Electron on Wayland might ignore `noBorder`, resize itself after a rule, or hide to the tray on close (then Win+H raises it and the supervisor relaunches an app that has no window).
* ChatGPT's real Wayland app_id. Its `.desktop` file has no `StartupWMClass` and its `package.json` has no `desktopName` (name `openai-codex-electron`, product `Codex`), so the class is one of `ChatGPT`, `codex`, `openai-codex-electron`; if it is something else, add it under `home_classes` in settings.json.
* Whether the apps honour `--force-device-scale-factor` (Chromium does; an app that sets its own zoom or drops unknown flags will not change). The Settings page says so; the apps are not patched.
* The physical Copilot key (the shortcut is `Meta+Shift+F23` and is checked only as a registered binding) and the Surface Laptop 7 hardware.
