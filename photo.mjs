import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { mkdtemp,writeFile,readFile,rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join,resolve,sep } from 'node:path';
import { maxMediaBytes,validateMedia } from './media.mjs';

export function validatePhotoUpload(bytes,mime){
 if(!bytes.length)throw Object.assign(new Error('Choose a nonempty photo.'),{status:400});
 if(bytes.length>maxMediaBytes)throw Object.assign(new Error('Photos must be at most 250 MB (0.25 GB) each.'),{status:413});
 const heif=['image/heic','image/heif'].includes(mime);
 let valid=heif?bytes.length>=24&&bytes.toString('ascii',4,8)==='ftyp'&&['heic','heix','hevc','hevx','mif1','msf1'].some(brand=>bytes.toString('ascii',8,Math.min(bytes.length,64)).includes(brand)):false;
 if(!heif){try{validateMedia(bytes.subarray(0,Math.min(bytes.length,1000000)),mime);valid=mime.startsWith('image/');}catch{}}
 if(!valid)throw Object.assign(new Error('Choose a valid JPEG, PNG, WebP or iPhone HEIC/HEIF photo.'),{status:400});
}

export async function normalizePhoto(bytes,mime){
 validatePhotoUpload(bytes,mime);let dir;
 try{
  dir=await mkdtemp(join(tmpdir(),'amerika-photo-'));const input=join(dir,'source'),output=join(dir,'display.webp');await writeFile(input,bytes);
  await new Promise((done,reject)=>{
   const child=spawn(process.execPath,['--max-old-space-size=384',fileURLToPath(new URL('./photo-worker.mjs',import.meta.url)),input,output,mime],{stdio:'ignore',windowsHide:true});
   const timer=setTimeout(()=>child.kill(),90000);
   child.once('error',()=>{clearTimeout(timer);reject(Object.assign(new Error('Photo processing is unavailable. Please retry.'),{status:503}));});
   child.once('close',code=>{clearTimeout(timer);code===0?done():reject(Object.assign(new Error('This photo could not be processed. Choose a valid photo up to 64 megapixels.'),{status:400}));});
  });
  const result=await readFile(output);validateMedia(result,'image/webp');return result;
 }finally{
  if(dir){const target=resolve(dir);if(!target.startsWith(resolve(tmpdir())+sep))throw Error('Unexpected photo temporary directory');await rm(target,{recursive:true,force:true});}
 }
}
