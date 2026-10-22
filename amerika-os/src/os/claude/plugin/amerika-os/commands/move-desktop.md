---
description: "Move a window to another virtual desktop (and optionally switch)"
argument-hint: "window desktop-number"
allowed-tools: mcp__amerika__desktops_list, mcp__plugin_amerika-os_amerika__desktops_list, mcp__amerika__windows_list, mcp__plugin_amerika-os_amerika__windows_list
---

Request: $ARGUMENTS (window name, desktop number). `amerika.desktops.list` for the valid numbers, `amerika.windows.list` to find the window, then `amerika.windows.to_desktop {id, desktop}`. Switch there with `amerika.desktops.switch {desktop}` only if the user asked. Verify with `amerika.windows.list` (desktops field).

Rules: follow the operate-desktop skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
