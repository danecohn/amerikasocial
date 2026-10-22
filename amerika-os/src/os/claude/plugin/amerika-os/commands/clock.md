---
description: "Clock format: 12/24 hour, seconds, date style"
argument-hint: "12h | 24h | seconds on|off | date none|short|long|numeric"
allowed-tools: mcp__amerika__bar_get, mcp__plugin_amerika-os_amerika__bar_get
---

Request: $ARGUMENTS. `amerika.bar.get` first (see `bar_clock_format`). Then `amerika.bar.set {clock_format: {...}}` with only what changes: `hour24` true/false for 24h/12h, `seconds` true/false, `date` none|short|long|numeric. Verify with `amerika.bar.get`; tell the user what the bar should now show.

Rules: follow the operate-desktop skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
