"""Apply browser presentation fixes to the isolated Pickle project copy only."""
from pathlib import Path
import argparse
parser=argparse.ArgumentParser();parser.add_argument('project');args=parser.parse_args();root=Path(args.project)
p=root/'scripts/assistant/shop_assistant.gd';s=p.read_text(encoding='utf-8')
if '# AMERIKA_BROWSER_PRESENTATION_V2' not in s:
 s=s.replace('var _face: AnimatedSprite2D','var _face_viewport: SubViewport\nvar _face: AnimatedSprite2D')
 s=s.replace('\t_viewport.add_child(_face)\n\t_viewport.move_child(_face, -1)', '''\t# The terminal is text-only. Animation belongs exclusively to AutoConsole on the right.
\t_face_viewport = SubViewport.new()
\t_face_viewport.name = "RightDisplayAnimation"
\t_face_viewport.size = Vector2i(640, 480)
\t_face_viewport.disable_3d = true
\t_face_viewport.world_2d = World2D.new()
\t_face_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
\tadd_child(_face_viewport)
\t_face_viewport.add_child(_face)''')
 s=s.replace('m.set_shader_parameter("intensity", 0.04)','m.set_shader_parameter("intensity", 0.008)').replace('m.set_shader_parameter("scanlines", 0.6)','m.set_shader_parameter("scanlines", 0.15)')
 s=s.replace('var _voice_player: AudioStreamPlayer3D','var _voice_player: AudioStreamPlayer')
 start=s.index('\tvar pos := Vector3.ZERO\n',s.index('func _play_voice('));end=s.index('\tif _voice_player == null:',start);s=s[:start]+s[end:]
 s=s.replace('_voice_player = AudioStreamPlayer3D.new()','_voice_player = AudioStreamPlayer.new()').replace('_voice_player.bus = "SFX"','_voice_player.bus = "Voice"').replace('\t\t_voice_player.unit_size = 12.0','\t\t_voice_player.volume_db = -2.0').replace('\t_voice_player.global_position = pos\n','')
 s=s.replace('AudioManager.set_voice_duck(true)','AudioManager.set_voice_duck(true, -12.0, 0.15, "assistant")').replace('AudioManager.set_voice_duck(false)','AudioManager.set_voice_duck(false, -12.0, 0.25, "assistant")')
 s=s.replace('VoiceBank.find(["assistant." + id, id], [text, _brain.last_raw], glitchy)','VoiceBank.find(["assistant." + id, id], [text, _brain.last_raw], false)')
 s+='\n\n# AMERIKA_BROWSER_PRESENTATION_V2\nfunc _exit_tree() -> void:\n\tAudioManager.set_voice_duck(false, -12.0, 0.25, "assistant")\n'
 p.write_text(s,encoding='utf-8')
p=root/'scripts/autoload/audio_manager.gd';s=p.read_text(encoding='utf-8')
if '# AMERIKA_VOICE_MIX_V2' not in s:
 s=s.replace('const BUSES: Array[String] = ["Music", "SFX", "Ambience"]','const BUSES: Array[String] = ["Music", "SFX", "Ambience", "Voice"]')
 s=s.replace('AudioServer.set_bus_send(idx, "Master")','AudioServer.set_bus_send(idx, "SFX" if bus_name == "Voice" else "Master")')
 s=s.replace('var extra: = _voice_duck_now if bus_name == "Ambience" else 0.0','var extra: = _voice_duck_now + (-3.0 if bus_name == "Ambience" and _voice_duck_now < 0.0 else 0.0)')
 s=s.replace('var _voice_duck_tween: Tween','var _voice_duck_tween: Tween\nvar _voice_sources: Dictionary = {}')
 start=s.index('func set_voice_duck(');end=s.index('\n\nfunc set_bus_volume',start)
 s=s[:start]+'''# AMERIKA_VOICE_MIX_V2
func set_voice_duck(on: bool, amount_db: float = -12.0, time: float = 0.2, source: String = "speech") -> void:
\tif on:
\t\t_voice_sources[source] = amount_db
\telse:
\t\t_voice_sources.erase(source)
\tvar target := 0.0
\tfor value in _voice_sources.values():
\t\ttarget = minf(target, float(value))
\tif _voice_duck_tween:
\t\t_voice_duck_tween.kill()
\t_voice_duck_tween = create_tween()
\t_voice_duck_tween.tween_method(func(v: float) -> void:
\t\t_voice_duck_now = v
\t\t_apply_duck(_duck_now), _voice_duck_now, target, time)
'''+s[end:]
 # Preserve positional volume cues for effects without their default heavy low-pass coloration.
 s=s.replace('\tp.unit_size = 4.0','\tp.unit_size = 4.0\n\tp.attenuation_filter_cutoff_hz = 18000.0\n\tp.attenuation_filter_db = -1.0')
 p.write_text(s,encoding='utf-8')
p=root/'scripts/office/phone_call.gd';s=p.read_text(encoding='utf-8')
if '# AMERIKA_PHONE_MIX_V2' not in s:
 s=s.replace('vp.bus = "SFX"','vp.bus = "Voice"').replace('AudioManager.set_voice_duck(true)','AudioManager.set_voice_duck(true, -12.0, 0.15, "phone")').replace('AudioManager.set_voice_duck(false)','AudioManager.set_voice_duck(false, -12.0, 0.25, "phone")')
 s+='\n\n# AMERIKA_PHONE_MIX_V2\n';p.write_text(s,encoding='utf-8')
print('Pickle browser fixes applied: separate right display, text-only terminal, clear dialogue and overlap-safe music ducking.')
