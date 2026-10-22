---
description: "Set the screen brightness"
argument-hint: "1-100 | up | down"
allowed-tools: mcp__amerika__system_status, mcp__plugin_amerika-os_amerika__system_status
---

Request: $ARGUMENTS. Read `amerika.system.status`. up/down means a step of 10. `amerika.display.set_brightness {percent}` (1-100). Verify with `amerika.system.status` and report what you read.

Rules: follow the system-settings skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
