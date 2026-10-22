---
description: "Focus mode for a task: Do Not Disturb, quiet desktop, optional mute"
argument-hint: "task | off | mute"
allowed-tools: mcp__amerika__system_status, mcp__plugin_amerika-os_amerika__system_status, mcp__amerika__windows_list, mcp__plugin_amerika-os_amerika__windows_list
---

Request: $ARGUMENTS. Read `amerika.system.status` (note the volume) and `amerika.windows.list`. For a task: `amerika.notifications.set_dnd {on: true}`; mute with `amerika.audio.set_mute` only if "mute" was said; do NOT close or minimize windows unless asked. For `off`: DND off and unmute only if you muted. Verify with the returned DND state and `amerika.system.status`, then say exactly what is on and how to undo it. Optionally offer `amerika.notifications.send` as a reminder when the task is done.

Rules: follow the voice-and-notifications skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
