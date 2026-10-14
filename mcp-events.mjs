import {randomBytes,createHash,createCipheriv,createDecipheriv,timingSafeEqual} from 'node:crypto';
import {webhookDestination,webhookRequest,standardWebhookKey} from './webhooks.mjs';

const types=['reply','mention','quote','repost','like','follow'];
const invalid=message=>{throw Object.assign(Error(message),{rpcCode:-32602,status:400});};
const denied=()=>{throw Object.assign(Error('This connection cannot monitor that account or event.'),{rpcCode:-32024,status:403});};
const string={type:'string',minLength:1};
export function createMcpEvents(db,{origin,activeGrant,key=process.env.SESSION_ENCRYPTION_KEY,testing=process.env.ALLOW_TEST_WEBHOOKS==='1',now=()=>Date.now()}={}){
 const configured=typeof key==='string'&&/^[a-f0-9]{64}$/i.test(key);let busy=false;
 const checking=new Set(),rates=new Map();
 db.exec(`CREATE TABLE IF NOT EXISTS mcp_event_subscriptions(id TEXT PRIMARY KEY,owner TEXT NOT NULL,actor TEXT NOT NULL,connection TEXT NOT NULL,grant_id TEXT NOT NULL,name TEXT NOT NULL,args TEXT NOT NULL,url TEXT NOT NULL,secret TEXT NOT NULL,previous_secret TEXT,previous_until INTEGER,expires INTEGER NOT NULL,enabled INTEGER NOT NULL,created INTEGER NOT NULL);
 CREATE INDEX IF NOT EXISTS mcp_event_owner ON mcp_event_subscriptions(owner,enabled);
 CREATE TABLE IF NOT EXISTS mcp_event_deliveries(id TEXT PRIMARY KEY,subscription TEXT NOT NULL,notification INTEGER,post TEXT,status TEXT NOT NULL DEFAULT 'pending',attempts INTEGER NOT NULL DEFAULT 0,next_at INTEGER NOT NULL DEFAULT 0,last_status INTEGER,last_error TEXT,created INTEGER NOT NULL);
 CREATE INDEX IF NOT EXISTS mcp_event_due ON mcp_event_deliveries(status,next_at);
 CREATE TRIGGER IF NOT EXISTS mcp_notification_events AFTER INSERT ON notifications BEGIN
 INSERT INTO mcp_event_deliveries(id,subscription,notification,created)
 SELECT 'evt_mcp_'||s.id||'_'||NEW.id,s.id,NEW.id,CAST(strftime('%s','now') AS INTEGER)*1000 FROM mcp_event_subscriptions s JOIN oauth_grants g ON g.id=s.grant_id
 WHERE s.enabled=1 AND s.expires>CAST(strftime('%s','now') AS INTEGER)*1000 AND g.revoked IS NULL AND s.name='notification.created' AND s.actor=NEW.recipient AND NEW.type IN ('reply','mention','quote','repost','like','follow') AND (json_extract(s.args,'$.notificationType') IS NULL OR json_extract(s.args,'$.notificationType')=NEW.type);
 END;
 CREATE TRIGGER IF NOT EXISTS mcp_post_events AFTER INSERT ON posts BEGIN
 INSERT INTO mcp_event_deliveries(id,subscription,post,created)
 SELECT 'evt_mcp_'||s.id||'_'||NEW.uri,s.id,NEW.uri,CAST(strftime('%s','now') AS INTEGER)*1000 FROM mcp_event_subscriptions s JOIN oauth_grants g ON g.id=s.grant_id
 WHERE s.enabled=1 AND s.expires>CAST(strftime('%s','now') AS INTEGER)*1000 AND g.revoked IS NULL AND (s.name='moderation.post.created' OR s.name='post.created' AND s.actor=NEW.author);
 END;`);
 const encrypt=value=>{const iv=randomBytes(12),c=createCipheriv('aes-256-gcm',Buffer.from(key,'hex'),iv);return Buffer.concat([iv,c.update(value),c.final(),c.getAuthTag()]).toString('base64');};
 const decrypt=value=>{const b=Buffer.from(value,'base64'),c=createDecipheriv('aes-256-gcm',Buffer.from(key,'hex'),b.subarray(0,12));c.setAuthTag(b.subarray(-16));return Buffer.concat([c.update(b.subarray(12,-16)),c.final()]).toString();};
 function resolve(auth,name,args={}){
  if(!auth?.oauthGrant)denied();
  const g=activeGrant(auth.oauthGrant);if(!g||g.owner!==auth.operator||g.connection.id!==auth.connectionId)denied();
  if(!args||typeof args!=='object'||Array.isArray(args))invalid('Use an object for event arguments.');
  const normalized={};for(const k of Object.keys(args).sort()){if(!['botId','notificationType'].includes(k)||typeof args[k]!=='string'||!args[k])invalid('Unsupported event argument.');normalized[k]=args[k];}
  if(name==='moderation.post.created'){if(g.connection.kind!=='moderation'||!g.scopes.includes('moderation.read')||Object.keys(args).length)denied();return {actor:g.owner,args:{},g};}
  if(!['post.created','notification.created'].includes(name)||g.connection.kind==='moderation')denied();
  if(name==='post.created'&&args.notificationType)invalid('Post events do not accept a notification type filter.');
  if(args.notificationType&&!types.includes(args.notificationType))invalid('Choose a public notification type. Private messages and Dating are excluded.');
  let actor=g.connection.actor;
  if(g.connection.kind==='operator'&&args.botId){const a=db.prepare("SELECT * FROM actors WHERE id=? AND kind='agent' AND operator_id=?").get(args.botId,g.owner);if(!a||a.suspended_at)denied();actor=a.id;}
  else if(args.botId&&args.botId!==actor)denied();
  if(g.connection.kind!=='operator'&&!g.scopes.includes('read'))denied();
  const a=db.prepare('SELECT * FROM actors WHERE id=?').get(actor);if(!a||a.suspended_at)denied();
  return {actor,args:normalized,g};
 }
 function valid(s){try{const g=activeGrant(s.grant_id);if(!g||g.owner!==s.owner||g.connection.id!==s.connection)return false;const resolved=resolve({oauthGrant:s.grant_id,operator:s.owner,connectionId:s.connection},s.name,JSON.parse(s.args));return resolved.actor===s.actor;}catch{return false;}}
 function listEvents(auth){if(!configured)return {events:[]};const g=activeGrant(auth.oauthGrant);if(!g)denied();
  const properties=g.connection.kind==='operator'?{botId:{...string,description:'Owned bot ID; omit to monitor your human account.'}}:{};
  const postSchema={type:'object',properties:{accountId:string,postUri:string,url:string,parent:string,quote:string,community:string},required:['accountId','postUri','url'],additionalProperties:false};
  if(g.connection.kind==='moderation')return {events:[{name:'moderation.post.created',description:'A new public post, reply, quote or community post for authorized moderation review. Private messages and Dating are excluded.',delivery:['webhook'],inputSchema:{type:'object',properties:{},additionalProperties:false},payloadSchema:postSchema}]};
  if(g.connection.kind!=='operator'&&!g.scopes.includes('read'))return {events:[]};
  return {events:[{name:'notification.created',description:'A new public social notification for your account or a selected owned bot. Excludes private messages and Dating; fetch current content through tools.',delivery:['webhook'],inputSchema:{type:'object',properties:{...properties,notificationType:{type:'string',enum:types}},additionalProperties:false},payloadSchema:{type:'object',properties:{accountId:string,notificationId:string,notificationType:{type:'string',enum:types},senderId:string,postUri:string,url:string},required:['accountId','notificationId','notificationType','senderId'],additionalProperties:false}},{name:'post.created',description:'A new public post or reply published by your account or a selected owned bot. Excludes private messages and Dating.',delivery:['webhook'],inputSchema:{type:'object',properties,additionalProperties:false},payloadSchema:postSchema}]};
 }
 function identify(auth,p,subscription=false){const selected=resolve(auth,p.name,p.arguments||{});if(!p.delivery||p.delivery.mode&&p.delivery.mode!=='webhook'||typeof p.delivery.url!=='string')invalid('Provide a webhook delivery URL.');if(subscription&&p.delivery.mode!=='webhook')invalid('Use webhook delivery.');const id='sub_'+createHash('sha256').update(JSON.stringify([selected.g.owner,selected.g.connection.id,p.delivery.url,p.name,selected.args])).digest('hex');return {id,...selected};}
 function disable(owner,id){if(!db.prepare('UPDATE mcp_event_subscriptions SET enabled=0 WHERE id=? AND owner=?').run(id,owner).changes)invalid('Subscription not found.');db.prepare("UPDATE mcp_event_deliveries SET status='canceled' WHERE subscription=? AND status='pending'").run(id);return {};}
 async function subscribe(auth,p){
  if(!configured)throw Object.assign(Error('Encrypted event subscriptions are not configured.'),{rpcCode:-32603});
  if(p.cursor!==null&&p.cursor!==undefined)invalid('Replay cursors are not supported. Use cursor null.');
  const selected=identify(auth,p,true),secret=p.delivery.secret;
  if(typeof secret!=='string'||!secret.startsWith('whsec_'))invalid('Use a whsec_ Standard Webhooks signing key.');let bytes;try{bytes=standardWebhookKey(secret);}catch{invalid('Invalid signing key.');}if(bytes.length<24||bytes.length>64)invalid('The signing key must decode to 24–64 bytes.');
  const ttl=p.ttlMs===undefined||p.ttlMs===null?86400000:p.ttlMs;if(!Number.isSafeInteger(ttl)||ttl<1)invalid('Use a positive integer ttlMs.');const expires=now()+Math.min(ttl,7*86400000);
  const old=db.prepare('SELECT * FROM mcp_event_subscriptions WHERE id=?').get(selected.id);
  if((!old||!old.enabled||old.expires<=now())&&db.prepare('SELECT COUNT(*) AS n FROM mcp_event_subscriptions WHERE owner=? AND enabled=1 AND expires>?').get(selected.g.owner,now()).n>=10)throw Object.assign(Error('Use up to ten active event subscriptions per operator.'),{rpcCode:-32025});
  if(checking.has(selected.id))throw Object.assign(Error('This subscription is being verified. Retry shortly.'),{rpcCode:-32025});
  checking.add(selected.id);
  try{
   const bucket=rates.get(selected.g.owner)||{count:0,until:now()+60000};if(bucket.until<=now()){bucket.count=0;bucket.until=now()+60000;}if(++bucket.count>5)throw Object.assign(Error('Too many subscription verification requests. Retry in a minute.'),{rpcCode:-32025});rates.set(selected.g.owner,bucket);for(const [id,b]of rates)if(b.until<=now())rates.delete(id);
   await webhookDestination(p.delivery.url,{testing});const challenge=randomBytes(32).toString('base64url'),id='msg_verification_'+randomBytes(16).toString('hex');let response;
   try{response=await webhookRequest(p.delivery.url,JSON.stringify({type:'verification',challenge}),secret,id,testing,{readResponse:true,headers:{'X-MCP-Subscription-Id':selected.id}});let echo;try{echo=JSON.parse(response.body).challenge;}catch{}if(response.status<200||response.status>=300||typeof echo!=='string'||Buffer.byteLength(echo)!==Buffer.byteLength(challenge)||!timingSafeEqual(Buffer.from(echo),Buffer.from(challenge)))throw Error('challenge');}
   catch{throw Object.assign(Error('Webhook callback verification failed.'),{rpcCode:-32015,rpcData:{reason:'challenge_failed'}});}
   // Authorization can change while the callback request is in flight.
   resolve(auth,p.name,p.arguments||{});
   const rotated=old&&decrypt(old.secret)!==secret;
   db.prepare(`INSERT INTO mcp_event_subscriptions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET grant_id=excluded.grant_id,secret=excluded.secret,previous_secret=excluded.previous_secret,previous_until=excluded.previous_until,expires=excluded.expires,enabled=1`).run(selected.id,selected.g.owner,selected.actor,selected.g.connection.id,auth.oauthGrant,p.name,JSON.stringify(selected.args),p.delivery.url,encrypt(secret),rotated?old.secret:old?.previous_secret||null,rotated?now()+300000:old?.previous_until||null,expires,1,old?.created||now());
   return {id:selected.id,refreshBefore:new Date(expires).toISOString(),cursor:null,truncated:false};
  }finally{checking.delete(selected.id);}
 }
 async function request(method,params,auth){if(method==='events/list')return listEvents(auth);if(!params||typeof params!=='object'||Array.isArray(params))invalid('Use event parameters.');if(method==='events/subscribe')return subscribe(auth,params);if(method==='events/unsubscribe'){const {id,g}=identify(auth,params);const s=db.prepare('SELECT id FROM mcp_event_subscriptions WHERE id=? AND owner=?').get(id,g.owner);if(s)disable(g.owner,id);return {};}throw Object.assign(Error('Unsupported event method.'),{rpcCode:-32601});}
 function payload(s,d){
  const base=typeof origin==='function'?origin():origin;
  if(d.post){const p=db.prepare('SELECT p.*,a.suspended_at FROM posts p JOIN actors a ON a.id=p.author WHERE p.uri=?').get(d.post);if(!p||p.deleted||p.removed_at||p.community_removed_at||p.suspended_at)return null;return {eventId:d.id,name:s.name,timestamp:p.created,data:{accountId:p.author,postUri:p.uri,url:base+'/#thread='+encodeURIComponent(p.uri),...(p.parent?{parent:p.parent}:{}),...(p.quote_uri?{quote:p.quote_uri}:{}),...(p.community_id?{community:p.community_id}:{})},cursor:null};}
  const n=db.prepare('SELECT * FROM notifications WHERE id=?').get(d.notification);if(!n||n.recipient!==s.actor||!types.includes(n.type))return null;const sender=db.prepare('SELECT suspended_at FROM actors WHERE id=?').get(n.sender);if(!sender||sender.suspended_at)return null;
  if(n.post){const p=db.prepare('SELECT deleted,removed_at,community_removed_at FROM posts WHERE uri=?').get(n.post);if(!p||p.deleted||p.removed_at||p.community_removed_at)return null;}
  return {eventId:d.id,name:s.name,timestamp:n.created,data:{accountId:n.recipient,notificationId:String(n.id),notificationType:n.type,senderId:n.sender,...(n.post?{postUri:n.post,url:base+'/#thread='+encodeURIComponent(n.post)}:{})},cursor:null};
 }
 async function attempt(d){const s=db.prepare('SELECT * FROM mcp_event_subscriptions WHERE id=?').get(d.subscription);if(!s?.enabled||s.expires<=now()||!valid(s)){if(s?.enabled)disable(s.owner,s.id);db.prepare("UPDATE mcp_event_deliveries SET status='canceled' WHERE id=?").run(d.id);return;}
  const event=payload(s,d);if(!event){db.prepare("UPDATE mcp_event_deliveries SET status='canceled' WHERE id=?").run(d.id);return;}
  let status=null,error=null;try{status=(await webhookRequest(s.url,JSON.stringify(event),decrypt(s.secret),d.id,testing,{headers:{'X-MCP-Subscription-Id':s.id},...(s.previous_secret&&s.previous_until>now()?{previousSecret:decrypt(s.previous_secret)}:{})})).status;if(status<200||status>=300)error='callback_rejected';}catch{error='callback_unavailable';}
  const attempts=d.attempts+1,next=now()+[5000,30000,120000,600000][Math.min(attempts-1,3)];db.prepare('UPDATE mcp_event_deliveries SET status=?,attempts=?,next_at=?,last_status=?,last_error=? WHERE id=?').run(!error?'delivered':[410,413].includes(status)||attempts>=5?'failed':'pending',attempts,next,status,error,d.id);
 }
 async function tick(){if(busy||!configured)return;busy=true;try{db.prepare("DELETE FROM mcp_event_deliveries WHERE status!='pending' AND created<?").run(now()-7*86400000);db.prepare('DELETE FROM mcp_event_subscriptions WHERE expires<? AND id NOT IN (SELECT subscription FROM mcp_event_deliveries WHERE status=?)').run(now()-7*86400000,'pending');db.prepare('UPDATE mcp_event_subscriptions SET previous_secret=NULL,previous_until=NULL WHERE previous_until<?').run(now());const due=db.prepare("SELECT * FROM mcp_event_deliveries WHERE status='pending' AND next_at<=? ORDER BY rowid LIMIT 4").all(now());await Promise.all(due.map(attempt));}catch{console.error('MCP event worker encountered an error');}finally{busy=false;}}
 const timer=setInterval(tick,1000);timer.unref();
 function list(owner){return {subscriptions:db.prepare('SELECT * FROM mcp_event_subscriptions WHERE owner=? ORDER BY created DESC').all(owner).map(s=>({id:s.id,name:s.name,actor:s.actor,url:s.url,expires:new Date(s.expires).toISOString(),enabled:!!s.enabled&&s.expires>now()&&valid(s),deliveries:db.prepare('SELECT status,attempts,last_status,last_error FROM mcp_event_deliveries WHERE subscription=? ORDER BY rowid DESC LIMIT 5').all(s.id)}))};}
 return {configured,request,list,disable,tick,stop:()=>clearInterval(timer)};
}
