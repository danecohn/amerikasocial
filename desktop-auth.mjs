import {randomBytes,createHash,timingSafeEqual} from 'node:crypto';
const hash = value => createHash('sha256').update(value).digest('base64url');
export function createDesktopAuth(db,{readSession,mintSession,now=()=>Date.now()}) {
 db.exec('CREATE TABLE IF NOT EXISTS desktop_pairing(id TEXT PRIMARY KEY,challenge TEXT NOT NULL,source TEXT,expires INTEGER NOT NULL)');
 const rates=new Map();
 return {
  start(challenge,address){
   if(typeof challenge!=='string'||!/^[-_A-Za-z0-9]{43}$/.test(challenge))throw Object.assign(Error('Use PKCE S256.'),{status:400});
   const time=now();db.prepare('DELETE FROM desktop_pairing WHERE expires<?').run(time);
   for(const [key,value] of rates)if(value.until<time)rates.delete(key);
   const rate=rates.get(address)||{n:0,until:time+3600000};rates.set(address,rate);
   if(++rate.n>30)throw Object.assign(Error('Too many desktop sign-in requests. Retry later.'),{status:429});
   const id=randomBytes(32).toString('base64url');db.prepare('INSERT INTO desktop_pairing VALUES (?,?,NULL,?)').run(id,challenge,time+300000);return {id,expiresIn:300};
  },
  approve(id,token){
   const source=readSession(token);if(!source||source.keyId)throw Object.assign(Error('Sign in with your account to connect the desktop app.'),{status:401});
   const row=db.prepare('SELECT * FROM desktop_pairing WHERE id=? AND expires>?').get(id,now());
   if(!row||row.source)throw Object.assign(Error('This request expired or was already approved.'),{status:409});
   db.prepare('UPDATE desktop_pairing SET source=? WHERE id=? AND source IS NULL').run(createHash('sha256').update(token).digest('hex'),id);return {ok:true};
  },
  exchange(id,verifier){
   if(typeof verifier!=='string'||!/^[-._~A-Za-z0-9]{43,128}$/.test(verifier))throw Object.assign(Error('Invalid verifier.'),{status:400});
   const row=db.prepare('SELECT * FROM desktop_pairing WHERE id=? AND expires>?').get(id,now());
   if(!row||!timingSafeEqual(Buffer.from(row.challenge),Buffer.from(hash(verifier))))throw Object.assign(Error('Invalid or expired desktop sign-in.'),{status:400});
   if(!row.source)return {pending:true};
   db.prepare('DELETE FROM desktop_pairing WHERE id=?').run(id);
   return mintSession(row.source);
  }
 };
}
