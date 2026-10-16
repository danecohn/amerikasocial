import {spawn} from 'node:child_process';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {DatabaseSync} from 'node:sqlite';
import test from 'node:test';
import assert from 'node:assert/strict';
import {crc32} from 'node:zlib';
import {authorizeMcp} from './oauth-helper.mjs';
function archive(name='index.html',html='<!doctype html><h1>Game Crafter test game</h1>'){const n=Buffer.from(name),d=Buffer.from(html),crc=crc32(d),h=Buffer.alloc(30),c=Buffer.alloc(46),e=Buffer.alloc(22);h.writeUInt32LE(0x04034b50);h.writeUInt16LE(20,4);h.writeUInt32LE(crc,14);h.writeUInt32LE(d.length,18);h.writeUInt32LE(d.length,22);h.writeUInt16LE(n.length,26);c.writeUInt32LE(0x02014b50);c.writeUInt16LE(20,4);c.writeUInt16LE(20,6);c.writeUInt32LE(crc,16);c.writeUInt32LE(d.length,20);c.writeUInt32LE(d.length,24);c.writeUInt16LE(n.length,28);e.writeUInt32LE(0x06054b50);e.writeUInt16LE(1,8);e.writeUInt16LE(1,10);e.writeUInt32LE(c.length+n.length,12);e.writeUInt32LE(h.length+n.length+d.length,16);return Buffer.concat([h,n,d,c,n,e]);}
test('Gaming OAuth is isolated; Plus-only one-use uploads remain private until explicit publication',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'amerika-gaming-mcp-'));const child=spawn(process.execPath,['server.mjs'],{env:{...process.env,DATA_DIR:dir,PORT:'0',PDS_URL:'',BACKUPS_ENABLED:'false',STRIPE_SECRET_KEY:'',HUMAN_CAPTCHA_REQUIRED:'false',TURNSTILE_SECRET_KEY:'',TURNSTILE_SITE_KEY:'',GAMING_LOCAL_PACKAGES:join(dir,'none')},stdio:['ignore','pipe','pipe']});
 const base=await new Promise((resolve,reject)=>{let output='';const timer=setTimeout(()=>reject(Error(output)),15000);child.stdout.on('data',c=>{output+=c;const m=output.match(/"port":(\d+)/);if(m){clearTimeout(timer);resolve('http://localhost:'+m[1]);}});child.stderr.on('data',c=>output+=c);child.once('exit',()=>{clearTimeout(timer);reject(Error(output));});});
 const api=async(path,data,token)=>{const r=await fetch(base+'/api/'+path,{method:data?'POST':'GET',headers:{...(token?{Authorization:'Bearer '+token}:{}),...(data?{'Content-Type':'application/json'}:{})},...(data?{body:JSON.stringify(data)}:{})});return {status:r.status,data:await r.json()};};
 const rpc=async(token,name,args={})=>{const r=await fetch(base+'/mcp/gaming',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method:name==='tools/list'?name:'tools/call',params:name==='tools/list'?{}:{name,arguments:args}})});const data=await r.json();return {status:r.status,data,result:data.result?.content?JSON.parse(data.result.content[0].text.startsWith('{')?data.result.content[0].text:'null'):data.result};};
 try{
  for(const suffix of ['','/support','/privacy','/terms']){const page=await fetch(base+'/game-crafter'+suffix);assert.equal(page.status,200);assert.match(page.headers.get('x-robots-tag'),/noindex/);const html=await page.text();assert.match(html,/Game Crafter/);assert.match(html,/noindex,nofollow/);if(suffix==='/support')assert.match(html,/mailto:support@amerika.social/);}
  assert.doesNotMatch(await (await fetch(base+'/')).text(),/href="\/game-crafter/);
  const download=await fetch(base+'/game-crafter/download',{method:'HEAD'});assert.equal(download.status,200);assert.equal(download.headers.get('content-type'),'application/zip');assert.ok(Number(download.headers.get('content-length'))>900000);
  assert.equal((await fetch(base+'/game-crafter/demo-game.zip')).status,200);
  const anon=await fetch(base+'/mcp/gaming',{method:'POST'});assert.equal(anon.status,401);assert.match(anon.headers.get('www-authenticate'),/oauth-protected-resource\/mcp\/gaming/);
  const meta=await (await fetch(base+'/.well-known/oauth-protected-resource/mcp/gaming')).json();assert.deepEqual(meta.scopes_supported,['gaming.read','gaming.publish']);
  const register=async handle=>(await api('register',{handle,name:handle,kind:'human',password:'gaming-mcp-test-password',americanConfirmed:true,rulesAccepted:true})).data;
  const human=await register('publisher.demo'),other=await register('other.demo');const tokens=await authorizeMcp(base,{mcpUrl:base+'/mcp/gaming'},human.token);
  const listed=await rpc(tokens.access_token,'tools/list');assert.equal(listed.result.tools.length,6);assert.ok(listed.result.tools.every(t=>typeof t.annotations.readOnlyHint==='boolean'&&typeof t.annotations.openWorldHint==='boolean'&&typeof t.annotations.destructiveHint==='boolean'));assert.equal(listed.result.tools.find(t=>t.name==='list_my_games').annotations.readOnlyHint,true);assert.equal((await rpc(tokens.access_token,'publish_post',{text:'no'})).data.error.code,-32602);
  const args={title:'Reviewer Game',description:'A local reproducible browser fixture',controls:'Mouse',rightsConfirmed:true,rulesAccepted:true};
  assert.equal((await rpc(tokens.access_token,'get_gaming_account')).result.plus,false);assert.equal((await rpc(tokens.access_token,'prepare_game_upload',args)).data.result.isError,true);
  const db=new DatabaseSync(join(dir,'botsky.sqlite'));const setPlus=value=>{if(value)db.prepare('INSERT OR REPLACE INTO billing_subscriptions VALUES (?,?,?,?,?,?,?)').run('fixture',human.actor.id,'no-payment','active',Math.floor(Date.now()/1000)+86400,0,new Date().toISOString());else db.prepare('DELETE FROM billing_subscriptions WHERE actor=?').run(human.actor.id);};setPlus(true);
  assert.equal((await rpc(tokens.access_token,'get_gaming_account')).result.canPublish,true);assert.equal((await rpc(tokens.access_token,'get_game_upload_guide')).result.maxFiles,10000);
  const prepared=(await rpc(tokens.access_token,'prepare_game_upload',args)).result;assert.equal(prepared.game.status,'draft');assert.equal((await api('gaming/catalog')).data.games.some(g=>g.id===prepared.game.id),false);
  const put=async(p,bytes=archive())=>fetch(p.uploadUrl,{method:'PUT',headers:p.headers,body:bytes});
  let uploaded=await put(prepared);assert.equal(uploaded.status,201);assert.equal((await uploaded.json()).game.status,'draft');assert.equal((await put(prepared)).status,401);
  const status=(await rpc(tokens.access_token,'get_game_upload_status',{gameId:prepared.game.id})).result;assert.equal(status.readyToPublish,true);assert.equal(status.upload.status,'complete');assert.equal(JSON.stringify(status).includes('secret'),false);
  assert.equal((await api('gaming/catalog')).data.games.some(g=>g.id===prepared.game.id),false);assert.equal((await rpc(tokens.access_token,'publish_game',{gameId:prepared.game.id,publishConfirmed:false})).data.result.isError,true);
  const otherTokens=await authorizeMcp(base,{mcpUrl:base+'/mcp/gaming'},other.token);assert.equal((await rpc(otherTokens.access_token,'get_game_upload_status',{gameId:prepared.game.id})).data.result.isError,true);
  const readOnly=await authorizeMcp(base,{mcpUrl:base+'/mcp/gaming'},human.token,'gaming.read');assert.equal((await rpc(readOnly.access_token,'prepare_game_upload',args)).data.error.code,-32602);
  setPlus(false);assert.equal((await rpc(tokens.access_token,'publish_game',{gameId:prepared.game.id,publishConfirmed:true})).data.result.isError,true);setPlus(true);
  assert.equal((await rpc(tokens.access_token,'publish_game',{gameId:prepared.game.id,publishConfirmed:true})).result.game.status,'published');assert.equal((await api('gaming/catalog')).data.games.some(g=>g.id===prepared.game.id),true);
  const invalid=(await rpc(tokens.access_token,'prepare_game_upload',args)).result;uploaded=await put(invalid,archive('../escape.html'));assert.equal(uploaded.status,400);assert.equal((await rpc(tokens.access_token,'get_game_upload_status',{gameId:invalid.game.id})).result.upload.status,'failed');
  const revoked=(await rpc(tokens.access_token,'prepare_game_upload',args)).result;const grants=await api('oauth/grants',null,human.token);const grant=grants.data.grants.find(g=>g.resource===base+'/mcp/gaming'&&g.scopes.includes('gaming.publish'));assert.ok(grant);await api('oauth/revoke',{id:grant.id},human.token);assert.equal((await put(revoked)).status,401);
  const service=await authorizeMcp(base,{mcpUrl:base+'/mcp/service'},human.token);assert.equal((await rpc(service.access_token,'list_my_games')).status,401);
  db.close();
 }finally{const exit=new Promise(r=>child.once('exit',r));child.kill();await exit;await rm(dir,{recursive:true,force:true});}
});
