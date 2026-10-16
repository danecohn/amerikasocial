import {randomBytes,randomUUID,createHash,timingSafeEqual} from 'node:crypto';
const fail=(status,message)=>{throw Object.assign(Error(message),{status});};
const hash=value=>createHash('sha256').update(value).digest('hex');
const text={type:'string',minLength:1};
export const gamingMcp={name:'Amerika Gaming Publisher',instructions:'Manage only the signed-in human account’s game library. No social posts, private messages, bots, or game saves are accessible here. Build/export locally with the user’s file and command tools; this service does not compile games. Read the upload guide. Prepare a draft only when the user has authorized upload and confirmed publishing rights and submission rules. Transfer the actual self-contained browser ZIP using the one-use HTTPS PUT instructions; never put the ZIP in a tool argument. Verify upload status, then publish only on the user’s explicit instruction. Plus is required for uploads and publication. Never claim a game is published unless publish_game returns published status.',definitions:[
 ['get_gaming_account','Read the signed-in publishing account’s handle and current Plus eligibility. No private social content.','gaming.read',{}],
 ['get_game_upload_guide','Read browser ZIP requirements, cloud-save SDK guidance and the secure upload procedure.','gaming.read',{}],
 ['list_my_games','List only games owned by the signed-in human account, including draft and publication status.','gaming.read',{}],
 ['prepare_game_upload','Create a private game draft and a single-use upload credential. Requires current Plus and explicit rights/rules confirmation. The ZIP transfer does not publish the game.','gaming.publish',{title:text,description:text,controls:text,rightsConfirmed:{type:'boolean'},rulesAccepted:{type:'boolean'}},['title','description','controls','rightsConfirmed','rulesAccepted']],
 ['get_game_upload_status','Read upload validation and publication status for a game owned by this account. Does not return upload credentials.','gaming.read',{gameId:text},['gameId']],
 ['publish_game','Publish a validated browser-game draft to the public Amerika Gaming library. Requires Plus, ownership and explicit user confirmation.','gaming.publish',{gameId:text,publishConfirmed:{type:'boolean'}},['gameId','publishConfirmed']]
]};

export function createGamingPublisher(db,{gaming,plus,activeGrant,origin,now=Date.now}){
 db.exec(`CREATE TABLE IF NOT EXISTS gaming_upload_tickets(id TEXT PRIMARY KEY,secret_hash TEXT NOT NULL,actor TEXT NOT NULL,game TEXT NOT NULL,grant_id TEXT NOT NULL,expires INTEGER NOT NULL,status TEXT NOT NULL,error TEXT,created INTEGER NOT NULL);`);
 function actor(id){const a=db.prepare('SELECT * FROM actors WHERE id=?').get(id);if(!a||a.kind!=='human'||a.deleted_at||a.suspended_at)fail(403,'An active human account is required.');return a;}
 function owner(auth,write=false){if(auth?.kind!=='gaming'||!auth.oauthGrant||!activeGrant(auth.oauthGrant))fail(401,'Reconnect the Gaming publisher with OAuth.');const a=actor(auth.actor);if(write&&!plus(a.id))fail(403,'Amerika Social Plus is required to upload and publish games.');return a;}
 function owned(who,id){const row=db.prepare('SELECT * FROM gaming_games WHERE id=? AND owner=? AND official=0 AND status!=?').get(id,who,'deleted');if(!row)fail(404,'Game not found in your library.');return row;}
 function status(who,id){const row=owned(who,id),ticket=db.prepare('SELECT status,error FROM gaming_upload_tickets WHERE actor=? AND game=? ORDER BY created DESC LIMIT 1').get(who,id);return {game:gaming.mine(who).games.find(g=>g.id===id),upload:ticket||null,readyToPublish:!!row.version&&row.status==='draft',libraryUrl:origin()+'/gaming'};}
 async function request(name,args,auth){const a=owner(auth,['prepare_game_upload','publish_game'].includes(name));
  if(name==='get_gaming_account')return {id:a.id,handle:a.handle,name:a.name,kind:a.kind,plus:plus(a.id),canPublish:plus(a.id)};
  if(name==='get_game_upload_guide')return {guideUrl:origin()+'/gaming/developers',format:'Self-contained HTML5/WebGL ZIP with one index.html entry point; native EXE/APK/IPA builds are not playable here.',maxArchiveBytesExclusive:1000000000,maxExtractedBytesExclusive:1000000000,maxFiles:10000,workflow:['Build and test a browser export locally; Godot web exports must use single-threaded WebGL 2.','Confirm rights and submission rules; prepare_game_upload creates a draft.','Use a file/command tool to PUT the actual ZIP bytes to the returned uploadUrl with its Authorization header and Content-Type application/zip. Credential expires in 15 minutes and can be used once. Do not paste credentials into public messages or commit them.','Read get_game_upload_status. A successful upload remains a draft.','After the user authorizes publication, call publish_game with publishConfirmed true.'],rules:['No crypto mining','No phishing','No card fraud or testing','No spam','No piracy','No illegal content'],cloudSaves:{sdk:origin()+'/gaming/sdk.js',guide:origin()+'/gaming/developers',note:'Embed the SDK and implement its save contract. Uploading alone cannot add save support to arbitrary game code.'},buildService:false};
  if(name==='list_my_games')return gaming.mine(a.id);
  if(name==='get_game_upload_status')return status(a.id,args.gameId);
  if(name==='prepare_game_upload'){
   if(args.controls.length>500)fail(400,'Keep controls under 500 characters.');
   db.prepare('DELETE FROM gaming_upload_tickets WHERE expires<? AND status!=?').run(now()-86400000,'uploading');
   const result=gaming.create(a.id,args),id=randomUUID(),secret=randomBytes(32).toString('base64url'),expires=now()+15*60000;
   db.prepare('INSERT INTO gaming_upload_tickets VALUES (?,?,?,?,?,?,?,NULL,?)').run(id,hash(secret),a.id,result.game.id,auth.oauthGrant,expires,'pending',now());
   return {...result,uploadId:id,uploadUrl:origin()+'/api/gaming/mcp-upload/'+id,method:'PUT',headers:{Authorization:'Bearer '+secret,'Content-Type':'application/zip'},expiresAt:new Date(expires).toISOString(),maxBytesExclusive:1000000000,instruction:'PUT the ZIP file bytes using a file/command tool. This one-use credential authorizes only this game upload, not account access. The upload remains a draft until publish_game.'};
  }
  if(name==='publish_game'){if(args.publishConfirmed!==true)fail(400,'Explicit user publication confirmation is required.');const row=owned(a.id,args.gameId);if(row.status!=='draft')fail(409,'Only a validated draft can be published by this connection.');return {...gaming.manage(a.id,row.id,{action:'publish'}),libraryUrl:origin()+'/gaming'};}
  fail(400,'Unsupported Gaming tool.');
 }
 async function upload(id,credential,req){const row=db.prepare('SELECT * FROM gaming_upload_tickets WHERE id=?').get(id),digest=hash(credential||'');if(!row||row.expires<=now()||row.status!=='pending'||!timingSafeEqual(Buffer.from(digest),Buffer.from(row.secret_hash)))fail(401,'Invalid, expired or already used game upload credential.');
  const grant=activeGrant(row.grant_id);if(!grant||grant.owner!==row.actor||grant.connection.kind!=='gaming')fail(401,'The Gaming authorization was revoked. Reconnect.');actor(row.actor);if(!plus(row.actor))fail(403,'Amerika Social Plus is required to upload games.');owned(row.actor,row.game);
  if(!req.headers['content-type']?.startsWith('application/zip'))fail(415,'Send ZIP file bytes with Content-Type application/zip.');
  if(!db.prepare("UPDATE gaming_upload_tickets SET status='uploading' WHERE id=? AND status='pending'").run(id).changes)fail(409,'This upload credential is already in use.');
  try{const result=await gaming.upload(row.actor,row.game,req,{publish:false});db.prepare("UPDATE gaming_upload_tickets SET status='complete' WHERE id=?").run(id);return {...result,readyToPublish:true};}
  catch(e){db.prepare("UPDATE gaming_upload_tickets SET status='failed',error=? WHERE id=?").run(e.status?e.message:'Upload failed. Prepare a new upload and try again.',id);throw e;}
 }
 return {request,upload};
}
