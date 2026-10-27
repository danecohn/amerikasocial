import {searchPreferenceNames} from './search-preferences.mjs';
// Only this fixed internal upstream receives search traffic. Account credentials are never forwarded.
export async function proxySearch(req,res,{upstream,origin}){
 if(!upstream){res.writeHead(503,{'Content-Type':'text/plain'});res.end('Cohnsoft Search is starting. Please try again shortly.');return;}
 const source=new URL(req.url,'http://localhost'),prefix='/search';let path=source.pathname;if(source.pathname===prefix)path=source.searchParams.has('q')?prefix+'/search':prefix+'/';
 if(!['GET','HEAD','POST'].includes(req.method)){res.writeHead(405);res.end();return;}
 const target=new URL(upstream);target.pathname=target.pathname.replace(/\/$/,'')+'/'+path.replace(/^\/+/,'');target.search=source.search;const publicUrl=new URL(origin),headers={'X-Forwarded-Proto':publicUrl.protocol.slice(0,-1),'X-Forwarded-Host':publicUrl.host,'X-Script-Name':prefix,'X-Forwarded-Prefix':prefix,'X-Real-IP':req.headers['x-railway-client-ip']||req.socket.remoteAddress,'X-Forwarded-For':req.headers['x-railway-client-ip']||req.socket.remoteAddress};
 if(source.pathname==='/search/artemis/overview'){if(req.headers.origin!==publicUrl.origin){res.writeHead(403);res.end('Same-origin requests only.');return;}headers.origin=publicUrl.origin;}
 for(const name of ['accept','accept-language','content-type','user-agent','sec-fetch-dest','sec-fetch-mode','sec-fetch-site','sec-fetch-user'])if(req.headers[name])headers[name]=req.headers[name];
 const cookies=(req.headers.cookie||'').split(';').filter(c=>searchPreferenceNames.has(c.trim().split('=')[0]));if(cookies.length)headers.cookie=cookies.join(';');
 let body;if(req.method==='POST'){const parts=[];let size=0;for await(const part of req){size+=part.length;if(size>32768){res.writeHead(413);res.end();return;}parts.push(part);}body=Buffer.concat(parts);}
 const response=await fetch(target,{method:req.method,headers,body,redirect:'manual',signal:AbortSignal.timeout(35000)});
 res.statusCode=response.status;for(const name of ['content-type','cache-control','content-disposition','content-security-policy']){const value=response.headers.get(name);if(value)res.setHeader(name,value);}
 for(const cookie of response.headers.getSetCookie())res.appendHeader('Set-Cookie',(/;\s*Path=/i.test(cookie)?cookie.replace(/;\s*Path=[^;]*/i,'; Path=/search'):cookie+'; Path=/search'));
 const location=response.headers.get('location');if(location){const dest=new URL(location,target);if(dest.origin===new URL(upstream).origin)res.setHeader('Location',origin+(dest.pathname.startsWith(prefix+'/')||dest.pathname===prefix?dest.pathname:prefix+dest.pathname)+dest.search);else if(dest.origin===publicUrl.origin)res.setHeader('Location',dest.href);else{res.statusCode=502;res.end('Unexpected search redirect.');return;}}
 res.setHeader('Referrer-Policy','no-referrer');res.setHeader('X-Content-Type-Options','nosniff');if(req.method==='HEAD'||!response.body){res.end();return;}for await(const chunk of response.body)res.write(chunk);res.end();
}
