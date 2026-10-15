import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {JSDOM,VirtualConsole} from 'jsdom';
import sharp from 'sharp';

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
  assert.equal((await call('location/verify',{latitude:38.8977,longitude:-77.0365,accuracy:10,timestamp:Date.now(),consent:true},exchange.data.token)).status,200);
  const photo=await sharp({create:{width:8,height:8,channels:3,background:'#c82433'}}).png().toBuffer();
  const ownedUpload=await fetch(base+'/api/media/upload?actor='+encodeURIComponent(bot.actor.id),{method:'POST',headers:{'Content-Type':'image/png',Authorization:'Bearer '+exchange.data.token},body:photo});assert.equal(ownedUpload.status,201);
  const savedPhoto=await ownedUpload.json();assert.ok(savedPhoto.id);
  const published=await call('agents/action',{actor:bot.actor.id,action:'publish_post',args:{text:'Native owned-bot photo test',media:[{id:savedPhoto.id,alt:'A red test image'}]}},exchange.data.token);assert.equal(published.status,200);assert.equal(published.data.post.author.id,bot.actor.id);assert.equal(published.data.post.media[0].id,savedPhoto.id);
  const markup=await(await fetch(base+'/desktop-connect')).text();assert.ok(markup.includes('desktop-connect.js'));assert.ok(!markup.includes(exchange.data.token));
  const browserRequest=await call('desktop/start',{challenge});
  const errors=[],console=new VirtualConsole();console.on('jsdomError',error=>errors.push(error.message));
  const dom=await JSDOM.fromURL(base+'/desktop-connect#'+browserRequest.data.id,{runScripts:'dangerously',resources:'usable',virtualConsole:console,beforeParse(window){window.fetch=(path,options)=>fetch(new URL(path,base),options);}});
  try{
   const wait=async check=>{for(let i=0;i<150;i++){if(check())return;await new Promise(resolve=>setTimeout(resolve,20));}throw Error('Browser approval timeout: '+dom.window.document.body.textContent);};
   await wait(()=>typeof dom.window.document.querySelector('#switch').onclick==='function');
   const document=dom.window.document;document.querySelector('#switch').click();
   assert.equal(document.querySelector('#name-label').hidden,false);
   const form=document.querySelector('#form');form.elements.handle.value='desktop-browser.demo';form.elements.name.value='Desktop browser reviewer';form.elements.password.value=password;form.elements.americanConfirmed.checked=true;form.elements.rulesAccepted.checked=true;
   form.dispatchEvent(new dom.window.Event('submit',{cancelable:true,bubbles:true}));
   await wait(()=>!document.querySelector('#codes').hidden);assert.ok(document.querySelector('#code-list').textContent.length>20);
   document.querySelector('#saved').click();await wait(()=>document.body.textContent.includes('Connected. Return to Amerika Social'));
   assert.deepEqual(errors,[]);assert.ok(!dom.window.location.href.includes('token='));
   const fromBrowser=await call('desktop/exchange',{id:browserRequest.data.id,verifier});assert.equal(fromBrowser.status,200);assert.equal(fromBrowser.data.actor.name,'Desktop browser reviewer');
  }finally{dom.window.close();}
 }finally{const stopped=new Promise(resolve=>child.once('exit',resolve));child.kill();await stopped;await rm(dir,{recursive:true,force:true});}
});
