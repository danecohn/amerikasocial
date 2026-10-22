---
description: "Switch to the Classic desktop (dock, no home app); reversible"
argument-hint: "revert"
allowed-tools: mcp__amerika__bar_get, mcp__plugin_amerika-os_amerika__bar_get, mcp__amerika__windows_list, mcp__plugin_amerika-os_amerika__windows_list
---

Argument: $ARGUMENTS. Read `amerika.bar.get` (home_mode, dock_enabled, copilot_app). Tell the user what changes (home app no longer enforced, dock back, Copilot key opens Claude, classic bar) and that `/amerika-os:claude-mode` or `revert` goes back. After a yes call `amerika.ui.mode {mode: "off"}` (or `{mode: "revert"}` if the argument is revert). Verify with `amerika.bar.get` and `amerika.windows.list`.

Rules: follow the operate-desktop skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
