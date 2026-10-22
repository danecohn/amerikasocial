extends SceneTree
# Drives the real ai_client.gd tool loop against a fake bridge (AMERIKA_STUDIO_URL / AMERIKA_STUDIO_TOKEN_FILE).
const Tools := preload("res://addons/amerika_engine/tools.gd")
const AiClient := preload("res://addons/amerika_engine/ai_client.gd")


func _initialize() -> void:
	var tools := Tools.new(self)
	var ai := AiClient.new()
	ai.tools = tools
	ai.review = false
	root.add_child(ai)
	var res: Dictionary = await ai.run_prompt(OS.get_environment("AMERIKA_TEST_PROMPT"))
	print("LOOP_RESULT " + JSON.stringify(res))
	quit(0 if res.get("ok", false) else 1)
