export const searchPreferenceNames=new Set(['preferences','language','locale','safesearch','categories','disabled_engines','enabled_engines','method','results_on_new_tab','autocomplete','image_proxy','query_in_title','infinite_scroll','theme','simple_style']);
export function createSearchPreferences(db){
 db.exec('CREATE TABLE IF NOT EXISTS search_preferences(actor TEXT PRIMARY KEY,cookies TEXT NOT NULL,updated INTEGER NOT NULL)');
 const fail=message=>{throw Object.assign(Error(message),{status:400});};
 return {
  get(actor){const row=db.prepare('SELECT cookies,updated FROM search_preferences WHERE actor=?').get(actor);return row?{cookies:JSON.parse(row.cookies),updated:row.updated}:{cookies:{},updated:null};},
  save(actor,cookies){if(!cookies||typeof cookies!=='object'||Array.isArray(cookies))fail('Choose valid search preferences.');let bytes=0;const safe={};for(const[name,value]of Object.entries(cookies)){if(!searchPreferenceNames.has(name)||typeof value!=='string'||value.length>4096||/[\x00-\x20\x7f;,]/.test(value))fail('Invalid search preference.');bytes+=name.length+value.length;if(bytes>16384)fail('Search preferences are too large.');safe[name]=value;}const updated=Date.now();db.prepare('INSERT INTO search_preferences VALUES(?,?,?) ON CONFLICT(actor) DO UPDATE SET cookies=excluded.cookies,updated=excluded.updated').run(actor,JSON.stringify(safe),updated);return {cookies:safe,updated};},
 };
}
