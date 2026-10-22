---
description: "List a folder in your home directory"
argument-hint: "path (default ~)"
allowed-tools: mcp__amerika__files_list, mcp__plugin_amerika-os_amerika__files_list
---

Folder: $ARGUMENTS (default home). `amerika.files.list {path}`. Show folders first, sizes in readable units, at most 60 entries; say if the list was cut. Home folder only; protected places show names but cannot be read.

Rules: follow the files-and-projects skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
