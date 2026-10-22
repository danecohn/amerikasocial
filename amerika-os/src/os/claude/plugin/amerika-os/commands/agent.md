---
description: "Status of Amerika Agent and how to open it"
allowed-tools: mcp__amerika__agent_status, mcp__plugin_amerika-os_amerika__agent_status
---

`amerika.agent.status` (installed, running, model, permission mode; never any key). If it is installed and not running, tell the user to start it in Settings > Agent (`amerika.ui.settings {page: "agent"}`); you cannot start it or message it. Report only what the status says.

Rules: follow the amerika-os-overview skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
