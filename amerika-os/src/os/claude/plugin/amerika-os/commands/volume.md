---
description: "Set, raise, lower or mute the volume"
argument-hint: "0-150 | up | down | mute | unmute"
allowed-tools: mcp__amerika__system_status, mcp__plugin_amerika-os_amerika__system_status
---

Request: $ARGUMENTS. Read `amerika.system.status` for the current volume. up/down means a step of 10. Set with `amerika.audio.set_volume {percent}` (ask before going above 100), or `amerika.audio.set_mute {muted}`. Verify with `amerika.system.status` and report the value you read.

Rules: follow the voice-and-notifications skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
