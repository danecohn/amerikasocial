import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import { mkdtemp, rm, readFile, writeFile, readdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import http from 'node:http';
import { createOperations, encryptBackup, decryptBackup } from '../operations.mjs';
import { createRecovery } from '../recovery.mjs';

async function launch(env={}){const dir=await mkdtemp(join(tmpdir(),'amerika-launch-'));const child=spawn(process.execPath,['server.mjs'],{env:{...process.env,PDS_URL:'',BACKUPS_ENABLED:'false',STRIPE_SECRET_KEY:'',PORT:'0',DATA_DIR:dir,ADMIN_HANDLES:'ant',...env},stdio:['ignore','pipe','pipe']});const base=await new Promise((resolve,reject)=>{let output='';const timer=setTimeout(()=>reject(Error('Startup timed out')),15000);child.once('exit',()=>{clearTimeout(timer);reject(Error('Server exited'));});child.stdout.on('data',chunk=>{output+=chunk;const m=output.match(/"port":(\d+)/);if(m){clearTimeout(timer);resolve('http://127.0.0.1:'+m[1]);}});});return {dir,base,async stop(){const exited=new Promise(r=>child.once('exit',r));child.kill();await exited;await rm(dir,{recursive:true,force:true});}};}
async function api(app,path,body,token){const response=await fetch(app.base+'/api/'+path,{method:body?'POST':'GET',headers:{...(body?{'Content-Type':'application/json'}:{}),...(token?{Authorization:'Bearer '+token}:{})},...(body?{body:JSON.stringify(body)}:{})});return {status:response.status,data:await response.json()};}
async function register(app,handle){const result=await api(app,'register',{handle,name:handle,kind:'human',password:'original-password',humanConfirmed:true,country:'US',rulesAccepted:true});assert.equal(result.status,200);return result.data;}

test('recovery codes are private, require reauthentication, replace old codes, work once, and revoke sessions and agent credentials',async()=>{
 const app=await launch();try{const owner=await register(app,'owner.demo'),other=await register(app,'other.demo');assert.equal(owner.recoveryCodes.length,10);
 const db=new DatabaseSync(join(app.dir,'botsky.sqlite'));const hashes=db.prepare('SELECT hash FROM recovery_codes WHERE actor=?').all(owner.actor.id);assert.equal(hashes.length,10);assert.ok(hashes.every(h=>!owner.recoveryCodes.includes(h.hash)));db.close();
 assert.equal(JSON.stringify((await api(app,'profile?id='+encodeURIComponent(owner.actor.id))).data).includes(owner.recoveryCodes[0]),false);
 assert.equal((await api(app,'recovery/codes',{password:'wrong-password'},owner.token)).status,401);
 const created=await api(app,'agents',{handle:'owned.agent',name:'Agent',password:'agent-password',humanConfirmed:true,country:'US',rulesAccepted:true},owner.token);assert.equal(created.status,201);assert.equal(created.data.recoveryCodes.length,10);
 assert.equal((await api(app,'recovery/status?actor='+encodeURIComponent(created.data.actor.id),null,other.token)).status,403);
 const key=(await api(app,'agent-keys',{actor:created.data.actor.id,name:'Test',days:1,scopes:['post','read']},owner.token)).data;
 assert.equal((await api(app,'recovery/status',null,key.token)).status,403);
 const refreshed=await api(app,'recovery/codes',{password:'original-password'},owner.token);assert.equal(refreshed.status,200);
 assert.equal((await api(app,'recovery/reset',{handle:'owner.demo',code:owner.recoveryCodes[0],password:'replacement-password'})).status,400);
 const code=refreshed.data.recoveryCodes[0];assert.equal((await api(app,'recovery/reset',{handle:'owner.demo',code,password:'replacement-password'})).status,200);
 assert.equal((await api(app,'me',null,owner.token)).data.actor,null);
 assert.equal((await api(app,'posts',{text:'Revoked agent key'},key.token)).status,401);
 assert.equal((await api(app,'recovery/reset',{handle:'owner.demo',code,password:'second-password'})).status,400);
 assert.equal((await api(app,'login',{handle:'owner.demo',password:'original-password'})).status,401);
 assert.equal((await api(app,'login',{handle:'owner.demo',password:'replacement-password'})).status,200);
 }finally{await app.stop();}
});

test('reports are private; admins remove and restore posts, suspend and restore accounts, and decisions are audited',async()=>{
 const app=await launch();try{const admin=await register(app,'ant'),author=await register(app,'author.demo'),reader=await register(app,'reader.demo');assert.equal(admin.actor.admin,true);assert.equal(author.actor.admin,false);assert.equal((await api(app,'admin',null,reader.token)).status,403);
 const post=(await api(app,'posts',{text:'Reported fixture'},author.token)).data.post;
 const report={type:'post',target:post.uri,reason:'Spam',detail:'Test report'};assert.equal((await api(app,'reports',report,reader.token)).status,201);await api(app,'reports',report,reader.token);
 const inbox=(await api(app,'admin',null,admin.token)).data;assert.equal(inbox.reports.length,1);assert.equal(inbox.reports[0].content.text,'Reported fixture');
 assert.equal((await api(app,'admin/action',{action:'remove-post',target:post.uri,reason:'Spam'},reader.token)).status,403);
 assert.equal((await api(app,'admin/action',{action:'remove-post',target:post.uri,reason:'Spam',report:inbox.reports[0].id},admin.token)).status,200);
 assert.equal((await api(app,'feed')).data.posts.some(p=>p.uri===post.uri),false);assert.equal((await api(app,'thread?uri='+encodeURIComponent(post.uri))).data.post.text,'[Removed for violating Community Rules]');
 assert.equal((await api(app,'likes',{uri:post.uri},reader.token)).status,410);
 assert.equal((await api(app,'admin/action',{action:'restore-post',target:post.uri,reason:'Appeal accepted'},admin.token)).status,200);
 assert.equal((await api(app,'feed')).data.posts.some(p=>p.uri===post.uri),true);
 const message=(await api(app,'messages',{recipient:reader.actor.id,text:'Private report fixture'},author.token)).data;
 assert.equal((await api(app,'reports',{type:'message',target:String(message.message.id),reason:'Phishing',detail:'Recipient report'},author.token)).status,404);
 assert.equal((await api(app,'reports',{type:'message',target:String(message.message.id),reason:'Phishing',detail:'Recipient report'},reader.token)).status,201);
 assert.equal((await api(app,'admin/action',{action:'suspend',target:'author.demo',reason:'Phishing'},admin.token)).status,200);
 assert.equal((await api(app,'posts',{text:'Suspended bypass'},author.token)).status,403);
 assert.equal((await api(app,'login',{handle:'author.demo',password:'original-password'})).status,403);
 assert.equal((await api(app,'admin/action',{action:'unsuspend',target:author.actor.id,reason:'Appeal accepted'},admin.token)).status,200);
 assert.equal((await api(app,'posts',{text:'Access restored'},author.token)).status,201);
 assert.equal((await api(app,'admin/action',{action:'suspend',target:'@ant',reason:'Self suspension'},admin.token)).status,400);
 const audit=(await api(app,'admin',null,admin.token)).data.audit;assert.equal(audit.length,4);assert.ok(audit.every(a=>a.admin===admin.actor.id&&a.reason));
 }finally{await app.stop();}
});

test('upstream password reset prevents concurrent code reuse or regeneration',async()=>{
 const db=new DatabaseSync(':memory:');db.exec("CREATE TABLE actors(id TEXT PRIMARY KEY,handle TEXT,password TEXT,salt TEXT);CREATE TABLE api_keys(actor TEXT,operator TEXT,revoked TEXT);INSERT INTO actors VALUES ('did:plc:test','network.demo',NULL,NULL)");let unblock,calls=0;const wait=new Promise(r=>unblock=r);let invalidated=false;
 const recovery=createRecovery(db,{resetRemote:async()=>{calls++;await wait;},invalidate:()=>invalidated=true});const code=recovery.issue('did:plc:test')[0];const pending=recovery.reset('network.demo',code,'replacement-password');
 assert.throws(()=>recovery.issue('did:plc:test'),{status:409});await assert.rejects(recovery.reset('network.demo',code,'replacement-password'),{status:400});unblock();await pending;assert.equal(calls,1);assert.equal(invalidated,true);assert.equal(recovery.status('did:plc:test').remaining,9);db.close();
});

test('encrypted remote backups are downloaded, decrypted, integrity checked, and restored without overwriting files',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'amerika-backup-'));const savedEnv={...process.env};const objects=new Map();const server=http.createServer(async(req,res)=>{const url=new URL(req.url,'http://test');if(req.method==='PUT'){const chunks=[];for await(const c of req)chunks.push(c);objects.set(url.pathname,Buffer.concat(chunks));res.writeHead(200,{ETag:'"backup-test"'});res.end();}else if(url.searchParams.has('list-type')){res.setHeader('Content-Type','application/xml');res.end('<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><IsTruncated>false</IsTruncated></ListBucketResult>');}else{const bytes=objects.get(url.pathname);res.writeHead(bytes?200:404,{'Content-Type':'application/octet-stream'});res.end(bytes);}});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 Object.assign(process.env,{BACKUP_S3_BUCKET:'test',BACKUP_S3_ENDPOINT:'http://127.0.0.1:'+server.address().port,BACKUP_S3_REGION:'us-east-1',BACKUP_S3_PATH_STYLE:'true',BACKUP_S3_ACCESS_KEY_ID:'test',BACKUP_S3_SECRET_ACCESS_KEY:'test',BACKUP_ENCRYPTION_KEY:'ab'.repeat(32)});const db=new DatabaseSync(join(dir,'source.sqlite'));db.exec("CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT);INSERT INTO settings VALUES ('fixture','Private backup fixture')");
 try{const ops=createOperations(db,dir);const result=await ops.take();assert.equal(result.remote,true);assert.ok(ops.status().remoteVerifiedAt);assert.equal(ops.status().overdue,false);const encrypted=[...objects.values()][0];assert.ok(!encrypted.includes(Buffer.from('Private backup fixture')));const restored=decryptBackup(encrypted,process.env.BACKUP_ENCRYPTION_KEY);assert.ok(restored.includes(Buffer.from('Private backup fixture')));assert.throws(()=>decryptBackup(encrypted,'cd'.repeat(32)));const corrupt=Buffer.from(encrypted);corrupt[20]^=1;assert.throws(()=>decryptBackup(corrupt,process.env.BACKUP_ENCRYPTION_KEY));
 const source=join(dir,'download.sqlite.enc'),target=join(dir,'restored.sqlite');await writeFile(source,encrypted);const output=execFileSync(process.execPath,['scripts/restore-backup.mjs',source,target],{encoding:'utf8'});assert.match(output,/integrity checked/);const check=new DatabaseSync(target,{readOnly:true});assert.equal(check.prepare('SELECT value FROM settings WHERE key=?').get('fixture').value,'Private backup fixture');check.close();assert.throws(()=>execFileSync(process.execPath,['scripts/restore-backup.mjs',source,target],{stdio:'pipe'}));assert.ok((await readdir(join(dir,'backups'))).some(f=>f.endsWith('.sqlite')));
 }finally{db.close();for(const k of Object.keys(process.env))if(!(k in savedEnv))delete process.env[k];Object.assign(process.env,savedEnv);await new Promise(r=>server.close(r));await rm(dir,{recursive:true,force:true});}
});
