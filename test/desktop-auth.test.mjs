import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {createHash} from 'node:crypto';
import {createDesktopAuth} from '../desktop-auth.mjs';

test('desktop pairing requires approval, PKCE, an ordinary session, and one-time exchange',()=>{
 const db=new DatabaseSync(':memory:');let time=1000000;let minted=0;
 const auth=createDesktopAuth(db,{now:()=>time,readSession:token=>token==='human'?{actor:'human'}:token==='botkey'?{actor:'bot',keyId:'key'}:null,mintSession:source=>{minted++;assert.equal(source,createHash('sha256').update('human').digest('hex'));return {token:'new-private-session'};}});
 const verifier='v'.repeat(64),challenge=createHash('sha256').update(verifier).digest('base64url');
 const {id}=auth.start(challenge,'127.0.0.1');
 assert.deepEqual(auth.exchange(id,verifier),{pending:true});
 assert.throws(()=>auth.approve(id,'botkey'),/Sign in/);
 assert.throws(()=>auth.exchange(id,'x'.repeat(64)),/Invalid/);
 auth.approve(id,'human');assert.throws(()=>auth.approve(id,'human'),/already approved/);
 assert.deepEqual(auth.exchange(id,verifier),{token:'new-private-session'});assert.equal(minted,1);
 assert.throws(()=>auth.exchange(id,verifier),/Invalid/);
 const expired=auth.start(challenge,'127.0.0.1');time+=300001;assert.throws(()=>auth.exchange(expired.id,verifier),/expired/);db.close();
});

test('desktop pairing rejects malformed challenges and bounds request creation',()=>{
 const db=new DatabaseSync(':memory:');const auth=createDesktopAuth(db,{readSession:()=>null,mintSession:()=>null});
 assert.throws(()=>auth.start('bad','ip'),/PKCE/);
 for(let i=0;i<30;i++)auth.start('a'.repeat(43),'ip');
 assert.throws(()=>auth.start('a'.repeat(43),'ip'),error=>error.status===429);db.close();
});
