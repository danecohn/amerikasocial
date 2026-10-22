---
description: "Set the power profile: power-saver, balanced or performance"
argument-hint: "power-saver | balanced | performance"
allowed-tools: mcp__amerika__system_status, mcp__plugin_amerika-os_amerika__system_status
---

Request: $ARGUMENTS. Read `amerika.system.status` (profile, battery). `performance` costs battery and heat, `power-saver` slows builds: say which in one sentence. Then `amerika.power.set_profile {profile}` and verify with `amerika.system.status`.

Rules: follow the hardware-surface-laptop-7 skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
