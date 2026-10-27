import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {JSDOM} from 'jsdom';

test('desktop homepage opens the AltStack app hub and preserves account and app destinations',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'altstack-platform-'));
 const child=spawn(process.execPath,['server.mjs'],{env:{...process.env,PORT:'0',HOST:'127.0.0.1',DATA_DIR:dir,PDS_URL:'',SESSION_ENCRYPTION_KEY:'a4'.repeat(32),STRIPE_SECRET_KEY:'',HUMAN_CAPTCHA_REQUIRED:'false',PUSH_NOTIFICATIONS_ENABLED:'false',OFFICE_ORIGIN:'https://office.example.test'},stdio:['ignore','pipe','pipe']});
 try{
  const base=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('startup timeout')),20000);child.stdout.on('data',data=>{const match=String(data).match(/"port":(\d+)/);if(match){clearTimeout(timer);resolve('http://127.0.0.1:'+match[1]);}});child.once('exit',()=>{clearTimeout(timer);reject(Error('server exited'));});});
  const dom=await JSDOM.fromURL(base,{runScripts:'dangerously',resources:'usable',beforeParse(window){window.fetch=(path,options)=>fetch(new URL(path,base),options);}});let d=dom.window.document;for(let i=0;i<100&&!d.querySelector('.desktop-app');i++)await new Promise(r=>setTimeout(r,20));
  assert.match(d.title,/Cohnsoft — Your desktop on the web/);
  assert.ok(d.querySelector('.desktop-app[href="/office"]'));for(const route of ['/office','/warehouse','/search/','/mail','/social'])assert.ok(d.querySelector('.dock-app[href="'+route+'"]'));assert.ok(d.body.textContent.includes('2 GB'));dom.window.close();
  for(const route of ['/social','/social/','/moderate']){
   const response=await fetch(base+route);assert.equal(response.status,200);
   assert.match(await response.text(),/id="feed-view"/);
  }
  for(const route of ['/office','/drive']){
   const response=await fetch(base+route,{redirect:'manual'});
   assert.equal(response.status,302);assert.equal(response.headers.get('location'),'https://office.example.test/');
  }
  for(const route of ['/platform.css','/platform.js','/platform-nav.css'])assert.equal((await fetch(base+route)).status,200);
  const downloads=new JSDOM(await (await fetch(base+'/downloads')).text()).window.document;
  assert.match(downloads.title,/Cohnsoft downloads/);
  assert.ok(downloads.querySelector('.downloads-products a[href="/downloads/mail"]'));
  assert.ok(!/Amerika|Makk/i.test(downloads.body.textContent));
  assert.equal(downloads.body.dataset.product,'social');assert.ok(downloads.querySelector('#download-cards'));
  assert.equal((await (await fetch(base+'/manifest.webmanifest')).json()).start_url,'/');
 }finally{await new Promise(resolve=>{if(child.exitCode!==null)return resolve();child.once('exit',resolve);child.kill();});await rm(dir,{recursive:true,force:true});}
});
