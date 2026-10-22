---
description: "Hardware report: CPU, memory, GPU/Vulkan, thermals, NPU, with advice"
allowed-tools: mcp__amerika__hw_report, mcp__plugin_amerika-os_amerika__hw_report, mcp__amerika__system_info, mcp__plugin_amerika-os_amerika__system_info, mcp__amerika__system_status, mcp__plugin_amerika-os_amerika__system_status
---

Run `amerika.hw.report`. If it fails with "not installed", say the user needs the amerika-gamedev package and fall back to `amerika.system.status` and `amerika.system.info`. Summarise: CPU and governor, memory and swap/zram, Vulkan device and driver, GPU clocks, temperatures, NPU status (state plainly that the NPU cannot run anything or speed up games here), and the report's advice. Quote numbers exactly as read; write "unknown" where the report has no value.

Rules: follow the hardware-surface-laptop-7 skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
