import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtemp,rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import http from 'node:http';
import { DatabaseSync } from 'node:sqlite';
import StripeClient from 'stripe';

async function launch(env={},dataDir){const dir=dataDir||await mkdtemp(join(tmpdir(),'amerika-billing-'));const child=spawn(process.execPath,['server.mjs'],{env:{...process.env,PDS_URL:'',STRIPE_SECRET_KEY:'',STRIPE_WEBHOOK_SECRET:'',PORT:'0',DATA_DIR:dir,...env},stdio:['ignore','pipe','pipe']});const base=await new Promise((resolve,reject)=>{let out='';child.once('exit',()=>reject(new Error('Server startup failed')));child.stdout.on('data',b=>{out+=b;const m=out.match(/"port":(\d+)/);if(m)resolve('http://127.0.0.1:'+m[1]);});});return {dir,base,async stop(){const done=new Promise(r=>child.once('exit',r));child.kill();await done;}};}
async function request(base,path,body,token,headers={}){const r=await fetch(base+path,{method:body?'POST':'GET',headers:{...(body?{'Content-Type':'application/json'}:{}),...(token?{Authorization:'Bearer '+token}:{}),...headers},...(body?{body:JSON.stringify(body)}:{})});return {status:r.status,data:await r.json()};}
async function register(app,handle){return (await request(app.base,'/api/register',{handle,name:handle,kind:'human',password:'billing-test-password',americanConfirmed:true,rulesAccepted:true})).data;}

test('rolling quota allows replies, counts deleted posts, survives restart, and reserves concurrent slots',async()=>{
  let app=await launch();const dir=app.dir;try{const user=await register(app,'quota.demo');const posted=await Promise.all(Array.from({length:4},(_,i)=>request(app.base,'/api/posts',{text:'Original '+i},user.token)));assert.equal(posted.filter(p=>p.status===201).length,3);assert.equal(posted.filter(p=>p.status===429).length,1);const root=posted.find(p=>p.status===201).data.post;
    for(let i=0;i<5;i++)assert.equal((await request(app.base,'/api/posts',{text:'Reply '+i,parent:root.uri},user.token)).status,201);
    await request(app.base,'/api/posts/delete',{uri:root.uri},user.token);assert.equal((await request(app.base,'/api/posts',{text:'Delete bypass'},user.token)).status,429);
    assert.equal((await request(app.base,'/api/billing',null,user.token)).data.originalPostsRemaining,0);
    await app.stop();app=await launch({},dir);const login=(await request(app.base,'/api/login',{handle:'quota.demo',password:'billing-test-password'})).data;
    assert.equal((await request(app.base,'/api/billing',null,login.token)).data.originalPostsRemaining,0);
    const db=new DatabaseSync(join(dir,'botsky.sqlite'));assert.equal(db.prepare('SELECT COUNT(*) AS n FROM post_quota WHERE actor=?').get(user.actor.id).n,3);db.prepare('UPDATE post_quota SET created=? WHERE actor=?').run(new Date(Date.now()-3600001).toISOString(),user.actor.id);db.close();assert.equal((await request(app.base,'/api/posts',{text:'Hour expired'},login.token)).status,201);
    assert.equal((await request(app.base,'/api/billing/checkout',{},login.token)).status,503);
  }finally{await app.stop();await rm(dir,{recursive:true,force:true});}
});

test('Stripe checkout ownership, signed webhooks, paid entitlement, unlimited posting, and cancellation',async()=>{
  const calls=[];let subscription=null,checkout=null,actor=null,customer='cus_test',checkoutCount=0;
  const mock=http.createServer(async(req,res)=>{let raw='';for await(const c of req)raw+=c;const fields=new URLSearchParams(raw);const url=new URL(req.url,'http://mock');calls.push({path:url.pathname,fields});res.setHeader('Content-Type','application/json');let data={};
    if(url.pathname==='/v1/prices/price_test')data={id:'price_test',object:'price',active:true,livemode:false,currency:'usd',unit_amount:800,recurring:{interval:'month',interval_count:1}};
    else if(url.pathname==='/v1/customers'){actor=fields.get('metadata[actor]');data={id:customer,object:'customer'};}
    else if(url.pathname==='/v1/checkout/sessions'){checkoutCount++;checkout={id:'cs_test_'+checkoutCount,object:'checkout.session',status:'open',url:'https://checkout.stripe.com/test-checkout'};data=checkout;}
    else if(url.pathname.startsWith('/v1/checkout/sessions/'))data=checkout;
    else if(url.pathname==='/v1/subscriptions')data={object:'list',data:subscription?[subscription]:[],has_more:false};
    else if(url.pathname==='/v1/subscriptions/sub_test')data=subscription;
    else if(url.pathname==='/v1/billing_portal/sessions')data={id:'bps_test',url:'https://billing.stripe.com/test-portal'};
    else {res.statusCode=404;data={error:{message:'Unknown test endpoint'}};}res.end(JSON.stringify(data));});await new Promise(r=>mock.listen(0,'127.0.0.1',r));
  const secret='whsec_test_billing',signer=new StripeClient('sk_test_fixture');const app=await launch({STRIPE_SECRET_KEY:'sk_test_fixture',STRIPE_WEBHOOK_SECRET:secret,STRIPE_PRICE_ID:'price_test',STRIPE_PORTAL_CONFIGURATION_ID:'bpc_test',STRIPE_LIVEMODE:'false',PUBLIC_ORIGIN:'http://127.0.0.1:3000',ALLOW_TEST_STRIPE:'1',STRIPE_TEST_URL:'http://127.0.0.1:'+mock.address().port});
  try{const user=await register(app,'paid.demo'),other=await register(app,'outsider.demo');
    assert.equal((await request(app.base,'/api/billing/checkout',{actor:other.actor.id},user.token)).status,403);
    const first=await request(app.base,'/api/billing/checkout',{},user.token);assert.equal(first.status,200);assert.equal(first.data.url,checkout.url);
    assert.equal((await request(app.base,'/api/billing/checkout',{},user.token)).status,200);assert.equal(checkoutCount,1,'Reuse pending checkout to prevent duplicate charges');
    const sessionCall=calls.find(c=>c.path==='/v1/checkout/sessions');assert.equal(sessionCall.fields.get('line_items[0][price]'),'price_test');assert.equal(sessionCall.fields.get('subscription_data[metadata][actor]'),user.actor.id);assert.equal(sessionCall.fields.get('payment_method_types[0]'),null);assert.match(sessionCall.fields.get('integration_identifier'),/^amerika_social_plus_[a-z]{8}$/);
    assert.equal((await request(app.base,'/api/billing',null,user.token)).data.plus,false,'Redirect and pending checkout never grant benefits');
    subscription={id:'sub_test',object:'subscription',customer,livemode:false,status:'active',metadata:{app:'amerika-social',actor},items:{data:[{price:{id:'price_test'},quantity:1,current_period_end:Math.floor(Date.now()/1000)+3600}]},latest_invoice:{id:'in_test',status:'paid'},cancel_at_period_end:false};checkout.status='complete';checkout.subscription='sub_test';
    let sequence=0;const send=async(type,object,id='evt_test_'+ ++sequence)=>{const event={id,object:'event',type,livemode:false,created:Math.floor(Date.now()/1000),data:{object}};const sig=signer.webhooks.generateTestHeaderString({payload:JSON.stringify(event),secret});return request(app.base,'/api/stripe/webhook',event,null,{'Stripe-Signature':sig});};
    const forged={id:'evt_forged',livemode:false,type:'customer.subscription.created',data:{object:subscription}};assert.equal((await request(app.base,'/api/stripe/webhook',forged)).status,400);
    assert.equal((await send('checkout.session.completed',{mode:'subscription',payment_status:'unpaid',subscription:'sub_test'})).status,200);assert.equal((await request(app.base,'/api/billing',null,user.token)).data.plus,false);
    assert.equal((await send('checkout.session.completed',{mode:'subscription',payment_status:'paid',subscription:'sub_test'},'evt_paid')).status,200);assert.equal((await send('checkout.session.completed',{mode:'subscription',payment_status:'paid',subscription:'sub_test'},'evt_paid')).status,200);
    assert.equal((await request(app.base,'/api/billing',null,user.token)).data.plus,true);assert.equal((await request(app.base,'/api/me',null,user.token)).data.actor.verified,true);
    for(let i=0;i<6;i++)assert.equal((await request(app.base,'/api/posts',{text:'Plus original '+i},user.token)).status,201);
    assert.equal((await request(app.base,'/api/billing/checkout',{},user.token)).status,409);
    assert.equal((await request(app.base,'/api/billing/portal',{},other.token)).status,404);assert.equal((await request(app.base,'/api/billing/portal',{},user.token)).data.url,'https://billing.stripe.com/test-portal');
    subscription.cancel_at_period_end=true;await send('customer.subscription.updated',subscription);assert.equal((await request(app.base,'/api/billing',null,user.token)).data.plus,true,'End-of-period cancellation retains paid access');
    subscription.status='past_due';subscription.latest_invoice.status='open';await send('invoice.payment_failed',{parent:{subscription_details:{subscription:'sub_test'}}});assert.equal((await request(app.base,'/api/billing',null,user.token)).data.plus,false);assert.equal((await request(app.base,'/api/posts',{text:'Unpaid bypass'},user.token)).status,429);
    subscription.status='canceled';await send('customer.subscription.deleted',subscription);assert.equal((await request(app.base,'/api/me',null,user.token)).data.actor.verified,false);
    // A delayed old event fetches current canceled state and cannot reactivate Plus.
    await send('customer.subscription.updated',{id:'sub_test',status:'active'});assert.equal((await request(app.base,'/api/billing',null,user.token)).data.plus,false);
    assert.equal((await request(app.base,'/api/billing/checkout',{},user.token)).status,200,'Canceled accounts may subscribe again');
  }finally{await app.stop();await new Promise(r=>mock.close(r));await rm(app.dir,{recursive:true,force:true});}
});
