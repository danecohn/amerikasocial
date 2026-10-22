---
description: "Switch to Claude-first mode: Claude home view, Caster on the Copilot key, no dock"
argument-hint: "chatgpt"
allowed-tools: mcp__amerika__bar_get, mcp__plugin_amerika-os_amerika__bar_get, mcp__amerika__windows_list, mcp__plugin_amerika-os_amerika__windows_list
---

Argument: $ARGUMENTS (empty = Claude first; `chatgpt` = ChatGPT first). Read `amerika.bar.get`. Tell the user what changes (home app fills the screen under the bar, dock hidden, Copilot key opens the Caster, home bar layout) and how to undo (`/amerika-os:classic-mode`). After a yes call `amerika.ui.mode {mode: "claude"}` or `{mode: "chatgpt"}`. Verify with `amerika.bar.get` and `amerika.windows.list`. Note that the real apps' behaviour under the window rules has not been verified on the laptop.

Rules: follow the operate-desktop skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
