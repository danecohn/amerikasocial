---
description: "Change the wallpaper: horizon, grid or dusk"
argument-hint: "horizon | grid | dusk"
allowed-tools: mcp__amerika__settings_get, mcp__plugin_amerika-os_amerika__settings_get
---

Wanted: $ARGUMENTS. Only horizon, grid and dusk are available through tools (for a picture file, open `amerika.ui.settings {page: "appearance"}`). Read `amerika.settings.get`, then `amerika.settings.set {key: "wallpaper", value}`, verify, mention the old value.

Rules: follow the system-settings skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
