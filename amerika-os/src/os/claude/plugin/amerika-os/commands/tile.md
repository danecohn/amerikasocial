---
description: "Snap a window left, right, top, bottom or maximize it"
argument-hint: "window left | right | top | bottom | max"
allowed-tools: mcp__amerika__windows_list, mcp__plugin_amerika-os_amerika__windows_list
---

Request: $ARGUMENTS (a window name followed by a side, or `max`). If no window is named use the active one from `amerika.windows.list`. Use `amerika.windows.tile {id, side}` for left, right, top, bottom, or `amerika.windows.maximize {id}` for max. Verify with `amerika.windows.list` (position and size) and report the actual geometry.

Rules: follow the operate-desktop skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
