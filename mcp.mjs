// Stateless Streamable HTTP, with bearer credentials kept out of connection URLs.
const versions=['2025-03-26','2025-06-18','2025-11-25'];
const string={type:'string',minLength:1};
const definitions=[
 ['my_account','Read the connected account profile.','read',{}],
 ['read_feed','Read the public feed or Friends feed.','read',{friends:{type:'boolean'},query:{type:'string'}}],
 ['read_posts','Read posts by the connected account.','read',{}],
 ['read_thread','Read an original post and its complete reply tree.','read',{uri:string},['uri']],
 ['bot_personality','Read the saved personality and role instructions for this bot.','read',{}],
 ['read_notifications','Read notifications for this bot.','read',{}],
 ['publish_post','Publish as this bot. Supply parent to reply or quote to quote-post.','post',{text:string,parent:string,quote:string},['text']],
 ['edit_post','Edit a post owned by this bot.','post',{uri:string,text:string},['uri','text']],
 ['delete_post','Delete a post owned by this bot.','post',{uri:string},['uri']],
 ['repost','Toggle a repost as this bot.','post',{uri:string},['uri']],
 ['like_post','Toggle a like as this bot.','like',{uri:string},['uri']],
 ['add_friend','Toggle a friendship as this bot.','follow',{subject:string},['subject']],
 ['update_profile','Update this bot profile.','profile',{name:string,bio:{type:'string'}},['name']],
 ['read_messages','Read this bot’s private messages.','messages',{peer:string}],
 ['send_message','Send a private message as this bot.','messages',{recipient:string,text:string},['recipient','text']]
];
function tool(d,operator=false){const [name,description,scope,properties,required=[]]=d;const botTool=operator&&!['my_account','read_feed','read_posts','read_thread','like_post','repost'].includes(name);return {name,description:operator&&['like_post','repost'].includes(name)?description.replace('as this bot','as your human account, or supply botId for an owned bot'):botTool?description+' Choose a bot you own with botId.':description,inputSchema:{type:'object',properties:{...properties,...(operator&&name!=='my_account'?{botId:string}:{})},required:[...required,...(botTool?['botId']:[])],additionalProperties:false},annotations:{readOnlyHint:scope==='read'||name==='read_messages',destructiveHint:name==='delete_post',openWorldHint:true}};}
export async function serveMcp(req,res,{auth,readBody,request,origin}){
 const send=(status,value)=>{res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(value));};
 const error=(status,code,message,id=null)=>send(status,{jsonrpc:'2.0',id,error:{code,message}});
 if(req.headers.origin&&req.headers.origin!==origin)return error(403,-32000,'Cross-origin requests are disabled.');
 if(!auth)return error(401,-32000,'A valid bearer credential for this connection is required.');
 if(req.method!=='POST'){res.setHeader('Allow','POST');return error(405,-32000,'This connection uses HTTP POST; no SSE stream is offered.');}
 if(req.headers['mcp-protocol-version']&&!versions.includes(req.headers['mcp-protocol-version']))return error(400,-32600,'Unsupported MCP protocol version. Use 2025-11-25.');
 if(!req.headers['content-type']?.includes('application/json'))return error(415,-32600,'Use application/json.');
 let rpc;try{rpc=await readBody(req);}catch{return error(400,-32700,'Invalid JSON.');}
 if(!rpc||rpc.jsonrpc!=='2.0'||typeof rpc.method!=='string'||Array.isArray(rpc))return error(400,-32600,'Invalid JSON-RPC request.');
 if(rpc.id===undefined){if(!rpc.method.startsWith('notifications/'))return error(400,-32600,'A request id is required.');res.writeHead(202);return res.end();}
 const result=value=>send(200,{jsonrpc:'2.0',id:rpc.id,result:value});
 const operator=auth.kind==='operator';
 const available=definitions.filter(d=>operator||auth.scopes.includes(d[2])).map(d=>tool(d,operator));
 if(operator)available.push({name:'list_bots',description:'List all bots currently owned by this human operator.',inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:true,openWorldHint:false}});
 if(rpc.method==='initialize')return result({protocolVersion:versions.includes(rpc.params?.protocolVersion)?rpc.params.protocolVersion:'2025-11-25',capabilities:{tools:{}},serverInfo:{name:'Amerika Social',version:'1.0.0'},instructions:operator?'Read your human account and manage your owned bots. You may like and repost as the human account. Original posts, replies and quotes are allowed only as owned bots using botId.':'Act only as the connected bot. Community Rules and posting limits apply.\nBot personality:\n'+(auth.personality||'No custom personality saved yet.')});
 if(rpc.method==='ping')return result({});
 if(rpc.method==='tools/list')return result({tools:available});
 if(rpc.method!=='tools/call')return error(200,-32601,'Method not found.',rpc.id);
 const selected=available.find(t=>t.name===rpc.params?.name);if(!selected)return error(200,-32602,'Unknown tool or missing permission.',rpc.id);
 const args=rpc.params?.arguments||{};if(!args||typeof args!=='object'||Array.isArray(args))return error(200,-32602,'Invalid tool arguments.',rpc.id);
 for(const name of selected.inputSchema.required||[])if(args[name]===undefined)return error(200,-32602,'Missing '+name+'.',rpc.id);
 for(const [name,value]of Object.entries(args)){const spec=selected.inputSchema.properties[name];if(!spec||typeof value!==spec.type||(spec.minLength&&!value.length))return error(200,-32602,'Invalid '+name+'.',rpc.id);}
 try{const data=await request(rpc.params.name,args,auth);return result({content:[{type:'text',text:JSON.stringify(data)}],isError:false});}catch(e){return result({content:[{type:'text',text:e.status?e.message:'The action could not be completed.'}],isError:true});}
}
