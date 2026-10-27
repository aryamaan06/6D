/* Persistent, local-only rocket launcher. Service calls belong to the host. */
(() => {
  'use strict';
  let current=null;
  const tabs=['nemotron','research'];
  const positionKey='sixd.rocket.position.v1';
  const placementKey='sixd.rocket.placement.v2';
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
    launcher.innerHTML=rocket+'<span class="sd-rocket-launcher-label">Ask 6D</span><span id="sd-rocket-move-hint" class="sd-rocket-move-hint">Drag to move. Release to park clear of page controls. The rocket stays still while you scroll; Dock safely or Minimize if it covers content. Alt plus an arrow key moves the rocket; Alt plus Home resets its position. Rocket options has help, docking and size controls. Click or press Enter to ask.</span><span class="sd-rocket-working" aria-hidden="true"></span>';
    const companion=document.createElement('div');companion.className='sd-rocket-companion';
    companion.innerHTML='<div class="sd-rocket-companion-tools"><button type="button" data-rocket-options aria-label="Rocket options and movement help" aria-haspopup="dialog" aria-controls="sd-rocket-controls">Options</button><button type="button" data-rocket-size aria-label="Minimize rocket" title="Minimize rocket">−</button></div><span class="sd-rocket-placement-status sd-rocket-move-hint" role="status" aria-live="polite"></span>';
    companion.prepend(launcher);
    const controls=document.createElement('dialog');controls.id='sd-rocket-controls';controls.className='sd-rocket-controls';
    controls.setAttribute('aria-labelledby','sd-rocket-controls-title');
    controls.innerHTML='<div class="sd-rocket-controls-heading"><h2 id="sd-rocket-controls-title">Your rocket companion</h2><button type="button" class="sd-icon-button" data-rocket-controls-close aria-label="Close rocket options">×</button></div><p>Click the rocket to ask 6D. Drag its body to move it; it parks clear of page controls when released.</p><p>It stays still while you scroll. Content can move beneath it: choose Dock safely, drag it elsewhere or minimize it when you need more space.</p><p>With the rocket focused, use <kbd>Alt</kbd> + an arrow key to move, add <kbd>Shift</kbd> for a larger step, or use <kbd>Alt</kbd> + <kbd>Home</kbd> to reset.</p><p data-rocket-placement-note></p><div class="sd-rocket-controls-actions"><button type="button" data-rocket-dock>Dock safely</button><button type="button" data-rocket-reset>Reset position</button><button type="button" data-rocket-controls-size>Minimize rocket</button></div>';
    const dialog=document.createElement('dialog');dialog.id='sd-rocket-dialog';
    dialog.className='sd-rocket-dialog';dialog.setAttribute('aria-labelledby','sd-rocket-title');
    dialog.setAttribute('aria-describedby','sd-rocket-context');
    dialog.innerHTML='<header class="sd-rocket-header"><div><h2 id="sd-rocket-title">Ask 6D</h2><p id="sd-rocket-context">Choose a project or ask for help with this page.</p></div><div class="sd-rocket-window-actions"><button type="button" class="sd-rocket-expand" data-rocket-expand aria-label="Expand conversation" title="Expand conversation" aria-pressed="false"><span aria-hidden="true">↗</span> <span data-rocket-expand-label>Expand</span></button><button type="button" class="sd-icon-button" data-rocket-close aria-label="Close Ask 6D">×</button></div></header>'+
      '<div class="sd-rocket-service-tabs" role="tablist" aria-label="Assistant service"><button type="button" id="sd-rocket-tab-nemotron" role="tab" aria-controls="sd-rocket-nemotron-host" aria-selected="true" data-rocket-tab="nemotron">Ask Nemotron</button><button type="button" id="sd-rocket-tab-research" role="tab" aria-controls="sd-rocket-research-host" aria-selected="false" tabindex="-1" data-rocket-tab="research">Find references</button></div>'+
      '<div class="sd-rocket-content"><section id="sd-rocket-nemotron-host" role="tabpanel" aria-labelledby="sd-rocket-tab-nemotron"></section><section id="sd-rocket-research-host" role="tabpanel" aria-labelledby="sd-rocket-tab-research" hidden></section></div><p class="sd-rocket-announcement" role="status" aria-live="polite"></p>';
    root.append(companion,dialog,controls);
    const s={launcher,dialog,callbacks,active:'nemotron',busy:false};current=s;
    const canvas=launcher.querySelector('#sd-rocket-canvas');
    const renderer=window.SixDRocketRenderer?.mount(canvas);
    if(!renderer){canvas.hidden=true;canvas.dataset.renderer='fallback';canvas.dataset.motion='paused';launcher.classList.add('sd-rocket-fallback-visible');}
    const movement=installMovement(launcher,companion,controls,root,paused=>renderer?.setPaused?.(paused));
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
      if(!dialog.open){dialog.showModal();launcher.setAttribute('aria-expanded','true');movement.refresh();}
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
    dialog.querySelector('[data-rocket-expand]').addEventListener('click',()=>{
      const transcript=dialog.querySelector('#sd-ai-transcript'),scrollTop=transcript?.scrollTop;
      const expanded=dialog.classList.toggle('sd-rocket-expanded');
      const button=dialog.querySelector('[data-rocket-expand]');
      button.setAttribute('aria-pressed',String(expanded));
      button.setAttribute('aria-label',expanded?'Restore conversation size':'Expand conversation');
      button.title=expanded?'Restore conversation size':'Expand conversation';
      button.querySelector('[data-rocket-expand-label]').textContent=expanded?'Restore size':'Expand';
      if(transcript)requestAnimationFrame(()=>{transcript.scrollTop=scrollTop;});
    });
    dialog.querySelector('.sd-rocket-service-tabs').addEventListener('click',event=>{
      const button=event.target.closest('[data-rocket-tab]');if(button)setTab(button.dataset.rocketTab);
    });
    dialog.querySelector('.sd-rocket-service-tabs').addEventListener('keydown',event=>{
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
      event.preventDefault();event.stopPropagation();const tab=event.key==='Home'?'nemotron':event.key==='End'?'research':s.active==='nemotron'?'research':'nemotron';
      setTab(tab);dialog.querySelector('[data-rocket-tab="'+tab+'"]').focus();
    });
    dialog.addEventListener('close',()=>{launcher.setAttribute('aria-expanded','false');movement.refresh();callbacks.onClose?.();});
    const api={open,close,setTab,isOpen:()=>dialog.open,tab:()=>s.active,
      refreshPlacement:movement.refresh,
      setContext:text=>{dialog.querySelector('#sd-rocket-context').textContent=String(text??'');},
      setBusy:busy=>{s.busy=Boolean(busy);launcher.classList.toggle('sd-rocket-is-busy',s.busy);launcher.setAttribute('aria-label',s.busy?'Ask 6D — investigation in progress':'Ask 6D');},
      announce:text=>{dialog.querySelector('.sd-rocket-announcement').textContent=String(text??'');}};
    s.api=api;return api;
  }
  function installMovement(launcher,companion,controls,root,pauseRenderer){
    const gap=10,clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
    let pausedState=null;
    const pause=value=>{if(pausedState!==value){pausedState=value;pauseRenderer(value);}};
    let pointer=null,position={x:8,y:8},preference=null,userCompact=false,compact=false,inline=false;
    let queued=0,next=null,refreshFrame=0,pendingRefresh=null,clickTimer=null,keyboardTimer=null,scrollUntil=0,savedPreference=null;
    const status=companion.querySelector('.sd-rocket-placement-status');
    const sizeButton=companion.querySelector('[data-rocket-size]');
    const optionsButton=companion.querySelector('[data-rocket-options]');
    const dimensions=()=>({width:companion.offsetWidth,height:companion.offsetHeight});
    const bounds=()=>{const size=dimensions();return{x:Math.max(8,innerWidth-size.width-8),y:Math.max(8,innerHeight-size.height-8)};};
    const valid=value=>value&&Number.isFinite(value.x)&&Number.isFinite(value.y);
    try{
      savedPreference=localStorage.getItem(placementKey);
      const saved=JSON.parse(savedPreference||'null');
      if(saved?.version===2){if(valid(saved.position))preference={x:clamp(saved.position.x,0,1),y:clamp(saved.position.y,0,1)};userCompact=saved.compact===true;}
      else{const old=JSON.parse(localStorage.getItem(positionKey)||'null');if(valid(old))preference={x:clamp(old.x,0,1),y:clamp(old.y,0,1)};}
    }catch{}
    function savePreference(){
      const value=JSON.stringify({version:2,position:preference,compact:userCompact});
      if(value===savedPreference)return;
      try{localStorage.setItem(placementKey,value);savedPreference=value;}catch{}
    }
    function remember(){const max=bounds();preference={x:max.x>8?(position.x-8)/(max.x-8):0,y:max.y>8?(position.y-8)/(max.y-8):0};savePreference();}
    function desired(){const max=bounds();return preference?{x:8+preference.x*(max.x-8),y:8+preference.y*(max.y-8)}:{x:innerWidth>950?258:innerWidth>650?200:12,y:max.y-24};}
    function place(x,y){const max=bounds();position={x:clamp(x,8,max.x),y:clamp(y,8,max.y)};companion.style.left=position.x+'px';companion.style.top=position.y+'px';}
    function setCompact(value){
      compact=value;companion.classList.toggle('sd-rocket-compact',compact);companion.dataset.mode=compact?'compact':'full';
      sizeButton.textContent=compact?'↗':'−';sizeButton.setAttribute('aria-label',compact?'Show full rocket':'Minimize rocket');sizeButton.title=compact?'Show full rocket':'Minimize rocket';
      controls.querySelector('[data-rocket-controls-size]').textContent=compact?'Show full rocket':'Minimize rocket';
    }
    function setInline(value){
      inline=value;companion.classList.toggle('sd-rocket-inline',inline);
      if(inline){const top=root.querySelector('.sd-top');if(top?.nextElementSibling!==companion)(top||root.firstElementChild)?.after(companion);}
      else if(companion.parentElement!==root)root.append(companion);
    }
    function visibleRect(node){
      if(!node.getClientRects().length||node.closest('[hidden],[inert]'))return null;
      const style=getComputedStyle(node);if(style.visibility==='hidden'||style.display==='none'||style.opacity==='0')return null;
      const rect=node.getBoundingClientRect();if(rect.width<=0||rect.height<=0||rect.bottom<=0||rect.right<=0||rect.top>=innerHeight||rect.left>=innerWidth)return null;
      // A scrolled control outside its clipping parent is not a visible obstacle.
      let left=Math.max(0,rect.left),right=Math.min(innerWidth,rect.right),top=Math.max(0,rect.top),bottom=Math.min(innerHeight,rect.bottom);
      for(let parent=node.parentElement;parent&&parent!==root;parent=parent.parentElement){const css=getComputedStyle(parent);if(/auto|scroll|hidden|clip/.test(css.overflow+css.overflowX+css.overflowY)){const clip=parent.getBoundingClientRect();left=Math.max(left,clip.left);right=Math.min(right,clip.right);top=Math.max(top,clip.top);bottom=Math.min(bottom,clip.bottom);}}
      return right>left&&bottom>top?{left,right,top,bottom}:null;
    }
    function obstacles(){
      const selector='button,a[href],input,select,textarea,summary,[role="button"],[role="tab"],[role="menuitem"],[role="slider"],[tabindex],[data-action],[data-kind][data-id]';
      return [...root.querySelectorAll(selector)].filter(node=>!companion.contains(node)&&!node.closest('dialog')).map(visibleRect).filter(Boolean);
    }
    // Sweep horizontal boundaries, then merge forbidden vertical intervals. A safe
    // slot is found without sampling pixels or changing the page's content width.
    function safePoint(preferred,rects,dock=false){
      const size=dimensions(),max=bounds();if(size.width>innerWidth-16||size.height>innerHeight-16)return null;
      const xs=new Set([8,max.x,clamp(preferred.x,8,max.x)]);
      for(const rect of rects){xs.add(clamp(rect.left-size.width-gap,8,max.x));xs.add(clamp(rect.right+gap,8,max.x));}
      let best=null,bestScore=Infinity;
      for(const x of xs){
        const intervals=rects.filter(r=>x<r.right+gap&&x+size.width>r.left-gap).map(r=>[r.top-size.height-gap,r.bottom+gap]).filter(r=>r[1]>8&&r[0]<max.y).sort((a,b)=>a[0]-b[0]);
        const free=[];let start=8;
        for(const [low,high] of intervals){if(low>start)free.push([start,Math.min(low,max.y)]);start=Math.max(start,high);if(start>max.y)break;}
        if(start<=max.y)free.push([start,max.y]);
        for(const [low,high] of free){
          if(high<low)continue;
          for(const y of dock?[clamp(preferred.y,low,high),low,high]:[clamp(preferred.y,low,high)]){
            const edge=Math.min(x-8,max.x-x,y-8,max.y-y);
            const score=Math.hypot(x-preferred.x,y-preferred.y)+(dock?edge*10000:edge*.02);
            if(score<bestScore){best={x,y};bestScore=score;}
          }
        }
      }
      return best;
    }
    function refreshNow({dock=false,announce=false,passive=false}={}){
      cancelAnimationFrame(refreshFrame);refreshFrame=0;pendingRefresh=null;if(pointer)return;
      const blocked=!!document.querySelector('dialog[open]');
      companion.classList.toggle('sd-rocket-obscured',blocked);pause(blocked||compact);
      if(blocked)return;
      // Scroll moves page controls beneath this viewport-fixed companion. Chasing
      // those controls on every frame made its position and full/compact mode
      // oscillate. Incidental sticky/lazy-layout mutations during scrolling must
      // not repark it either. Deliberate host renders, resize and user controls
      // still request a fresh safe position; there is no scroll-end snap.
      if(passive&&performance.now()<scrollUntil)return;
      setInline(false);setCompact(userCompact);
      let preferred=desired(),rects=obstacles(),safe=safePoint(preferred,rects,dock);
      if(!safe&&!compact){setCompact(true);preferred=desired();safe=safePoint(preferred,rects,dock);}
      if(safe)place(safe.x,safe.y);
      else{
        // Extremely dense screens get normal-flow access, so even the compact
        // launcher never steals a page control's hit target.
        setCompact(true);setInline(true);
      }
      pause(compact);
      const note=inline?'Compact access is below the workspace header because this screen has no clear floating space.':compact?(userCompact?'The rocket is minimized. Use Show full rocket to restore it.':'Compact access was selected for this layout. Dock safely checks the current controls; Show full rocket restores it when space permits.'):'The full rocket stays at its chosen position while you scroll. Dock safely checks the current controls.';
      controls.querySelector('[data-rocket-placement-note]').textContent=note;
      if(announce)status.textContent=note;
      savePreference();
    }
    function refresh(options={}){
      const passive=options.passive===true;
      pendingRefresh={...pendingRefresh,...options,passive:pendingRefresh?pendingRefresh.passive===true&&passive:passive};
      if(!refreshFrame)refreshFrame=requestAnimationFrame(()=>refreshNow(pendingRefresh));
    }
    function reset(){preference=null;userCompact=false;refreshNow({dock:true,announce:true});remember();}
    function resize(){refresh();}
    function toggleSize(){userCompact=!compact;savePreference();refreshNow({announce:true});}
    sizeButton.addEventListener('click',toggleSize);
    optionsButton.addEventListener('click',()=>{controls.showModal();refreshNow();});
    controls.querySelector('[data-rocket-controls-close]').addEventListener('click',()=>controls.close());
    controls.querySelector('[data-rocket-dock]').addEventListener('click',()=>{controls.close();refreshNow({dock:true,announce:true});remember();launcher.focus({preventScroll:true});});
    controls.querySelector('[data-rocket-reset]').addEventListener('click',()=>{controls.close();reset();launcher.focus({preventScroll:true});});
    controls.querySelector('[data-rocket-controls-size]').addEventListener('click',()=>{controls.close();toggleSize();launcher.focus({preventScroll:true});});
    controls.addEventListener('close',()=>refresh());
    function flush(){queued=0;if(next){place(next.x,next.y);next=null;}}
    launcher.addEventListener('pointerdown',event=>{
      if(event.button!==0||event.isPrimary===false||inline)return;
      clearTimeout(clickTimer);clearTimeout(keyboardTimer);launcher.dataset.suppressClick='false';
      pointer={id:event.pointerId,x:event.clientX,y:event.clientY,left:position.x,top:position.y,dragged:false};
      try{launcher.setPointerCapture(event.pointerId);}catch{}
    });
    launcher.addEventListener('pointermove',event=>{
      if(!pointer||event.pointerId!==pointer.id)return;
      const dx=event.clientX-pointer.x,dy=event.clientY-pointer.y;if(!pointer.dragged&&Math.hypot(dx,dy)<6)return;
      pointer.dragged=true;launcher.dataset.dragging='true';companion.classList.add('sd-rocket-dragging');event.preventDefault();
      next={x:pointer.left+dx,y:pointer.top+dy};if(!queued)queued=requestAnimationFrame(flush);
    });
    function end(event){
      if(!pointer||event.pointerId!==pointer.id)return;
      const wasDragged=pointer.dragged;pointer=null;cancelAnimationFrame(queued);flush();
      launcher.dataset.dragging='false';companion.classList.remove('sd-rocket-dragging');
      if(wasDragged){event.preventDefault();launcher.dataset.suppressClick='true';remember();refreshNow({announce:true});clickTimer=setTimeout(()=>launcher.dataset.suppressClick='false',400);}
      try{if(launcher.hasPointerCapture(event.pointerId))launcher.releasePointerCapture(event.pointerId);}catch{}
    }
    launcher.addEventListener('pointerup',end);launcher.addEventListener('pointercancel',end);launcher.addEventListener('lostpointercapture',end);
    launcher.addEventListener('keydown',event=>{
      if(!event.altKey||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home'].includes(event.key))return;
      event.preventDefault();event.stopPropagation();if(event.key==='Home'){reset();return;}
      if(inline)return;
      const step=event.shiftKey?32:16;place(position.x+(event.key==='ArrowLeft'?-step:event.key==='ArrowRight'?step:0),position.y+(event.key==='ArrowUp'?-step:event.key==='ArrowDown'?step:0));remember();
      clearTimeout(keyboardTimer);keyboardTimer=setTimeout(()=>refreshNow({announce:true}),150);
    });
    launcher.addEventListener('keyup',event=>{if(event.key.startsWith('Arrow')){clearTimeout(keyboardTimer);refreshNow({announce:true});}});
    window.addEventListener('resize',resize);
    window.addEventListener('scroll',()=>{scrollUntil=performance.now()+200;},{capture:true,passive:true});
    const observer=new MutationObserver(records=>{
      if(records.some(record=>!companion.contains(record.target)&&!controls.contains(record.target)&&record.target!==companion))refresh({passive:true});
    });
    observer.observe(root,{subtree:true,childList:true,attributes:true,attributeFilter:['hidden','open','class','style','disabled']});
    if(document.body!==root)observer.observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:['open']});
    if(window.ResizeObserver){const resizeObserver=new ResizeObserver(()=>refresh({passive:true}));resizeObserver.observe(root);const main=root.querySelector('.sd-main');if(main)resizeObserver.observe(main);}
    refreshNow();return {refresh};
  }
  window.SixDRocketAssistant=Object.freeze({mount,open:tab=>current?.api.open(tab),close:()=>current?.api.close(),
    setTab:tab=>current?.api.setTab(tab),isOpen:()=>current?.api.isOpen()??false,tab:()=>current?.api.tab()??'nemotron',
    setContext:text=>current?.api.setContext(text),setBusy:busy=>current?.api.setBusy(busy),announce:text=>current?.api.announce(text),refreshPlacement:()=>current?.api.refreshPlacement()});
})();
