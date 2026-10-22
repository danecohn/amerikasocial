---
description: "Status of Amerika Studio and its four apps; open one"
argument-hint: "status | render | engine | sprite | box"
allowed-tools: mcp__amerika__studio_status, mcp__plugin_amerika-os_amerika__studio_status
---

Argument: $ARGUMENTS. `amerika.studio.status` (bridge, key present yes/no, budget, running apps). If Studio is not installed, say Amerika Developer Edition is needed (Amerika Software). If asked to open an app, call `studio_launch {app}` from the studio server and verify with `amerika.studio.status`. Never read or show keys.

Rules: follow the game-dev-studio skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
