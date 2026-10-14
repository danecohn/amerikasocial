import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {createAccountSafety} from '../account-safety.mjs';
test('remote deletion retries across worker restart and purges late writes before completing',async()=>{
 const db=new DatabaseSync(':memory:');
 db.exec(`CREATE TABLE actors(id TEXT PRIMARY KEY,kind TEXT,operator_id TEXT,handle TEXT,name TEXT,bio TEXT,photo TEXT,avatar_blob TEXT,password TEXT,salt TEXT,agent_instructions TEXT,us_location_verified_at TEXT,suspended_at TEXT,suspension_reason TEXT);
 CREATE TABLE posts(uri TEXT PRIMARY KEY,author TEXT,text TEXT,embed TEXT,deleted INTEGER);
 CREATE TABLE messages(id INTEGER PRIMARY KEY,sender TEXT,recipient TEXT,text TEXT);
 INSERT INTO actors(id,kind,handle,name,bio) VALUES ('did:plc:synthetic','human','test.demo','Test','Sensitive bio');
 INSERT INTO posts VALUES ('post','did:plc:synthetic','Erase this',NULL,0);`);
 let time=Date.now(),remoteCalls=0,canceled=0;
 let safety=createAccountSafety(db,{now:()=>time,cancelBilling:async()=>{canceled++;},remoteDelete:async()=>{remoteCalls++;throw Error('Temporary account-server outage');}});
 try{
  safety.request('did:plc:synthetic',null,'DELETE');
  assert.equal(db.prepare('SELECT text FROM posts').get().text,'');
  await safety.tick();
  assert.equal(safety.jobs()[0].status,'pending');assert.equal(safety.jobs()[0].attempts,1);
  assert.ok(!safety.jobs()[0].last_error.includes('outage'));
  safety.stop();time+=11000;
  safety=createAccountSafety(db,{now:()=>time,cancelBilling:async()=>{canceled++;},remoteDelete:async()=>{remoteCalls++;db.prepare('INSERT INTO messages VALUES (1,?,?,?)').run('did:plc:synthetic','peer','Late in-flight write');}});
  await safety.tick();
  assert.equal(safety.jobs()[0].status,'complete');assert.equal(remoteCalls,2);assert.equal(canceled,2);
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM messages').get().n,0);
  assert.equal(db.prepare('SELECT password FROM actors').get().password,null);
  await safety.tick();assert.equal(remoteCalls,2,'Completed remote cleanup must be idempotent');
 }finally{safety.stop();db.close();}
});
