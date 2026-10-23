import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {JSDOM,VirtualConsole} from 'jsdom';
const wait=async fn=>{const deadline=Date.now()+8000;while(Date.now()<deadline){if(fn())return;await new Promise(r=>setTimeout(r,20));}throw Error('UI timeout');};
test('Makk thread windows close, minimize, restore, maximize and respect editor Escape',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'makk-window-test-'));
 const child=spawn(process.execPath,['server.mjs'],{env:{...process.env,PORT:'0',HOST:'127.0.0.1',PDS_URL:'',DATA_DIR:dir,SESSION_ENCRYPTION_KEY:'a4'.repeat(32),STRIPE_SECRET_KEY:'',HUMAN_CAPTCHA_REQUIRED:'false',PUSH_NOTIFICATIONS_ENABLED:'false'},stdio:['ignore','pipe','pipe']});
 let dom;
 try{
  const base=await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>reject(Error('startup timeout')),10000);child.stdout.on('data',data=>{const found=String(data).match(/"port":(\d+)/);if(found){clearTimeout(timeout);resolve('http://127.0.0.1:'+found[1]);}});child.once('exit',()=>reject(Error('server exited')));});
  assert.equal((await fetch(base+'/makk.css')).status,200);
  for(const mobile of [false,true]){
   const errors=[],console=new VirtualConsole();console.on('jsdomError',error=>{if(!/navigation \(except hash changes\)/.test(error.message))errors.push(error.message);});
   dom=await JSDOM.fromURL(base,{runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,virtualConsole:console,beforeParse(w){w.fetch=(url,options)=>fetch(new URL(url,base),options);w.matchMedia=()=>({matches:mobile,addEventListener(){},removeEventListener(){}});w.scrollTo=()=>{};w.HTMLElement.prototype.scrollIntoView=()=>{};w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};}});
   const w=dom.window,d=w.document;
   await wait(()=>d.querySelector('#feed .post'));
   const threadButton=[...d.querySelectorAll('#feed button')].find(b=>b.textContent.includes('View thread'));
   assert.ok(threadButton);threadButton.click();await wait(()=>!d.querySelector('#thread-view').classList.contains('hidden'));
   const frame=d.querySelector('#thread-view'),min=d.querySelector('#thread-minimize'),max=d.querySelector('#thread-maximize');
   assert.ok(!d.querySelector('#feed-view').classList.contains('hidden'),'feed remains behind thread');
   min.click();assert.ok(frame.classList.contains('makk-minimized'));assert.equal(min.getAttribute('aria-expanded'),'false');
   min.click();assert.ok(!frame.classList.contains('makk-minimized'));max.click();assert.ok(frame.classList.contains('makk-maximized'));assert.equal(max.getAttribute('aria-pressed'),'true');max.click();assert.ok(!frame.classList.contains('makk-maximized'));
   d.querySelector('#auth-dialog').showModal();d.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));assert.ok(!frame.classList.contains('hidden'),'an editor/dialog gets Escape before the thread');d.querySelector('#auth-dialog').close();
   d.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));await wait(()=>frame.classList.contains('hidden'));assert.equal(w.location.hash,'#feed');
   threadButton.click();await wait(()=>!frame.classList.contains('hidden'));d.querySelector('#thread-back').click();await wait(()=>frame.classList.contains('hidden'));
   assert.equal(d.title,'AltStack Social — Why Can\'t We Be Friends?');assert.deepEqual(errors,[]);dom.window.close();dom=null;
  }
 }finally{dom?.window.close();await new Promise(resolve=>{if(child.exitCode!==null)return resolve();child.once('exit',resolve);child.kill();});await rm(dir,{recursive:true,force:true});}
});
