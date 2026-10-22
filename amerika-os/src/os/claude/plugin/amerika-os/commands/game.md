---
description: "Orchestrate a whole game: code, art, model and music from one idea"
argument-hint: "game idea"
allowed-tools: mcp__amerika__studio_status, mcp__plugin_amerika-os_amerika__studio_status
---

Idea: $ARGUMENTS. Plan first and show the user a short plan: genre/recipe, project name, and which of the four apps makes which asset; wait for a yes. Check `amerika.studio.status` (stop with instructions if Studio or its key is missing; mind the token budget). Then, in order: Engine skeleton (`engine_recipe_get`, `engine_recipe_assemble`, `engine_recipe_validate`); Sprite art (`sprite_canvas_describe_to_sprite`, `sprite_export`); Render model if 3D (`render_model_create_from_description`, `render_export`, then `engine_import_model`); Box music (`box_song_compose_from_description`, `box_export_wav`); wire up with `engine_script_create`/`engine_node_add`. Finish with `engine_project_run`, `engine_project_logs`, `engine_game_screenshot`. Report what runs and what does not, with evidence; list anything you skipped.

Rules: follow the game-dev-studio skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
