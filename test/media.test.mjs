import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { validateMedia } from '../media.mjs';
test('media rejects spoofed MIME, oversized images, truncated videos, unsupported codecs and excessive duration',async()=>{
 const clip=await readFile(new URL('./fixtures/red.mp4',import.meta.url));validateMedia(clip,'video/mp4');
 assert.throws(()=>validateMedia(Buffer.from('<script>bad</script>'),'image/png'),e=>e.status===400);
 assert.throws(()=>validateMedia(Buffer.alloc(1000001),'image/jpeg'),e=>e.status===413);
 assert.throws(()=>validateMedia(clip.subarray(0,30),'video/mp4'),e=>e.status===400);
 const wrongCodec=Buffer.from(clip);wrongCodec.write('hvc1',wrongCodec.lastIndexOf('avc1'),'ascii');assert.throws(()=>validateMedia(wrongCodec,'video/mp4'),e=>e.status===400);
 const long=Buffer.from(clip);const header=long.indexOf('mvhd');const scale=long.readUInt32BE(header+16);long.writeUInt32BE(scale*61,header+20);assert.throws(()=>validateMedia(long,'video/mp4'),e=>e.status===400);
});


test('video accepts the 250 MB limit and converts real iPhone HEVC MOV for portable playback',async()=>{
 const {normalizeVideo}=await import('../video.mjs');const {maxMediaBytes}=await import('../media.mjs');assert.equal(maxMediaBytes,250000000);
 assert.throws(()=>validateMedia(Buffer.alloc(maxMediaBytes+1),'video/mp4'),e=>e.status===413);
 const clip=await readFile(new URL('./fixtures/red.mp4',import.meta.url));const padding=Buffer.alloc(21000000);padding.writeUInt32BE(padding.length,0);padding.write('free',4,'ascii');validateMedia(Buffer.concat([clip,padding]),'video/mp4');
 const iphone=await readFile(new URL('./fixtures/iphone.mov',import.meta.url));assert.throws(()=>validateMedia(iphone,'video/mp4'),e=>e.status===400);assert.equal(validateMedia(iphone,'video/quicktime',{allowIphone:true}).h264,false);
 if(!process.env.FFMPEG_PATH)return;
 const converted=await normalizeVideo(iphone,'video/quicktime');assert.equal(validateMedia(converted,'video/mp4').h264,true);assert.equal(converted.toString('ascii',4,8),'ftyp');
 await assert.rejects(normalizeVideo(Buffer.from('not a movie'),'video/quicktime'),e=>e.status===400);
});
