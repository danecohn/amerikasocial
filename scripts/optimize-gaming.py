from pathlib import Path
from PIL import Image
from io import BytesIO
import json,struct,argparse
parser=argparse.ArgumentParser();parser.add_argument('project');parser.add_argument('--max-texture',type=int,default=512);args=parser.parse_args();root=Path(args.project).resolve()
if not (root/'project.godot').is_file():raise SystemExit('Provide the copied Godot project folder.')
saved=0
for path in root.rglob('*'):
 if not path.is_file() or '.godot' in path.parts:continue
 if path.suffix.lower() in ['.png','.jpg','.jpeg']:
  with Image.open(path) as image:
   if max(image.size)<=args.max_texture:continue
   before=path.stat().st_size;image.thumbnail((args.max_texture,args.max_texture),Image.Resampling.LANCZOS);image.save(path,**({'quality':84,'optimize':True} if path.suffix.lower()!='.png' else {'optimize':True}));saved+=before-path.stat().st_size
 elif path.suffix.lower()=='.glb':
  data=path.read_bytes()
  if data[:4]!=b'glTF':continue
  length,kind=struct.unpack_from('<II',data,12)
  doc=json.loads(data[20:20+length]);offset=20+length
  if len(doc.get('buffers',[]))!=1 or offset+8>len(data):continue
  size,kind=struct.unpack_from('<II',data,offset);binary=data[offset+8:offset+8+size];replacements={}
  for image in doc.get('images',[]):
   index=image.get('bufferView')
   if index is None:continue
   view=doc['bufferViews'][index];raw=binary[view.get('byteOffset',0):view.get('byteOffset',0)+view['byteLength']]
   with Image.open(BytesIO(raw)) as photo:
    if max(photo.size)<=args.max_texture:continue
    photo.thumbnail((args.max_texture,args.max_texture),Image.Resampling.LANCZOS);out=BytesIO();photo.save(out,format='PNG' if image.get('mimeType')=='image/png' else 'JPEG',**({'quality':84,'optimize':True} if image.get('mimeType')!='image/png' else {'optimize':True}));replacements[index]=out.getvalue()
  if not replacements:continue
  assembled=bytearray()
  for i,view in enumerate(doc['bufferViews']):
   while len(assembled)%4:assembled.append(0)
   raw=replacements.get(i,binary[view.get('byteOffset',0):view.get('byteOffset',0)+view['byteLength']]);view['byteOffset']=len(assembled);view['byteLength']=len(raw);assembled.extend(raw)
  doc['buffers'][0]['byteLength']=len(assembled)
  while len(assembled)%4:assembled.append(0)
  encoded=json.dumps(doc,separators=(',',':')).encode()
  while len(encoded)%4:encoded+=b' '
  result=struct.pack('<III',0x46546c67,2,12+8+len(encoded)+8+len(assembled))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(assembled),0x004e4942)+assembled
  path.write_bytes(result);saved+=len(data)-len(result)
print('Web asset reduction:',round(saved/1000000,1),'MB; originals unchanged')
