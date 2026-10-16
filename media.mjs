import { randomUUID } from 'node:crypto';
const error=(status,message)=>Object.assign(new Error(message),{status});
export const maxMediaBytes=250000000;
export const maxVideoDuration=180;
export function validateMedia(bytes,mime,{allowIphone=false,maxDuration=maxVideoDuration}={}){
 if(!bytes.length)throw error(400,'Choose a nonempty media file.');
 const image=mime.startsWith('image/');
 if(bytes.length>(image?1000000:maxMediaBytes))throw error(413,image?'Images must be under 1 MB after resizing.':'Videos must be under 250 MB (0.25 GB).');
 const signature=mime==='image/png'?bytes.length>24&&bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])):mime==='image/jpeg'?bytes.length>4&&bytes[0]===255&&bytes[1]===216&&bytes[2]===255:mime==='image/webp'?bytes.length>20&&bytes.toString('ascii',0,4)==='RIFF'&&bytes.toString('ascii',8,12)==='WEBP':false;
 if(image){if(!signature)throw error(400,'Choose a valid PNG, JPEG, or WebP image.');return;}
 if(!(mime==='video/mp4'||allowIphone&&mime==='video/quicktime')||bytes.length<24||bytes.toString('ascii',4,8)!=='ftyp')throw error(400,'Choose an MP4 or iPhone MOV video.');
 let duration=null,h264=false,hevc=false,hasData=false;
 function boxes(start,end,depth=0){if(depth>8)throw error(400,'Invalid MP4 structure.');let offset=start;while(offset+8<=end){let size=bytes.readUInt32BE(offset);const type=bytes.toString('ascii',offset+4,offset+8);let header=8;if(size===1){if(offset+16>end)throw error(400,'Invalid MP4 structure.');const big=bytes.readBigUInt64BE(offset+8);if(big>BigInt(bytes.length))throw error(400,'Invalid MP4 structure.');size=Number(big);header=16;}if(size===0)size=end-offset;if(size<header||offset+size>end)throw error(400,'Invalid MP4 structure.');const p=offset+header;
 if(type==='mdat'&&size>header)hasData=true;
 if(type==='mvhd'){const version=bytes[p];const scaleOffset=version===0?p+12:version===1?p+20:-1;const length=version===1?12:8;if(scaleOffset<0||scaleOffset+length>offset+size)throw error(400,'Invalid MP4 duration.');const scale=bytes.readUInt32BE(scaleOffset);const ticks=version===1?Number(bytes.readBigUInt64BE(scaleOffset+4)):bytes.readUInt32BE(scaleOffset+4);duration=scale?ticks/scale:null;}
 if(type==='stsd'){if(p+8>offset+size)throw error(400,'Invalid MP4 codecs.');const entries=bytes.readUInt32BE(p+4);let e=p+8;for(let i=0;i<entries;i++){if(e+8>offset+size)throw error(400,'Invalid MP4 codecs.');const n=bytes.readUInt32BE(e);if(n<8||e+n>offset+size)throw error(400,'Invalid MP4 codecs.');if(['avc1','avc3'].includes(bytes.toString('ascii',e+4,e+8)))h264=true;if(['hvc1','hev1'].includes(bytes.toString('ascii',e+4,e+8)))hevc=true;e+=n;}}
 if(['moov','trak','mdia','minf','stbl'].includes(type))boxes(p,offset+size,depth+1);offset+=size;}}
 boxes(0,bytes.length);
 if(!hasData||!(h264||allowIphone&&hevc)||!Number.isFinite(duration)||duration<=0||duration>maxDuration)throw error(400,'Use an H.264 or HEVC video no longer than '+maxDuration+' seconds.');
 return {h264,duration};
}
export function createMedia(db){
 db.exec(`CREATE TABLE IF NOT EXISTS media(id TEXT PRIMARY KEY,actor TEXT NOT NULL REFERENCES actors(id),mime TEXT NOT NULL,bytes BLOB NOT NULL,blob TEXT,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS post_media(post TEXT NOT NULL REFERENCES posts(uri),media TEXT NOT NULL REFERENCES media(id),alt TEXT NOT NULL DEFAULT '',position INTEGER NOT NULL,PRIMARY KEY(post,media));`);
 function cleanup(){db.prepare('DELETE FROM media WHERE created<? AND id NOT IN (SELECT media FROM post_media)').run(new Date(Date.now()-86400000).toISOString());}
 cleanup();setInterval(cleanup,3600000).unref();
 return {
  checkQuota(actor,incoming=0){const count=db.prepare('SELECT COUNT(*) AS n,COALESCE(SUM(length(bytes)),0) AS size FROM media WHERE actor=? AND created>?').get(actor,new Date(Date.now()-3600000).toISOString());if(count.n>=20||count.size+incoming>1000000000)throw error(429,'Media upload allowance reached. Try again in an hour.');},
  save(actor,mime,bytes,blob){this.checkQuota(actor,bytes.length);const id=randomUUID();db.prepare('INSERT INTO media VALUES (?,?,?,?,?,?)').run(id,actor,mime,bytes,blob?JSON.stringify(blob):null,new Date().toISOString());return {id,mime};},
  select(actor,attachments=[]){if(!Array.isArray(attachments)||attachments.length>4)throw error(400,'Attach up to four images or one video.');const used=new Set();const rows=attachments.map(a=>{if(!a||typeof a.id!=='string'||used.has(a.id)||typeof a.alt!=='string'||a.alt.length>2000)throw error(400,'Use distinct media attachments with descriptions under 2,000 characters.');used.add(a.id);const row=db.prepare('SELECT id,actor,mime,blob FROM media WHERE id=?').get(a.id);if(!row||row.actor!==actor)throw error(403,'You can attach only your own uploaded media.');return {...row,alt:a.alt};});if(rows.some(r=>r.mime==='video/mp4')&&rows.length!==1)throw error(400,'Attach one video or up to four images, not both.');return rows;},
  embed(rows){if(!rows.length||rows.some(r=>!r.blob))return null;if(rows[0].mime==='video/mp4')return {$type:'app.bsky.embed.video',video:JSON.parse(rows[0].blob),alt:rows[0].alt};return {$type:'app.bsky.embed.images',images:rows.map(r=>({image:JSON.parse(r.blob),alt:r.alt}))};},
  link(uri,rows){const stmt=db.prepare('INSERT INTO post_media VALUES (?,?,?,?)');rows.forEach((r,i)=>stmt.run(uri,r.id,r.alt,i));},
  view(uri){return db.prepare('SELECT m.id,m.mime,pm.alt FROM post_media pm JOIN media m ON m.id=pm.media WHERE pm.post=? ORDER BY pm.position').all(uri).map(m=>({...m,url:'/api/media?id='+m.id}));},
  serve(id,req,res){const row=db.prepare('SELECT m.mime,m.bytes FROM media m WHERE m.id=? AND EXISTS (SELECT 1 FROM post_media pm JOIN posts p ON p.uri=pm.post JOIN actors a ON a.id=p.author WHERE pm.media=m.id AND p.deleted=0 AND p.removed_at IS NULL AND p.community_removed_at IS NULL AND a.suspended_at IS NULL)').get(id);if(!row)throw error(404,'Media not found.');const bytes=Buffer.from(row.bytes);const range=req.headers.range;res.setHeader('Content-Type',row.mime);res.setHeader('Accept-Ranges','bytes');res.setHeader('Cache-Control','no-store');if(range){const match=range.match(/^bytes=(\d*)-(\d*)$/);let start=match?.[1]?Number(match[1]):Math.max(0,bytes.length-Number(match?.[2]));let end=match?.[1]&&match?.[2]?Number(match[2]):bytes.length-1;if(!match||(!match[1]&&!match[2])||!Number.isSafeInteger(start)||!Number.isSafeInteger(end)||start<0||start>=bytes.length||end<start){res.writeHead(416,{'Content-Range':`bytes */${bytes.length}`});res.end();return;}end=Math.min(end,bytes.length-1);res.writeHead(206,{'Content-Range':`bytes ${start}-${end}/${bytes.length}`,'Content-Length':end-start+1});res.end(bytes.subarray(start,end+1));return;}res.setHeader('Content-Length',bytes.length);res.end(bytes);}
 };
}
