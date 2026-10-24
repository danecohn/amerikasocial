# AltStack Desktop, Claude first (concept 4.0)

AltStack Desktop becomes a computer built around the **Claude desktop app** (primary) with the **ChatGPT desktop app** as the backup. No dock/app tray. Claude IS the home screen. The Copilot key opens the **Caster** to switch between the two. The Windows key opens the full app menu. A customizable top bar carries the time and status. Claude operates the computer through MCP tools and skills we ship.

## Honest limits (do not violate, do not promise otherwise)
- The Claude and ChatGPT desktop apps are **proprietary Electron apps**. We do not patch, repack or modify them. "Highly customized" means: we place them (fullscreen, borderless, under our top bar, as the home window), size them (Electron scale flag for bigger text), launch/supervise them, and surround them with our own shell (bar, Caster, app menu, notifications). We cannot change their internal UI.
- Claude's built-in browser and terminal live inside the Claude app (Claude Code tab / Claude in Chrome). The system's default browser/terminal handlers cannot point into them; the OS keeps normal handlers, but the launcher/Caster/home make the Claude app the main surface.
- Never edit the user's real `~/.claude`, `~/.codex` configuration except through an explicit user-pressed "Connect" action in Settings (existing pattern in `ai/connect.py`), which backs up first and can be undone.
- Opt-in and reversible for anything touching session defaults. The existing Plasma/other sessions stay as fallbacks. Version/time facts: Ubuntu 26.10 ARM64, Surface Laptop 7.

## Components

| Piece | Owner | What |
|---|---|---|
| **Home mode** | shell | Setting `home_mode` (`claude`/`chatgpt`/`off`, default `claude` for new installs under this concept). The home AI app runs fullscreen-in-workarea (maximized, borderless, below the top bar), supervised (relaunched if closed), and is the thing you see when no other window is open. Other apps open on top of it normally. Meta+H (and a Home entry in the app menu) returns home. Bridge/KWin: a window rule keyed on resource class (`com.anthropic.Claude`, ChatGPT's class) set from bridge.js. |
| **No dock** | shell | `dock_enabled` setting (default false in Claude-OS mode; the dock code stays, user can turn it on in Settings). The bar remains. |
| **Caster** | shell | Copilot key (Shift+Super+F23, existing key plumbing) opens a full-screen overlay "Caster": two large cards (Claude, ChatGPT) with logo, name, running state, last-used; Left/Right/Tab or click to choose, Enter opens/raises it as the home view, Esc closes; pressing the Copilot key again while open cycles to the other card; also `1`/`2`. Setting `copilot_app` gains `caster` (default). |
| **Top bar** | shell | Customizable: widgets (launcher button, active-window title, AI chip, clock, date, status icons, tray, notifications) with enable/disable, left/center/right placement and order, clock format (12/24h, seconds, date), height, translucency; stored in settings `bar_layout`; Settings page "Top bar"; live apply. The clock/time is always shown on the home view by default. |
| **App menu** | shell | Windows key opens the launcher as the full all-apps menu (grid, search, categories, Home/Settings/Power entries, "Ask Claude" row). |
| **Text size** | shell | Setting `ai_text_scale` (default 1.25 for ChatGPT, 1.0 for Claude, per-app) applied as Electron `--force-device-scale-factor` when the shell launches/relaunches these apps, plus the `.desktop` overrides shipped for launches from elsewhere. Settings control with live preview text. |
| **Claude skills & plugin** | skills | Skills (SKILL.md folders) and a Claude Code plugin that teach Claude to operate AltStack Desktop through the `amerika` MCP server, plus any missing MCP tools. Installed ONLY via an explicit Connect button/CLI (`amerika-claude install`), with backup/undo; also exportable as zips for Claude Desktop's Skills upload. |
| **ChatGPT side** | later | The same but ChatGPT first; handed off to ChatGPT/Codex with a written handoff prompt when the Claude side is ready. |

Existing pieces that stay: `amerika-mcp` + approval broker (risk classes read/act/sensitive/critical, modes ask/safe/trusted, Stop switch, audit log), Amerika Agent (OpenClaw, optional), Amerika Studio (Developer Edition), settings, login/boot screens.

## Conventions
- Repo `/home/ant/Documents/Codex/2026-10-20/i-w/work/amerika-os`; Python in `src/os/amerika/...`; builders via `tools/builders/*.py` (`register(b)`), do NOT edit `build.py`; tests `python3 -m unittest discover -s tests -q` must stay green (currently 301); UI verified in `kwin_wayland --virtual` rigs (`tools/kwin-rig.sh`, `tests/rig/*`) with screenshots under `dist/` inspected via Read.
- Retro-futurist look (`am-*` CSS, neon on chrome). No emoji.
- Never touch the real `~/.claude`, `~/.codex`, `~/.openclaw`; never print or store keys; exact-PID cleanup (never `pkill -f`); no pushes/releases.
- Final report: concise, with an explicit list of what could not be verified (the real laptop, the real proprietary apps' behaviour under our window rules, the real Copilot key).
