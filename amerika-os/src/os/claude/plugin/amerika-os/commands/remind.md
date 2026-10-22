---
description: "Remind me later with a notification"
argument-hint: "when what  (for example: 20m stand up)"
---

Request: $ARGUMENTS (a time such as 20m, 2h or 2026-10-22 09:00, then the text). Compute the exact moment and repeat it back. Ask for approval of this one command, then run it with `amerika.shell.run`: `systemd-run --user --unit=amerika-reminder-SLUG --on-active=20m notify-send "Reminder" "TEXT"` (use `--on-calendar="YYYY-MM-DD HH:MM"` for a clock time; quote safely, no shell metacharacters from the user text). Verify with `amerika.shell.run` `systemctl --user list-timers --no-pager` and say when it will fire. Tell the user it vanishes on reboot.

Rules: follow the schedule-and-automation skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
