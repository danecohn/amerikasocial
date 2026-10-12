import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {createOnboarding} from '../onboarding.mjs';
test('welcome friendship retries durably, remains removable, and Ant invitation is optional',async()=>{
 const db=new DatabaseSync(':memory:');db.exec('CREATE TABLE actors(id TEXT PRIMARY KEY,handle TEXT,kind TEXT,suspended_at TEXT);CREATE TABLE follows(actor TEXT,subject TEXT,PRIMARY KEY(actor,subject));');
 for(const [id,handle,kind]of [['official','amerika.demo','agent'],['ant','ant.demo','human'],['new','new.demo','human'],['bot','bot.demo','agent']])db.prepare('INSERT INTO actors VALUES (?,?,?,NULL)').run(id,handle,kind);
 let failFirst=true;const options={handleDomain:null,publicActor:a=>({id:a.id,handle:a.handle}),addFriend:async(actor,subject)=>{if(failFirst){failFirst=false;throw Error('Temporary network failure');}db.prepare('INSERT OR IGNORE INTO follows VALUES (?,?)').run(actor,subject);}};
 let welcome=createOnboarding(db,options);
 try{welcome.schedule({id:'new'});assert.equal(welcome.status('new').pendingOfficial,true);assert.equal(welcome.status('new').invites[0].id,'ant');await welcome.complete('new');assert.equal(welcome.status('new').pendingOfficial,true);welcome.stop();welcome=createOnboarding(db,options);await welcome.complete('new');assert.equal(welcome.status('new').pendingOfficial,false);assert.ok(db.prepare('SELECT 1 FROM follows WHERE actor=? AND subject=?').get('new','official'));assert.equal(db.prepare('SELECT 1 FROM follows WHERE actor=? AND subject=?').get('new','ant'),undefined);await welcome.accept('new','ant');assert.equal(welcome.status('new').invites.length,0);await assert.rejects(welcome.accept('new','bot'));db.prepare('DELETE FROM follows WHERE actor=? AND subject=?').run('new','official');await welcome.complete('new');assert.equal(db.prepare('SELECT 1 FROM follows WHERE actor=? AND subject=?').get('new','official'),undefined,'A completed welcome does not force friendships back on');welcome.schedule({id:'bot'});welcome.dismiss('bot','ant');assert.equal(welcome.status('bot').invites.length,0);}finally{welcome.stop();db.close();}
});
