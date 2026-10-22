# Claude skills and plugin for Amerika OS

Package: `amerika-claude` (arch all, depends on `amerika-desktop-shell`). Installing the package changes nothing in anyone's home folder. Skills are installed only when the user runs `amerika-claude install` or presses the button in Settings > AI (`ai.connect.install_skills()`).

## What ships
| Piece | Location (package) | Purpose |
|---|---|---|
| Plugin `amerika-os` | `/usr/share/amerika-claude/plugin/amerika-os/` | `.claude-plugin/plugin.json`, 11 skills, 63 slash commands (`commands/`, cheat sheet `commands.md`), `.mcp.json` (servers `amerika`, and `amerika-studio` when installed), `AMERIKA.md` |
| Operating manual | `/usr/share/amerika-claude/AMERIKA.md` (also inside the plugin and the overview skill) | OS map, tool catalogue, rules |
| CLI | `/usr/bin/amerika-claude` | `status`, `install`, `remove`, `export DIR`, `doctor` |
| Python | `amerika_claude` in dist-packages | logic used by the CLI and by `ai/connect.py` |

Hooks are deliberately not shipped: nothing about operating the desktop is safe to run unattended on every tool call, and the shell already audits all calls.

## The skills
| Skill | Use it for |
|---|---|
| `amerika-os-overview` | Start here: what the OS is, connection check, approval model, verify-before-claim |
| `operate-desktop` | Apps, windows, virtual desktops, launcher, home, Caster, top bar |
| `system-settings` | Audio, brightness, scale, Wi-Fi, power profile, preferences; read, change one thing, read back, revert |
| `files-and-projects` | Home-confined file work, protected places, safe edit/tidy/delete |
| `software-and-updates` | Amerika Software, apt (read-only checks), update channels; the user authorises installs |
| `diagnose-and-repair` | Journal, units, hardware report, safe fixes, recovery paths |
| `game-dev-studio` | Render, Engine (recipes), Sprite, Box via the studio MCP |
| `hardware-surface-laptop-7` | Turnip Vulkan, perf modes, thermals, NPU reality |
| `voice-and-notifications` | Notifications, Do Not Disturb, volume, honest voice limits |
| `schedule-and-automation` | systemd user timers, reminders, removal |
| `privacy-and-safety` | What to ask first, secrets, untrusted content, the Stop switch |

## Slash commands
Claude Code plugin commands are invoked as `/amerika-os:<name>`; the short form works when it does not clash with a Claude Code built-in (`/status`, `/logout` and a few others need the prefix). `/amerika-os:amerika` prints this index. Each command is a short prompt that restricts Claude to the `amerika` tools, tells it to verify the outcome with a read tool and to report only what it verified. `allowed-tools` pre-approves only read-only tools (both the `mcp__amerika__` and `mcp__plugin_amerika-os_amerika__` spellings); act, sensitive and critical tools keep asking, in Claude Code and in the Amerika broker. Reboot, shutdown, logout and sleep always confirm; install/update/uninstall never run sudo (the user answers the administrator prompt); tidy proposes first and never deletes. The files are generated from one spec by `tools/gen-claude-commands.py` (edit that, not the .md files).

<!-- commands:start -->
### Start here

| Command | What it does |
|---|---|
| `/amerika-os:amerika` `[topic]` | Index of every Amerika OS command, grouped, with what each one does |
| `/amerika-os:status` | One-screen status of this computer: system, power, network, windows, hardware, services |

### Hardware

| Command | What it does |
|---|---|
| `/amerika-os:hw` | Hardware report: CPU, memory, GPU/Vulkan, thermals, NPU, with advice |
| `/amerika-os:perf` `game | balanced` | Switch the performance mode: game or balanced (asks for administrator approval) |
| `/amerika-os:bench` | Explain and prepare a GPU benchmark (it runs in your terminal) |
| `/amerika-os:tune` `apply | revert` | Explain the opt-in system tuning (zram, file-watch limits, shader cache) and how to undo it |

### Home and AI apps

| Command | What it does |
|---|---|
| `/amerika-os:home` | Go to the home view (the home AI app) |
| `/amerika-os:caster` `[next | prev | close]` | Open, close or cycle the Caster (Claude / ChatGPT switcher) |
| `/amerika-os:chatgpt` `[open]` | Make ChatGPT the home AI app, or just open it |

### Windows and apps

| Command | What it does |
|---|---|
| `/amerika-os:windows` `[filter]` | List open windows, grouped by desktop, with size and state |
| `/amerika-os:raise` `window name` | Bring a window to the front by name |
| `/amerika-os:tile` `window left | right | top | bottom | max` | Snap a window left, right, top, bottom or maximize it |
| `/amerika-os:close` `window name` | Close a window (asks first if it may hold unsaved work) |
| `/amerika-os:move-desktop` `window desktop-number` | Move a window to another virtual desktop (and optionally switch) |
| `/amerika-os:open` `app name` | Open an application by name |
| `/amerika-os:apps` `[search]` | Search the installed applications |
| `/amerika-os:quit` `app name` | Close all windows of an application |

### Desktop and top bar

| Command | What it does |
|---|---|
| `/amerika-os:bar` `show | preset classic|home | height N | opacity N | hide WIDGET | show WIDGET` | Show or change the top bar (widgets, preset, height, opacity) |
| `/amerika-os:clock` `12h | 24h | seconds on|off | date none|short|long|numeric` | Clock format: 12/24 hour, seconds, date style |
| `/amerika-os:theme` `colour or name, optional second colour` | Change the accent and secondary colours |
| `/amerika-os:wallpaper` `horizon | grid | dusk` | Change the wallpaper: horizon, grid or dusk |
| `/amerika-os:dock` `on | off` | Show or hide the dock |
| `/amerika-os:text-size` `claude|chatgpt scale` | Text size of the Claude or ChatGPT app (0.8 to 2.0) |

### Settings

| Command | What it does |
|---|---|
| `/amerika-os:settings` `page name | key` | Open a Settings page or read a setting |
| `/amerika-os:volume` `0-150 | up | down | mute | unmute` | Set, raise, lower or mute the volume |
| `/amerika-os:brightness` `1-100 | up | down` | Set the screen brightness |
| `/amerika-os:wifi` `on | off` | Turn Wi-Fi on or off |
| `/amerika-os:bluetooth` | Open Bluetooth settings (pairing is done by the user) |
| `/amerika-os:dnd` `on | off` | Do Not Disturb on or off |
| `/amerika-os:night` | Open the night light and colour settings |
| `/amerika-os:power-profile` `power-saver | balanced | performance` | Set the power profile: power-saver, balanced or performance |

### Files

| Command | What it does |
|---|---|
| `/amerika-os:files` `path (default ~)` | List a folder in your home directory |
| `/amerika-os:find` `name or part of it` | Find files by name in your home directory |
| `/amerika-os:recent` `[days, default 2]` | Show recently changed files in your home directory |
| `/amerika-os:tidy` `folder` | Propose how to organise a folder (nothing is moved or deleted without your approval) |
| `/amerika-os:clip` `show | set TEXT` | Read or set the clipboard |
| `/amerika-os:shot` `screen | window` | Take a screenshot of the screen or the active window |

### Notifications

| Command | What it does |
|---|---|
| `/amerika-os:notify` `title | body` | Show a desktop notification |
| `/amerika-os:remind` `when what  (for example: 20m stand up)` | Remind me later with a notification |

### Software

| Command | What it does |
|---|---|
| `/amerika-os:install` `package or app name` | Install software (you approve the administrator prompt) |
| `/amerika-os:update` `check | amerika` | Check for updates and guide the upgrade |
| `/amerika-os:uninstall` `package or app name` | Remove software (you approve; asks every time) |

### Diagnose and repair

| Command | What it does |
|---|---|
| `/amerika-os:journal` `[unit] [since]` | Read recent errors from the user journal (secrets are redacted) |
| `/amerika-os:fix` `what is wrong` | Diagnose a symptom and fix it with the smallest safe step |
| `/amerika-os:restart-shell` | What to do when the bar or shell is frozen (tools cannot restart it) |
| `/amerika-os:recover` | Recovery steps for a broken session, home mode, login or boot screen |

### Session and power

| Command | What it does |
|---|---|
| `/amerika-os:lock` | Lock the screen |
| `/amerika-os:sleep` | Suspend the computer (always confirm) |
| `/amerika-os:logout` | Log out of the Amerika session (always confirm) |
| `/amerika-os:reboot` | Restart the computer (always confirm) |
| `/amerika-os:shutdown` | Shut the computer down (always confirm) |

### Game and media studio

| Command | What it does |
|---|---|
| `/amerika-os:studio` `status | render | engine | sprite | box` | Status of Amerika Studio and its four apps; open one |
| `/amerika-os:render` `description` | Make or change a 3D model in Amerika Render (Blender) |
| `/amerika-os:engine` `description` | Build or change a game in Amerika Engine (Godot) |
| `/amerika-os:sprite` `description` | Draw or change pixel art in Amerika Sprite |
| `/amerika-os:box` `description` | Compose or change chiptune music in AmerikaBox |
| `/amerika-os:game` `game idea` | Orchestrate a whole game: code, art, model and music from one idea |

### Modes

| Command | What it does |
|---|---|
| `/amerika-os:focus` `task | off | mute` | Focus mode for a task: Do Not Disturb, quiet desktop, optional mute |
| `/amerika-os:gamedev-mode` `on | off` | Game development mode: performance profile, quiet notifications, Studio ready |
| `/amerika-os:presentation-mode` `on | off` | Presentation mode: Do Not Disturb, no sleep surprises, clean bar |
| `/amerika-os:classic-mode` `revert` | Switch to the Classic desktop (dock, no home app); reversible |
| `/amerika-os:claude-mode` `chatgpt` | Switch to Claude-first mode: Claude home view, Caster on the Copilot key, no dock |
| `/amerika-os:agent` | Status of Amerika Agent and how to open it |

<!-- commands:end -->

Without the plugin (Claude Desktop with only skills or the MCP connection) the same wishes work as plain sentences; `amerika-claude export` includes the cheat sheet as `commands.md`.

## MCP tools added for the skills
Read: `hw.report`, `journal.read` (user journal, 500 lines max, secrets redacted), `units.status` (amerika-* user units), `studio.status`, `bar.get` (bar_layout, bar_preset, bar_clock_format, bar_height, bar_opacity, home_mode, dock_enabled, copilot_app, ai_text_scale). Act: `ui.home` (Control action `home`), `ui.caster` (`caster`, `caster:next|prev|close`), `bar.set` (preset, layout, clock_format, height, opacity; validated against `shell/barlayout.py`), `ui.text_scale` (`ai_text_scale`, 0.8-2.0), `ui.settings` (opens `amerika-settings PAGE` for known pages only). Sensitive: `ui.mode` (claude, chatgpt, off, revert via `shell/home.py` presets and snapshot), `ui.relaunch` (`relaunch:claude|chatgpt`), `units.restart` (amerika-*.service only, never shell/session/login/broker), `apps.close`. Critical: `hw.perf` (pkexec). `settings.set` follows the keys of the settings API (now including `home_mode`, `dock_enabled`, `bar_height`, `copilot_app` caster), `settings.get` returns them. `ui.*` tools that drive Control actions return a clear error on a shell that lacks the action.

### Tool names for MCP clients
Anthropic tool names must match `^[a-zA-Z0-9_-]{1,64}$`. `amerika-mcp` therefore advertises every tool with dots replaced by underscores (`windows.list` -> `windows_list`) and maps the name back on each call; the registry, the broker, the audit log and the approval dialog keep the dotted names, and calls using the dotted name still work. Skills and commands write names as `amerika.windows.list` for readability. All go through the broker: risk class, mode, approval, Stop switch and audit log apply unchanged. Existing tools were reused instead of aliased (`clipboard.get/set`, `notifications.set_dnd`, `screenshot.take`, `apps.list/launch`, `windows.*`).

## Install
```
amerika-claude install                 # skills + plugin marketplace
amerika-claude install --skills-only   # only ~/.claude/skills/amerika-*
amerika-claude install --plugin-only
amerika-claude status
amerika-claude doctor
```
It writes only: `~/.claude/skills/amerika-*/`, `~/.claude/plugins/amerika-marketplace/`, the manifest `~/.local/state/amerika-os/claude-install.json` and a timestamped backup under `~/.local/state/amerika-os/claude-backup/`. It refuses (changing nothing) if a target folder exists that Amerika did not create (no `.amerika-managed` marker). Running it again is a no-op unless files changed.

Plugin activation is explicit in Claude Code: `/plugin marketplace add ~/.claude/plugins/amerika-marketplace` then `/plugin install amerika-os@amerika-os`. If skills appear twice (direct and via the plugin) use only one of `--skills-only` / `--plugin-only`.

## Manual upload (Claude Desktop)
`amerika-claude export ~/Documents/amerika-skills` writes one `amerika-<skill>.zip` per skill (a folder named after the skill with `SKILL.md` inside), `custom-instructions.md` and `commands.md` (the command cheat sheet). Upload each zip under Settings > Capabilities > Skills and paste the instructions into your profile or a Project.

## Undo
`amerika-claude remove` deletes exactly the files in the manifest and removes folders it created if they are empty. Files you edited after installing are kept (and listed); `--force` deletes them too. Backups are never deleted automatically. Plugin side: `/plugin uninstall amerika-os@amerika-os` and `/plugin marketplace remove amerika-os` before or after `remove`.

## Settings UI hooks
`ai.connect.skills_status()`, `install_skills(skills=True, plugin=True)`, `remove_skills(force=False)`, `export_skills(dir)`. They raise `ValueError` with a user-fit message; `skills_status()['available']` is False when the package is absent. The existing Connect/Disconnect behaviour is untouched.

## Maintaining
Edit skills in `src/os/claude/plugin/amerika-os/skills/`; commands in `tools/gen-claude-commands.py` (then run it from the repo root). `AMERIKA.md` exists in three identical copies (source, plugin, overview skill reference); a test enforces this. Every `amerika.<tool>` mentioned in a skill must exist in `ai/tools.py`, every studio tool in `studio/tools.json`: `python3 -m unittest tests.test_claude_skills`.
