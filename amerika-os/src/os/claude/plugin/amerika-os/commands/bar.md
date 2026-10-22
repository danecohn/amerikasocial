---
description: "Show or change the top bar (widgets, preset, height, opacity)"
argument-hint: "show | preset classic|home | height N | opacity N | hide WIDGET | show WIDGET"
allowed-tools: mcp__amerika__bar_get, mcp__plugin_amerika-os_amerika__bar_get
---

Request: $ARGUMENTS. Always start with `amerika.bar.get` and remember the old values. Empty or "show": describe the layout in words (widgets by zone, enabled or not, height, opacity). Otherwise apply with `amerika.bar.set`: `preset` (classic|home), `height` (28-64), `opacity` (0.3-1), or `layout` (send the full widget list with the one widget's `enabled` or `zone` changed; ids: launcher, home, ai_apps, title, pager, clock, date, ai_chip, agent_chip, status, tray, bell). Verify with `amerika.bar.get`, report old and new values, and say how to undo.

Rules: follow the operate-desktop skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
