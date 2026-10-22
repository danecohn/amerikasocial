---
description: "Go to the home view (the home AI app)"
allowed-tools: mcp__amerika__bar_get, mcp__plugin_amerika-os_amerika__bar_get, mcp__amerika__windows_list, mcp__plugin_amerika-os_amerika__windows_list
---

Call `amerika.ui.home`. If it reports the action is unsupported, tell the user to update amerika-desktop-shell. If `amerika.bar.get` shows `home_mode` off, say Classic desktop has no home app and offer `/amerika-os:claude-mode`. Verify with `amerika.windows.list` that the home app window is active and report what you see.

Rules: follow the operate-desktop skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
