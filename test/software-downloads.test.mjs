import test from 'node:test';import assert from 'node:assert/strict';import {createSoftwareDownloads}from '../software-downloads.mjs';
test('only published assets in the fixed project repository are exposed',async()=>{const read=createSoftwareDownloads({request:async()=>Response.json([{draft:false,tag_name:'v1',assets:[{name:'AmerikaVenture-linux-arm64.tar.gz',browser_download_url:'https://github.com/danecohn/AmerikaVenture/releases/download/v1/AmerikaVenture-linux-arm64.tar.gz',size:100},{name:'AmerikaVenture-windows-x64.zip',browser_download_url:'https://evil.example/download',size:100},{name:'debug-symbols.zip',browser_download_url:'https://github.com/danecohn/AmerikaVenture/releases/download/v1/debug-symbols.zip'}]}])});const d=await read('venture');assert.equal(d.assets.length,1);assert.equal(d.assets[0].name,'AmerikaVenture-linux-arm64.tar.gz');assert.equal(d.status,'available');});
test('empty releases have no fabricated downloads',async()=>{const read=createSoftwareDownloads({request:async()=>Response.json([])});const d=await read('office');assert.equal(d.status,'building');assert.deepEqual(d.assets,[]);});
test('arbitrary repository names cannot be requested',async()=>{await assert.rejects(createSoftwareDownloads()('other'),/Unknown product/);});
test('upstream failures are handled without exposing internal errors',async()=>{const read=createSoftwareDownloads({catalog:{},request:async()=>{throw Error('private details');}});const d=await read('venture');assert.equal(d.status,'unavailable');assert.deepEqual(d.assets,[]);});

test('GameProducer exposes all six verified repository assets and adjacent checksums',async()=>{const base='https://github.com/danecohn/GameProducer/releases/download/v0.1.3/';const names=['win-x64.exe','win-arm64.exe','mac-x64.dmg','mac-arm64.dmg','linux-x64.AppImage','linux-arm64.AppImage'].map(n=>'AltStackGameProducer-'+n);const assets=names.flatMap(name=>[{name,browser_download_url:base+name,size:100},{name:name+'.sha256',browser_download_url:base+name+'.sha256',size:64}]);assets.push({name:'AltStackGameProducer-win-x64.exe',browser_download_url:'https://evil.example/installer.exe'});const read=createSoftwareDownloads({request:async()=>Response.json([{tag_name:'v0.1.3',assets}])});const d=await read('gameproducer');assert.equal(d.assets.length,6);assert.ok(d.assets.every(a=>a.checksumUrl===a.url+'.sha256'));});


test('rate limited GitHub uses verified current installers for all six platforms',async()=>{
 const read=createSoftwareDownloads({request:async()=>new Response('',{status:403})});
 for(const product of ['social','office','venture','mail','gameproducer']){
  const result=await read(product);assert.equal(result.assets.length,6);assert.equal(result.source,'verified-catalogue');
  assert.ok(result.assets.every(a=>a.checksumUrl===a.url+'.sha256'));
 }
 assert.equal((await read('office')).assets[0].version,'altoffice-desktop-v0.3.0');
});
test('verified catalogue cannot replace a newer previously fetched release',async()=>{
 let fail=false;const read=createSoftwareDownloads({now:()=>fail?200000:0,request:async()=>{
  if(fail)throw Error('rate limited');
  return Response.json([{tag_name:'future',published_at:'2030-01-01T00:00:00Z',html_url:'https://github.com/danecohn/AmerikaOffice/releases/tag/future',assets:[{name:'AltOffice-linux-x64.deb',browser_download_url:'https://github.com/danecohn/AmerikaOffice/releases/download/future/AltOffice-linux-x64.deb',size:100}]}]);
 }});await read('office');fail=true;assert.equal((await read('office')).assets[0].version,'future');
});
