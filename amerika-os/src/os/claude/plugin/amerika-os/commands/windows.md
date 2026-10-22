---
description: "List open windows, grouped by desktop, with size and state"
argument-hint: "[filter]"
allowed-tools: mcp__amerika__desktops_list, mcp__plugin_amerika-os_amerika__desktops_list, mcp__amerika__windows_list, mcp__plugin_amerika-os_amerika__windows_list
---

Call `amerika.windows.list` and `amerika.desktops.list`. Filter (optional): $ARGUMENTS. Show a compact table: id, title, app, desktop, state (active, minimized, fullscreen), size. Do not change anything.

Rules: follow the operate-desktop skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
