---
description: "Close all windows of an application"
argument-hint: "app name"
allowed-tools: mcp__amerika__apps_list, mcp__plugin_amerika-os_amerika__apps_list, mcp__amerika__windows_list, mcp__plugin_amerika-os_amerika__windows_list
---

Application to close: $ARGUMENTS. Find it with `amerika.windows.list` and `amerika.apps.list {query}`. Warn that unsaved work may be lost, list the windows that would close, and wait for a yes (never close the Claude app this chat runs in without explicit confirmation). Then `amerika.apps.close {id}`. Verify with `amerika.windows.list`.

Rules: follow the operate-desktop skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
