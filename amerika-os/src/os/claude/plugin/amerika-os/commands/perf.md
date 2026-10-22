---
description: "Switch the performance mode: game or balanced (asks for administrator approval)"
argument-hint: "game | balanced"
allowed-tools: mcp__amerika__hw_report, mcp__plugin_amerika-os_amerika__hw_report, mcp__amerika__system_status, mcp__plugin_amerika-os_amerika__system_status
---

Requested mode: $ARGUMENTS (must be exactly `game` or `balanced`; otherwise ask which).
1. Read `amerika.hw.report` (clocks, temperatures) and `amerika.system.status` (power profile, battery) for the "before" picture.
2. Tell the user in two sentences what the mode does (game pins CPU and GPU clocks high until reboot, costs battery and heat; balanced restores) and that an administrator dialog will appear. Wait for a yes.
3. Call `amerika.hw.perf {mode}` (critical: it asks every time). For game also offer `amerika.power.set_profile {profile: "performance"}` and do it only if they say yes.
4. Verify with `amerika.hw.report` again and report the before and after clocks you actually read. If the dialog was cancelled, say the mode is unchanged.

Rules: follow the hardware-surface-laptop-7 skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
