import {createReadStream} from 'node:fs';
import {stat,readFile} from 'node:fs/promises';
import {join,resolve,sep} from 'node:path';

// Serves the signed AltStack Desktop APT repository from a fixed directory. Only paths that match the
// repository layout below are ever mapped to files; nothing from the request is used to build another path.
const SUITE='stable',ARCH='arm64';
const PACKAGE_FILE='[a-z0-9][a-z0-9+.~_-]{1,120}_[A-Za-z0-9.+~:-]{1,60}_(?:arm64|all)\\.deb';
const ROUTES=[
 {re:/^\/apt\/(amerika-archive-keyring\.gpg)$/,type:'application/pgp-keys',cache:'public,max-age=300'},
 {re:/^\/apt\/(amerika-archive-keyring\.asc)$/,type:'text/plain; charset=utf-8',cache:'public,max-age=300'},
 {re:/^\/apt\/(manifest\.json)$/,type:'application/json; charset=utf-8',cache:'public,max-age=60'},
 {re:new RegExp(`^/apt/(dists/${SUITE}/(?:InRelease|Release))$`),type:'text/plain; charset=utf-8',cache:'no-cache'},
 {re:new RegExp(`^/apt/(dists/${SUITE}/Release\\.gpg)$`),type:'application/pgp-signature',cache:'no-cache'},
 {re:new RegExp(`^/apt/(dists/${SUITE}/main/binary-${ARCH}/Packages)$`),type:'text/plain; charset=utf-8',cache:'no-cache'},
 {re:new RegExp(`^/apt/(dists/${SUITE}/main/binary-${ARCH}/Packages\\.gz)$`),type:'application/gzip',cache:'no-cache'},
 {re:new RegExp(`^/apt/(dists/${SUITE}/main/binary-${ARCH}/Packages\\.xz)$`),type:'application/x-xz',cache:'no-cache'},
 {re:new RegExp(`^/apt/(pool/main/[a-z0-9]/[a-z0-9][a-z0-9+.-]{1,60}/${PACKAGE_FILE})$`),type:'application/vnd.debian.binary-package',cache:'public,max-age=31536000,immutable',pool:true},
];
const REDIRECT_URL=/^https:\/\/github\.com\/danecohn\/amerikasocial\/releases\/download\/[A-Za-z0-9._-]{1,80}\/[A-Za-z0-9.+~_-]{1,200}\.deb$/;

export function createAptRepository({dir}){
 const base=resolve(dir);
 let redirects=null;
 async function redirectFor(name){
  if(!redirects){try{redirects=JSON.parse(await readFile(join(base,'pool-redirects.json'),'utf8'));}catch{redirects={};}}
  const entry=Object.hasOwn(redirects,name)?redirects[name]:null;
  return entry&&REDIRECT_URL.test(entry.url)?entry.url:null;
 }
 return async function serve(req,res,rawPath){
  // APT percent-encodes characters such as '~' in package file names.
  let path;try{path=decodeURIComponent(rawPath);}catch{path='';}
  if(/[\\\0]/.test(path))path='';
  const route=ROUTES.find(r=>r.re.test(path));
  if(!route){res.statusCode=404;res.setHeader('Content-Type','text/plain');res.end('Not found.');return;}
  if(req.method!=='GET'&&req.method!=='HEAD'){res.statusCode=405;res.setHeader('Allow','GET, HEAD');res.end('Use GET.');return;}
  const rel=path.match(route.re)[1];
  const file=resolve(base,rel);
  if(!file.startsWith(base+sep)){res.statusCode=404;res.end('Not found.');return;}
  let info;
  try{info=await stat(file);if(!info.isFile())throw Error();}catch{
   const target=route.pool?await redirectFor(rel.split('/').at(-1)):null;
   if(target){res.statusCode=302;res.setHeader('Location',target);res.setHeader('Cache-Control','public,max-age=3600');res.end();return;}
   res.statusCode=404;res.setHeader('Content-Type','text/plain');res.end('Not found.');return;
  }
  const etag=`"${info.size.toString(16)}-${Math.floor(info.mtimeMs).toString(16)}"`;
  res.setHeader('Content-Type',route.type);res.setHeader('Cache-Control',route.cache);res.setHeader('ETag',etag);
  res.setHeader('Accept-Ranges','bytes');res.setHeader('X-Content-Type-Options','nosniff');
  if(req.headers['if-none-match']===etag){res.statusCode=304;res.end();return;}
  let start=0,end=info.size-1;
  const range=/^bytes=(\d*)-(\d*)$/.exec(req.headers.range||'');
  if(range&&(range[1]||range[2])){
   if(range[1]){start=Number(range[1]);if(range[2])end=Math.min(Number(range[2]),end);}else{start=Math.max(0,info.size-Number(range[2]));}
   if(!(start<=end)||start>=info.size){res.statusCode=416;res.setHeader('Content-Range',`bytes */${info.size}`);res.end();return;}
   res.statusCode=206;res.setHeader('Content-Range',`bytes ${start}-${end}/${info.size}`);
  }
  res.setHeader('Content-Length',String(end-start+1));
  if(req.method==='HEAD'){res.end();return;}
  createReadStream(file,{start,end}).on('error',()=>res.destroy()).pipe(res);
 };
}
