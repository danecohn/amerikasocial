// SPDX-License-Identifier: GPL-3.0-or-later
export function companyHostRoute(req,url){
 const host=String(req.headers.host||'').split(':')[0].toLowerCase();
 if(!['vigiltech.org','www.vigiltech.org'].includes(host))return null;
 // 308 preserves POST bodies on the www alias.
 if(host==='www.vigiltech.org')return{kind:'redirect',status:308,location:'https://vigiltech.org'+url.pathname+url.search};
 if(['/','/vigiltech','/vigiltech/'].includes(url.pathname)&&['GET','HEAD'].includes(req.method))return{kind:'company'};
 return null;
}
