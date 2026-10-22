---
description: "Propose how to organise a folder (nothing is moved or deleted without your approval)"
argument-hint: "folder"
allowed-tools: mcp__amerika__files_list, mcp__plugin_amerika-os_amerika__files_list
---

Folder: $ARGUMENTS. Step 1, look only: `amerika.files.list {path}`. Step 2, propose a plan: which files go into which new subfolders, as a table, with counts. Step 3, STOP and wait for the user to approve the plan. Never delete in this command; deletion is a separate request and goes through `amerika.files.delete` (trash) one path at a time. After approval, move files in small batches (each move is one approved `amerika.shell.run` such as `mv -n`), and verify with `amerika.files.list` that source and destination match the plan.

Rules: follow the files-and-projects skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
