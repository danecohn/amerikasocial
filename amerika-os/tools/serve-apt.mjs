// Local test server: serves a repository directory through the same module Amerika Social uses.
import {createServer} from 'node:http';
import {createAptRepository} from '../../social-main/apt-repository.mjs';
const serve=createAptRepository({dir:process.argv[2]});
createServer((req,res)=>{const p=new URL(req.url,'http://x').pathname;if(p.startsWith('/apt/'))return serve(req,res,p);res.statusCode=404;res.end();}).listen(Number(process.argv[3]||8099),'127.0.0.1',()=>console.log('listening'));
