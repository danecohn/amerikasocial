---
description: "Recovery steps for a broken session, home mode, login or boot screen"
allowed-tools: mcp__amerika__bar_get, mcp__plugin_amerika-os_amerika__bar_get, mcp__amerika__journal_read, mcp__plugin_amerika-os_amerika__journal_read, mcp__amerika__system_status, mcp__plugin_amerika-os_amerika__system_status, mcp__amerika__units_status, mcp__plugin_amerika-os_amerika__units_status
---

Read-only first: `amerika.system.status`, `amerika.units.status`, `amerika.journal.read {priority: "err", lines: 60}`, and `amerika.bar.get` (home_mode, dock_enabled). Then give the user the documented recovery path that matches, in this order of gentleness:
1. In the session: Settings > Home & Caster > Classic desktop (or Revert). Win+Space opens the app menu; Win+Q closes the active window. (`/amerika-os:classic-mode` does the Classic switch for them if tools still work.)
2. Screen unusable: Ctrl+Alt+F3, log in on the text console, run `amerika-settings --classic` (sets home_mode off, dock on, Copilot key to Claude, classic bar), then log out and in. By hand: in `~/.config/amerika-os/settings.json` set `"home_mode": "off"` and `"dock_enabled": true`.
3. Broken Amerika session or themes: from the console, `amerika-agent disable --now`; `amerika-login disable` and/or `amerika-boot disable` if those themes were enabled; choose the fallback (Plasma) desktop at the login screen.
4. Hardware tuning: `amerika-hw tune revert`, `amerika-hw perf balanced`.
Say clearly that lock screen, suspend/resume and these recovery paths are not fully tested on the real laptop. Save logs locally and review them before sharing.

Rules: follow the diagnose-and-repair skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
