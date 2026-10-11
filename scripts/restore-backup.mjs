import { readFile,writeFile,access } from 'node:fs/promises';
import { DatabaseSync } from 'node:sqlite';
import { decryptBackup } from '../operations.mjs';
const [source,target]=process.argv.slice(2);
if(!source||!target)throw Error('Usage: BACKUP_ENCRYPTION_KEY=... node scripts/restore-backup.mjs downloaded.sqlite.enc new-output.sqlite');
try{await access(target);throw Error('Refusing to overwrite an existing file. Choose a new output path.');}catch(e){if(e.code!=='ENOENT')throw e;}
const bytes=decryptBackup(await readFile(source),process.env.BACKUP_ENCRYPTION_KEY);
await writeFile(target,bytes,{flag:'wx',mode:0o600});
const db=new DatabaseSync(target,{readOnly:true});try{if(db.prepare('PRAGMA integrity_check').get().integrity_check!=='ok')throw Error('Restored database failed integrity checking.');console.log('Backup restored and integrity checked. Keep the service stopped before replacing its database.');}finally{db.close();}
