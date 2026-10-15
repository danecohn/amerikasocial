import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';

test('desktop browser pairing creates an independent session and bot media delegation is owner-bound',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'amerika-desktop-integration-'));
 const child=spawn(process.execPath,['server.mjs'],{env:{...process.env,PORT:'0',HOST:'127.0.0.1',PDS_URL:'',DATA_DIR:dir,SESSION_ENCRYPTION_KEY:'c7'.repeat(32),STRIPE_SECRET_KEY:'',STRIPE_WEBHOOK_SECRET:'',HUMAN_CAPTCHA_REQUIRED:'false',TURNSTILE_SITE_KEY:'',TURNSTILE_SECRET_KEY:'',PUSH_NOTIFICATIONS_ENABLED:'false'},stdio:['ignore','pipe','pipe']});let logs='';child.stderr.on('data',d=>logs+=d);
 try{
  const base=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Startup timeout '+logs)),15000);child.stdout.on('data',d=>{const m=String(d).match(/"port":(\d+)/);if(m){clearTimeout(timer);resolve('http://127.0.0.1:'+m[1]);}});child.once('exit',()=>reject(Error('Startup failed '+logs)));});
  const call=async(path,body,token)=>{const r=await fetch(base+'/api/'+path,{method:body?'POST':'GET',headers:{...(body?{'Content-Type':'application/json'}:{}),...(token?{Authorization:'Bearer '+token}:{})},...(body?{body:JSON.stringify(body)}:{})});return {status:r.status,data:await r.json()};};
  const password='Synthetic-Desktop-Test-2026!',register=async(handle,owner)=>{const r=await call(owner?'agents':'register',{handle,name:handle,password,kind:'human',americanConfirmed:true,rulesAccepted:true},owner);assert.ok(r.status===200||r.status===201,JSON.stringify(r));return r.data;};
  const human=await register('desktop-human.demo'),bot=await register('desktop-bot.demo',human.token),other=await register('desktop-other.demo');
  const verifier='u'.repeat(64),challenge=createHash('sha256').update(verifier).digest('base64url');
  const start=await call('desktop/start',{challenge});assert.equal(start.status,201);
  const id=start.data.id;assert.equal((await call('desktop/approve',{id})).status,401);
  const denied=await fetch(base+'/api/desktop/approve',{method:'POST',headers:{Origin:'https://evil.example','Content-Type':'application/json',Authorization:'Bearer '+human.token},body:JSON.stringify({id})});assert.equal(denied.status,403);
  assert.equal((await call('desktop/approve',{id},human.token)).status,200);
  const exchange=await call('desktop/exchange',{id,verifier});assert.equal(exchange.status,200);assert.notEqual(exchange.data.token,human.token);assert.equal(exchange.data.actor.id,human.actor.id);
  assert.equal((await call('desktop/exchange',{id,verifier})).status,400);
  await call('logout',{},human.token);assert.equal((await call('me',null,exchange.data.token)).data.actor.id,human.actor.id);
  const upload=await fetch(base+'/api/media/upload?actor='+encodeURIComponent(bot.actor.id),{method:'POST',headers:{'Content-Type':'image/png',Authorization:'Bearer '+other.token},body:Buffer.from('bad')});assert.equal(upload.status,403);
  const markup=await(await fetch(base+'/desktop-connect')).text();assert.ok(markup.includes('desktop-connect.js'));assert.ok(!markup.includes(exchange.data.token));
 }finally{const stopped=new Promise(resolve=>child.once('exit',resolve));child.kill();await stopped;await rm(dir,{recursive:true,force:true});}
});
