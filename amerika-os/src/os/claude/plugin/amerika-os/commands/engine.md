---
description: "Build or change a game in Amerika Engine (Godot)"
argument-hint: "description"
allowed-tools: mcp__amerika__studio_status, mcp__plugin_amerika-os_amerika__studio_status
---

Brief: $ARGUMENTS. `amerika.studio.status`, `engine_project_info`. For a new game follow the recipe flow: `engine_recipe_get`, `engine_recipe_assemble`, `engine_recipe_validate`. For changes use `engine_scene_describe`, `engine_script_create`, `engine_script_edit`, `engine_node_add`. Verify by `engine_project_run`, `engine_project_logs` (errors first) and `engine_game_screenshot`; report what you saw. Offer `engine_history_undo` if it went wrong.

Rules: follow the game-dev-studio skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
