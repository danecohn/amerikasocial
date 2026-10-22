---
description: "Diagnose a symptom and fix it with the smallest safe step"
argument-hint: "what is wrong"
allowed-tools: mcp__amerika__hw_report, mcp__plugin_amerika-os_amerika__hw_report, mcp__amerika__journal_read, mcp__plugin_amerika-os_amerika__journal_read, mcp__amerika__notifications_list, mcp__plugin_amerika-os_amerika__notifications_list, mcp__amerika__system_status, mcp__plugin_amerika-os_amerika__system_status, mcp__amerika__units_status, mcp__plugin_amerika-os_amerika__units_status, mcp__amerika__windows_list, mcp__plugin_amerika-os_amerika__windows_list
---

Symptom: $ARGUMENTS. Observe with read tools only (`amerika.system.status`, `amerika.journal.read`, `amerika.units.status`, `amerika.hw.report`, `amerika.windows.list`, `amerika.notifications.list`). State the most likely cause with the evidence (time, unit, value). Propose the smallest reversible fix and wait for the user's yes before any change; allowed fixes are the dedicated tools (`amerika.units.restart` for amerika-* services, `amerika.windows.restore`, `amerika.audio.set_mute`, `amerika.network.set_wifi`, `amerika.power.set_profile`). After the fix repeat the observation that showed the problem and report before and after. If it is not fixed, say so and stop after two attempts.

Rules: follow the diagnose-and-repair skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
