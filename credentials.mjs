import { randomBytes, createCipheriv, createDecipheriv } from 'node:crypto';

export function createCredentialStore(db,key){
  if(key&&!/^[a-f0-9]{64}$/i.test(key))throw Error('SESSION_ENCRYPTION_KEY must be 64 hexadecimal characters.');
  if(!db.prepare('PRAGMA table_info(login_sessions)').all().some(c=>c.name==='pds_session'))db.exec('ALTER TABLE login_sessions ADD COLUMN pds_session TEXT');
  db.exec('CREATE TABLE IF NOT EXISTS agent_sessions(actor TEXT PRIMARY KEY REFERENCES actors(id),encrypted TEXT NOT NULL)');
  function encrypt(value){const iv=randomBytes(12),cipher=createCipheriv('aes-256-gcm',Buffer.from(key,'hex'),iv);return Buffer.concat([iv,cipher.update(JSON.stringify(value)),cipher.final(),cipher.getAuthTag()]).toString('base64');}
  function decrypt(value){const bytes=Buffer.from(value,'base64'),cipher=createDecipheriv('aes-256-gcm',Buffer.from(key,'hex'),bytes.subarray(0,12));cipher.setAuthTag(bytes.subarray(-16));return JSON.parse(Buffer.concat([cipher.update(bytes.subarray(12,-16)),cipher.final()]).toString());}
  function saveLogin(tokenHash,s){if(s.accessJwt&&!key)return;db.prepare('INSERT INTO login_sessions(token_hash,actor,expires,pds_session) VALUES (?,?,?,?) ON CONFLICT(token_hash) DO UPDATE SET expires=excluded.expires,pds_session=excluded.pds_session').run(tokenHash,s.actor,s.expires,s.accessJwt?encrypt({accessJwt:s.accessJwt,refreshJwt:s.refreshJwt,jwtExpires:s.jwtExpires}):null);}
  function login(tokenHash){const saved=db.prepare('SELECT actor,expires,pds_session FROM login_sessions WHERE token_hash=? AND expires>?').get(tokenHash,Date.now());if(!saved)return null;try{return {actor:saved.actor,expires:saved.expires,...(saved.pds_session?(key?decrypt(saved.pds_session):{}):{})};}catch{return null;}}
  function saveAgent(actor,value){if(key)db.prepare('INSERT INTO agent_sessions VALUES (?,?) ON CONFLICT(actor) DO UPDATE SET encrypted=excluded.encrypted').run(actor,encrypt(value));}
  function agent(actor){if(!key)return null;const value=db.prepare('SELECT encrypted FROM agent_sessions WHERE actor=?').get(actor);try{return value?decrypt(value.encrypted):null;}catch{return null;}}
  return {saveLogin,login,saveAgent,agent};
}
