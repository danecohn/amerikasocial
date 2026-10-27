'use strict';
(()=>{
 const root=document.documentElement;
 try{const theme=localStorage.getItem('cohnsoft-appearance-v1');if(theme==='light'||theme==='dark')root.dataset.theme=theme;const font=localStorage.getItem('cohnsoft-font-v1');if(font==='system')document.body.dataset.font='system'}catch{}
 const header=document.querySelector('.menubar,.top,header,.sidebar');if(!header)return;
 const controls=document.createElement('details');controls.className='cohnsoft-appearance';
 const summary=document.createElement('summary');summary.textContent='Appearance';summary.setAttribute('aria-label','Cohnsoft appearance settings');controls.append(summary);
 const menu=document.createElement('div');menu.className='cohnsoft-appearance-menu';
 for(const [label,theme]of [['System appearance','system'],['Light appearance','light'],['Dark appearance','dark']]){const b=document.createElement('button');b.type='button';b.textContent=label;b.setAttribute('aria-label',label);b.onclick=()=>{if(theme==='system')delete root.dataset.theme;else root.dataset.theme=theme;try{localStorage.setItem('cohnsoft-appearance-v1',theme)}catch{}controls.open=false};menu.append(b)}
 const font=document.createElement('button');font.type='button';font.textContent='Use system font';font.setAttribute('aria-label','Toggle system font');font.onclick=()=>{const system=document.body.dataset.font!=='system';if(system)document.body.dataset.font='system';else delete document.body.dataset.font;try{localStorage.setItem('cohnsoft-font-v1',system?'system':'cohn')}catch{}font.textContent=system?'Use Cohn Sans':'Use system font'};menu.append(font);controls.append(menu);header.append(controls);
})();
// Standard publisher credit, without touching user-generated posts or saved content.
(()=>{const footer=document.querySelector('.desktop-footer,body>footer,main>footer');if(footer&&!footer.textContent.includes('A product of Cohnsoft.')){const credit=document.createElement('span');credit.className='cohnsoft-credit';credit.textContent='A product of Cohnsoft.';footer.append(credit)}})();
