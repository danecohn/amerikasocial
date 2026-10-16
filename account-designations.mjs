// Administrator-managed exceptions keyed by immutable account ID, never by handle.
export function accountDesignations(raw=process.env.ACCOUNT_DESIGNATIONS||'{}') {
  const entries=JSON.parse(raw);
  if(!entries||typeof entries!=='object'||Array.isArray(entries))throw Error('ACCOUNT_DESIGNATIONS must be an account-ID object.');
  const result=new Map();
  for(const [id,value] of Object.entries(entries)){
    if(!id||!value||typeof value!=='object'||Array.isArray(value)||value.country!==undefined&&value.country!=='CA'||value.permanentPlus!==undefined&&typeof value.permanentPlus!=='boolean')throw Error('Invalid ACCOUNT_DESIGNATIONS entry.');
    result.set(id,{country:value.country==='CA'?{code:'CA',label:'Canadian',source:'platform',verified:true}:null,permanentPlus:value.permanentPlus===true});
  }
  return result;
}
