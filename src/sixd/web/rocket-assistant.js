/* Persistent, local-only rocket launcher. Service calls belong to the host. */
(() => {
  'use strict';
  let current=null;
  const tabs=['nemotron','research'];
  const positionKey='sixd.rocket.position.v1';
  const rocket=`<span class="sd-rocket-visual" aria-hidden="true"><canvas id="sd-rocket-canvas" class="sd-rocket-art" width="256" height="304" aria-hidden="true"></canvas>
    <svg class="sd-rocket-fallback" viewBox="0 0 110 150" focusable="false" aria-hidden="true"><defs>
      <linearGradient id="sd-fallback-metal"><stop stop-color="#28313c"/><stop offset=".27" stop-color="#aebbc8"/><stop offset=".42" stop-color="#fcfdfd"/><stop offset=".56" stop-color="#8995a3"/><stop offset=".78" stop-color="#e3e8ed"/><stop offset="1" stop-color="#313e4b"/></linearGradient>
      <linearGradient id="sd-fallback-fire" x2="0" y2="1"><stop stop-color="#f8fcff"/><stop offset=".35" stop-color="#99c7ff"/><stop offset=".7" stop-color="#f8bd76" stop-opacity=".7"/><stop offset="1" stop-color="#f8bd76" stop-opacity="0"/></linearGradient>
    </defs><g transform="rotate(24 55 73)"><path d="M48 108 Q44 131 55 147 Q66 131 62 108Z" fill="url(#sd-fallback-fire)"/>
      <path d="M41 76 L21 108 L41 99 M69 76 L89 108 L69 99" fill="#7c8997" stroke="#44515e"/>
      <path d="M55 9 Q39 25 40 49 L42 109 H68 L70 49 Q71 25 55 9Z" fill="url(#sd-fallback-metal)" stroke="#5d6a77" stroke-width=".7"/>
      <path d="M42 47 L29 66 L42 62 M68 47 L81 66 L68 62" fill="#8e9ca9" stroke="#566472" stroke-width=".6"/>
      <path d="M43 102 H67 L64 113 H46Z" fill="#35404b"/><path d="M42 72 H68 M42 83 H68 M42 94 H68" stroke="#55616c" stroke-width=".4" opacity=".6"/>
    </g></svg></span>`;

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
    launcher.title='Click to ask · drag to move · Alt + arrow keys to reposition';
    launcher.setAttribute('aria-describedby','sd-rocket-move-hint');
    launcher.innerHTML=rocket+'<span class="sd-rocket-launcher-label">Ask 6D</span><span id="sd-rocket-move-hint" class="sd-rocket-move-hint">Drag to move. Alt plus an arrow key moves the rocket; Alt plus Home resets its position. Click or press Enter to ask.</span><span class="sd-rocket-working" aria-hidden="true"></span>';
    const dialog=document.createElement('dialog');dialog.id='sd-rocket-dialog';
    dialog.className='sd-rocket-dialog';dialog.setAttribute('aria-labelledby','sd-rocket-title');
    dialog.setAttribute('aria-describedby','sd-rocket-context');
    dialog.innerHTML='<header class="sd-rocket-header"><div><span class="sd-label">Your workspace companion</span><h2 id="sd-rocket-title">Ask 6D</h2><p id="sd-rocket-context">Choose a project or ask for help with this page.</p></div><button type="button" class="sd-icon-button" data-rocket-close aria-label="Close Ask 6D">×</button></header>'+
      '<div class="sd-rocket-service-tabs" role="tablist" aria-label="Assistant service"><button type="button" id="sd-rocket-tab-nemotron" role="tab" aria-controls="sd-rocket-nemotron-host" aria-selected="true" data-rocket-tab="nemotron">Ask Nemotron</button><button type="button" id="sd-rocket-tab-research" role="tab" aria-controls="sd-rocket-research-host" aria-selected="false" tabindex="-1" data-rocket-tab="research">Find references</button></div>'+
      '<div class="sd-rocket-content"><section id="sd-rocket-nemotron-host" role="tabpanel" aria-labelledby="sd-rocket-tab-nemotron"></section><section id="sd-rocket-research-host" role="tabpanel" aria-labelledby="sd-rocket-tab-research" hidden></section></div><p class="sd-rocket-announcement" role="status" aria-live="polite"></p>';
    root.append(launcher,dialog);
    const s={launcher,dialog,callbacks,active:'nemotron',busy:false};current=s;
    const canvas=launcher.querySelector('#sd-rocket-canvas');
    const renderer=window.SixDRocketRenderer?.mount(canvas);
    if(!renderer){canvas.hidden=true;canvas.dataset.renderer='fallback';canvas.dataset.motion='paused';launcher.classList.add('sd-rocket-fallback-visible');}
    installMovement(launcher);
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
      if(!dialog.open){dialog.showModal();launcher.setAttribute('aria-expanded','true');renderer?.setPaused?.(true);}
      callbacks.onOpen?.(s.active);
    }
    function close(){
      if(!dialog.open)return;
      if(window.SixDOverlayDismiss)window.SixDOverlayDismiss.requestClose(dialog,'close-button');
      else if(typeof dialog.requestClose==='function')dialog.requestClose();
      else if(dialog.dispatchEvent(new Event('cancel',{cancelable:true})))dialog.close();
    }
    launcher.addEventListener('click',event=>{if(launcher.dataset.suppressClick==='true'&&event.detail>0){event.preventDefault();event.stopImmediatePropagation();return;}open();});
    dialog.querySelector('[data-rocket-close]').addEventListener('click',close);
    dialog.querySelector('.sd-rocket-service-tabs').addEventListener('click',event=>{
      const button=event.target.closest('[data-rocket-tab]');if(button)setTab(button.dataset.rocketTab);
    });
    dialog.querySelector('.sd-rocket-service-tabs').addEventListener('keydown',event=>{
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
      event.preventDefault();event.stopPropagation();const tab=event.key==='Home'?'nemotron':event.key==='End'?'research':s.active==='nemotron'?'research':'nemotron';
      setTab(tab);dialog.querySelector('[data-rocket-tab="'+tab+'"]').focus();
    });
    dialog.addEventListener('close',()=>{launcher.setAttribute('aria-expanded','false');renderer?.setPaused?.(false);callbacks.onClose?.();});
    const api={open,close,setTab,isOpen:()=>dialog.open,tab:()=>s.active,
      setContext:text=>{dialog.querySelector('#sd-rocket-context').textContent=String(text??'');},
      setBusy:busy=>{s.busy=Boolean(busy);launcher.classList.toggle('sd-rocket-is-busy',s.busy);launcher.setAttribute('aria-label',s.busy?'Ask 6D — investigation in progress':'Ask 6D');},
      announce:text=>{dialog.querySelector('.sd-rocket-announcement').textContent=String(text??'');}};
    s.api=api;return api;
  }
  function installMovement(launcher){
    let pointer=null,position={x:0,y:0},normalized=null,queued=0,next=null,clickTimer=null;
    const bounds=()=>({x:Math.max(8,innerWidth-launcher.offsetWidth-8),y:Math.max(8,innerHeight-launcher.offsetHeight-8)});
    const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
    function place(x,y){const max=bounds();position={x:clamp(x,8,max.x),y:clamp(y,8,max.y)};launcher.style.left=position.x+'px';launcher.style.top=position.y+'px';launcher.style.bottom='auto';launcher.style.right='auto';}
    function save(){const max=bounds();normalized={x:max.x>8?(position.x-8)/(max.x-8):0,y:max.y>8?(position.y-8)/(max.y-8):0};try{localStorage.setItem(positionKey,JSON.stringify(normalized));}catch{}}
    function initial(){place(innerWidth>950?258:innerWidth>650?200:12,innerHeight-launcher.offsetHeight-38);save();}
    try{const value=JSON.parse(localStorage.getItem(positionKey)||'null');if(value&&typeof value.x==='number'&&Number.isFinite(value.x)&&typeof value.y==='number'&&Number.isFinite(value.y))normalized={x:clamp(value.x,0,1),y:clamp(value.y,0,1)};}catch{}
    if(normalized){const max=bounds();place(8+normalized.x*(max.x-8),8+normalized.y*(max.y-8));}else initial();
    function flush(){queued=0;if(next){place(next.x,next.y);next=null;}}
    launcher.addEventListener('pointerdown',event=>{
      if(event.button!==0||event.isPrimary===false)return;
      clearTimeout(clickTimer);launcher.dataset.suppressClick='false';
      pointer={id:event.pointerId,x:event.clientX,y:event.clientY,left:position.x,top:position.y,dragged:false};
      try{launcher.setPointerCapture(event.pointerId);}catch{}
    });
    launcher.addEventListener('pointermove',event=>{
      if(!pointer||event.pointerId!==pointer.id)return;
      const dx=event.clientX-pointer.x,dy=event.clientY-pointer.y;
      if(!pointer.dragged&&Math.hypot(dx,dy)<6)return;
      pointer.dragged=true;launcher.dataset.dragging='true';launcher.classList.add('sd-rocket-dragging');event.preventDefault();
      next={x:pointer.left+dx,y:pointer.top+dy};if(!queued)queued=requestAnimationFrame(flush);
    });
    function end(event){
      if(!pointer||event.pointerId!==pointer.id)return;
      const wasDragged=pointer.dragged;pointer=null;cancelAnimationFrame(queued);flush();
      launcher.dataset.dragging='false';launcher.classList.remove('sd-rocket-dragging');
      if(wasDragged){event.preventDefault();launcher.dataset.suppressClick='true';save();clickTimer=setTimeout(()=>launcher.dataset.suppressClick='false',400);}
      try{if(launcher.hasPointerCapture(event.pointerId))launcher.releasePointerCapture(event.pointerId);}catch{}
    }
    launcher.addEventListener('pointerup',end);launcher.addEventListener('pointercancel',end);
    launcher.addEventListener('keydown',event=>{
      if(!event.altKey||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home'].includes(event.key))return;
      event.preventDefault();event.stopPropagation();if(event.key==='Home'){initial();return;}
      const step=event.shiftKey?32:16;place(position.x+(event.key==='ArrowLeft'?-step:event.key==='ArrowRight'?step:0),position.y+(event.key==='ArrowUp'?-step:event.key==='ArrowDown'?step:0));save();
    });
    window.addEventListener('resize',()=>{const max=bounds();if(normalized)place(8+normalized.x*(max.x-8),8+normalized.y*(max.y-8));else initial();});
  }
  window.SixDRocketAssistant=Object.freeze({mount,open:tab=>current?.api.open(tab),close:()=>current?.api.close(),
    setTab:tab=>current?.api.setTab(tab),isOpen:()=>current?.api.isOpen()??false,tab:()=>current?.api.tab()??'nemotron',
    setContext:text=>current?.api.setContext(text),setBusy:busy=>current?.api.setBusy(busy),announce:text=>current?.api.announce(text)});
})();
