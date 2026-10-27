import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {createLoginGuard,loginClientIp} from '../login-guard.mjs';
import {spawn} from 'node:child_process';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

test('device password timeouts escalate, persist, reset on success and expire without collecting passwords',()=>{
 const db=new DatabaseSync(':memory:');let time=100000;
 let guard=createLoginGuard(db,{now:()=>time,railway:false});
 const response=()=>({headers:{},setHeader(k,v){this.headers[k]=v;}});
 const req=(cookie,ip='203.0.113.5')=>({headers:{cookie},socket:{remoteAddress:ip}});
 const res=response();guard.identity(req(),res);const cookie=res.headers['Set-Cookie'].split(';')[0];
 const ids=guard.identity(req(cookie),response());
 for(let i=0;i<4;i++){const end=guard.begin(ids);guard.failure(ids);end();}
 const end=guard.begin(ids);assert.throws(()=>guard.failure(ids),e=>e.retryAfter===30);end();
 guard=createLoginGuard(db,{now:()=>time,railway:false});assert.throws(()=>guard.begin(ids),e=>e.retryAfter===30);
 const other=guard.identity(req(),response());assert.doesNotThrow(()=>guard.begin(other)());
 time+=30001;const retry=guard.begin(ids);assert.throws(()=>guard.failure(ids),e=>e.retryAfter===120);retry();
 for(const seconds of [300,900,3600,3600]){time+=3600001;const release=guard.begin(ids);assert.throws(()=>guard.failure(ids),e=>e.retryAfter===seconds);release();}
 time+=3600001;guard.success(ids);assert.doesNotThrow(()=>guard.begin(ids)());guard.failure(ids);
 time+=86400001;assert.doesNotThrow(()=>guard.begin(ids)());guard.failure(ids);assert.equal(db.prepare('SELECT failures FROM login_failures WHERE id=?').get(ids.device).failures,1);
 assert.ok(db.prepare('SELECT id FROM login_failures').all().every(r=>/^[a-f0-9]{64}$/.test(r.id)));
 db.close();
});
test('forged or omitted cookies retain a network backstop, concurrent guesses cannot bypass device lock and only Railway trusts its client IP',()=>{
 const db=new DatabaseSync(':memory:');let time=100000;const guard=createLoginGuard(db,{now:()=>time,railway:true});
 const res={setHeader(){}};const req={headers:{'x-real-ip':'203.0.113.7',cookie:'amerika_device='+'a'.repeat(64)+'.'+'b'.repeat(64)},socket:{remoteAddress:'127.0.0.1'}};
 assert.equal(loginClientIp(req,false),'127.0.0.1');assert.equal(loginClientIp(req,true),'203.0.113.7');
 assert.equal(loginClientIp({...req,headers:{'x-real-ip':'bad'}},true),'127.0.0.1');
 const ids=guard.identity(req,res),noCookie=guard.identity({...req,headers:{'x-real-ip':'203.0.113.7'}},res);assert.deepEqual(ids,noCookie);
 const end=guard.begin(ids);assert.throws(()=>guard.begin(ids),e=>e.retryAfter===1);end();
 for(let i=0;i<29;i++)guard.failure({...ids,device:String(i)});
 assert.throws(()=>guard.failure({...ids,device:'fresh'}),e=>e.retryAfter===30);
 assert.throws(()=>guard.begin({...ids,device:'another'}),e=>e.retryAfter===30);
 db.close();
});

test('login route blocks the fifth bad password, reports Retry-After, isolates devices and leaves recovery available',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'amerika-login-guard-'));
 const child=spawn(process.execPath,['server.mjs'],{env:{...process.env,PDS_URL:'',PORT:'0',HOST:'127.0.0.1',DATA_DIR:dir,RAILWAY_ENVIRONMENT_ID:''},stdio:['ignore','pipe','pipe']});
 const base=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Startup timed out')),10000);child.stdout.on('data',d=>{const m=String(d).match(/"port":(\d+)/);if(m){clearTimeout(timer);resolve('http://127.0.0.1:'+m[1]);}});child.once('exit',()=>reject(Error('Server exited')));});
 const post=(path,body,cookie)=>fetch(base+'/api/'+path,{method:'POST',headers:{'Content-Type':'application/json',...(cookie?{Cookie:cookie}:{})},body:JSON.stringify(body)});
 try{
  const config=await fetch(base+'/api/config'),cookie=config.headers.get('set-cookie').split(';')[0];assert.match(config.headers.get('set-cookie'),/HttpOnly; SameSite=Strict/);
  const otherCookie=(await fetch(base+'/api/config')).headers.get('set-cookie').split(';')[0];
  assert.equal((await post('register',{handle:'guard.demo',name:'Guard',kind:'human',password:'guard-correct-password',humanConfirmed:true,country:'US',rulesAccepted:true},cookie)).status,200);
  for(let i=0;i<4;i++)assert.equal((await post('login',{handle:i%2?'@guard.demo':'GUARD.DEMO',password:'wrong-password'},cookie)).status,401);
  const fifth=await post('login',{handle:'guard.demo',password:'wrong-password'},cookie);assert.equal(fifth.status,429);assert.equal(fifth.headers.get('retry-after'),'30');assert.equal((await fifth.json()).retryAfter,30);
  assert.equal((await post('login',{handle:'guard.demo',password:'guard-correct-password'},cookie)).status,429,'Correct passwords must wait out the same device timeout');
  assert.equal((await post('login',{handle:'guard.demo',password:'guard-correct-password'},otherCookie)).status,200,'A different device is not blocked after only five failures');
  const recovery=await post('recovery/reset',{handle:'guard.demo',code:'not-a-real-code',password:'guard-new-password'},cookie);assert.notEqual(recovery.status,429,'Device sign-in timeout must not prohibit recovery');
  const db=new DatabaseSync(join(dir,'botsky.sqlite'));db.prepare('UPDATE login_failures SET blocked_until=0').run();db.close();
  const sixth=await post('login',{handle:'guard.demo',password:'wrong-password'},cookie);assert.equal(sixth.status,429);assert.equal(sixth.headers.get('retry-after'),'120');
 }finally{const exited=new Promise(resolve=>child.once('exit',resolve));child.kill();await exited;await rm(dir,{recursive:true,force:true});}
});
