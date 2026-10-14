import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {createHmac} from 'node:crypto';
import {spawn} from 'node:child_process';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {DatabaseSync} from 'node:sqlite';
test('moderation webhooks sign public post events, persist retries, isolate ownership and stop on revocation',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'amerika-moderation-hooks-')),received=[];let failFirst=true,app,db;
 const receiver=createServer(async(req,res)=>{let raw='';for await(const c of req)raw+=c;received.push({raw,headers:req.headers,body:JSON.parse(raw)});res.writeHead(failFirst?500:204);failFirst=false;res.end();});await new Promise(r=>receiver.listen(0,'127.0.0.1',r));
 const url='http://127.0.0.1:'+receiver.address().port+'/events';
 async function launch(){const child=spawn(process.execPath,['server.mjs'],{env:{...process.env,PORT:'0',HOST:'127.0.0.1',PDS_URL:'',DATA_DIR:dir,ADMIN_HANDLES:'hookadmin.demo',SESSION_ENCRYPTION_KEY:'bd'.repeat(32),ALLOW_TEST_WEBHOOKS:'1'},stdio:['ignore','pipe','pipe']});const base=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Startup timed out')),10000);child.stdout.on('data',d=>{const m=String(d).match(/"port":(\d+)/);if(m){clearTimeout(timer);resolve('http://127.0.0.1:'+m[1]);}});child.once('exit',()=>reject(Error('Startup failed')));});return {base,stop:()=>new Promise(r=>{child.once('exit',r);child.kill();})};}
 const api=async(path,body,token)=>{const r=await fetch(app.base+'/api/'+path,{method:body?'POST':'GET',headers:{...(body?{'Content-Type':'application/json'}:{}),...(token?{Authorization:'Bearer '+token}:{})},...(body?{body:JSON.stringify(body)}:{})});return {status:r.status,data:await r.json()};};
 async function wait(check){const end=Date.now()+10000;while(Date.now()<end){if(await check())return;await new Promise(r=>setTimeout(r,100));}assert.fail('Delivery timed out');}
 try{app=await launch();const register=async handle=>(await api('register',{handle,name:handle,kind:'human',password:'hook-test-password',americanConfirmed:true,rulesAccepted:true})).data;
  const admin=await register('hookadmin.demo'),other=await register('hookmember.demo');const key=(await api('moderation/connection',{name:'Post reviewer',neverExpires:true},admin.token)).data;
  assert.equal((await api('moderation/webhook',{connection:key.id,url},other.token)).status,403);
  assert.equal((await api('moderation/webhook',{connection:key.id,url:'http://127.0.0.1:1'},admin.token)).status,200,'Test-mode local receiver is allowed');
  const customSecret='moderation-receiver-test-secret-123';const hook=(await api('moderation/webhook',{connection:key.id,url,signingSecret:customSecret},admin.token)).data;assert.equal(hook.secret,customSecret);
  assert.equal((await api('webhooks',{actor:other.actor.id,url,events:['post_created']},other.token)).status,400,'Ordinary users cannot subscribe to global posts');
  assert.equal((await api('webhooks',null,admin.token)).data.webhooks.length,0,'Moderation hooks are isolated from account notifications');
  const listed=(await api('moderation/webhooks?connection='+key.id,null,admin.token)).data;assert.ok(!JSON.stringify(listed).includes(hook.secret));
  const root=(await api('posts',{text:'New public content'},other.token)).data.post;await wait(()=>received.length===1);
  const first=received[0];assert.equal(first.body.type,'moderation.post.created');assert.equal(first.body.connectionId,key.id);assert.equal(first.body.data.post.uri,root.uri);assert.equal(first.body.data.post.text,undefined);
  const stamp=first.headers['amerika-webhook-timestamp'];assert.equal(first.headers['amerika-webhook-signature'],'v1='+createHmac('sha256',hook.secret).update(stamp+'.'+first.raw).digest('hex'));
  await wait(async()=>{const list=(await api('moderation/webhooks?connection='+key.id,null,admin.token)).data;return list.webhooks.find(w=>w.id===hook.id).deliveries[0]?.status==='pending';});
  await app.stop();app=null;db=new DatabaseSync(join(dir,'botsky.sqlite'));assert.ok(!db.prepare('SELECT secret FROM webhooks WHERE id=?').get(hook.id).secret.includes(hook.secret));db.prepare('UPDATE webhook_deliveries SET next_at=0 WHERE hook=?').run(hook.id);db.close();db=null;app=await launch();await wait(()=>received.length===2);assert.equal(received[1].body.id,first.body.id,'Retry keeps the event ID across restarts');
  await api('messages',{recipient:admin.actor.id,text:'Private chat must not trigger moderation'},other.token);await new Promise(r=>setTimeout(r,1200));assert.equal(received.length,2);
  const reply=(await api('posts',{text:'Public reply event',parent:root.uri},other.token)).data.post;await wait(()=>received.length===3);assert.equal(received[2].body.data.post.parent,root.uri);
  const rotatedSecret='moderation-rotated-test-secret-456';assert.equal((await api('webhooks/secret',{id:hook.id,signingSecret:rotatedSecret},admin.token)).status,404);assert.equal((await api('moderation/webhook-secret',{connection:key.id,id:hook.id,signingSecret:rotatedSecret},other.token)).status,403);assert.equal((await api('moderation/webhook-secret',{connection:key.id,id:hook.id,signingSecret:rotatedSecret},admin.token)).status,200);
  await api('moderation/webhook-test',{connection:key.id,id:hook.id},admin.token);await wait(()=>received.length===4);assert.equal(received[3].body.type,'webhook.test');assert.equal(received[3].headers['amerika-webhook-signature'],'v1='+createHmac('sha256',rotatedSecret).update(received[3].headers['amerika-webhook-timestamp']+'.'+received[3].raw).digest('hex'));
  assert.equal((await api('webhooks/test',{id:hook.id},admin.token)).status,404,'Account endpoint cannot manage moderation hooks');
  await api('moderation/webhook-disable',{connection:key.id,id:hook.id},admin.token);await api('posts',{text:'Disabled receiver does not wake',parent:reply.uri},other.token);await new Promise(r=>setTimeout(r,1200));assert.equal(received.length,4);
  const key2=(await api('moderation/connection',{name:'Expiry reviewer',neverExpires:true},admin.token)).data;const hook2=(await api('moderation/webhook',{connection:key2.id,url},admin.token)).data;
  db=new DatabaseSync(join(dir,'botsky.sqlite'));db.prepare('UPDATE moderation_mcp SET expires=? WHERE id=?').run('2000-01-01T00:00:00Z',key2.id);db.close();db=null;await api('posts',{text:'Expired connection event',parent:root.uri},other.token);await wait(async()=>{const list=(await api('moderation/webhooks?connection='+key2.id,null,admin.token)).data;return list.webhooks.find(w=>w.id===hook2.id).deliveries[0]?.status==='canceled';});assert.equal(received.length,4);
  await api('moderation/revoke',{id:key.id},admin.token);assert.equal((await api('moderation/webhook',{connection:key.id,url},admin.token)).status,400);
  const key3=(await api('moderation/connection',{name:'Removal reviewer',neverExpires:true},admin.token)).data;const hook3=(await api('moderation/webhook',{connection:key3.id,url},admin.token)).data;
  db=new DatabaseSync(join(dir,'botsky.sqlite'));db.exec('BEGIN');db.prepare('INSERT INTO posts(uri,cid,author,text,created) VALUES (?,?,?,?,?)').run('preview:removed-before-delivery','preview',other.actor.id,'Removed before delivery',new Date().toISOString());db.prepare('UPDATE posts SET removed_at=? WHERE uri=?').run(new Date().toISOString(),'preview:removed-before-delivery');db.exec('COMMIT');db.close();db=null;
  await wait(async()=>{const list=(await api('moderation/webhooks?connection='+key3.id,null,admin.token)).data;return list.webhooks.find(w=>w.id===hook3.id).deliveries[0]?.status==='canceled';});assert.equal(received.length,4,'Removed content is skipped before delivery');
  await api('moderation/revoke',{id:key3.id},admin.token);assert.equal((await api('moderation/webhooks?connection='+key3.id,null,admin.token)).data.webhooks[0].enabled,0,'Connection revocation disables linked receivers');
 }finally{db?.close();if(app)await app.stop();await new Promise(r=>receiver.close(r));await rm(dir,{recursive:true,force:true});}
});
