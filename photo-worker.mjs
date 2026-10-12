import sharp from 'sharp';
import libheif from 'libheif-js/wasm-bundle.js';
import { readFile,writeFile } from 'node:fs/promises';

sharp.cache(false);sharp.concurrency(1);
const [input,output,mime]=process.argv.slice(2);let written=false;
try{
 let source=await readFile(input),options={limitInputPixels:64000000,failOn:'error'};
 if(['image/heic','image/heif'].includes(mime)){
  const images=new libheif.HeifDecoder().decode(source);
  try{
   const image=images.find(i=>i.is_primary?.())||images[0];if(!image)throw Error('Invalid HEIF');
   const width=image.get_width(),height=image.get_height();if(width<=0||height<=0||width*height>64000000)throw Error('Photo dimensions exceed limit');
   const decoded=await new Promise((done,reject)=>image.display({data:new Uint8ClampedArray(width*height*4),width,height},result=>result?done(result):reject(Error('HEIF decoding failed'))));
   source=Buffer.from(decoded.data.buffer,decoded.data.byteOffset,decoded.data.byteLength);options={raw:{width,height,channels:4},limitInputPixels:64000000};
   for(const quality of [85,70,50,35]){const result=await sharp(source,options).rotate().resize(1600,1600,{fit:'inside',withoutEnlargement:true}).webp({quality}).toBuffer();if(result.length<=1000000){await writeFile(output,result);written=true;process.exitCode=0;break;}}
  }finally{images.forEach(i=>i.free());}
 }else{
  for(const quality of [85,70,50,35]){const result=await sharp(source,options).rotate().resize(1600,1600,{fit:'inside',withoutEnlargement:true}).webp({quality}).toBuffer();if(result.length<=1000000){await writeFile(output,result);written=true;break;}}
 }
}catch{process.exitCode=1;}

if(!written)process.exitCode=1;
