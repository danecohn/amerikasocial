import {randomUUID} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {AppStoreServerAPIClient,Environment,SignedDataVerifier} from '@apple/app-store-server-library';
const fail=(status,message)=>{throw Object.assign(Error(message),{status});};
export function createAppleBilling(db,{env=process.env,client,verifier,now=Date.now}={}){
 db.exec(`CREATE TABLE IF NOT EXISTS apple_accounts(actor TEXT PRIMARY KEY REFERENCES actors(id),token TEXT UNIQUE NOT NULL);
 CREATE TABLE IF NOT EXISTS apple_subscriptions(original_id TEXT PRIMARY KEY,actor TEXT NOT NULL REFERENCES actors(id),transaction_id TEXT NOT NULL,product TEXT NOT NULL,expires INTEGER NOT NULL,revoked INTEGER NOT NULL,signed_at INTEGER NOT NULL,environment TEXT NOT NULL);
 CREATE INDEX IF NOT EXISTS apple_subscription_actor ON apple_subscriptions(actor);
 CREATE TABLE IF NOT EXISTS apple_notifications(id TEXT PRIMARY KEY,created INTEGER NOT NULL);`);
 const bundle=env.APPLE_BUNDLE_ID||'social.amerika.ios',product=env.APPLE_PLUS_PRODUCT_ID||'social.amerika.plus.monthly';
 const environment=env.APPLE_IAP_ENVIRONMENT==='Production'?Environment.PRODUCTION:Environment.SANDBOX;
 const configured=!!(env.APPLE_IAP_ENABLED==='true'&&env.APPLE_IAP_KEY_ID&&env.APPLE_IAP_ISSUER_ID&&env.APPLE_IAP_PRIVATE_KEY&&env.APPLE_BUNDLE_ID&&(environment!==Environment.PRODUCTION||Number(env.APPLE_APP_ID)>0));
 if(configured&&!client){client=new AppStoreServerAPIClient(env.APPLE_IAP_PRIVATE_KEY.replace(/\\n/g,'\n'),env.APPLE_IAP_KEY_ID,env.APPLE_IAP_ISSUER_ID,bundle,environment);}
 if(configured&&!verifier){const roots=['AppleRootCA-G3.cer','AppleRootCA-G2.cer'].map(name=>readFileSync(new URL('./certificates/'+name,import.meta.url)));verifier=new SignedDataVerifier(roots,true,environment,bundle,environment===Environment.PRODUCTION?Number(env.APPLE_APP_ID):undefined);}
 const enabled=configured&&!!client&&!!verifier;
 const requireEnabled=()=>{if(!enabled)fail(503,'Apple subscriptions are not available yet.');};
 function account(actor){requireEnabled();db.prepare('INSERT OR IGNORE INTO apple_accounts VALUES (?,?)').run(actor,randomUUID());return {enabled,productId:product,appAccountToken:db.prepare('SELECT token FROM apple_accounts WHERE actor=?').get(actor).token};}
 function apply(t,expectedActor){
  if(t.bundleId!==bundle||t.productId!==product||t.environment!==environment||t.type!=='Auto-Renewable Subscription'||t.inAppOwnershipType!=='PURCHASED')fail(400,'This transaction is not an AltStack Plus subscription.');
  if(!t.transactionId||!t.originalTransactionId||!Number.isSafeInteger(t.expiresDate)||!Number.isSafeInteger(t.signedDate)||!t.appAccountToken)fail(400,'Apple returned incomplete subscription data.');
  const owner=db.prepare('SELECT actor FROM apple_accounts WHERE token=?').get(t.appAccountToken)?.actor;
  if(!owner||expectedActor&&owner!==expectedActor)fail(403,'This Apple subscription belongs to a different Amerika account.');
  const old=db.prepare('SELECT * FROM apple_subscriptions WHERE original_id=?').get(t.originalTransactionId);
  if(old&&old.actor!==owner)fail(403,'This subscription is already linked to another account.');
  if(!old||(t.signedDate>=old.signed_at&&(t.transactionId===old.transaction_id||t.expiresDate>=old.expires)))db.prepare(`INSERT INTO apple_subscriptions VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(original_id) DO UPDATE SET transaction_id=excluded.transaction_id,expires=excluded.expires,revoked=excluded.revoked,signed_at=excluded.signed_at`).run(t.originalTransactionId,owner,t.transactionId,product,t.expiresDate,Number(!!t.revocationDate),t.signedDate,environment);
  return owner;
 }
 async function verify(actor,id){requireEnabled();if(typeof id!=='string'||!/^\d{1,30}$/.test(id))fail(400,'Provide a valid Apple transaction ID.');let t;try{const response=await client.getTransactionInfo(id);t=await verifier.verifyAndDecodeTransaction(response.signedTransactionInfo);}catch{fail(502,'Apple could not verify this purchase. Retry or restore purchases.');}if(t.transactionId!==id)fail(400,'Apple transaction mismatch.');apply(t,actor);return {verified:true,active:!!db.prepare('SELECT 1 FROM apple_subscriptions WHERE actor=? AND expires>? AND revoked=0').get(actor,now())};}
 async function notification(payload){requireEnabled();if(typeof payload!=='string'||payload.length>100000)fail(400,'Invalid Apple notification.');let n,t;try{n=await verifier.verifyAndDecodeNotification(payload);if(n.data?.signedTransactionInfo)t=await verifier.verifyAndDecodeTransaction(n.data.signedTransactionInfo);}catch{fail(400,'Apple notification signature verification failed.');}if(!n.notificationUUID)fail(400,'Apple notification ID is missing.');if(db.prepare('SELECT 1 FROM apple_notifications WHERE id=?').get(n.notificationUUID))return {ok:true,duplicate:true};if(n.notificationType==='TEST')return {ok:true};if(!t)fail(400,'Apple subscription transaction is missing.');
  db.exec('BEGIN IMMEDIATE');try{apply(t);db.prepare('INSERT INTO apple_notifications VALUES (?,?)').run(n.notificationUUID,now());db.prepare('DELETE FROM apple_notifications WHERE created<?').run(now()-90*86400000);db.exec('COMMIT');}catch(e){db.exec('ROLLBACK');throw e;}return {ok:true};
 }
 return {enabled,product,account,verify,notification};
}
