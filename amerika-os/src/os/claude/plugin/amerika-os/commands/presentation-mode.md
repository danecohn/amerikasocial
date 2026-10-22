---
description: "Presentation mode: Do Not Disturb, no sleep surprises, clean bar"
argument-hint: "on | off"
allowed-tools: mcp__amerika__bar_get, mcp__plugin_amerika-os_amerika__bar_get, mcp__amerika__system_status, mcp__plugin_amerika-os_amerika__system_status
---

Argument: $ARGUMENTS. Read `amerika.system.status` and `amerika.bar.get` to remember brightness, volume and the bar. on: tell the user the plan, wait for a yes, then `amerika.notifications.set_dnd {on: true}`, `amerika.audio.set_mute {muted: true}` (only if they want silence) and optionally `amerika.bar.set {opacity: 1}`. Say that you cannot disable sleep or the lock screen from here. off: undo exactly what you did. Verify with the read tools and report.

Rules: follow the voice-and-notifications skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
