/* Persistent, local-only rocket launcher. Service calls belong to the host. */
(() => {
  'use strict';
  let current=null;
  const tabs=['nemotron','research'];
  const rocket=`<svg class="sd-rocket-art" viewBox="0 0 80 112" aria-hidden="true" focusable="false">
    <g class="sd-rocket-exhaust">
      <path class="sd-rocket-flame-outer" d="M31 73 Q26 91 40 105 Q55 91 49 73Z" fill="#efad68"/>
      <path class="sd-rocket-flame-inner" d="M35 73 Q31 84 40 94 Q49 84 45 73Z" fill="#fff1c9"/>
      <ellipse class="sd-rocket-gas sd-rocket-gas-one" cx="40" cy="94" rx="10" ry="4" fill="#cbd5de"/>
      <ellipse class="sd-rocket-gas sd-rocket-gas-two" cx="40" cy="94" rx="10" ry="4" fill="#cbd5de"/>
      <ellipse class="sd-rocket-gas sd-rocket-gas-three" cx="40" cy="94" rx="10" ry="4" fill="#cbd5de"/>
    </g>
    <g class="sd-rocket-body">
      <path d="M29 48 Q13 56 15 77 L29 69Z" fill="#8da8c1" stroke="#52677d" stroke-width="1.3"/>
      <path d="M51 48 Q67 56 65 77 L51 69Z" fill="#8da8c1" stroke="#52677d" stroke-width="1.3"/>
      <path d="M40 7 C21 24 23 52 29 72 L51 72 C57 52 59 24 40 7Z" fill="#eff3f7" stroke="#52677d" stroke-width="1.4"/>
      <path d="M40 7 C31 15 27 25 26 35 L54 35 C53 25 49 15 40 7Z" fill="#a5bfd6"/>
      <path d="M41 10 C51 30 50 53 46 69 L50 69 C56 49 56 25 41 10Z" fill="#d9e2eb"/>
      <circle cx="40" cy="40" r="10" fill="#dee8f2" stroke="#71879b" stroke-width="1.3"/>
      <circle cx="40" cy="40" r="7" fill="#345a7b"/>
      <path d="M36 37 Q39 34 43 36" fill="none" stroke="#c6e8fa" stroke-width="1.7" stroke-linecap="round"/>
      <path d="M33 58 H47" stroke="#c3cfdb" stroke-width="1.3"/>
      <path d="M29 69 H51 L48 76 H32Z" fill="#73899e" stroke="#52677d" stroke-width="1.2"/>
      <path d="M40 56 L36 75 H44Z" fill="#819fb9" stroke="#52677d" stroke-width="1.1"/>
    </g>
  </svg>`;

  function mount(callbacks={}) {
    if(current)return current.api;
    const root=document.querySelector('#sixd-workspace');
    if(!root)throw new Error('Mount the rocket after the workspace exists.');
    const launcher=document.createElement('button');
    launcher.type='button';launcher.id='sd-rocket-launcher';
    launcher.className='sd-rocket-launcher';
    launcher.setAttribute('aria-label','Ask 6D');
    launcher.setAttribute('aria-haspopup','dialog');
    launcher.setAttribute('aria-controls','sd-rocket-dialog');
    launcher.setAttribute('aria-expanded','false');
    launcher.innerHTML=rocket+'<span class="sd-rocket-launcher-label">Ask 6D</span><span class="sd-rocket-working" aria-hidden="true"></span>';
    const dialog=document.createElement('dialog');dialog.id='sd-rocket-dialog';
    dialog.className='sd-rocket-dialog';dialog.setAttribute('aria-labelledby','sd-rocket-title');
    dialog.setAttribute('aria-describedby','sd-rocket-context');
    dialog.innerHTML='<header class="sd-rocket-header"><div><span class="sd-label">Your workspace companion</span><h2 id="sd-rocket-title">Ask 6D</h2><p id="sd-rocket-context">Choose a project or ask for help with this page.</p></div><button type="button" class="sd-icon-button" data-rocket-close aria-label="Close Ask 6D">×</button></header>'+
      '<div class="sd-rocket-service-tabs" role="tablist" aria-label="Assistant service"><button type="button" id="sd-rocket-tab-nemotron" role="tab" aria-controls="sd-rocket-nemotron-host" aria-selected="true" data-rocket-tab="nemotron">Ask Nemotron</button><button type="button" id="sd-rocket-tab-research" role="tab" aria-controls="sd-rocket-research-host" aria-selected="false" tabindex="-1" data-rocket-tab="research">Find references</button></div>'+
      '<div class="sd-rocket-content"><section id="sd-rocket-nemotron-host" role="tabpanel" aria-labelledby="sd-rocket-tab-nemotron"></section><section id="sd-rocket-research-host" role="tabpanel" aria-labelledby="sd-rocket-tab-research" hidden></section></div><p class="sd-rocket-announcement" role="status" aria-live="polite"></p>';
    root.append(launcher,dialog);
    const s={launcher,dialog,callbacks,active:'nemotron',busy:false};current=s;
    function setTab(tab,notify=true){
      if(!tabs.includes(tab))tab='nemotron';
      const changed=s.active!==tab;s.active=tab;
      for(const name of tabs){
        const button=dialog.querySelector('[data-rocket-tab="'+name+'"]');
        const active=name===tab;button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;
        dialog.querySelector('#sd-rocket-'+name+'-host').hidden=!active;
      }
      if(changed&&notify)callbacks.onTabChange?.(tab);
    }
    function open(tab=s.active){
      setTab(tab,false);
      if(!dialog.open){dialog.showModal();launcher.setAttribute('aria-expanded','true');}
      callbacks.onOpen?.(s.active);
    }
    function close(){
      if(!dialog.open)return;
      if(window.SixDOverlayDismiss)window.SixDOverlayDismiss.requestClose(dialog,'close-button');
      else if(typeof dialog.requestClose==='function')dialog.requestClose();
      else if(dialog.dispatchEvent(new Event('cancel',{cancelable:true})))dialog.close();
    }
    launcher.addEventListener('click',()=>open());
    dialog.querySelector('[data-rocket-close]').addEventListener('click',close);
    dialog.querySelector('.sd-rocket-service-tabs').addEventListener('click',event=>{
      const button=event.target.closest('[data-rocket-tab]');if(button)setTab(button.dataset.rocketTab);
    });
    dialog.querySelector('.sd-rocket-service-tabs').addEventListener('keydown',event=>{
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
      event.preventDefault();event.stopPropagation();const tab=event.key==='Home'?'nemotron':event.key==='End'?'research':s.active==='nemotron'?'research':'nemotron';
      setTab(tab);dialog.querySelector('[data-rocket-tab="'+tab+'"]').focus();
    });
    dialog.addEventListener('close',()=>{launcher.setAttribute('aria-expanded','false');callbacks.onClose?.();});
    const api={open,close,setTab,isOpen:()=>dialog.open,tab:()=>s.active,
      setContext:text=>{dialog.querySelector('#sd-rocket-context').textContent=String(text??'');},
      setBusy:busy=>{s.busy=Boolean(busy);launcher.classList.toggle('sd-rocket-is-busy',s.busy);launcher.setAttribute('aria-label',s.busy?'Ask 6D — investigation in progress':'Ask 6D');},
      announce:text=>{dialog.querySelector('.sd-rocket-announcement').textContent=String(text??'');}};
    s.api=api;return api;
  }
  window.SixDRocketAssistant=Object.freeze({mount,open:tab=>current?.api.open(tab),close:()=>current?.api.close(),
    setTab:tab=>current?.api.setTab(tab),isOpen:()=>current?.api.isOpen()??false,tab:()=>current?.api.tab()??'nemotron',
    setContext:text=>current?.api.setContext(text),setBusy:busy=>current?.api.setBusy(busy),announce:text=>current?.api.announce(text)});
})();
