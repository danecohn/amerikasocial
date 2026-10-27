// SPDX-License-Identifier: GPL-3.0-or-later
// Fixed first-party services only: never accept an upstream URL from the request.
import http from 'node:http';
import https from 'node:https';
import {pipeline} from 'node:stream/promises';
const hop=new Set(['connection','keep-alive','proxy-authenticate','proxy-authorization','te','trailer','transfer-encoding','upgrade','host','cookie','origin','referer','forwarded','x-forwarded-host','x-forwarded-proto','x-forwarded-prefix','x-forwarded-for','x-real-ip']);
export async function proxyApp(req,res,{upstream,prefix,origin,cookies=[],keepPrefix=false,canonicalUpstreamOrigin}){
 if(!upstream){res.writeHead(503,{'Content-Type':'text/plain','Cache-Control':'no-store'});res.end('This app is temporarily unavailable. Please try again shortly.');return;}
 const source=new URL(req.url,origin),publicUrl=new URL(origin),backend=new URL(upstream);
 if(!['http:','https:'].includes(backend.protocol)||backend.username||backend.password)throw Error('Invalid app upstream');
 if(source.pathname===prefix){res.writeHead(308,{Location:prefix+'/'+source.search,'Cache-Control':'no-store'});res.end();return;}
 // Browser state-changing calls must originate at this owned gateway. Non-browser signed
 // callbacks and bearer-authenticated MCP calls omit Origin and keep their own app checks.
 if(req.headers.origin&&req.headers.origin!==publicUrl.origin){res.writeHead(403,{'Cache-Control':'no-store'});res.end('Request origin rejected.');return;}
 const local=keepPrefix?source.pathname:source.pathname.slice(prefix.length)||'/';
 backend.pathname=backend.pathname.replace(/\/$/,'')+local;backend.search=source.search;
 const headers={};for(const[k,v]of Object.entries(req.headers))if(!hop.has(k.toLowerCase())&&!k.toLowerCase().startsWith('x-forwarded-'))headers[k]=v;
 headers.host=backend.host;headers['x-forwarded-proto']='https';headers['x-forwarded-host']=publicUrl.host;headers['x-forwarded-prefix']=prefix;headers['x-vigil-suite-path']=prefix;
 headers['x-forwarded-for']=req.headers['x-railway-client-ip']||req.socket.remoteAddress;
 // Only configured app cookies leave this service. Hub/other-app credentials never do.
 const selected=String(req.headers.cookie||'').split(';').filter(c=>cookies.some(pattern=>pattern.test(c.trim().split('=')[0])));if(selected.length)headers.cookie=selected.join(';');
 if(req.headers.origin)headers.origin=new URL(canonicalUpstreamOrigin||upstream).origin;
 const transport=backend.protocol==='https:'?https:http;
 await new Promise((resolve,reject)=>{
  const outgoing=transport.request(backend,{method:req.method,headers},async response=>{
   try{
    res.statusCode=response.statusCode;
    for(const[k,v]of Object.entries(response.headers))if(!hop.has(k)&&!['set-cookie','location','clear-site-data','strict-transport-security'].includes(k)&&v!==undefined)res.setHeader(k,v);
    // Do not allow an app logout to clear storage/caches for the whole suite.
    if(response.headers['set-cookie'])for(const c of response.headers['set-cookie']){
     const name=c.split('=')[0];if(!cookies.some(pattern=>pattern.test(name)))continue;
     let cookie=c.replace(/;\s*Domain=[^;]*/ig,'').replace(/;\s*Path=[^;]*/ig,'');cookie+='; Path='+(name.startsWith('__Host-')?'/':prefix+'/');res.appendHeader('Set-Cookie',cookie);
    }
    const location=response.headers.location;if(location){const target=new URL(location,backend);const owned=new Set([new URL(upstream).origin,new URL(canonicalUpstreamOrigin||upstream).origin]);
     if(owned.has(target.origin)&&target.origin!==publicUrl.origin){res.setHeader('Location',publicUrl.origin+(keepPrefix||target.pathname===prefix||target.pathname.startsWith(prefix+'/')?target.pathname:prefix+target.pathname)+target.search+target.hash);}else res.setHeader('Location',target.href);
    }
    await pipeline(response,res);resolve();
   }catch(e){reject(e);}
  });
  const abort=()=>outgoing.destroy();res.once('close',abort);outgoing.once('close',()=>res.off('close',abort));
  outgoing.once('error',reject);outgoing.setTimeout(180000,()=>outgoing.destroy(Error('App upstream timeout')));
  req.pipe(outgoing);
 });
}
