// SPDX-License-Identifier: GPL-3.0-or-later
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const catalogue=JSON.parse(await readFile(new URL('./public/assets-collection/catalog.json',import.meta.url),'utf8'));
const byId=new Map(catalogue.items.map(item=>[item.id,item]));
export function createAssetsGallery({fetchAsset=fetch}={}){
 const cache=new Map();let cacheBytes=0;
 return async function serveAssets(req,res,url){
  const preview=url.pathname.startsWith('/assets/preview/');
  if(!preview&&!url.pathname.startsWith('/assets/download/'))return false;
  if(!['GET','HEAD'].includes(req.method)){res.writeHead(405,{'Allow':'GET, HEAD'});res.end();return true;}
  const item=byId.get(url.pathname.slice(preview?'/assets/preview/'.length:'/assets/download/'.length));
  if(!item){res.writeHead(404);res.end('Asset not found.');return true;}
  const expectedBytes=preview?item.previewBytes:item.bytes,expectedHash=preview?item.previewSha256:item.sha256;
  const cacheKey=(preview?'preview:':'file:')+item.id;
  const headers={'Content-Type':'image/png','Content-Disposition':`${preview?'inline':'attachment'}; filename="${item.path.split('/').pop()}"`,'X-Content-Type-Options':'nosniff','Cache-Control':'public, max-age=86400','Content-Length':String(expectedBytes)};
  if(req.method==='HEAD'){res.writeHead(200,headers);res.end();return true;}
  if(cache.has(cacheKey)){res.writeHead(200,headers);res.end(cache.get(cacheKey));return true;}
  try{
   // The client supplies only an opaque catalogue ID, never a URL or filesystem path.
   const response=await fetchAsset(catalogue.rawBase+(preview?item.previewPath:item.path),{redirect:'error',signal:AbortSignal.timeout(20000)});
   if(!response.ok)throw Error('Source unavailable');
   const chunks=[];let bytes=0;
   for await(const part of response.body){bytes+=part.length;if(bytes>expectedBytes)throw Error('Asset size mismatch');chunks.push(part);}
   const buffer=Buffer.concat(chunks);
   if(bytes!==expectedBytes||createHash('sha256').update(buffer).digest('hex')!==expectedHash)throw Error('Asset integrity mismatch');
   while(cacheBytes+buffer.length>32*1024*1024&&cache.size){const key=cache.keys().next().value;cacheBytes-=cache.get(key).length;cache.delete(key);}
   cache.set(cacheKey,buffer);cacheBytes+=buffer.length;
   res.writeHead(200,headers);res.end(buffer);
  }catch{res.writeHead(502,{'Content-Type':'text/plain','Cache-Control':'no-store'});res.end('The original download is temporarily unavailable. Please try again or use the source collection.');}
  return true;
 };
}
