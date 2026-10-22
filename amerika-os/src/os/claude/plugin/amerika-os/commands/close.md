---
description: "Close a window (asks first if it may hold unsaved work)"
argument-hint: "window name"
allowed-tools: mcp__amerika__windows_list, mcp__plugin_amerika-os_amerika__windows_list
---

Window to close: $ARGUMENTS. List with `amerika.windows.list`, identify exactly one window (ask if unsure). Closing can lose unsaved work: tell the user which window, and confirm unless it is clearly harmless. Then `amerika.windows.close {id}`. Verify it is gone with `amerika.windows.list`. Offer `amerika.windows.minimize` as the safer option.

Rules: follow the operate-desktop skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
