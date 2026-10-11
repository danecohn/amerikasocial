import { backup, DatabaseSync } from 'node:sqlite';
import { mkdir, readFile, readdir, unlink, rename } from 'node:fs/promises';
import { join } from 'node:path';
import { randomBytes, createCipheriv, createDecipheriv } from 'node:crypto';
import { S3Client, PutObjectCommand, GetObjectCommand, ListObjectsV2Command, DeleteObjectCommand } from '@aws-sdk/client-s3';
export function encryptBackup(bytes,key){const iv=randomBytes(12),c=createCipheriv('aes-256-gcm',Buffer.from(key,'hex'),iv);return Buffer.concat([Buffer.from('ASB1'),iv,c.update(bytes),c.final(),c.getAuthTag()]);}
export function decryptBackup(bytes,key){if(bytes.subarray(0,4).toString()!=='ASB1')throw Error('Invalid backup');const c=createDecipheriv('aes-256-gcm',Buffer.from(key,'hex'),bytes.subarray(4,16));c.setAuthTag(bytes.subarray(-16));return Buffer.concat([c.update(bytes.subarray(16,-16)),c.final()]);}
export function createOperations(db,dir){
  const folder=join(dir,'backups');let running=false;
  const bucket=process.env.BACKUP_S3_BUCKET;
  const key=process.env.BACKUP_ENCRYPTION_KEY;
  const remote=!!(bucket&&process.env.BACKUP_S3_ENDPOINT&&process.env.BACKUP_S3_ACCESS_KEY_ID&&process.env.BACKUP_S3_SECRET_ACCESS_KEY&&/^[a-f0-9]{64}$/i.test(key||''));
  const s3=remote?new S3Client({endpoint:process.env.BACKUP_S3_ENDPOINT,region:process.env.BACKUP_S3_REGION||'auto',forcePathStyle:process.env.BACKUP_S3_PATH_STYLE==='true',credentials:{accessKeyId:process.env.BACKUP_S3_ACCESS_KEY_ID,secretAccessKey:process.env.BACKUP_S3_SECRET_ACCESS_KEY}}):null;
  let last=db.prepare("SELECT value FROM settings WHERE key='last_backup'").get()?.value||null;
  let verified=db.prepare("SELECT value FROM settings WHERE key='backup_verified'").get()?.value||null;
  async function take(){if(running)throw Error('A backup is already running');running=true;let temp;try{await mkdir(folder,{recursive:true});const name='amerika-'+new Date().toISOString().replace(/[:.]/g,'-')+'.sqlite';temp=join(folder,name+'.partial');await backup(db,temp);const check=new DatabaseSync(temp,{readOnly:true});try{if(check.prepare('PRAGMA quick_check').get().quick_check!=='ok')throw Error('Backup integrity check failed');}finally{check.close();}const bytes=await readFile(temp);if(s3){await s3.send(new PutObjectCommand({Bucket:bucket,Key:'amerika/'+name+'.enc',Body:encryptBackup(bytes,key),ContentType:'application/octet-stream'}));const retrieved=await s3.send(new GetObjectCommand({Bucket:bucket,Key:'amerika/'+name+'.enc'}));const restored=decryptBackup(Buffer.from(await retrieved.Body.transformToByteArray()),key);if(!restored.equals(bytes))throw Error('Remote backup restore verification failed');verified=new Date().toISOString();db.prepare("INSERT INTO settings VALUES ('backup_verified',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value").run(verified);}
    await rename(temp,join(folder,name));temp=null;last=new Date().toISOString();db.prepare("INSERT INTO settings VALUES ('last_backup',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value").run(last);
    const files=(await readdir(folder)).filter(f=>/^amerika-.*\.sqlite$/.test(f)).sort();for(const file of files.slice(0,-7))await unlink(join(folder,file));
    if(s3){const listed=await s3.send(new ListObjectsV2Command({Bucket:bucket,Prefix:'amerika/'}));const old=(listed.Contents||[]).filter(o=>o.Key.endsWith('.enc')).sort((a,b)=>b.LastModified-a.LastModified).slice(30);for(const o of old)await s3.send(new DeleteObjectCommand({Bucket:bucket,Key:o.Key}));}
    console.info('Backup completed: '+(remote?'encrypted copy uploaded to separate storage':'local snapshot only'));
    return {created:last,remote};}finally{if(temp)await unlink(temp).catch(()=>{});running=false;}}
  function status(){return {lastBackup:last,remoteVerifiedAt:verified,remoteConfigured:remote,running,overdue:!last||Date.now()-Date.parse(last)>26*3600000};}
  let timer;
  return {take,status,start:()=>{if(!timer){timer=setInterval(()=>take().catch(()=>console.error('Scheduled backup failed; check backup configuration.')),86400000);timer.unref();}return take().catch(()=>console.error('Startup backup failed; check backup configuration.'));}};
}
