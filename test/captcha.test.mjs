import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createCaptcha} from '../captcha.mjs';
test('human verification rejects missing, replayed, foreign-host and foreign-action tokens and fails closed on outages',async()=>{
  let calls=0,response={success:true,hostname:'www.amerika.social',action:'human-login'};
  const captcha=createCaptcha({siteKey:'public-key',secret:'private-key',origin:'https://www.amerika.social',required:true,fetcher:async(url,options)=>{calls++;assert.equal(url,'https://challenges.cloudflare.com/turnstile/v0/siteverify');assert.equal(options.redirect,'error');assert.deepEqual(JSON.parse(options.body),{secret:'private-key',response:'valid-token'});return {ok:true,json:async()=>response};}});
  await assert.rejects(captcha.verify(),e=>e.status===400);assert.equal(calls,0);
  await captcha.verify('valid-token');response={success:true,hostname:'www.amerika.social',action:'human-register'};await captcha.verify('valid-token','human-register');await assert.rejects(captcha.verify('valid-token'),e=>e.status===400);
  for(const invalid of [{success:false,'error-codes':['timeout-or-duplicate']},{success:true,hostname:'evil.example',action:'human-login'},{success:true,hostname:'www.amerika.social',action:'other-action'}]){response=invalid;await assert.rejects(captcha.verify('valid-token'),e=>e.status===400);}
  const unavailable=createCaptcha({siteKey:'public',secret:'private',origin:'https://www.amerika.social',required:true,fetcher:async()=>{throw Error('Network failure');}});await assert.rejects(unavailable.verify('token'),e=>e.status===503);
  await assert.rejects(createCaptcha({required:true}).verify('token'),e=>e.status===503);
});
