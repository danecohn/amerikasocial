---
description: "One-screen status of this computer: system, power, network, windows, hardware, services"
allowed-tools: mcp__amerika__agent_status, mcp__plugin_amerika-os_amerika__agent_status, mcp__amerika__bar_get, mcp__plugin_amerika-os_amerika__bar_get, mcp__amerika__hw_report, mcp__plugin_amerika-os_amerika__hw_report, mcp__amerika__studio_status, mcp__plugin_amerika-os_amerika__studio_status, mcp__amerika__system_info, mcp__plugin_amerika-os_amerika__system_info, mcp__amerika__system_status, mcp__plugin_amerika-os_amerika__system_status, mcp__amerika__units_status, mcp__plugin_amerika-os_amerika__units_status, mcp__amerika__windows_list, mcp__plugin_amerika-os_amerika__windows_list
---

Report the state of this computer. Read-only. Call, in this order: `amerika.system.info`, `amerika.system.status`, `amerika.windows.list`, `amerika.units.status`, `amerika.bar.get`, `amerika.hw.report` (skip quietly if not installed), `amerika.agent.status`, `amerika.studio.status` (skip if not installed).
Summarise in under 15 lines: OS and uptime, home mode and dock, battery and power profile, network, volume and brightness, open windows (titles only), anything failing. Flag problems; fix nothing.

Rules: follow the amerika-os-overview skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
