---
description: "Make ChatGPT the home AI app, or just open it"
argument-hint: "[open]"
allowed-tools: mcp__amerika__apps_list, mcp__plugin_amerika-os_amerika__apps_list, mcp__amerika__bar_get, mcp__plugin_amerika-os_amerika__bar_get, mcp__amerika__windows_list, mcp__plugin_amerika-os_amerika__windows_list
---

Argument: $ARGUMENTS. Read `amerika.bar.get` for `home_mode`. If the user said "open", or `home_mode` is off, use `amerika.apps.list {query: "chatgpt"}` then `amerika.apps.launch` with the exact id (if none is installed, say so). Otherwise set `amerika.settings.set {key: "home_mode", value: "chatgpt"}` after telling the user that Claude stops being the home view, and how to switch back (`/amerika-os:claude-mode`). Verify with `amerika.bar.get` and `amerika.windows.list`.

Rules: follow the operate-desktop skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
