// SPDX-License-Identifier: GPL-3.0-or-later
import {readFile} from 'node:fs/promises';import {createHash} from 'node:crypto';
const collections=JSON.parse(await readFile(new URL('./public/collections/manifest.json',import.meta.url),'utf8'));
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
export function createCollections({request=fetch}={}){const cache=new Map();let cacheBytes=0;return async(req,res,url)=>{
 if(!url.pathname.startsWith('/collections/'))return false;
 if(!['GET','HEAD'].includes(req.method)){res.writeHead(405,{Allow:'GET, HEAD'});res.end();return true}
 const [, ,key,...parts]=url.pathname.split('/'),collection=collections[key];if(!collection){res.writeHead(404);res.end();return true}
 if(!parts.length){res.writeHead(308,{Location:'/collections/'+key+'/'});res.end();return true}
 const rel=parts.join('/')||'index.html';
 if(key==='icons'&&/^products\/[a-z0-9-]+\/$/.test(rel)){
  const id=rel.split('/')[1],name=collection.productNames?.[id];if(!name){res.writeHead(404);res.end();return true}
  const list=Object.keys(collection.files).filter(path=>path.startsWith(rel));
  const escape=value=>String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const links=list.map(path=>'<li><a href="/collections/icons/'+path+'" download>'+escape(path.slice(rel.length))+'</a></li>').join('');
  const html='<!doctype html><html lang="en" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(name)+' icon kit · VigilTech</title><link rel="stylesheet" href="/brand/vigiltech/css/vigilsans.css"><link rel="stylesheet" href="/brand/vigiltech/css/goldengate.css"><link rel="stylesheet" href="/icons-wallpapers.css"><script defer src="/vigiltech.js"></script></head><body class="vt"><header class="gallery-header vt-glass"><a href="/collections/icons/">← Product icons</a><strong>'+escape(name)+'</strong></header><main><section class="install vt-card"><div><img src="desktop/'+id+'-256.png" width="128" height="128" alt="'+escape(name)+'"><h1>'+escape(name)+' icon kit</h1><p>Original files by VigilTech, copied unchanged. Choose the format for your platform.</p><p><a href="/collections/icons/USE.md">Installation and usage guide</a></p></div><div><p><a href="desktop/'+id+'.icns" download>macOS ICNS</a> · <a href="desktop/'+id+'.ico" download>Windows ICO</a> · <a href="desktop/'+id+'-512.png" download>512px PNG</a></p><ul>'+links+'</ul></div></section></main><footer>A product of VigilTech, vigiltech.org. GNU GPL v3. <a href="https://github.com/'+collection.repo+'/tree/'+collection.commit+'/'+rel+'">Source and files</a></footer></body></html>';
  res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'});res.end(req.method==='HEAD'?undefined:html);return true
 }
 const file=collection.files[rel];if(!file){res.writeHead(404);res.end();return true}
 try{const cacheKey=key+'/'+rel;let bytes=cache.get(cacheKey);
  if(!bytes){if(rel==='index.html')bytes=await readFile(new URL('./public/collections/'+key+'/index.html',import.meta.url));else{const response=await request(collection.base+rel,{redirect:'error',signal:AbortSignal.timeout(25000)});if(!response.ok)throw Error();const chunks=[];let size=0;for await(const chunk of response.body){size+=chunk.length;if(size>file.size)throw Error();chunks.push(chunk)}bytes=Buffer.concat(chunks)}if(bytes.length!==file.size||sha(bytes)!==file.sha256)throw Error('integrity');while(cacheBytes+bytes.length>32*1024*1024&&cache.size){const k=cache.keys().next().value;cacheBytes-=cache.get(k).length;cache.delete(k)}cache.set(cacheKey,bytes);cacheBytes+=bytes.length}
  const ext=rel.split('.').pop().toLowerCase(),type={html:'text/html; charset=utf-8',css:'text/css',js:'text/javascript',json:'application/json',png:'image/png',jpg:'image/jpeg',jpeg:'image/jpeg',webp:'image/webp',svg:'image/svg+xml',ico:'image/x-icon',icns:'image/icns',woff2:'font/woff2',ttf:'font/ttf',wav:'audio/wav',md:'text/plain; charset=utf-8',txt:'text/plain; charset=utf-8'}[ext]||'application/octet-stream';
  res.setHeader('Content-Type',type);res.setHeader('Cache-Control',ext==='html'?'no-store':'public,max-age=3600');res.setHeader('X-Content-Type-Options','nosniff');
  if(ext==='html'){const html=bytes.toString(),attributes=[...bytes.toString().matchAll(/style=["']([^"']*)["']/g)].map(m=>"'sha256-"+createHash('sha256').update(m[1]).digest('base64')+"'").join(' '),hashes=tag=>[...html.matchAll(new RegExp('<'+tag+'(?:\\s[^>]*)?>([\\s\\S]*?)</'+tag+'>','gi'))].map(m=>"'sha256-"+createHash('sha256').update(m[1]).digest('base64')+"'").join(' ');res.setHeader('Content-Security-Policy',`default-src 'self'; script-src 'self' ${hashes('script')}; style-src 'self' ${hashes('style')}; style-src-attr 'unsafe-hashes' ${attributes}; img-src 'self' data:; font-src 'self'; media-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'`)}
  res.setHeader('Content-Length',String(bytes.length));res.writeHead(200);res.end(req.method==='HEAD'?undefined:bytes)
 }catch{res.writeHead(502,{'Content-Type':'text/plain','Cache-Control':'no-store'});res.end('The original collection is temporarily unavailable. Please try again shortly.')}return true
}}
