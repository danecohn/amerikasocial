# Amerika Agent: architecture (v3.1)

Amerika Agent is the agentic layer of AltStack Desktop. It **bundles OpenClaw (MIT, https://github.com/openclaw/openclaw)** as its engine and wires it into the Amerika shell, Settings, login-keyring and the existing `amerika-mcp` tool broker. Upstream licence (MIT, "Copyright OpenClaw contributors/Foundation") and notices must ship in the package (`/usr/share/doc/amerika-agent/`), and the UI must say plainly that Amerika Agent is built on OpenClaw. Do not fork or vendor the 1 GB source tree; install the **published npm package `openclaw` at a pinned version** (currently 2026.10.5) into `/opt/amerika/agent` with Node 24.x (Ubuntu 26.10 `nodejs` 24.19 satisfies OpenClaw's `>=24.16 <25`).

Verified on this ARM64 machine: `npm install openclaw@2026.10.5 --omit=dev` works (614 MB node_modules), `openclaw gateway run` starts headless on loopback, `/` serves the Control UI (HTTP 200), `openclaw health` answers. Dev Node lives at `work/tools/node/bin` (v24.22.1) and a reference install at `work/openclaw-src/stage-install` (do not run it with the real `$HOME`; use a throwaway `HOME`). OpenClaw docs are at `work/openclaw-src/src/docs` (read `gateway/`, `plugins/`, `providers/anthropic.md`, `providers/openai.md`, `gateway/secrets/*`, `gateway/sandboxing*`, `gateway/permission-modes.md`, `gateway/configuration-reference.md`, `platforms/linux*` before designing against it).

## Components

```
 user ── Settings > Amerika Agent (enter Anthropic / OpenAI key, pick model, permissions)
          │ key stored in the login keyring (libsecret, Secret Service). Never in a file, argv, env of other processes, logs or git.
          ▼
 amerika-agent (systemd --user: amerika-agent-gateway.service) = `openclaw gateway run`, loopback only, token auth
   • config: ~/.config/amerika-agent/ (OPENCLAW_STATE_DIR/OPENCLAW_CONFIG_PATH point here, never ~/.openclaw of an existing user install)
   • provider credentials resolved with an OpenClaw SecretRef `exec` provider that runs `amerika-agent-secret get <name>` (keyring lookup)
   • MCP: `mcp.servers.amerika` = our stdio `amerika-mcp` (OS control: windows, files in $HOME, settings, notifications, apps, power…)
   • node: OpenClaw `linux-node` plugin (notifications, camera, location) enabled when the user opts in
   • channels (Telegram, Discord, etc.) available but OFF by default; the UI explains inbound-message risk
          │
          ▼
 Amerika shell: bar agent chip + "Ask Amerika Agent" in the launcher + Agent window (Control UI in WebKitGTK) + approvals
 through the existing broker (risk classes read/act/sensitive/critical; modes ask/safe/trusted; Stop switch; audit log)
```

Security invariants (all subagents):
1. API keys only via the keyring path above; never printed, logged, put in argv, in `/proc/*/environ` of unrelated processes, in `openclaw.json`, or in tests (tests use obviously fake values like `sk-test-FAKE`).
2. Gateway binds loopback, token auth, token generated per user, kept in the keyring.
3. Agent actions that touch the system go through `amerika-mcp` and its approval broker; "critical" always asks. The global Stop switch must stop the agent.
4. Nothing in this work may change login manager, GRUB, initramfs or default session without the existing opt-in/revert pattern.
5. Don't touch the user's real `~/.openclaw`, `~/.claude`, `~/.codex`.
6. Production AltStack Social/PDS services are off limits. Railway builds are paused: do not deploy.
7. No test credentials against real services; no network calls to model providers in tests.

## Build conventions

- The repo is `work/amerika-os`. `build.py` loads `tools/builders/*.py`; each exposes `register(b)` returning `{package_name: builder_fn}` (builder returns a `b.Pkg`) and optional `META_DEPENDS` / `META_RECOMMENDS` lists. `b.Pkg(...)`, `b.OS` (= `src/os`), `b.DE_VERSION`, `b.STAGE`, `b.ARCH`, `b.shutil`, `b.write`, `b.copy`, `b.sh`, `b.desktop_file` are available. **Do not edit `build.py` itself** (the integrator owns it); ask by putting needs in your report.
- Python lives in `src/os/amerika/...` (installed to `/usr/lib/python3/dist-packages/amerika`). GTK4 + gtk4-layer-shell; CSS in `theme.py` (escape `%` as `%%`).
- Run unit tests with `python3 -m unittest discover -s tests -q`; add tests for everything with logic (`tests/test_<area>.py`). UI is verified in the `kwin_wayland --virtual` rig (`tests/rig/`, `tools/kwin-rig.sh`) with a private D-Bus; screenshot widgets via `Gtk.WidgetPaintable`.
- Style: match surrounding code; retro-futurist look (neon on chrome, `am-*` CSS classes); no new emoji; icons come from the `amerika-icon-theme` (`tools/make_icons.py`).
- Large (>5 MB) debs are redirected to GitHub release assets; do not rebuild unchanged large debs.
- The user wants one final report only. Work autonomously; make decisions; verify what can be verified in this sandbox and state in your report exactly what could not be tested (anything needing the real laptop, real boot, real API keys, or network services).

## File ownership (avoid conflicts)

| Area | Owns |
|---|---|
| agent-core | `src/os/agent/**`, `tools/builders/agent.py`, `tests/test_agent_core.py`, `tools/fetch-openclaw.sh`, `docs/agent/**` |
| agent-ui | `src/os/amerika/agent/**`, `src/os/amerika/shell/agent_*.py`, `src/os/amerika/settings/page_agent.py` plus minimal marked insertions into `shell/bar.py`, `shell/launcher.py`, `shell/app.py`, `settings/app.py`, `theme.py` (`/* agent */` CSS block), `ai/tools.py` (agent tools), `tests/test_agent_ui.py` |
| desktop-parity | `src/os/amerika/shell/{switcher,workspaces,overview,hotcorners,clipboard,screenshot,lockscreen,osd}.py`, `bridge/bridge.js` (workspace/switcher parts), `src/os/amerika/system.py` additions, `tests/test_desktop.py` |
| settings-parity | `src/os/amerika/settings/page_*.py` (all pages except agent), `src/os/amerika/netman.py`, `audio.py`, `bluetooth.py`, `displays.py`, `tests/test_settings_pages.py` |
| flavor | `flavor/**` (live-build config, Calamares config, seeds, os-release/branding, motd, GRUB theme, man pages, `debian/` source packaging, lintian config, CI workflow templates), `tools/builders/flavor.py`, `docs/FLAVOR.md`, `tests/test_flavor.py` |
| qa-security | `tests/security/**`, `docs/SECURITY.md`, `docs/THREAT-MODEL-AGENT.md`; reviews all other areas last |
