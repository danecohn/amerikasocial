---
description: "Text size of the Claude or ChatGPT app (0.8 to 2.0)"
argument-hint: "claude|chatgpt scale"
allowed-tools: mcp__amerika__bar_get, mcp__plugin_amerika-os_amerika__bar_get
---

Request: $ARGUMENTS (app and a scale such as 1.25). `amerika.bar.get` shows the current `ai_text_scale`. Set it with `amerika.ui.text_scale {app, scale}`; it applies at the app's next start. Restarting now closes the app and the chat you are in: explain that and call `amerika.ui.relaunch {app}` only if the user clearly says yes. Verify with `amerika.bar.get`. Note that an app which ignores the Chromium scale flag will not change.

Rules: follow the system-settings skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
