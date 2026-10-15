extends Node
var failures := 0
func check(value: bool, label: String) -> void:
 if value: print("PASS ", label)
 else:
  failures += 1
  push_error(label)
func _ready() -> void:
 run.call_deferred()
func run() -> void:
 GameState.cli["skip-intro"] = "1"
 var office: Node = load("res://scenes/office.tscn").instantiate()
 add_child(office)
 await get_tree().process_frame
 await get_tree().process_frame
 var assistant: ShopAssistant = office.assistant
 check(assistant._face != null, "Pickle animation exists")
 check(assistant._face.get_viewport() == assistant._face_viewport, "Pickle animation has its own display")
 check(not assistant._viewport.is_ancestor_of(assistant._face), "Terminal cannot render the pickle face")
 check(assistant._face_mat != null, "Right console has a face material")
 var terminal_mesh := NodeFinder.find_mesh(assistant._crt)
 check(terminal_mesh != null and terminal_mesh.material_override != assistant._face_mat, "Terminal and right display use distinct materials")
 check(terminal_mesh.material_override.albedo_texture == assistant._viewport.get_texture(), "Terminal keeps its text viewport")
 AudioManager.set_voice_duck(true, -12.0, 0.0, "phone")
 AudioManager.set_voice_duck(true, -12.0, 0.0, "assistant")
 await get_tree().process_frame
 await get_tree().process_frame
 check(AudioManager._voice_duck_now < -11.0, "Background is lowered during speech")
 AudioManager.set_voice_duck(false, -12.0, 0.0, "phone")
 await get_tree().process_frame
 await get_tree().process_frame
 check(AudioManager._voice_duck_now < -11.0, "Phone ending does not unduck another speaker")
 AudioManager.set_voice_duck(false, -12.0, 0.0, "assistant")
 await get_tree().process_frame
 await get_tree().process_frame
 check(absf(AudioManager._voice_duck_now) < 0.01, "Background returns after all speech ends")
 var stream := AudioStreamWAV.new()
 stream.format = AudioStreamWAV.FORMAT_16_BITS
 stream.mix_rate = 44100
 var samples := PackedByteArray()
 samples.resize(8820)
 stream.data = samples
 assistant._play_voice(stream)
 check(assistant._voice_player is AudioStreamPlayer, "Dialogue uses clear non-positional playback")
 check(assistant._voice_player.bus == "Voice", "Dialogue has a dedicated voice bus")
 office.queue_free()
 await get_tree().process_frame
 print("AMERIKA_GAME_CHECK_FAILURES=", failures)
 get_tree().quit(0 if failures == 0 else 1)
