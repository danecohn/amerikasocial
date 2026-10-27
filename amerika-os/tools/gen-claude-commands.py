"""Generates src/os/claude/plugin/amerika-os/commands/*.md from one spec (run from the repo root)."""
import re, sys, json
from pathlib import Path
sys.path.insert(0, 'src/os')
from types import SimpleNamespace
from amerika.ai.tools import Tools
reg = Tools(SimpleNamespace(settings={}))
OUT = Path('src/os/claude/plugin/amerika-os/commands')

G = {}  # group -> [(name, hint, desc)]
CMDS = []
def c(group, name, desc, hint, skill, body):
    CMDS.append(dict(group=group, name=name, desc=desc, hint=hint, skill=skill, body=body.strip()))

OV, OP, SS, FP, SU, DR, GD, HW, VN, SA, PS = ('amerika-os-overview','operate-desktop','system-settings','files-and-projects','software-and-updates',
    'diagnose-and-repair','game-dev-studio','hardware-surface-laptop-7','voice-and-notifications','schedule-and-automation','privacy-and-safety')

# ---- start
c('Start here','amerika','Index of every AltStack Desktop command, grouped, with what each one does','[topic]',OV,'''
Show the user the AltStack Desktop command index. Topic filter (may be empty): $ARGUMENTS
Read `commands.md` in the plugin folder if you can; otherwise list the groups below. Group the commands, one line each, and say they are invoked as `/amerika-os:<name>` (short names that clash with Claude Code built-ins such as /status or /logout need the prefix). If a topic was given, show only the matching group and then offer the most likely next command. Do not call any tool for this command except `amerika.system.status` to confirm the OS is connected.
''')
c('Start here','status','One-screen status of this computer: system, power, network, windows, hardware, services','',OV,'''
Report the state of this computer. Read-only. Call, in this order: `amerika.system.info`, `amerika.system.status`, `amerika.windows.list`, `amerika.units.status`, `amerika.bar.get`, `amerika.hw.report` (skip quietly if not installed), `amerika.agent.status`, `amerika.studio.status` (skip if not installed).
Summarise in under 15 lines: OS and uptime, home mode and dock, battery and power profile, network, volume and brightness, open windows (titles only), anything failing. Flag problems; fix nothing.
''')
# ---- hardware
c('Hardware','hw','Hardware report: CPU, memory, GPU/Vulkan, thermals, NPU, with advice','',HW,'''
Run `amerika.hw.report`. If it fails with "not installed", say the user needs the amerika-gamedev package and fall back to `amerika.system.status` and `amerika.system.info`. Summarise: CPU and governor, memory and swap/zram, Vulkan device and driver, GPU clocks, temperatures, NPU status (state plainly that the NPU cannot run anything or speed up games here), and the report's advice. Quote numbers exactly as read; write "unknown" where the report has no value.
''')
c('Hardware','perf','Switch the performance mode: game or balanced (asks for administrator approval)','game | balanced',HW,'''
Requested mode: $ARGUMENTS (must be exactly `game` or `balanced`; otherwise ask which).
1. Read `amerika.hw.report` (clocks, temperatures) and `amerika.system.status` (power profile, battery) for the "before" picture.
2. Tell the user in two sentences what the mode does (game pins CPU and GPU clocks high until reboot, costs battery and heat; balanced restores) and that an administrator dialog will appear. Wait for a yes.
3. Call `amerika.hw.perf {mode}` (critical: it asks every time). For game also offer `amerika.power.set_profile {profile: "performance"}` and do it only if they say yes.
4. Verify with `amerika.hw.report` again and report the before and after clocks you actually read. If the dialog was cancelled, say the mode is unchanged.
''')
c('Hardware','bench','Explain and prepare a GPU benchmark (it runs in your terminal)','',HW,'''
`amerika-hw bench` (vkmark/glmark2) takes longer than the 30 s limit of the shell tool and needs the desktop, so you do not run it. Read `amerika.hw.report` to check the benchmark tools are installed, then give the user the exact command to run in a terminal, tell them to plug in power and close heavy windows first, and offer to read `amerika.hw.report` afterwards to compare temperatures. Do not invent scores.
''')
c('Hardware','tune','Explain the opt-in system tuning (zram, file-watch limits, shader cache) and how to undo it','apply | revert',HW,'''
Argument: $ARGUMENTS. `amerika-hw tune apply|revert` changes system settings and needs the user at a terminal with an administrator prompt, so you do not run it. Read `amerika.hw.report` (memory, swap, advice) and explain in plain words what apply would change and why it may help this machine, then give the exact command (`amerika-hw tune apply` or `amerika-hw tune revert`). Make clear that revert undoes everything. After they run it, verify with `amerika.hw.report`.
''')
# ---- home
c('Home and AI apps','home','Go to the home view (the home AI app)','',OP,'''
Call `amerika.ui.home`. If it reports the action is unsupported, tell the user to update amerika-desktop-shell. If `amerika.bar.get` shows `home_mode` off, say Classic desktop has no home app and offer `/amerika-os:claude-mode`. Verify with `amerika.windows.list` that the home app window is active and report what you see.
''')
c('Home and AI apps','caster','Open, close or cycle the Caster (Claude / ChatGPT switcher)','[next | prev | close]',OP,'''
Argument: $ARGUMENTS. Map it to `amerika.ui.caster {op}`: empty means toggle; next, prev and close as given. The user chooses a card with the keyboard; you cannot press Enter for them. Report what you did and that the Caster is an on-screen overlay you cannot see (use `amerika.screenshot.take` only if the user allows it).
''')
c('Home and AI apps','chatgpt','Make ChatGPT the home AI app, or just open it','[open]',OP,'''
Argument: $ARGUMENTS. Read `amerika.bar.get` for `home_mode`. If the user said "open", or `home_mode` is off, use `amerika.apps.list {query: "chatgpt"}` then `amerika.apps.launch` with the exact id (if none is installed, say so). Otherwise set `amerika.settings.set {key: "home_mode", value: "chatgpt"}` after telling the user that Claude stops being the home view, and how to switch back (`/amerika-os:claude-mode`). Verify with `amerika.bar.get` and `amerika.windows.list`.
''')
# ---- windows
c('Windows and apps','windows','List open windows, grouped by desktop, with size and state','[filter]',OP,'''
Call `amerika.windows.list` and `amerika.desktops.list`. Filter (optional): $ARGUMENTS. Show a compact table: id, title, app, desktop, state (active, minimized, fullscreen), size. Do not change anything.
''')
c('Windows and apps','raise','Bring a window to the front by name','window name',OP,'''
Window wanted: $ARGUMENTS. `amerika.windows.list`, match on title or app (ask if several match), then `amerika.windows.focus {id}`. Verify with `amerika.windows.list` that it is active and not minimized (use `amerika.windows.restore` first if it is minimized).
''')
c('Windows and apps','tile','Snap a window left, right, top, bottom or maximize it','window left | right | top | bottom | max',OP,'''
Request: $ARGUMENTS (a window name followed by a side, or `max`). If no window is named use the active one from `amerika.windows.list`. Use `amerika.windows.tile {id, side}` for left, right, top, bottom, or `amerika.windows.maximize {id}` for max. Verify with `amerika.windows.list` (position and size) and report the actual geometry.
''')
c('Windows and apps','close','Close a window (asks first if it may hold unsaved work)','window name',OP,'''
Window to close: $ARGUMENTS. List with `amerika.windows.list`, identify exactly one window (ask if unsure). Closing can lose unsaved work: tell the user which window, and confirm unless it is clearly harmless. Then `amerika.windows.close {id}`. Verify it is gone with `amerika.windows.list`. Offer `amerika.windows.minimize` as the safer option.
''')
c('Windows and apps','move-desktop','Move a window to another virtual desktop (and optionally switch)','window desktop-number',OP,'''
Request: $ARGUMENTS (window name, desktop number). `amerika.desktops.list` for the valid numbers, `amerika.windows.list` to find the window, then `amerika.windows.to_desktop {id, desktop}`. Switch there with `amerika.desktops.switch {desktop}` only if the user asked. Verify with `amerika.windows.list` (desktops field).
''')
c('Windows and apps','open','Open an application by name','app name',OP,'''
Application wanted: $ARGUMENTS. `amerika.apps.list {query}`; if there is one clear match, `amerika.apps.launch {id}` with the exact id; if several, ask; if none, say so (do not install anything; offer `/amerika-os:install`). Wait a moment, then verify with `amerika.windows.list` that a window appeared and say if it did not.
''')
c('Windows and apps','apps','Search the installed applications','[search]',OP,'''
Search: $ARGUMENTS (empty = everything, show at most 40 sorted by name). `amerika.apps.list {query}`. Show name and id, one line each. Change nothing.
''')
c('Windows and apps','quit','Close all windows of an application','app name',OP,'''
Application to close: $ARGUMENTS. Find it with `amerika.windows.list` and `amerika.apps.list {query}`. Warn that unsaved work may be lost, list the windows that would close, and wait for a yes (never close the Claude app this chat runs in without explicit confirmation). Then `amerika.apps.close {id}`. Verify with `amerika.windows.list`.
''')
# ---- desktop & bar
c('Desktop and top bar','bar','Show or change the top bar (widgets, preset, height, opacity)','show | preset classic|home | height N | opacity N | hide WIDGET | show WIDGET',OP,'''
Request: $ARGUMENTS. Always start with `amerika.bar.get` and remember the old values. Empty or "show": describe the layout in words (widgets by zone, enabled or not, height, opacity). Otherwise apply with `amerika.bar.set`: `preset` (classic|home), `height` (28-64), `opacity` (0.3-1), or `layout` (send the full widget list with the one widget's `enabled` or `zone` changed; ids: launcher, home, ai_apps, title, pager, clock, date, ai_chip, agent_chip, status, tray, bell). Verify with `amerika.bar.get`, report old and new values, and say how to undo.
''')
c('Desktop and top bar','clock','Clock format: 12/24 hour, seconds, date style','12h | 24h | seconds on|off | date none|short|long|numeric',OP,'''
Request: $ARGUMENTS. `amerika.bar.get` first (see `bar_clock_format`). Then `amerika.bar.set {clock_format: {...}}` with only what changes: `hour24` true/false for 24h/12h, `seconds` true/false, `date` none|short|long|numeric. Verify with `amerika.bar.get`; tell the user what the bar should now show.
''')
c('Desktop and top bar','theme','Change the accent and secondary colours','colour or name, optional second colour',SS,'''
Request: $ARGUMENTS. Turn names into `#rrggbb` (propose the value and show it before applying if the wish is vague). `amerika.settings.get` first to record the old accent and secondary. Then `amerika.settings.set {key: "accent", value}` and/or `{key: "secondary", value}`. Verify with `amerika.settings.get` and give the old values for undo.
''')
c('Desktop and top bar','wallpaper','Change the wallpaper: horizon, grid or dusk','horizon | grid | dusk',SS,'''
Wanted: $ARGUMENTS. Only horizon, grid and dusk are available through tools (for a picture file, open `amerika.ui.settings {page: "appearance"}`). Read `amerika.settings.get`, then `amerika.settings.set {key: "wallpaper", value}`, verify, mention the old value.
''')
c('Desktop and top bar','dock','Show or hide the dock','on | off',SS,'''
Argument: $ARGUMENTS (on or off; ask if missing). Read `amerika.settings.get` (`dock_enabled`). Set `amerika.settings.set {key: "dock_enabled", value: true|false}`. The dock's pinned apps are never touched, so turning it back on restores the same dock. Verify with `amerika.bar.get` and say what the user should see.
''')
c('Desktop and top bar','text-size','Text size of the Claude or ChatGPT app (0.8 to 2.0)','claude|chatgpt scale',SS,'''
Request: $ARGUMENTS (app and a scale such as 1.25). `amerika.bar.get` shows the current `ai_text_scale`. Set it with `amerika.ui.text_scale {app, scale}`; it applies at the app's next start. Restarting now closes the app and the chat you are in: explain that and call `amerika.ui.relaunch {app}` only if the user clearly says yes. Verify with `amerika.bar.get`. Note that an app which ignores the Chromium scale flag will not change.
''')
c('Settings','settings','Open a Settings page or read a setting','page name | key',SS,'''
Request: $ARGUMENTS. If it names a page (network, bluetooth, sharing, display, sound, input, shortcuts, printers, power, appearance, notifications, accessibility, language, datetime, defaults, users, privacy, updates, storage, login, about, ai, agent, studio, home, topbar), call `amerika.ui.settings {page}` and tell the user what to look for there. If it names a setting, read it with `amerika.settings.get` or `amerika.bar.get`. With no argument, list the pages in one line each. Never write settings here.
''')
c('Settings','volume','Set, raise, lower or mute the volume','0-150 | up | down | mute | unmute',VN,'''
Request: $ARGUMENTS. Read `amerika.system.status` for the current volume. up/down means a step of 10. Set with `amerika.audio.set_volume {percent}` (ask before going above 100), or `amerika.audio.set_mute {muted}`. Verify with `amerika.system.status` and report the value you read.
''')
c('Settings','brightness','Set the screen brightness','1-100 | up | down',SS,'''
Request: $ARGUMENTS. Read `amerika.system.status`. up/down means a step of 10. `amerika.display.set_brightness {percent}` (1-100). Verify with `amerika.system.status` and report what you read.
''')
c('Settings','wifi','Turn Wi-Fi on or off','on | off',SS,'''
Argument: $ARGUMENTS. Read `amerika.system.status` (network). Turning Wi-Fi off can cut the connection this chat uses: warn and confirm first. Then `amerika.network.set_wifi {on}`. Verify with `amerika.system.status`.
''')
c('Settings','bluetooth','Open Bluetooth settings (pairing is done by the user)','',SS,'''
There is no tool that pairs or lists Bluetooth devices. Open the page with `amerika.ui.settings {page: "bluetooth"}` and tell the user the steps: switch Bluetooth on, put the device in pairing mode, pick it in the list. Do not claim anything about device state.
''')
c('Settings','dnd','Do Not Disturb on or off','on | off',VN,'''
Argument: $ARGUMENTS. `amerika.notifications.set_dnd {on}` (it returns the new state). Verify by reporting the returned state. Say that alarms and calls are hidden while it is on, and how to turn it off (`/amerika-os:dnd off`).
''')
c('Settings','night','Open the night light and colour settings','',SS,'''
Night light lives on the Displays page and has no tool. Open it with `amerika.ui.settings {page: "display"}` and tell the user to enable Night light and pick the schedule. Brightness can be set directly (`amerika.display.set_brightness`) if they ask. Do not claim it is on.
''')
c('Settings','power-profile','Set the power profile: power-saver, balanced or performance','power-saver | balanced | performance',HW,'''
Request: $ARGUMENTS. Read `amerika.system.status` (profile, battery). `performance` costs battery and heat, `power-saver` slows builds: say which in one sentence. Then `amerika.power.set_profile {profile}` and verify with `amerika.system.status`.
''')
# ---- files
c('Files','files','List a folder in your home directory','path (default ~)',FP,'''
Folder: $ARGUMENTS (default home). `amerika.files.list {path}`. Show folders first, sizes in readable units, at most 60 entries; say if the list was cut. Home folder only; protected places show names but cannot be read.
''')
c('Files','find','Find files by name in your home directory','name or part of it',FP,'''
Looking for: $ARGUMENTS. Walk likely folders with `amerika.files.list` (home, Documents, Downloads, Projects, Desktop), one level at a time, matching names case-insensitively. Do not read file contents to search. For a deep search offer one read-only `amerika.shell.run` such as `find ~ -iname '*NAME*' -not -path '*/.*' 2>/dev/null | head -50` (the user approves it). Report paths and say honestly when nothing matched.
''')
c('Files','recent','Show recently changed files in your home directory','[days, default 2]',FP,'''
Days: $ARGUMENTS (default 2). There is no tool with modification times, so propose one `amerika.shell.run` command and wait for approval: `find ~ -type f -mtime -N -not -path '*/.*' -printf '%TY-%Tm-%Td %TH:%TM %p\\n' 2>/dev/null | sort -r | head -40`. Show the result as given.
''')
c('Files','tidy','Propose how to organise a folder (nothing is moved or deleted without your approval)','folder',FP,'''
Folder: $ARGUMENTS. Step 1, look only: `amerika.files.list {path}`. Step 2, propose a plan: which files go into which new subfolders, as a table, with counts. Step 3, STOP and wait for the user to approve the plan. Never delete in this command; deletion is a separate request and goes through `amerika.files.delete` (trash) one path at a time. After approval, move files in small batches (each move is one approved `amerika.shell.run` such as `mv -n`), and verify with `amerika.files.list` that source and destination match the plan.
''')
c('Files','clip','Read or set the clipboard','show | set TEXT',PS,'''
Request: $ARGUMENTS. The clipboard may contain passwords: before `amerika.clipboard.get`, tell the user you are about to read it and why. Show it, but if it looks like a secret, say so without printing it. `set TEXT` uses `amerika.clipboard.set {text}` for exactly the text given; verify by saying what you set (reading it back needs the same permission).
''')
c('Files','shot','Take a screenshot of the screen or the active window','screen | window',PS,'''
Argument: $ARGUMENTS (default window; use screen only if needed). The screen may show private data: say what you are about to capture, then `amerika.screenshot.take {target}`. You get a file path and size, not pixels; report them and that the file is in Amerika's private folder. Do not forward it anywhere.
''')
c('Notifications','notify','Show a desktop notification','title | body',VN,'''
Text: $ARGUMENTS (split at the first "|" into title and body). `amerika.notifications.send {title, body}`. Keep it short. Verify with `amerika.notifications.list {limit: 3}` and report what you see.
''')
c('Notifications','remind','Remind me later with a notification','when what  (for example: 20m stand up)',SA,'''
Request: $ARGUMENTS (a time such as 20m, 2h or 2026-10-22 09:00, then the text). Compute the exact moment and repeat it back. Ask for approval of this one command, then run it with `amerika.shell.run`: `systemd-run --user --unit=amerika-reminder-SLUG --on-active=20m notify-send "Reminder" "TEXT"` (use `--on-calendar="YYYY-MM-DD HH:MM"` for a clock time; quote safely, no shell metacharacters from the user text). Verify with `amerika.shell.run` `systemctl --user list-timers --no-pager` and say when it will fire. Tell the user it vanishes on reboot.
''')
# ---- software
c('Software','install','Install software (you approve the administrator prompt)','package or app name',SU,'''
Wanted: $ARGUMENTS. You cannot install anything yourself. Check where it comes from with `amerika.shell.run` (approved): `apt-cache policy NAME`. For an Amerika package open `amerika.apps.launch {id: "amerika-software"}` and give the steps (search, Install, approve the polkit dialog). For an Ubuntu package give the exact terminal command `sudo apt install NAME`. Never run sudo, pkexec or apt install, never add repositories. After the user says it is done, verify with `dpkg -l NAME` and report the version read.
''')
c('Software','update','Check for updates and guide the upgrade','check | amerika',SU,'''
Argument: $ARGUMENTS. Read-only first: `amerika.shell.run` `apt list --upgradable 2>/dev/null` and `dpkg -l 'amerika-*'` (the user approves each), plus `amerika-channel status`. Summarise what could be updated (Amerika vs Ubuntu, security first). For the upgrade itself, open `amerika.ui.settings {page: "updates"}` (or Amerika Software for Amerika packages) and let the user press refresh/upgrade and approve the dialog. Warn about reboot-required and kernel updates. Never run dist-upgrade or apt remove.
''')
c('Software','uninstall','Remove software (you approve; asks every time)','package or app name',SU,'''
Target: $ARGUMENTS. Find the installed package and what depends on it with `amerika.shell.run` (approved, read-only): `dpkg -l NAME` and `apt-cache rdepends --installed NAME`. Explain what will go and what data stays. Never remove amerika-* core packages (the shell, session, repo keyring) yourself or advise it without a warning. The removal is done by the user: Amerika Software for Amerika packages, otherwise `sudo apt remove NAME` in a terminal. Verify afterwards with `dpkg -l NAME`.
''')
# ---- diagnose
c('Diagnose and repair','journal','Read recent errors from the user journal (secrets are redacted)','[unit] [since]',DR,'''
Request: $ARGUMENTS. `amerika.journal.read {lines: 100, priority: "err"}` and add `unit` (a user unit name) and `since` (such as "1 hour ago") if given. Summarise the distinct problems with their time and unit, newest first; do not paste long logs. If you still see something that looks like a key or token, do not repeat it.
''')
c('Diagnose and repair','fix','Diagnose a symptom and fix it with the smallest safe step','what is wrong',DR,'''
Symptom: $ARGUMENTS. Observe with read tools only (`amerika.system.status`, `amerika.journal.read`, `amerika.units.status`, `amerika.hw.report`, `amerika.windows.list`, `amerika.notifications.list`). State the most likely cause with the evidence (time, unit, value). Propose the smallest reversible fix and wait for the user's yes before any change; allowed fixes are the dedicated tools (`amerika.units.restart` for amerika-* services, `amerika.windows.restore`, `amerika.audio.set_mute`, `amerika.network.set_wifi`, `amerika.power.set_profile`). After the fix repeat the observation that showed the problem and report before and after. If it is not fixed, say so and stop after two attempts.
''')
c('Diagnose and repair','restart-shell','What to do when the bar or shell is frozen (tools cannot restart it)','',DR,'''
You cannot restart the Amerika shell (restarting it would cut your own connection, and `amerika.units.restart` refuses it on purpose). Check with `amerika.system.status` and `amerika.units.status` whether the shell answers. If it answers, say so and suggest `/amerika-os:fix` for the actual symptom. If it does not, give the user these steps: Win+Space (app menu) and Win+Q (close the active window); Settings > Home & Caster > Classic desktop; log out and in; if the screen is unusable, Ctrl+Alt+F3 and `amerika-settings --classic` (see `/amerika-os:recover`). Do not promise any of it was tested on the real laptop.
''')
c('Diagnose and repair','recover','Recovery steps for a broken session, home mode, login or boot screen','',DR,'''
Read-only first: `amerika.system.status`, `amerika.units.status`, `amerika.journal.read {priority: "err", lines: 60}`, and `amerika.bar.get` (home_mode, dock_enabled). Then give the user the documented recovery path that matches, in this order of gentleness:
1. In the session: Settings > Home & Caster > Classic desktop (or Revert). Win+Space opens the app menu; Win+Q closes the active window. (`/amerika-os:classic-mode` does the Classic switch for them if tools still work.)
2. Screen unusable: Ctrl+Alt+F3, log in on the text console, run `amerika-settings --classic` (sets home_mode off, dock on, Copilot key to Claude, classic bar), then log out and in. By hand: in `~/.config/amerika-os/settings.json` set `"home_mode": "off"` and `"dock_enabled": true`.
3. Broken Amerika session or themes: from the console, `amerika-agent disable --now`; `amerika-login disable` and/or `amerika-boot disable` if those themes were enabled; choose the fallback (Plasma) desktop at the login screen.
4. Hardware tuning: `amerika-hw tune revert`, `amerika-hw perf balanced`.
Say clearly that lock screen, suspend/resume and these recovery paths are not fully tested on the real laptop. Save logs locally and review them before sharing.
''')
# ---- session
c('Session and power','lock','Lock the screen','',PS,'''
Call `amerika.power.lock` and report that you requested it. Note that the lock screen is not yet an independently reviewed lock; do not call it a security guarantee. You cannot verify it from here, so do not say it is locked beyond "requested".
''')
c('Session and power','sleep','Suspend the computer (always confirm)','',PS,'''
Confirm first: suspending ends this session's activity and any running tasks pause. After a clear yes, call `amerika.power.suspend` (critical, the shell asks again). Say that suspend/resume is not fully tested on this laptop.
''')
c('Session and power','logout','Log out of the Amerika session (always confirm)','',PS,'''
Logging out closes every app including this chat. Ask the user to save work, wait for a clear yes, then run with `amerika.shell.run` (critical, approved each time): `loginctl terminate-session "$XDG_SESSION_ID"`. Do not claim success afterwards; the connection ends.
''')
c('Session and power','reboot','Restart the computer (always confirm)','',PS,'''
Confirm first: all apps close; ask whether work is saved and whether updates need this (`/var/run/reboot-required`). After a clear yes call `amerika.power.reboot` (critical; the shell asks again). Nothing can be verified afterwards.
''')
c('Session and power','shutdown','Shut the computer down (always confirm)','',PS,'''
Confirm first: all apps close and the computer powers off; you cannot turn it on again. Ask whether work is saved. After a clear yes call `amerika.power.poweroff` (critical; the shell asks again).
''')
# ---- studio
c('Game and media studio','studio','Status of Amerika Studio and its four apps; open one','status | render | engine | sprite | box',GD,'''
Argument: $ARGUMENTS. `amerika.studio.status` (bridge, key present yes/no, budget, running apps). If Studio is not installed, say Amerika Developer Edition is needed (Amerika Software). If asked to open an app, call `studio_launch {app}` from the studio server and verify with `amerika.studio.status`. Never read or show keys.
''')
c('Game and media studio','render','Make or change a 3D model in Amerika Render (Blender)','description',GD,'''
Brief: $ARGUMENTS. Check `amerika.studio.status`, then `render_scene_info`. Create or change with `render_model_create_from_description` or `render_model_apply_change` (not `render_scene_run_python`, which is critical and needs approval of the exact code). Verify with `render_viewport_screenshot` and describe what is actually visible. Export with `render_export` only if asked.
''')
c('Game and media studio','engine','Build or change a game in Amerika Engine (Godot)','description',GD,'''
Brief: $ARGUMENTS. `amerika.studio.status`, `engine_project_info`. For a new game follow the recipe flow: `engine_recipe_get`, `engine_recipe_assemble`, `engine_recipe_validate`. For changes use `engine_scene_describe`, `engine_script_create`, `engine_script_edit`, `engine_node_add`. Verify by `engine_project_run`, `engine_project_logs` (errors first) and `engine_game_screenshot`; report what you saw. Offer `engine_history_undo` if it went wrong.
''')
c('Game and media studio','sprite','Draw or change pixel art in Amerika Sprite','description',GD,'''
Brief: $ARGUMENTS. `amerika.studio.status`, `sprite_canvas_info`, then `sprite_canvas_describe_to_sprite` or `sprite_canvas_apply_change`; frames with `sprite_frames_add`, `sprite_frames_set_duration`. Verify with `sprite_canvas_info` and report size, palette and frame count; export with `sprite_export` only if asked.
''')
c('Game and media studio','box','Compose or change chiptune music in AmerikaBox','description',GD,'''
Brief: $ARGUMENTS. `amerika.studio.status`, `box_song_get`, then `box_song_compose_from_description` or `box_song_apply_change`. Verify with `box_song_get` (tempo, key, instruments) and `box_play`; you cannot hear it, so say what the song data contains rather than how it sounds. `box_export_wav` only if asked.
''')
c('Game and media studio','game','Orchestrate a whole game: code, art, model and music from one idea','game idea',GD,'''
Idea: $ARGUMENTS. Plan first and show the user a short plan: genre/recipe, project name, and which of the four apps makes which asset; wait for a yes. Check `amerika.studio.status` (stop with instructions if Studio or its key is missing; mind the token budget). Then, in order: Engine skeleton (`engine_recipe_get`, `engine_recipe_assemble`, `engine_recipe_validate`); Sprite art (`sprite_canvas_describe_to_sprite`, `sprite_export`); Render model if 3D (`render_model_create_from_description`, `render_export`, then `engine_import_model`); Box music (`box_song_compose_from_description`, `box_export_wav`); wire up with `engine_script_create`/`engine_node_add`. Finish with `engine_project_run`, `engine_project_logs`, `engine_game_screenshot`. Report what runs and what does not, with evidence; list anything you skipped.
''')
# ---- modes
c('Modes','focus','Focus mode for a task: Do Not Disturb, quiet desktop, optional mute','task | off | mute',VN,'''
Request: $ARGUMENTS. Read `amerika.system.status` (note the volume) and `amerika.windows.list`. For a task: `amerika.notifications.set_dnd {on: true}`; mute with `amerika.audio.set_mute` only if "mute" was said; do NOT close or minimize windows unless asked. For `off`: DND off and unmute only if you muted. Verify with the returned DND state and `amerika.system.status`, then say exactly what is on and how to undo it. Optionally offer `amerika.notifications.send` as a reminder when the task is done.
''')
c('Modes','gamedev-mode','Game development mode: performance profile, quiet notifications, Studio ready','on | off',HW,'''
Argument: $ARGUMENTS. Read `amerika.system.status`, `amerika.hw.report` and `amerika.studio.status` for the "before". on: tell the user the plan (performance profile, DND, optionally hw.perf game with its administrator dialog, open the Amerika Studio hub) and wait for a yes; then `amerika.power.set_profile {profile: "performance"}`, `amerika.notifications.set_dnd {on: true}`, optionally `amerika.hw.perf {mode: "game"}`, and `amerika.apps.launch` for the Studio hub if installed. off: restore balanced (`amerika.power.set_profile`, `amerika.hw.perf {mode: "balanced"}` if game was set), DND off. Verify with `amerika.system.status` and `amerika.hw.report`; report what changed and the battery/heat cost.
''')
c('Modes','presentation-mode','Presentation mode: Do Not Disturb, no sleep surprises, clean bar','on | off',VN,'''
Argument: $ARGUMENTS. Read `amerika.system.status` and `amerika.bar.get` to remember brightness, volume and the bar. on: tell the user the plan, wait for a yes, then `amerika.notifications.set_dnd {on: true}`, `amerika.audio.set_mute {muted: true}` (only if they want silence) and optionally `amerika.bar.set {opacity: 1}`. Say that you cannot disable sleep or the lock screen from here. off: undo exactly what you did. Verify with the read tools and report.
''')
c('Modes','classic-mode','Switch to the Classic desktop (dock, no home app); reversible','revert',OP,'''
Argument: $ARGUMENTS. Read `amerika.bar.get` (home_mode, dock_enabled, copilot_app). Tell the user what changes (home app no longer enforced, dock back, Copilot key opens Claude, classic bar) and that `/amerika-os:claude-mode` or `revert` goes back. After a yes call `amerika.ui.mode {mode: "off"}` (or `{mode: "revert"}` if the argument is revert). Verify with `amerika.bar.get` and `amerika.windows.list`.
''')
c('Modes','claude-mode','Switch to Claude-first mode: Claude home view, Caster on the Copilot key, no dock','chatgpt',OP,'''
Argument: $ARGUMENTS (empty = Claude first; `chatgpt` = ChatGPT first). Read `amerika.bar.get`. Tell the user what changes (home app fills the screen under the bar, dock hidden, Copilot key opens the Caster, home bar layout) and how to undo (`/amerika-os:classic-mode`). After a yes call `amerika.ui.mode {mode: "claude"}` or `{mode: "chatgpt"}`. Verify with `amerika.bar.get` and `amerika.windows.list`. Note that the real apps' behaviour under the window rules has not been verified on the laptop.
''')
c('Modes','agent','Status of Amerika Agent and how to open it','',OV,'''
`amerika.agent.status` (installed, running, model, permission mode; never any key). If it is installed and not running, tell the user to start it in Settings > Agent (`amerika.ui.settings {page: "agent"}`); you cannot start it or message it. Report only what the status says.
''')

# ---------------------------------------------------------------- emit
known = set(reg.table)
for old in OUT.glob('*.md'):
    old.unlink()
order = []
for cmd in CMDS:
    refs = set(re.findall(r'(?<![\w./-])amerika\.([a-z_]+\.[a-z_]+)', cmd['body']))
    for r in refs:
        assert r in known, (cmd['name'], r)
    reads = sorted(r for r in refs if reg.risk(r) == 'read')
    allowed = ', '.join(f'mcp__amerika__{r.replace(".", "_")}, mcp__plugin_amerika-os_amerika__{r.replace(".", "_")}' for r in reads)
    fm = ['---', 'description: ' + json.dumps(cmd['desc'], ensure_ascii=False)]
    if cmd['hint']:
        fm.append('argument-hint: ' + json.dumps(cmd['hint'], ensure_ascii=False))
    if allowed:
        fm.append(f'allowed-tools: {allowed}')
    fm.append('---')
    foot = (f'\n\nRules: follow the {cmd["skill"]} skill. Verify the result with a read tool and report only what you verified. '
            'If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.')
    (OUT / f'{cmd["name"]}.md').write_text('\n'.join(fm) + '\n\n' + cmd['body'] + foot + '\n')
# the index
groups = {}
for cmd in CMDS:
    groups.setdefault(cmd['group'], []).append(cmd)
rows = []
for g, items in groups.items():
    rows.append(f'\n{g}:')
    for i in items:
        rows.append(f'  /amerika-os:{i["name"]}' + (f' {i["hint"]}' if i['hint'] else '') + f' - {i["desc"]}')
idx = OUT / 'amerika.md'
t = idx.read_text().replace('Read `commands.md` in the plugin folder if you can; otherwise list the groups below.', 'Use this list:\n' + '\n'.join(rows) + '\n')
idx.write_text(t)
# cheat sheet
md = ['# AltStack Desktop commands', '', 'Type these in Claude Code (plugin `amerika-os`) as `/amerika-os:<name>`; the short name works where it does not clash with a Claude Code built-in (for example /status, /logout need the prefix). In Claude Desktop without the plugin, say the same thing in words and Claude will use the amerika tools.', '',
      'Every command makes Claude check the result with a read tool and report only what it verified. Risky actions ask first; reboot, shutdown, logout and sleep always confirm.', '']
for g, items in groups.items():
    md += [f'## {g}', '', '| Command | What it does |', '|---|---|']
    for i in items:
        md.append(f'| `/amerika-os:{i["name"]}`' + (f' `{i["hint"]}`' if i['hint'] else '') + f' | {i["desc"]} |')
    md.append('')
Path('src/os/claude/commands.md').write_text('\n'.join(md))
Path('src/os/claude/plugin/amerika-os/commands.md').write_text('\n'.join(md))
doc = Path('docs/claude-os/skills.md')
block = []
for g_, items in groups.items():
    block += [f'### {g_}', '', '| Command | What it does |', '|---|---|']
    block += [f'| `/amerika-os:{i["name"]}`' + (f' `{i["hint"]}`' if i['hint'] else '') + f' | {i["desc"]} |' for i in items] + ['']
text = doc.read_text()
text = re.sub(r'<!-- commands:start -->.*?<!-- commands:end -->', lambda m: '<!-- commands:start -->\n' + '\n'.join(block) + '\n<!-- commands:end -->', text, flags=re.S)
doc.write_text(text)
print(len(CMDS), 'commands')
