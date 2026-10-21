'use strict';
const product=document.body.dataset.product;
const families=[{id:'windows',label:'Windows',glyph:'▦',platforms:['windows','win']},{id:'macos',label:'macOS',glyph:'⌘',platforms:['macos','mac']},{id:'linux',label:'Linux',glyph:'>_',platforms:['linux']}];
function el(tag,props={},...children){const n=document.createElement(tag);for(const[k,v]of Object.entries(props)){if(k==='text')n.textContent=v;else if(k==='class')n.className=v;else n.setAttribute(k,v);}for(const c of children)n.append(c);return n;}
function formatBytes(n){return(n/1048576).toFixed(1)+' MB';}
async function load(){
 const response=await fetch('/api/software-downloads?product='+encodeURIComponent(product));if(!response.ok)throw Error('Release information unavailable.');const data=await response.json();const cards=document.querySelector('#download-cards');cards.replaceChildren();
 for(const family of families){const card=el('article',{class:'card'},el('div',{class:'platform','aria-hidden':'true',text:family.glyph}),el('h3',{text:family.label}));
  for(const arch of ['x64','arm64']){const title=arch==='arm64'?(family.id==='macos'?'Apple Silicon · ARM64':'ARM64'):(family.id==='macos'?'Intel · x64':'Intel / AMD · x64');const group=el('div',{class:'arch-download'},el('h4',{text:title}));
   const asset=data.assets.find(x=>family.platforms.some(p=>x.name.toLowerCase().includes('-'+p+'-'))&&x.name.toLowerCase().includes('-'+arch+'.'));
   if(asset){const url=new URL(asset.url);if(url.origin!=='https://github.com')continue;const extension=asset.name.endsWith('.tar.gz')?'TAR.GZ':asset.name.split('.').pop().toUpperCase();group.append(el('a',{class:'button primary',href:asset.url,text:'Download '+family.label+' '+(arch==='arm64'?'ARM64':'x64')+' ↓'}),el('small',{text:formatBytes(asset.size)+' · '+extension+' · '+asset.version}),el('a',{class:'checksum',href:asset.url+'.sha256',text:'SHA-256 checksum'}));}
   else group.append(el('div',{class:'build-pending',text:data.status==='unavailable'?'Release status unavailable. Check the releases page.':'Build pending publication'}));card.append(group);
  }
  cards.append(card);
 }
 const count=data.assets.length;document.querySelector('#release-status').textContent=count?(count+' platform download'+(count===1?' is':'s are')+' available. Other builds appear here after validation and publication.'):'The first platform builds are being prepared. Published downloads appear here automatically; there are no placeholder download links.';
 if(!count){document.querySelector('#release-status').append(' ',el('a',{href:data.repository+'/actions',text:'View build progress ↗'}));}
 if(count<6)setTimeout(()=>load().catch(()=>{}),45000);
}
load().catch(()=>{document.querySelector('#release-status').replaceChildren(el('span',{text:'Download status is temporarily unavailable. '}),el('a',{href:'https://github.com/danecohn/'+(product==='office'?'AmerikaOffice':'AmerikaVenture')+'/releases',text:'View published releases ↗'}));});
