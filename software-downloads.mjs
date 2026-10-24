const products={social:'danecohn/AmerikaWindows',venture:'danecohn/AmerikaVenture',office:'danecohn/AmerikaOffice'};
export function createSoftwareDownloads({request=fetch,now=()=>Date.now()}={}){
 const cache=new Map();
 return async function releases(product){
  const repo=products[product];if(!repo)throw Object.assign(Error('Unknown product.'),{status:404});
  const previous=cache.get(product);if(previous&&previous.until>now())return previous.data;
  try{
   const response=await request(`https://api.github.com/repos/${repo}/releases?per_page=5`,{headers:{Accept:'application/vnd.github+json','User-Agent':'AltStack-Software-Downloads'},signal:AbortSignal.timeout(10000)});
   if(!response.ok)throw Error('Release information is temporarily unavailable.');
   const list=await response.json();if(!Array.isArray(list))throw Error('Invalid release information.');
   const assets=[],seen=new Set();
   for(const release of list){if(release.draft)continue;for(const file of release.assets||[]){const url=file.browser_download_url;if(typeof url!=='string'||!url.startsWith(`https://github.com/${repo}/releases/download/`))continue;const name=String(file.name||'');const allowed=product==='office'?/^AltOffice-(?:windows-(?:x64|arm64)\.exe|mac-(?:x64|arm64)\.dmg|linux-(?:x64|arm64)\.deb)$/:product==='social'?/^AltStackSocial-(?:windows-(?:x64|arm64)\.zip|macos-(?:x64|arm64)\.dmg|linux-(?:x64|arm64)\.tar\.gz)$/:/^AltStackVenture-(?:windows-(?:x64|arm64)\.zip|macos-(?:x64|arm64)\.dmg|linux-(?:x64|arm64)\.tar\.gz)$/;if(!allowed.test(name))continue;if(seen.has(name))continue;seen.add(name);const checksum=(release.assets||[]).find(x=>x.name===name+'.sha256'&&x.browser_download_url===url+'.sha256');assets.push({name,url,size:file.size,version:release.tag_name,published:release.published_at,notes:release.html_url,...(checksum?{checksumUrl:checksum.browser_download_url}:{})});}}
   const data={product,repository:'https://github.com/'+repo,assets,status:assets.length?'available':'building'};cache.set(product,{data,until:now()+(assets.length?180000:30000)});return data;
  }catch(error){if(previous)return {...previous.data,stale:true};return {product,repository:'https://github.com/'+repo,assets:[],status:'unavailable'};}
 };
}
