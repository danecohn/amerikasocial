---
description: "Open Bluetooth settings (pairing is done by the user)"
---

There is no tool that pairs or lists Bluetooth devices. Open the page with `amerika.ui.settings {page: "bluetooth"}` and tell the user the steps: switch Bluetooth on, put the device in pairing mode, pick it in the list. Do not claim anything about device state.

Rules: follow the system-settings skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
