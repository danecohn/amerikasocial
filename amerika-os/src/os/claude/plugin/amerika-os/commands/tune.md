---
description: "Explain the opt-in system tuning (zram, file-watch limits, shader cache) and how to undo it"
argument-hint: "apply | revert"
allowed-tools: mcp__amerika__hw_report, mcp__plugin_amerika-os_amerika__hw_report
---

Argument: $ARGUMENTS. `amerika-hw tune apply|revert` changes system settings and needs the user at a terminal with an administrator prompt, so you do not run it. Read `amerika.hw.report` (memory, swap, advice) and explain in plain words what apply would change and why it may help this machine, then give the exact command (`amerika-hw tune apply` or `amerika-hw tune revert`). Make clear that revert undoes everything. After they run it, verify with `amerika.hw.report`.

Rules: follow the hardware-surface-laptop-7 skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
