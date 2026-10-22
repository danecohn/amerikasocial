---
description: "Open, close or cycle the Caster (Claude / ChatGPT switcher)"
argument-hint: "[next | prev | close]"
---

Argument: $ARGUMENTS. Map it to `amerika.ui.caster {op}`: empty means toggle; next, prev and close as given. The user chooses a card with the keyboard; you cannot press Enter for them. Report what you did and that the Caster is an on-screen overlay you cannot see (use `amerika.screenshot.take` only if the user allows it).

Rules: follow the operate-desktop skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
