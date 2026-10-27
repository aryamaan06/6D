/* Layout-only navigation preference. Never remount project or authoring state. */
(() => {
  'use strict';
  let current=null;
  function mount(root){
    if(current?.root===root)return current.api;
    current?.api.dispose();
    const sidebar=root.querySelector('#sd-sidebar'),button=root.querySelector('#sd-sidebar-toggle');
    if(!sidebar||!button)throw Error('The sidebar layout controls are missing.');
    const storageKey='sixd.sidebar.layout.v1',media=window.matchMedia('(max-width:650px)');
    let preferences={desktop:false,mobile:true};
    try{const saved=JSON.parse(localStorage.getItem(storageKey)||'null');if(saved?.version===1&&typeof saved.desktop==='boolean'&&typeof saved.mobile==='boolean')preferences={desktop:saved.desktop,mobile:saved.mobile};}catch{}
    const mode=()=>media.matches?'mobile':'desktop';
    function apply(announce=false){
      const collapsed=preferences[mode()];
      if(collapsed&&sidebar.contains(document.activeElement))button.focus({preventScroll:true});
      sidebar.hidden=collapsed;
      root.classList.toggle('sd-sidebar-collapsed',collapsed);
      root.classList.toggle('sd-tree-open',!collapsed);
      button.setAttribute('aria-expanded',String(!collapsed));
      button.setAttribute('aria-label',collapsed?'Show sidebar':'Hide sidebar');
      button.title=(collapsed?'Show':'Hide')+' sidebar (Ctrl/Cmd + \\)';
      button.querySelector('[data-sidebar-label]').textContent=collapsed?'Show sidebar':'Hide sidebar';
      if(announce){const status=root.querySelector('#sd-sidebar-status');if(status)status.textContent=collapsed?'Sidebar hidden. The project stays open.':'Sidebar shown. Your current project and page are unchanged.';}
    }
    function toggle(){
      preferences[mode()]=!preferences[mode()];
      try{localStorage.setItem(storageKey,JSON.stringify({version:1,...preferences}));}catch{}
      apply(true);
      // Existing plots and companion placement can respond to the new geometry.
      window.dispatchEvent(new Event('resize'));
    }
    const click=event=>{if(event.target.closest('#sd-sidebar-toggle'))toggle();};
    const keyboard=event=>{if((event.ctrlKey||event.metaKey)&&!event.altKey&&(event.code==='Backslash'||event.key==='\\')){event.preventDefault();toggle();}};
    const breakpoint=()=>{apply();window.dispatchEvent(new Event('resize'));};
    root.addEventListener('click',click);root.addEventListener('keydown',keyboard);media.addEventListener('change',breakpoint);
    apply();
    const api={toggle,refresh:()=>apply(),dispose(){root.removeEventListener('click',click);root.removeEventListener('keydown',keyboard);media.removeEventListener('change',breakpoint);if(current?.api===api)current=null;}};
    current={root,api};return api;
  }
  window.SixDSidebar=Object.freeze({mount,toggle:()=>current?.api.toggle()});
})();
