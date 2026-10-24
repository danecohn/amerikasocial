import sharp from 'sharp';
import {readFileSync} from 'node:fs';
const blossom=readFileSync(new URL('./public/logo.svg',import.meta.url),'utf8').replace('<svg ','<svg width="64" height="64" ');
import {createHash} from 'node:crypto';

export const escapeHtml=value=>String(value??'').toWellFormed().replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]/g,'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const postPath=uri=>'/post/'+encodeURIComponent(uri);
const segmenter=new Intl.Segmenter('en',{granularity:'grapheme'});
function lines(text,max){const rows=[];for(const paragraph of text.split('\n')){let line='',width=0;for(const {segment}of segmenter.segment(paragraph)){const size=/[\u2e80-\uffff]|\p{Extended_Pictographic}/u.test(segment)?2:/[MW@]/.test(segment)?1.8:/[A-Z]/.test(segment)?1.4:/[il .,!'|]/.test(segment)?0.5:1;if(width+size>max){const at=line.lastIndexOf(' ');if(at>0){rows.push(line.slice(0,at));line=line.slice(at+1);width=[...segmenter.segment(line)].reduce((n,{segment:s})=>n+(/[\u2e80-\uffff]|\p{Extended_Pictographic}/u.test(s)?2:/[MW@]/.test(s)?1.8:/[A-Z]/.test(s)?1.4:/[il .,!'|]/.test(s)?0.5:1),0);}else{rows.push(line);line='';width=0;}}line+=segment;width+=size;}rows.push(line);}return rows;}
const text=(value,x,y,size=32,color='#263e52',weight=400)=>`<text x="${x}" y="${y}" fill="${color}" font-size="${size}" font-weight="${weight}" font-family="DejaVu Sans,Noto Color Emoji,Arial,sans-serif">${escapeHtml(value)}</text>`;
export function createSharing({getPost,getImages,origin,handleDomain}){
 const cache=new Map(),pending=new Map();let cachedBytes=0;let active=0;
 const handle=value=>handleDomain&&value.endsWith('.'+handleDomain)?value.slice(0,-handleDomain.length-1):value;
 const url=uri=>origin()+postPath(uri);
 function page(html,uri){const p=getPost(uri),title=p.author.name+' on AltStack Social',description=p.text.slice(0,200)||'A post from @'+handle(p.author.handle),image=origin()+'/share-image?format=preview&uri='+encodeURIComponent(uri),canonical=url(uri);return html.replace(/<title>.*?<\/title>/,`<title>${escapeHtml(title)}</title>`).replace(/<meta name="description" content="[^"]*">/,`<meta name="description" content="${escapeHtml(description)}">`).replace('</head>',`<link rel="canonical" href="${escapeHtml(canonical)}"><meta property="og:type" content="article"><meta property="og:site_name" content="AltStack Social"><meta property="og:title" content="${escapeHtml(title)}"><meta property="og:description" content="${escapeHtml(description)}"><meta property="og:url" content="${escapeHtml(canonical)}"><meta property="og:image" content="${escapeHtml(image)}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="${escapeHtml(description)}"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="${escapeHtml(title)}"><meta name="twitter:description" content="${escapeHtml(description)}"><meta name="twitter:image" content="${escapeHtml(image)}"><link rel="alternate" type="application/json+oembed" href="${escapeHtml(origin()+'/api/oembed?url='+encodeURIComponent(canonical))}" title="AltStack Social post"></head>`);}
 function embed(uri){const p=getPost(uri);return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escapeHtml(p.author.name)} on AltStack Social</title><link rel="stylesheet" href="/style.css"><link rel="stylesheet" href="/makk.css"></head><body class="embed-page"><article class="embed-card"><a class="embed-brand" href="${escapeHtml(url(uri))}" target="_blank" rel="noopener"><img src="/logo.svg" alt="AltStack Social"> AltStack Social</a><h2>${escapeHtml(p.author.name)}</h2><p class="muted">@${escapeHtml(handle(p.author.handle))}</p><p class="embed-text">${escapeHtml(p.text)}</p>${p.media.filter(m=>m.mime!=='video/mp4').map(m=>`<img class="embed-photo" src="${escapeHtml(m.url)}" alt="${escapeHtml(m.alt)}" loading="lazy">`).join('')}${p.media.some(m=>m.mime==='video/mp4')?'<p>Video attached · watch on AltStack Social</p>':''}<a class="primary inline" href="${escapeHtml(url(uri))}" target="_blank" rel="noopener">View conversation ↗</a><p class="muted">altstack.io</p></article></body></html>`;}
 async function image(uri,preview=false){
  const p=getPost(uri);const key=createHash('sha256').update(JSON.stringify([preview,p])).digest('hex');const hit=cache.get(key);if(hit)return hit;if(pending.has(key))return pending.get(key);
  if(active>=2)throw Object.assign(Error('Share images are busy. Please try again shortly.'),{status:503});active++;
  const job=(async()=>{try{
   const width=preview?1200:1080,pad=64;let y=272;
   const previewPhoto=preview?getImages(uri)[0]:null;
   let body=lines(p.text,preview?(previewPhoto?31:59):45);if(preview&&body.length>5)body=[...body.slice(0,4),body[4].slice(0,previewPhoto?28:55)+'…'];
   const size=preview?32:36,leading=preview?45:52;
   let svg=`<rect width="100%" height="100%" fill="#eef3f8"/><rect width="100%" height="126" fill="#dbe4ec"/><g transform="translate(64 30)">${blossom}</g>${text('ALTSTACK SOCIAL',154,75,34,'#263e52',750)}${text('Why Can’t We Be Friends?',154,103,18)}${text(lines(p.author.name,45)[0],pad,191,32,'#263e52',700)}${text('@'+handle(p.author.handle),pad,231,23,'#536b80')}`;
   if(p.author.verified)svg+=text('✓',width-pad,191,32,p.author.verificationType==='platform'?'#ff0058':'#263e52',700);
   for(const line of body){svg+=text(line,pad,y,size);y+=leading;}
   if(!preview&&p.quote&&!p.quote.deleted){y+=20;svg+=`<rect x="64" y="${y-24}" width="${width-128}" height="150" rx="8" fill="#dce6ee"/>${text('Quoting @'+handle(p.quote.author.handle),84,y+10,22,'#536b80')}`;for(const line of lines(p.quote.text,58).slice(0,2)){y+=36;svg+=text(line,84,y+10,24);}y+=65;}
   const composites=[];
   if(previewPhoto){const bytes=await sharp(previewPhoto,{limitInputPixels:64000000}).resize(400,250,{fit:'inside'}).png().toBuffer();const meta=await sharp(bytes).metadata();composites.push({input:bytes,left:Math.round(736+(400-meta.width)/2),top:252});}
   if(!preview){const photos=getImages(uri).slice(0,4);if(photos.length){y+=20;const cell=photos.length===1?width-128:(width-144)/2;const h=photos.length===1?480:340;for(let i=0;i<photos.length;i++){const bytes=await sharp(photos[i],{limitInputPixels:64000000}).resize(Math.round(cell),h,{fit:'inside'}).png().toBuffer();const meta=await sharp(bytes).metadata();composites.push({input:bytes,left:Math.round(pad+(i%2)*(cell+16)+(cell-meta.width)/2),top:Math.round(y+Math.floor(i/2)*(h+16))});}y+=Math.ceil(photos.length/2)*(h+16);}
    if(p.media.some(m=>m.mime==='video/mp4')){y+=30;svg+=text('▶ Video attached · watch on AltStack Social',pad,y,25,'#536b80');y+=35;}
   }
   const height=preview?630:Math.max(650,y+155);const footer=height-80;
   svg+=`<path d="M64 ${footer-34}H${width-64}" stroke="#333"/>${text('altstack.io',pad,footer+10,28,'#263e52',700)}${text(new Date(p.created).toISOString().slice(0,10),width-245,footer+10,22,'#aaa')}`;
   const buffer=await sharp(Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">${svg}</svg>`)).composite(composites).png().toBuffer();
   getPost(uri); // Recheck visibility after asynchronous rendering.
   while(cache.size>=24||cachedBytes+buffer.length>16000000){const first=cache.keys().next().value;if(!first)break;cachedBytes-=cache.get(first).length;cache.delete(first);}if(buffer.length<=16000000){cache.set(key,buffer);cachedBytes+=buffer.length;}return buffer;
  }finally{active--;pending.delete(key);}})();pending.set(key,job);return job;
 }
 return {page,embed,image,url};
}
