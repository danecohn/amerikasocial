import {randomBytes,createHmac,timingSafeEqual} from 'node:crypto';
import {isIP} from 'node:net';

const delays=[30,120,300,900,3600];
const day=86400000;
export function loginClientIp(req,railway=!!process.env.RAILWAY_ENVIRONMENT_ID){
 const forwarded=req.headers['x-real-ip'];
 return railway&&typeof forwarded==='string'&&isIP(forwarded.trim())?forwarded.trim():req.socket.remoteAddress||'unknown';
}
export function createLoginGuard(db,{now=()=>Date.now(),railway=!!process.env.RAILWAY_ENVIRONMENT_ID}={}){
 db.exec('CREATE TABLE IF NOT EXISTS login_guard_config(id INTEGER PRIMARY KEY,secret TEXT NOT NULL); CREATE TABLE IF NOT EXISTS login_failures(id TEXT PRIMARY KEY,failures INTEGER NOT NULL,blocked_until INTEGER NOT NULL,last_failure INTEGER NOT NULL);');
 db.prepare('INSERT OR IGNORE INTO login_guard_config VALUES (1,?)').run(randomBytes(32).toString('hex'));
 const secret=db.prepare('SELECT secret FROM login_guard_config WHERE id=1').get().secret;
 const digest=s=>createHmac('sha256',secret).update(s).digest('hex');
 const inFlight=new Set();let lastCleanup=0;
 function identity(req,res){
  const ip=loginClientIp(req,railway);const raw=String(req.headers.cookie||'').split(';').map(s=>s.trim()).find(s=>s.startsWith('amerika_device='))?.slice(15);
  const parts=raw?.split('.');const valid=parts?.length===2&&/^[a-f0-9]{64}$/.test(parts[0])&&/^[a-f0-9]{64}$/.test(parts[1])&&timingSafeEqual(Buffer.from(parts[1],'hex'),Buffer.from(digest(parts[0]),'hex'));
  if(!valid){const id=randomBytes(32).toString('hex');res.setHeader('Set-Cookie','amerika_device='+id+'.'+digest(id)+'; Path=/; Max-Age=2592000; HttpOnly; SameSite=Strict'+(req.socket.encrypted||railway?'; Secure':''));}
  // Cookie-free requests share a network bucket until they retain a device cookie.
  return {device:digest('device:'+(valid?parts[0]:'no-cookie:'+ip)),network:digest('network:'+ip)};
 }
 function state(id){const row=db.prepare('SELECT * FROM login_failures WHERE id=?').get(id);return row&&now()-row.last_failure<day?row:null;}
 function wait(ids){const until=Math.max(...ids.map(id=>state(id)?.blocked_until||0));return Math.max(0,Math.ceil((until-now())/1000));}
 function blocked(seconds){throw Object.assign(Error('Too many failed sign-in attempts. Try again in '+seconds+' seconds. You can still use password recovery.'),{status:429,retryAfter:seconds});}
 function begin(ids){const seconds=wait([ids.device,ids.network]);if(seconds)blocked(seconds);if(inFlight.has(ids.device))blocked(1);inFlight.add(ids.device);return ()=>inFlight.delete(ids.device);}
 function add(id,threshold){const row=state(id),failures=(row?.failures||0)+1;const seconds=failures>=threshold?delays[Math.min(failures-threshold,delays.length-1)]:0;db.prepare('INSERT INTO login_failures VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET failures=excluded.failures,blocked_until=excluded.blocked_until,last_failure=excluded.last_failure').run(id,failures,seconds?now()+seconds*1000:0,now());}
 function failure(ids){add(ids.device,5);add(ids.network,30);if(now()-lastCleanup>3600000){db.prepare('DELETE FROM login_failures WHERE last_failure<?').run(now()-day);lastCleanup=now();}const seconds=wait([ids.device,ids.network]);if(seconds)blocked(seconds);}
 function success(ids){db.prepare('DELETE FROM login_failures WHERE id=?').run(ids.device);}
 return {identity,begin,failure,success,clientIp:req=>loginClientIp(req,railway)};
}
