---
description: "Read recent errors from the user journal (secrets are redacted)"
argument-hint: "[unit] [since]"
allowed-tools: mcp__amerika__journal_read, mcp__plugin_amerika-os_amerika__journal_read
---

Request: $ARGUMENTS. `amerika.journal.read {lines: 100, priority: "err"}` and add `unit` (a user unit name) and `since` (such as "1 hour ago") if given. Summarise the distinct problems with their time and unit, newest first; do not paste long logs. If you still see something that looks like a key or token, do not repeat it.

Rules: follow the diagnose-and-repair skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
