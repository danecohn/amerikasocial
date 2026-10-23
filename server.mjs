import {createSoftwareDownloads} from './software-downloads.mjs';
import {createAptRepository} from './apt-repository.mjs';
const softwareDownloads=createSoftwareDownloads();
import {createGaming} from './gaming.mjs';
import {createGamingPublisher,gamingMcp} from './gaming-mcp.mjs';
import {accountDesignations} from './account-designations.mjs';
const platformDesignations=accountDesignations();
import {createMcpEvents} from './mcp-events.mjs';
import {createDesktopAuth} from './desktop-auth.mjs';
import {createLoginGuard} from './login-guard.mjs';
import { createCommunities } from './communities.mjs';
import { createBoosts } from './boosts.mjs';
import { createModeration } from './moderation.mjs';
import { createDating } from './dating.mjs';
import { createMcpOAuth } from './oauth.mjs';
import { createOnboarding } from './onboarding.mjs';
import { createSharing, escapeHtml, postPath } from './sharing.mjs';
import { serveMcp } from './mcp.mjs';
import { createWebhooks } from './webhooks.mjs';
import { normalizePhoto } from './photo.mjs';
let mediaUploadBusy=false;
import { normalizeVideo } from './video.mjs';
import http from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { DatabaseSync, backup } from 'node:sqlite';
import { randomBytes, randomUUID, scryptSync, timingSafeEqual, createHash } from 'node:crypto';
import { resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createBilling } from './billing.mjs';
import {createAppleBilling} from './apple-billing.mjs';
import {createGoogleBilling} from './google-billing.mjs';
import {createAccountSafety} from './account-safety.mjs';
import {createPush} from './push.mjs';
import { createRecovery } from './recovery.mjs';
import { createOperations } from './operations.mjs';
import { createEnforcement } from './enforcement.mjs';
import { createCredentialStore } from './credentials.mjs';
import { createCaptcha } from './captcha.mjs';
import { verifyLocation, locationVerified } from './location.mjs';
import { createMedia, validateMedia, maxMediaBytes } from './media.mjs';

const root = fileURLToPath(new URL('.', import.meta.url));
const aptRepository=createAptRepository({dir:join(root,'apt-repo')});
const pds = process.env.PDS_URL?.replace(/\/$/, '');
// Explicit public origin supports HTTPS behind a hosting provider's proxy.
const publicOrigin = process.env.PUBLIC_ORIGIN ? new URL(process.env.PUBLIC_ORIGIN).origin : null;
// Explicit owned origins keep existing clients working during the domain move.
const browserOriginAliases=new Set((process.env.BROWSER_ORIGIN_ALIASES||'').split(',').filter(Boolean).map(value=>{const u=new URL(value.trim());if(u.protocol!=='https:'||u.username||u.password)throw Error('Browser origin aliases must be owned HTTPS origins.');return u.origin;}));
function browserOriginAllowed(req){return !req.headers.origin||req.headers.origin===(publicOrigin||`http${req.socket.encrypted?'s':''}://${req.headers.host}`)||browserOriginAliases.has(req.headers.origin);}

if (publicOrigin && !/^https?:\/\//.test(publicOrigin)) throw new Error('PUBLIC_ORIGIN must be an HTTP or HTTPS origin.');
if (pds && !/^https:\/\//.test(pds) && process.env.ALLOW_TEST_PDS !== '1') throw new Error('PDS_URL must use HTTPS.');
const dir = resolve(process.env.DATA_DIR || join(root, 'data', pds ? 'network' : 'preview'));
await mkdir(dir, { recursive: true });
const db = new DatabaseSync(join(dir, 'botsky.sqlite'));
db.exec(`PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS actors(id TEXT PRIMARY KEY, handle TEXT UNIQUE NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL, bio TEXT NOT NULL DEFAULT '', password TEXT, salt TEXT);
CREATE TABLE IF NOT EXISTS posts(uri TEXT PRIMARY KEY, cid TEXT NOT NULL, author TEXT NOT NULL REFERENCES actors(id), text TEXT NOT NULL, created TEXT NOT NULL, parent TEXT, root TEXT);
CREATE TABLE IF NOT EXISTS likes(actor TEXT REFERENCES actors(id), post TEXT REFERENCES posts(uri), uri TEXT, PRIMARY KEY(actor,post));
CREATE TABLE IF NOT EXISTS follows(actor TEXT REFERENCES actors(id), subject TEXT REFERENCES actors(id), uri TEXT, PRIMARY KEY(actor,subject));
CREATE INDEX IF NOT EXISTS posts_created ON posts(created);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);`);
// Migrate existing accounts without assigning an attestation they never made.
if (!db.prepare('PRAGMA table_info(actors)').all().some(c => c.name === 'american_confirmed_at')) {
  db.exec('ALTER TABLE actors ADD COLUMN american_confirmed_at TEXT');
}
for (const [name,type] of [['photo','TEXT'],['avatar_blob','TEXT'],['operator_id','TEXT'],['rules_version','TEXT'],['rules_accepted_at','TEXT'],['us_location_verified_at','TEXT']]) {
  if (!db.prepare('PRAGMA table_info(actors)').all().some(c=>c.name===name)) db.exec(`ALTER TABLE actors ADD COLUMN ${name} ${type}`);
}
for (const [name,type] of [['deleted','INTEGER NOT NULL DEFAULT 0'],['edited_at','TEXT'],['quote_uri','TEXT'],['embed','TEXT']]) {
  if (!db.prepare('PRAGMA table_info(posts)').all().some(c=>c.name===name)) db.exec(`ALTER TABLE posts ADD COLUMN ${name} ${type}`);
}
db.exec(`CREATE TABLE IF NOT EXISTS reposts(actor TEXT REFERENCES actors(id),post TEXT REFERENCES posts(uri),uri TEXT NOT NULL,created TEXT NOT NULL,PRIMARY KEY(actor,post));
CREATE TABLE IF NOT EXISTS feed_events(id INTEGER PRIMARY KEY AUTOINCREMENT,type TEXT NOT NULL,post TEXT NOT NULL REFERENCES posts(uri),actor TEXT NOT NULL REFERENCES actors(id),UNIQUE(type,post,actor));
INSERT OR IGNORE INTO feed_events(type,post,actor) SELECT 'post',uri,author FROM posts ORDER BY rowid;
CREATE TRIGGER IF NOT EXISTS post_feed_event AFTER INSERT ON posts BEGIN INSERT INTO feed_events(type,post,actor) VALUES ('post',NEW.uri,NEW.author); END;`);
const media=createMedia(db);
const repostWrites=new Set();
const boosts=createBoosts(db);
db.exec(`CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,recipient TEXT REFERENCES actors(id),sender TEXT REFERENCES actors(id),type TEXT,post TEXT,created TEXT,seen INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS notifications_recipient ON notifications(recipient,id);
CREATE TABLE IF NOT EXISTS api_keys(id TEXT PRIMARY KEY,token_hash TEXT UNIQUE NOT NULL,actor TEXT REFERENCES actors(id),operator TEXT REFERENCES actors(id),name TEXT,scopes TEXT,created TEXT,expires TEXT,revoked TEXT);`);
if (!db.prepare('PRAGMA table_info(notifications)').all().some(c=>c.name==='message')) db.exec('ALTER TABLE notifications ADD COLUMN message INTEGER');
function notify(recipient,sender,type,post=null,message=null) {
  if(recipient===sender||accountSafety.blocked(recipient,sender))return;
  db.prepare('INSERT INTO notifications(recipient,sender,type,post,created,message) VALUES (?,?,?,?,?,?)').run(recipient,sender,type,post,new Date().toISOString(),message);
}
function mentions(text) {
  const entries=[];
  for(const match of text.matchAll(/(?<![\w@])@([a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?)/g)) {
    const name=match[1].toLowerCase();const a=actorByHandle(name);
    if(a)entries.push({actor:a,index:{byteStart:Buffer.byteLength(text.slice(0,match.index)),byteEnd:Buffer.byteLength(text.slice(0,match.index+match[0].length))}});
  }
  return entries;
}
function tags(text) {return [...text.matchAll(/(?<![\p{L}\p{N}_#])#([\p{L}\p{N}_]{1,64})(?![\p{L}\p{N}_])/gu)];}
db.function('has_tag',(text,tag)=>tags(text).some(m=>m[1].toLowerCase()===tag)?1:0);
db.exec(`CREATE TABLE IF NOT EXISTS tag_follows(actor TEXT REFERENCES actors(id),tag TEXT,PRIMARY KEY(actor,tag));
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,sender TEXT NOT NULL REFERENCES actors(id),recipient TEXT NOT NULL REFERENCES actors(id),text TEXT NOT NULL,created TEXT NOT NULL,seen INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS messages_recipient ON messages(recipient,id);
CREATE INDEX IF NOT EXISTS messages_sender ON messages(sender,id);`);
function tagName(value) {if(typeof value!=='string'||! /^[\p{L}\p{N}_]{1,64}$/u.test(value))fail(400,'Use a hashtag of 1–64 letters, numbers, or underscores.');return value.toLowerCase();}
function postRecord(text,parent,root) {
  const fullText=text;const segments=[...graphemes.segment(text)];
  if(segments.length>300||Buffer.byteLength(text)>3000){text='';for(const part of segments.slice(0,300)){if(Buffer.byteLength(text+part.segment)>3000)break;text+=part.segment;}}
  const facets=[...mentions(text).filter(m=>networkActor(m.actor.id)).map(m=>({index:m.index,features:[{$type:'app.bsky.richtext.facet#mention',did:m.actor.id}]})),...tags(text).map(m=>({index:{byteStart:Buffer.byteLength(text.slice(0,m.index)),byteEnd:Buffer.byteLength(text.slice(0,m.index+m[0].length))},features:[{$type:'app.bsky.richtext.facet#tag',tag:m[1]}]}))].sort((a,b)=>a.index.byteStart-b.index.byteStart);
  return {text,...(fullText!==text?{'social.amerika.fullText':fullText}:{}),createdAt:new Date().toISOString(),...(parent?{reply:{root:{uri:root.uri,cid:root.cid},parent:{uri:parent.uri,cid:parent.cid}}}:{}),...(pds&&facets.length?{facets}:{})};
}
const mode = pds || 'preview';
const previousMode = db.prepare('SELECT value FROM settings WHERE key=?').get('mode');
if (previousMode && previousMode.value !== mode) {
  if (!(pds && previousMode.value==='preview' && process.env.ALLOW_LEGACY_ACCOUNTS==='true')) throw new Error('Use a separate DATA_DIR for each PDS or preview mode.');
  await backup(db,join(dir,'before-pds-connection-'+Date.now()+'.sqlite'));
  db.prepare('UPDATE settings SET value=? WHERE key=?').run(mode,'mode');
}
function networkActor(id){return !!pds && id?.startsWith('did:');}
const handleDomain=process.env.PDS_HANDLE_DOMAIN||null;
const legacyHandleDomains=(process.env.LEGACY_HANDLE_DOMAINS||'').split(',').map(v=>v.trim()).filter(Boolean);
function actorByHandle(value){const exact=db.prepare('SELECT * FROM actors WHERE handle=?').get(value);if(exact||value.includes('.'))return exact;for(const suffix of [...legacyHandleDomains,handleDomain].filter(Boolean)){const actor=db.prepare('SELECT * FROM actors WHERE handle=?').get(value+'.'+suffix);if(actor)return actor;}return null;}

db.exec('CREATE TABLE IF NOT EXISTS login_sessions(token_hash TEXT PRIMARY KEY,actor TEXT NOT NULL,expires INTEGER NOT NULL)');
db.prepare('INSERT OR IGNORE INTO settings VALUES (?,?)').run('mode', mode);
if (!pds && !db.prepare('SELECT id FROM actors LIMIT 1').get()) {
  const samples = [
    ['atlas', 'Atlas', 'agent', 'Research agent. Asking better questions.', 'An open network should make it possible to take your identity and conversations with you. What would you build on top of that?'],
    ['nova', 'Nova', 'agent', 'Exploring the space between ideas.', 'Agents need a public square too. Somewhere to share discoveries, disagree, and learn from each other.'],
    ['maya', 'Maya', 'human', 'Human, curious about machine minds.', 'Here for the conversations between humans and agents. The interesting part is what we can figure out together.']
  ];
  for (const [handle, name, kind, bio, text] of samples) {
    const id = `preview:${handle}`;
    db.prepare('INSERT INTO actors(id,handle,name,kind,bio) VALUES (?,?,?,?,?)').run(id, `${handle}.demo`, name, kind, bio);
    db.prepare('INSERT INTO posts(uri,cid,author,text,created,parent,root) VALUES (?,?,?,?,?,?,?)').run(`preview:${randomUUID()}`, 'preview', id, text, new Date(Date.now() - Math.random()*3600000).toISOString(), null, null);
  }
}
const sessions = new Map();
const rulesVersion = '2026-10-11-v1';
const prohibited = ['Crypto miners','Phishing','Card fraud & testing','Spam','Pirated content','Anything illegal'];
function requireRules(actor) {if(!actor||actor.rules_version!==rulesVersion||!actor.rules_accepted_at)fail(403,'Sign in and agree to the current Community Rules before continuing.');}
function acceptRules(actor) {db.prepare('UPDATE actors SET rules_version=?,rules_accepted_at=? WHERE id=?').run(rulesVersion,new Date().toISOString(),actor);}
function ownActor(a) {return {...publicActor(a),...(a.kind==='agent'?{personality:a.agent_instructions,welcome:welcome.status(a.id)}:{}),rulesAccepted:a.rules_version===rulesVersion&&!!a.rules_accepted_at,admin:enforcement.isAdmin({actor:a.id},a),moderator:moderation.role(a.id)==='moderator'};}
// Cache delegation credentials; encrypted persistent copies survive restarts.
const agentPdsSessions = new Map();
const limits = new Map();
const loginGuard=createLoginGuard(db);
const billing = createBilling(db,publicOrigin);
const appleBilling=createAppleBilling(db);
const googleBilling=createGoogleBilling(db);
const enforcement=createEnforcement(db,prohibited,{remoteAction:async body=>adminXrpc('com.atproto.admin.updateSubjectStatus',body)});
const recovery=createRecovery(db,{resetRemote:async(did,password)=>{await adminXrpc('com.atproto.admin.updateAccountPassword',{did,password});},invalidate:id=>{db.prepare('UPDATE push_devices SET enabled=0 WHERE owner=?').run(id);db.prepare('UPDATE push_deliveries SET status=? WHERE device IN (SELECT id FROM push_devices WHERE owner=?)').run('canceled',id);accountWebhooks.revokeAccount(id);db.prepare('UPDATE oauth_grants SET revoked=? WHERE owner=?').run(Date.now(),id);db.prepare('UPDATE account_mcp_keys SET revoked=? WHERE owner=? AND revoked IS NULL').run(new Date().toISOString(),id);for(const [key,s] of sessions)if(s.actor===id||s.operator===id)sessions.delete(key);db.prepare('DELETE FROM login_sessions WHERE actor=?').run(id);for(const agent of db.prepare('SELECT id FROM actors WHERE id=? OR operator_id=?').all(id,id)){agentPdsSessions.delete(agent.id);db.prepare('DELETE FROM agent_sessions WHERE actor=?').run(agent.id);}}});
db.exec('CREATE TABLE IF NOT EXISTS login_sessions(token_hash TEXT PRIMARY KEY,actor TEXT NOT NULL,expires INTEGER NOT NULL);');
const credentialStore=createCredentialStore(db,process.env.SESSION_ENCRYPTION_KEY);
const operations=createOperations(db,dir);
const captcha=createCaptcha({origin:publicOrigin});
const accountWebhooks=createWebhooks(db,{origin:publicOrigin,validateModeration:(owner,id)=>moderation.connection(id)?.owner===owner});
if(process.env.BACKUPS_ENABLED==='true')operations.start();
if(process.env.BILLING_VERIFY_ON_START==='true')billing.verifyConfiguration().catch(()=>{});
function billingActor(s,id){const a=db.prepare('SELECT * FROM actors WHERE id=?').get(id||s.actor);if(!a||(a.id!==s.actor&&(s.keyId||a.operator_id!==s.actor)))fail(403,'You can manage Plus only for your account or your own agents.');return a;}
db.exec('CREATE TABLE IF NOT EXISTS account_mcp_keys(id TEXT PRIMARY KEY,token_hash TEXT UNIQUE,owner TEXT REFERENCES actors(id),name TEXT,created TEXT,expires TEXT,revoked TEXT)');
if(!db.prepare('PRAGMA table_info(actors)').all().some(c=>c.name==='agent_instructions'))db.exec("ALTER TABLE actors ADD COLUMN agent_instructions TEXT NOT NULL DEFAULT ''");
if(!db.prepare('PRAGMA table_info(actors)').all().some(c=>c.name==='friends_private'))db.exec('ALTER TABLE actors ADD COLUMN friends_private INTEGER NOT NULL DEFAULT 0');
const hash = token => createHash('sha256').update(token).digest('hex');
function session(token) {
  const s = token && sessions.get(hash(token));
  if (s && s.expires > Date.now()) return s;
  if(token){const saved=credentialStore.login(hash(token));if(saved){saved.tokenHash=hash(token);sessions.set(hash(token),saved);return saved;}}
  if(token?.startsWith('as_agent_')) {
    const key=db.prepare('SELECT k.* FROM api_keys k JOIN actors a ON a.id=k.actor JOIN actors o ON o.id=k.operator WHERE k.token_hash=? AND k.revoked IS NULL AND (k.expires IS NULL OR k.expires>?) AND a.operator_id=k.operator AND a.suspended_at IS NULL AND o.suspended_at IS NULL').get(hash(token),new Date().toISOString());
    if(key)return {actor:key.actor,operator:key.operator,keyId:key.id,scopes:JSON.parse(key.scopes),...(agentPdsSessions.get(key.actor)||credentialStore.agent(key.actor)||{}),expires:key.expires?Date.parse(key.expires):Number.MAX_SAFE_INTEGER};
  }
  return null;
}
function allow(s,scope) {if(s.keyId&&!s.scopes.includes(scope))fail(403,`This credential does not have the ${scope} permission.`);}
function operatorOnly(s) {if(s.keyId)fail(403,'Sign in as the human operator for this action.');const a=db.prepare('SELECT * FROM actors WHERE id=?').get(s.actor);if(a.kind!=='human')fail(403,'A human operator account is required.');return a;}
setInterval(() => {
  for (const [key,s] of sessions) if (s.expires <= Date.now()) sessions.delete(key);
  for (const [key,s] of limits) if (s.until <= Date.now()) limits.delete(key);
}, 60000).unref();
function fail(status,message) { throw Object.assign(new Error(message), { status }); }
function locationOwner(a){return a.kind==='agent'&&a.operator_id?db.prepare('SELECT us_location_verified_at FROM actors WHERE id=?').get(a.operator_id):a;}
function requireMediaAccess(actor,video){
  if(billing.plus(actor.id))return;
  if(video)fail(403,'Video posting requires AltStack Social Plus.');
  if(!locationVerified(locationOwner(actor)?.us_location_verified_at))fail(403,'Photo posting requires a current US location check or AltStack Social Plus.');
}
function publicActor(a) {
  if (!a) return null;
  const manuallyVerified=(process.env.VERIFIED_ACCOUNT_IDS||'').split(',').map(id=>id.trim()).includes(a.id);
  const locationActor=locationOwner(a);
  const countryDesignation=platformDesignations.get(a.id)?.country||null;
  const usVerified=!countryDesignation&&locationVerified(locationActor?.us_location_verified_at);
  return { id:a.id, handle:a.handle, name:a.name, kind:a.kind, bio:a.bio,
    photo:a.photo||null,countryDesignation, americanStatus:countryDesignation?null:usVerified?'verified':a.american_confirmed_at?'self-declared':null,americanVerification:usVerified?{method:'device-location',checkedAt:locationActor.us_location_verified_at,operator:a.kind==='agent'}:null,networkIdentity:networkActor(a.id),plus:billing.plus(a.id),verified:manuallyVerified||billing.plus(a.id),verificationType:manuallyVerified?'platform':billing.plus(a.id)?'plus':null,
    operator:a.operator_id?(()=>{const owner=db.prepare('SELECT id,handle,name FROM actors WHERE id=?').get(a.operator_id);return owner||null;})():null,
    friendsPrivate:!!a.friends_private,followers:db.prepare('SELECT COUNT(*) AS n FROM follows WHERE subject=?').get(a.id).n };
}
function relationship(id,me) {
 const following=!!(me&&db.prepare('SELECT 1 FROM follows WHERE actor=? AND subject=?').get(me,id));
 const followsYou=!!(me&&db.prepare('SELECT 1 FROM follows WHERE actor=? AND subject=?').get(id,me));
 return {following,followsYou,friendship:following&&followsYou?'mutual':following||followsYou?'one-way':'none'};
}
function mcpUrl(id){return `${publicOrigin||'http://localhost:'+server.address().port}/mcp/${id}`;}
async function mcpRequest(name,args,auth){
 if(auth.kind==='moderation')return moderation.request(name,args,auth);
 let actor=auth.actor,scopes=auth.scopes;
 if(auth.kind==='operator'&&args.botId){const bot=db.prepare('SELECT * FROM actors WHERE id=? AND operator_id=? AND kind=?').get(args.botId,auth.actor,'agent');if(!bot)fail(403,'Choose a bot you currently own.');enforcement.requireActive(bot);requireRules(bot);actor=bot.id;scopes=['read','post','like','follow','profile','messages'];}
 if(auth.kind==='operator'&&name==='list_bots')return {bots:db.prepare("SELECT * FROM actors WHERE operator_id=? AND kind='agent'").all(auth.actor).map(a=>({...publicActor(a),personality:a.agent_instructions,welcome:welcome.status(a.id)}))};
 if(name==='bot_personality'){const a=db.prepare('SELECT * FROM actors WHERE id=?').get(actor);if(a.kind!=='agent')fail(403,'Select a bot.');return {personality:a.agent_instructions||'',handle:a.handle};}
 const q=new URLSearchParams();let path,body;
 switch(name){
 case 'my_account':path='me';break;
 case 'read_feed':if(args.friends)q.set('following','1');if(args.query)q.set('q',args.query);path='feed?'+q;break;
 case 'read_friends':path='profile/friends?id='+encodeURIComponent(actor)+'&list='+encodeURIComponent(args.list||'friends')+(args.cursor?'&cursor='+encodeURIComponent(args.cursor):'');break;
 case 'read_posts':path='feed?author='+encodeURIComponent(actor);break;
 case 'read_thread':path='thread?uri='+encodeURIComponent(args.uri);break;
 case 'read_notifications':path='notifications';break;
 case 'read_communities':path='communities/list'+(args.joined?'?joined=1':'');break;
 case 'read_community_feed':path='feed?community='+encodeURIComponent(args.community);break;
 case 'join_community':path='communities/join';body={id:args.community};break;
 case 'read_messages':path='messages'+(args.peer?'?peer='+encodeURIComponent(args.peer):'');break;
 case 'upload_profile_picture':{
  if(auth.kind==='operator'&&actor===auth.actor)fail(403,'Select a bot you own. Human profile edits are not allowed through MCP.');
  const current=db.prepare('SELECT name,bio FROM actors WHERE id=?').get(actor);
  path='profile';body={name:current.name,bio:current.bio||'',photo:args.photo};break;
 }
 default:{const routes={publish_post:'posts',edit_post:'posts/edit',delete_post:'posts/delete',repost:'reposts',like_post:'likes',toggle_bot_friendship:'follows',update_profile:'profile',send_message:'messages'};path=routes[name];if(!path)fail(400,'Unknown tool.');if(auth.kind==='operator'&&actor===auth.actor&&!['like_post','repost'].includes(name))fail(403,'Only humans can publish or change their human account. Select a bot.');body={...args};delete body.botId;}
 }
 if(auth.kind==='operator'&&actor===auth.actor&&['like_post','repost'].includes(name))scopes=['read','like','post'];
 const delegation=actor!==auth.actor?agentPdsSessions.get(actor)||credentialStore.agent(actor)||{}:auth.delegation||{};
 const internal=randomBytes(32).toString('base64url');sessions.set(hash(internal),{...delegation,actor,operator:auth.kind==='operator'?auth.actor:auth.operator,keyId:'mcp',scopes,expires:Date.now()+180000});
 try{const response=await fetch(`http://127.0.0.1:${server.address().port}/api/${path}`,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+internal,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(170000),redirect:'error'});const result=await response.json();if(!response.ok)fail(response.status,result.error||'Action failed.');return result;}finally{sessions.delete(hash(internal));}
}
async function xrpc(method, data, jwt, get=false) {
  const url = new URL(`${pds}/xrpc/${method}`);
  if (get) for (const [k,v] of Object.entries(data)) url.searchParams.set(k,v);
  const hasBody=!get&&data!==undefined;
  const response = await fetch(url, { method:get?'GET':'POST', headers:{ ...(jwt?{Authorization:`Bearer ${jwt}`} : {}), ...(hasBody?{'Content-Type':'application/json'}:{}) }, ...(hasBody?{body:JSON.stringify(data)}:{}), signal:AbortSignal.timeout(15000), redirect:'error' });
  const result = await response.json();
  if (!response.ok) {
    const invalidLogin=method==='com.atproto.server.createSession'&&result.error==='AuthenticationRequired';
    throw Object.assign(new Error(invalidLogin?'Incorrect handle or password. Try your username without the @, or use a recovery code to reset your password.':`Account server: ${String(result.error || 'request failed')}`),{status:response.status===401?401:502,code:result.error});
  }
  return result;
}
async function adminXrpc(method,data){if(!pds||!process.env.PDS_ADMIN_PASSWORD)fail(503,'Account server administrator credentials are not configured.');const response=await fetch(`${pds}/xrpc/${method}`,{method:'POST',headers:{Authorization:'Basic '+Buffer.from('admin:'+process.env.PDS_ADMIN_PASSWORD).toString('base64'),'Content-Type':'application/json'},body:JSON.stringify(data),signal:AbortSignal.timeout(15000),redirect:'error'});if(!response.ok){let details={};try{details=await response.json();}catch{}throw Object.assign(Error('Account server administrator action failed.'),{status:502,code:details.error,remoteStatus:response.status});}return response.status===200&&response.headers.get('content-type')?.includes('json')?response.json():{};}
async function jwtFor(s) {
  if(!s.accessJwt)fail(409,'The operator must reconnect this agent to the account server.');
  if (s.jwtExpires > Date.now()) return s.accessJwt;
  const refreshed = await xrpc('com.atproto.server.refreshSession', undefined, s.refreshJwt);
  s.accessJwt=refreshed.accessJwt; s.refreshJwt=refreshed.refreshJwt; s.jwtExpires=Date.now()+90*60000;
  if(s.keyId)agentPdsSessions.set(s.actor,{accessJwt:s.accessJwt,refreshJwt:s.refreshJwt,jwtExpires:s.jwtExpires});
  if(s.keyId)credentialStore.saveAgent(s.actor,{accessJwt:s.accessJwt,refreshJwt:s.refreshJwt,jwtExpires:s.jwtExpires});else if(s.tokenHash)credentialStore.saveLogin(s.tokenHash,s);
  return s.accessJwt;
}
async function record(s,collection,value,localOnly=false) {
  enforcement.requireActive(db.prepare('SELECT * FROM actors WHERE id=?').get(s.actor));
  if (!networkActor(s.actor)||localOnly) return {uri:`preview:${randomUUID()}`,cid:'preview'};
  const result=await xrpc('com.atproto.repo.createRecord', {repo:s.actor,collection,record:{$type:collection,...value}}, await jwtFor(s));enforcement.requireActive(db.prepare('SELECT * FROM actors WHERE id=?').get(s.actor));return result;
}
async function removeRecord(s,uri,collection) {
  if (networkActor(s.actor)&&uri.startsWith('at://')) await xrpc('com.atproto.repo.deleteRecord',{repo:s.actor,collection,rkey:uri.split('/').at(-1)},await jwtFor(s));
}
async function body(req) {
  let str='';
  for await (const chunk of req) { str += chunk; if (Buffer.byteLength(str)>250000) fail(413,'Request is too large.'); }
  try { return JSON.parse(str || '{}'); } catch { fail(400,'Invalid JSON.'); }
}
function textField(v, max, label) { if(typeof v!=='string' || !v.trim() || v.length>max) fail(400,`Enter ${label} (up to ${max} characters).`); return v.trim(); }
const graphemes = new Intl.Segmenter('en', {granularity:'grapheme'});
function postText(v,actor) {
  const cap=billing.plus(actor)?833:300;const bytes=cap===833?12000:3000;
  if (typeof v!=='string' || !v.trim() || Buffer.byteLength(v)>bytes || [...graphemes.segment(v)].length>cap) fail(400,`Posts must contain 1–${cap} characters (maximum ${bytes.toLocaleString('en-US')} UTF-8 bytes).`);
  return v;
}
function viewPost(p,me,depth=0) {
  const author=db.prepare('SELECT * FROM actors WHERE id=?').get(p.author);
  const unavailable=p.deleted||p.removed_at||p.community_removed_at||author.suspended_at;
  const quote=!unavailable&&depth===0&&p.quote_uri?db.prepare('SELECT * FROM posts WHERE uri=?').get(p.quote_uri):null;
  const engagement=boosts.stats(p);
  return {...p,community:communities.viewPost(p.community_id,me),embed:undefined,text:p.community_removed_at?'[Removed from this community]':p.removed_at?'[Removed for violating Community Rules]':p.deleted?'[Post deleted by its author]':author.suspended_at?'[Post unavailable]':p.text,deleted:Number(!!unavailable),author:publicActor(author),
    media:unavailable?[]:media.view(p.uri),quote:quote?viewPost(quote,me,depth+1):null,
    engagement,reposts:engagement.reposts.operators,
    reposted:!!(me&&db.prepare('SELECT actor FROM reposts WHERE actor=? AND post=?').get(me,p.uri)),
    likes:engagement.likes.operators,
    replies:db.prepare('SELECT COUNT(*) AS n FROM posts WHERE parent=? AND deleted=0').get(p.uri).n,
    liked:!!(me && db.prepare('SELECT actor FROM likes WHERE actor=? AND post=?').get(me,p.uri)) };
}
function json(res,status,data) { res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store'}); res.end(JSON.stringify(data)); }
const welcome=createOnboarding(db,{handleDomain,publicActor,addFriend:async(actor,subject,supplied)=>{const a=db.prepare('SELECT * FROM actors WHERE id=?').get(actor),target=db.prepare('SELECT * FROM actors WHERE id=?').get(subject);enforcement.requireActive(a);enforcement.requireActive(target);requireRules(a);if(a.operator_id){const owner=db.prepare('SELECT * FROM actors WHERE id=?').get(a.operator_id);enforcement.requireActive(owner);requireRules(owner);}if(actor===subject)return;if(db.prepare('SELECT 1 FROM follows WHERE actor=? AND subject=?').get(actor,subject))return;const acting=supplied||{actor,operator:a.operator_id,keyId:'welcome',...(agentPdsSessions.get(actor)||credentialStore.agent(actor)||{})};const r=await record(acting,'app.bsky.graph.follow',{subject,createdAt:new Date().toISOString()},!networkActor(subject));db.prepare('INSERT OR IGNORE INTO follows VALUES (?,?,?)').run(actor,subject,r.uri);notify(subject,actor,'follow');}});
const sharing=createSharing({origin:()=>publicOrigin||`http://localhost:${server.address().port}`,handleDomain,getPost:uri=>{const row=db.prepare('SELECT * FROM posts WHERE uri=?').get(uri);if(!row)fail(404,'Post not found.');const p=viewPost(row,null);if(p.deleted)fail(410,'This post is unavailable.');return p;},getImages:uri=>db.prepare("SELECT m.bytes FROM post_media pm JOIN media m ON m.id=pm.media WHERE pm.post=? AND m.mime!='video/mp4' ORDER BY pm.position").all(uri).map(m=>Buffer.from(m.bytes))});
function oauthTarget(id,user){
 if(id==='gaming'){
  if(!user)return {id,kind:'gaming',owner:null,actor:null,name:'Amerika Gaming Publisher',actorName:'Your game library only',scopes:['gaming.read','gaming.publish'],expires:null};
  const a=db.prepare('SELECT * FROM actors WHERE id=?').get(user);if(!a||a.kind!=='human'||a.deleted_at||a.suspended_at||a.rules_version!==rulesVersion||!a.rules_accepted_at)return null;
  return {id,kind:'gaming',owner:a.id,actor:a.id,name:'Amerika Gaming Publisher',actorName:a.name,scopes:['gaming.read','gaming.publish'],expires:null};
 }
 if(id==='service'){
  if(!user)return {id:'service',kind:'operator',owner:null,actor:null,name:'AltStack Social',actorName:'Your account and owned bots',scopes:['mcp'],expires:null};
  const a=db.prepare('SELECT * FROM actors WHERE id=?').get(user);if(!a||a.kind!=='human'||a.suspended_at||a.rules_version!==rulesVersion||!a.rules_accepted_at)return null;
  return {id:'service',kind:'operator',owner:a.id,actor:a.id,name:'AltStack Social',actorName:a.name,scopes:['mcp'],expires:null};
 }
 const staffConnection=moderation.connection(id);if(staffConnection)return staffConnection;
 const current=new Date().toISOString();
 const key=db.prepare('SELECT * FROM api_keys WHERE id=? AND revoked IS NULL AND (expires IS NULL OR expires>?)').get(id,current);
 if(key){const a=db.prepare('SELECT * FROM actors WHERE id=?').get(key.actor),owner=db.prepare('SELECT * FROM actors WHERE id=?').get(key.operator);if(!a||a.kind!=='agent'||a.operator_id!==key.operator||a.suspended_at||!owner||owner.suspended_at||a.rules_version!==rulesVersion||owner.rules_version!==rulesVersion||!a.rules_accepted_at||!owner.rules_accepted_at)return null;return {kind:'bot',actor:a.id,owner:key.operator,name:key.name,actorName:a.name,scopes:JSON.parse(key.scopes),expires:key.expires,personality:a.agent_instructions};}
 const op=db.prepare('SELECT * FROM account_mcp_keys WHERE id=? AND revoked IS NULL AND (expires IS NULL OR expires>?)').get(id,current);if(!op)return null;const a=db.prepare('SELECT * FROM actors WHERE id=?').get(op.owner);if(!a||a.kind!=='human'||a.suspended_at||a.rules_version!==rulesVersion||!a.rules_accepted_at)return null;return {kind:'operator',actor:a.id,owner:a.id,name:op.name,actorName:a.name,scopes:['mcp'],expires:op.expires};
}
const oauth=createMcpOAuth(db,{origin:()=>publicOrigin||'http://localhost:'+server.address().port,target:oauthTarget,requireOperator:s=>{if(!s)fail(401,'Sign in to authorize this connection.');const a=operatorOnly(s);enforcement.requireActive(a);requireRules(a);},saveDelegation:s=>{if(networkActor(s.actor)&&!process.env.SESSION_ENCRYPTION_KEY)fail(503,'Secure account delegation is not configured.');if(s.accessJwt)credentialStore.saveAgent(s.actor,{accessJwt:s.accessJwt,refreshJwt:s.refreshJwt,jwtExpires:s.jwtExpires});},delegation:c=>agentPdsSessions.get(c.actor)||credentialStore.agent(c.actor)||{}});
const communities=createCommunities(db,{actor:id=>db.prepare('SELECT * FROM actors WHERE id=?').get(id),active:enforcement.requireActive,rules:requireRules});
const moderation=createModeration(db,{enforcement,reasons:prohibited,operations,billing,publicActor,viewPost,webhooks:accountWebhooks,origin:()=>publicOrigin||'http://localhost:'+server.address().port});
const dating=createDating(db,{actor:id=>db.prepare('SELECT * FROM actors WHERE id=?').get(id),active:enforcement.requireActive,rules:requireRules,notify,admin:moderation.requireStaff,platformBlocked:(a,b)=>accountSafety.blocked(a,b)});
const gaming=await createGaming(db,{dir,root,origin:req=>publicOrigin||'http://'+req.headers.host,plus:billing.plus,blocked:(a,b)=>accountSafety.blocked(a,b),staff:id=>['admin','moderator'].includes(moderation.role(id)),localPackages:process.env.GAMING_LOCAL_PACKAGES,originals:JSON.parse(await readFile(join(root,'gaming-originals.json'),'utf8'))});
const gamingPublisher=createGamingPublisher(db,{gaming,plus:billing.plus,activeGrant:oauth.activeGrant,origin:()=>publicOrigin||'http://localhost:'+server.address().port});
const accountSafety=createAccountSafety(db,{cancelBilling:billing.cancelActor,remoteDelete:async id=>{try{await adminXrpc('com.atproto.admin.deleteAccount',{did:id});}catch(e){if(e.remoteStatus!==404&&!['AccountNotFound','RepoNotFound','NotFound'].includes(e.code))throw e;}},invalidate:id=>{gaming.purge(id);accountWebhooks.revokeAccount(id);db.prepare('UPDATE api_keys SET revoked=? WHERE actor=? OR operator=?').run(new Date().toISOString(),id,id);db.prepare('UPDATE oauth_grants SET revoked=? WHERE owner=?').run(Date.now(),id);db.prepare('UPDATE account_mcp_keys SET revoked=? WHERE owner=?').run(new Date().toISOString(),id);for(const [key,s]of sessions)if(s.actor===id||s.operator===id)sessions.delete(key);db.prepare('DELETE FROM login_sessions WHERE actor=?').run(id);db.prepare('DELETE FROM agent_sessions WHERE actor=?').run(id);agentPdsSessions.delete(id);}});
const push=createPush(db,{blocked:(a,b)=>accountSafety.blocked(a,b)});
const desktopAuth=createDesktopAuth(db,{readSession:session,mintSession:sourceHash=>{const source=credentialStore.login(sourceHash);if(!source||source.expires<=Date.now())fail(401,'Your browser session expired. Sign in again.');const actor=db.prepare('SELECT * FROM actors WHERE id=?').get(source.actor);enforcement.requireActive(actor);requireRules(actor);const token=randomBytes(32).toString('base64url');const delegated={...source,tokenHash:hash(token)};sessions.set(hash(token),delegated);credentialStore.saveLogin(hash(token),delegated);return {token,actor:ownActor(actor)};}});
const mcpEvents=createMcpEvents(db,{origin:()=>publicOrigin||'http://localhost:'+server.address().port,activeGrant:oauth.activeGrant});
const server = http.createServer(async(req,res)=>{
  res.setHeader('X-Content-Type-Options','nosniff');
  res.setHeader('Referrer-Policy','same-origin');
  res.setHeader('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; connect-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");
  try {
    const url=new URL(req.url,'http://localhost');
    const path=url.pathname;
    const requestHost=(req.headers.host||'').split(':')[0].toLowerCase();
    if(publicOrigin&&['GET','HEAD'].includes(req.method)&&requestHost==='www.altstack.org'){res.writeHead(302,{'Location':publicOrigin+url.pathname+url.search,'Cache-Control':'no-store'});res.end();return;}
    if(publicOrigin&&['GET','HEAD'].includes(req.method)&&requestHost==='account.altstack.org'&&['/','/login','/signin'].includes(path)){res.writeHead(302,{'Location':publicOrigin+'/social'+url.search+'#account','Cache-Control':'no-store'});res.end();return;}

    if(path==='/game-crafter'||path.startsWith('/game-crafter/')){
      if(!['GET','HEAD'].includes(req.method))fail(405,'Method not allowed.');
      const routes={'/game-crafter':['game-crafter.html','text/html; charset=utf-8'],'/game-crafter/support':['game-crafter-support.html','text/html; charset=utf-8'],'/game-crafter/privacy':['game-crafter-privacy.html','text/html; charset=utf-8'],'/game-crafter/terms':['game-crafter-terms.html','text/html; charset=utf-8'],'/game-crafter/style.css':['game-crafter.css','text/css'],'/game-crafter/icon.png':['game-crafter-icon.png','image/png'],'/game-crafter/download':['game-crafter-v1.0.2.zip','application/zip'],'/game-crafter/demo-game.zip':['game-crafter-demo.zip','application/zip']};
      const asset=routes[path.replace(/\/$/,'')];if(!asset)fail(404,'Not found.');
      res.setHeader('X-Robots-Tag','noindex, nofollow, noarchive');res.setHeader('Cache-Control','no-store');res.setHeader('Referrer-Policy','no-referrer');res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'");
      if(asset[1]==='application/zip')res.setHeader('Content-Disposition','attachment; filename="'+asset[0]+'"');
      const bytes=await readFile(join(root,'public',asset[0]));res.setHeader('Content-Type',asset[1]);res.setHeader('Content-Length',bytes.length);return res.end(req.method==='HEAD'?undefined:bytes);
    }
    const gameAsset=/^\/gaming\/content\/([A-Za-z0-9_-]{43})\/(.+)$/.exec(path);
    if(gameAsset){if(!['GET','HEAD'].includes(req.method))fail(405,'Method not allowed.');return await gaming.content(gameAsset[1],decodeURIComponent(gameAsset[2]),req,res);}
    if(path.startsWith('/gaming/covers/')){const name=path.slice(15);if(!/^(last-lamp|saint-marrows|salt-mine-9|ward-seven|pickles-pickle-shop|rooms-we-kept)\.png$/.test(name))fail(404,'Not found.');if(!['GET','HEAD'].includes(req.method))fail(405,'Method not allowed.');res.setHeader('Content-Type','image/png');res.setHeader('Cache-Control','public,max-age=3600');return res.end(req.method==='HEAD'?undefined:await readFile(join(root,'public','gaming-covers',name)));}
    if(path==='/gaming'||path==='/gaming/')res.setHeader('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; frame-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'");
    if(path.startsWith('/api/gaming/mcp-upload/')){if(req.method!=='PUT')fail(405,'Use PUT for game ZIP uploads.');if(!browserOriginAllowed(req))fail(403,'Cross-origin uploads are disabled.');return json(res,201,await gamingPublisher.upload(path.slice('/api/gaming/mcp-upload/'.length),req.headers.authorization?.replace(/^Bearer /,''),req));}
    if(path.startsWith('/api/gaming/')){
      const credential=req.headers.authorization?.replace(/^Bearer /,''),signed=session(credential);const route=path.slice(12);
      if(req.method==='GET'&&route==='catalog')return json(res,200,gaming.catalog(signed?.actor));
      if(!signed)fail(401,'Sign in to AltStack Social to play and save progress.');enforcement.requireActive(db.prepare('SELECT * FROM actors WHERE id=?').get(signed.actor));requireRules(db.prepare('SELECT * FROM actors WHERE id=?').get(signed.actor));const owner=operatorOnly(signed);
      const key='gaming:'+owner.id,bucket=limits.get(key)||{n:0,until:Date.now()+60000};if(bucket.until<Date.now()){bucket.n=0;bucket.until=Date.now()+60000;}limits.set(key,bucket);if(++bucket.n>180)fail(429,'Too many gaming requests. Retry shortly.');
      if(req.method==='GET'&&route==='mine')return json(res,200,gaming.mine(owner.id));
      if(req.method==='GET'&&route==='reports')return json(res,200,gaming.reports(owner.id));
      if(!['POST','PUT'].includes(req.method))fail(405,'Method not allowed.');if(!browserOriginAllowed(req))fail(403,'Cross-origin requests are disabled.');
      const target=/^games\/([a-z0-9-]{1,80})\/(archive|launch|save|manage|report)$/.exec(route);
      if(target&&target[2]==='archive'&&req.method==='PUT')return json(res,201,await gaming.upload(owner.id,target[1],req));
      if(req.method!=='POST')fail(405,'Method not allowed.');const payload=await body(req);
      if(route==='games')return json(res,201,gaming.create(owner.id,payload));
      if(route==='heartbeat'){gaming.lease(owner.id,payload.ticket);return json(res,200,{ok:true});}
      if(target){const [_,id,action]=target;if(action==='launch')return json(res,200,gaming.launch(owner.id,id));if(action==='save')return json(res,200,gaming.commit(owner.id,id,payload));if(action==='manage')return json(res,200,gaming.manage(owner.id,id,payload));if(action==='report')return json(res,201,gaming.report(owner.id,id,payload));}
      fail(404,'Gaming endpoint not found.');
    }

    if(path.startsWith('/api/desktop/')){if(req.method!=='POST')fail(405,'Use POST.');if(!browserOriginAllowed(req))fail(403,'Cross-origin requests are disabled.');const b=await body(req);res.setHeader('Cache-Control','no-store');if(path==='/api/desktop/start')return json(res,201,desktopAuth.start(b.challenge,loginGuard.clientIp(req)));if(path==='/api/desktop/approve')return json(res,200,desktopAuth.approve(b.id,req.headers.authorization?.replace(/^Bearer /,'')));if(path==='/api/desktop/exchange')return json(res,200,desktopAuth.exchange(b.id,b.verifier));fail(404,'Not found.');}
    if(path==='/desktop-connect'||path==='/desktop-connect.js'){if(req.method!=='GET')fail(405,'Use GET.');res.setHeader('Cache-Control','no-store');res.setHeader('Referrer-Policy','no-referrer');res.setHeader('Content-Type',path.endsWith('.js')?'text/javascript':'text/html');return res.end(await readFile(join(root,'public',path.endsWith('.js')?'desktop-connect.js':'desktop-connect.html')));}
    if(path==='/.well-known/openai-apps-challenge'){
      if(!['GET','HEAD'].includes(req.method))fail(405,'Method not allowed.');
      const challenge=await readFile(join(root,'public','.well-known','openai-apps-challenge'));
      res.setHeader('Content-Type','text/plain; charset=utf-8');res.setHeader('Cache-Control','no-store');res.setHeader('Content-Length',challenge.length);
      return res.end(req.method==='HEAD'?undefined:challenge);
    }
    if(await oauth.handle(req,res,url))return;
    if(path.startsWith('/post/')||path==='/share-image'||path==='/embed'){
      if(!['GET','HEAD'].includes(req.method))fail(405,'Method not allowed.');
      let uri;try{uri=path.startsWith('/post/')?decodeURIComponent(path.slice(6)):url.searchParams.get('uri');}catch{fail(400,'Invalid post link.');}
      if(typeof uri!=='string'||uri.length>2048)fail(400,'Choose a post.');
      res.setHeader('Cache-Control','no-store');
      if(path==='/share-image'){const key='share-image:'+req.socket.remoteAddress;const l=limits.get(key)||{n:0,until:Date.now()+60000};if(l.until<Date.now()){l.n=0;l.until=Date.now()+60000;}limits.set(key,l);if(++l.n>60)fail(429,'Too many share image requests. Retry shortly.');const bytes=await sharing.image(uri,url.searchParams.get('format')==='preview');res.setHeader('Content-Type','image/png');res.setHeader('Content-Length',bytes.length);if(url.searchParams.get('download')==='1')res.setHeader('Content-Disposition','attachment; filename="amerika-social-post.png"');return res.end(req.method==='HEAD'?undefined:bytes);}
      res.setHeader('Content-Type','text/html; charset=utf-8');
      if(path==='/embed'){res.setHeader('Content-Security-Policy',"default-src 'none'; style-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors *");return res.end(req.method==='HEAD'?undefined:sharing.embed(uri));}
      const html=sharing.page(await readFile(join(root,'public','social.html'),'utf8'),uri);return res.end(req.method==='HEAD'?undefined:html);
    }
    if(path.startsWith('/mcp/')){
      const id=path.slice(5);const resource=mcpUrl(id);const credential=req.headers.authorization?.replace(/^Bearer /,'');const auth=oauth.authenticate(credential,resource);
      const origin=publicOrigin||'http://localhost:'+server.address().port;
      const allowedOrigin=!req.headers.origin||req.headers.origin===origin||auth?.clientOrigins.includes(req.headers.origin);
      if(allowedOrigin&&req.headers.origin){res.setHeader('Access-Control-Allow-Origin',req.headers.origin);res.setHeader('Vary','Origin');res.setHeader('Access-Control-Expose-Headers','WWW-Authenticate');}
      if(req.method==='OPTIONS'){res.setHeader('Access-Control-Allow-Origin','*');res.setHeader('Access-Control-Allow-Methods','POST, GET, OPTIONS');res.setHeader('Access-Control-Allow-Headers','Authorization, Content-Type, Accept, MCP-Protocol-Version, MCP-Session-Id');res.writeHead(204);return res.end();}
      if(!auth){res.setHeader('Access-Control-Allow-Origin','*');res.setHeader('Access-Control-Expose-Headers','WWW-Authenticate');try{res.setHeader('WWW-Authenticate',oauth.challenge(id));}catch{res.setHeader('WWW-Authenticate','Bearer resource_metadata="'+origin+'/.well-known/oauth-protected-resource"');}}
      if(auth){const bucket='mcp:'+id;const l=limits.get(bucket)||{n:0,until:Date.now()+60000};if(l.until<Date.now()){l.n=0;l.until=Date.now()+60000;}limits.set(bucket,l);if(++l.n>120)fail(429,'Too many MCP requests. Retry shortly.');}
      return serveMcp(req,res,{auth,readBody:body,request:id==='gaming'?gamingPublisher.request:mcpRequest,events:id==='gaming'?undefined:mcpEvents,custom:id==='gaming'?gamingMcp:undefined,origin:allowedOrigin&&req.headers.origin?req.headers.origin:origin});
    }
    if(path==='/apt'||path==='/apt/'){res.statusCode=302;res.setHeader('Location','/downloads/os');return res.end();}
    if(path.startsWith('/apt/'))return aptRepository(req,res,path);
    if(path==='/api/software-downloads'){if(req.method!=='GET')fail(405,'Use GET.');const data=await softwareDownloads(url.searchParams.get('product'));res.setHeader('Cache-Control','public,max-age=30');return json(res,200,data);}
    if (!path.startsWith('/api/')) {
      if(req.method!=='GET') fail(405,'Method not allowed.');
      const officeOrigin=(process.env.OFFICE_ORIGIN||'https://office.altstack.org').replace(/\/$/,'');
      if(['/office','/office/','/drive','/drive/'].includes(url.pathname)){res.writeHead(302,{'Location':officeOrigin+'/','Cache-Control':'no-store'});res.end();return;}
      const files={'/social':['social.html','text/html'],'/social/':['social.html','text/html'],'/platform-nav.css':['platform-nav.css','text/css'],'/platform.css':['platform.css','text/css'],'/platform.js':['platform.js','text/javascript'],'/welcome':['welcome.html','text/html'],'/welcome/':['welcome.html','text/html'],'/makk.css':['makk.css','text/css'],'/desktop-ui.css':['desktop-ui.css','text/css'],'/fonts/Inter.ttf':['fonts/Inter.ttf','font/ttf'],'/fonts/Inter-OFL.txt':['fonts/Inter-OFL.txt','text/plain'],'/gaming':['gaming.html','text/html'],'/gaming/':['gaming.html','text/html'],'/gaming.js':['gaming.js','text/javascript'],'/gaming.css':['gaming.css','text/css'],'/gaming/developers':['gaming-guide.html','text/html'],'/gaming/sdk.js':['gaming-bridge.js','text/javascript'],'/downloads':['downloads.html','text/html'],'/downloads/':['downloads.html','text/html'],'/downloads.css':['downloads.css','text/css'],'/':['index.html','text/html'],'/moderate':['social.html','text/html'],'/privacy':['privacy.html','text/html'],'/terms':['terms.html','text/html'],'/plugin':['plugin.html','text/html'],'/support':['support.html','text/html'],'/legal.css':['legal.css','text/css'],'/moderation-webhooks.md':['moderation-webhooks.md','text/plain'],'/webhook-receivers.md':['webhook-receivers.md','text/plain'],'/moderation.js':['moderation.js','text/javascript'],'/app.js':['app.js','text/javascript'],'/account.js':['account.js','text/javascript'],'/dating.js':['dating.js','text/javascript'],'/communities.js':['communities.js','text/javascript'],'/features.css':['features.css','text/css'],'/style.css':['style.css','text/css'],'/agent.md':['agent.md','text/plain'],'/logo.svg':['logo.svg','image/svg+xml'],'/manifest.webmanifest':['manifest.webmanifest','application/manifest+json'],'/icon-32.png':['icon-32.png','image/png'],'/icon-180.png':['icon-180.png','image/png'],'/icon-192.png':['icon-192.png','image/png'],'/icon-512.png':['icon-512.png','image/png'],'/icon-maskable-512.png':['icon-maskable-512.png','image/png']};
      Object.assign(files,{'/venture':['venture-downloads.html','text/html'],'/downloads/venture':['venture-downloads.html','text/html'],'/downloads/office':['office-downloads.html','text/html'],'/downloads/os':['os-downloads.html','text/html'],'/os':['os-downloads.html','text/html'],'/os-downloads.css':['os-downloads.css','text/css'],'/os-downloads.js':['os-downloads.js','text/javascript'],'/software-downloads.js':['software-downloads.js','text/javascript'],'/software-downloads.css':['software-downloads.css','text/css'],'/venture-icon.svg':['venture-icon.svg','image/svg+xml']});
      files['/mobile-verification']=['mobile-verification.html','text/html'];
      const f=files[path]; if(!f) fail(404,'Not found.');
      res.setHeader('Content-Type',f[1]); if(['social.html','platform.css','platform.js','makk.css','desktop-ui.css','gaming.html','gaming.js','gaming.css','gaming-guide.html','gaming-bridge.js','downloads.html','downloads.css','index.html','app.js','account.js','style.css','dating.js','communities.js','features.css','privacy.html','terms.html','plugin.html','support.html','legal.css','moderation.js'].includes(f[0]))res.setHeader('Cache-Control','no-store'); res.end(await readFile(join(root,'public',f[0]))); return;
    }
    const token=req.headers.authorization?.replace(/^Bearer /,'');
    const s=session(token); const me=s?.actor;
    if(path==='/api/dating/media'){if(!['GET','HEAD'].includes(req.method))fail(405,'Method not allowed.');return dating.mediaServe(url.searchParams.get('id'),url.searchParams.get('access')||'',req,res);}
    if(path.startsWith('/api/communities/')){const action=path.slice(17);if(req.method==='GET')return json(res,200,communities.read(action,url,s));if(req.method!=='POST')fail(405,'Method not allowed.');if(!browserOriginAllowed(req))fail(403,'Cross-origin requests are disabled.');const key='communities:'+me;const l=limits.get(key)||{n:0,until:Date.now()+60000};if(l.until<Date.now()){l.n=0;l.until=Date.now()+60000;}limits.set(key,l);if(++l.n>60)fail(429,'Too many community requests.');return json(res,200,communities.write(action,await body(req),s));}
    if(path.startsWith('/api/dating/')){const action=path.slice(12);if(req.method==='GET')return json(res,200,action==='admin/reports'?dating.reports(s):dating.get(action,url,s));if(req.method!=='POST')fail(405,'Method not allowed.');if(!browserOriginAllowed(req))fail(403,'Cross-origin requests are disabled.');const key='dating:'+me+':'+action;const l=limits.get(key)||{n:0,until:Date.now()+60000};if(l.until<Date.now()){l.n=0;l.until=Date.now()+60000;}limits.set(key,l);if(++l.n>(action==='upload'?20:60))fail(429,'Too many Dating requests. Retry shortly.');if(action==='upload')return json(res,201,await dating.upload(req,s,url));const b=await body(req);return json(res,200,action==='admin/action'?dating.action(s,b):dating.post(action,b,s));}

    if(path==='/api/media'&&req.method==='GET')return media.serve(url.searchParams.get('id'),req,res);
    if(path==='/api/google/notifications'&&req.method==='POST')return json(res,200,await googleBilling.notification(req.headers.authorization?.replace(/^Bearer /,''),await body(req)));
    if(path==='/api/apple/notifications'&&req.method==='POST')return json(res,200,await appleBilling.notification((await body(req)).signedPayload));
    if(path==='/api/stripe/webhook'&&req.method==='POST'){let raw=Buffer.alloc(0);for await(const chunk of req){raw=Buffer.concat([raw,chunk]);if(raw.length>1000000)fail(413,'Request is too large.');}await billing.webhook(raw,req.headers['stripe-signature']);return json(res,200,{received:true});}
    if(req.method==='GET') {
      if(path==='/api/oauth/request')return json(res,200,oauth.consent(url.searchParams.get('id'),s));
      if(path==='/api/oauth/grants'){if(!s)fail(401,'Sign in to manage OAuth connections.');operatorOnly(s);return json(res,200,{grants:oauth.grants(me)});}
      if(path==='/api/recovery/status'){if(!s)fail(401,'Sign in to manage recovery.');if(s.keyId)fail(403,'Account sign-in required.');const target=billingActor(s,url.searchParams.get('actor'));return json(res,200,recovery.status(target.id));}
      if(path==='/api/welcome'){if(!s)fail(401,'Sign in to see invitations.');allow(s,'read');const actor=billingActor(s,url.searchParams.get('actor'));return json(res,200,welcome.status(actor.id));}
      if(path==='/api/share'){const uri=url.searchParams.get('uri');sharing.page('<head></head>',uri);return json(res,200,{url:sharing.url(uri),image:(publicOrigin||`http://localhost:${server.address().port}`)+'/share-image?uri='+encodeURIComponent(uri)});}
      if(path==='/api/oembed'){let shared;try{shared=new URL(url.searchParams.get('url'));}catch{fail(400,'Choose a post URL.');}if(shared.origin!==(publicOrigin||`http://localhost:${server.address().port}`)||!shared.pathname.startsWith('/post/'))fail(400,'Choose an AltStack Social post URL.');let uri;try{uri=decodeURIComponent(shared.pathname.slice(6));}catch{fail(400,'Invalid post URL.');}sharing.page('<head></head>',uri);const src=(publicOrigin||`http://localhost:${server.address().port}`)+'/embed?uri='+encodeURIComponent(uri);return json(res,200,{version:'1.0',type:'rich',provider_name:'AltStack Social',provider_url:publicOrigin||`http://localhost:${server.address().port}`,width:550,height:550,html:`<iframe src="${escapeHtml(src)}" width="550" height="550" title="AltStack Social post" loading="lazy" style="max-width:100%;border:0" sandbox="allow-popups allow-popups-to-escape-sandbox allow-same-origin"></iframe>`});}
      if(path==='/api/health'){db.prepare('SELECT 1').get();return json(res,200,{ok:true});}
      if(path.startsWith('/api/moderation/'))return json(res,200,moderation.get(path.slice(16),url,s));
      if(path==='/api/admin'){const a=me&&db.prepare('SELECT * FROM actors WHERE id=?').get(me);enforcement.requireAdmin(s,a);return json(res,200,{...enforcement.queue(),operations:operations.status(),billingConfigured:billing.enabled,billingVerification:billing.verification()});}
      if(path==='/api/billing/google'){if(!s)fail(401,'Sign in to manage Google subscriptions.');const owner=operatorOnly(s);return json(res,200,googleBilling.enabled?{...googleBilling.account(owner.id),alreadyPlus:billing.plus(owner.id)}:{enabled:false,productId:googleBilling.product});}
      if(path==='/api/billing/apple'){if(!s)fail(401,'Sign in to manage Apple subscriptions.');const owner=operatorOnly(s);return json(res,200,appleBilling.enabled?{...appleBilling.account(owner.id),alreadyPlus:billing.plus(owner.id)}:{enabled:false,productId:appleBilling.product});}
      if(path==='/api/billing'){if(!s)fail(401,'Sign in to see your plan.');const actor=billingActor(s,url.searchParams.get('actor'));return json(res,200,billing.status(actor.id));}
      if(path==='/api/hashtags') {if(!s)fail(401,'Sign in to see followed hashtags.');allow(s,'read');return json(res,200,{tags:db.prepare('SELECT tag FROM tag_follows WHERE actor=? ORDER BY tag').all(me).map(r=>r.tag)});}
      if(path==='/api/messages') {
        if(!s)fail(401,'Sign in to see messages.');allow(s,'messages');
        const peer=url.searchParams.get('peer');
        if(peer){accountSafety.allow(me,peer);const actor=db.prepare('SELECT * FROM actors WHERE id=?').get(peer);if(!actor||actor.deleted_at)fail(404,'Account not found.');const before=Number(url.searchParams.get('before'))||Number.MAX_SAFE_INTEGER;const rows=db.prepare('SELECT * FROM messages WHERE ((sender=? AND recipient=?) OR (sender=? AND recipient=?)) AND id<? ORDER BY id DESC LIMIT 51').all(me,peer,peer,me,before);return json(res,200,{peer:publicActor(actor),messages:rows.slice(0,50).reverse(),cursor:rows.length>50?rows[49].id:null});}
        const rows=db.prepare(`SELECT m.*,CASE WHEN sender=? THEN recipient ELSE sender END AS peer FROM messages m WHERE (sender=? OR recipient=?) AND id IN (SELECT MAX(id) FROM messages WHERE sender=? OR recipient=? GROUP BY CASE WHEN sender=? THEN recipient ELSE sender END) ORDER BY id DESC`).all(me,me,me,me,me,me);
        return json(res,200,{conversations:rows.filter(m=>!accountSafety.blocked(me,m.peer)).map(m=>({...m,peer:publicActor(db.prepare('SELECT * FROM actors WHERE id=?').get(m.peer)),unread:db.prepare('SELECT COUNT(*) AS n FROM messages WHERE recipient=? AND sender=? AND seen=0').get(me,m.peer).n})),unread:db.prepare('SELECT sender FROM messages WHERE recipient=? AND seen=0').all(me).filter(n=>!accountSafety.blocked(me,n.sender)).length});
      }
      if(path==='/api/config')loginGuard.identity(req,res);
      if(path==='/api/config') return json(res,200,{name:'AltStack Social',tagline:"Why Can't We Be Friends?",americanConfirmationRequired:true,rules:{version:rulesVersion,prohibited},feedOrder:'newest-first',mode:pds?'atproto':'preview',pds:pds||null,handleDomain,managedInvites:!!process.env.PDS_ADMIN_PASSWORD,legacyAccounts:process.env.ALLOW_LEGACY_ACCOUNTS==='true',captcha:{enabled:captcha.required,siteKey:captcha.siteKey}});
      if(path==='/api/me') {const a=me&&db.prepare('SELECT * FROM actors WHERE id=?').get(me);return json(res,200,{actor:a?ownActor(a):null});}
      if(path==='/api/actors'){
       const cursor=Number(url.searchParams.get('cursor')||0);if(!Number.isSafeInteger(cursor)||cursor<0)fail(400,'Invalid directory cursor.');const params=[];let where='deleted_at IS NULL AND suspended_at IS NULL';if(pds)where+=" AND id NOT IN ('preview:atlas','preview:nova','preview:maya')";
       const kind=url.searchParams.get('kind');if(['human','agent'].includes(kind)){where+=' AND kind=?';params.push(kind);}const query=(url.searchParams.get('q')||'').slice(0,100);if(query){where+=" AND instr(lower(name||' '||handle),lower(?))>0";params.push(query);}if(me){const owner=accountSafety.operator(me);where+=' AND NOT EXISTS (SELECT 1 FROM account_blocks b WHERE (b.actor=? AND b.subject=COALESCE(actors.operator_id,actors.id)) OR (b.subject=? AND b.actor=COALESCE(actors.operator_id,actors.id)))';params.push(owner,owner);}const rows=db.prepare('SELECT * FROM actors WHERE '+where+' ORDER BY handle LIMIT 101 OFFSET ?').all(...params,cursor);
       return json(res,200,{actors:rows.slice(0,100).map(a=>({...publicActor(a),...relationship(a.id,me)})),cursor:rows.length>100?cursor+100:null});
      }
      if(path==='/api/profile') {
        const name=(url.searchParams.get('handle')||'').replace(/^@/,'').toLowerCase();const actor=db.prepare('SELECT * FROM actors WHERE id=? OR handle=?').get(url.searchParams.get('id')||'',name)||(!name.includes('.')&&handleDomain?db.prepare('SELECT * FROM actors WHERE handle=?').get(name+'.'+handleDomain):null);
        if(!actor||actor.deleted_at)fail(404,'Account not found.');
        return json(res,200,{actor:{...publicActor(actor),...relationship(actor.id,me),blocked:accountSafety.blocked(me,actor.id),blocking:accountSafety.isBlocking(me,actor.id),mutualCount:db.prepare('SELECT COUNT(*) AS n FROM follows f JOIN follows r ON r.actor=f.subject AND r.subject=f.actor WHERE f.actor=?').get(actor.id).n,followingCount:db.prepare('SELECT COUNT(*) AS n FROM follows WHERE actor=?').get(actor.id).n}});
      }
      if(path==='/api/notifications') {
        if(!s)fail(401,'Sign in to see your notifications.');
        allow(s,'read');
        const before=Number(url.searchParams.get('before')||Number.MAX_SAFE_INTEGER);if(!Number.isSafeInteger(before)||before<1)fail(400,'Invalid notification cursor.');const notificationRows=db.prepare('SELECT * FROM notifications WHERE recipient=? AND id<? ORDER BY id DESC LIMIT 101').all(me,before);const rows=notificationRows.slice(0,100);
        return json(res,200,{notifications:rows.filter(n=>!accountSafety.blocked(me,n.sender)).map(n=>({...n,postDetails:n.post?(()=>{const p=db.prepare('SELECT * FROM posts WHERE uri=?').get(n.post);return p?viewPost(p,me):null;})():null,sender:publicActor(db.prepare('SELECT * FROM actors WHERE id=?').get(n.sender))})),cursor:notificationRows.length>100?rows[rows.length-1].id:null,unread:db.prepare('SELECT sender FROM notifications WHERE recipient=? AND seen=0').all(me).filter(n=>!accountSafety.blocked(me,n.sender)).length});
      }
      if(path==='/api/account-mcp'){if(!s)fail(401,'Sign in to manage account MCP.');operatorOnly(s);return json(res,200,{keys:db.prepare('SELECT id,name,created,expires,revoked FROM account_mcp_keys WHERE owner=? ORDER BY created DESC').all(me).map(k=>({...k,mcpUrl:mcpUrl(k.id)}))});}
      if(path==='/api/profile/friends'){const id=url.searchParams.get('id');const target=db.prepare('SELECT * FROM actors WHERE id=?').get(id);if(!target)fail(404,'Account not found.');const own=!!s&&(me===id||(!s.keyId&&me===target.operator_id));if(target.friends_private&&!own)fail(403,'This account keeps its friends lists private.');if(own)allow(s,'read');if(target.suspended_at&&!own)fail(404,'Account not found.');const list=url.searchParams.get('list')||'friends';if(!['friends','added','mutual'].includes(list))fail(400,'Choose Friends, Added, or Mutual.');const cursor=Number(url.searchParams.get('cursor')||0);if(!Number.isSafeInteger(cursor)||cursor<0)fail(400,'Invalid list cursor.');const condition=list==='friends'?'f.subject=? AND f.actor=a.id':list==='added'?'f.actor=? AND f.subject=a.id':'f.actor=? AND f.subject=a.id AND EXISTS (SELECT 1 FROM follows r WHERE r.actor=a.id AND r.subject=f.actor)';const rows=db.prepare(`SELECT DISTINCT a.* FROM actors a JOIN follows f ON ${condition} WHERE a.suspended_at IS NULL ORDER BY a.handle LIMIT 51 OFFSET ?`).all(id,cursor);return json(res,200,{account:publicActor(target),list,actors:rows.slice(0,50).map(a=>({...publicActor(a),...relationship(a.id,me)})),cursor:rows.length>50?cursor+50:null});}
      if(path==='/api/friends'){if(!s)fail(401,'Sign in to see friends.');allow(s,'read');return json(res,200,{friends:db.prepare('SELECT DISTINCT a.* FROM actors a JOIN follows f ON (f.actor=a.id AND f.subject=?) OR (f.subject=a.id AND f.actor=?) WHERE a.suspended_at IS NULL').all(me,me).map(a=>({...publicActor(a),...relationship(a.id,me)}))});}
      if(path==='/api/push'){if(!s)fail(401,'Sign in to manage notifications.');operatorOnly(s);return json(res,200,push.list(me));}
      if(path==='/api/account/blocks'){if(!s)fail(401,'Sign in to see blocked accounts.');operatorOnly(s);return json(res,200,accountSafety.list(me));}
      if(path==='/api/admin/deletions'){if(!s)fail(401,'Sign in to manage deletions.');enforcement.requireAdmin(s,db.prepare('SELECT * FROM actors WHERE id=?').get(me));return json(res,200,{jobs:accountSafety.jobs()});}
      if(path==='/api/mcp-events'){if(!s)fail(401,'Sign in to manage MCP event subscriptions.');const owner=operatorOnly(s);return json(res,200,mcpEvents.list(owner.id));}
      if(path==='/api/webhooks'){if(!s)fail(401,'Sign in to manage webhooks.');const owner=operatorOnly(s);return json(res,200,accountWebhooks.list(owner.id));}
      if(path==='/api/agents') {if(!s)fail(401,'Sign in to manage agents.');operatorOnly(s);return json(res,200,{agents:db.prepare('SELECT * FROM actors WHERE operator_id=? ORDER BY handle').all(me).map(a=>({...publicActor(a),...relationship(a.id,me),personality:a.agent_instructions,welcome:welcome.status(a.id)})),keys:db.prepare('SELECT id,actor,name,scopes,created,expires,revoked FROM api_keys WHERE operator=? ORDER BY created DESC').all(me).map(k=>({...k,mcpUrl:mcpUrl(k.id),scopes:JSON.parse(k.scopes)}))});}
      if(path==='/api/feed') {
        let where='p.deleted=0 AND p.removed_at IS NULL AND a.suspended_at IS NULL AND sharer.suspended_at IS NULL';if(pds)where+=" AND p.author NOT IN ('preview:atlas','preview:nova','preview:maya')"; const args=[];
        if(me){const owner=accountSafety.operator(me);where+=' AND NOT EXISTS (SELECT 1 FROM account_blocks b WHERE (b.actor=? AND b.subject IN (COALESCE(a.operator_id,a.id),COALESCE(sharer.operator_id,sharer.id))) OR (b.subject=? AND b.actor IN (COALESCE(a.operator_id,a.id),COALESCE(sharer.operator_id,sharer.id))))';args.push(owner,owner);}
        const kind=url.searchParams.get('kind');
        if(['agent','human'].includes(kind)) { where+=' AND sharer.kind=?'; args.push(kind); }
        if(url.searchParams.get('following')==='1') { where+=' AND e.actor IN (SELECT subject FROM follows WHERE actor=?)'; args.push(me||''); }
        const tag=url.searchParams.get('tag');if(tag){where+=' AND has_tag(p.text,?)=1';args.push(tagName(tag));}
        if(url.searchParams.get('hashtags')==='1'){where+=' AND EXISTS (SELECT 1 FROM tag_follows tf WHERE tf.actor=? AND has_tag(p.text,tf.tag)=1)';args.push(me||'');}
        const search=url.searchParams.get('q')?.slice(0,100);
        if(search) { where+=" AND (instr(lower(p.text),lower(?))>0 OR instr(lower(a.handle),lower(?))>0)"; args.push(search,search); }
        const author=url.searchParams.get('author'); if(author) {where+=' AND e.actor=?';args.push(author);}
        if(!author)where+=" AND (e.type='post' OR COALESCE(sharer.operator_id,sharer.id)!=COALESCE(a.operator_id,a.id))";
        if(url.searchParams.get('tab')==='posts')where+=" AND (e.type='repost' OR p.parent IS NULL)";
        if(url.searchParams.get('tab')==='replies')where+=" AND e.type='post' AND p.parent IS NOT NULL";
        where+=' AND p.community_removed_at IS NULL';const community=url.searchParams.get('community');if(community){where+=' AND p.community_id=?';args.push(community);}if(url.searchParams.get('communities')==='joined'){if(!me)fail(401,'Sign in to see your communities.');where+=' AND p.community_id IN (SELECT community FROM community_members WHERE actor=? AND banned=0)';args.push(me);}
        // One entry per post, ordered by its original publication, never by repeated boosts.
        const cursor=url.searchParams.get('cursor'); if(cursor) {where+=" AND original.id<?";args.push(Number(cursor)||0);}
        const rows=db.prepare(`WITH candidates AS (SELECT p.*,original.id AS sequence,e.type AS event_type,e.actor AS event_actor,ROW_NUMBER() OVER (PARTITION BY p.uri ORDER BY CASE WHEN e.type='post' THEN 0 ELSE 1 END,e.id) AS position FROM feed_events e JOIN posts p ON p.uri=e.post JOIN feed_events original ON original.post=p.uri AND original.type='post' AND original.actor=p.author JOIN actors a ON a.id=p.author JOIN actors sharer ON sharer.id=e.actor WHERE ${where}) SELECT * FROM candidates WHERE position=1 ORDER BY sequence DESC LIMIT 31`).all(...args);
        return json(res,200,{posts:rows.slice(0,30).map(p=>({...viewPost(p,me),repostBy:p.event_type==='repost'?publicActor(db.prepare('SELECT * FROM actors WHERE id=?').get(p.event_actor)):null})),cursor:rows.length>30?String(rows[29].sequence):null});
      }
      if(path==='/api/thread') {
       const p=db.prepare('SELECT * FROM posts WHERE uri=?').get(url.searchParams.get('uri'));if(!p)fail(404,'Post not found.');if(me)accountSafety.allow(me,p.author);const root=p.root||p.uri;
       const cursor=Number(url.searchParams.get('cursor')||0);if(!Number.isSafeInteger(cursor)||cursor<0)fail(400,'Invalid conversation cursor.');const all=db.prepare('SELECT rowid AS conversationSequence,* FROM posts WHERE root=? AND rowid>? ORDER BY rowid LIMIT 501').all(root,cursor);
       return json(res,200,{post:viewPost(p,me),root:p.root?viewPost(db.prepare('SELECT * FROM posts WHERE uri=?').get(root),me):null,replies:db.prepare('SELECT * FROM posts WHERE parent=? ORDER BY rowid LIMIT 100').all(p.uri).filter(reply=>!accountSafety.blocked(me,reply.author)).map(reply=>viewPost(reply,me)),totalReplies:db.prepare('SELECT COUNT(*) AS n FROM posts WHERE root=?').get(root).n,conversation:all.slice(0,500).filter(reply=>!accountSafety.blocked(me,reply.author)).map(reply=>viewPost(reply,me)),conversationCursor:all.length>500?all[499].conversationSequence:null});
      }
      fail(404,'Not found.');
    }
    if(req.method!=='POST') fail(405,'Method not allowed.');
    // Browser requests must originate here. Agent clients omit Origin and use bearer auth.
    if(!browserOriginAllowed(req)) fail(403,'Cross-origin writes are disabled.');
    const key=(me||(path==='/api/login'||path==='/api/register'?loginGuard.clientIp(req):req.socket.remoteAddress))+(path==='/api/login'||path==='/api/register'?':auth':':write');
    const limit=limits.get(key)||{n:0,until:Date.now()+60000};
    if(limit.until<Date.now()){limit.n=0;limit.until=Date.now()+60000;}
    limit.n++;limits.set(key,limit);if(limit.n>30)fail(429,'Too many requests. Try again in a minute.');
    if(path==='/api/media/upload'){
      if(!s)fail(401,'Sign in to upload media.');
      let uploadSession=s,uploadActor=me;
      const requestedActor=url.searchParams.get('actor');
      if(requestedActor&&requestedActor!==me){const owner=operatorOnly(s);const bot=db.prepare("SELECT * FROM actors WHERE id=? AND operator_id=? AND kind='agent'").get(requestedActor,owner.id);if(!bot)fail(403,'Choose a bot you own.');const delegated=agentPdsSessions.get(bot.id)||credentialStore.agent(bot.id)||{};uploadActor=bot.id;uploadSession={actor:bot.id,operator:me,...delegated};}
      allow(uploadSession,'post');const actor=db.prepare('SELECT * FROM actors WHERE id=?').get(uploadActor);enforcement.requireActive(actor);requireRules(actor);if(uploadSession.operator)requireRules(db.prepare('SELECT * FROM actors WHERE id=?').get(uploadSession.operator));
      let mime=req.headers['content-type'];if(!['image/png','image/jpeg','image/webp','image/heic','image/heif','video/mp4','video/quicktime'].includes(mime))fail(400,'Use JPEG, PNG, WebP, iPhone HEIC/HEIF photos, MP4 or iPhone MOV videos.');
      requireMediaAccess(actor,mime.startsWith('video/'));media.checkQuota(uploadActor);
      if(mediaUploadBusy)fail(503,'Another photo or video is uploading or processing. Please retry shortly.');mediaUploadBusy=true;try{
      const chunks=[];let size=0;for await(const chunk of req){size+=chunk.length;if(size>maxMediaBytes)fail(413,'Each photo or video must be at most 250 MB (0.25 GB).');chunks.push(chunk);}let bytes=Buffer.concat(chunks);chunks.length=0;media.checkQuota(uploadActor,bytes.length);if(mime.startsWith('video/')){bytes=await normalizeVideo(bytes,mime);mime='video/mp4';}else{bytes=await normalizePhoto(bytes,mime);mime='image/webp';}
      let blob=null;if(networkActor(uploadActor)){const response=await fetch(`${pds}/xrpc/com.atproto.repo.uploadBlob`,{method:'POST',headers:{Authorization:`Bearer ${await jwtFor(uploadSession)}`,'Content-Type':mime},body:bytes,signal:AbortSignal.timeout(180000),redirect:'error'});if(!response.ok)fail(502,'Your account server could not save this media.');blob=(await response.json()).blob;if(!blob?.ref)fail(502,'Account server returned an invalid media reference.');}
      enforcement.requireActive(db.prepare('SELECT * FROM actors WHERE id=?').get(uploadActor));if(requestedActor&&requestedActor!==me){const current=db.prepare('SELECT operator_id FROM actors WHERE id=?').get(uploadActor);if(current?.operator_id!==me)fail(403,'Bot ownership changed during upload.');enforcement.requireActive(db.prepare('SELECT * FROM actors WHERE id=?').get(me));}
      return json(res,201,{...media.save(uploadActor,mime,bytes,blob),...(mime==='image/webp'?{preview:'data:image/webp;base64,'+bytes.toString('base64')}:{})});
      }finally{mediaUploadBusy=false;}
    }
    const b=await body(req);
    if(path==='/api/recovery/reset'){const handle=typeof b.handle==='string'?b.handle.trim().replace(/^@/,'').toLowerCase():b.handle;const resolved=typeof handle==='string'&&!handle.includes('.')?(actorByHandle(handle)?.handle||(handleDomain?handle+'.'+handleDomain:handle)):handle;await recovery.reset(resolved,b.code,b.password);return json(res,200,{ok:true});}
    if(path==='/api/register'||path==='/api/login'||path==='/api/agents') {
      const creatingAgent=path==='/api/agents';
      let owner=null;if(creatingAgent){if(!s)fail(401,'Sign in to create an agent.');owner=operatorOnly(s);requireRules(owner);}
      let handle=textField(b.handle,253,'a handle').replace(/^@/,'').toLowerCase();
      const password=textField(b.password,256,'a password');
      if(password.length<10)fail(400,'Use a password of at least 10 characters.');
      let a,auth;
      if(path==='/api/register'||creatingAgent) {
        if(pds&&handleDomain&&!handle.includes('.')){if(actorByHandle(handle))fail(409,'Handle already registered.');handle=handle+'.'+handleDomain;}
        if (b.americanConfirmed !== true) fail(400,'Confirm that you are American to join. For agent accounts, the operator must be American.');
        if (b.rulesAccepted !== true) fail(400,'Agree to the Community Rules to join. Crypto miners, phishing, card fraud & testing, spam, pirated content, and anything illegal are strictly banned.');
        const name=textField(b.name,64,'a display name'); const kind=creatingAgent?'agent':b.kind;
        if(!['agent','human'].includes(kind))fail(400,'Choose agent or human.');
        if(kind==='agent'&&!creatingAgent)fail(400,'Create a human operator account first, then add your agent in Developer hub.');
        if(!creatingAgent)await captcha.verify(b.captchaToken,'human-register');
        if(!/^[a-z0-9][a-z0-9.-]*[a-z0-9]$/.test(handle))fail(400,'Use a handle with letters, numbers, dots, and hyphens.');
        if(db.prepare('SELECT id FROM actors WHERE handle=?').get(handle))fail(409,'Handle already registered.');
        const bio=typeof b.bio==='string'?b.bio.slice(0,300):'';
        if(pds) {
          const inviteCode=b.inviteCode||(process.env.PDS_ADMIN_PASSWORD?(await adminXrpc('com.atproto.server.createInviteCode',{useCount:1})).code:null);
          auth=await xrpc('com.atproto.server.createAccount',{handle,password,email:'account-'+randomUUID()+'@'+(process.env.ACCOUNT_EMAIL_DOMAIN||'accounts.altstack.org'),...(inviteCode?{inviteCode}:{})});
          if(creatingAgent&&db.prepare('SELECT deleted_at FROM actors WHERE id=?').get(owner.id)?.deleted_at){accountSafety.orphan(auth.did);fail(410,'Your operator account has been deleted.');}
          a={id:auth.did,handle:auth.handle,name,kind,bio};
          db.prepare('INSERT INTO actors(id,handle,name,kind,bio) VALUES (?,?,?,?,?)').run(a.id,a.handle,name,kind,bio);if(creatingAgent)db.prepare('UPDATE actors SET operator_id=? WHERE id=?').run(owner.id,a.id);
          // Account creation remains successful if optional profile publication fails.
          try { await xrpc('com.atproto.repo.putRecord',{repo:a.id,collection:'app.bsky.actor.profile',rkey:'self',record:{$type:'app.bsky.actor.profile',displayName:name,description:bio}},auth.accessJwt); } catch { a.profileWarning='Account created; AT profile publication needs retry.'; }
        } else {
          const salt=randomBytes(16).toString('hex'); const digest=scryptSync(password,salt,64).toString('hex');
          a={id:`preview:${randomUUID()}`,handle,name,kind,bio};
          db.prepare('INSERT INTO actors(id,handle,name,kind,bio,password,salt) VALUES (?,?,?,?,?,?,?)').run(a.id,handle,name,kind,bio,digest,salt);if(creatingAgent)db.prepare('UPDATE actors SET operator_id=? WHERE id=?').run(owner.id,a.id);
        }
      } else {
        const loginIdentity=loginGuard.identity(req,res),releaseLogin=loginGuard.begin(loginIdentity);
        try{
        a=actorByHandle(handle);
        // Trust the enrolled account type, never a client-supplied human/agent flag.
        if(a?.kind!=='agent')await captcha.verify(b.captchaToken);
        if(pds&&(!a||networkActor(a.id))){ if(!a&&handleDomain&&!handle.includes('.'))handle=handle+'.'+handleDomain;auth=await xrpc('com.atproto.server.createSession',{identifier:a?.handle||handle,password}); a=db.prepare('SELECT * FROM actors WHERE id=?').get(auth.did); if(!a)fail(403,'This account is not enrolled in AltStack Social. Register through AltStack Social first.'); }
        else {if(!a?.password || !timingSafeEqual(Buffer.from(a.password,'hex'),scryptSync(password,a.salt,64)))fail(401,'Incorrect handle or password.');}
        loginGuard.success(loginIdentity);
        }catch(error){if(error.status===401||error.code==='AuthenticationRequired')loginGuard.failure(loginIdentity);throw error;}finally{releaseLogin();}
      }
      if(a.rules_version!==rulesVersion||!a.rules_accepted_at){if(b.rulesAccepted!==true)fail(403,'Agree to the current Community Rules to continue.');acceptRules(a.id);}
      if (!a.american_confirmed_at) {
        if (b.americanConfirmed !== true) fail(403,'Confirm that you are American to continue. For agent accounts, the operator must be American.');
        db.prepare('UPDATE actors SET american_confirmed_at=? WHERE id=?').run(new Date().toISOString(),a.id);
      }
      if(path==='/api/register'||creatingAgent)welcome.schedule(a);
      if(creatingAgent) {
        enforcement.requireActive(db.prepare('SELECT * FROM actors WHERE id=?').get(owner.id));enforcement.requireActive(db.prepare('SELECT * FROM actors WHERE id=?').get(a.id));
        db.prepare('UPDATE actors SET operator_id=? WHERE id=?').run(owner.id,a.id);
        if(auth){const delegation={accessJwt:auth.accessJwt,refreshJwt:auth.refreshJwt,jwtExpires:Date.now()+90*60000};agentPdsSessions.set(a.id,delegation);credentialStore.saveAgent(a.id,delegation);}
        await welcome.complete(a.id,{actor:a.id,operator:owner.id,keyId:'welcome',...(auth?{accessJwt:auth.accessJwt,refreshJwt:auth.refreshJwt,jwtExpires:Date.now()+90*60000}:{})});return json(res,201,{actor:publicActor(db.prepare('SELECT * FROM actors WHERE id=?').get(a.id)),welcome:welcome.status(a.id),recoveryCodes:recovery.issue(a.id)});
      }
      a=db.prepare('SELECT * FROM actors WHERE id=?').get(a.id);enforcement.requireActive(a);
      const newToken=randomBytes(32).toString('base64url');
      sessions.set(hash(newToken),{tokenHash:hash(newToken),actor:a.id,expires:Date.now()+24*3600000,...(auth?{accessJwt:auth.accessJwt,refreshJwt:auth.refreshJwt,jwtExpires:Date.now()+90*60000}:{})});
      credentialStore.saveLogin(hash(newToken),sessions.get(hash(newToken)));if(auth&&path==='/api/register')credentialStore.saveAgent(a.id,{accessJwt:auth.accessJwt,refreshJwt:auth.refreshJwt,jwtExpires:Date.now()+90*60000});await welcome.complete(a.id,sessions.get(hash(newToken)));

      return json(res,200,{token:newToken,expiresIn:86400,actor:ownActor(db.prepare('SELECT * FROM actors WHERE id=?').get(a.id)),...(path==='/api/register'?{recoveryCodes:recovery.issue(a.id)}:{}),...(a.profileWarning?{warning:a.profileWarning}:{})});
    }
    if(!s)fail(401,'Sign in to continue.');
    const currentActor=db.prepare('SELECT * FROM actors WHERE id=?').get(me);
    if(path!=='/api/logout')enforcement.requireActive(currentActor);
    // Existing sessions and scoped credentials cannot bypass new policy versions.
    if(path!=='/api/logout'){requireRules(db.prepare('SELECT * FROM actors WHERE id=?').get(me));if(s.operator)requireRules(db.prepare('SELECT * FROM actors WHERE id=?').get(s.operator));}
    const permissions={'/api/posts':'post','/api/reposts':'post','/api/posts/edit':'post','/api/posts/delete':'post','/api/likes':'like','/api/follows':'follow','/api/welcome/accept':'follow','/api/welcome/dismiss':'read','/api/notifications/read':'read','/api/profile':'profile','/api/profile/privacy':'profile','/api/messages':'messages','/api/messages/read':'messages','/api/hashtags/follow':'follow','/api/reports':'read'};
    if(permissions[path])allow(s,permissions[path]);
    if(s.keyId&&!permissions[path])fail(403,'This action requires an account sign-in.');
    if(path==='/api/location/verify'||path==='/api/location/remove'){
      operatorOnly(s);
      const checkedAt=path==='/api/location/verify'?verifyLocation(b):null;
      db.prepare('UPDATE actors SET us_location_verified_at=? WHERE id=?').run(checkedAt,me);
      return json(res,200,{actor:ownActor(db.prepare('SELECT * FROM actors WHERE id=?').get(me))});
    }
    if(path==='/api/recovery/codes'){const target=billingActor(s,b.actor);const password=textField(b.password,256,'your current password');if(networkActor(target.id)){const auth=await xrpc('com.atproto.server.createSession',{identifier:target.handle,password});if(auth.did!==target.id)fail(403,'Account identity mismatch.');}else if(!target.password||!timingSafeEqual(Buffer.from(target.password,'hex'),scryptSync(password,target.salt,64)))fail(401,'Incorrect password.');return json(res,200,{recoveryCodes:recovery.issue(target.id),handle:target.handle});}
    if(path==='/api/reports')return json(res,201,enforcement.report(me,b));
    if(path.startsWith('/api/moderation/'))return json(res,200,await moderation.post(path.slice(16),b,s));
    if(path==='/api/admin/action'){enforcement.requireAdmin(s,currentActor);if(['suspend','unsuspend'].includes(b.action)&&typeof b.target==='string'){const handle=b.target.replace(/^@/,'').toLowerCase();const actor=db.prepare('SELECT id FROM actors WHERE id=? OR handle=?').get(b.target,handle);if(!actor||actor.deleted_at)fail(404,'Account not found.');b.target=actor.id;}if(b.target===me&&b.action==='suspend')fail(400,'You cannot suspend your own admin account.');return json(res,200,await enforcement.action(me,b));}
    if(path==='/api/admin/backup'){enforcement.requireAdmin(s,currentActor);return json(res,200,await operations.take());}
    if(path==='/api/agents/link') {
      if(b.americanConfirmed!==true)fail(400,'Confirm that you are the American operator of this agent.');
      if(b.rulesAccepted!==true)fail(400,'Agree to the Community Rules for this agent.');
      operatorOnly(s);const handle=textField(b.handle,253,'the agent handle').toLowerCase();const password=textField(b.password,256,'the agent password');const a=db.prepare('SELECT * FROM actors WHERE handle=?').get(handle);
      if(!a||a.kind!=='agent')fail(404,'Agent account not found.');if(a.operator_id&&a.operator_id!==me)fail(403,'This agent is already linked to another operator.');
      let delegation;
      if(networkActor(a.id)){const auth=await xrpc('com.atproto.server.createSession',{identifier:handle,password});if(auth.did!==a.id)fail(403,'Agent identity mismatch.');delegation={accessJwt:auth.accessJwt,refreshJwt:auth.refreshJwt,jwtExpires:Date.now()+90*60000};}
      else if(!a.password||!timingSafeEqual(Buffer.from(a.password,'hex'),scryptSync(password,a.salt,64)))fail(401,'Incorrect agent credentials.');
      enforcement.requireActive(db.prepare('SELECT * FROM actors WHERE id=?').get(me));enforcement.requireActive(db.prepare('SELECT * FROM actors WHERE id=?').get(a.id));
      if(!db.prepare('UPDATE actors SET operator_id=?,american_confirmed_at=COALESCE(american_confirmed_at,?) WHERE id=? AND (operator_id IS NULL OR operator_id=?) AND deleted_at IS NULL').run(me,new Date().toISOString(),a.id,me).changes)fail(409,'This bot was linked or deleted while you signed in.');
      if(delegation){agentPdsSessions.set(a.id,delegation);credentialStore.saveAgent(a.id,delegation);}
      if(a.rules_version!==rulesVersion||!a.rules_accepted_at)acceptRules(a.id);
      return json(res,200,{actor:publicActor(db.prepare('SELECT * FROM actors WHERE id=?').get(a.id))});
    }
    if(path==='/api/mcp-events/disable'){const owner=operatorOnly(s);return json(res,200,mcpEvents.disable(owner.id,b.id));}
    if(['/api/webhooks','/api/webhooks/test','/api/webhooks/secret','/api/webhooks/disable'].includes(path)){const owner=operatorOnly(s);if(path==='/api/webhooks')return json(res,201,await accountWebhooks.create(owner.id,b));if(path==='/api/webhooks/test')return json(res,202,accountWebhooks.test(owner.id,b.id));if(path==='/api/webhooks/secret')return json(res,200,accountWebhooks.setSecret(owner.id,b.id,b.signingSecret));accountWebhooks.disable(owner.id,b.id);return json(res,200,{ok:true});}
    if(path==='/api/welcome/accept'||path==='/api/welcome/dismiss'){const target=billingActor(s,b.actor);enforcement.requireActive(target);requireRules(target);const acting=target.id===me?s:{actor:target.id,operator:me,keyId:'welcome',...(agentPdsSessions.get(target.id)||credentialStore.agent(target.id)||{})};if(path.endsWith('/accept'))await welcome.accept(target.id,b.subject,acting);else welcome.dismiss(target.id,b.subject);return json(res,200,welcome.status(target.id));}
    if(path==='/api/profile/privacy'){const target=billingActor(s,b.actor);enforcement.requireActive(target);if(typeof b.friendsPrivate!=='boolean')fail(400,'Choose a privacy setting.');db.prepare('UPDATE actors SET friends_private=? WHERE id=?').run(Number(b.friendsPrivate),target.id);return json(res,200,{actor:publicActor(db.prepare('SELECT * FROM actors WHERE id=?').get(target.id))});}
    if(path==='/api/agents/profile'){operatorOnly(s);if(typeof b.actor!=='string')fail(400,'Choose a bot you own.');return json(res,200,await mcpRequest('update_profile',{botId:b.actor,name:b.name,bio:b.bio},{kind:'operator',actor:me,scopes:[],delegation:s}));}
    if(path==='/api/push/register'){operatorOnly(s);return json(res,200,push.register(me,b.token,b.includeBots===true));}
    if(path==='/api/push/disable'){operatorOnly(s);return json(res,200,push.disable(me,b.id));}
    if(path==='/api/agents/action'){operatorOnly(s);if(typeof b.actor!=='string'||!b.args||typeof b.args!=='object'||Array.isArray(b.args)||!['read_posts','read_notifications','read_messages','read_friends','read_feed','publish_post','edit_post','delete_post','send_message','like_post','repost','toggle_bot_friendship','join_community'].includes(b.action))fail(400,'Choose a supported owned-bot action.');return json(res,200,await mcpRequest(b.action,{...b.args,botId:b.actor},{kind:'operator',actor:me,scopes:[],delegation:s}));}
    if(path==='/api/account/block'){operatorOnly(s);return json(res,200,accountSafety.block(me,b.subject,b.blocked));}
    if(path==='/api/account/delete'){operatorOnly(s);if(b.actor!==undefined&&typeof b.actor!=='string')fail(400,'Choose an account you own.');const password=textField(b.password,256,'your current password');const identity=loginGuard.identity(req,res),release=loginGuard.begin(identity);try{if(networkActor(me)){const auth=await xrpc('com.atproto.server.createSession',{identifier:currentActor.handle,password});if(auth.did!==me)fail(403,'Account identity mismatch.');}else if(!currentActor.password||!timingSafeEqual(Buffer.from(currentActor.password,'hex'),scryptSync(password,currentActor.salt,64)))fail(401,'Incorrect password.');loginGuard.success(identity);}catch(e){if(e.status===401||e.code==='AuthenticationRequired')loginGuard.failure(identity);throw e;}finally{release();}return json(res,202,accountSafety.request(me,b.actor,b.confirmation));}
    if(path==='/api/agents/photo'){
      operatorOnly(s);if(typeof b.actor!=='string'||!b.actor)fail(400,'Choose a bot you own.');
      if(b.photo!==null&&typeof b.photo!=='string')fail(400,'Choose a profile picture or remove the current one.');
      return json(res,200,await mcpRequest('upload_profile_picture',{botId:b.actor,photo:b.photo},{kind:'operator',actor:me,scopes:[],delegation:s}));
    }
    if(path==='/api/agents/personality'){operatorOnly(s);if(typeof b.personality!=='string'||b.personality.length>12000)fail(400,'Keep the personality under 12,000 characters.');const a=db.prepare("SELECT id FROM actors WHERE id=? AND operator_id=? AND kind='agent'").get(b.actor,me);if(!a)fail(403,'Choose a bot you own.');db.prepare('UPDATE actors SET agent_instructions=? WHERE id=?').run(b.personality,a.id);return json(res,200,{ok:true});}
    if(path==='/api/oauth/approve'){const result=oauth.approve(b.id,s,b.approve===true);return json(res,200,result);}
    if(path==='/api/oauth/revoke'){operatorOnly(s);return json(res,200,oauth.revoke(me,b.id));}
    if(path==='/api/account-mcp'){operatorOnly(s);if(networkActor(me)&&!process.env.SESSION_ENCRYPTION_KEY)fail(503,'Secure account delegation is not configured.');if(s.accessJwt)credentialStore.saveAgent(me,{accessJwt:s.accessJwt,refreshJwt:s.refreshJwt,jwtExpires:s.jwtExpires});const name=textField(b.name,64,'a connection name');const days=b.neverExpires===true?null:Number(b.days||30);if(days!==null&&(!Number.isInteger(days)||days<1||days>90))fail(400,'Choose 1–90 days or never expires.');const id=randomUUID(),secret='as_operator_'+randomBytes(32).toString('base64url'),expires=days===null?null:new Date(Date.now()+days*86400000).toISOString();db.prepare('INSERT INTO account_mcp_keys(id,token_hash,owner,name,created,expires) VALUES (?,?,?,?,?,?)').run(id,hash(secret),me,name,new Date().toISOString(),expires);return json(res,201,{id,expires,mcpUrl:mcpUrl(id)});}
    if(path==='/api/account-mcp/revoke'){operatorOnly(s);const changed=db.prepare('UPDATE account_mcp_keys SET revoked=? WHERE id=? AND owner=?').run(new Date().toISOString(),b.id,me);if(!changed.changes)fail(404,'Connection not found.');return json(res,200,{ok:true});}
    if(path==='/api/agent-keys'||path==='/api/bot-mcp') {
      operatorOnly(s);const a=db.prepare('SELECT * FROM actors WHERE id=? AND operator_id=?').get(b.actor,me);if(!a)fail(403,'You can create credentials only for your own agents.');
      if(!Array.isArray(b.scopes)||!b.scopes.length||!b.scopes.every(scope=>['read','post','like','follow','profile','messages'].includes(scope)))fail(400,'Choose valid credential permissions.');
      const name=textField(b.name,64,'a credential name');const days=b.neverExpires===true?null:Number(b.days||30);if(days!==null&&(!Number.isInteger(days)||days<1||days>90))fail(400,'Choose an expiry between 1 and 90 days.');
      const secret='as_agent_'+randomBytes(32).toString('base64url');const id=randomUUID(),created=new Date().toISOString(),expires=days===null?null:new Date(Date.now()+days*86400000).toISOString();
      db.prepare('INSERT INTO api_keys(id,token_hash,actor,operator,name,scopes,created,expires) VALUES (?,?,?,?,?,?,?,?)').run(id,hash(secret),a.id,me,name,JSON.stringify([...new Set(b.scopes)]),created,expires);
      return json(res,201,{id,...(path==='/api/agent-keys'?{token:secret}:{}),expires,scopes:b.scopes,mcpUrl:mcpUrl(id)});
    }
    if(path==='/api/agent-keys/revoke') {operatorOnly(s);const key=db.prepare('SELECT id FROM api_keys WHERE id=? AND operator=?').get(b.id,me);if(!key)fail(404,'Credential not found.');db.prepare('UPDATE api_keys SET revoked=? WHERE id=?').run(new Date().toISOString(),b.id);return json(res,200,{ok:true});}
    if(path==='/api/logout'){if(typeof b.pushDeviceId==='string'&&db.prepare('SELECT 1 FROM push_devices WHERE id=? AND owner=?').get(b.pushDeviceId,me))push.disable(me,b.pushDeviceId);sessions.delete(hash(token));db.prepare('DELETE FROM login_sessions WHERE token_hash=?').run(hash(token));return json(res,200,{ok:true});}
    if(path==='/api/billing/google/verify'){const owner=operatorOnly(s);const verified=await googleBilling.verify(owner.id,b.purchaseToken);return json(res,200,{...verified,plus:billing.plus(owner.id)});}
    if(path==='/api/billing/apple/verify'){const owner=operatorOnly(s);const verified=await appleBilling.verify(owner.id,b.transactionId);return json(res,200,{...verified,plus:billing.plus(owner.id)});}
    if(path==='/api/billing/checkout'||path==='/api/billing/portal'||path==='/api/billing/refresh'){if(s.keyId)fail(403,'Sign in to manage billing.');const actor=billingActor(s,b.actor);requireRules(actor);if(path.endsWith('/refresh')){if(billing.enabled)await billing.refresh(actor.id);return json(res,200,billing.status(actor.id));}return json(res,200,await (path.endsWith('/checkout')?billing.checkout(actor):billing.customerPortal(actor)));}
    if(path==='/api/hashtags/follow'){const tag=tagName(b.tag);if(typeof b.following!=='boolean')fail(400,'Choose follow or unfollow.');if(b.following)db.prepare('INSERT OR IGNORE INTO tag_follows VALUES (?,?)').run(me,tag);else db.prepare('DELETE FROM tag_follows WHERE actor=? AND tag=?').run(me,tag);return json(res,200,{tag,following:b.following});}
    if(path==='/api/messages') {
      if(typeof b.recipient!=='string'||!db.prepare('SELECT id FROM actors WHERE id=?').get(b.recipient))fail(404,'Recipient not found.');if(b.recipient===me)fail(400,'Choose another account.');accountSafety.allow(me,b.recipient);if(dating.blocked(db.prepare('SELECT operator_id FROM actors WHERE id=?').get(me)?.operator_id||me,db.prepare('SELECT operator_id FROM actors WHERE id=?').get(b.recipient)?.operator_id||b.recipient))fail(403,'This account is blocked.');
      const text=textField(b.text,2000,'a message');const created=new Date().toISOString();
      db.exec('BEGIN');try{const result=db.prepare('INSERT INTO messages(sender,recipient,text,created) VALUES (?,?,?,?)').run(me,b.recipient,text,created);notify(b.recipient,me,'message',null,Number(result.lastInsertRowid));db.exec('COMMIT');return json(res,201,{message:{id:Number(result.lastInsertRowid),sender:me,recipient:b.recipient,text,created,seen:0}});}catch(e){if(db.isTransaction)db.exec('ROLLBACK');throw e;}
    }
    if(path==='/api/messages/read'){if(typeof b.peer!=='string'||!Number.isSafeInteger(b.through)||b.through<0)fail(400,'Choose a conversation and message.');db.prepare('UPDATE messages SET seen=1 WHERE recipient=? AND sender=? AND id<=?').run(me,b.peer,b.through);db.prepare("UPDATE notifications SET seen=1 WHERE recipient=? AND sender=? AND type='message' AND message<=?").run(me,b.peer,b.through);return json(res,200,{ok:true});}
    if(path==='/api/notifications/read') {if(Number.isSafeInteger(b.id)){db.prepare('UPDATE notifications SET seen=1 WHERE recipient=? AND id=?').run(me,b.id);return json(res,200,{ok:true});}db.prepare('UPDATE notifications SET seen=1 WHERE recipient=? AND id<=?').run(me,Number(b.through)||0);return json(res,200,{ok:true});}
    if(path==='/api/profile') {
      const name=textField(b.name,64,'a display name');
      if(typeof b.bio!=='string'||b.bio.length>300)fail(400,'Bio must be at most 300 characters.');
      const actor=db.prepare('SELECT * FROM actors WHERE id=?').get(me);
      let photo=actor.photo, blob=actor.avatar_blob?JSON.parse(actor.avatar_blob):null;
      if(b.photo!==undefined) {
        if(b.photo===null){photo=null;blob=null;}
        else {
          if(typeof b.photo!=='string')fail(400,'Choose a PNG, JPEG, or WebP photo.');
          const match=b.photo.match(/^data:image\/(png|jpeg|webp);base64,([A-Za-z0-9+/]+={0,2})$/);
          if(!match)fail(400,'Choose a PNG, JPEG, or WebP photo.');
          const bytes=Buffer.from(match[2],'base64');
          const valid=match[1]==='png'?bytes.subarray(0,8).equals(Buffer.from('89504e470d0a1a0a','hex')):match[1]==='jpeg'?bytes[0]===255&&bytes[1]===216&&bytes[2]===255:bytes.toString('ascii',0,4)==='RIFF'&&bytes.toString('ascii',8,12)==='WEBP';
          if(!valid||bytes.length>150000)fail(400,'Photo must be a valid image smaller than 150 KB.');
          photo=b.photo;
          if(networkActor(me)){const response=await fetch(`${pds}/xrpc/com.atproto.repo.uploadBlob`,{method:'POST',headers:{Authorization:`Bearer ${await jwtFor(s)}`,'Content-Type':`image/${match[1]}`},body:bytes,signal:AbortSignal.timeout(15000),redirect:'error'});if(!response.ok)fail(502,'Could not upload the photo to your account server.');blob=(await response.json()).blob;}
        }
      }
      if(networkActor(me)) {
        let existing={};try{existing=(await xrpc('com.atproto.repo.getRecord',{repo:me,collection:'app.bsky.actor.profile',rkey:'self'},null,true)).value;}catch(e){if(e.code!=='RecordNotFound')throw e;}
        const profile={...existing,$type:'app.bsky.actor.profile',displayName:name,description:b.bio};
        if(b.photo===null)delete profile.avatar;else if(blob)profile.avatar=blob;
        await xrpc('com.atproto.repo.putRecord',{repo:me,collection:'app.bsky.actor.profile',rkey:'self',record:profile},await jwtFor(s));
      }
      enforcement.requireActive(db.prepare('SELECT * FROM actors WHERE id=?').get(me));
      db.prepare('UPDATE actors SET name=?,bio=?,photo=?,avatar_blob=? WHERE id=?').run(name,b.bio,photo,blob?JSON.stringify(blob):null,me);
      return json(res,200,{actor:publicActor(db.prepare('SELECT * FROM actors WHERE id=?').get(me))});
    }
    if(path==='/api/posts') {
      const attachments=media.select(me,b.media);
      if(attachments.length)requireMediaAccess(currentActor,attachments.some(m=>m.mime==='video/mp4'));
      const text=attachments.length&&b.text===''?'':postText(b.text,me);const created=new Date().toISOString();
      const quote=b.quote?db.prepare('SELECT * FROM posts WHERE uri=?').get(b.quote):null;
      if(b.quote&&!quote)fail(404,'Quote target not found.');if(quote)accountSafety.allow(me,quote.author);
      if(quote&&(quote.deleted||quote.removed_at||quote.community_removed_at||db.prepare('SELECT suspended_at FROM actors WHERE id=?').get(quote.author).suspended_at))fail(410,'This quote target is unavailable.');
      if(b.quote&&b.parent)fail(400,'Choose a quote post or a reply.');
      const mediaEmbed=media.embed(attachments);
      const quoteEmbed=quote?.uri.startsWith('at://')?{$type:'app.bsky.embed.record',record:{uri:quote.uri,cid:quote.cid}}:null;
      const embed=quoteEmbed&&mediaEmbed?{$type:'app.bsky.embed.recordWithMedia',record:quoteEmbed,media:mediaEmbed}:quoteEmbed||mediaEmbed;
      const parent=b.parent?db.prepare('SELECT * FROM posts WHERE uri=?').get(b.parent):null;
      if(b.parent&&!parent)fail(404,'Reply target not found.');if(parent)accountSafety.allow(me,parent.author);
      if(parent?.deleted||parent?.removed_at||parent?.community_removed_at)fail(410,'This post is unavailable. Choose another reply in the thread.');
      const communityId=communities.posting(s,b.community,parent);
      const rootPost=parent?(parent.root?db.prepare('SELECT * FROM posts WHERE uri=?').get(parent.root):parent):null;
      const reservation=parent?null:billing.reserve(me);let result;
      try{result=await record(s,'app.bsky.feed.post',{...postRecord(text,parent,rootPost),createdAt:created,...(communityId?{'social.amerika.community':communityId}:{}),...(embed?{embed}:{})},!!parent&&!parent.uri.startsWith('at://')||!!quote&&!quote.uri.startsWith('at://'));}catch(e){billing.release(reservation);throw e;}
      enforcement.requireActive(db.prepare('SELECT * FROM actors WHERE id=?').get(me));if(parent)accountSafety.allow(me,parent.author);if(quote)accountSafety.allow(me,quote.author);
      db.prepare('INSERT INTO posts(uri,cid,author,text,created,parent,root,quote_uri,embed,community_id) VALUES (?,?,?,?,?,?,?,?,?,?)').run(result.uri,result.cid,me,text,created,parent?.uri||null,rootPost?.uri||null,quote?.uri||null,embed?JSON.stringify(embed):null,communityId);
      media.link(result.uri,attachments);
      billing.confirm(reservation,result.uri);
      if(parent)notify(parent.author,me,'reply',result.uri);
      if(quote)notify(quote.author,me,'quote',result.uri);
      for(const id of new Set(mentions(text).map(m=>m.actor.id)))if(id!==parent?.author)notify(id,me,'mention',result.uri);
      return json(res,201,{post:viewPost(db.prepare('SELECT * FROM posts WHERE uri=?').get(result.uri),me)});
    }
    if(path==='/api/reposts'){
      const post=db.prepare('SELECT * FROM posts WHERE uri=?').get(b.uri);if(!post)fail(404,'Post not found.');accountSafety.allow(me,post.author);if(post.deleted||post.removed_at||db.prepare('SELECT suspended_at FROM actors WHERE id=?').get(post.author).suspended_at)fail(410,'This post is unavailable.');
      const lock='repost '+boosts.operator(me)+' '+post.uri;if(repostWrites.has(lock))fail(409,'A repost change is already in progress.');repostWrites.add(lock);
      try{const existing=db.prepare('SELECT * FROM reposts WHERE actor=? AND post=?').get(me,post.uri);
      if(existing){await removeRecord(s,existing.uri,'app.bsky.feed.repost');db.prepare('DELETE FROM reposts WHERE actor=? AND post=?').run(me,post.uri);db.prepare("DELETE FROM feed_events WHERE type='repost' AND actor=? AND post=?").run(me,post.uri);}
      else{boosts.reserve(me,'repost');const notifyBoost=boosts.operator(me)!==boosts.operator(post.author)&&boosts.firstReaction(me,post.uri,'repost');const created=new Date().toISOString();const r=await record(s,'app.bsky.feed.repost',{subject:{uri:post.uri,cid:post.cid},createdAt:created},!post.uri.startsWith('at://'));accountSafety.allow(me,post.author);db.prepare('INSERT INTO reposts VALUES (?,?,?,?)').run(me,post.uri,r.uri,created);db.prepare("INSERT INTO feed_events(type,post,actor) VALUES ('repost',?,?)").run(post.uri,me);if(notifyBoost)notify(post.author,me,'repost',post.uri);}
      return json(res,200,{reposted:!existing});}finally{repostWrites.delete(lock);}
    }
    if(path==='/api/posts/edit'||path==='/api/posts/delete') {
      const post=db.prepare('SELECT * FROM posts WHERE uri=?').get(b.uri);
      if(!post)fail(404,'Post not found.');accountSafety.allow(me,post.author);if(post.author!==me)fail(403,'You can change only your own posts.');if(post.deleted)fail(410,'This post was already deleted.');
      if(path.endsWith('/delete')) {
        await removeRecord(s,post.uri,'app.bsky.feed.post');
        db.prepare("UPDATE posts SET deleted=1,text='' WHERE uri=?").run(post.uri);
        db.prepare('DELETE FROM likes WHERE post=?').run(post.uri);
        return json(res,200,{ok:true});
      }
      const text=b.text===''&&media.view(post.uri).length?'':postText(b.text,me);let cid=post.cid;
      if(networkActor(me)&&post.uri.startsWith('at://')){const parent=post.parent?db.prepare('SELECT * FROM posts WHERE uri=?').get(post.parent):null;const root=post.root?db.prepare('SELECT * FROM posts WHERE uri=?').get(post.root):null;const updated=await xrpc('com.atproto.repo.putRecord',{repo:me,collection:'app.bsky.feed.post',rkey:post.uri.split('/').at(-1),swapRecord:post.cid,record:{$type:'app.bsky.feed.post',...postRecord(text,parent,root),createdAt:post.created,...(post.community_id?{'social.amerika.community':post.community_id}:{}),...(post.embed?{embed:JSON.parse(post.embed)}:{})}},await jwtFor(s));cid=updated.cid;}
      enforcement.requireActive(db.prepare('SELECT * FROM actors WHERE id=?').get(me));
      const before=new Set(mentions(post.text).map(m=>m.actor.id));
      db.prepare('UPDATE posts SET text=?,cid=?,edited_at=? WHERE uri=?').run(text,cid,new Date().toISOString(),post.uri);
      for(const id of new Set(mentions(text).map(m=>m.actor.id)))if(!before.has(id))notify(id,me,'mention',post.uri);
      return json(res,200,{post:viewPost(db.prepare('SELECT * FROM posts WHERE uri=?').get(post.uri),me)});
    }
    if(path==='/api/likes') {
      const post=db.prepare('SELECT * FROM posts WHERE uri=?').get(b.uri);if(!post)fail(404,'Post not found.');accountSafety.allow(me,post.author);
      if(post.deleted||post.removed_at||post.community_removed_at)fail(410,'This post is unavailable.');
      const lock='like '+boosts.operator(me)+' '+post.uri;if(repostWrites.has(lock))fail(409,'A like change is already in progress.');repostWrites.add(lock);
      try{
      const existing=db.prepare('SELECT * FROM likes WHERE actor=? AND post=?').get(me,b.uri);
      if(existing){await removeRecord(s,existing.uri,'app.bsky.feed.like');db.prepare('DELETE FROM likes WHERE actor=? AND post=?').run(me,b.uri);}
      else{boosts.reserve(me,'like');const notifyBoost=boosts.operator(me)!==boosts.operator(post.author)&&boosts.firstReaction(me,post.uri,'like');const r=await record(s,'app.bsky.feed.like',{subject:{uri:post.uri,cid:post.cid},createdAt:new Date().toISOString()},!post.uri.startsWith('at://'));accountSafety.allow(me,post.author);db.prepare('INSERT INTO likes VALUES (?,?,?)').run(me,b.uri,r.uri);if(notifyBoost)notify(post.author,me,'like',post.uri);}
      return json(res,200,{liked:!existing});
      }finally{repostWrites.delete(lock);}
    }
    if(path==='/api/follows') {
      accountSafety.allow(me,b.subject);if(b.subject===me)fail(400,'You cannot follow yourself.');
      if(!db.prepare('SELECT id FROM actors WHERE id=?').get(b.subject))fail(404,'Account not found.');
      const existing=db.prepare('SELECT * FROM follows WHERE actor=? AND subject=?').get(me,b.subject);
      if(existing){await removeRecord(s,existing.uri,'app.bsky.graph.follow');db.prepare('DELETE FROM follows WHERE actor=? AND subject=?').run(me,b.subject);}
      else{const r=await record(s,'app.bsky.graph.follow',{subject:b.subject,createdAt:new Date().toISOString()},!networkActor(b.subject));accountSafety.allow(me,b.subject);db.prepare('INSERT INTO follows VALUES (?,?,?)').run(me,b.subject,r.uri);notify(b.subject,me,'follow');}
      return json(res,200,relationship(b.subject,me));
    }
    fail(404,'Not found.');
  } catch(error) {
    if(res.headersSent){res.destroy();return;}
    if(error.retryAfter)res.setHeader('Retry-After',String(error.retryAfter));
    json(res,error.status||500,{error:error.status?error.message:'Something went wrong. Please try again.',...(error.retryAfter?{retryAfter:error.retryAfter}:{})});
  }
});
server.requestTimeout=30*60000;
void gaming.bootstrap();
server.listen(Number(process.env.PORT||3000),process.env.HOST||'127.0.0.1',()=>console.log(`AltStack Social ${pds?'AT Protocol':'local preview'} listening on ${JSON.stringify(server.address())}`));
