import {authorizeMcp} from './oauth-helper.mjs';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {DatabaseSync} from 'node:sqlite';

test('friends, complete threads, notification context and scoped bot/operator MCP',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'amerika-square-'));
 const child=spawn(process.execPath,['server.mjs'],{env:{...process.env,PORT:'0',HOST:'127.0.0.1',PDS_URL:'',DATA_DIR:dir},stdio:['ignore','pipe','pipe']});
 const base=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Startup timed out')),10000);child.stdout.on('data',data=>{const match=String(data).match(/"port":(\d+)/);if(match){clearTimeout(timer);resolve('http://127.0.0.1:'+match[1]);}});child.once('exit',()=>{clearTimeout(timer);reject(Error('Server exited'));});});
 const api=async(path,body,token)=>{const r=await fetch(base+'/api/'+path,{method:body?'POST':'GET',headers:{...(body?{'Content-Type':'application/json'}:{}),...(token?{Authorization:'Bearer '+token}:{})},...(body?{body:JSON.stringify(body)}:{})});return {status:r.status,data:await r.json()};};
 let ownerSession;const oauthTokens=new Map();
 const rpc=async(key,method,params={},extra={})=>{if(!oauthTokens.has(key.id))oauthTokens.set(key.id,(await authorizeMcp(base,key,ownerSession)).access_token);const r=await fetch(base+new URL(key.mcpUrl).pathname,{method:'POST',headers:{Authorization:'Bearer '+oauthTokens.get(key.id),'Content-Type':'application/json',Accept:'application/json, text/event-stream',...extra},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params})});return {status:r.status,data:await r.json()};};
 const call=async(key,name,args={})=>(await rpc(key,'tools/call',{name,arguments:args})).data;
 try{
  const register=async handle=>(await api('register',{handle,name:handle,kind:'human',password:'square-test-password',americanConfirmed:true,rulesAccepted:true})).data;
  const owner=await register('ant.demo');ownerSession=owner.token;const official=(await api('agents',{handle:'amerika.demo',name:'Amerika',password:'square-test-password',americanConfirmed:true,rulesAccepted:true},owner.token)).data.actor;const other=await register('other.demo');const onboarding=(await api('welcome',null,other.token)).data;assert.equal(onboarding.official.id,official.id);assert.equal(onboarding.pendingOfficial,false);assert.equal(onboarding.invites[0].id,owner.actor.id);const addedAtSignup=(await api('profile/friends?id='+other.actor.id+'&list=added',null,other.token)).data.actors;assert.ok(addedAtSignup.some(a=>a.id===official.id));assert.ok(!addedAtSignup.some(a=>a.id===owner.actor.id));
  const root=(await api('posts',{text:'The original'},owner.token)).data.post;
  const reply=(await api('posts',{text:'First reply',parent:root.uri},other.token)).data.post;
  const nested=(await api('posts',{text:'Nested reply',parent:reply.uri},owner.token)).data.post;
  const shared=(await api('share?uri='+encodeURIComponent(root.uri))).data;assert.ok(shared.url.includes('/post/'));const sharePath=new URL(shared.url).pathname;const sharePage=await fetch(base+sharePath);const shareHtml=await sharePage.text();assert.equal(sharePage.status,200);assert.match(shareHtml,/property="og:image"/);assert.match(shareHtml,/application\/json\+oembed/);const imageResponse=await fetch(base+'/share-image?uri='+encodeURIComponent(root.uri));assert.equal(imageResponse.status,200);const sharp=(await import('sharp')).default;const imageInfo=await sharp(Buffer.from(await imageResponse.arrayBuffer())).metadata();assert.equal(imageInfo.width,1080);assert.ok(imageInfo.height>=650);const previewResponse=await fetch(base+'/share-image?format=preview&uri='+encodeURIComponent(root.uri));const previewInfo=await sharp(Buffer.from(await previewResponse.arrayBuffer())).metadata();assert.equal(previewInfo.width,1200);assert.equal(previewInfo.height,630);const embedResponse=await fetch(base+'/embed?uri='+encodeURIComponent(root.uri));assert.match(embedResponse.headers.get('content-security-policy'),/frame-ancestors \*/);assert.match(await embedResponse.text(),/The original/);const oembed=(await api('oembed?url='+encodeURIComponent(shared.url))).data;assert.equal(oembed.type,'rich');assert.match(oembed.html,/<iframe/);
  const thread=(await api('thread?uri='+encodeURIComponent(reply.uri))).data;
  assert.equal(thread.root.uri,root.uri);assert.equal(thread.conversation.length,2);assert.equal(thread.totalReplies,2);assert.equal(thread.conversation[1].uri,nested.uri);
  const alert=(await api('notifications',null,owner.token)).data.notifications.find(n=>n.type==='reply');assert.equal(alert.postDetails.uri,reply.uri);assert.equal(alert.postDetails.text,'First reply');
  await api('notifications/read',{id:alert.id},owner.token);assert.equal((await api('notifications',null,owner.token)).data.notifications.find(n=>n.id===alert.id).seen,1);
  assert.equal((await api('follows',{subject:other.actor.id},owner.token)).data.friendship,'one-way');
  assert.equal((await api('follows',{subject:owner.actor.id},other.token)).data.friendship,'mutual');
  await api('welcome/accept',{subject:owner.actor.id},other.token);assert.equal((await api('welcome',null,other.token)).data.invites.length,0);const friends=(await api('friends',null,owner.token)).data.friends;assert.equal(friends[0].friendship,'mutual');assert.equal((await api('profile?id='+owner.actor.id,null,owner.token)).data.actor.mutualCount,1);
  const publicList=await api('profile/friends?id='+owner.actor.id+'&list=mutual');assert.equal(publicList.status,200);assert.equal(publicList.data.actors[0].id,other.actor.id);
  assert.equal((await api('profile/privacy',{friendsPrivate:true},owner.token)).status,200);assert.equal((await api('profile/friends?id='+owner.actor.id)).status,403);assert.equal((await api('profile/friends?id='+owner.actor.id,null,other.token)).status,403);assert.equal((await api('profile/friends?id='+owner.actor.id,null,owner.token)).status,200);
  const bot=(await api('agents' ,{handle:'square-bot.demo',name:'Bot',password:'square-test-password',americanConfirmed:true,rulesAccepted:true},owner.token)).data.actor;
  await api('profile/privacy',{actor:bot.id,friendsPrivate:true},owner.token);assert.equal((await api('profile/friends?id='+bot.id)).status,403);assert.equal((await api('profile/friends?id='+bot.id,null,owner.token)).status,200);assert.equal((await api('profile/friends?id='+bot.id,null,other.token)).status,403);assert.equal((await api('profile/privacy',{actor:bot.id,friendsPrivate:false},other.token)).status,403);await api('agents/personality',{actor:bot.id,personality:'You are a cheerful gardener.'},owner.token);
  assert.equal((await api('agents/personality',{actor:bot.id,personality:'Stolen'},other.token)).status,403);
  assert.equal((await api('profile?id='+bot.id)).data.actor.personality,undefined);
  const botKey=(await api('agent-keys',{actor:bot.id,name:'MCP bot',scopes:['read','post'],neverExpires:true},owner.token)).data;assert.equal(botKey.expires,null);
  assert.equal((await api('profile/friends?id='+bot.id,null,botKey.token)).status,200);const init=(await rpc(botKey,'initialize',{protocolVersion:'2025-11-25'})).data.result;assert.match(init.instructions,/cheerful gardener/);
  const tools=(await rpc(botKey,'tools/list')).data.result.tools;assert.ok(tools.some(t=>t.name==='publish_post'));assert.ok(!tools.some(t=>t.name==='send_message'));
  assert.equal((await call(botKey,'publish_post',{text:'Hello',parent:reply.uri})).result.isError,false);
  assert.equal((await call(botKey,'send_message',{recipient:owner.actor.id,text:'No'})).error.code,-32602);
  assert.equal((await rpc(botKey,'tools/list',{}, {Origin:'https://evil.example'})).status,403);
  const op=(await api('account-mcp',{name:'Operator',neverExpires:true},owner.token)).data;assert.equal(op.expires,null);
  assert.equal((await api('posts',{text:'Human impersonation'},op.token)).status,401);
  assert.equal((await call(op,'publish_post',{text:'Human impersonation'})).error.code,-32602);
  assert.equal((await call(op,'publish_post',{botId:owner.actor.id,text:'Human impersonation'})).result.isError,true);
  assert.equal((await call(op,'read_friends',{list:'mutual'})).result.isError,false);assert.equal((await call(op,'read_friends',{botId:bot.id,list:'friends'})).result.isError,false);const bots=JSON.parse((await call(op,'list_bots')).result.content[0].text).bots;assert.equal(bots.find(a=>a.id===bot.id).personality,'You are a cheerful gardener.');
  assert.equal((await call(op,'publish_post',{botId:bot.id,text:'An operator-directed bot reply',parent:reply.uri})).result.isError,false);
  assert.equal((await call(op,'like_post',{uri:root.uri})).result.isError,false);assert.equal((await call(op,'repost',{uri:reply.uri})).result.isError,false);
  const myPosts=JSON.parse((await call(op,'read_posts')).result.content[0].text).posts;assert.ok(myPosts.some(p=>p.uri===root.uri));
  const db=new DatabaseSync(join(dir,'botsky.sqlite'));
  db.prepare('UPDATE api_keys SET expires=? WHERE id=?').run('2000-01-01T00:00:00Z',botKey.id);assert.equal((await rpc(botKey,'tools/list')).status,401);
  db.prepare('UPDATE actors SET operator_id=? WHERE id=?').run(other.actor.id,bot.id);assert.equal((await call(op,'publish_post',{botId:bot.id,text:'No longer owned'})).result.isError,true);db.close();
  await api('posts/delete',{uri:root.uri},owner.token);assert.equal((await fetch(base+sharePath)).status,410);assert.equal((await fetch(base+'/share-image?uri='+encodeURIComponent(root.uri))).status,410,'Deleted posts cannot be retrieved from the image cache');await api('account-mcp/revoke',{id:op.id},owner.token);assert.equal((await rpc(op,'tools/list')).status,401);
 }finally{await new Promise(resolve=>{child.once('exit',resolve);child.kill();});await rm(dir,{recursive:true,force:true});}
});

