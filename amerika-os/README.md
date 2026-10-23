> **AltStack Desktop 3.1.0**: adds the opt-in Amerika Agent (OpenClaw engine, MIT, bundled and pinned), native Settings, virtual desktops, switcher/overview, clipboard, calendar, OSD, KWin-enforced lock screen and the flavour packaging (branding, defaults, update channels, manuals, ISO and installer preparation). Items that need real hardware, your own API key, or a VM install are listed honestly in [release gates](docs/RELEASE-GATES.md); the bootable ISO and installer are **not** finished. Nothing has been pushed, uploaded or deployed. See the [Agent guide](docs/agent/README.md), [testing](docs/DEVELOPMENT-TESTING.md) and [flavour status](docs/FLAVOR.md).

# AltStack Desktop 3.0

AltStack Desktop is its own desktop environment for Ubuntu 26.10 (ARM64), designed so that the **Claude** and **ChatGPT** desktop
apps can operate the computer, under the user's control, with a retro-futurist look. Packages come from the signed APT
repository at <https://altstack.io/apt>; install instructions are at <https://altstack.io/downloads/os>.

It is not a Linux distribution or kernel. **KWin** (from KDE) is the window compositor; everything the user sees and uses is
Amerika's own: the shell (top bar, dock, launcher, notifications, quick controls), the settings app, the icons and
wallpapers, and the AI system-control layer. No Plasma shell, no GNOME Shell.

## Architecture

```
GDM  ->  amerika-session  ->  kwin_wayland --exit-with-session=session-start
                                   |
                         session-start: first-run look and feel, polkit agent, supervised amerika-shell
                                   |
amerika-shell (GTK4 + gtk4-layer-shell):  desktop (wallpaper) | bar + tray | dock | launcher | notifications daemon
        |   \                              AI broker (permissions, approvals, audit, Stop switch)
        |    D-Bus org.amerika.Windows  <-  KWin script (bridge.js): window list, shortcuts, one-shot window commands
        |
   control socket $XDG_RUNTIME_DIR/amerika/control.sock (0600, same user)
        |
amerika-mcp (stdio MCP server)  <-  started by the Claude / ChatGPT (Codex) apps
```

### Packages

| Package | Contents |
| --- | --- |
| `amerika-desktop` | Meta package for everything below |
| `amerika-session` | Login session entry, `amerika-session`, `session-start` |
| `amerika-desktop-shell` | The `amerika` Python package: shell, settings, AI layer, KWin bridge; `amerika-shell`, `amerika-settings`, `amerika-mcp`, `amerika-first-run` |
| `amerika-theme`, `amerika-icon-theme` | Wallpapers, colour scheme, neon cartridge icons |
| `amerika-apps` | Files, Terminal, Text, Settings launchers (Nautilus, Ptyxis, GNOME Text Editor) |
| `amerika-software` | Graphical package manager (Qt) and its Polkit-guarded root helper |
| `amerika-social`, `amerika-venture`, `amerika-office` | Application payloads repackaged from the published ARM64 releases |
| `amerika-repo-keyring` | Signing key, APT source, and the per-host pipelining setting |

Only ARM64 is built and tested.

## The AI layer

* `amerika-mcp --client claude|chatgpt` is a Model Context Protocol server (stdio, newline-delimited JSON-RPC). The AI app
  starts it; it forwards each tool call to the running shell's broker.
* The broker classifies every tool as `read`, `act`, `sensitive` or `critical` and applies the user's mode
  (`ask`, `safe` = balanced, `trusted`). Critical tools (power off, restart, delete) always ask. "Always allow" grants are
  per app and never apply to critical tools. Approvals are full-screen prompts that show the app, the tool and its arguments.
* Every call, refusal and pause is appended to `~/.local/state/amerika-os/ai-audit.log` and shown in Settings.
* The bar shows which app is operating the computer. `Ctrl+Alt+Esc` (or the Stop button) pauses all AI actions; pressing it
  again resumes. A paused broker refuses everything and cancels open approval prompts.
* Nothing is connected by default. Settings > AI & Assistants > Connect adds an `amerika` MCP server to Claude's
  `claude_desktop_config.json` (backed up once) and to Codex's `config.toml` (marked block), and Disconnect removes it.

Tools (see `src/os/amerika/ai/tools.py`): system info/status, apps, windows (list, focus, minimize, maximize, restore, fullscreen,
tile, move/resize, to desktop, close), desktops, audio, brightness, display scale, Wi-Fi, power profile, notifications,
Do Not Disturb, preferences, clipboard, files (home folder only), lock, suspend, restart, shut down, delete, and `shell.run`.

Not included yet: screenshots and synthetic keyboard/mouse input (they need a portal or libei integration).

## System tray (3.0.8)

The bar hosts StatusNotifierItem / AppIndicator icons through the session bus. It runs
`org.kde.StatusNotifierWatcher` when no watcher exists, or joins an existing watcher as a host.
It supports named icons (including app-specific theme paths), ARGB pixmaps, passive/attention
states, tooltips, primary/secondary clicks and scrolling. Exported `com.canonical.dbusmenu`
menus support actions, disabled/hidden entries, checked states, submenus and live updates.
App exit removes its icons. All app calls have timeouts and run asynchronously.

This is a Wayland StatusNotifier host; old XEmbed-only icons are not supported. Attention
movie animations, overlay badges and menu shortcut/icon decoration are not implemented.
Apps without an exported menu receive the legacy `ContextMenu(0, 0)` request; placement
depends on the app because Wayland does not expose global window coordinates to clients.

Validated with a synthetic application in the private KWin rig, including rapid menu
reopening, service disappearance and joining another watcher. Steam, Discord, Nextcloud
and NetworkManager applets still need testing in the real laptop session.

```bash
sh tools/kwin-rig.sh 'sh tests/rig/tray_test.sh'
cat "$(cat dist/rig-dir)/script.log"
```

## Keys

| Key | Action |
| --- | --- |
| Super (Windows), tap | Launcher (a KWin script shortcut on "Meta") |
| Super+Space | Launcher |
| Copilot key | Claude, ChatGPT or a picker (Settings > AI & Assistants) |
| Super+1 / Super+2 | First / second AI app |
| Super+, | Settings |
| Super+L | Lock |
| Super+Q | Close window |
| Super+Left/Right/Up/Down | Tile left, tile right, maximize, restore |
| Ctrl+Alt+Esc | Pause or resume all AI actions |

The Windows key is a KWin script shortcut on `Meta` (Plasma 6.7's KWin binds modifier-only keys through the global shortcut
system; the old `ModifierOnlyShortcuts` setting in `kwinrc` is no longer used). The Copilot key needs one thing before KWin
starts, so `amerika-session` points `XKB_CONFIG_EXTRA_PATH` at a generated copy of the `inet` layout in which Shift+Super+F23
stays F23. The stock layout turns the Copilot key's Shift+Super+F23 into `XF86Assistant`, which KWin cannot bind.

## Build and test

```bash
python3 tools/make_icons.py          # icon theme (SVG)  -> src/os/icons/AmerikaOS
python3 tools/make_wallpapers.py     # wallpapers        -> src/os/wallpapers
python3 build.py --init-key          # once; the key goes to ~/.local/share/amerika-os-signing, never into git
python3 build.py                     # packages in ./dist/packages and the signed tree in ./dist/apt
python3 tools/stage-for-social.py ../path/to/amerikasocial   # metadata + small debs -> apt-repo/
PYTHONPATH=src/os python3 -m unittest discover tests          # unit tests (permissions, MCP, config, window safety)
tools/kwin-rig.sh <script>           # headless KWin on a private D-Bus for end-to-end tests (needs dbus-run-session)
```

`tests/rig_ai_e2e.py` (run inside the rig) drives the real shell through the MCP server: window tiling and resizing are
verified against KWin's geometry, sensitive tools are asked about and cancelled by Stop, and the audit log is checked.

## Key handling

The private signing key lives only in `$AMERIKA_SIGNING_HOME` (default `~/.local/share/amerika-os-signing`), is not in this
repository and must be backed up by the owner.

## Limitations

* The shell, settings and AI layer are tested in an isolated KWin session and by automated tests, not through a real login on
  many machines.
* Screen locking uses KDE's stock locker (libkscreenlocker6, with its lock screen from plasma-desktop-data); authentication
  prompts use KDE's polkit agent. Both are replaceable later.
* Window decorations are KWin's Breeze, recoloured by the Amerika Retro scheme with buttons on the left.
* The first-run step writes a few keys to `kwinrc`, `kdeglobals` and the GTK `gtk.css` files, which other sessions on the same
  account also read.
* `claude-desktop` and `chatgpt` icons in the theme are generic stand-ins, not the logos of Anthropic or OpenAI.
* Social, Venture and Office ship unsigned upstream builds. Venture is Firefox 158.0.1 with Amerika branding (MPL-2.0).
  Office keeps ONLYOFFICE Community Edition branding.

License: GPL-3.0-only for Amerika code. Third-party components keep their own licenses.
