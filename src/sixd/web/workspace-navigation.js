/* Browser locations contain navigation context only, never project data or credentials. */
(() => {
  'use strict';
  const PAGES = new Set(['home','projects','review-home','engineering','analysis','evidence','setup',
    'system','systems','chains','attitude','power','powered-flight','guided-ascent','staged-ascent',
    'simulation','scenarios','envelopes','simulation-imports','test-data','coverage','sources',
    'actions','comparison','changes','report','authoring','ai-quality','owner-settings']);
  const PARAMS = new Set(['system','view','kind','item','panel','scope','trajectory','run']);
  const VIEWS = new Set(['canvas','table','reader']);
  const PANELS = new Set(['details','evidence','assistant']);
  const KINDS = new Set(['input','model','requirement']);
  const SLOT = '__sixdNavigation';
  const text = value => typeof value === 'string' && value.length > 0 && value.length <= 500 && !/[\u0000-\u001f\u007f]/.test(value);
  function normalize(value) {
    if (!value || !PAGES.has(value.page)) throw new Error('That 6D view is not available.');
    if (value.page === 'home') return {page:'home'};
    if (value.page === 'projects') return {page:'projects'};
    if (!text(value.projectId) || !Number.isSafeInteger(value.revision) || value.revision < 1)
      throw new Error('The 6D location needs a valid project and saved revision.');
    const route = {projectId:value.projectId, revision:value.revision, page:value.page,
      system:value.system || 'overview', view:value.view || 'canvas', panel:value.panel || 'details'};
    if (!text(route.system) || !VIEWS.has(route.view) || !PANELS.has(route.panel))
      throw new Error('The 6D location contains an invalid view or panel.');
    if (value.selected) {
      if (!KINDS.has(value.selected.kind) || !text(value.selected.id)) throw new Error('The selected engineering item is invalid.');
      route.selected = {kind:value.selected.kind, id:value.selected.id};
    }
    if (value.aiScope !== undefined) {
      if (!['project','requirement'].includes(value.aiScope)) throw new Error('The investigation scope is invalid.');
      route.aiScope = value.aiScope;
    }
    if (value.trajectory) {
      if (!text(value.trajectory.modelId) || (value.trajectory.runId !== undefined && !text(value.trajectory.runId)))
        throw new Error('The saved trajectory location is invalid.');
      route.trajectory = {modelId:value.trajectory.modelId};
      if (value.trajectory.runId !== undefined) route.trajectory.runId = value.trajectory.runId;
    }
    return route;
  }
  function format(value) {
    const route = normalize(value);
    if (route.page === 'home') return '#/';
    if (route.page === 'projects') return '#/projects';
    const query = new URLSearchParams();
    if (route.system !== 'overview') query.set('system',route.system);
    if (route.view !== 'canvas') query.set('view',route.view);
    if (route.selected) {query.set('kind',route.selected.kind);query.set('item',route.selected.id);}
    if (route.panel !== 'details') query.set('panel',route.panel);
    if (route.aiScope) query.set('scope',route.aiScope);
    if (route.trajectory) {
      query.set('trajectory',route.trajectory.modelId);
      if (route.trajectory.runId) query.set('run',route.trajectory.runId);
    }
    return '#/projects/' + encodeURIComponent(route.projectId) + '/r/' + route.revision + '/' + route.page + (query.size ? '?' + query : '');
  }
  function parse(hash) {
    if (!hash || hash === '#') return null;
    if (hash === '#/' || hash === '#/home' || hash === '#/home/') return {page:'home'};
    if (typeof hash !== 'string' || hash.length > 4096 || !hash.startsWith('#/projects')) throw new Error('This is not a recognised 6D location.');
    if (hash === '#/projects' || hash === '#/projects/') return {page:'projects'};
    const match = /^#\/projects\/([^/]+)\/r\/([1-9]\d*)\/([^/?]+)(?:\?(.*))?$/.exec(hash);
    if (!match) throw new Error('This 6D location is incomplete.');
    const params = new URLSearchParams(match[4] || '');
    for (const key of params.keys()) if (!PARAMS.has(key) || params.getAll(key).length !== 1) throw new Error('This 6D location contains an unsupported or repeated option.');
    if (params.has('kind') !== params.has('item') || params.has('run') && !params.has('trajectory')) throw new Error('This 6D location has incomplete item information.');
    let projectId;
    try {projectId = decodeURIComponent(match[1]);} catch {throw new Error('The project location is not correctly encoded.');}
    return normalize({projectId,revision:Number(match[2]),page:match[3],system:params.get('system') || undefined,
      view:params.get('view') || undefined,panel:params.get('panel') || undefined,
      selected:params.has('kind') ? {kind:params.get('kind'),id:params.get('item')} : undefined,
      aiScope:params.get('scope') || undefined,
      trajectory:params.has('trajectory') ? {modelId:params.get('trajectory'),...(params.has('run') ? {runId:params.get('run')} : {})} : undefined});
  }
  function create({read,apply,onError=()=>{},onChange=()=>{}}) {
    let started=false, disposed=false, applying=false, current=null, maximum=0, pending=null, scheduled=false;
    let settled=Promise.resolve(), release=null, restoring=null, previousScrollRestoration=null;
    const indexOf = state => Number.isSafeInteger(state?.[SLOT]?.index) && state[SLOT].index >= 0 ? state[SLOT].index : null;
    function stateFor(index) {
      const base = window.history.state;
      return {...(base && typeof base === 'object' && !Array.isArray(base) ? base : {}),[SLOT]:{version:1,index}};
    }
    function locationMatches(target) {return window.location.hash === target.hash && indexOf(window.history.state) === target.index;}
    function adopt(route,index,replace=false) {
      const hash=format(route);
      if (replace) window.history.replaceState(stateFor(index),'',hash);
      current={hash,index};maximum=Math.max(maximum,index);onChange();
    }
    function sync() {
      if (!started || disposed || applying || restoring || pending) return;
      try {
        const route=normalize(read()),hash=format(route);
        if (hash === current.hash) return;
        const index=current.index+1;
        window.history.pushState(stateFor(index),'',hash);maximum=index;adopt(route,index);
      } catch(error) {onError(error);}
    }
    function start() {
      if (started || disposed) return;
      const route=normalize(read()),index=indexOf(window.history.state) ?? 0;
      if('scrollRestoration' in window.history){previousScrollRestoration=window.history.scrollRestoration;window.history.scrollRestoration='manual';}
      started=true;adopt(route,index,true);
      window.addEventListener('popstate',changed);window.addEventListener('hashchange',changed);
    }
    function cancel(target) {
      if (!locationMatches(target)) return;
      pending=null;
      if (target.index !== null && target.index !== current.index) {
        restoring={...current};window.history.go(current.index-target.index);
      } else {
        window.history.replaceState(stateFor(current.index),'',current.hash);
      }
    }
    async function drain() {
      applying=true;
      try {
        while (pending && !disposed && !restoring) {
          const target=pending;pending=null;
          try {
            const route=parse(target.hash);
            if (!route) throw new Error('This 6D location is empty.');
            const hash=format(route),index=target.index ?? current.index+1;
            if (hash === current.hash) {adopt(route,index,true);continue;}
            const accepted=await apply(route);
            if (disposed) return;
            if (accepted === false) {cancel(target);continue;}
            if (locationMatches(target)) adopt(normalize(read()),index,true);
            else if (!pending) {pending={hash:window.location.hash,index:indexOf(window.history.state)};}
          } catch(error) {onError(error);cancel(target);}
        }
      } finally {
        applying=false;scheduled=false;
        if (pending && !disposed) schedule();
        else if (!restoring) {const done=release;release=null;done?.();onChange();}
      }
    }
    function schedule() {
      if (scheduled || disposed) return;
      scheduled=true;
      if (!release) settled=new Promise(resolve=>{release=resolve;});
      queueMicrotask(()=>void drain());
    }
    function changed() {
      if (!started || disposed) return;
      if (restoring) {
        if (window.location.hash === restoring.hash && indexOf(window.history.state) === restoring.index) {
          restoring=null;const done=release;release=null;done?.();onChange();
        }
        return;
      }
      const target={hash:window.location.hash,index:indexOf(window.history.state)};
      if (target.hash === current.hash && target.index === current.index) return;
      pending=target;schedule();
    }
    return {getInitial:()=>parse(window.location.hash),start,sync,
      back:()=>window.history.back(),forward:()=>window.history.forward(),
      get canBack(){return !!current && current.index > 0;},
      get canForward(){return !!current && current.index < maximum;},
      get applying(){return applying || !!restoring;},get settled(){return settled;},
      dispose(){disposed=true;window.removeEventListener('popstate',changed);window.removeEventListener('hashchange',changed);if(previousScrollRestoration!==null)window.history.scrollRestoration=previousScrollRestoration;const done=release;release=null;done?.();}};
  }
  window.SixDNavigation={parse,format,create};
})();
