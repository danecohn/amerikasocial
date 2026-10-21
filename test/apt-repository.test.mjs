import test from 'node:test';import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile} from 'node:fs/promises';import {tmpdir} from 'node:os';import {join} from 'node:path';
import {createAptRepository} from '../apt-repository.mjs';
async function fixture(){
 const dir=await mkdtemp(join(tmpdir(),'apt-'));
 await mkdir(join(dir,'dists/stable/main/binary-arm64'),{recursive:true});
 await mkdir(join(dir,'pool/main/a/amerika-hub'),{recursive:true});
 await writeFile(join(dir,'dists/stable/InRelease'),'signed');
 await writeFile(join(dir,'dists/stable/main/binary-arm64/Packages'),'Package: x\n');
 await writeFile(join(dir,'pool/main/a/amerika-hub/amerika-hub_1.0.0_all.deb'),'0123456789');
 await writeFile(join(dir,'pool-redirects.json'),JSON.stringify({
  'amerika-office_0.1.0-1_arm64.deb':{url:'https://github.com/danecohn/amerikasocial/releases/download/os-1.0.0/amerika-office_0.1.0-1_arm64.deb'},
  'amerika-evil_1_arm64.deb':{url:'https://evil.example/x.deb'}}));
 await writeFile(join(dir,'secret.txt'),'private');
 return createAptRepository({dir});
}
import {createServer} from 'node:http';
async function call(serve,path,{method='GET',headers={}}={}){
 const server=createServer((req,res)=>serve(req,res,new URL(req.url,'http://x').pathname));
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 try{
  const raw=await new Promise((resolve,reject)=>{
   import('node:http').then(({request})=>{const q=request({host:'127.0.0.1',port:server.address().port,path,method,headers},res=>{const c=[];res.on('data',d=>c.push(d));res.on('end',()=>resolve({status:res.statusCode,headers:res.headers,body:c}));});q.on('error',reject);q.end();});
  });
  return raw;
 }finally{server.close();}
}
test('serves repository metadata and pool packages with range support',async()=>{
 const serve=await fixture();
 let r=await call(serve,'/apt/dists/stable/InRelease');assert.equal(r.status,200);assert.equal(Buffer.concat(r.body).toString(),'signed');assert.equal(r.headers['cache-control'],'no-cache');
 r=await call(serve,'/apt/pool/main/a/amerika-hub/amerika-hub_1.0.0_all.deb',{headers:{range:'bytes=2-5'}});assert.equal(r.status,206);assert.equal(Buffer.concat(r.body).toString(),'2345');assert.equal(r.headers['content-range'],'bytes 2-5/10');
 r=await call(serve,'/apt/pool/main/a/amerika-hub/amerika-hub_1.0.0_all.deb',{method:'HEAD'});assert.equal(r.headers['content-length'],'10');assert.match(r.headers['cache-control'],/immutable/);
});
test('percent-encoded tildes in package names are accepted (as sent by APT) but encoded traversal is not',async()=>{
 const serve=await fixture();
 let r=await call(serve,'/apt/pool/main/a/amerika-office/amerika-office_0.1.0-1_arm64.deb');assert.equal(r.status,302);
 r=await call(serve,'/apt/pool/main/a/amerika-office/amerika-office_0.1.0%2d1_arm64.deb');assert.equal(r.status,302);
 for(const p of ['/apt/pool/main/a/amerika-hub/%2e%2e%2f%2e%2e%2fsecret.txt','/apt/dists/stable/%2e%2e/%2e%2e/secret.txt','/apt/%5csecret.txt','/apt/pool/main/a/amerika-hub/amerika-hub_1.0.0_all.deb%00']){r=await call(serve,p);assert.equal(r.status,404,p);}
});
test('only repository layout paths are mapped and traversal is impossible',async()=>{
 const serve=await fixture();
 for(const p of ['/apt/secret.txt','/apt/../secret.txt','/apt/dists/stable/../../secret.txt','/apt/pool/main/a/amerika-hub/..%2f..%2fsecret.txt','/apt/pool/main/a/amerika-hub/x.txt','/apt/dists/unstable/InRelease','/apt/pool-redirects.json']){
  const r=await call(serve,p);assert.equal(r.status,404,p);}
});
test('methods other than GET and HEAD are refused',async()=>{
 const r=await call(await fixture(),'/apt/dists/stable/InRelease',{method:'POST'});assert.equal(r.status,405);
});
test('large packages redirect only to the fixed GitHub release location',async()=>{
 const serve=await fixture();
 let r=await call(serve,'/apt/pool/main/a/amerika-office/amerika-office_0.1.0-1_arm64.deb');assert.equal(r.status,302);assert.match(r.headers.location,/^https:\/\/github\.com\/danecohn\/amerikasocial\/releases\/download\//);
 r=await call(serve,'/apt/pool/main/a/amerika-evil/amerika-evil_1_arm64.deb');assert.equal(r.status,404);
 r=await call(serve,'/apt/pool/main/a/amerika-missing/amerika-missing_1_arm64.deb');assert.equal(r.status,404);
});
