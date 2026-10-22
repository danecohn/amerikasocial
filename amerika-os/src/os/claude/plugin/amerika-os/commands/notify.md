---
description: "Show a desktop notification"
argument-hint: "title | body"
allowed-tools: mcp__amerika__notifications_list, mcp__plugin_amerika-os_amerika__notifications_list
---

Text: $ARGUMENTS (split at the first "|" into title and body). `amerika.notifications.send {title, body}`. Keep it short. Verify with `amerika.notifications.list {limit: 3}` and report what you see.

Rules: follow the voice-and-notifications skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
