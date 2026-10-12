import { test } from 'node:test';
import assert from 'node:assert/strict';
import { inUS, verifyLocation, locationVerified, locationValidityMs } from '../location.mjs';

test('US boundaries include states and inhabited territories without nearby foreign cities or ocean',()=>{
 for(const [lat,lon] of [[33.45,-112.07],[38.90,-77.04],[61.22,-149.90],[21.30,-157.85],[18.45,-66.07],[13.47,144.75],[-14.28,-170.70],[15.18,145.75],[18.34,-64.93],[52.85,173.18]])assert.equal(inUS(lat,lon),true,`${lat},${lon}`);
 for(const [lat,lon] of [[43.65,-79.38],[32.51,-117.04],[49.28,-123.12],[51.50,-0.12],[0,0],[30,-70],[-33.86,151.21]])assert.equal(inUS(lat,lon),false,`${lat},${lon}`);
});
test('location requires consent, fresh numeric accurate coordinates; result contains only a date',()=>{
 const now=Date.now();const valid={consent:true,latitude:33.45,longitude:-112.07,accuracy:20,timestamp:now};
 assert.equal(verifyLocation(valid,now),new Date(now).toISOString());
 for(const patch of [{consent:false},{latitude:'33.45'},{longitude:Infinity},{latitude:91},{accuracy:-1},{accuracy:1001},{timestamp:now-120001},{timestamp:now+10001},{latitude:43.65,longitude:-79.38}])assert.throws(()=>verifyLocation({...valid,...patch},now),e=>e.status===400);
 assert.equal(locationVerified(new Date(now).toISOString(),now),true);
 assert.equal(locationVerified(new Date(now-locationValidityMs).toISOString(),now),false);
 assert.equal(locationVerified(null,now),false);
});
