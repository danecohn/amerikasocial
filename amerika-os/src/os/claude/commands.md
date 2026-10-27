# AltStack Desktop commands

Type these in Claude Code (plugin `amerika-os`) as `/amerika-os:<name>`; the short name works where it does not clash with a Claude Code built-in (for example /status, /logout need the prefix). In Claude Desktop without the plugin, say the same thing in words and Claude will use the amerika tools.

Every command makes Claude check the result with a read tool and report only what it verified. Risky actions ask first; reboot, shutdown, logout and sleep always confirm.

## Start here

| Command | What it does |
|---|---|
| `/amerika-os:amerika` `[topic]` | Index of every AltStack Desktop command, grouped, with what each one does |
| `/amerika-os:status` | One-screen status of this computer: system, power, network, windows, hardware, services |

## Hardware

| Command | What it does |
|---|---|
| `/amerika-os:hw` | Hardware report: CPU, memory, GPU/Vulkan, thermals, NPU, with advice |
| `/amerika-os:perf` `game | balanced` | Switch the performance mode: game or balanced (asks for administrator approval) |
| `/amerika-os:bench` | Explain and prepare a GPU benchmark (it runs in your terminal) |
| `/amerika-os:tune` `apply | revert` | Explain the opt-in system tuning (zram, file-watch limits, shader cache) and how to undo it |

## Home and AI apps

| Command | What it does |
|---|---|
| `/amerika-os:home` | Go to the home view (the home AI app) |
| `/amerika-os:caster` `[next | prev | close]` | Open, close or cycle the Caster (Claude / ChatGPT switcher) |
| `/amerika-os:chatgpt` `[open]` | Make ChatGPT the home AI app, or just open it |

## Windows and apps

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

## Desktop and top bar

| Command | What it does |
|---|---|
| `/amerika-os:bar` `show | preset classic|home | height N | opacity N | hide WIDGET | show WIDGET` | Show or change the top bar (widgets, preset, height, opacity) |
| `/amerika-os:clock` `12h | 24h | seconds on|off | date none|short|long|numeric` | Clock format: 12/24 hour, seconds, date style |
| `/amerika-os:theme` `colour or name, optional second colour` | Change the accent and secondary colours |
| `/amerika-os:wallpaper` `horizon | grid | dusk` | Change the wallpaper: horizon, grid or dusk |
| `/amerika-os:dock` `on | off` | Show or hide the dock |
| `/amerika-os:text-size` `claude|chatgpt scale` | Text size of the Claude or ChatGPT app (0.8 to 2.0) |

## Settings

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

## Files

| Command | What it does |
|---|---|
| `/amerika-os:files` `path (default ~)` | List a folder in your home directory |
| `/amerika-os:find` `name or part of it` | Find files by name in your home directory |
| `/amerika-os:recent` `[days, default 2]` | Show recently changed files in your home directory |
| `/amerika-os:tidy` `folder` | Propose how to organise a folder (nothing is moved or deleted without your approval) |
| `/amerika-os:clip` `show | set TEXT` | Read or set the clipboard |
| `/amerika-os:shot` `screen | window` | Take a screenshot of the screen or the active window |

## Notifications

| Command | What it does |
|---|---|
| `/amerika-os:notify` `title | body` | Show a desktop notification |
| `/amerika-os:remind` `when what  (for example: 20m stand up)` | Remind me later with a notification |

## Software

| Command | What it does |
|---|---|
| `/amerika-os:install` `package or app name` | Install software (you approve the administrator prompt) |
| `/amerika-os:update` `check | amerika` | Check for updates and guide the upgrade |
| `/amerika-os:uninstall` `package or app name` | Remove software (you approve; asks every time) |

## Diagnose and repair

| Command | What it does |
|---|---|
| `/amerika-os:journal` `[unit] [since]` | Read recent errors from the user journal (secrets are redacted) |
| `/amerika-os:fix` `what is wrong` | Diagnose a symptom and fix it with the smallest safe step |
| `/amerika-os:restart-shell` | What to do when the bar or shell is frozen (tools cannot restart it) |
| `/amerika-os:recover` | Recovery steps for a broken session, home mode, login or boot screen |

## Session and power

| Command | What it does |
|---|---|
| `/amerika-os:lock` | Lock the screen |
| `/amerika-os:sleep` | Suspend the computer (always confirm) |
| `/amerika-os:logout` | Log out of the Amerika session (always confirm) |
| `/amerika-os:reboot` | Restart the computer (always confirm) |
| `/amerika-os:shutdown` | Shut the computer down (always confirm) |

## Game and media studio

| Command | What it does |
|---|---|
| `/amerika-os:studio` `status | render | engine | sprite | box` | Status of Amerika Studio and its four apps; open one |
| `/amerika-os:render` `description` | Make or change a 3D model in Amerika Render (Blender) |
| `/amerika-os:engine` `description` | Build or change a game in Amerika Engine (Godot) |
| `/amerika-os:sprite` `description` | Draw or change pixel art in Amerika Sprite |
| `/amerika-os:box` `description` | Compose or change chiptune music in AmerikaBox |
| `/amerika-os:game` `game idea` | Orchestrate a whole game: code, art, model and music from one idea |

## Modes

| Command | What it does |
|---|---|
| `/amerika-os:focus` `task | off | mute` | Focus mode for a task: Do Not Disturb, quiet desktop, optional mute |
| `/amerika-os:gamedev-mode` `on | off` | Game development mode: performance profile, quiet notifications, Studio ready |
| `/amerika-os:presentation-mode` `on | off` | Presentation mode: Do Not Disturb, no sleep surprises, clean bar |
| `/amerika-os:classic-mode` `revert` | Switch to the Classic desktop (dock, no home app); reversible |
| `/amerika-os:claude-mode` `chatgpt` | Switch to Claude-first mode: Claude home view, Caster on the Copilot key, no dock |
| `/amerika-os:agent` | Status of Amerika Agent and how to open it |
