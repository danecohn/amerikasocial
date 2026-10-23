import {test} from 'node:test';
import assert from 'node:assert/strict';
import sharp from 'sharp';
import {createSharing} from '../sharing.mjs';

test('branded exports preserve long posts and photo grids; metadata escapes content and visibility is rechecked',async()=>{
 let visible=true;
 const post={uri:'at://did:plc:example/app.bsky.feed.post/test',text:'A thoughtful community reply. '.repeat(27)+'<script>alert("x")</script>',created:'2026-10-12T12:00:00Z',author:{name:'A <friendly> voice',handle:'gardener.pds.amerika.social',verified:true,verificationType:'platform'},media:[1,2,3,4].map(id=>({id,mime:'image/webp'})),quote:null};
 const photo=await sharp({create:{width:90,height:60,channels:3,background:'#00ff00'}}).webp().toBuffer();
 const sharing=createSharing({origin:()=> 'https://altstack.io',handleDomain:'pds.amerika.social',getPost:()=>{if(!visible)throw Object.assign(Error('Unavailable'),{status:410});return post;},getImages:()=>[photo,photo,photo,photo]});
 const html=sharing.page('<head><title>Old</title><meta name="description" content="old"></head>',post.uri);assert.match(html,/og:image/);assert.ok(!html.includes('<friendly>'));assert.ok(!html.includes('<script>'));assert.match(sharing.embed(post.uri),/&lt;script&gt;/);
 const [first,second]=await Promise.all([sharing.image(post.uri),sharing.image(post.uri)]);assert.equal(first,second,'Concurrent requests share one rendering job');const meta=await sharp(first).metadata();assert.equal(meta.width,1080);assert.ok(meta.height>1500,'Long text and all photos get room');
 const pixel=await sharp(first).extract({left:500,top:meta.height-400,width:1,height:1}).raw().toBuffer();assert.ok(pixel[1]>200,'A photo in the second row is present');
 const preview=await sharp(await sharing.image(post.uri,true)).metadata();assert.equal(preview.width,1200);assert.equal(preview.height,630);
 visible=false;await assert.rejects(sharing.image(post.uri),e=>e.status===410);
});
