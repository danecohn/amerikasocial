---
description: "What to do when the bar or shell is frozen (tools cannot restart it)"
allowed-tools: mcp__amerika__system_status, mcp__plugin_amerika-os_amerika__system_status, mcp__amerika__units_status, mcp__plugin_amerika-os_amerika__units_status
---

You cannot restart the Amerika shell (restarting it would cut your own connection, and `amerika.units.restart` refuses it on purpose). Check with `amerika.system.status` and `amerika.units.status` whether the shell answers. If it answers, say so and suggest `/amerika-os:fix` for the actual symptom. If it does not, give the user these steps: Win+Space (app menu) and Win+Q (close the active window); Settings > Home & Caster > Classic desktop; log out and in; if the screen is unusable, Ctrl+Alt+F3 and `amerika-settings --classic` (see `/amerika-os:recover`). Do not promise any of it was tested on the real laptop.

Rules: follow the diagnose-and-repair skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
