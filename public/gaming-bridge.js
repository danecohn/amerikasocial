/* Amerika Gaming SDK v1. Authentication remains in the parent website. */
(()=>{'use strict';if(window.AmerikaCloud)return;
 // Sandboxed games cannot install service workers. Hide the unavailable API from engine feature detection.
 try{delete Navigator.prototype.serviceWorker;}catch{}
 const MAX=1000000,host=new URL(location.href).origin;
 let channel='',state={sdk:null,storage:{},godotFiles:{}},initialized=false,sequence=0;
 const pending=new Map();let resolveReady;const ready=new Promise(resolve=>{resolveReady=resolve;});
 function clone(value){const text=JSON.stringify(value);if(text===undefined||new TextEncoder().encode(text).length>MAX)throw Error('Game save exceeds 1 MB.');return JSON.parse(text);}
 function snapshot(){return clone({version:1,sdk:state.sdk,storage:state.storage,godotFiles:state.godotFiles});}
 function commit(){if(!initialized)return Promise.reject(Error('Wait for AmerikaGame.ready before saving.'));const payload=snapshot(),id=String(++sequence);return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{pending.delete(id);reject(Error('Cloud save has not been confirmed. Check the game page’s save status.'));},20000);pending.set(id,{resolve,reject,timer});parent.postMessage({type:'amerika.game.save',channel,id,payload},host);});}
 function quietCommit(){void commit().catch(()=>{});}
 function storage(persist){let ephemeral=Object.create(null);const values=()=>persist?state.storage:ephemeral;const changed=()=>{if(persist)quietCommit();};const methods={getItem:key=>Object.hasOwn(values(),String(key))?values()[String(key)]:null,setItem:(key,value)=>{const candidate={...values(),[String(key)]:String(value)};clone(candidate);if(persist)state.storage=Object.assign(Object.create(null),candidate);else ephemeral=Object.assign(Object.create(null),candidate);changed();},removeItem:key=>{delete values()[String(key)];changed();},clear:()=>{if(persist)state.storage=Object.create(null);else ephemeral=Object.create(null);changed();},key:index=>Object.keys(values())[index]??null};return new Proxy(Object.create(null),{get:(_,key)=>key==='length'?Object.keys(values()).length:Object.hasOwn(methods,key)?methods[key]:values()[key],set:(_,key,value)=>{methods.setItem(key,value);return true;},deleteProperty:(_,key)=>{methods.removeItem(key);return true;},ownKeys:()=>Object.keys(values()),getOwnPropertyDescriptor:(_,key)=>Object.hasOwn(values(),key)?{configurable:true,enumerable:true,value:values()[key],writable:true}:undefined});}
 try{Object.defineProperty(window,'localStorage',{value:storage(true),configurable:false});Object.defineProperty(window,'sessionStorage',{value:storage(false),configurable:false});}catch{ /* Explicit SDK saving still works if a browser prevents storage replacement. */ }
 const cloud={ready,channel:'',initialFilesJSON:'{}',onFlush:null,setFiles(files){state.godotFiles=clone(files);quietCommit();}};
 window.AmerikaCloud=cloud;
 window.AmerikaGame=Object.freeze({ready,load:async()=>{await ready;return clone(state.sdk);},save:async value=>{await ready;state.sdk=clone(value);return commit();},flush:()=>commit()});
 addEventListener('message',event=>{if(event.source!==parent||event.origin!==host||!event.data||typeof event.data!=='object')return;const data=event.data;
  if(data.type==='amerika.host.init'&&!initialized&&typeof data.channel==='string'){channel=data.channel;cloud.channel=channel;const value=data.payload||{};state={sdk:value.sdk??null,storage:Object.assign(Object.create(null),value.storage||{}),godotFiles:value.godotFiles||{}};cloud.initialFilesJSON=JSON.stringify(state.godotFiles);initialized=true;resolveReady();parent.postMessage({type:'amerika.game.ready',channel},host);return;}
  if(!initialized||data.channel!==channel)return;
  if(data.type==='amerika.host.flush'){try{cloud.onFlush?.([]);}catch{}quietCommit();}
  if(data.type==='amerika.host.saved'){for(const id of data.ids||[]){const task=pending.get(id);if(task){clearTimeout(task.timer);pending.delete(id);data.error?task.reject(Error(data.error)):task.resolve({revision:data.revision});}}}
 });
 parent.postMessage({type:'amerika.game.hello'},host);
})();
