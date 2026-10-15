import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {generateKeyPairSync,sign} from 'node:crypto';
import {createGoogleBilling} from '../google-billing.mjs';
import {createBilling} from '../billing.mjs';
test('Google purchases require server-confirmed account ownership, plan, payment and acknowledgement; updates revoke inherited Plus',async()=>{
 const db=new DatabaseSync(':memory:');db.exec("CREATE TABLE actors(id TEXT PRIMARY KEY,kind TEXT,operator_id TEXT); CREATE TABLE posts(uri TEXT,author TEXT,parent TEXT,created TEXT); INSERT INTO actors VALUES ('owner','human',NULL),('other','human',NULL),('bot','agent','owner')");
 const billing=createBilling(db,'https://www.amerika.social');let purchase,ack=0,outage=false,denyAck=false;const google=createGoogleBilling(db,{env:{GOOGLE_PLAY_ENABLED:'true',SESSION_ENCRYPTION_KEY:'ad'.repeat(32),GOOGLE_RTDN_AUDIENCE:'https://www.amerika.social/api/google/notifications',GOOGLE_RTDN_EMAIL:'pubsub@example.invalid'},publisher:{get:async()=>{if(outage)throw Error();return purchase;},acknowledge:async()=>{if(denyAck)throw Error();ack++;}},identityVerifier:async jwt=>{if(jwt!=='GOOGLE-SIGNED-JWT')throw Object.assign(Error('Unauthenticated'),{status:401});}});
 try{const account=google.account('owner');assert.equal(google.account('owner').obfuscatedAccountId,account.obfuscatedAccountId);purchase={externalAccountIdentifiers:{obfuscatedExternalAccountId:account.obfuscatedAccountId},subscriptionState:'SUBSCRIPTION_STATE_ACTIVE',acknowledgementState:'ACKNOWLEDGEMENT_STATE_PENDING',lineItems:[{productId:'amerika_plus',offerDetails:{basePlanId:'monthly'},expiryTime:new Date(Date.now()+3600000).toISOString()}]};
 await assert.rejects(google.verify('other','valid-purchase-token'),{status:403});assert.equal(billing.plus('owner'),false);assert.equal(ack,0);
 denyAck=true;await assert.rejects(google.verify('owner','valid-purchase-token'),{status:502});assert.equal(billing.plus('owner'),false);denyAck=false;
 await google.verify('owner','valid-purchase-token');assert.equal(ack,1);assert.equal(billing.plus('owner'),true);assert.equal(billing.plus('bot'),true);assert.equal(db.prepare('SELECT token FROM google_subscriptions').get().token.includes('valid-purchase-token'),false);
 purchase.acknowledgementState='ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED';await Promise.all([google.verify('owner','valid-purchase-token'),google.verify('owner','valid-purchase-token')]);assert.equal(db.prepare('SELECT COUNT(*) n FROM google_subscriptions').get().n,1);
 outage=true;await assert.rejects(google.verify('owner','valid-purchase-token'),{status:502});outage=false;
 const payload={message:{data:Buffer.from(JSON.stringify({packageName:'social.amerika.android',subscriptionNotification:{purchaseToken:'valid-purchase-token'}})).toString('base64')}};
 await assert.rejects(google.notification('forged',payload),{status:401});purchase.subscriptionState='SUBSCRIPTION_STATE_ON_HOLD';await google.notification('GOOGLE-SIGNED-JWT',payload);assert.equal(billing.plus('owner'),false);assert.equal(billing.plus('bot'),false);
 purchase.subscriptionState='SUBSCRIPTION_STATE_PENDING';await google.verify('owner','valid-purchase-token');assert.equal(billing.plus('owner'),false);
 purchase.subscriptionState='SUBSCRIPTION_STATE_CANCELED';await google.verify('owner','valid-purchase-token');assert.equal(billing.plus('owner'),true);
 purchase.lineItems[0].expiryTime=new Date(Date.now()-1).toISOString();await google.verify('owner','valid-purchase-token');assert.equal(billing.plus('owner'),false);
 purchase.lineItems[0].expiryTime=new Date(Date.now()+3600000).toISOString();purchase.testPurchase={};await google.verify('owner','valid-purchase-token');assert.equal(billing.plus('owner'),false);delete purchase.testPurchase;
 purchase.lineItems[0].productId='other_product';await assert.rejects(google.verify('owner','valid-purchase-token'),{status:400});
 await assert.rejects(google.verify('owner','bad'),{status:400});
 }finally{google.stop();db.close();}
});
test('Google RTDN verifies the actual Google OIDC signature, issuer, audience, service identity and expiry',async()=>{
 const db=new DatabaseSync(':memory:');db.exec('CREATE TABLE actors(id TEXT PRIMARY KEY)');const {privateKey,publicKey}=generateKeyPairSync('rsa',{modulusLength:2048});const jwk={...publicKey.export({format:'jwk'}),kid:'google-key',alg:'RS256'};let fetched=0;
 const google=createGoogleBilling(db,{env:{GOOGLE_PLAY_ENABLED:'true',SESSION_ENCRYPTION_KEY:'ae'.repeat(32),GOOGLE_RTDN_AUDIENCE:'https://www.amerika.social/api/google/notifications',GOOGLE_RTDN_EMAIL:'pubsub@example.invalid'},publisher:{get:async()=>{throw Error('Not expected');}},fetcher:async url=>{assert.equal(url,'https://www.googleapis.com/oauth2/v3/certs');fetched++;return Response.json({keys:[jwk]});}});
 const payload={message:{data:Buffer.from(JSON.stringify({packageName:'social.amerika.android',testNotification:{}})).toString('base64')}};
 const token=override=>{const h=Buffer.from(JSON.stringify({alg:'RS256',kid:'google-key'})).toString('base64url'),p=Buffer.from(JSON.stringify({iss:'https://accounts.google.com',aud:'https://www.amerika.social/api/google/notifications',email:'pubsub@example.invalid',email_verified:true,exp:Math.floor(Date.now()/1000)+300,iat:Math.floor(Date.now()/1000),...override})).toString('base64url'),data=h+'.'+p;return data+'.'+sign('RSA-SHA256',Buffer.from(data),privateKey).toString('base64url');};
 try{assert.deepEqual(await google.notification(token({}),payload),{ok:true});for(const invalid of [{aud:'wrong'},{email:'attacker@example.invalid'},{email_verified:false},{exp:1},{iss:'attacker'}])await assert.rejects(google.notification(token(invalid),payload),{status:401});await assert.rejects(google.notification(token({}).slice(0,-12)+'forged',payload),{status:401});assert.equal(fetched,1);}finally{google.stop();db.close();}
});
