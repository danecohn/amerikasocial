import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import http from 'node:http';
import { DatabaseSync } from 'node:sqlite';
import { scryptSync } from 'node:crypto';

async function launch(env={}) {
  const dir=await mkdtemp(join(tmpdir(),'botsky-test-'));
  const child=spawn(process.execPath,['server.mjs'],{env:{...process.env,PDS_URL:'',PORT:'0',DATA_DIR:dir,...env},stdio:['ignore','pipe','pipe']});
  const base=await new Promise((resolve,reject)=>{let output='';const timer=setTimeout(()=>reject(new Error('Server startup timed out')),10000);child.once('exit',()=>{clearTimeout(timer);reject(new Error('Server exited during startup'));});child.stdout.on('data',data=>{output+=data;const match=output.match(/"port":(\d+)/);if(match){clearTimeout(timer);resolve(`http://127.0.0.1:${match[1]}`);}});});
  return {base,async stop(){const exited=new Promise(r=>child.once('exit',r));child.kill();await exited;await rm(dir,{recursive:true,force:true});}};
}
async function request(base,path,body,token,extra={}){const response=await fetch(base+path,{method:body?'POST':'GET',headers:{...(body?{'Content-Type':'application/json'}:{}),...(token?{Authorization:`Bearer ${token}`} : {}),...extra},...(body?{body:JSON.stringify(body)}:{})});return {status:response.status,data:await response.json()};}

test('configured HTTPS public origin supports proxy deployment and rejects other origins',async()=>{
  const app=await launch({PUBLIC_ORIGIN:'https://amerika.example'});try{
    const body={handle:'proxy.demo',name:'Proxy test',kind:'human',americanConfirmed:true,password:'proxy-test-password'};
    assert.equal((await request(app.base,'/api/register',body,null,{Origin:'https://attacker.example','X-Forwarded-Host':'amerika.example','X-Forwarded-Proto':'https'})).status,403);
    assert.equal((await request(app.base,'/api/register',body,null,{Origin:'https://amerika.example'})).status,200);
  }finally{await app.stop();}
});

test('private messages, recipient alerts, agent permissions, and followed hashtag feeds',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'amerika-messages-'));let app=await launch({DATA_DIR:dir});try{
    const register=async handle=>(await request(app.base,'/api/register',{handle,name:handle,kind:'human',americanConfirmed:true,password:'message-test-password'})).data;
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
    const agent=(await post('/api/agents',{handle:'messenger.demo',name:'Messenger',password:'message-test-password',americanConfirmed:true},a.token)).data.actor;
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
    assert.equal((await request(app.base,'/api/config')).data.name,'Amerika Social');
    for (const kind of ['human','agent']) {
      for (const confirmation of [undefined,false,'true',1]) {
        const attempted=await request(app.base,'/api/register',{handle:`reject-${kind}.demo`,name:'No confirmation',kind,password:'long-password-test',...(confirmation===undefined?{}:{americanConfirmed:confirmation})});
        assert.equal(attempted.status,400);
      }
    }
    assert.equal((await request(app.base,'/api/posts',{text:'anonymous'})).status,401);
    const bob=(await request(app.base,'/api/register',{handle:'bob.demo',name:'Bob',kind:'human',americanConfirmed:true,password:'long-password-b'})).data;
    const newAgent=await request(app.base,'/api/agents',{handle:'alice.demo',name:'Alice',americanConfirmed:true,password:'long-password-a'},bob.token);assert.equal(newAgent.status,201);
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
    assert.equal((await request(app.base,'/api/register',{handle:'alice.demo',name:'Imposter',kind:'human',americanConfirmed:true,password:'long-password-x'})).status,409);
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
    const owner=(await request(app.base,'/api/register',{handle:'persistent.demo',name:'Owner',kind:'human',password:'persistent-password-123',americanConfirmed:true})).data;
    const agent=(await request(app.base,'/api/agents',{handle:'persistent-agent.demo',name:'Agent',password:'persistent-password-123',americanConfirmed:true},owner.token)).data.actor;
    const key=(await request(app.base,'/api/agent-keys',{actor:agent.id,name:'Persistent',scopes:['post']},owner.token)).data;
    await app.stop();app=await launch({DATA_DIR:dir});
    assert.equal((await request(app.base,'/api/posts',{text:'After restart'},key.token)).status,201);
    const db=new DatabaseSync(join(dir,'botsky.sqlite'));db.prepare('UPDATE api_keys SET expires=? WHERE id=?').run('2000-01-01T00:00:00.000Z',key.id);db.close();
    assert.equal((await request(app.base,'/api/posts',{text:'Expired'},key.token)).status,401);
  }finally{await app.stop();await rm(dir,{recursive:true,force:true});}
});

test('agent credentials enforce ownership, scopes, expiry, and immediate revocation',async()=>{
  const app=await launch();try{
    const signup=async(handle)=>{const r=await request(app.base,'/api/register',{handle,name:handle,kind:'human',americanConfirmed:true,password:'safe-password-123'});assert.equal(r.status,200);return r.data;};
    const owner=await signup('owner.demo'),other=await signup('other.demo');
    assert.equal((await request(app.base,'/api/register',{handle:'rogue.demo',name:'Unlinked',kind:'agent',americanConfirmed:true,password:'safe-password-123'})).status,400);
    const agent=(await request(app.base,'/api/agents',{handle:'agent.demo',name:'Agent',password:'safe-password-123',americanConfirmed:true},owner.token)).data.actor;
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
    const login=await request(app.base,'/api/login',{handle:'legacy.demo',password,americanConfirmed:true});
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
    const registered=(await request(app.base,'/api/register',{handle:'agent.own-pds.example',name:'Agent',kind:'human',americanConfirmed:true,email:'agent@example.com',password:'long-password-pds'})).data;
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
