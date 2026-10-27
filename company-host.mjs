// Public company hosting does not migrate account origins, cookies or app IDs.
export function companyHostRoute(req,url,{platformOrigin='https://www.amerika.social'}={}){
 const host=String(req.headers.host||'').split(':')[0].toLowerCase();
 if(!['vigiltech.org','www.vigiltech.org'].includes(host))return null;
 if(!['GET','HEAD'].includes(req.method))return{kind:'method-not-allowed'};
 if(host==='www.vigiltech.org')return{kind:'redirect',location:'https://vigiltech.org'+url.pathname+url.search};
 if(['/','/vigiltech','/vigiltech/'].includes(url.pathname))return{kind:'company'};
 // Account and app journeys continue at the existing origin, with their existing cookies.
 if(/^\/(?:social|office|search|mail|calendar|warehouse|drive|journal|fm-journal|sso|game-crafter)(?:\/|$)/.test(url.pathname)||url.pathname.startsWith('/api/')&&!['/api/software-downloads','/api/fmjournal-downloads'].includes(url.pathname))return{kind:'redirect',location:platformOrigin+url.pathname+url.search};
 return null;
}
