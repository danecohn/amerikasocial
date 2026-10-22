---
description: "Open an application by name"
argument-hint: "app name"
allowed-tools: mcp__amerika__apps_list, mcp__plugin_amerika-os_amerika__apps_list, mcp__amerika__windows_list, mcp__plugin_amerika-os_amerika__windows_list
---

Application wanted: $ARGUMENTS. `amerika.apps.list {query}`; if there is one clear match, `amerika.apps.launch {id}` with the exact id; if several, ask; if none, say so (do not install anything; offer `/amerika-os:install`). Wait a moment, then verify with `amerika.windows.list` that a window appeared and say if it did not.

Rules: follow the operate-desktop skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
