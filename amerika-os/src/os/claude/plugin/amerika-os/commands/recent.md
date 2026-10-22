---
description: "Show recently changed files in your home directory"
argument-hint: "[days, default 2]"
---

Days: $ARGUMENTS (default 2). There is no tool with modification times, so propose one `amerika.shell.run` command and wait for approval: `find ~ -type f -mtime -N -not -path '*/.*' -printf '%TY-%Tm-%Td %TH:%TM %p\n' 2>/dev/null | sort -r | head -40`. Show the result as given.

Rules: follow the files-and-projects skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
