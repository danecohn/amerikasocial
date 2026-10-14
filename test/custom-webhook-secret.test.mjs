import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {createServer} from 'node:http';
import {createHmac} from 'node:crypto';
import {createWebhooks,standardWebhookKey} from '../webhooks.mjs';

test('custom account webhook secrets sign deliveries exactly, stay encrypted, rotate securely and keep generated defaults',async()=>{
 const db=new DatabaseSync(':memory:');
 db.exec(`CREATE TABLE actors(id TEXT PRIMARY KEY,kind TEXT,operator_id TEXT,suspended_at TEXT); INSERT INTO actors VALUES ('owner','human',NULL,NULL),('other','human',NULL,NULL); CREATE TABLE posts(uri TEXT,created TEXT); CREATE TABLE notifications(id INTEGER,recipient TEXT,type TEXT,created TEXT);`);
 let received;const receiver=createServer(async(req,res)=>{let raw='';for await(const b of req)raw+=b;received={raw,headers:req.headers};res.writeHead(204);res.end();});await new Promise(r=>receiver.listen(0,'127.0.0.1',r));
 const hooks=createWebhooks(db,{key:'ab'.repeat(32),testing:true}),base={actor:'owner',url:'http://127.0.0.1:'+receiver.address().port,events:['reply']};hooks.stop();
 try{
  const secret='workflow-supplied-signing-key-123';const hook=await hooks.create('owner',{...base,signingSecret:secret});assert.equal(hook.secret,secret);
  assert.notEqual(db.prepare('SELECT secret FROM webhooks WHERE id=?').get(hook.id).secret,secret);assert.ok(!JSON.stringify(hooks.list('owner')).includes(secret));
  hooks.test('owner',hook.id);await hooks.tick();assert.equal(received.headers['amerika-webhook-signature'],'v1='+createHmac('sha256',secret).update(received.headers['amerika-webhook-timestamp']+'.'+received.raw).digest('hex'));
  for(const signingSecret of ['short','has spaces in this secret',null,123,'x'.repeat(513),'x'.repeat(20)+'\n'])await assert.rejects(hooks.create('owner',{...base,signingSecret}),e=>e.status===400);
  assert.throws(()=>hooks.setSecret('other',hook.id,'another-signing-secret-456'),e=>e.status===404);
  const next='another-signing-secret-456';hooks.setSecret('owner',hook.id,next);hooks.test('owner',hook.id);await hooks.tick();assert.equal(received.headers['amerika-webhook-signature'],'v1='+createHmac('sha256',next).update(received.headers['amerika-webhook-timestamp']+'.'+received.raw).digest('hex'));assert.ok(!JSON.stringify(hooks.list('owner')).includes(next));
  assert.throws(()=>hooks.setSecret('owner',hook.id,''),e=>e.status===400);
  const grokKey=Buffer.alloc(32,7),grokSecret='whsec_'+grokKey.toString('base64');hooks.setSecret('owner',hook.id,grokSecret);hooks.test('owner',hook.id);await hooks.tick();assert.equal(received.headers['webhook-id'],received.headers['amerika-webhook-id']);assert.equal(received.headers['webhook-timestamp'],received.headers['amerika-webhook-timestamp']);assert.equal(received.headers['webhook-signature'],'v1,'+createHmac('sha256',grokKey).update(received.headers['webhook-id']+'.'+received.headers['webhook-timestamp']+'.'+received.raw).digest('base64'));assert.deepEqual(standardWebhookKey(grokKey.toString('base64')),grokKey);assert.throws(()=>standardWebhookKey('whsec_not-a-valid-key'));
  const generated=await hooks.create('owner',base);assert.match(generated.secret,/^as_whsec_/);
 }finally{hooks.stop();await new Promise(r=>receiver.close(r));db.close();}
});
