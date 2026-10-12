import {test} from 'node:test';import assert from 'node:assert/strict';import {webhookDestination,publicWebhookIp} from '../webhooks.mjs';
test('webhook destinations reject private, alternate IPv4, IPv6, credentials and insecure URLs and revalidate DNS',async()=>{
 for(const ip of ['127.0.0.1','10.0.0.1','169.254.169.254','172.16.1.1','192.168.1.1','100.64.0.1','0.0.0.0','224.0.0.1','::1','::ffff:127.0.0.1'])assert.equal(publicWebhookIp(ip),false);assert.equal(publicWebhookIp('8.8.8.8'),true);
 for(const url of ['http://example.com/x','https://user:pass@example.com','https://example.com:8080/x','https://example.com/x#fragment'])await assert.rejects(webhookDestination(url,{resolver:async()=>[{address:'8.8.8.8'}]}));
 for(const url of ['https://127.1','https://2130706433','https://localhost','https://[::1]'])await assert.rejects(webhookDestination(url,{resolver:async()=>[{address:'127.0.0.1'}]}));
 await assert.rejects(webhookDestination('https://public.example',{resolver:async()=>[{address:'8.8.8.8'},{address:'10.0.0.1'}]}));
 assert.equal((await webhookDestination('https://public.example',{resolver:async()=>[{address:'8.8.8.8'}]})).address,'8.8.8.8');
});
