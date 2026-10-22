---
description: "Show or hide the dock"
argument-hint: "on | off"
allowed-tools: mcp__amerika__bar_get, mcp__plugin_amerika-os_amerika__bar_get, mcp__amerika__settings_get, mcp__plugin_amerika-os_amerika__settings_get
---

Argument: $ARGUMENTS (on or off; ask if missing). Read `amerika.settings.get` (`dock_enabled`). Set `amerika.settings.set {key: "dock_enabled", value: true|false}`. The dock's pinned apps are never touched, so turning it back on restores the same dock. Verify with `amerika.bar.get` and say what the user should see.

Rules: follow the system-settings skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
