---
name: schedule-and-automation
description: Schedule tasks and reminders on AltStack Desktop with systemd user timers (and cron when needed) safely - one-off reminders, recurring scripts, listing and removing them. Use when the user asks to do something later, every day, on a schedule, at login, or to remove such automation.
---

# Schedule and automation

**Principle:** prefer systemd **user** timers. They run as the user, are inspectable and removable. Never schedule anything with elevated rights, and never schedule something the user has not seen in full. Creating a timer is persistent change: ask first, show the exact unit text.

## Tools you have
- Read: `amerika.units.status` (lists `amerika-*` user units), `amerika.journal.read {unit}` for results.
- Scripts and notes: `amerika.files.write` under `~/Projects/automation/` (allowed). Units under `~/.config/systemd/user` are **protected** from the file tools on purpose.
- `amerika.shell.run` (critical, asked every time, 30 s) to talk to systemd.
- `amerika.notifications.send` for the "notify me" part.

## One-off reminder (no files)
Ask for the time; then, after approval of the command:
`systemd-run --user --unit=amerika-reminder-<short-slug> --on-active=45m notify-send "Reminder" "Stand up"` (relative) or `--on-calendar="2026-10-22 09:00"` (absolute). It disappears after firing and on reboot (transient). Say that. Verify: `systemctl --user list-timers --no-pager`.

## Recurring task (persistent)
1. Write the script with `amerika.files.write {path: "~/Projects/automation/<name>.sh", text}`: start with `#!/bin/sh` and `set -eu`; do one thing; log to stdout (the journal captures it); no secrets, no `sudo`, no network unless the user asked, no deleting.
2. Show the user the script and the two unit files, and ask for a yes:
   - `amerika-task-<name>.service`: `[Service]` `Type=oneshot`, `ExecStart=/bin/sh %h/Projects/automation/<name>.sh`
   - `amerika-task-<name>.timer`: `[Timer]` `OnCalendar=...`, `Persistent=true`; `[Install]` `WantedBy=timers.target`
3. With the user's approval of the exact command, create the units from one `amerika.shell.run` command (a here-doc into `~/.config/systemd/user/`, then `systemctl --user daemon-reload && systemctl --user enable --now amerika-task-<name>.timer`). If the user would rather do it themselves, give them the text.
4. Verify: `amerika.units.status {unit: "amerika-task-<name>.timer"}` and `systemctl --user list-timers`. Say when the next run is.
5. After the first run: `amerika.journal.read {unit: "amerika-task-<name>.service", lines: 30}`; report the actual outcome.

## Listing and removing
- List: `systemctl --user list-timers --all --no-pager`, `amerika.units.status`.
- Remove: `systemctl --user disable --now amerika-task-<name>.timer`, then delete the two unit files and the script (`rm` for the units needs shell.run approval; the script via `amerika.files.delete`), then `systemctl --user daemon-reload`. Only touch units named `amerika-task-*` or `amerika-reminder-*` that you created; never remove other units.

## Cron
Do not edit the crontab: editing replaces the whole file and loses entries. If the user insists, show `crontab -l` first (read), and give them the single line to add themselves.

## Safe patterns
- Use `OnCalendar` with explicit times; avoid per-second or per-minute schedules (battery, noise). Minimum sensible period: 5 minutes.
- Idempotent scripts; `flock -n` if they might overlap.
- Notify on failure only (`OnFailure=` is not needed; have the script call `notify-send` itself on error).
- Never schedule: package installs, `power.*`, deleting user data, anything that reads secrets, or a command that asks Claude to run something later (no self-prompting loops).

## Failure handling
- "Failed to connect to bus": not inside the user session; tell the user.
- Timer not firing: `systemctl --user status <timer>`; check the clock/timezone with `amerika.system.status`; check `Persistent=true`.
- Script fails: read the journal; fix the script with `files.write`; do not widen permissions.
