---
description: "Log out of the Amerika session (always confirm)"
---

Logging out closes every app including this chat. Ask the user to save work, wait for a clear yes, then run with `amerika.shell.run` (critical, approved each time): `loginctl terminate-session "$XDG_SESSION_ID"`. Do not claim success afterwards; the connection ends.

Rules: follow the privacy-and-safety skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
