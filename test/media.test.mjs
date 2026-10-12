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
