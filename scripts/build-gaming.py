"""Build isolated web editions; never modifies the supplied desktop projects."""
import argparse,json,re,shutil,subprocess,zipfile,hashlib,sys
from pathlib import Path

parser=argparse.ArgumentParser();parser.add_argument('--godot',required=True);parser.add_argument('--work',required=True);parser.add_argument('--variety',required=True);parser.add_argument('--pickles',required=True);parser.add_argument('--only');args=parser.parse_args()
repo=Path(__file__).resolve().parent.parent;work=Path(args.work);work.mkdir(parents=True,exist_ok=True)
games=[('last-lamp','THE LAST LAMP','The_Last_Lamp'),('saint-marrows',"SAINT MARROW'S",'Saint_Marrows'),('salt-mine-9','SALT MINE 9','Salt_Mine_9'),('ward-seven','WARD SEVEN','Ward_Seven'),('pickles-pickle-shop',"Pickle’s Pickle Shop",'Godot')]
cloud='''extends Node
var elapsed := 0.0
var previous := ""
var flush_callback: JavaScriptObject
func _enter_tree() -> void:
 process_mode = Node.PROCESS_MODE_ALWAYS
 if not OS.has_feature("web"): return
 var raw: String = str(JavaScriptBridge.eval("window.AmerikaCloud.initialFilesJSON", true))
 var files: Variant = JSON.parse_string(raw)
 if files is Dictionary:
  for name in files:
   if not _valid_name(str(name)): continue
   var path: String = "user://" + str(name)
   DirAccess.make_dir_recursive_absolute(path.get_base_dir())
   var file := FileAccess.open(path, FileAccess.WRITE)
   if file: file.store_buffer(Marshalls.base64_to_raw(str(files[name])))
 flush_callback = JavaScriptBridge.create_callback(_flush)
 JavaScriptBridge.get_interface("AmerikaCloud").onFlush = flush_callback
func _valid_name(name: String) -> bool:
 return not name.contains("..") and not name.begins_with("/") and not name.contains(":") and not name.contains("\\\\") and name.get_extension().to_lower() in ["cfg","json","sav","save","dat"]
func _files(path: String, result: Dictionary) -> void:
 var dir := DirAccess.open("user://" + path)
 if not dir: return
 var names := dir.get_files(); names.sort()
 for name in names:
  var full: String = path + name
  if _valid_name(full):
   var bytes := FileAccess.get_file_as_bytes("user://" + full)
   if bytes.size() < 750000: result[full] = Marshalls.raw_to_base64(bytes)
 for name in dir.get_directories():
  if not name.begins_with(".") and name != "logs": _files(path + name + "/", result)
func _process(delta: float) -> void:
 if not OS.has_feature("web"): return
 elapsed += delta
 if elapsed >= 1.0: elapsed = 0.0; _flush([])
func _flush(_arguments: Array) -> void:
 var files: Dictionary = {}; _files("", files)
 var raw := JSON.stringify(files)
 if raw == previous: return
 previous = raw
 JavaScriptBridge.eval("window.AmerikaCloud.setFiles(" + raw + ")", true)
'''
shell='''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Amerika Gaming</title><style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#090909;color:white;font-family:system-ui}canvas{display:block;width:100%;height:100%}#start{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:18px;background:#090909;z-index:5}#start img{width:80px;height:80px}button{background:#c82433;color:white;padding:16px 30px;border:0;border-radius:8px;font-weight:700;font-size:16px;cursor:pointer}#error{max-width:650px;white-space:pre-wrap;padding:20px}small{color:#aaa}</style>$GODOT_HEAD_INCLUDE</head><body><canvas id="canvas">Your browser needs WebGL 2 to play this game.</canvas><div id="start"><img src="amerika-logo.svg" alt="Amerika LLC"><b>AMERIKA LLC</b><h1>GAME_TITLE</h1><small>Presented by Amerika LLC · Original game by Forgotten Woods Studios</small><button id="play" disabled>Connecting cloud save…</button><div id="error" role="status"></div></div><script src="amerika-bridge.js"></script><script src="$GODOT_URL"></script><script>const config=$GODOT_CONFIG;config.persistentPaths=[];const engine=new Engine(config);let started=false;AmerikaCloud.ready.then(()=>{document.querySelector('#play').disabled=false;document.querySelector('#play').textContent='Start playing';});document.querySelector('#play').onclick=async()=>{if(started)return;started=true;document.querySelector('#play').disabled=true;try{await engine.startGame({canvas:document.querySelector('#canvas'),onProgress:(done,total)=>{const progress=document.querySelector('#error');if(progress)progress.textContent=total?'Loading '+Math.round(done/total*100)+'%':'Loading game…';}});document.querySelector('#start').remove();parent.postMessage({type:'amerika.game.started',channel:AmerikaCloud.channel},'*');}catch(error){document.querySelector('#error').textContent='Could not start: '+error.message;started=false;document.querySelector('#play').disabled=false;}};</script></body></html>'''
for slug,title,folder in games:
 if args.only and slug!=args.only:continue
 dest=work/'projects'/slug;output=work/'exports'/slug;output.mkdir(parents=True,exist_ok=True)
 if not (dest/'project.godot').exists():
  if slug=='pickles-pickle-shop':
   shutil.copytree(Path(args.pickles)/'Godot',dest,ignore=shutil.ignore_patterns('.godot','.git','*.import','*.part*','*.zip','*.exe','*.pck','*.log','exports'),dirs_exist_ok=True)
   source=Path(args.pickles)/'Godot'
   for first in source.rglob('*.part00'):
    base=Path(str(first)[:-7]);target=dest/base.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():
     with target.open('wb') as out:
      for part in sorted(first.parent.glob(base.name+'.part*')):
       with part.open('rb') as f:shutil.copyfileobj(f,out)
  else:
   archive=next((Path(args.variety)/title/'PROJECT').glob('*.zip'))
   with zipfile.ZipFile(archive) as z:
    prefix=folder+'/'
    for entry in z.infolist():
     if not entry.filename.startswith(prefix) or entry.is_dir():continue
     relative=Path(entry.filename[len(prefix):])
     if any(p in ['..','.godot','.git','generator'] for p in relative.parts) or relative.suffix in ['.import','.zip']:continue
     target=dest/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(entry))
 if slug!='pickles-pickle-shop':
  game=dest/'kit/game.gd';source=game.read_text()
  source=source.replace('return int(save.get("runs", 0)) > 0 or bool(save.get("seen_intro", false))','return not (save.get("amerika_checkpoint", {}) as Dictionary).is_empty() or int(save.get("runs", 0)) > 0 or bool(save.get("seen_intro", false))');game.write_text(source)
  title_script=dest/'kit/title.gd';source=title_script.read_text()
  source=source.replace('"continue":\n\t\t\tGame.goto("hub")','"continue":\n\t\t\tif not (Game.save.get("amerika_checkpoint", {}) as Dictionary).is_empty():\n\t\t\t\tGame.run = {"opts": true, "amerika_resume": true}\n\t\t\t\tGame.goto("run")\n\t\t\telse:\n\t\t\t\tGame.goto("hub")').replace('FORGOTTEN WOODS STUDIOS" %','AMERIKA LLC / FORGOTTEN WOODS" %');title_script.write_text(source)
  run_script=dest/'kit/run.gd';source=run_script.read_text()
  if 'var _amerika_checkpoint:' not in source:
   source=source.replace('var opts: Dictionary = {}','var opts: Dictionary = {}\nvar _amerika_checkpoint: Dictionary = {}')
   source=source.replace('var dread := int(Game.save.get("dread", 0))','if opts.get("amerika_resume", false):\n\t\t_amerika_checkpoint = (Game.save.get("amerika_checkpoint", {}) as Dictionary).duplicate(true)\n\tvar dread := int(Game.save.get("dread", 0))')
   source=source.replace('\trun = Game.run','\tif not _amerika_checkpoint.is_empty():\n\t\tGame.run = (_amerika_checkpoint.get("run", Game.run) as Dictionary).duplicate(true)\n\trun = Game.run',1)
   source=source.replace('\tvar cli := Game.cli','''\tif not _amerika_checkpoint.is_empty():
\t\trefresh_stats()
\t\tplayer.hp = clampi(int(_amerika_checkpoint.get("hp", 1)), 1, int(player.st["hp"]))
\t\tlight = float(_amerika_checkpoint.get("light", 1.0))
\t\tsanity = float(_amerika_checkpoint.get("sanity", 1.0))
\t\t_used_events = _amerika_checkpoint.get("used_events", [])
\t\t_load_floor(clampi(int(_amerika_checkpoint.get("floor", 0)), 0, Game.def["floors"].size() - 1))
\t\troom_n = int(_amerika_checkpoint.get("room", 0))
\t\tawait _enter_room(str(_amerika_checkpoint.get("kind", "combat")), str(_amerika_checkpoint.get("reward", "mem")), true)
\t\tplayer.locked = false
\t\treturn
\tvar cli := Game.cli''',1)
   source=source.replace('func _enter_room(kind: String, reward: String, first := false) -> void:\n','''func _enter_room(kind: String, reward: String, first := false) -> void:
\tGame.save["amerika_checkpoint"] = {"version": 1, "run": run.duplicate(true), "floor": floor_i, "room": room_n, "kind": kind, "reward": reward, "hp": player.hp, "light": light, "sanity": sanity, "used_events": _used_events.duplicate()}
\tGame.write_save()
''')
   source=source.replace('\tended = true','\tended = true\n\tGame.save.erase("amerika_checkpoint")',1)
   run_script.write_text(source)
 text=(dest/'project.godot').read_text(encoding='utf-8')
 text=re.sub(r'config/features=.*', 'config/features=PackedStringArray("4.7", "GL Compatibility")',text)
 if 'AmerikaCloud=' not in text:text=text.replace('[autoload]','[autoload]\n\nAmerikaCloud="*res://amerika_cloud.gd"')
 text=re.sub(r'config/company=.*','config/company="Amerika LLC"',text)
 if slug=='pickles-pickle-shop':
  text=text.replace('config/name=', 'run/max_fps=30\nconfig/name=',1) if 'run/max_fps=' not in text else text
 if '[rendering]' not in text:text+='\n[rendering]\n'
 text=re.sub(r'^renderer/rendering_method(?:\.mobile)?=.*\n?','',text,flags=re.M)
 text=text.replace('[rendering]','[rendering]\nrenderer/rendering_method="gl_compatibility"\nrenderer/rendering_method.mobile="gl_compatibility"',1)
 (dest/'project.godot').write_text(text,encoding='utf-8');(dest/'amerika_cloud.gd').write_text(cloud,encoding='utf-8')
 (dest/'amerika_shell.html').write_text(shell.replace('GAME_TITLE',title.replace('&','&amp;').replace('<','&lt;')),encoding='utf-8')
 (dest/'export_presets.cfg').write_text('''[preset.0]
name="Amerika Web"
platform="Web"
runnable=true
custom_features=""
export_filter="all_resources"
include_filter="*.json,*.txt,*.cfg,*.csv,*.dat"
exclude_filter="scripts/dev/*,tools/*,docs/*,generator/*,*.part*"
export_path=""
[preset.0.options]
variant/extensions_support=false
variant/thread_support=false
vram_texture_compression/for_desktop=true
vram_texture_compression/for_mobile=true
html/custom_html_shell="res://amerika_shell.html"
html/canvas_resize_policy=2
html/focus_canvas_on_start=true
progressive_web_app/enabled=false
''',encoding='utf-8')
 if slug=='pickles-pickle-shop':
  subprocess.run([sys.executable,str(repo/'scripts/patch-pickles.py'),str(dest)],check=True)
  subprocess.run([sys.executable,str(repo/'scripts/optimize-gaming.py'),str(dest)],check=True)
 log=work/(slug+'-export.log')
 with log.open('w',encoding='utf-8') as stream:
  for command in [[args.godot,'--headless','--path',str(dest),'--editor','--import'],[args.godot,'--headless','--path',str(dest),'--export-release','Amerika Web',str(output/'index.html')]]:
   result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=900)
   if result.returncode:raise RuntimeError('Web export failed for '+slug+'; see '+str(log))
 shutil.copyfile(repo/'public/logo.svg',output/'amerika-logo.svg')
 shutil.copyfile(repo/'public/gaming-bridge.js',output/'amerika-bridge.js')
 archive=work/(slug+'-web.zip')
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for path in output.rglob('*'):
   if path.is_file():z.write(path,path.relative_to(output).as_posix())
 print(json.dumps({'id':slug,'archive':str(archive),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}),flush=True)
