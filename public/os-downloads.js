(()=>{
 for(const button of document.querySelectorAll('.copy')){
  button.addEventListener('click',async()=>{
   const text=document.getElementById(button.dataset.copy)?.innerText||'';
   try{await navigator.clipboard.writeText(text);button.textContent='Copied';}catch{button.textContent='Select and copy';}
   setTimeout(()=>{button.textContent='Copy';},1800);
  });
 }
 const size=n=>n>1048576?(n/1048576).toFixed(1)+' MB':Math.max(1,Math.round(n/1024))+' KB';
 fetch('/apt/manifest.json',{cache:'no-cache'}).then(r=>r.ok?r.json():Promise.reject()).then(m=>{
  const body=document.querySelector('#packages tbody');
  for(const [file,info] of Object.entries(m.packages||{}).sort()){
   const match=/^([^_]+)_([^_]+)_([^_]+)\.deb$/.exec(file);if(!match)continue;
   const row=document.createElement('tr');
   for(const text of [match[1],match[2],match[3],size(info.size),info.sha256.slice(0,16)+'…']){const cell=document.createElement('td');cell.textContent=text;row.append(cell);}
   row.lastChild.title=info.sha256;
   body.append(row);
  }
  document.getElementById('pkg-status').textContent=`Suite “${m.suite}” for ${m.architecture}, generated ${m.generated}. Signing key fingerprint ${m.fingerprint.replace(/(.{4})/g,'$1 ').trim()}.`;
 }).catch(()=>{document.getElementById('pkg-status').textContent='The package list is temporarily unavailable.';});
})();
