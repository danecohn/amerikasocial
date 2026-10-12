import { readFileSync } from 'node:fs';

// Local public-domain boundaries: no coordinates are sent to a geocoding service.
const data=JSON.parse(readFileSync(new URL('./geo/us-boundaries.json',import.meta.url),'utf8'));
const polygons=data.geometries.flatMap(g=>g.type==='MultiPolygon'?g.coordinates:[g.coordinates]).map(p=>p.map(ring=>{
  let previous=ring[0][0];
  return ring.map(([longitude,latitude])=>{while(longitude-previous>180)longitude-=360;while(longitude-previous< -180)longitude+=360;previous=longitude;return [longitude,latitude];});
}));
function inRing(longitude,latitude,ring){
  while(longitude-ring[0][0]>180)longitude-=360;
  while(longitude-ring[0][0]< -180)longitude+=360;
  let inside=false;
  for(let i=0,j=ring.length-1;i<ring.length;j=i++){
    const [xi,yi]=ring[i], [xj,yj]=ring[j];
    if((yi>latitude)!==(yj>latitude)&&longitude<(xj-xi)*(latitude-yi)/(yj-yi)+xi)inside=!inside;
  }
  return inside;
}
export function inUS(latitude,longitude){return polygons.some(p=>inRing(longitude,latitude,p[0])&&!p.slice(1).some(r=>inRing(longitude,latitude,r)));}
export const locationValidityMs=90*24*3600000;
export function locationVerified(at,now=Date.now()){const time=Date.parse(at);return Number.isFinite(time)&&time<=now&&now-time<locationValidityMs;}
export function verifyLocation(b,now=Date.now()){
  const reject=message=>{throw Object.assign(new Error(message),{status:400});};
  if(b.consent!==true)reject('Agree to the optional location check first.');
  const {latitude,longitude,accuracy,timestamp}=b;
  if(![latitude,longitude,accuracy,timestamp].every(v=>typeof v==='number'&&Number.isFinite(v))||Math.abs(latitude)>90||Math.abs(longitude)>180||accuracy<0)reject('Share a valid location from your device.');
  if(timestamp>now+10000||now-timestamp>120000)reject('That location has expired. Share a fresh location.');
  if(accuracy>1000)reject('Your location is too approximate. Enable precise location and try again.');
  if(!inUS(latitude,longitude))reject('This location could not be confirmed inside the United States. No new verification was granted.');
  // Avoid awarding a badge when the reported uncertainty crosses the border.
  for(let i=0;i<8;i++){
    const angle=i*Math.PI/4;
    const lat=latitude+Math.sin(angle)*accuracy/111320;
    const lon=longitude+Math.cos(angle)*accuracy/(111320*Math.cos(latitude*Math.PI/180));
    if(!inUS(lat,lon))reject('Your location is too close to a border or coastline to confirm. Try a more precise location.');
  }
  return new Date(now).toISOString();
}
