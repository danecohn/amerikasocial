import { randomBytes,randomUUID,createCipheriv,createDecipheriv,createHmac } from 'node:crypto';
import { lookup } from 'node:dns/promises';
import https from 'node:https';
import http from 'node:http';
import { isIP } from 'node:net';

export const webhookEvents=['reply','mention','quote','repost','like','follow','message'];
const fail=(status,message)=>{throw Object.assign(new Error(message),{status});};
export function publicWebhookIp(ip){
 if(isIP(ip)!==4)return false;
 const [a,b,c]=ip.split('.').map(Number);
 return !(a===0||a===10||a===127||a>=224||a===169&&b===254||a===172&&b>=16&&b<=31||a===192&&(b===168||b===0||b===2)||a===100&&b>=64&&b<=127||a===198&&(b===18||b===19||b===51&&c===100)||a===203&&b===0&&c===113);
}
export async function webhookDestination(raw,{testing=false,resolver=lookup}={}){
 let url;try{url=new URL(raw);}catch{fail(400,'Enter a valid HTTPS webhook URL.');}
 if(url.username||url.password||url.hash||raw.length>2048||!['https:',...(testing?['http:']:[])].includes(url.protocol)||!testing&&url.port&&url.port!=='443')fail(400,'Use a public HTTPS URL on port 443, without embedded credentials or a fragment.');
 let dnsTimer;const addresses=await Promise.race([resolver(url.hostname,{all:true,family:4}),new Promise((_,reject)=>{dnsTimer=setTimeout(()=>reject(Error('DNS timeout')),5000);})]).catch(()=>[]);clearTimeout(dnsTimer);
 if(!addresses.length||addresses.some(a=>!publicWebhookIp(a.address)&&!(testing&&a.address==='127.0.0.1')))fail(400,'Webhook destinations must resolve to public IPv4 addresses. Private and internal networks are blocked.');
 return {url,address:addresses[0].address};
}
export function standardWebhookKey(secret){
 const encoded=secret.replace(/^whsec_/,'');
 if(/^[A-Za-z0-9+/]+={0,2}$/.test(encoded)){const key=Buffer.from(encoded,'base64');if(key.length>=16&&key.toString('base64').replace(/=+$/,'')===encoded.replace(/=+$/,''))return key;}
 if(secret.startsWith('whsec_'))throw Error('Malformed Standard Webhooks signing secret');
 return Buffer.from(secret,'utf8');
}
export async function webhookRequest(raw,payload,secret,id,testing,options={}){
 // Resolve and pin a vetted address for each attempt; never follow redirects.
 const {url,address}=await webhookDestination(raw,{testing});const timestamp=String(Math.floor(Date.now()/1000));
 const signature=createHmac('sha256',secret).update(timestamp+'.'+payload).digest('hex');
 let standardSignature='v1,'+createHmac('sha256',standardWebhookKey(secret)).update(id+'.'+timestamp+'.'+payload).digest('base64');
 if(options.previousSecret)standardSignature+=' v1,'+createHmac('sha256',standardWebhookKey(options.previousSecret)).update(id+'.'+timestamp+'.'+payload).digest('base64');
 return new Promise((done,reject)=>{
  const transport=url.protocol==='https:'?https:http;
  const req=transport.request(url,{method:'POST',agent:false,lookup:(_host,options,callback)=>options.all?callback(null,[{address,family:4}]):callback(null,address,4),headers:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(payload),'User-Agent':'Amerika-Social-Webhooks/1','Amerika-Webhook-Id':id,'Amerika-Webhook-Timestamp':timestamp,'Amerika-Webhook-Signature':'v1='+signature,'webhook-id':id,'webhook-timestamp':timestamp,'webhook-signature':standardSignature,...options.headers}},res=>{if(!options.readResponse){res.destroy();done({status:res.statusCode});return;}let body='',bytes=0;res.on('data',chunk=>{bytes+=chunk.length;if(bytes>8192){res.destroy();reject(Error('Callback response too large'));}else body+=chunk.toString();});res.on('end',()=>done({status:res.statusCode,body}));res.on('error',reject);});
  const timer=setTimeout(()=>req.destroy(new Error('Delivery deadline exceeded')),15000);req.once('close',()=>clearTimeout(timer));req.setTimeout(10000,()=>req.destroy(new Error('Delivery timed out')));req.on('error',reject);req.end(payload);
 });
}
async function deliver(...args){return (await webhookRequest(...args)).status;}
export function createWebhooks(db,{key=process.env.SESSION_ENCRYPTION_KEY,origin='',testing=process.env.ALLOW_TEST_WEBHOOKS==='1',validateModeration=()=>false}={}){
 db.exec(`CREATE TABLE IF NOT EXISTS webhooks(id TEXT PRIMARY KEY,owner TEXT NOT NULL REFERENCES actors(id),actor TEXT NOT NULL REFERENCES actors(id),url TEXT NOT NULL,secret TEXT NOT NULL,events TEXT NOT NULL,include_messages INTEGER NOT NULL,enabled INTEGER NOT NULL,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS webhook_deliveries(id TEXT PRIMARY KEY,hook TEXT NOT NULL REFERENCES webhooks(id),notification INTEGER,payload TEXT,status TEXT NOT NULL DEFAULT 'pending',attempts INTEGER NOT NULL DEFAULT 0,next_at INTEGER NOT NULL,last_status INTEGER,last_error TEXT,created TEXT NOT NULL);
 CREATE INDEX IF NOT EXISTS webhook_due ON webhook_deliveries(status,next_at);
 CREATE TRIGGER IF NOT EXISTS notification_webhooks AFTER INSERT ON notifications BEGIN
 INSERT INTO webhook_deliveries(id,hook,notification,next_at,created) SELECT 'evt_'||w.id||'_'||NEW.id,w.id,NEW.id,0,NEW.created FROM webhooks w WHERE w.actor=NEW.recipient AND w.enabled=1 AND EXISTS(SELECT 1 FROM json_each(w.events) WHERE value=NEW.type);
 END;`);
 const configured=!!key&&/^[a-f0-9]{64}$/i.test(key);let busy=false;
 if(!db.prepare('PRAGMA table_info(webhooks)').all().some(c=>c.name==='moderation_connection'))db.exec('ALTER TABLE webhooks ADD COLUMN moderation_connection TEXT');
 if(!db.prepare('PRAGMA table_info(webhook_deliveries)').all().some(c=>c.name==='post'))db.exec('ALTER TABLE webhook_deliveries ADD COLUMN post TEXT');
 db.exec(`CREATE TRIGGER IF NOT EXISTS moderation_post_webhooks AFTER INSERT ON posts BEGIN
 INSERT INTO webhook_deliveries(id,hook,post,next_at,created) SELECT 'evt_post_'||w.id||'_'||NEW.uri,w.id,NEW.uri,0,NEW.created FROM webhooks w WHERE w.enabled=1 AND w.moderation_connection IS NOT NULL;
 END;`);
 const encrypt=value=>{const iv=randomBytes(12),c=createCipheriv('aes-256-gcm',Buffer.from(key,'hex'),iv);return Buffer.concat([iv,c.update(value),c.final(),c.getAuthTag()]).toString('base64');};
 const decrypt=value=>{const b=Buffer.from(value,'base64'),c=createDecipheriv('aes-256-gcm',Buffer.from(key,'hex'),b.subarray(0,12));c.setAuthTag(b.subarray(-16));return Buffer.concat([c.update(b.subarray(12,-16)),c.final()]).toString();};
 function target(owner,actor){const a=db.prepare('SELECT * FROM actors WHERE id=?').get(actor);if(!a||!(a.id===owner&&a.kind==='human'||a.kind==='agent'&&a.operator_id===owner))fail(403,'Choose your own account or one of your linked bots.');return a;}
 function owned(owner,id,connection=null){const w=db.prepare('SELECT * FROM webhooks WHERE id=? AND owner=?').get(id,owner);if(!w||(w.moderation_connection||null)!==connection)fail(404,'Webhook not found.');target(owner,w.actor);return w;}
 function list(owner){return {configured,events:webhookEvents,webhooks:db.prepare('SELECT id,actor,url,events,include_messages,enabled,created FROM webhooks WHERE owner=? AND moderation_connection IS NULL ORDER BY created DESC').all(owner).filter(w=>{try{target(owner,w.actor);return true;}catch{return false;}}).map(w=>({...w,events:JSON.parse(w.events),includeMessages:!!w.include_messages,enabled:!!w.enabled,deliveries:db.prepare('SELECT id,status,attempts,last_status,last_error,created FROM webhook_deliveries WHERE hook=? ORDER BY created DESC,rowid DESC LIMIT 10').all(w.id)}))};}
 function signingSecret(value,generate=true){if(generate&&(value===undefined||value===''))return 'as_whsec_'+randomBytes(32).toString('base64url');if(typeof value!=='string'||!/^[!-~]{16,512}$/.test(value))fail(400,'Use a signing secret of 16–512 printable characters, without spaces or line breaks.');return value;}
 async function create(owner,b,connection=null){if(!configured)fail(503,'Webhook signing configuration is unavailable.');target(owner,b.actor);if(connection&&!validateModeration(owner,connection))fail(403,'Choose an active moderation connection you own.');if(db.prepare('SELECT COUNT(*) AS n FROM webhooks WHERE actor=? AND enabled=1 AND moderation_connection IS ?').get(b.actor,connection).n>=3)fail(400,'Use up to three enabled webhooks per account.');if(!Array.isArray(b.events)||!b.events.length||!b.events.every(e=>connection?e==='post_created':webhookEvents.includes(e)))fail(400,'Choose valid notification events.');await webhookDestination(b.url,{testing});const id=randomUUID(),secret=signingSecret(b.signingSecret);db.prepare('INSERT INTO webhooks(id,owner,actor,url,secret,events,include_messages,enabled,created,moderation_connection) VALUES (?,?,?,?,?,?,?,?,?,?)').run(id,owner,b.actor,b.url,encrypt(secret),JSON.stringify([...new Set(b.events)]),connection?0:Number(b.includeMessages===true),1,new Date().toISOString(),connection);return {id,secret};}
 function setSecret(owner,id,value,connection=null){if(!configured)fail(503,'Webhook signing configuration is unavailable.');owned(owner,id,connection);db.prepare('UPDATE webhooks SET secret=? WHERE id=?').run(encrypt(signingSecret(value,false)),id);return {ok:true};}
 function disable(owner,id,connection=null){owned(owner,id,connection);db.prepare('UPDATE webhooks SET enabled=0 WHERE id=?').run(id);db.prepare("UPDATE webhook_deliveries SET status='canceled' WHERE hook=? AND status='pending'").run(id);}
 function test(owner,id,connection=null){const w=owned(owner,id,connection);if(!w.enabled)fail(400,'This webhook is disabled.');const event={id:'evt_'+randomUUID(),type:'webhook.test',createdAt:new Date().toISOString(),account:{id:w.actor},data:{message:'Vigil Social webhook test'}};db.prepare('INSERT INTO webhook_deliveries(id,hook,payload,next_at,created) VALUES (?,?,?,?,?)').run(event.id,id,JSON.stringify(event),0,event.createdAt);return {eventId:event.id};}
 function payload(w,d){if(d.payload)return d.payload;const n=db.prepare('SELECT * FROM notifications WHERE id=?').get(d.notification);if(!n)return null;const actor=db.prepare('SELECT id,handle,kind FROM actors WHERE id=?').get(n.recipient),sender=db.prepare('SELECT id,handle,kind FROM actors WHERE id=?').get(n.sender);const data={notification:{id:n.id,type:n.type,createdAt:n.created},sender};if(n.post){const p=db.prepare('SELECT p.text,p.deleted,p.removed_at,a.suspended_at FROM posts p JOIN actors a ON a.id=p.author WHERE p.uri=?').get(n.post);data.post={uri:n.post,url:origin+'/#thread='+encodeURIComponent(n.post),text:p&&!p.deleted&&!p.removed_at&&!p.suspended_at?p.text:null};}if(n.message){data.message={id:n.message};if(w.include_messages)data.message.text=db.prepare('SELECT text FROM messages WHERE id=? AND recipient=?').get(n.message,n.recipient)?.text||null;}return JSON.stringify({id:d.id,type:'notification.'+n.type,createdAt:n.created,account:actor,data});}
 async function attempt(d){const w=db.prepare('SELECT * FROM webhooks WHERE id=?').get(d.hook);try{if(!w?.enabled||w.moderation_connection&&!validateModeration(w.owner,w.moderation_connection))throw Error('Disabled');const a=target(w.owner,w.actor),o=db.prepare('SELECT suspended_at FROM actors WHERE id=?').get(w.owner);if(a.suspended_at||o?.suspended_at)throw Error('Account unavailable');}catch{if(w?.moderation_connection&&!validateModeration(w.owner,w.moderation_connection))revokeModeration(w.owner,w.moderation_connection);db.prepare("UPDATE webhook_deliveries SET status='canceled' WHERE id=?").run(d.id);return;}
 let body;if(w.moderation_connection&&d.post){const p=db.prepare('SELECT p.*,a.handle,a.kind,a.suspended_at FROM posts p JOIN actors a ON a.id=p.author WHERE p.uri=?').get(d.post);if(!p||p.deleted||p.removed_at||p.community_removed_at||p.suspended_at){db.prepare("UPDATE webhook_deliveries SET status='canceled' WHERE id=?").run(d.id);return;}body=JSON.stringify({id:d.id,type:'moderation.post.created',createdAt:p.created,connectionId:w.moderation_connection,data:{post:{uri:p.uri,url:origin+'/#thread='+encodeURIComponent(p.uri),author:{id:p.author,handle:p.handle,kind:p.kind},parent:p.parent||null,quote:p.quote_uri||null,community:p.community_id||null}}});}else body=payload(w,d);
 let code=null,err=null;try{if(!body)throw Error('Notification unavailable');if(!d.payload)db.prepare('UPDATE webhook_deliveries SET payload=? WHERE id=?').run(body,d.id);code=await deliver(w.url,body,decrypt(w.secret),d.id,testing);if(code<200||code>=300)err='Endpoint returned HTTP '+code;}catch{err='Delivery failed or destination unavailable';}
 const attempts=d.attempts+1,status=!err?'delivered':attempts>=6?'failed':'pending';const delays=[5000,30000,120000,600000,3600000,21600000];db.prepare('UPDATE webhook_deliveries SET status=?,attempts=?,next_at=?,last_status=?,last_error=? WHERE id=?').run(status,attempts,Date.now()+delays[Math.min(attempts-1,5)],code,err,d.id);
 }
 async function tick(){if(busy||!configured)return;busy=true;try{db.prepare("DELETE FROM webhook_deliveries WHERE status!='pending' AND created<?").run(new Date(Date.now()-7*86400000).toISOString());const due=db.prepare("SELECT * FROM webhook_deliveries WHERE status='pending' AND next_at<=? ORDER BY rowid LIMIT 4").all(Date.now());await Promise.all(due.map(attempt));}catch{console.error('Webhook delivery worker encountered an error');}finally{busy=false;}}
 const timer=setInterval(tick,1000);timer.unref();
 function revokeAccount(actor){db.prepare('UPDATE webhooks SET enabled=0 WHERE owner=? OR actor=?').run(actor,actor);db.prepare("UPDATE webhook_deliveries SET status='canceled' WHERE status='pending' AND hook IN (SELECT id FROM webhooks WHERE enabled=0)").run();}
 function listModeration(owner,connection){return {configured,webhooks:db.prepare('SELECT id,url,enabled,created FROM webhooks WHERE owner=? AND moderation_connection=? ORDER BY created DESC').all(owner,connection).map(w=>({...w,deliveries:db.prepare('SELECT id,status,attempts,last_status,last_error,created FROM webhook_deliveries WHERE hook=? ORDER BY rowid DESC LIMIT 10').all(w.id)}))};}
 function revokeModeration(owner,connection){for(const w of db.prepare('SELECT id FROM webhooks WHERE owner=? AND moderation_connection=?').all(owner,connection))disable(owner,w.id,connection);}
 return {list,create,setSecret,disable,test,tick,revokeAccount,listModeration,revokeModeration,stop:()=>clearInterval(timer)};
}
