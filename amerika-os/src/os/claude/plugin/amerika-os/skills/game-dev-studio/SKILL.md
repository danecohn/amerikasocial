---
name: game-dev-studio
description: Build games and assets with Amerika Studio - Render (Blender), Engine (Godot), Sprite (pixel art) and Box (chiptune music) - through the amerika-studio MCP tools, including the Godot recipe workflow and visual verification. Use when the user wants to make, change, run or export a game, 3D model, sprite or music.
---

# Game development with Amerika Studio

Studio is optional (`amerika-developer`). Check first: `amerika.studio.status` (bridge, whether an Anthropic key is set - yes/no only, budget, running apps). If it errors "not installed", tell the user to install **Amerika Developer Edition** with Amerika Software. If the status says no key, the user must enter it in Amerika Studio (hub) or Settings > Amerika Studio; you never handle the key.

The studio tools come from the `amerika-studio` MCP server and are named `<app>_<tool>` with dots as underscores: `engine_project_info`, `render_scene_info`, `sprite_canvas_info`, `box_song_get`, plus `studio_status` and `studio_launch {app}`. If the app is not running the server launches it and waits until ready. Files are confined to the project folder `~/Studio/<App>/...`; anything outside is refused.

## Common loop (all apps)
1. **Inspect:** the `*_info`/`*_get`/`*_describe` read tool. Never edit blind.
2. **Change in small steps** with the specific tools, or hand a natural-language job to the app's own assistant with `<app>_app_prompt` (same chat panel the user sees; returns its reply and a summary of its tool calls).
3. **Verify visually/audibly:** `render_viewport_screenshot`, `engine_game_screenshot`, `sprite_canvas_info`, `box_play`. Look at the returned image; describe what is actually there, not what you intended.
4. **Undo path:** Engine keeps history: `engine_history_list`, `engine_history_undo`, `engine_history_redo`. Tell the user how to roll back.

## Engine (Godot) recipe workflow
1. `engine_project_info` (project dir, Godot version, main scene, whether running). New project: the user runs `amerika-studio new-game NAME` or the hub's New game; ask for a name.
2. `engine_recipe_get` with no name lists genre recipes (platformer, top-down, shooter, puzzle, ...). Pick with the user.
3. `engine_recipe_assemble {name | description}` builds a playable skeleton; `engine_recipe_validate` must report no problems before continuing.
4. Iterate: `engine_scene_describe`, `engine_script_create` / `engine_script_edit` (instruction-based, undo copy kept), `engine_node_add`, `engine_node_set_property`, `engine_script_attach`, `engine_input_set`, `engine_import_model` (glb from Render).
5. `engine_project_run`, then `engine_project_logs` (errors first), `engine_game_screenshot` to judge the result, `engine_project_stop`.
6. Export: `engine_export_set_preset`, then ask the user to export from Godot; use the Vulkan renderer on this hardware.
Rules: `engine_files_write` needs `overwrite: true` to replace a file - only after reading it. Do not claim "it runs" without logs and a screenshot.

## Render (Blender)
`render_scene_info` -> `render_model_create_from_description` / `render_model_apply_change` -> `render_viewport_screenshot` -> `render_export` (e.g. glb into the project). `render_scene_run_python` is **critical**: the user must approve the exact code each time; prefer the model tools. Never run code that touches files outside the project or the network.

## Sprite and Box
Sprite: `sprite_canvas_info`, `sprite_palette_get`, `sprite_canvas_describe_to_sprite`, `sprite_canvas_apply_change`, frames (`sprite_frames_list|add|duplicate|delete|select|set_duration`), `sprite_export` (PNG, GIF, sheet). Box: `box_song_get`, `box_song_compose_from_description`, `box_song_apply_change`, `box_play`, `box_stop`, `box_export_wav`.

## Cost and limits
Each app-assistant call spends the user's Anthropic budget (daily token budget in the hub; `studio.status` shows it). Prefer direct tools for simple edits. If a call fails with a budget or key error, stop and tell the user; do not retry.

## Safety
Do not read the Studio key or token files. Do not export or publish anything without being asked. Code the model writes (GDScript, bpy) runs only inside the apps with the user's review settings.

## Failure handling
App not ready (-32004): wait and `studio_launch`; busy (-32002): retry once later; denied (-32001): the user declined; path outside project (-32003): choose a path under `~/Studio`.
