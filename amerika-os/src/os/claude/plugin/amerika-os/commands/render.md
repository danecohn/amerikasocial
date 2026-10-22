---
description: "Make or change a 3D model in Amerika Render (Blender)"
argument-hint: "description"
allowed-tools: mcp__amerika__studio_status, mcp__plugin_amerika-os_amerika__studio_status
---

Brief: $ARGUMENTS. Check `amerika.studio.status`, then `render_scene_info`. Create or change with `render_model_create_from_description` or `render_model_apply_change` (not `render_scene_run_python`, which is critical and needs approval of the exact code). Verify with `render_viewport_screenshot` and describe what is actually visible. Export with `render_export` only if asked.

Rules: follow the game-dev-studio skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
