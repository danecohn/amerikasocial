// SPDX-License-Identifier: GPL-3.0-or-later
import {companyHostRoute} from '../company-host.mjs';
import {request as httpRequest} from 'node:http';import test from 'node:test';import assert from 'node:assert/strict';import {spawn} from 'node:child_process';import {mkdtemp,rm} from 'node:fs/promises';import {tmpdir} from 'node:os';import {join} from 'node:path';
test('company domains serve public marketing while existing app origins and account gates stay intact',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'vigil-company-host-'));const child=spawn(process.execPath,['server.mjs'],{env:{...process.env,HOST:'127.0.0.1',PORT:'0',DATA_DIR:dir,PUBLIC_ORIGIN:'https://www.amerika.social',PDS_URL:'',BACKUPS_ENABLED:'false',HUMAN_CAPTCHA_REQUIRED:'false',PUSH_NOTIFICATIONS_ENABLED:'false',STRIPE_SECRET_KEY:''},stdio:['ignore','pipe','pipe']});
 try{const base=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('startup timeout')),15000);child.stdout.on('data',b=>{const m=String(b).match(/"port":(\d+)/);if(m){clearTimeout(timer);resolve('http://127.0.0.1:'+m[1])}});child.once('exit',()=>reject(Error('server exited')))});
 const request=(path,host='vigiltech.org',extra={})=>new Promise((resolve,reject)=>{const req=httpRequest(base+path,{method:extra.method||'GET',headers:{host,...extra.headers}},res=>{const chunks=[];res.on('data',b=>chunks.push(b));res.on('end',()=>resolve(new Response(Buffer.concat(chunks),{status:res.statusCode,headers:res.headers})));res.on('error',reject)});req.on('error',reject);req.setTimeout(15000,()=>req.destroy(Error('request timeout')));req.end(extra.body)});
 const home=await request('/');assert.equal(home.status,200);const html=await home.text();assert.ok(html.includes('<h1>VigilTech <span>Software and services.</span></h1>'));assert.ok(html.includes('/brand/products/office.png'));assert.ok(html.includes('VigilTech Game Producer'));assert.ok(html.includes('VigilOS'));assert.ok(html.includes('href="https://www.amerika.social/social"'));assert.ok(!html.includes('Calm software,'));
 const head=await request('/','vigiltech.org',{method:'HEAD'});assert.equal(head.status,200);assert.equal(await head.text(),'');
 const alias=await request('/downloads?product=office','www.vigiltech.org');assert.equal(alias.status,302);assert.equal(alias.headers.get('location'),'https://vigiltech.org/downloads?product=office');
 for(const path of ['/social','/sso/auth','/api/me','/search/?q=test']){const response=await request(path);assert.equal(response.status,302);assert.equal(response.headers.get('location'),'https://www.amerika.social'+path)}
 assert.equal((await request('/api/login','vigiltech.org',{method:'POST',headers:{'content-type':'application/json'},body:'{}'})).status,405);
 const platform=await request('/','www.amerika.social');assert.equal(platform.status,200);assert.ok(!(await platform.text()).includes('<h1>VigilTech <span>Software and services.</span></h1>'));
 assert.equal((await request('/brand/products/office.png')).status,200);
 }finally{await new Promise(resolve=>{if(child.exitCode!==null)return resolve();child.once('exit',resolve);child.kill()});await rm(dir,{recursive:true,force:true})}
});

test('both public release APIs remain on the company origin',()=>{for(const path of ['/api/software-downloads','/api/fmjournal-downloads'])assert.equal(companyHostRoute({method:'GET',headers:{host:'vigiltech.org'}},new URL('https://vigiltech.org'+path)),null)});
