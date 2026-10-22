---
description: "Read or set the clipboard"
argument-hint: "show | set TEXT"
---

Request: $ARGUMENTS. The clipboard may contain passwords: before `amerika.clipboard.get`, tell the user you are about to read it and why. Show it, but if it looks like a secret, say so without printing it. `set TEXT` uses `amerika.clipboard.set {text}` for exactly the text given; verify by saying what you set (reading it back needs the same permission).

Rules: follow the privacy-and-safety skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
