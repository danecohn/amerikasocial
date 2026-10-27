const fail=(status,message)=>{throw Object.assign(new Error(message),{status});};
export function createCaptcha({siteKey=process.env.TURNSTILE_SITE_KEY,secret=process.env.TURNSTILE_SECRET_KEY,origin,originAliases=[],required=process.env.HUMAN_CAPTCHA_REQUIRED==='true'||!!(siteKey||secret),fetcher=fetch}={}){
  const hostname=origin?new URL(origin).hostname:null;
  const hostnames=new Set([hostname,...originAliases.map(value=>new URL(value).hostname),...(process.env.BROWSER_ORIGIN_ALIASES||'').split(',').filter(Boolean).map(value=>new URL(value.trim()).hostname)]);
  async function verify(token,action='human-login'){
    if(!required)return;
    if(!siteKey||!secret||!hostname)fail(503,'Human verification is unavailable. Please try again later.');
    if(typeof token!=='string'||!token.trim()||token.length>2048)fail(400,'Complete the human verification to continue.');
    let result;
    try{const response=await fetcher('https://challenges.cloudflare.com/turnstile/v0/siteverify',{method:'POST',redirect:'error',headers:{'Content-Type':'application/json'},body:JSON.stringify({secret,response:token}),signal:AbortSignal.timeout(10000)});if(!response.ok)throw Error('Verification unavailable');result=await response.json();}catch{fail(503,'Human verification is unavailable. Please try again later.');}
    if(result.success!==true||!hostnames.has(result.hostname)||result.action!==action)fail(400,'Human verification failed or expired. Please try again.');
  }
  return {required,siteKey:siteKey||null,verify};
}
