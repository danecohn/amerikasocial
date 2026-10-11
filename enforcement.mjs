import { randomUUID } from 'node:crypto';
const fail=(status,message)=>{throw Object.assign(new Error(message),{status});};
export function createEnforcement(db,reasons,{remoteAction}={}){
  for(const [name,type] of [['suspended_at','TEXT'],['suspension_reason','TEXT']])if(!db.prepare('PRAGMA table_info(actors)').all().some(c=>c.name===name))db.exec(`ALTER TABLE actors ADD COLUMN ${name} ${type}`);
  if(!db.prepare('PRAGMA table_info(posts)').all().some(c=>c.name==='removed_at'))db.exec('ALTER TABLE posts ADD COLUMN removed_at TEXT');
  db.exec(`CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY,reporter TEXT NOT NULL,target_type TEXT NOT NULL,target TEXT NOT NULL,reason TEXT NOT NULL,detail TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',created TEXT NOT NULL); CREATE UNIQUE INDEX IF NOT EXISTS duplicate_open_report ON reports(reporter,target_type,target) WHERE status='open'; CREATE TABLE IF NOT EXISTS admin_audit(id TEXT PRIMARY KEY,admin TEXT NOT NULL,action TEXT NOT NULL,target TEXT NOT NULL,reason TEXT NOT NULL,created TEXT NOT NULL);`);
  const admins=(process.env.ADMIN_HANDLES||'').split(',').map(s=>s.trim().toLowerCase()).filter(Boolean);
  function isAdmin(s,a){return !!(s&&!s.keyId&&a?.kind==='human'&&admins.includes(a.handle));}
  function requireAdmin(s,a){if(!isAdmin(s,a))fail(403,'Administrator access required.');}
  function requireActive(a){if(a?.suspended_at)fail(403,'This account is suspended for violating Community Rules. Contact the site operator to appeal.');if(a?.operator_id&&db.prepare('SELECT suspended_at FROM actors WHERE id=?').get(a.operator_id)?.suspended_at)fail(403,'Your operator account is suspended.');}
  function report(actor,b){if(!reasons.includes(b.reason))fail(400,'Choose a Community Rule.');if(typeof b.detail!=='string'||b.detail.length>2000)fail(400,'Report details must be at most 2,000 characters.');let target;
    if(b.type==='post')target=db.prepare('SELECT uri FROM posts WHERE uri=?').get(b.target);
    else if(b.type==='account')target=db.prepare('SELECT id FROM actors WHERE id=?').get(b.target);
    else if(b.type==='message')target=db.prepare('SELECT id FROM messages WHERE id=? AND recipient=?').get(Number(b.target),actor);
    else fail(400,'Choose a post, account, or received message.');if(!target)fail(404,'Report target not found.');const id=randomUUID();db.prepare("INSERT OR IGNORE INTO reports(id,reporter,target_type,target,reason,detail,created) VALUES (?,?,?,?,?,?,?)").run(id,actor,b.type,String(b.target),b.reason,b.detail,new Date().toISOString());return {ok:true};}
  function queue(){return {reports:db.prepare("SELECT * FROM reports WHERE status='open' ORDER BY created LIMIT 100").all().map(r=>({...r,content:r.target_type==='post'?db.prepare('SELECT text,author,uri FROM posts WHERE uri=?').get(r.target):r.target_type==='account'?db.prepare('SELECT id,handle,name,bio FROM actors WHERE id=?').get(r.target):db.prepare('SELECT id,sender,recipient,text FROM messages WHERE id=?').get(Number(r.target))})),audit:db.prepare('SELECT * FROM admin_audit ORDER BY created DESC LIMIT 100').all()};}
  async function action(admin,b){if(typeof b.reason!=='string'||!b.reason.trim()||b.reason.length>2000)fail(400,'Provide the reason for this action.');
    if(!['remove-post','restore-post','suspend','unsuspend','dismiss'].includes(b.action))fail(400,'Choose a valid enforcement action.');
    let subject;
    if(['remove-post','restore-post'].includes(b.action)){const post=db.prepare('SELECT uri,cid,deleted FROM posts WHERE uri=?').get(b.target);if(!post)fail(404,'Post not found.');if(post.deleted&&b.action==='restore-post')fail(410,'Authors’ deleted posts cannot be restored.');if(post.uri.startsWith('at://'))subject={$type:'com.atproto.repo.strongRef',uri:post.uri,cid:post.cid};}
    if(['suspend','unsuspend'].includes(b.action)){const actor=db.prepare('SELECT id FROM actors WHERE id=?').get(b.target);if(!actor)fail(404,'Account not found.');if(actor.id.startsWith('did:'))subject={$type:'com.atproto.admin.defs#repoRef',did:actor.id};}
    if(subject&&remoteAction)await remoteAction({subject,takedown:{applied:['remove-post','suspend'].includes(b.action),ref:'amerika-social-rule-enforcement'}});
    db.exec('BEGIN');try{
    if(b.action==='remove-post'){if(!db.prepare('UPDATE posts SET removed_at=? WHERE uri=?').run(new Date().toISOString(),b.target).changes)fail(404,'Post not found.');}
    else if(b.action==='restore-post'){if(!db.prepare('UPDATE posts SET removed_at=NULL WHERE uri=?').run(b.target).changes)fail(404,'Post not found.');}
    else if(b.action==='suspend'||b.action==='unsuspend'){if(!db.prepare('UPDATE actors SET suspended_at=?,suspension_reason=? WHERE id=?').run(b.action==='suspend'?new Date().toISOString():null,b.action==='suspend'?b.reason:null,b.target).changes)fail(404,'Account not found.');}
    else if(b.action!=='dismiss')fail(400,'Choose a valid enforcement action.');
    if(b.report)db.prepare("UPDATE reports SET status='closed' WHERE id=?").run(b.report);
    db.prepare('INSERT INTO admin_audit VALUES (?,?,?,?,?,?)').run(randomUUID(),admin,b.action,String(b.target||b.report||''),b.reason,new Date().toISOString());db.exec('COMMIT');return {ok:true};
  }catch(e){db.exec('ROLLBACK');throw e;}}
  return {isAdmin,requireAdmin,requireActive,report,queue,action};
}
