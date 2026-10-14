import {randomUUID} from 'node:crypto';
const fail=(status,message)=>{throw Object.assign(Error(message),{status});};
export function createAccountSafety(db,{invalidate=()=>{},remoteDelete=async()=>{},cancelBilling=async()=>{},now=Date.now}={}){
 if(!db.prepare('PRAGMA table_info(actors)').all().some(c=>c.name==='deleted_at'))db.exec('ALTER TABLE actors ADD COLUMN deleted_at TEXT');
 db.exec(`CREATE TABLE IF NOT EXISTS account_blocks(actor TEXT NOT NULL REFERENCES actors(id),subject TEXT NOT NULL REFERENCES actors(id),created TEXT NOT NULL,PRIMARY KEY(actor,subject));
 CREATE TABLE IF NOT EXISTS account_deletions(actor TEXT PRIMARY KEY REFERENCES actors(id),requested INTEGER NOT NULL,status TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,next_at INTEGER NOT NULL DEFAULT 0,last_error TEXT);`);
 const actor=id=>db.prepare('SELECT * FROM actors WHERE id=?').get(id);
 function operator(id){const a=actor(id);return a?.operator_id||a?.id||id;}
 function blocked(a,b){if(!a||!b)return false;const x=operator(a),y=operator(b);return x!==y&&!!db.prepare('SELECT 1 FROM account_blocks WHERE (actor=? AND subject=?) OR (actor=? AND subject=?)').get(x,y,y,x);}
 function allow(a,b){if(blocked(a,b))fail(403,'This account is blocked.');if(actor(b)?.deleted_at)fail(410,'This account has been deleted.');}
 function block(who,subject,value){const owner=actor(who),target=actor(operator(subject));if(!owner||owner.kind!=='human'||owner.deleted_at||!target||target.deleted_at||operator(who)===target.id)fail(400,'Choose another account to block.');if(typeof value!=='boolean')fail(400,'Choose block or unblock.');if(value){db.prepare('INSERT OR IGNORE INTO account_blocks VALUES (?,?,?)').run(who,target.id,new Date(now()).toISOString());db.prepare('DELETE FROM follows WHERE (actor IN (SELECT id FROM actors WHERE id=? OR operator_id=?) AND subject IN (SELECT id FROM actors WHERE id=? OR operator_id=?)) OR (subject IN (SELECT id FROM actors WHERE id=? OR operator_id=?) AND actor IN (SELECT id FROM actors WHERE id=? OR operator_id=?))').run(who,who,target.id,target.id,who,who,target.id,target.id);}else db.prepare('DELETE FROM account_blocks WHERE actor=? AND subject=?').run(who,target.id);return {blocked:value};}
 function list(who){return {accounts:db.prepare('SELECT a.id,a.handle,a.name,a.kind,a.bio,a.photo FROM account_blocks b JOIN actors a ON a.id=b.subject WHERE b.actor=? AND a.deleted_at IS NULL ORDER BY b.created DESC').all(who)};}
 const has=table=>!!db.prepare("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?").get(table);
 function remove(table,condition,args){if(has(table))db.prepare('DELETE FROM '+table+' WHERE '+condition).run(...args);}
 function purge(id){
  invalidate(id);
  if(has('post_media'))remove('post_media','post IN (SELECT uri FROM posts WHERE author=?)',[id]);
  remove('media','actor=?',[id]);
  db.prepare("UPDATE posts SET deleted=1,text='',embed=NULL WHERE author=?").run(id);
  for(const table of ['likes','reposts'])remove(table,'actor=? OR post IN (SELECT uri FROM posts WHERE author=?)',[id,id]);
  remove('follows','actor=? OR subject=?',[id,id]);remove('tag_follows','actor=?',[id]);
  remove('notifications','recipient=? OR sender=?',[id,id]);remove('messages','sender=? OR recipient=?',[id,id]);
  remove('dating_messages','thread IN (SELECT id FROM dating_threads WHERE a=? OR b=?)',[id,id]);remove('dating_threads','a=? OR b=?',[id,id]);remove('dating_media','actor=?',[id]);remove('dating_profiles','actor=?',[id]);remove('dating_blocks','actor=? OR subject=?',[id,id]);
  remove('recovery_codes','actor=?',[id]);remove('community_members','actor=?',[id]);
  if(has('communities'))db.prepare('UPDATE communities SET archived=COALESCE(archived,?) WHERE owner=?').run(new Date(now()).toISOString(),id);
  remove('account_blocks','actor=? OR subject=?',[id,id]);
  if(has('mcp_event_subscriptions')){remove('mcp_event_deliveries','subscription IN (SELECT id FROM mcp_event_subscriptions WHERE owner=? OR actor=?)',[id,id]);remove('mcp_event_subscriptions','owner=? OR actor=?',[id,id]);}
  if(has('webhooks')){remove('webhook_deliveries','hook IN (SELECT id FROM webhooks WHERE owner=? OR actor=?)',[id,id]);remove('webhooks','owner=? OR actor=?',[id,id]);}
  if(has('push_devices')){remove('push_deliveries','device IN (SELECT id FROM push_devices WHERE owner=?)',[id]);remove('push_devices','owner=?',[id]);}
  remove('site_roles','actor=?',[id]);
  db.prepare("UPDATE actors SET deleted_at=?,suspended_at=?,suspension_reason='Account deletion requested',handle=?,name='Deleted account',bio='',photo=NULL,avatar_blob=NULL,password=NULL,salt=NULL,agent_instructions='',operator_id=NULL,us_location_verified_at=NULL WHERE id=?").run(new Date(now()).toISOString(),new Date(now()).toISOString(),'deleted-'+randomUUID()+'.invalid',id);
 }
 function request(who,target,confirmation){const owner=actor(who),a=actor(target||who);if(!owner||owner.kind!=='human'||owner.deleted_at||!a||a.deleted_at||a.id!==who&&a.operator_id!==who)fail(403,'Delete only your own account or a bot you own.');if(confirmation!=='DELETE')fail(400,'Type DELETE to confirm permanent deletion.');const ids=a.id===who?db.prepare('SELECT id FROM actors WHERE id=? OR operator_id=?').all(who,who).map(r=>r.id):[a.id];db.exec('BEGIN IMMEDIATE');try{for(const id of ids){db.prepare('INSERT INTO account_deletions(actor,requested,status) VALUES (?,?,?)').run(id,now(),'pending');purge(id);}db.exec('COMMIT');}catch(e){if(db.isTransaction)db.exec('ROLLBACK');throw e;}return {accepted:true,accounts:ids.length,remoteDeletion:'queued',appleSubscriptions:'Manage or cancel Apple subscriptions in Apple subscription settings.'};}
 let busy=false;
 async function tick(){if(busy)return;busy=true;try{const jobs=db.prepare("SELECT * FROM account_deletions WHERE status='pending' AND next_at<=? ORDER BY requested LIMIT 3").all(now());for(const j of jobs){try{await cancelBilling(j.actor);if(j.actor.startsWith('did:'))await remoteDelete(j.actor);db.exec('BEGIN IMMEDIATE');try{purge(j.actor);db.prepare("UPDATE account_deletions SET status='complete',last_error=NULL WHERE actor=?").run(j.actor);db.exec('COMMIT');}catch(e){if(db.isTransaction)db.exec('ROLLBACK');throw e;}}catch{db.prepare('UPDATE account_deletions SET attempts=attempts+1,next_at=?,last_error=? WHERE actor=?').run(now()+Math.min(3600000,10000*2**Math.min(j.attempts,8)),'Remote cleanup is pending; retry scheduled.',j.actor);}}}finally{busy=false;}}
 const timer=setInterval(()=>void tick().catch(()=>console.error('Account deletion worker failed')),5000);timer.unref();
 function orphan(id){if(typeof id!=='string'||!id.startsWith('did:'))fail(400,'Invalid orphan account.');db.prepare("INSERT OR IGNORE INTO actors(id,handle,name,kind,bio) VALUES (?,?,'Deleted account','agent','')").run(id,'deleted-'+randomUUID()+'.invalid');db.prepare('INSERT OR IGNORE INTO account_deletions(actor,requested,status) VALUES (?,?,?)').run(id,now(),'pending');purge(id);}
 return {operator,blocked,allow,block,list,request,tick,orphan,stop:()=>clearInterval(timer),jobs:()=>db.prepare('SELECT actor,requested,status,attempts,last_error FROM account_deletions ORDER BY requested DESC LIMIT 100').all()};
}
