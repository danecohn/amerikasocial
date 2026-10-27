import {verifiedReleases} from "./software-release-catalog.mjs";
const retired={social:new Set(['altstack-social-v1.1.1']),venture:new Set(['altstack-venture-zen-v1.23.4b-1']),mail:new Set(['altstack-mail-v1.0.0'])};
const products={lookout:'danecohn/lookout',mind:'danecohn/artemismind',prompter:'danecohn/artemisprompter',gameproducer:'danecohn/GameProducer',social:'danecohn/AmerikaWindows',venture:'danecohn/AmerikaVenture',office:'danecohn/AmerikaOffice',mail:'danecohn/AltStackMail'};
export function createSoftwareDownloads({request=fetch,now=()=>Date.now(),catalog=verifiedReleases}={}){
 const cache=new Map();
 return async function releases(product){
  const repo=products[product];if(!repo)throw Object.assign(Error('Unknown product.'),{status:404});
  const previous=cache.get(product);if(previous&&previous.until>now())return previous.data;
  try{
   const response=await request(`https://api.github.com/repos/${repo}/releases?per_page=5`,{headers:{Accept:'application/vnd.github+json','User-Agent':'AltStack-Software-Downloads'},signal:AbortSignal.timeout(10000)});
   if(!response.ok)throw Error('Release information is temporarily unavailable.');
   const list=await response.json();if(!Array.isArray(list))throw Error('Invalid release information.');
   const data=releaseData(product,repo,list);cache.set(product,{data,until:now()+(data.assets.length?180000:30000)});return data;
  }catch(error){
   const verified=releaseData(product,repo,catalog[product]||[]);
   const newest=data=>Math.max(0,...data.assets.map(a=>Date.parse(a.published)||0));
   if(verified.assets.length&&(!previous||newest(verified)>=newest(previous.data))){const data={...verified,stale:true,source:'verified-catalogue'};cache.set(product,{data,until:now()+30000});return data;}
   if(previous)return {...previous.data,stale:true};
   return {product,repository:'https://github.com/'+repo,assets:[],status:'unavailable'};
  }
 };
}


function releaseData(product,repo,list){
   const assets=[],seen=new Set();
   for(const release of list){if(release.draft||retired[product]?.has(release.tag_name))continue;for(const file of release.assets||[]){const url=file.browser_download_url;if(typeof url!=='string'||!url.startsWith(`https://github.com/${repo}/releases/download/`))continue;const name=String(file.name||'');const allowed=product==='lookout'?/^ArtemisLookout-mac-(?:x64|arm64)\.dmg$/:(product==='mind'||product==='prompter')?new RegExp('^Artemis'+(product==='mind'?'Mind':'Prompter')+'-(?:win-(?:x64|arm64)\\.exe|mac-(?:x64|arm64)\\.dmg|linux-(?:x64|x86_64|arm64)\\.AppImage)$'):product==='gameproducer'?/^AltStackGameProducer-(?:win-(?:x64|arm64)\.exe|mac-(?:x64|arm64)\.dmg|linux-(?:x64|arm64)\.AppImage)$/:product==='mail'?/^AltStackMail-(?:windows-(?:x64|arm64)\.exe|macos-(?:x64|arm64)\.dmg|linux-(?:x64|arm64)\.AppImage)$/:product==='office'?/^AltOffice-(?:windows-(?:x64|arm64)\.exe|mac-(?:x64|arm64)\.dmg|linux-(?:x64|arm64)\.deb)$/:product==='social'?/^AltStackSocial-(?:windows-(?:x64|arm64)\.zip|macos-(?:x64|arm64)\.dmg|linux-(?:x64|arm64)\.tar\.gz)$/:/^AltStackVenture-(?:windows-(?:x64|arm64)\.zip|macos-(?:x64|arm64)\.dmg|linux-(?:x64|arm64)\.tar\.gz)$/;if(!allowed.test(name))continue;if(seen.has(name))continue;seen.add(name);const checksum=(release.assets||[]).find(x=>x.name===name+'.sha256'&&x.browser_download_url===url+'.sha256');assets.push({name,url,size:file.size,version:release.tag_name,published:release.published_at,notes:release.html_url,...(checksum?{checksumUrl:checksum.browser_download_url}:{})});}}
   return {product,repository:"https://github.com/"+repo,assets,status:assets.length?"available":"building"};
}
