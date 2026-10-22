---
description: "Compose or change chiptune music in AmerikaBox"
argument-hint: "description"
allowed-tools: mcp__amerika__studio_status, mcp__plugin_amerika-os_amerika__studio_status
---

Brief: $ARGUMENTS. `amerika.studio.status`, `box_song_get`, then `box_song_compose_from_description` or `box_song_apply_change`. Verify with `box_song_get` (tempo, key, instruments) and `box_play`; you cannot hear it, so say what the song data contains rather than how it sounds. `box_export_wav` only if asked.

Rules: follow the game-dev-studio skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
