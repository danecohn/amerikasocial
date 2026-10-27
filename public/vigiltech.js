// SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(()=>{
 const root=document.documentElement,body=document.body;
 let theme='dark',font='vigil';
 try{theme=localStorage.getItem('vigiltech-appearance')||localStorage.getItem('cohnsoft-appearance-v1')||'dark';font=localStorage.getItem('vigiltech-font')||localStorage.getItem('cohnsoft-font-v1')||'vigil'}catch{}
 if(theme==='system')delete root.dataset.theme;else root.dataset.theme=theme==='light'?'light':'dark';body.dataset.font=font==='system'?'system':'vigil';
 const header=document.querySelector('.menubar,.top,.company-header,header,.sidebar');if(!header)return;
 const controls=document.createElement('details');controls.className='vigiltech-appearance';const summary=document.createElement('summary');summary.textContent='Appearance';summary.setAttribute('aria-label','VigilTech appearance settings');controls.append(summary);const menu=document.createElement('div');menu.className='vigiltech-appearance-menu';
 for(const [label,value]of [['System appearance','system'],['Dawn appearance','light'],['Night appearance','dark']]){const b=document.createElement('button');b.type='button';b.textContent=label;b.setAttribute('aria-label',label);b.onclick=()=>{if(value==='system')delete root.dataset.theme;else root.dataset.theme=value;try{localStorage.setItem('vigiltech-appearance',value)}catch{}controls.open=false};menu.append(b)}
 const f=document.createElement('button');f.type='button';const label=()=>f.textContent=body.dataset.font==='system'?'Use Vigil Sans':'Use system font';label();f.setAttribute('aria-label','Toggle system font');f.onclick=()=>{body.dataset.font=body.dataset.font==='system'?'vigil':'system';try{localStorage.setItem('vigiltech-font',body.dataset.font)}catch{}label()};menu.append(f);controls.append(menu);header.append(controls);
 const footer=document.querySelector('.desktop-footer,body>footer,main>footer');if(footer&&!footer.textContent.includes('A product of VigilTech, vigiltech.org.')){const credit=document.createElement('span');credit.className='vigiltech-credit';credit.textContent='A product of VigilTech, vigiltech.org.';footer.append(credit)}
})();
