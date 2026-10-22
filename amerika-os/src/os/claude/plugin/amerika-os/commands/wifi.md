---
description: "Turn Wi-Fi on or off"
argument-hint: "on | off"
allowed-tools: mcp__amerika__system_status, mcp__plugin_amerika-os_amerika__system_status
---

Argument: $ARGUMENTS. Read `amerika.system.status` (network). Turning Wi-Fi off can cut the connection this chat uses: warn and confirm first. Then `amerika.network.set_wifi {on}`. Verify with `amerika.system.status`.

Rules: follow the system-settings skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
