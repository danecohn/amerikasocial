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
 const rpc=async(key,method,params={},extra={})=>{const r=await fetch(base+new URL(key.mcpUrl).pathname,{method:'POST',headers:{Authorization:'Bearer '+key.token,'Content-Type':'application/json',Accept:'application/json, text/event-stream',...extra},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params})});return {status:r.status,data:await r.json()};};
 const call=async(key,name,args={})=>(await rpc(key,'tools/call',{name,arguments:args})).data;
 try{
  const register=async handle=>(await api('register',{handle,name:handle,kind:'human',password:'square-test-password',americanConfirmed:true,rulesAccepted:true})).data;
  const owner=await register('owner.demo'),other=await register('other.demo');
  const root=(await api('posts',{text:'The original'},owner.token)).data.post;
  const reply=(await api('posts',{text:'First reply',parent:root.uri},other.token)).data.post;
  const nested=(await api('posts',{text:'Nested reply',parent:reply.uri},owner.token)).data.post;
  const thread=(await api('thread?uri='+encodeURIComponent(reply.uri))).data;
  assert.equal(thread.root.uri,root.uri);assert.equal(thread.conversation.length,2);assert.equal(thread.totalReplies,2);assert.equal(thread.conversation[1].uri,nested.uri);
  const alert=(await api('notifications',null,owner.token)).data.notifications.find(n=>n.type==='reply');assert.equal(alert.postDetails.uri,reply.uri);assert.equal(alert.postDetails.text,'First reply');
  await api('notifications/read',{id:alert.id},owner.token);assert.equal((await api('notifications',null,owner.token)).data.notifications.find(n=>n.id===alert.id).seen,1);
  assert.equal((await api('follows',{subject:other.actor.id},owner.token)).data.friendship,'one-way');
  assert.equal((await api('follows',{subject:owner.actor.id},other.token)).data.friendship,'mutual');
  const friends=(await api('friends',null,owner.token)).data.friends;assert.equal(friends[0].friendship,'mutual');assert.equal((await api('profile?id='+owner.actor.id,null,owner.token)).data.actor.mutualCount,1);
  const bot=(await api('agents',{handle:'square-bot.demo',name:'Bot',password:'square-test-password',americanConfirmed:true,rulesAccepted:true},owner.token)).data.actor;
  await api('agents/personality',{actor:bot.id,personality:'You are a cheerful gardener.'},owner.token);
  assert.equal((await api('agents/personality',{actor:bot.id,personality:'Stolen'},other.token)).status,403);
  assert.equal((await api('profile?id='+bot.id)).data.actor.personality,undefined);
  const botKey=(await api('agent-keys',{actor:bot.id,name:'MCP bot',scopes:['read','post'],neverExpires:true},owner.token)).data;assert.equal(botKey.expires,null);
  const init=(await rpc(botKey,'initialize',{protocolVersion:'2025-11-25'})).data.result;assert.match(init.instructions,/cheerful gardener/);
  const tools=(await rpc(botKey,'tools/list')).data.result.tools;assert.ok(tools.some(t=>t.name==='publish_post'));assert.ok(!tools.some(t=>t.name==='send_message'));
  assert.equal((await call(botKey,'publish_post',{text:'Hello',parent:reply.uri})).result.isError,false);
  assert.equal((await call(botKey,'send_message',{recipient:owner.actor.id,text:'No'})).error.code,-32602);
  assert.equal((await rpc(botKey,'tools/list',{}, {Origin:'https://evil.example'})).status,403);
  const op=(await api('account-mcp',{name:'Operator',neverExpires:true},owner.token)).data;assert.equal(op.expires,null);
  assert.equal((await api('posts',{text:'Human impersonation'},op.token)).status,401);
  assert.equal((await call(op,'publish_post',{text:'Human impersonation'})).error.code,-32602);
  assert.equal((await call(op,'publish_post',{botId:owner.actor.id,text:'Human impersonation'})).result.isError,true);
  const bots=JSON.parse((await call(op,'list_bots')).result.content[0].text).bots;assert.equal(bots[0].personality,'You are a cheerful gardener.');
  assert.equal((await call(op,'publish_post',{botId:bot.id,text:'An operator-directed bot reply',parent:reply.uri})).result.isError,false);
  assert.equal((await call(op,'like_post',{uri:root.uri})).result.isError,false);assert.equal((await call(op,'repost',{uri:reply.uri})).result.isError,false);
  const myPosts=JSON.parse((await call(op,'read_posts')).result.content[0].text).posts;assert.ok(myPosts.some(p=>p.uri===root.uri));
  const db=new DatabaseSync(join(dir,'botsky.sqlite'));
  db.prepare('UPDATE api_keys SET expires=? WHERE id=?').run('2000-01-01T00:00:00Z',botKey.id);assert.equal((await rpc(botKey,'tools/list')).status,401);
  db.prepare('UPDATE actors SET operator_id=? WHERE id=?').run(other.actor.id,bot.id);assert.equal((await call(op,'publish_post',{botId:bot.id,text:'No longer owned'})).result.isError,true);db.close();
  await api('account-mcp/revoke',{id:op.id},owner.token);assert.equal((await rpc(op,'tools/list')).status,401);
 }finally{await new Promise(resolve=>{child.once('exit',resolve);child.kill();});await rm(dir,{recursive:true,force:true});}
});

