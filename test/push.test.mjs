import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {createPush} from '../push.mjs';
test('native push encrypts tokens, excludes content, checks receipt failures, and cancels after block or device transfer',async()=>{
 const db=new DatabaseSync(':memory:');db.exec("CREATE TABLE actors(id TEXT PRIMARY KEY,kind TEXT,suspended_at TEXT,operator_id TEXT);INSERT INTO actors VALUES ('a','human',NULL,NULL),('b','human',NULL,NULL),('bot','agent',NULL,'a');CREATE TABLE notifications(id INTEGER PRIMARY KEY,recipient TEXT,sender TEXT,type TEXT,post TEXT,seen INTEGER DEFAULT 0)");let time=Date.now(),blocked=false,sent=[],receiptError=false;
 const push=createPush(db,{key:'fa'.repeat(32),enabled:true,now:()=>time,blocked:()=>blocked,fetcher:async(url,options)=>{const body=JSON.parse(options.body);sent.push({url,body});return {ok:true,json:async()=>url.endsWith('getReceipts')?{data:Object.fromEntries(body.ids.map(id=>[id,receiptError?{status:'error',details:{error:'DeviceNotRegistered'}}:{status:'ok'}]))}:{data:{status:'ok',id:'apple-ticket-'+sent.length}}};}});
 try{const token='ExponentPushToken[synthetic_token_abcdefgh]',device=push.register('a',token,true);assert.ok(!JSON.stringify(push.list('a')).includes(token));assert.ok(!db.prepare('SELECT token FROM push_devices WHERE id=?').get(device.id).token.includes(token));assert.throws(()=>push.disable('b',device.id),{status:404});
 db.prepare('INSERT INTO notifications VALUES (1,?,?,?,?,0)').run('bot','b','dating_message','private-uri');await push.tick();assert.equal(sent.length,1);assert.equal(sent[0].body.body,'You have new activity on AltStack Social.');assert.deepEqual(sent[0].body.data,{notificationId:1,recipient:'bot'});assert.ok(!JSON.stringify(sent).includes('private-uri'));assert.ok(!JSON.stringify(sent).includes('dating_message'));
 time+=16*60000;await push.tick();assert.equal(db.prepare('SELECT status FROM push_deliveries').get().status,'delivered');
 blocked=true;db.prepare('INSERT INTO notifications VALUES (2,?,?,?,?,0)').run('a','b','message','secret');await push.tick();assert.equal(sent.length,2);assert.equal(db.prepare('SELECT status FROM push_deliveries WHERE notification=2').get().status,'canceled');blocked=false;
 db.prepare('INSERT INTO notifications VALUES (3,?,?,?,?,0)').run('a','b','message','secret');push.register('b',token);await push.tick();assert.equal(db.prepare('SELECT status FROM push_deliveries WHERE notification=3').get().status,'canceled');assert.equal(sent.length,2);
 db.prepare('INSERT INTO notifications VALUES (4,?,?,?,?,0)').run('b','a','reply','public');await push.tick();receiptError=true;time+=16*60000;await push.tick();assert.equal(push.list('b').devices[0].enabled,false);
 }finally{push.stop();db.close();}
});
test('disabled native push cancels outstanding alerts and does not queue new deliveries',()=>{
 const db=new DatabaseSync(':memory:');db.exec("CREATE TABLE actors(id TEXT PRIMARY KEY,kind TEXT,suspended_at TEXT,operator_id TEXT);INSERT INTO actors VALUES ('a','human',NULL,NULL);CREATE TABLE notifications(id INTEGER PRIMARY KEY,recipient TEXT,sender TEXT,type TEXT,post TEXT,seen INTEGER DEFAULT 0)");
 let push=createPush(db,{key:'ab'.repeat(32),enabled:true});
 try{push.register('a','ExpoPushToken[synthetic_abcdefgh]');db.exec("INSERT INTO notifications VALUES (1,'a','peer','reply','post',0)");push.stop();push=createPush(db,{key:'ab'.repeat(32),enabled:false});assert.equal(db.prepare('SELECT status FROM push_deliveries').get().status,'canceled');db.exec("INSERT INTO notifications VALUES (2,'a','peer','reply','post',0)");assert.equal(db.prepare('SELECT COUNT(*) AS n FROM push_deliveries').get().n,1);assert.throws(()=>push.register('a','ExpoPushToken[synthetic_other]'),{status:503});}finally{push.stop();db.close();}
});
