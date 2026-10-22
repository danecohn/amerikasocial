---
description: "Change the accent and secondary colours"
argument-hint: "colour or name, optional second colour"
allowed-tools: mcp__amerika__settings_get, mcp__plugin_amerika-os_amerika__settings_get
---

Request: $ARGUMENTS. Turn names into `#rrggbb` (propose the value and show it before applying if the wish is vague). `amerika.settings.get` first to record the old accent and secondary. Then `amerika.settings.set {key: "accent", value}` and/or `{key: "secondary", value}`. Verify with `amerika.settings.get` and give the old values for undo.

Rules: follow the system-settings skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
