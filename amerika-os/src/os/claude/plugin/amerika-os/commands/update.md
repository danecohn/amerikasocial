---
description: "Check for updates and guide the upgrade"
argument-hint: "check | amerika"
---

Argument: $ARGUMENTS. Read-only first: `amerika.shell.run` `apt list --upgradable 2>/dev/null` and `dpkg -l 'amerika-*'` (the user approves each), plus `amerika-channel status`. Summarise what could be updated (Amerika vs Ubuntu, security first). For the upgrade itself, open `amerika.ui.settings {page: "updates"}` (or Amerika Software for Amerika packages) and let the user press refresh/upgrade and approve the dialog. Warn about reboot-required and kernel updates. Never run dist-upgrade or apt remove.

Rules: follow the software-and-updates skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
