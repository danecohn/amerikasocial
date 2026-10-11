const fail=(status,message)=>{throw Object.assign(new Error(message),{status});};
export function createCaptcha({siteKey=process.env.TURNSTILE_SITE_KEY,secret=process.env.TURNSTILE_SECRET_KEY,origin,required=process.env.HUMAN_CAPTCHA_REQUIRED==='true'||!!(siteKey||secret),fetcher=fetch}={}){
  const hostname=origin?new URL(origin).hostname:null;
  async function verify(token){
    if(!required)return;
    if(!siteKey||!secret||!hostname)fail(503,'Human verification is unavailable. Please try again later.');
    if(typeof token!=='string'||!token.trim()||token.length>2048)fail(400,'Complete the human verification before signing in.');
    let result;
    try{const response=await fetcher('https://challenges.cloudflare.com/turnstile/v0/siteverify',{method:'POST',redirect:'error',headers:{'Content-Type':'application/json'},body:JSON.stringify({secret,response:token}),signal:AbortSignal.timeout(10000)});if(!response.ok)throw Error('Verification unavailable');result=await response.json();}catch{fail(503,'Human verification is unavailable. Please try again later.');}
    if(result.success!==true||result.hostname!==hostname||result.action!=='human-login')fail(400,'Human verification failed or expired. Please try again.');
  }
  return {required,siteKey:siteKey||null,verify};
}
