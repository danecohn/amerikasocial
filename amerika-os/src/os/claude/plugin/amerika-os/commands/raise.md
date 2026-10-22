---
description: "Bring a window to the front by name"
argument-hint: "window name"
allowed-tools: mcp__amerika__windows_list, mcp__plugin_amerika-os_amerika__windows_list
---

Window wanted: $ARGUMENTS. `amerika.windows.list`, match on title or app (ask if several match), then `amerika.windows.focus {id}`. Verify with `amerika.windows.list` that it is active and not minimized (use `amerika.windows.restore` first if it is minimized).

Rules: follow the operate-desktop skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
