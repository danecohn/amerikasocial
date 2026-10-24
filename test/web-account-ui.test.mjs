import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {JSDOM,VirtualConsole} from 'jsdom';
const wait=async predicate=>{const until=Date.now()+8000;while(Date.now()<until){if(predicate())return;await new Promise(r=>setTimeout(r,20));}throw Error('Website UI did not reach the expected state.');};
test('mobile and desktop account UI can manage blocks, owned bot profiles and developer navigation',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'amerika-web-ui-'));
 const child=spawn(process.execPath,['server.mjs'],{env:{...process.env,PORT:'0',HOST:'127.0.0.1',PDS_URL:'',DATA_DIR:dir,HUMAN_CAPTCHA_REQUIRED:'false',TURNSTILE_SITE_KEY:'',TURNSTILE_SECRET_KEY:'',SESSION_ENCRYPTION_KEY:'a4'.repeat(32),PUSH_NOTIFICATIONS_ENABLED:'false',STRIPE_SECRET_KEY:''},stdio:['ignore','pipe','pipe']});
 let dom;try{
  const base=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Test startup timeout')),10000);child.stdout.on('data',d=>{const m=String(d).match(/"port":(\d+)/);if(m){clearTimeout(timer);resolve('http://127.0.0.1:'+m[1]);}});child.once('exit',()=>reject(Error('Test server failed')));});
  const password='Synthetic-Web-Test-2026!';
  const call=async(path,body,token)=>{const r=await fetch(base+'/api/'+path,{method:body?'POST':'GET',headers:{...(body?{'Content-Type':'application/json'}:{}),...(token?{Authorization:'Bearer '+token}:{})},...(body?{body:JSON.stringify(body)}:{})});return {status:r.status,data:await r.json()};};
  const register=async handle=>(await call('register',{handle,name:handle,password,kind:'human',humanConfirmed:true,country:'US',rulesAccepted:true})).data;
  const owner=await register('owner.demo'),neighbor=await register('neighbor.demo');
  await call('posts',{text:'Neighbor post for block visibility checks'},neighbor.token);
  const bot=(await call('agents',{handle:'owned-bot.demo',name:'Owned Bot',password,humanConfirmed:true,country:'US',rulesAccepted:true},owner.token)).data.actor;
  for(const mobile of [true,false]){
   const errors=[],console=new VirtualConsole();console.on('jsdomError',e=>{if(!/navigation \(except hash changes\)/.test(e.message))errors.push(e.message);});
   dom=await JSDOM.fromURL(base+'/social#account',{runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,virtualConsole:console,beforeParse(w){w.sessionStorage.setItem('botsky-token',owner.token);w.fetch=(url,options)=>fetch(new URL(url,base),options);w.matchMedia=()=>({matches:mobile,addEventListener(){},removeEventListener(){}});w.scrollTo=()=>{};w.HTMLElement.prototype.scrollIntoView=()=>{};w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};}});
   const w=dom.window,d=w.document,submit=form=>form.dispatchEvent(new w.Event('submit',{cancelable:true,bubbles:true}));
   await wait(()=>d.querySelector('.settings-danger'));
   assert.equal(d.querySelector('[data-mobile=more]').getAttribute('aria-current'),'page');
   d.querySelector('[data-mobile=more]').click();
   const menu=mobile?d.querySelector('.mobile-dialog'):d.querySelector('#mobile-menu-dialog');assert.ok(menu);assert.ok(menu.querySelector('[data-view=developers]'));menu.querySelector('[data-view=account]').click();await wait(()=>d.querySelector('.settings-danger'));
   // Scope to the settings form, rather than the hidden sign-in dialog.
   const blockInput=d.querySelector('#account-settings input[name=handle]');blockInput.value='neighbor.demo';submit(blockInput.form);
   await wait(()=>d.querySelector('#account-action-content .primary'));
   d.querySelector('#account-action-content .primary').click();await wait(()=>d.querySelector('.settings-block-row'));
   assert.equal((await call('account/blocks',null,owner.token)).data.accounts[0].id,neighbor.actor.id);
   assert.ok(!d.querySelector('#feed').textContent.includes('Neighbor post for block visibility checks'));
   d.querySelector('.settings-block-row button').click();await wait(()=>!d.querySelector('.settings-block-row'));assert.equal((await call('account/blocks',null,owner.token)).data.accounts.length,0);
   assert.ok(d.querySelector('#feed').textContent.includes('Neighbor post for block visibility checks'));
   const select=d.querySelector('#account-settings>label select');select.value=bot.id;select.dispatchEvent(new w.Event('change',{bubbles:true}));await wait(()=>d.querySelector('#account-settings input[name=name]')?.value==='Owned Bot'||d.querySelector('#account-settings input[name=name]')?.value==='Updated Bot');
   const name=d.querySelector('#account-settings input[name=name]');name.value='Updated Bot';submit(name.form);await wait(()=>name.form.textContent.includes('Profile saved.'));assert.equal((await call('agents',null,owner.token)).data.agents.find(a=>a.id===bot.id).name,'Updated Bot');
   d.querySelector('[data-mobile=more]').click();const features=mobile?d.querySelector('.mobile-dialog'):d.querySelector('#mobile-menu-dialog');features.querySelector('[data-view=developers]').click();await wait(()=>d.querySelector('#agent-dashboard').textContent.includes('Bot display name'));assert.ok(d.querySelector('#agent-dashboard').textContent.includes('Your agents'));
   await wait(()=>w.eval('agentDashboardLoading')===false);
   assert.deepEqual(errors,[]);dom.window.close();dom=null;
  }
 }finally{dom?.window.close();await new Promise(resolve=>{if(child.exitCode!==null)return resolve();child.once('exit',resolve);child.kill();});await rm(dir,{recursive:true,force:true});}
});
