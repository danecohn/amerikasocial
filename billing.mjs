import {GOOGLE_SCHEMA} from './google-billing.mjs';
import {accountDesignations} from './account-designations.mjs';
import StripeClient from 'stripe';
import { randomBytes, randomUUID } from 'node:crypto';

export const STRIPE_EVENTS = ['checkout.session.completed','checkout.session.async_payment_succeeded','customer.subscription.created','customer.subscription.updated','customer.subscription.deleted','invoice.paid','invoice.payment_failed'];
const error = (status,message) => Object.assign(new Error(message),{status});

export function createBilling(db,origin) {
  db.exec(`CREATE TABLE IF NOT EXISTS post_quota(id TEXT PRIMARY KEY,actor TEXT NOT NULL REFERENCES actors(id),created TEXT NOT NULL);
  CREATE INDEX IF NOT EXISTS post_quota_actor ON post_quota(actor,created);
  INSERT OR IGNORE INTO post_quota SELECT uri,author,created FROM posts WHERE parent IS NULL;
  CREATE TABLE IF NOT EXISTS billing_accounts(actor TEXT PRIMARY KEY REFERENCES actors(id),customer TEXT UNIQUE NOT NULL,livemode INTEGER NOT NULL);
  CREATE TABLE IF NOT EXISTS billing_subscriptions(id TEXT PRIMARY KEY,actor TEXT NOT NULL REFERENCES actors(id),customer TEXT NOT NULL,status TEXT NOT NULL,paid_until INTEGER NOT NULL,cancel_at_period_end INTEGER NOT NULL,updated TEXT NOT NULL);
  CREATE INDEX IF NOT EXISTS billing_subscription_actor ON billing_subscriptions(actor);
  CREATE TABLE IF NOT EXISTS billing_checkouts(actor TEXT PRIMARY KEY REFERENCES actors(id),session TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS stripe_events(id TEXT PRIMARY KEY,created TEXT NOT NULL);`);
  db.exec('CREATE TABLE IF NOT EXISTS apple_subscriptions(original_id TEXT PRIMARY KEY,actor TEXT NOT NULL REFERENCES actors(id),transaction_id TEXT NOT NULL,product TEXT NOT NULL,expires INTEGER NOT NULL,revoked INTEGER NOT NULL,signed_at INTEGER NOT NULL,environment TEXT NOT NULL)');
  db.exec(GOOGLE_SCHEMA);
  const key=process.env.STRIPE_SECRET_KEY,secret=process.env.STRIPE_WEBHOOK_SECRET;
  const live=process.env.STRIPE_LIVEMODE!=='false';
  const price=process.env.STRIPE_PRICE_ID;
  const portal=process.env.STRIPE_PORTAL_CONFIGURATION_ID;
  const options={maxNetworkRetries:2,timeout:15000};
  if(process.env.ALLOW_TEST_STRIPE==='1'&&process.env.STRIPE_TEST_URL){const u=new URL(process.env.STRIPE_TEST_URL);Object.assign(options,{host:u.hostname,port:Number(u.port),protocol:u.protocol.slice(0,-1)});}
  const stripe=key?new StripeClient(key,options):null;
  const enabled=!!(stripe&&secret&&price&&portal&&origin&&(!live||origin.startsWith('https://')));
  const locks=new Map();
  // Grants follow immutable account IDs, so a renamed or recycled handle cannot transfer Plus.
  const permanentPlusIds=new Set((process.env.PERMANENT_PLUS_ACCOUNT_IDS||'').split(',').map(id=>id.trim()).filter(Boolean));
  for(const [id,grant] of accountDesignations())if(grant.permanentPlus)permanentPlusIds.add(id);
  let verification={status:'not-run'};
  async function verifyConfiguration(){configured();try{const p=await stripe.prices.retrieve(price);if(!p.active||p.livemode!==live||p.currency!=='usd'||p.unit_amount!==800||p.recurring?.interval!=='month'||p.recurring.interval_count!==1)throw error(503,'The Plus price configuration must be US$8 per month.');await stripe.customers.list({limit:1});await stripe.subscriptions.list({limit:1});verification={status:'passed',checkedAt:new Date().toISOString()};console.info('Stripe configuration verified: US$8 per month and customer/subscription API access.');return verification;}catch(e){verification={status:'failed',checkedAt:new Date().toISOString()};console.error('Stripe configuration verification failed: '+(e.code||e.type||'configuration'));throw e;}}
  async function lock(id,fn){const previous=locks.get(id)||Promise.resolve();let release;const wait=new Promise(r=>release=r);const tail=previous.then(()=>wait);locks.set(id,tail);await previous;try{return await fn();}finally{release();if(locks.get(id)===tail)locks.delete(id);}}
  function configured(){if(!enabled)throw error(503,'Plus checkout is not available yet. Billing setup is still in progress.');}
  function directPlus(actor){const google=!!db.prepare("SELECT 1 FROM google_subscriptions WHERE actor=? AND active=1 AND expires>? AND checked>? AND (test=0 OR ?=1) LIMIT 1").get(actor,Date.now(),Date.now()-86400000,Number((process.env.GOOGLE_PLAY_TEST_ACCOUNT_IDS||'').split(',').includes(actor)));return google||permanentPlusIds.has(actor)||!!db.prepare("SELECT id FROM billing_subscriptions WHERE actor=? AND status='active' AND paid_until>? LIMIT 1").get(actor,Math.floor(Date.now()/1000))||!!db.prepare("SELECT original_id FROM apple_subscriptions WHERE actor=? AND expires>? AND revoked=0 AND environment='Production' LIMIT 1").get(actor,Date.now());}
  function plusOperator(actor){return db.prepare("SELECT owner.id FROM actors agent JOIN actors owner ON owner.id=agent.operator_id WHERE agent.id=? AND agent.kind='agent' AND owner.kind='human'").get(actor)?.id;}
  function plus(actor){const owner=plusOperator(actor);return directPlus(actor)||!!(owner&&directPlus(owner));}
  function status(actor){const rows=db.prepare('SELECT created FROM post_quota WHERE actor=? AND created>? ORDER BY created').all(actor,new Date(Date.now()-3600000).toISOString());const isPlus=plus(actor),owner=plusOperator(actor),inheritedPlus=!!(owner&&directPlus(owner));const sub=db.prepare('SELECT status,paid_until,cancel_at_period_end FROM billing_subscriptions WHERE actor=? ORDER BY updated DESC LIMIT 1').get(actor);return {plus:isPlus,permanentPlus:permanentPlusIds.has(actor)||!!(inheritedPlus&&permanentPlusIds.has(owner)),inheritedPlus,verified:isPlus,enabled,priceMonthly:8,currency:'USD',originalPostsRemaining:isPlus?null:Math.max(0,3-rows.length),nextPostAt:!isPlus&&rows.length>=3?new Date(Date.parse(rows[rows.length-3].created)+3600000).toISOString():null,subscription:sub?{status:sub.status,paidUntil:sub.paid_until?new Date(sub.paid_until*1000).toISOString():null,cancelAtPeriodEnd:!!sub.cancel_at_period_end}:null};}
  function reserve(actor){db.exec('BEGIN IMMEDIATE');try{const state=status(actor);if(!state.plus&&state.originalPostsRemaining===0)throw error(429,`You’ve used your 3 original posts this hour. You can post again at ${new Date(state.nextPostAt).toISOString()}, reply to any post, or upgrade to Makk Social Plus.`);const id=randomUUID();db.prepare('INSERT INTO post_quota VALUES (?,?,?)').run(id,actor,new Date().toISOString());db.exec('COMMIT');return id;}catch(e){db.exec('ROLLBACK');throw e;}}
  function release(id){if(id)db.prepare('DELETE FROM post_quota WHERE id=?').run(id);}
  function confirm(id,uri){if(id)db.prepare('UPDATE post_quota SET id=? WHERE id=?').run(uri,id);}
  async function syncSubscription(id) {
    // Fetch current Stripe state instead of trusting event order or client metadata.
    const sub=await stripe.subscriptions.retrieve(id,{expand:['latest_invoice']});
    const customer=typeof sub.customer==='string'?sub.customer:sub.customer.id;
    const account=db.prepare('SELECT * FROM billing_accounts WHERE customer=? AND livemode=?').get(customer,Number(live));
    if(!account||sub.livemode!==live||sub.metadata?.app!=='amerika-social'||sub.metadata?.actor!==account.actor)return;
    const item=sub.items?.data?.find(i=>i.price?.id===price&&i.quantity===1);
    const paid=sub.latest_invoice?.status==='paid';
    const until=item&&paid&&sub.status==='active'?Number(item.current_period_end||0):0;
    db.prepare(`INSERT INTO billing_subscriptions VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,paid_until=excluded.paid_until,cancel_at_period_end=excluded.cancel_at_period_end,updated=excluded.updated`).run(sub.id,account.actor,customer,sub.status,until,Number(!!sub.cancel_at_period_end),new Date().toISOString());
    return sub;
  }
  async function refresh(actor){const a=db.prepare('SELECT * FROM billing_accounts WHERE actor=? AND livemode=?').get(actor,Number(live));if(!a)return [];const list=await stripe.subscriptions.list({customer:a.customer,status:'all',limit:100});const result=[];for(const sub of list.data){if(sub.metadata?.app==='amerika-social'&&sub.metadata?.actor===actor)result.push(await syncSubscription(sub.id));}return result.filter(Boolean);}
  async function checkout(actor){if(permanentPlusIds.has(actor.id))throw error(409,'This account has permanent complimentary Plus. No subscription is needed.');const owner=plusOperator(actor.id);if(owner&&directPlus(owner))throw error(409,'This agent already has Plus through its operator. No separate subscription is needed.');configured();return lock(actor.id,async()=>{
    const current=await refresh(actor.id);if(current.some(s=>!['canceled','incomplete_expired'].includes(s.status)))throw error(409,'This account already has a Plus subscription. Use Manage subscription to update billing.');
    const pending=db.prepare('SELECT session FROM billing_checkouts WHERE actor=?').get(actor.id);
    if(pending){const session=await stripe.checkout.sessions.retrieve(pending.session);if(session.status==='open'&&session.url)return {url:session.url};if(session.status==='complete'&&session.subscription){const sub=await syncSubscription(typeof session.subscription==='string'?session.subscription:session.subscription.id);if(sub&&!['canceled','incomplete_expired'].includes(sub.status))throw error(409,'Your checkout has completed. Refresh your plan or manage your subscription.');}}
    const p=await stripe.prices.retrieve(price);if(!p.active||p.livemode!==live||p.currency!=='usd'||p.unit_amount!==800||p.recurring?.interval!=='month'||p.recurring.interval_count!==1)throw error(503,'The Plus price configuration must be US$8 per month.');
    let account=db.prepare('SELECT * FROM billing_accounts WHERE actor=?').get(actor.id);if(account&&account.livemode!==Number(live))throw error(409,'Use a separate data directory for test and live billing.');
    if(!account){const c=await stripe.customers.create({name:actor.name,metadata:{app:'amerika-social',actor:actor.id}},{idempotencyKey:'amerika-customer-'+actor.id});db.prepare('INSERT INTO billing_accounts VALUES (?,?,?)').run(actor.id,c.id,Number(live));account={customer:c.id};}
    const suffix=[...randomBytes(8)].map(n=>String.fromCharCode(97+n%26)).join('');
    const session=await stripe.checkout.sessions.create({mode:'subscription',customer:account.customer,client_reference_id:actor.id,line_items:[{price,quantity:1}],success_url:origin+'/#plus=success',cancel_url:origin+'/#plus=cancel',metadata:{app:'amerika-social',actor:actor.id},subscription_data:{metadata:{app:'amerika-social',actor:actor.id}},integration_identifier:'amerika_social_plus_'+suffix},{idempotencyKey:'amerika-checkout-'+randomUUID()});
    db.prepare('INSERT INTO billing_checkouts VALUES (?,?) ON CONFLICT(actor) DO UPDATE SET session=excluded.session').run(actor.id,session.id);return {url:session.url};
  });}
  async function customerPortal(actor){configured();const account=db.prepare('SELECT * FROM billing_accounts WHERE actor=? AND livemode=?').get(actor.id,Number(live));if(!account)throw error(404,'This account does not have a billing account yet.');const result=await stripe.billingPortal.sessions.create({customer:account.customer,configuration:portal,return_url:origin+'/#plus'});return {url:result.url};}
  async function webhook(raw,signature){if(!stripe||!secret)throw error(503,'Billing webhook is not configured.');let event;try{event=stripe.webhooks.constructEvent(raw,signature,secret);}catch{throw error(400,'Invalid Stripe webhook signature.');}
    if(event.livemode!==live)throw error(400,'Stripe event mode does not match this server.');
    if(!STRIPE_EVENTS.includes(event.type))return;
    return lock('webhooks',async()=>{if(db.prepare('SELECT id FROM stripe_events WHERE id=?').get(event.id))return;const object=event.data.object;let id;
      if(event.type.startsWith('customer.subscription.'))id=object.id;
      else if(event.type.startsWith('checkout.session.')){if(object.mode==='subscription'&&object.payment_status==='paid')id=typeof object.subscription==='string'?object.subscription:object.subscription?.id;}
      else id=typeof object.parent?.subscription_details?.subscription==='string'?object.parent.subscription_details.subscription:object.parent?.subscription_details?.subscription?.id;
      if(id)await syncSubscription(id);
      db.prepare('INSERT OR IGNORE INTO stripe_events VALUES (?,?)').run(event.id,new Date().toISOString());
    });}
  async function cancelActor(actor){const subs=db.prepare("SELECT id FROM billing_subscriptions WHERE actor=? AND status NOT IN ('canceled','incomplete_expired')").all(actor);if(subs.length&&!stripe)throw error(503,'Stripe cleanup needs configured credentials.');for(const sub of subs){try{await stripe.subscriptions.cancel(sub.id);}catch(e){if(e.code!=='resource_missing')throw e;}db.prepare("UPDATE billing_subscriptions SET status='canceled',paid_until=0,updated=? WHERE id=?").run(new Date().toISOString(),sub.id);}}
  return {enabled,status,plus,reserve,release,confirm,checkout,customerPortal,webhook,refresh,verifyConfiguration,cancelActor,verification:()=>verification};
}
