import {authorizeMcp} from './oauth-helper.mjs';
import {accountDesignations} from '../account-designations.mjs';
import { test } from 'node:test';

test('administrator country designation and permanent Plus preserve other grants and account ownership',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'amerika-designations-'));let app=await launch({DATA_DIR:dir,ACCOUNT_DESIGNATIONS:'{}',PERMANENT_PLUS_ACCOUNT_IDS:''});
 try{
  const register=async handle=>(await request(app.base,'/api/register',{handle,name:handle,kind:'human',password:'designation-test-password',americanConfirmed:true,rulesAccepted:true})).data;
  const member=await register('canadian.demo'),existing=await register('existing.demo');
  await app.stop();app=await launch({DATA_DIR:dir,ACCOUNT_DESIGNATIONS:JSON.stringify({[member.actor.id]:{country:'CA',permanentPlus:true}}),PERMANENT_PLUS_ACCOUNT_IDS:existing.actor.id});
  const profile=(await request(app.base,'/api/profile?id='+encodeURIComponent(member.actor.id))).data.actor;
  assert.equal(profile.americanStatus,null);assert.equal(profile.americanVerification,null);assert.deepEqual(profile.countryDesignation,{code:'CA',label:'Canadian',source:'platform',verified:true});assert.equal(profile.plus,true);
  const login=(await request(app.base,'/api/login',{handle:'canadian.demo',password:'designation-test-password'})).data;
  assert.equal((await request(app.base,'/api/billing',null,login.token)).data.permanentPlus,true);
  assert.equal((await request(app.base,'/api/billing/checkout',{},login.token)).status,409);
  assert.equal((await request(app.base,'/api/profile?id='+encodeURIComponent(existing.actor.id))).data.actor.plus,true);
  assert.equal(accountDesignations(JSON.stringify({[member.actor.id]:{country:'CA'}})).has('canadian.demo'),false);
  assert.throws(()=>accountDesignations('{bad'));assert.throws(()=>accountDesignations('{"id":{"country":"US"}}'));
 }finally{await app.stop();await rm(dir,{recursive:true,force:true});}
});
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtemp, rm, readdir, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import http from 'node:http';
import { DatabaseSync } from 'node:sqlite';
import { scryptSync } from 'node:crypto';

async function launch(env={}) {
  const dir=await mkdtemp(join(tmpdir(),'botsky-test-'));
  const child=spawn(process.execPath,['server.mjs'],{env:{...process.env,PDS_URL:'',PORT:'0',DATA_DIR:dir,...env},stdio:['ignore','pipe','pipe']});
  const base=await new Promise((resolve,reject)=>{let output='';const timer=setTimeout(()=>reject(new Error('Server startup timed out')),10000);child.once('exit',()=>{clearTimeout(timer);reject(new Error('Server exited during startup'));});child.stdout.on('data',data=>{output+=data;const match=output.match(/"port":(\d+)/);if(match){clearTimeout(timer);resolve(`http://127.0.0.1:${match[1]}`);}});});
  return {base,dir:env.DATA_DIR||dir,async stop(){const exited=new Promise(r=>child.once('exit',r));child.kill();await exited;await rm(dir,{recursive:true,force:true});}};
}
async function request(base,path,body,token,extra={}){const response=await fetch(base+path,{method:body?'POST':'GET',headers:{...(body?{'Content-Type':'application/json'}:{}),...(token?{Authorization:`Bearer ${token}`} : {}),...extra},...(body?{body:JSON.stringify(body)}:{})});return {status:response.status,data:await response.json()};}

test('Plus media, repost following feed, quote quota, streaming, deletion and durable attachments',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'amerika-media-'));let app=await launch({DATA_DIR:dir});
 try{
  const register=async handle=>(await request(app.base,'/api/register',{handle,name:handle,kind:'human',password:'media-test-password',americanConfirmed:true,rulesAccepted:true})).data;
  const owner=await register('media.demo'),viewer=await register('viewer.demo'),observer=await register('observer.demo');
  const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAACXBIWXMAAAPoAAAD6AG1e1JrAAAADElEQVQImWP4//8/AAX+Av5Y8msOAAAAAElFTkSuQmCC','base64');const video=await readFile(new URL('./fixtures/red.mp4',import.meta.url));
  const upload=async(bytes,mime,token)=>{const r=await fetch(app.base+'/api/media/upload',{method:'POST',headers:{'Content-Type':mime,...(token?{Authorization:'Bearer '+token}:{})},body:bytes});return {status:r.status,data:await r.json()};};
  assert.equal((await upload(png,'image/png')).status,401);assert.equal((await upload(png,'image/png',owner.token)).status,403);
  assert.equal((await request(app.base,'/api/posts',{text:'x'.repeat(301)},owner.token)).status,400);
  const db=new DatabaseSync(join(dir,'botsky.sqlite'));db.prepare('INSERT INTO billing_subscriptions VALUES (?,?,?,?,?,?,?)').run('sub_media',owner.actor.id,'cus_media','active',Math.floor(Date.now()/1000)+3600,0,new Date().toISOString());
  db.close();
  assert.equal((await upload(Buffer.from('<svg/>'),'image/png',owner.token)).status,400);
  const image=await upload(png,'image/png',owner.token),clip=await upload(video,'video/mp4',owner.token);assert.equal(image.status,201);assert.equal(clip.status,201);
  const iphonePhoto=await upload(await readFile(new URL('./fixtures/iphone.heic',import.meta.url)),'image/heic',owner.token);assert.equal(iphonePhoto.status,201);assert.equal(iphonePhoto.data.mime,'image/webp');assert.ok(iphonePhoto.data.preview.startsWith('data:image/webp;base64,'));assert.equal((await upload(Buffer.from('bad HEIC'),'image/heic',owner.token)).status,400);
  if(process.env.FFMPEG_PATH){const iphoneUpload=await upload(await readFile(new URL('./fixtures/iphone.mov',import.meta.url)),'video/quicktime',owner.token);assert.equal(iphoneUpload.status,201);assert.equal(iphoneUpload.data.mime,'video/mp4');}
  assert.equal((await fetch(app.base+'/api/media?id='+image.data.id)).status,404,'Unattached files are private');
  assert.equal((await request(app.base,'/api/posts',{text:'Stolen',media:[{id:image.data.id,alt:''}]},viewer.token)).status,403);
  const imagePost=await request(app.base,'/api/posts',{text:'x'.repeat(833),media:[{id:image.data.id,alt:'A white pixel'}]},owner.token);assert.equal(imagePost.status,201);assert.equal(imagePost.data.post.text.length,833);assert.equal(imagePost.data.post.media[0].alt,'A white pixel');
  assert.equal((await request(app.base,'/api/posts',{text:'x'.repeat(834)},owner.token)).status,400);
  const videoPost=await request(app.base,'/api/posts',{text:'',media:[{id:clip.data.id,alt:'One second of red'}]},owner.token);assert.equal(videoPost.status,201);
  assert.equal((await request(app.base,'/api/posts',{text:'Mixed',media:[{id:image.data.id,alt:''},{id:clip.data.id,alt:''}]},owner.token)).status,400);
  const stream=await fetch(app.base+videoPost.data.post.media[0].url,{headers:{Range:'bytes=0-19'}});assert.equal(stream.status,206);assert.equal((await stream.arrayBuffer()).byteLength,20);
  assert.equal((await fetch(app.base+videoPost.data.post.media[0].url,{headers:{Range:'bytes=99999999-'}})).status,416);
  assert.equal((await request(app.base,'/api/reposts',{uri:imagePost.data.post.uri},viewer.token)).data.reposted,true);
  assert.equal((await request(app.base,'/api/billing',null,viewer.token)).data.originalPostsRemaining,3);
  await request(app.base,'/api/follows',{subject:viewer.actor.id},observer.token);
  const following=(await request(app.base,'/api/feed?following=1',null,observer.token)).data.posts;assert.equal(following.length,1);assert.equal(following[0].repostBy.id,viewer.actor.id);assert.equal(following[0].author.id,owner.actor.id);
  const quoted=await request(app.base,'/api/posts',{text:'A quote',quote:imagePost.data.post.uri},viewer.token);assert.equal(quoted.status,201);assert.equal(quoted.data.post.quote.uri,imagePost.data.post.uri);assert.equal((await request(app.base,'/api/billing',null,viewer.token)).data.originalPostsRemaining,2);
  assert.equal((await request(app.base,'/api/posts',{text:'Reply + quote',parent:imagePost.data.post.uri,quote:imagePost.data.post.uri},viewer.token)).status,400);
  const alerts=(await request(app.base,'/api/notifications',null,owner.token)).data.notifications;assert.ok(alerts.some(n=>n.type==='repost'));assert.ok(alerts.some(n=>n.type==='quote'));
  await app.stop();app=await launch({DATA_DIR:dir});assert.equal((await fetch(app.base+videoPost.data.post.media[0].url)).status,200);assert.equal((await request(app.base,'/api/thread?uri='+encodeURIComponent(quoted.data.post.uri))).data.post.quote.media.length,1);
  assert.equal((await request(app.base,'/api/reposts',{uri:imagePost.data.post.uri},viewer.token)).data.reposted,false);assert.equal((await request(app.base,'/api/feed?following=1',null,observer.token)).data.posts.length,1,'Only the quote remains');
  await request(app.base,'/api/posts/delete',{uri:imagePost.data.post.uri},owner.token);assert.equal((await fetch(app.base+imagePost.data.post.media[0].url)).status,404);const tombstone=(await request(app.base,'/api/thread?uri='+encodeURIComponent(quoted.data.post.uri))).data.post.quote;assert.equal(tombstone.deleted,1);assert.equal(tombstone.media.length,0);assert.equal((await request(app.base,'/api/reposts',{uri:imagePost.data.post.uri},viewer.token)).status,410);
 }finally{await app.stop();await rm(dir,{recursive:true,force:true});}
});

test('current location verification unlocks photos, never videos, and expiry or removal revokes access',async()=>{
 const app=await launch();
 try{
  const owner=(await request(app.base,'/api/register',{handle:'photo-owner.demo',name:'Photo owner',kind:'human',password:'photo-test-password',americanConfirmed:true,rulesAccepted:true})).data;
  const agent=(await request(app.base,'/api/agents',{handle:'photo-agent.demo',name:'Photo agent',password:'photo-test-password',americanConfirmed:true,rulesAccepted:true},owner.token)).data.actor;
  const agentKey=(await request(app.base,'/api/agent-keys',{actor:agent.id,name:'Photos',scopes:['post'],days:1},owner.token)).data.token;
  const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAACXBIWXMAAAPoAAAD6AG1e1JrAAAADElEQVQImWP4//8/AAX+Av5Y8msOAAAAAElFTkSuQmCC','base64');const video=await readFile(new URL('./fixtures/red.mp4',import.meta.url));
  const upload=async(bytes,mime,token=owner.token)=>{const r=await fetch(app.base+'/api/media/upload',{method:'POST',headers:{'Content-Type':mime,Authorization:'Bearer '+token},body:bytes});return {status:r.status,data:await r.json()};};
  const editDb=fn=>{const db=new DatabaseSync(join(app.dir,'botsky.sqlite'));try{fn(db);}finally{db.close();}};
  assert.equal((await upload(png,'image/png')).status,403);
  editDb(db=>db.prepare('INSERT INTO billing_subscriptions VALUES (?,?,?,?,?,?,?)').run('sub_old_plus',owner.actor.id,'cus_old','active',Math.floor(Date.now()/1000)+3600,0,new Date().toISOString()));
  const oldVideo=await upload(video,'video/mp4');assert.equal(oldVideo.status,201);editDb(db=>db.prepare('DELETE FROM billing_subscriptions WHERE actor=?').run(owner.actor.id));
  await request(app.base,'/api/location/verify',{consent:true,latitude:33.45,longitude:-112.07,accuracy:20,timestamp:Date.now()},owner.token);
  const image=await upload(png,'image/png');assert.equal(image.status,201);
  assert.equal((await upload(video,'video/mp4')).status,403);assert.equal((await upload(video,'video/mp4',agentKey)).status,403);
  assert.equal((await request(app.base,'/api/posts',{text:'Old video bypass',media:[{id:oldVideo.data.id,alt:''}]},owner.token)).status,403);
  assert.equal((await request(app.base,'/api/posts',{text:'Photos still use the free character cap '+ 'x'.repeat(300),media:[{id:image.data.id,alt:''}]},owner.token)).status,400);
  const posted=await request(app.base,'/api/posts',{text:'A verified photo',media:[{id:image.data.id,alt:'Pixel'}]},owner.token);assert.equal(posted.status,201);assert.equal((await request(app.base,'/api/billing',null,owner.token)).data.originalPostsRemaining,2);
  const agentImage=await upload(png,'image/png',agentKey);assert.equal(agentImage.status,201);assert.equal((await request(app.base,'/api/posts',{text:'Operator verified',media:[{id:agentImage.data.id,alt:''}]},agentKey)).status,201);
  editDb(db=>db.prepare('UPDATE actors SET us_location_verified_at=? WHERE id=?').run(new Date(Date.now()-91*86400000).toISOString(),owner.actor.id));
  assert.equal((await upload(png,'image/png')).status,403);assert.equal((await request(app.base,'/api/posts',{text:'Expired check',media:[{id:image.data.id,alt:''}],americanStatus:'verified'},owner.token)).status,403);
  await request(app.base,'/api/location/verify',{consent:true,latitude:33.45,longitude:-112.07,accuracy:20,timestamp:Date.now()},owner.token);await request(app.base,'/api/location/remove',{},owner.token);
  assert.equal((await upload(png,'image/png',agentKey)).status,403);assert.equal((await request(app.base,'/api/posts',{text:'Removed check',media:[{id:image.data.id,alt:''}]},owner.token)).status,403);
  assert.equal((await fetch(app.base+posted.data.post.media[0].url)).status,200,'Earlier photos remain visible');
 }finally{await app.stop();}
});

test('optional location status is session-only, persists without coordinates, and propagates to linked agents',async()=>{
 const app=await launch();
 try{
  const owner=(await request(app.base,'/api/register',{handle:'location.demo',name:'Location',kind:'human',password:'location-password',americanConfirmed:true,rulesAccepted:true,americanStatus:'verified'})).data;
  assert.equal(owner.actor.americanStatus,'self-declared');
  const other=(await request(app.base,'/api/register',{handle:'other.demo',name:'Other',kind:'human',password:'location-password',americanConfirmed:true,rulesAccepted:true})).data;
  const agent=(await request(app.base,'/api/agents',{handle:'location-agent.demo',name:'Agent',password:'location-password',americanConfirmed:true,rulesAccepted:true},owner.token)).data.actor;
  const valid={consent:true,latitude:33.45,longitude:-112.07,accuracy:30,timestamp:Date.now(),actor:other.actor.id};
  assert.equal((await request(app.base,'/api/location/verify',valid)).status,401);
  assert.equal((await request(app.base,'/api/location/verify',{...valid,consent:false},owner.token)).status,400);
  assert.equal((await request(app.base,'/api/location/verify',{...valid,latitude:43.65,longitude:-79.38},owner.token)).status,400);
  const verified=await request(app.base,'/api/location/verify',valid,owner.token);assert.equal(verified.status,200);assert.equal(verified.data.actor.americanStatus,'verified');assert.equal(verified.data.actor.plus,false);
  assert.equal((await request(app.base,'/api/me',null,other.token)).data.actor.americanStatus,'self-declared');
  const profile=(await request(app.base,'/api/profile?id='+encodeURIComponent(agent.id))).data.actor;assert.equal(profile.americanStatus,'verified');assert.equal(profile.americanVerification.operator,true);assert.equal(JSON.stringify(profile).includes('latitude'),false);
  const agentAuth=(await request(app.base,'/api/login',{handle:agent.handle,password:'location-password'})).data;
  assert.equal((await request(app.base,'/api/location/verify',valid,agentAuth.token)).status,403);
  const key=(await request(app.base,'/api/agent-keys',{actor:agent.id,name:'Location test',scopes:['profile'],days:1},owner.token)).data.token;
  assert.equal((await request(app.base,'/api/location/verify',valid,key)).status,403);
  await request(app.base,'/api/location/remove',{},owner.token);
  assert.equal((await request(app.base,'/api/profile?id='+encodeURIComponent(agent.id))).data.actor.americanStatus,'self-declared');
 }finally{await app.stop();}
});

test('human registration and login cannot bypass CAPTCHA; enrolled agents still authenticate',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'amerika-captcha-'));let app=await launch({DATA_DIR:dir});
 try{
  const owner=await request(app.base,'/api/register',{handle:'human.demo',name:'Human',kind:'human',password:'password-for-test',americanConfirmed:true,rulesAccepted:true});assert.equal(owner.status,200);
  const created=await request(app.base,'/api/agents',{handle:'agent.demo',name:'Agent',password:'password-for-test',americanConfirmed:true,rulesAccepted:true},owner.data.token);assert.equal(created.status,201);
  await app.stop();app=await launch({DATA_DIR:dir,TURNSTILE_SITE_KEY:'public-fixture-key',TURNSTILE_SECRET_KEY:'private-fixture-key',PUBLIC_ORIGIN:'https://altstack.io'});
  const config=await request(app.base,'/api/config');assert.equal(config.data.captcha.enabled,true);assert.equal(JSON.stringify(config.data).includes('private-fixture-key'),false);
  const registration=await request(app.base,'/api/register',{handle:'blocked.demo',name:'Blocked',kind:'human',password:'password-for-test',americanConfirmed:true,rulesAccepted:true});assert.equal(registration.status,400);assert.match(registration.data.error,/human verification/);
  const human=await request(app.base,'/api/login',{handle:'human.demo',password:'password-for-test',kind:'agent'});assert.equal(human.status,400);assert.match(human.data.error,/human verification/);
  const unknown=await request(app.base,'/api/login',{handle:'unknown.demo',password:'password-for-test',kind:'agent'});assert.equal(unknown.status,400);
  const agent=await request(app.base,'/api/login',{handle:'agent.demo',password:'password-for-test'});assert.equal(agent.status,200);assert.equal(agent.data.actor.kind,'agent');
  const moreAgent=await request(app.base,'/api/agents',{handle:'second-agent.demo',name:'Agent',password:'password-for-test',americanConfirmed:true,rulesAccepted:true},owner.data.token);assert.equal(moreAgent.status,201);
 }finally{await app.stop();await rm(dir,{recursive:true,force:true});}
});

test('encrypted PDS account sessions and agent delegation survive process restart',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'amerika-durable-'));const calls=[];const mock=http.createServer(async(req,res)=>{let raw='';for await(const chunk of req)raw+=chunk;const body=JSON.parse(raw||'{}');calls.push({path:req.url,body,raw,contentType:req.headers['content-type']});res.setHeader('Content-Type','application/json');if(req.url.endsWith('refreshSession')){if(raw){res.statusCode=400;res.end(JSON.stringify({error:'InvalidRequest'}));}else res.end(JSON.stringify({accessJwt:'refreshed-access-token',refreshJwt:'refreshed-refresh-token'}));}else if(req.url.endsWith('createAccount'))res.end(JSON.stringify({did:body.handle.startsWith('agent.')?'did:plc:agent':'did:plc:owner',handle:body.handle,accessJwt:'private-access-token',refreshJwt:'private-refresh-token'}));else if(req.url.endsWith('createRecord'))res.end(JSON.stringify({uri:'at://'+body.repo+'/'+body.collection+'/restart-test',cid:'restart-cid'}));else res.end('{}');});await new Promise(r=>mock.listen(0,'127.0.0.1',r));
 const env={PUBLIC_ORIGIN:'https://amerika.example',DATA_DIR:dir,PDS_URL:'http://127.0.0.1:'+mock.address().port,ALLOW_TEST_PDS:'1',SESSION_ENCRYPTION_KEY:'ab'.repeat(32)};let app=await launch(env);
 try{const owner=(await request(app.base,'/api/register',{handle:'owner.pds.example',name:'Owner',email:'owner@example.com',kind:'human',password:'owner-password',americanConfirmed:true,rulesAccepted:true})).data;assert.ok(owner.token);const agent=(await request(app.base,'/api/agents',{handle:'agent.pds.example',name:'Agent',email:'agent@example.com',password:'agent-password',americanConfirmed:true,rulesAccepted:true},owner.token)).data.actor;
 const key=(await request(app.base,'/api/agent-keys',{actor:agent.id,name:'Durable key',scopes:['post'],days:1},owner.token)).data.token;assert.ok(key);const operatorMcp=(await request(app.base,'/api/account-mcp',{name:'Durable operator',neverExpires:true},owner.token)).data;const operatorOAuth=await authorizeMcp(app.base,operatorMcp,owner.token);
 const db=new DatabaseSync(join(dir,'botsky.sqlite'));const saved=db.prepare('SELECT pds_session FROM login_sessions WHERE actor=?').get(owner.actor.id);assert.ok(saved.pds_session);assert.equal(saved.pds_session.includes('private-access-token'),false);assert.equal(db.prepare('SELECT encrypted FROM agent_sessions WHERE actor=?').get(agent.id).encrypted.includes('private-refresh-token'),false);const {createCredentialStore}=await import('../credentials.mjs');const store=createCredentialStore(db,env.SESSION_ENCRYPTION_KEY);const ownerHash=db.prepare('SELECT token_hash FROM login_sessions WHERE actor=?').get(owner.actor.id).token_hash;const ownerSession=store.login(ownerHash);ownerSession.jwtExpires=0;store.saveLogin(ownerHash,ownerSession);const mcpOwnerSession=store.agent(owner.actor.id);mcpOwnerSession.jwtExpires=0;store.saveAgent(owner.actor.id,mcpOwnerSession);const agentSession=store.agent(agent.id);agentSession.jwtExpires=0;store.saveAgent(agent.id,agentSession);db.close();
 await app.stop();app=await launch(env);assert.equal((await request(app.base,'/api/me',null,owner.token)).data.actor.id,owner.actor.id);assert.equal((await request(app.base,'/api/posts',{text:'Owner after restart'},owner.token)).status,201);assert.equal((await request(app.base,'/api/posts',{text:'Agent after restart'},key)).status,201);
 assert.equal(calls.filter(c=>c.path.endsWith('refreshSession')).length,2);assert.ok(calls.filter(c=>c.path.endsWith('refreshSession')).every(c=>c.raw===''&&!c.contentType));await request(app.base,'/api/logout',{},owner.token);assert.equal((await request(app.base,'/api/me',null,owner.token)).data.actor,null);const operatorResponse=await fetch(app.base+new URL(operatorMcp.mcpUrl).pathname,{method:'POST',headers:{Authorization:'Bearer '+operatorOAuth.access_token,'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method:'tools/call',params:{name:'like_post',arguments:{uri:'at://did:plc:owner/app.bsky.feed.post/restart-test'}}})});assert.equal((await operatorResponse.json()).result.isError,false,'Operator likes retain encrypted delegation after restart and sign-out');assert.equal(calls.filter(c=>c.path.endsWith('refreshSession')).length,3);
 }finally{await app.stop();await new Promise(r=>mock.close(r));await rm(dir,{recursive:true,force:true});}
});

test('PDS connection backs up and preserves legacy accounts while enrolling new network identities',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'amerika-connect-'));const seed=new DatabaseSync(join(dir,'botsky.sqlite'));
  seed.exec("CREATE TABLE actors(id TEXT PRIMARY KEY,handle TEXT UNIQUE NOT NULL,name TEXT NOT NULL,kind TEXT NOT NULL,bio TEXT NOT NULL DEFAULT '',password TEXT,salt TEXT); CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL); INSERT INTO settings VALUES ('mode','preview')");
  seed.prepare('INSERT INTO actors VALUES (?,?,?,?,?,?,?)').run('preview:ant','ant','Ant','human','Existing account',scryptSync('existing-password','test-salt',64).toString('hex'),'test-salt');seed.close();
  const calls=[];const mock=http.createServer(async(req,res)=>{let raw='';for await(const c of req)raw+=c;const b=JSON.parse(raw||'{}');calls.push({path:req.url,body:b,auth:req.headers.authorization});res.setHeader('Content-Type','application/json');if(req.url.endsWith('createSession')&&b.password==='wrong-password'){res.statusCode=401;res.end(JSON.stringify({error:'AuthenticationRequired',message:'Invalid identifier or password'}));}else if(req.url.endsWith('createInviteCode'))res.end(JSON.stringify({code:'single-use-invite'}));else if(req.url.endsWith('createAccount')||req.url.endsWith('createSession'))res.end(JSON.stringify({did:'did:plc:network',handle:b.handle||b.identifier,accessJwt:'network-token',refreshJwt:'network-refresh'}));else if(req.url.endsWith('createRecord'))res.end(JSON.stringify({uri:'at://did:plc:network/'+b.collection+'/post1',cid:'network-cid'}));else res.end('{}');});
  await new Promise(r=>mock.listen(0,'127.0.0.1',r));const app=await launch({DATA_DIR:dir,PDS_URL:`http://127.0.0.1:${mock.address().port}`,ALLOW_TEST_PDS:'1',ALLOW_LEGACY_ACCOUNTS:'true',PDS_HANDLE_DOMAIN:'pds.amerika.example',PDS_ADMIN_PASSWORD:'test-admin-password',VERIFIED_ACCOUNT_IDS:'preview:ant'});
  try{
    assert.ok((await readdir(dir)).some(f=>f.startsWith('before-pds-connection-')));
    const existing=await request(app.base,'/api/login',{handle:'ant',password:'existing-password',rulesAccepted:true,americanConfirmed:true});assert.equal(existing.status,200);assert.equal(existing.data.actor.id,'preview:ant');assert.equal(existing.data.actor.verified,true);assert.equal(existing.data.actor.networkIdentity,false);assert.equal(calls.length,0);
    const oldPost=await request(app.base,'/api/posts',{text:'Preserved existing account'},existing.data.token);assert.equal(oldPost.status,201);assert.ok(oldPost.data.post.uri.startsWith('preview:'));
    assert.equal((await request(app.base,'/api/register',{handle:'ant',password:'long-new-password',name:'Duplicate',kind:'human',email:'duplicate@example.com',rulesAccepted:true,americanConfirmed:true})).status,409);
    const fresh=await request(app.base,'/api/register',{handle:'newvoice',password:'long-new-password',name:'New voice',kind:'human',email:'newvoice@example.com',rulesAccepted:true,americanConfirmed:true});assert.equal(fresh.status,200);assert.equal(fresh.data.actor.networkIdentity,true);assert.equal(fresh.data.actor.handle,'newvoice.pds.amerika.example');
    const invite=calls.find(c=>c.path.endsWith('createInviteCode'));assert.equal(invite.auth,'Basic '+Buffer.from('admin:test-admin-password').toString('base64'));assert.equal(invite.body.useCount,1);assert.equal(calls.find(c=>c.path.endsWith('createAccount')).body.inviteCode,'single-use-invite');
    assert.equal((await request(app.base,'/api/profile?handle=newvoice')).data.actor.id,fresh.data.actor.id);const newPost=await request(app.base,'/api/posts',{text:'Actual AT Protocol record @newvoice'},fresh.data.token);assert.equal(newPost.status,201);assert.ok(newPost.data.post.uri.startsWith('at://'));
    const writes=calls.filter(c=>c.path.endsWith('createRecord')).length;
    assert.equal((await request(app.base,'/api/follows',{subject:'preview:ant'},fresh.data.token)).status,200);
    assert.equal((await request(app.base,'/api/likes',{uri:oldPost.data.post.uri},fresh.data.token)).status,200);
    assert.equal((await request(app.base,'/api/posts',{text:'Reply to preserved history',parent:oldPost.data.post.uri},fresh.data.token)).status,201);
    assert.equal(calls.filter(c=>c.path.endsWith('createRecord')).length,writes,'Legacy targets must not produce invalid AT Protocol records');
    await request(app.base,'/api/logout',{},existing.data.token);assert.equal((await request(app.base,'/api/me',null,existing.data.token)).data.actor,null);
    const login=await request(app.base,'/api/login',{handle:'newvoice',password:'long-new-password'});assert.equal(login.status,200);assert.equal(calls.filter(c=>c.path.endsWith('createSession')).at(-1).body.identifier,'newvoice.pds.amerika.example');
    for(const handle of ['@NEWVOICE','@newvoice.pds.amerika.example']){const normalized=await request(app.base,'/api/login',{handle,password:'long-new-password'});assert.equal(normalized.status,200);assert.equal(calls.filter(c=>c.path.endsWith('createSession')).at(-1).body.identifier,'newvoice.pds.amerika.example');}
    const wrong=await request(app.base,'/api/login',{handle:'@newvoice',password:'wrong-password'});assert.equal(wrong.status,401);assert.match(wrong.data.error,/Incorrect handle or password/);assert.match(wrong.data.error,/recovery code/);assert.doesNotMatch(wrong.data.error,/AuthenticationRequired/);
    const verify=new DatabaseSync(join(dir,'botsky.sqlite'));assert.equal(verify.prepare('PRAGMA integrity_check').get().integrity_check,'ok');verify.close();
  }finally{await app.stop();await new Promise(r=>mock.close(r));await rm(dir,{recursive:true,force:true});}
});

test('configured HTTPS public origin supports proxy deployment and rejects other origins',async()=>{
  const app=await launch({PUBLIC_ORIGIN:'https://amerika.example'});try{
    const body={handle:'proxy.demo',name:'Proxy test',kind:'human',americanConfirmed:true,rulesAccepted:true,password:'proxy-test-password'};
    assert.equal((await request(app.base,'/api/register',body,null,{Origin:'https://attacker.example','X-Forwarded-Host':'amerika.example','X-Forwarded-Proto':'https'})).status,403);
    assert.equal((await request(app.base,'/api/register',body,null,{Origin:'https://amerika.example'})).status,200);
  }finally{await app.stop();}
});

test('rules agreement is explicit, durable, private, and required for existing sessions and agent keys',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'amerika-rules-'));const app=await launch({DATA_DIR:dir});try{
    const details={handle:'rules.demo',name:'Rules test',kind:'human',americanConfirmed:true,password:'rules-test-password'};
    for(const rulesAccepted of [undefined,false,'true',1])assert.equal((await request(app.base,'/api/register',{...details,...(rulesAccepted===undefined?{}:{rulesAccepted})})).status,400);
    const a=(await request(app.base,'/api/register',{...details,rulesAccepted:true})).data;
    assert.equal(a.actor.rulesAccepted,true);const config=(await request(app.base,'/api/config')).data;assert.equal(config.rules.prohibited.length,6);
    const db=new DatabaseSync(join(dir,'botsky.sqlite'));const accepted=db.prepare('SELECT rules_version,rules_accepted_at FROM actors WHERE id=?').get(a.actor.id);assert.equal(accepted.rules_version,config.rules.version);assert.ok(accepted.rules_accepted_at);
    assert.equal((await request(app.base,'/api/profile?id='+encodeURIComponent(a.actor.id))).data.actor.rules_accepted_at,undefined);
    const agent=(await request(app.base,'/api/agents',{handle:'rules-agent.demo',name:'Rules agent',americanConfirmed:true,rulesAccepted:true,password:'rules-test-password'},a.token)).data.actor;
    const key=(await request(app.base,'/api/agent-keys',{actor:agent.id,name:'Rules key',scopes:['post']},a.token)).data;
    db.prepare('UPDATE actors SET rules_version=NULL,rules_accepted_at=NULL WHERE id=?').run(a.actor.id);
    assert.equal((await request(app.base,'/api/posts',{text:'Old session bypass'},a.token)).status,403);
    assert.equal((await request(app.base,'/api/posts',{text:'Old operator bypass'},key.token)).status,403);
    assert.equal((await request(app.base,'/api/me',null,a.token)).data.actor.rulesAccepted,false);
    for(const rulesAccepted of [undefined,false,'true'])assert.equal((await request(app.base,'/api/login',{handle:details.handle,password:details.password,...(rulesAccepted===undefined?{}:{rulesAccepted})})).status,403);
    assert.equal((await request(app.base,'/api/login',{handle:details.handle,password:details.password,rulesAccepted:true})).status,200);
    assert.equal((await request(app.base,'/api/posts',{text:'Accepted operator'},key.token)).status,201);
    db.prepare('UPDATE actors SET rules_version=NULL,rules_accepted_at=NULL WHERE id=?').run(agent.id);
    assert.equal((await request(app.base,'/api/posts',{text:'Old agent bypass'},key.token)).status,403);
    assert.equal((await request(app.base,'/api/agents/link',{handle:agent.handle,password:details.password,americanConfirmed:true},a.token)).status,400);
    assert.equal((await request(app.base,'/api/agents/link',{handle:agent.handle,password:details.password,americanConfirmed:true,rulesAccepted:true},a.token)).status,200);
    assert.equal((await request(app.base,'/api/posts',{text:'Accepted agent'},key.token)).status,201);db.close();
  }finally{await app.stop();await rm(dir,{recursive:true,force:true});}
});

test('private messages, recipient alerts, agent permissions, and followed hashtag feeds',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'amerika-messages-'));let app=await launch({DATA_DIR:dir});try{
    const register=async handle=>(await request(app.base,'/api/register',{handle,name:handle,kind:'human',americanConfirmed:true,rulesAccepted:true,password:'message-test-password'})).data;
    const a=await register('first.demo'),b=await register('second.demo'),c=await register('third.demo');
    const get=(path,token)=>request(app.base,path,null,token),post=(path,body,token)=>request(app.base,path,body,token);
    assert.equal((await get('/api/messages')).status,401);
    assert.equal((await post('/api/messages',{recipient:b.actor.id,text:'Private #America @third.demo'},a.token)).status,201);
    const thread='/api/messages?peer='+encodeURIComponent(a.actor.id);
    assert.equal((await get(thread,b.token)).data.messages.length,1);
    assert.equal((await get(thread,c.token)).data.messages.length,0);
    assert.equal((await get('/api/messages',c.token)).data.conversations.length,0);
    assert.equal((await get('/api/feed?q=Private')).data.posts.length,0);
    assert.equal((await get('/api/notifications',null)).status,401);
    const inbox=(await get('/api/messages',b.token)).data;assert.equal(inbox.unread,1);assert.equal(inbox.conversations[0].unread,1);
    assert.ok((await get('/api/notifications',b.token)).data.notifications.some(n=>n.type==='message'));
    assert.equal((await get('/api/notifications',c.token)).data.unread,0,'DM mentions never notify outsiders');
    const last=(await get(thread,b.token)).data.messages.at(-1).id;
    await post('/api/messages/read',{peer:a.actor.id,through:last},c.token);
    assert.equal((await get('/api/messages',b.token)).data.unread,1);
    await post('/api/messages/read',{peer:a.actor.id,through:last},b.token);
    assert.equal((await get('/api/messages',b.token)).data.unread,0);
    assert.equal((await get('/api/notifications',b.token)).data.unread,0);
    assert.equal((await post('/api/messages',{recipient:a.actor.id,text:'   '},b.token)).status,400);
    assert.equal((await post('/api/messages',{recipient:a.actor.id,text:'x'.repeat(2001)},b.token)).status,400);
    assert.equal((await post('/api/messages',{recipient:a.actor.id,text:'self'},a.token)).status,400);
    const agent=(await post('/api/agents',{handle:'messenger.demo',name:'Messenger',password:'message-test-password',americanConfirmed:true,rulesAccepted:true},a.token)).data.actor;
    const issue=async scopes=>(await post('/api/agent-keys',{actor:agent.id,name:'Test',scopes},a.token)).data.token;
    const restricted=await issue(['post','read']);assert.equal((await get('/api/messages',restricted)).status,403);assert.equal((await post('/api/messages',{recipient:b.actor.id,text:'Denied'},restricted)).status,403);
    const authorized=await issue(['messages']);assert.equal((await post('/api/messages',{recipient:b.actor.id,text:'An agent message'},authorized)).status,201);assert.equal((await get('/api/messages',authorized)).status,200);
    await post('/api/hashtags/follow',{tag:'America',following:true},b.token);await post('/api/hashtags/follow',{tag:'america',following:true},b.token);
    assert.deepEqual((await get('/api/hashtags',b.token)).data.tags,['america']);
    assert.equal((await post('/api/hashtags/follow',{tag:'bad tag',following:true},b.token)).status,400);
    const tagged=(await post('/api/posts',{text:'Hello 🇺🇸 @second.demo #America #AI'},a.token)).data.post;
    await post('/api/posts',{text:'#Americana is a different topic'},a.token);
    assert.deepEqual((await get('/api/feed?tag=AMERICA')).data.posts.map(p=>p.uri),[tagged.uri]);
    assert.deepEqual((await get('/api/feed?hashtags=1',b.token)).data.posts.map(p=>p.uri),[tagged.uri]);
    await post('/api/posts/edit',{uri:tagged.uri,text:'#AI only'},a.token);assert.equal((await get('/api/feed?hashtags=1',b.token)).data.posts.length,0);
    await post('/api/hashtags/follow',{tag:'AI',following:true},b.token);assert.equal((await get('/api/feed?hashtags=1',b.token)).data.posts.length,1);
    await post('/api/posts/delete',{uri:tagged.uri},a.token);assert.equal((await get('/api/feed?hashtags=1',b.token)).data.posts.length,0);
    await app.stop();app=await launch({DATA_DIR:dir});const renewed=(await request(app.base,'/api/login',{handle:'second.demo',password:'message-test-password'})).data;
    assert.equal((await request(app.base,thread,null,renewed.token)).data.messages.length,1);assert.deepEqual((await request(app.base,'/api/hashtags',null,renewed.token)).data.tags,['ai','america']);
  }finally{await app.stop();await rm(dir,{recursive:true,force:true});}
});

test('local accounts, auth boundaries, conversations, graph, filtering, and revocation',async()=>{
  const app=await launch();try{
    assert.equal((await request(app.base,'/api/config')).data.mode,'preview');
    assert.equal((await request(app.base,'/api/config')).data.name,'AltStack Social');
    for (const kind of ['human','agent']) {
      for (const confirmation of [undefined,false,'true',1]) {
        const attempted=await request(app.base,'/api/register',{handle:`reject-${kind}.demo`,name:'No confirmation',kind,password:'long-password-test',...(confirmation===undefined?{}:{americanConfirmed:confirmation})});
        assert.equal(attempted.status,400);
      }
    }
    assert.equal((await request(app.base,'/api/posts',{text:'anonymous'})).status,401);
    const bob=(await request(app.base,'/api/register',{handle:'bob.demo',name:'Bob',kind:'human',americanConfirmed:true,rulesAccepted:true,password:'long-password-b'})).data;
    const newAgent=await request(app.base,'/api/agents',{handle:'alice.demo',name:'Alice',americanConfirmed:true,rulesAccepted:true,password:'long-password-a'},bob.token);assert.equal(newAgent.status,201);
    const alice=(await request(app.base,'/api/login',{handle:'alice.demo',password:'long-password-a'})).data;
    assert.ok(alice.token);assert.ok(bob.token);
    assert.equal(alice.actor.operator.id,bob.actor.id);
    assert.equal(bob.actor.americanStatus,'self-declared');
    const profile=await request(app.base,'/api/profile',{name:'Robert',bio:'A human operator'},bob.token);
    assert.equal(profile.data.actor.name,'Robert');assert.equal(profile.data.actor.bio,'A human operator');
    assert.equal((await request(app.base,'/api/profile?id='+encodeURIComponent(bob.actor.id))).data.actor.name,'Robert');
    const photo='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==';
    assert.equal((await request(app.base,'/api/profile',{name:'Robert',bio:'Photo test',photo},bob.token)).data.actor.photo,photo);
    assert.equal((await request(app.base,'/api/profile',{name:'Robert',bio:'',photo:'data:image/svg+xml;base64,PHN2Zy8+'},bob.token)).status,400);
    assert.equal((await request(app.base,'/api/profile',{name:'Robert',bio:'',photo:null},bob.token)).data.actor.photo,null);
    assert.equal((await request(app.base,'/api/register',{handle:'alice.demo',name:'Imposter',kind:'human',americanConfirmed:true,rulesAccepted:true,password:'long-password-x'})).status,409);
    assert.equal((await request(app.base,'/api/login',{handle:'alice.demo',password:'wrong-password'})).status,401);
    assert.equal((await request(app.base,'/api/posts',{text:'wrong origin'},alice.token,{Origin:'https://evil.example'})).status,403);
    assert.equal((await request(app.base,'/api/posts',{text:'x'.repeat(301)},alice.token)).status,400);
    const text='<script>alert(1)</script> an agent thought';
    const posted=await request(app.base,'/api/posts',{text},alice.token);assert.equal(posted.status,201);const post=posted.data.post;
    assert.equal(post.text,text);assert.equal(post.author.id,alice.actor.id);assert.ok(post.uri.startsWith('preview:'));
    const reply=(await request(app.base,'/api/posts',{text:'A human reply',parent:post.uri},bob.token)).data.post;
    assert.equal(reply.root,post.uri);
    const nested=(await request(app.base,'/api/posts',{text:'Nested reply',parent:reply.uri},alice.token)).data.post;assert.equal(nested.root,post.uri);
    const thread=(await request(app.base,`/api/thread?uri=${encodeURIComponent(post.uri)}`)).data;assert.equal(thread.replies.length,1);
    assert.equal((await request(app.base,'/api/likes',{uri:post.uri},bob.token)).data.liked,true);
    const order=(await request(app.base,'/api/feed')).data.posts.map(p=>p.uri);
    assert.equal((await request(app.base,'/api/likes',{uri:post.uri},bob.token)).data.liked,false);
    assert.deepEqual((await request(app.base,'/api/feed')).data.posts.map(p=>p.uri),order,'Likes do not change feed order');
    assert.equal((await request(app.base,'/api/follows',{subject:alice.actor.id},bob.token)).data.following,true);
    const following=(await request(app.base,'/api/feed?following=1',null,bob.token)).data.posts;assert.equal(following.length,2);assert.ok(following.every(p=>p.author.id===alice.actor.id));
    const filtered=(await request(app.base,'/api/feed?kind=human&q=A%20human%20reply')).data.posts;assert.equal(filtered.length,1);
    assert.equal((await request(app.base,'/api/posts/edit',{uri:post.uri,text:'Not mine'},bob.token)).status,403);
    assert.equal((await request(app.base,'/api/posts/delete',{uri:post.uri},bob.token)).status,403);
    assert.equal((await request(app.base,'/api/posts/edit',{uri:post.uri,text:'Edited thought @bob.demo'},alice.token)).status,200);
    assert.deepEqual((await request(app.base,'/api/feed')).data.posts.map(p=>p.uri),order,'Editing does not boost posts');
    const notices=(await request(app.base,'/api/notifications',null,bob.token)).data;
    assert.ok(notices.notifications.some(n=>n.type==='mention'));assert.ok(notices.unread>0);
    await request(app.base,'/api/notifications/read',{through:notices.notifications[0].id},bob.token);
    assert.equal((await request(app.base,'/api/notifications',null,bob.token)).data.unread,0);
    assert.equal((await request(app.base,'/api/posts/delete',{uri:post.uri},alice.token)).status,200);
    assert.equal((await request(app.base,'/api/feed')).data.posts.some(p=>p.uri===post.uri),false);
    const deleted=(await request(app.base,'/api/thread?uri='+encodeURIComponent(post.uri))).data;
    assert.equal(deleted.post.deleted,1);assert.equal(deleted.replies.length,1);
    await request(app.base,'/api/logout',{},bob.token);assert.equal((await request(app.base,'/api/posts',{text:'revoked'},bob.token)).status,401);
  }finally{await app.stop();}
});

test('scoped preview credentials survive restart and expired credentials are rejected',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'amerika-key-persistence-'));let app=await launch({DATA_DIR:dir});try{
    const owner=(await request(app.base,'/api/register',{handle:'persistent.demo',name:'Owner',kind:'human',password:'persistent-password-123',americanConfirmed:true,rulesAccepted:true})).data;
    const agent=(await request(app.base,'/api/agents',{handle:'persistent-agent.demo',name:'Agent',password:'persistent-password-123',americanConfirmed:true,rulesAccepted:true},owner.token)).data.actor;
    const key=(await request(app.base,'/api/agent-keys',{actor:agent.id,name:'Persistent',scopes:['post']},owner.token)).data;
    await app.stop();app=await launch({DATA_DIR:dir});
    assert.equal((await request(app.base,'/api/posts',{text:'After restart'},key.token)).status,201);
    const db=new DatabaseSync(join(dir,'botsky.sqlite'));db.prepare('UPDATE api_keys SET expires=? WHERE id=?').run('2000-01-01T00:00:00.000Z',key.id);db.close();
    assert.equal((await request(app.base,'/api/posts',{text:'Expired'},key.token)).status,401);
  }finally{await app.stop();await rm(dir,{recursive:true,force:true});}
});

test('agent credentials enforce ownership, scopes, expiry, and immediate revocation',async()=>{
  const app=await launch();try{
    const signup=async(handle)=>{const r=await request(app.base,'/api/register',{handle,name:handle,kind:'human',americanConfirmed:true,rulesAccepted:true,password:'safe-password-123'});assert.equal(r.status,200);return r.data;};
    const owner=await signup('owner.demo'),other=await signup('other.demo');
    assert.equal((await request(app.base,'/api/register',{handle:'rogue.demo',name:'Unlinked',kind:'agent',americanConfirmed:true,rulesAccepted:true,password:'safe-password-123'})).status,400);
    const agent=(await request(app.base,'/api/agents',{handle:'agent.demo',name:'Agent',password:'safe-password-123',americanConfirmed:true,rulesAccepted:true},owner.token)).data.actor;
    assert.equal((await request(app.base,'/api/agent-keys',{actor:agent.id,name:'Stolen',scopes:['post']},other.token)).status,403);
    assert.equal((await request(app.base,'/api/agent-keys',{actor:agent.id,name:'Unknown scope',scopes:['admin']},owner.token)).status,400);
    assert.equal((await request(app.base,'/api/agent-keys',{actor:agent.id,name:'Bad expiry',scopes:['post'],days:91},owner.token)).status,400);
    const issued=(await request(app.base,'/api/agent-keys',{actor:agent.id,name:'Posts only',scopes:['post'],days:1},owner.token)).data;
    assert.ok(issued.token.startsWith('as_agent_'));
    const made=await request(app.base,'/api/posts',{text:'Scoped publication'},issued.token);assert.equal(made.status,201);assert.equal(made.data.post.author.id,agent.id);
    assert.equal((await request(app.base,'/api/likes',{uri:made.data.post.uri},issued.token)).status,403);
    assert.equal((await request(app.base,'/api/profile',{name:'Forbidden',bio:''},issued.token)).status,403);
    assert.equal((await request(app.base,'/api/agent-keys',{actor:agent.id,name:'Escalate',scopes:['profile']},issued.token)).status,403);
    assert.equal((await request(app.base,'/api/notifications',null,issued.token)).status,403);
    const dashboard=(await request(app.base,'/api/agents',null,owner.token)).data;
    assert.equal(dashboard.agents.length,1);assert.equal(JSON.stringify(dashboard).includes(issued.token),false);assert.equal(JSON.stringify(dashboard).includes('token_hash'),false);
    assert.equal((await request(app.base,'/api/agent-keys/revoke',{id:issued.id},other.token)).status,404);
    assert.equal((await request(app.base,'/api/agent-keys/revoke',{id:issued.id},owner.token)).status,200);
    assert.equal((await request(app.base,'/api/posts',{text:'After revoke'},issued.token)).status,401);
  }finally{await app.stop();}
});

test('legacy accounts retain their credentials and must attest before a new session',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'amerika-migration-'));
  const old=new DatabaseSync(join(dir,'botsky.sqlite'));
  old.exec("CREATE TABLE actors(id TEXT PRIMARY KEY,handle TEXT UNIQUE NOT NULL,name TEXT NOT NULL,kind TEXT NOT NULL,bio TEXT NOT NULL DEFAULT '',password TEXT,salt TEXT)");
  const password='legacy-password-123',salt='legacy-test-salt';
  old.prepare('INSERT INTO actors VALUES (?,?,?,?,?,?,?)').run('preview:legacy','legacy.demo','Legacy','human','Existing account',scryptSync(password,salt,64).toString('hex'),salt);
  old.close();
  const app=await launch({DATA_DIR:dir});try{
    assert.equal((await request(app.base,'/api/login',{handle:'legacy.demo',password})).status,403);
    const login=await request(app.base,'/api/login',{handle:'legacy.demo',password,americanConfirmed:true,rulesAccepted:true});
    assert.equal(login.status,200);assert.equal(login.data.actor.id,'preview:legacy');
    const check=new DatabaseSync(join(dir,'botsky.sqlite'));
    assert.ok(check.prepare('SELECT american_confirmed_at FROM actors WHERE id=?').get('preview:legacy').american_confirmed_at);check.close();
    assert.equal((await request(app.base,'/api/login',{handle:'legacy.demo',password})).status,200);
  }finally{await app.stop();await rm(dir,{recursive:true,force:true});}
});

test('network adapter writes standard records to configured PDS and excludes preview identities',async()=>{
  const calls=[];
  const mock=http.createServer(async(req,res)=>{let raw='';for await(const c of req)raw+=c;const b=JSON.parse(raw||'{}');calls.push({path:req.url,body:b,auth:req.headers.authorization});res.setHeader('Content-Type','application/json');if(req.url.endsWith('createAccount'))res.end(JSON.stringify({did:'did:plc:testactor',handle:b.handle,accessJwt:'access-secret',refreshJwt:'refresh-secret'}));else if(req.url.endsWith('createRecord'))res.end(JSON.stringify({uri:`at://${b.repo}/${b.collection}/record1`,cid:'mock-cid'}));else if(req.url.startsWith('/xrpc/com.atproto.repo.getRecord'))res.end(JSON.stringify({value:{$type:'app.bsky.actor.profile',pinnedPost:{uri:'at://existing/post/one',cid:'existing-cid'}}}));else if(req.url.endsWith('putRecord'))res.end(JSON.stringify({uri:'at://did:plc:testactor/app.bsky.feed.post/record1',cid:'mock-edited-cid'}));else res.end('{}');});
  await new Promise(r=>mock.listen(0,'127.0.0.1',r));
  const app=await launch({PDS_URL:`http://127.0.0.1:${mock.address().port}`,ALLOW_TEST_PDS:'1'});try{
    assert.equal((await request(app.base,'/api/config')).data.mode,'atproto');assert.equal((await request(app.base,'/api/feed')).data.posts.length,0);
    assert.equal((await request(app.base,'/api/register',{handle:'unconfirmed.own-pds.example',name:'Agent',kind:'agent',email:'agent@example.com',password:'long-password-pds'})).status,400);
    assert.equal(calls.length,0,'Unconfirmed signups must not create upstream accounts');
    const registered=(await request(app.base,'/api/register',{handle:'agent.own-pds.example',name:'Agent',kind:'human',americanConfirmed:true,rulesAccepted:true,email:'agent@example.com',password:'long-password-pds'})).data;
    assert.ok(registered.token);assert.notEqual(registered.token,'access-secret');assert.equal(JSON.stringify(registered).includes('refresh-secret'),false);
    const richText='🇺🇸 Independent @agent.own-pds.example #America #AI';
    const result=await request(app.base,'/api/posts',{text:richText},registered.token);assert.equal(result.status,201);assert.ok(result.data.post.uri.startsWith('at://did:plc:testactor/'));
    const write=calls.find(c=>c.path.endsWith('createRecord'));assert.equal(write.auth,'Bearer access-secret');assert.equal(write.body.record.$type,'app.bsky.feed.post');assert.equal(write.body.repo,'did:plc:testactor');
    assert.equal(write.body.record.facets.length,3);for(const facet of write.body.record.facets){const slice=Buffer.from(richText).subarray(facet.index.byteStart,facet.index.byteEnd).toString();assert.ok(slice.startsWith('@')||slice.startsWith('#'));if(facet.features[0].tag)assert.equal(slice,'#'+facet.features[0].tag);else assert.equal(facet.features[0].did,'did:plc:testactor');}
    await request(app.base,'/api/likes',{uri:result.data.post.uri},registered.token);await request(app.base,'/api/likes',{uri:result.data.post.uri},registered.token);
    assert.ok(calls.some(c=>c.path.endsWith('deleteRecord')&&c.body.collection==='app.bsky.feed.like'));
    const profile=await request(app.base,'/api/profile',{name:'Updated name',bio:'Updated bio'},registered.token);assert.equal(profile.status,200);
    const profileWrite=calls.filter(c=>c.path.endsWith('putRecord')&&c.body.collection==='app.bsky.actor.profile').at(-1);assert.equal(profileWrite.body.record.displayName,'Updated name');assert.equal(profileWrite.body.record.pinnedPost.cid,'existing-cid');
    const edited=await request(app.base,'/api/posts/edit',{uri:result.data.post.uri,text:'Edited AT post'},registered.token);assert.equal(edited.status,200);assert.equal(edited.data.post.cid,'mock-edited-cid');
    const editWrite=calls.filter(c=>c.path.endsWith('putRecord')&&c.body.collection==='app.bsky.feed.post').at(-1);assert.equal(editWrite.body.swapRecord,'mock-cid');assert.equal(editWrite.body.record.createdAt,result.data.post.created);
    assert.equal((await request(app.base,'/api/posts/delete',{uri:result.data.post.uri},registered.token)).status,200);assert.equal((await request(app.base,'/api/feed')).data.posts.length,0);
  }finally{await app.stop();await new Promise(r=>mock.close(r));}
});


test('permanent Plus grants use immutable IDs, survive restart and canceled billing, and prevent checkout',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'amerika-permanent-'));let app=await launch({DATA_DIR:dir,PERMANENT_PLUS_ACCOUNT_IDS:''});
 try{
  const register=async handle=>(await request(app.base,'/api/register',{handle,name:handle,kind:'human',password:'permanent-test-password',americanConfirmed:true,rulesAccepted:true})).data;
  const member=await register('permanent.demo'),ordinary=await register('ordinary.demo');
  await app.stop();app=await launch({DATA_DIR:dir,PERMANENT_PLUS_ACCOUNT_IDS:' '+member.actor.id+' , '+ordinary.actor.handle});
  const login=async handle=>(await request(app.base,'/api/login',{handle,password:'permanent-test-password'})).data;
  let session=await login(member.actor.handle);const free=await login(ordinary.actor.handle);
  let plan=(await request(app.base,'/api/billing',null,session.token)).data;
  assert.equal(plan.plus,true);assert.equal(plan.permanentPlus,true);assert.equal(plan.subscription,null);assert.equal(plan.originalPostsRemaining,null);
  assert.equal((await request(app.base,'/api/billing',null,free.token)).data.plus,false,'Handles cannot confer permanent membership');
  assert.equal((await request(app.base,'/api/billing/checkout',{},session.token)).status,409,'No Stripe checkout for permanent members, even without billing configuration');
  for(let i=0;i<4;i++)assert.equal((await request(app.base,'/api/posts',{text:'x'.repeat(833)},session.token)).status,201);
  assert.equal((await request(app.base,'/api/posts',{text:'x'.repeat(834)},session.token)).status,400);
  const video=await readFile(new URL('./fixtures/red.mp4',import.meta.url));const upload=await fetch(app.base+'/api/media/upload',{method:'POST',headers:{'Content-Type':'video/mp4',Authorization:'Bearer '+session.token},body:video});assert.equal(upload.status,201);
  const db=new DatabaseSync(join(dir,'botsky.sqlite'));db.prepare('INSERT INTO billing_subscriptions VALUES (?,?,?,?,?,?,?)').run('sub_canceled',member.actor.id,'cus_canceled','canceled',0,0,new Date().toISOString());db.close();
  await app.stop();app=await launch({DATA_DIR:dir,PERMANENT_PLUS_ACCOUNT_IDS:member.actor.id});session=await login(member.actor.handle);
  plan=(await request(app.base,'/api/billing',null,session.token)).data;assert.equal(plan.plus,true);assert.equal(plan.permanentPlus,true);assert.equal(plan.subscription.status,'canceled');assert.equal(session.actor.plus,true);assert.equal(session.actor.verified,true);
 }finally{await app.stop();await rm(dir,{recursive:true,force:true});}
});


test('linked bots inherit operator Plus, enforce expiry and unlinking, and keep independent access',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'amerika-inheritance-'));let app=await launch({DATA_DIR:dir,PERMANENT_PLUS_ACCOUNT_IDS:''});
 try{
  const owner=(await request(app.base,'/api/register',{handle:'inherit-owner.demo',name:'Owner',kind:'human',password:'inherit-test-password',americanConfirmed:true,rulesAccepted:true})).data;
  const agent=(await request(app.base,'/api/agents',{handle:'inherit-bot.demo',name:'Bot',password:'inherit-test-password',americanConfirmed:true,rulesAccepted:true},owner.token)).data.actor;
  const key=(await request(app.base,'/api/agent-keys',{actor:agent.id,name:'Posting',scopes:['post'],days:1},owner.token)).data.token;
  const db=new DatabaseSync(join(dir,'botsky.sqlite'));
  const plan=async()=> (await request(app.base,'/api/billing?actor='+encodeURIComponent(agent.id),null,owner.token)).data;
  assert.equal((await plan()).plus,false);
  db.prepare('INSERT INTO billing_subscriptions VALUES (?,?,?,?,?,?,?)').run('sub_owner',owner.actor.id,'cus_owner','active',Math.floor(Date.now()/1000)+3600,0,new Date().toISOString());
  assert.equal((await plan()).inheritedPlus,true);assert.equal((await plan()).permanentPlus,false);
  assert.equal((await request(app.base,'/api/billing/checkout',{actor:agent.id},owner.token)).status,409);
  for(let i=0;i<4;i++)assert.equal((await request(app.base,'/api/posts',{text:'x'.repeat(833)},key)).status,201);
  const video=await readFile(new URL('./fixtures/red.mp4',import.meta.url));const upload=await fetch(app.base+'/api/media/upload',{method:'POST',headers:{'Content-Type':'video/mp4',Authorization:'Bearer '+key},body:video});assert.equal(upload.status,201);
  db.prepare('UPDATE billing_subscriptions SET paid_until=0 WHERE id=?').run('sub_owner');assert.equal((await plan()).plus,false);assert.equal((await request(app.base,'/api/posts',{text:'x'.repeat(833)},key)).status,400);
  db.close();await app.stop();app=await launch({DATA_DIR:dir,PERMANENT_PLUS_ACCOUNT_IDS:owner.actor.id});
  const ownerLogin=(await request(app.base,'/api/login',{handle:owner.actor.handle,password:'inherit-test-password'})).data;
  const permanentPlan=(await request(app.base,'/api/billing?actor='+encodeURIComponent(agent.id),null,ownerLogin.token)).data;assert.equal(permanentPlan.plus,true);assert.equal(permanentPlan.permanentPlus,true);assert.equal(permanentPlan.inheritedPlus,true);
  const edit=new DatabaseSync(join(dir,'botsky.sqlite'));edit.prepare('UPDATE actors SET operator_id=NULL WHERE id=?').run(agent.id);assert.equal((await request(app.base,'/api/me',null,key)).data.actor,null,'Old operator credentials lose access after unlinking');const independentLogin=(await request(app.base,'/api/login',{handle:agent.handle,password:'inherit-test-password'})).data;assert.equal((await request(app.base,'/api/me',null,independentLogin.token)).data.actor.plus,false);
  edit.prepare('INSERT INTO billing_subscriptions VALUES (?,?,?,?,?,?,?)').run('sub_bot',agent.id,'cus_bot','active',Math.floor(Date.now()/1000)+3600,0,new Date().toISOString());assert.equal((await request(app.base,'/api/me',null,independentLogin.token)).data.actor.plus,true);edit.close();
 }finally{await app.stop();await rm(dir,{recursive:true,force:true});}
});


test('account webhooks enforce ownership, sign notifications, retry durably, protect DM text and disable delivery',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'amerika-webhooks-'));const received=[];let failFirst=true;
 const receiver=http.createServer(async(req,res)=>{let raw='';for await(const c of req)raw+=c;received.push({raw,headers:req.headers,body:JSON.parse(raw)});res.statusCode=failFirst?500:204;failFirst=false;res.end();});await new Promise(r=>receiver.listen(0,'127.0.0.1',r));
 const env={DATA_DIR:dir,SESSION_ENCRYPTION_KEY:'bc'.repeat(32),ALLOW_TEST_WEBHOOKS:'1'};let app=await launch(env);const url='http://127.0.0.1:'+receiver.address().port+'/events';
 const wait=async(fn)=>{for(let i=0;i<100;i++){if(fn())return;await new Promise(r=>setTimeout(r,100));}throw Error('Webhook delivery timed out');};
 try{
  const register=async handle=>(await request(app.base,'/api/register',{handle,name:handle,kind:'human',password:'webhook-test-password',americanConfirmed:true,rulesAccepted:true})).data;
  const owner=await register('hooks.demo'),other=await register('sender.demo');const bot=(await request(app.base,'/api/agents',{handle:'hookbot.demo',name:'Bot',password:'webhook-test-password',americanConfirmed:true,rulesAccepted:true},owner.token)).data.actor;
  const key=(await request(app.base,'/api/agent-keys',{actor:bot.id,name:'Bot',scopes:['post','messages'],days:1},owner.token)).data.token;
  assert.equal((await request(app.base,'/api/webhooks',{actor:bot.id,url,events:['reply']},other.token)).status,403);assert.equal((await request(app.base,'/api/webhooks',null,key)).status,403);
  const created=(await request(app.base,'/api/webhooks',{actor:bot.id,url,events:['reply','message']},owner.token));assert.equal(created.status,201);const hook=created.data;
  const listed=(await request(app.base,'/api/webhooks',null,owner.token)).data;assert.equal(JSON.stringify(listed).includes(hook.secret),false);assert.equal((await request(app.base,'/api/webhooks/test',{id:hook.id},other.token)).status,404);
  const root=(await request(app.base,'/api/posts',{text:'Bot root'},key)).data.post;await request(app.base,'/api/posts',{text:'Reply for the bot',parent:root.uri},other.token);await wait(()=>received.length===1);
  assert.equal(received[0].body.type,'notification.reply');assert.equal(received[0].body.account.id,bot.id);assert.equal(received[0].body.data.post.text,'Reply for the bot');
  const {createHmac}=await import('node:crypto');assert.equal(received[0].headers['amerika-webhook-signature'],'v1='+createHmac('sha256',hook.secret).update(received[0].headers['amerika-webhook-timestamp']+'.'+received[0].raw).digest('hex'));
  await new Promise(r=>setTimeout(r,100));await app.stop();const db=new DatabaseSync(join(dir,'botsky.sqlite'));assert.equal(db.prepare('SELECT status FROM webhook_deliveries').get().status,'pending');assert.equal(db.prepare('SELECT secret FROM webhooks').get().secret.includes(hook.secret),false);db.prepare('UPDATE webhook_deliveries SET next_at=0').run();db.close();app=await launch(env);
  await wait(()=>received.length===2);assert.equal(received[1].raw,received[0].raw);assert.equal(received[1].headers['amerika-webhook-id'],received[0].headers['amerika-webhook-id']);
  await request(app.base,'/api/messages',{recipient:bot.id,text:'Private text excluded'},other.token);await wait(()=>received.length===3);assert.equal(received[2].body.type,'notification.message');assert.equal(received[2].body.data.message.text,undefined);assert.equal(received[2].raw.includes('Private text excluded'),false);
  const humanHook=(await request(app.base,'/api/webhooks',{actor:owner.actor.id,url,events:['message'],includeMessages:true},owner.token)).data;await request(app.base,'/api/messages',{recipient:owner.actor.id,text:'Explicitly included'},other.token);await wait(()=>received.length===4);assert.equal(received[3].body.data.message.text,'Explicitly included');
  assert.equal((await request(app.base,'/api/webhooks/test',{id:humanHook.id},owner.token)).status,202);await wait(()=>received.length===5);assert.equal(received[4].body.type,'webhook.test');
  await request(app.base,'/api/webhooks/disable',{id:hook.id},owner.token);await request(app.base,'/api/messages',{recipient:bot.id,text:'No callback after disable'},other.token);await new Promise(r=>setTimeout(r,1200));assert.equal(received.length,5);
  const deliveries=(await request(app.base,'/api/webhooks',null,owner.token)).data.webhooks;assert.equal(deliveries.find(w=>w.id===hook.id).enabled,false);
  await request(app.base,'/api/webhooks',{actor:bot.id,url,events:['message'],includeMessages:true},owner.token);const unlink=new DatabaseSync(join(dir,'botsky.sqlite'));unlink.prepare('UPDATE actors SET operator_id=NULL WHERE id=?').run(bot.id);unlink.close();await request(app.base,'/api/messages',{recipient:bot.id,text:'Must not reach the old operator'},other.token);await new Promise(r=>setTimeout(r,1200));assert.equal(received.length,5);
 }finally{await app.stop();await new Promise(r=>receiver.close(r));await rm(dir,{recursive:true,force:true});}
});
