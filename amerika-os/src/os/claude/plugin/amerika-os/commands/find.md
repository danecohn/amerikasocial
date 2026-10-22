---
description: "Find files by name in your home directory"
argument-hint: "name or part of it"
allowed-tools: mcp__amerika__files_list, mcp__plugin_amerika-os_amerika__files_list
---

Looking for: $ARGUMENTS. Walk likely folders with `amerika.files.list` (home, Documents, Downloads, Projects, Desktop), one level at a time, matching names case-insensitively. Do not read file contents to search. For a deep search offer one read-only `amerika.shell.run` such as `find ~ -iname '*NAME*' -not -path '*/.*' 2>/dev/null | head -50` (the user approves it). Report paths and say honestly when nothing matched.

Rules: follow the files-and-projects skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
