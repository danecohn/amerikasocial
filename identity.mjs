// AltStack account provider. Protocol handling is delegated to oidc-provider.
import Provider from 'oidc-provider';
import {createHash,generateKeyPairSync,createPrivateKey,sign,randomBytes} from 'node:crypto';
import {existsSync,readFileSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';

export function createIdentity({db,dir,origin,warehouseOrigin,clientSecret,cookieKey,readSession,account,plus,prepare=async()=>{},mailOrigin,mailClientSecret}){
 if(!cookieKey||(!warehouseOrigin&&!mailOrigin))return null;
 const issuer=origin+'/sso',redirect=warehouseOrigin?new URL('/apps/user_oidc/code',warehouseOrigin).href:null;
 db.exec(`CREATE TABLE IF NOT EXISTS identity_records(model TEXT NOT NULL,id TEXT NOT NULL,payload TEXT NOT NULL,expires INTEGER NOT NULL,PRIMARY KEY(model,id));
 CREATE TABLE IF NOT EXISTS identity_accounts(uid TEXT PRIMARY KEY,actor TEXT UNIQUE NOT NULL);`);
 class Adapter{
  constructor(model){this.model=model;}
  async upsert(id,payload,expiresIn){db.prepare('INSERT INTO identity_records VALUES(?,?,?,?) ON CONFLICT(model,id) DO UPDATE SET payload=excluded.payload,expires=excluded.expires').run(this.model,id,JSON.stringify(payload),Date.now()+(expiresIn||86400)*1000);}
  async find(id){const r=db.prepare('SELECT payload FROM identity_records WHERE model=? AND id=? AND expires>?').get(this.model,id,Date.now());return r?JSON.parse(r.payload):undefined;}
  async findByUid(uid){return this.#find('uid',uid);}
  async findByUserCode(code){return this.#find('userCode',code);}
  #find(field,value){const r=db.prepare('SELECT payload FROM identity_records WHERE model=? AND expires>? AND json_extract(payload,?)=?').get(this.model,Date.now(),'$.'+field,value);return r?JSON.parse(r.payload):undefined;}
  async destroy(id){db.prepare('DELETE FROM identity_records WHERE model=? AND id=?').run(this.model,id);}
  async consume(id){db.prepare("UPDATE identity_records SET payload=json_set(payload,'$.consumed',?) WHERE model=? AND id=?").run(Math.floor(Date.now()/1000),this.model,id);}
  async revokeByGrantId(id){db.prepare("DELETE FROM identity_records WHERE json_extract(payload,'$.grantId')=?").run(id);}
 }
 const keyFile=join(dir,'altstack-identity-key.json');let key;
 if(existsSync(keyFile))key=JSON.parse(readFileSync(keyFile,'utf8'));
 else{const pair=generateKeyPairSync('rsa',{modulusLength:3072});key=pair.privateKey.export({format:'jwk'});key.kid=randomBytes(16).toString('hex');key.alg='RS256';key.use='sig';writeFileSync(keyFile,JSON.stringify(key),{mode:0o600,flag:'wx'});}
 const uidFor=id=>'ast_'+createHash('sha256').update(id).digest('hex').slice(0,40);
 function enroll(id){const uid=uidFor(id);db.prepare('INSERT OR IGNORE INTO identity_accounts VALUES(?,?)').run(uid,id);return uid;}
 function claims(id){const a=account(id);if(!a||a.kind!=='human'||a.deleted_at||a.suspended_at)throw Error('Account unavailable');return {sub:enroll(id),name:a.name,preferred_username:a.handle,altstack_actor:a.id,quota:String(plus(a.id)?8_000_000_000:2_000_000_000),country:a.country_code||null};}
 const provider=new Provider(issuer,{
  adapter:Adapter,jwks:{keys:[key]},cookies:{keys:[cookieKey]},
  clients:[...(warehouseOrigin&&clientSecret?[{client_id:'altstack-warehouse',client_secret:clientSecret,redirect_uris:[redirect],response_types:['code'],grant_types:['authorization_code'],token_endpoint_auth_method:'client_secret_basic',id_token_signed_response_alg:'RS256'}]:[]),...(mailOrigin&&mailClientSecret?[{client_id:'altstack-mail',client_secret:mailClientSecret,redirect_uris:[new URL('/auth/callback',mailOrigin).href],response_types:['code'],grant_types:['authorization_code'],token_endpoint_auth_method:'client_secret_basic',id_token_signed_response_alg:'RS256'}]:[])],
  claims:{openid:['sub'],profile:['name','preferred_username','country'],quota:['quota','altstack_actor']},scopes:['openid','profile','quota'],
  features:{claimsParameter:{enabled:true},devInteractions:{enabled:false},registration:{enabled:false},resourceIndicators:{enabled:false}},
  pkce:{required:()=>true},ttl:{AccessToken:300,AuthorizationCode:60,IdToken:300,Interaction:600,Session:86400,Grant:86400},
  interactions:{url:(ctx,interaction)=>'/sso/interaction/'+interaction.uid},
  async findAccount(ctx,uid){const row=db.prepare('SELECT actor FROM identity_accounts WHERE uid=?').get(uid);if(!row)return undefined;return {accountId:uid,claims:async()=>claims(row.actor)};},
  extraTokenClaims:async(ctx,token)=>{const row=db.prepare('SELECT actor FROM identity_accounts WHERE uid=?').get(token.accountId);return row?claims(row.actor):{};},
 });
 provider.proxy=true;
 const callback=provider.callback();
 function warehouseToken(actor){const now=Math.floor(Date.now()/1000),head=Buffer.from(JSON.stringify({alg:'RS256',typ:'at+jwt',kid:key.kid})).toString('base64url'),body=Buffer.from(JSON.stringify({...claims(actor.id),iss:issuer,aud:'altstack-warehouse',azp:'altstack-warehouse',iat:now,exp:now+300,jti:randomBytes(16).toString('hex'),scope:'openid profile quota'})).toString('base64url');const unsigned=head+'.'+body;return unsigned+'.'+sign('RSA-SHA256',Buffer.from(unsigned),createPrivateKey({key,format:'jwk'})).toString('base64url');}
 async function confirm(req,res){
  if(req.headers.origin!==origin)throw Object.assign(Error('Request origin rejected.'),{status:403});
  const chunks=[];let length=0;for await(const chunk of req){length+=chunk.length;if(length>8192)throw Object.assign(Error('Request too large.'),{status:413});chunks.push(chunk);}const fields=new URLSearchParams(Buffer.concat(chunks).toString());
  const s=readSession(fields.get('altstack_session'));if(!s||s.keyId)throw Object.assign(Error('Sign in with your AltStack account.'),{status:401});
  const a=account(s.actor);if(!a||a.kind!=='human'||a.deleted_at||a.suspended_at)throw Object.assign(Error('This account cannot sign in.'),{status:403});
  const details=await provider.interactionDetails(req,res);await prepare(a,details.params.client_id);const uid=enroll(a.id);let grant;
  if(details.grantId)grant=await provider.Grant.find(details.grantId);
  if(!grant)grant=new provider.Grant({accountId:uid,clientId:details.params.client_id});
  if(details.prompt.details.missingOIDCScope)grant.addOIDCScope(details.prompt.details.missingOIDCScope.join(' '));
  if(details.prompt.details.missingOIDCClaims)grant.addOIDCClaims(details.prompt.details.missingOIDCClaims);
  // The only configured client receives the explicitly listed identity and quota claims.
  grant.addOIDCScope('openid profile quota');const grantId=await grant.save();
  await provider.interactionFinished(req,res,{login:{accountId:uid},consent:{grantId}},{mergeWithLastSubmission:true});
 }
 return {provider,warehouseToken,details:(req,res)=>provider.interactionDetails(req,res),async handle(req,res){const original=req.url,originalBase=req.baseUrl,originalUrl=req.originalUrl;req.originalUrl=original;req.baseUrl='/sso';req.url=req.url.replace(/^\/sso(?=\/|\?|$)/,'')||'/';try{await callback(req,res);}finally{req.url=original;req.baseUrl=originalBase;req.originalUrl=originalUrl;}},confirm};
}

