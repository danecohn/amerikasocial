import {randomBytes,createHash} from 'node:crypto';
export async function authorizeMcp(base,key,owner,scope){
 const redirect='http://127.0.0.1:9876/callback';
 const client=await (await fetch(base+'/oauth/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({client_name:'MCP test client',redirect_uris:[redirect]})})).json();
 const verifier=randomBytes(32).toString('base64url'),challenge=createHash('sha256').update(verifier).digest('base64url');
 const params=new URLSearchParams({client_id:client.client_id,response_type:'code',redirect_uri:redirect,resource:key.mcpUrl,state:'test-state',code_challenge_method:'S256',code_challenge:challenge,...(scope?{scope}:{})});
 const authorization=await fetch(base+'/oauth/authorize?'+params,{redirect:'manual'});
 if(authorization.status!==302)throw Error(JSON.stringify(await authorization.json()));
 const id=new URL(authorization.headers.get('location')).hash.slice(7);
 const approval=await fetch(base+'/api/oauth/approve',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+owner},body:JSON.stringify({id,approve:true})});
 const approved=await approval.json();if(!approval.ok)throw Error(JSON.stringify(approved));
 const code=new URL(approved.redirect).searchParams.get('code');
 const response=await fetch(base+'/oauth/token',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({grant_type:'authorization_code',client_id:client.client_id,redirect_uri:redirect,resource:key.mcpUrl,code,code_verifier:verifier})});
 const tokens=await response.json();if(!response.ok)throw Error(JSON.stringify(tokens));return {...tokens,client_id:client.client_id,id,code,verifier,redirect};
}
