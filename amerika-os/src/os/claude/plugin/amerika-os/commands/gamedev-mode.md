---
description: "Game development mode: performance profile, quiet notifications, Studio ready"
argument-hint: "on | off"
allowed-tools: mcp__amerika__hw_report, mcp__plugin_amerika-os_amerika__hw_report, mcp__amerika__studio_status, mcp__plugin_amerika-os_amerika__studio_status, mcp__amerika__system_status, mcp__plugin_amerika-os_amerika__system_status
---

Argument: $ARGUMENTS. Read `amerika.system.status`, `amerika.hw.report` and `amerika.studio.status` for the "before". on: tell the user the plan (performance profile, DND, optionally hw.perf game with its administrator dialog, open the Amerika Studio hub) and wait for a yes; then `amerika.power.set_profile {profile: "performance"}`, `amerika.notifications.set_dnd {on: true}`, optionally `amerika.hw.perf {mode: "game"}`, and `amerika.apps.launch` for the Studio hub if installed. off: restore balanced (`amerika.power.set_profile`, `amerika.hw.perf {mode: "balanced"}` if game was set), DND off. Verify with `amerika.system.status` and `amerika.hw.report`; report what changed and the battery/heat cost.

Rules: follow the hardware-surface-laptop-7 skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
