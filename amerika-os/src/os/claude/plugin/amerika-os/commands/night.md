---
description: "Open the night light and colour settings"
---

Night light lives on the Displays page and has no tool. Open it with `amerika.ui.settings {page: "display"}` and tell the user to enable Night light and pick the schedule. Brightness can be set directly (`amerika.display.set_brightness`) if they ask. Do not claim it is on.

Rules: follow the system-settings skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
