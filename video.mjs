import { spawn } from 'node:child_process';
import { mkdtemp,writeFile,readFile,rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join,resolve,sep } from 'node:path';
import { validateMedia,maxMediaBytes } from './media.mjs';

let converting=false;
export async function normalizeVideo(bytes,mime){
  const info=validateMedia(bytes,mime,{allowIphone:true});
  if(mime==='video/mp4'&&info.h264&&bytes.length<=20000000)return bytes;
  if(converting)throw Object.assign(new Error('Another iPhone video is processing. Please retry shortly.'),{status:503});
  converting=true;let dir;
  try{
    dir=await mkdtemp(join(tmpdir(),'amerika-video-'));const input=join(dir,'input.mov'),output=join(dir,'output.mp4');await writeFile(input,bytes);
    await new Promise((done,reject)=>{
      const child=spawn(process.env.FFMPEG_PATH||'ffmpeg',['-nostdin','-hide_banner','-loglevel','error','-protocol_whitelist','file','-i',input,'-map','0:v:0','-map','0:a:0?','-map_metadata','-1','-vf','scale=1280:1280:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1','-c:v','libx264','-preset','veryfast','-crf','23','-maxrate','4M','-bufsize','8M','-pix_fmt','yuv420p','-threads','2','-c:a','aac','-b:a','128k','-movflags','+faststart','-fs',String(maxMediaBytes),output],{stdio:'ignore',windowsHide:true});
      const timer=setTimeout(()=>{child.kill();},180000);
      child.once('error',()=>{clearTimeout(timer);reject(Object.assign(new Error('Video conversion is unavailable. Try an H.264 MP4 file.'),{status:503}));});
      child.once('close',code=>{clearTimeout(timer);code===0?done():reject(Object.assign(new Error('Could not convert this video. Choose a valid MP4 or iPhone MOV clip up to 60 seconds.'),{status:400}));});
    });
    const normalized=await readFile(output);validateMedia(normalized,'video/mp4');return normalized;
  }finally{
    converting=false;
    if(dir){const target=resolve(dir),root=resolve(tmpdir())+sep;if(!target.startsWith(root))throw Error('Unexpected video temporary directory');await rm(target,{recursive:true,force:true});}
  }
}
