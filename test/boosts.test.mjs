import {test} from 'node:test';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {DatabaseSync} from 'node:sqlite';
import {createBoosts} from '../boosts.mjs';
test('swarm engagement is grouped, self-support excluded, feeds deduplicated and shared limits enforced',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'amerika-boosts-'));
 const child=spawn(process.execPath,['server.mjs'],{env:{...process.env,PORT:'0',HOST:'127.0.0.1',PDS_URL:'',DATA_DIR:dir},stdio:['ignore','pipe','pipe']});
 const base=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Startup timed out')),10000);child.stdout.on('data',d=>{const m=String(d).match(/"port":(\d+)/);if(m){clearTimeout(timer);resolve('http://127.0.0.1:'+m[1]);}});child.once('exit',()=>reject(Error('Startup failed')));});
 const api=async(path,body,token)=>{const r=await fetch(base+'/api/'+path,{method:body?'POST':'GET',headers:{...(body?{'Content-Type':'application/json'}:{}),...(token?{Authorization:'Bearer '+token}:{})},...(body?{body:JSON.stringify(body)}:{})});return {status:r.status,data:await r.json()};};
 let db;
 try{
  const register=async handle=>(await api('register',{handle,name:handle,kind:'human',password:'boost-test-password',humanConfirmed:true,country:'US',rulesAccepted:true})).data;
  const owner=await register('boostowner.demo'),other=await register('boostother.demo'),viewer=await register('boostviewer.demo');
  async function bot(handle,human){const a=(await api('agents',{handle,name:handle,password:'boost-test-password',humanConfirmed:true,country:'US',rulesAccepted:true},human.token)).data.actor;const key=(await api('agent-keys',{actor:a.id,name:'Boost test',scopes:['read','like','post'],neverExpires:true},human.token)).data;return {...a,token:key.token};}
  const b1=await bot('boostone.demo',owner),b2=await bot('boosttwo.demo',owner),b3=await bot('boostthree.demo',other);
  const old=(await api('posts',{text:'Older original'},owner.token)).data.post;
  const newer=(await api('posts',{text:'Newer original'},other.token)).data.post;
  for(const a of [owner,b1,b2,other,b3]){assert.equal((await api('likes',{uri:old.uri},a.token)).status,200);assert.equal((await api('reposts',{uri:old.uri},a.token)).status,200);}
  let post=(await api('thread?uri='+encodeURIComponent(old.uri))).data.post;
  assert.equal(post.likes,2);assert.equal(post.reposts,2);assert.equal(post.engagement.likes.humans,2);assert.equal(post.engagement.likes.agents,3);assert.equal(post.engagement.likes.independentOperators,1);assert.equal(post.engagement.independentSupporters,1,'Like and repost from the same other operator count once');
  const notifications=(await api('notifications',null,owner.token)).data.notifications.filter(n=>n.post===old.uri&&['like','repost'].includes(n.type));assert.equal(notifications.length,2,'No self-support alerts or repeated swarm alerts');
  for(const a of [b1,b2,other,b3])await api('follows',{subject:a.id},viewer.token);
  const feed=(await api('feed')).data.posts;assert.equal(feed.filter(p=>p.uri===old.uri).length,1);assert.ok(feed.findIndex(p=>p.uri===newer.uri)<feed.findIndex(p=>p.uri===old.uri),'Reposts do not bump old content');
  const friends=(await api('feed?following=1',null,viewer.token)).data.posts;assert.equal(friends.filter(p=>p.uri===old.uri).length,1);assert.ok([b1.id,b2.id,other.actor.id,b3.id].includes(friends.find(p=>p.uri===old.uri).repostBy.id));
  const agentsOnly=(await api('feed?kind=agent')).data.posts;assert.ok(agentsOnly.some(p=>p.uri===old.uri&&p.repostBy.id===b3.id),'Only independent bot reposts distribute human content');
  await api('reposts',{uri:old.uri},b3.token);assert.ok(!(await api('feed?kind=agent')).data.posts.some(p=>p.uri===old.uri),'Author-owned swarms cannot distribute self-reposts');await api('reposts',{uri:old.uri},b3.token);
  const page=(await api('feed?cursor='+feed.find(p=>p.uri===newer.uri).sequence)).data.posts;assert.equal(page.filter(p=>p.uri===old.uri).length,1);
  db=new DatabaseSync(join(dir,'botsky.sqlite'));
  db.prepare('UPDATE actors SET operator_id=NULL WHERE id=?').run(b3.id);post=(await api('thread?uri='+encodeURIComponent(old.uri))).data.post;assert.equal(post.engagement.independentSupporters,1,'Unlinked bots do not add influence');
  db.prepare('UPDATE actors SET suspended_at=? WHERE id=?').run(new Date().toISOString(),other.actor.id);post=(await api('thread?uri='+encodeURIComponent(old.uri))).data.post;assert.equal(post.engagement.independentSupporters,0,'Suspended operators do not add influence');
  db.prepare('UPDATE actors SET suspended_at=NULL WHERE id=?').run(other.actor.id);
  for(const kind of ['like','repost']){const limit=kind==='like'?120:60;db.prepare('DELETE FROM boost_usage WHERE operator=? AND kind=?').run(owner.actor.id,kind);const insert=db.prepare('INSERT INTO boost_usage(operator,actor,kind,created) VALUES (?,?,?,?)');for(let i=0;i<limit;i++)insert.run(owner.actor.id,b1.id,kind,Date.now());
   for(const a of [owner,b1,b2])assert.equal((await api(kind==='like'?'likes':'reposts',{uri:newer.uri},a.token)).status,429);
   assert.equal((await api(kind==='like'?'likes':'reposts',{uri:old.uri},b1.token)).status,200,'Undo remains available at the limit');
   assert.equal((await api(kind==='like'?'likes':'reposts',{uri:old.uri},b1.token)).status,429,'Undo and redo cannot reset the allowance');
  }
  const budget=createBoosts(db,{now:()=>Date.now()+3600001});assert.doesNotThrow(()=>budget.reserve(b2.id,'repost'),'Rolling allowance expires');
  db.close();db=null;
 }finally{db?.close();await new Promise(resolve=>{child.once('exit',resolve);child.kill();});await rm(dir,{recursive:true,force:true});}
});
