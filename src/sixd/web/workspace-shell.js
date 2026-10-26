/* Hierarchical access to existing views. No inference, calculations or storage. */
(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const areas = [
    {id:'review-home',label:'Overview',icon:'house',description:'Start with the saved design, current findings and next step.',items:[]},
    {id:'engineering',label:'Engineering',icon:'boxes',description:'Explore the design, its inputs and the calculations that support it.',items:[
      ['system','Systems workspace','Explore systems and their inputs, calculations and requirements.'],
      ['systems','Systems & interfaces','Define subsystem ownership and declared interface contracts.'],
      ['chains','Calculation chains','Inspect the scalar links between supported calculations.'],
      ['power','Power & energy','Inspect supplied power and energy budgets.'],
      ['attitude','Guidance & control','Inspect the bounded single-axis pointing model.'] ]},
    {id:'analysis',label:'Simulations & studies',icon:'orbit',description:'Choose the type of analysis, then inspect its saved runs or configure an explicit calculation.',items:[
      ['vertical-mode','Vertical flight','Thrust, propellant, gravity and drag along a vertical path.','powered-flight'],
      ['guided-ascent','Planar ascent','Horizontal and vertical motion with supplied steering.'],
      ['staged-ascent','Variable thrust & staging','Serial stages, thrust profiles and propellant events.'],
      ['simulation','Orbital simulation','Inspect or calculate bounded two-body orbital trajectories.'],
      ['scenarios','Scenarios','Compare explicit hypothetical alternatives with a baseline.'],
      ['envelopes','Envelope studies','Explore a declared grid of operating conditions.'] ]},
    {id:'evidence',label:'Evidence & review',icon:'files',description:'Understand what was checked, what changed and which supporting records remain applicable.',items:[
      ['coverage','Engineering coverage','Distinguish calculated findings from unassessed scope.'],
      ['changes','Changes','Review input changes and affected dependencies.'],
      ['comparison','Compare designs','Compare saved revisions and their findings.'],
      ['sources','Source library','Review supplied references and optional source research.'],
      ['test-data','Test data','Compare supplied measurements with saved predictions.'],
      ['simulation-imports','Simulation imports','Import and compare supported specialist time histories.'],
      ['actions','Engineering actions','Track follow-up and evidence needing attention.'],
      ['report','Review report','Read the saved conclusions and export their evidence.'] ]},
    {id:'setup',label:'Project setup',icon:'settings-2',description:'Define the project, open a reference example or inspect AI quality and connections.',items:[
      ['author-project','Author project','Define sourced inputs, supported models and requirements.','authoring'],
      ['rocket-reference','Rocket reference','Create a constructed baseline, thrust-change and correction example.'],
      ['import','Import or use a template','Start from a supported file or another reference template.'],
      ['new-project','New project','Create an empty engineering project.'],
      ['owner-settings','Owner settings','Manage connections, usage and verification tools.'] ]}
  ];
  const hubs = new Set(['projects','engineering','analysis','evidence','setup','owner-settings']);
  function areaFor(page) {
    if (page === 'projects') return null;
    if(page==='ai-quality')return areas.find(a=>a.id==='setup');
    return areas.find(a => a.id === page || a.items.some(i => (i[3] || i[0]) === page)) || areas[0];
  }
  function labelFor(page) {
    if (page === 'projects') return 'Projects';
    if(page==='ai-quality')return 'Owner AI quality & tools';
    const area = areaFor(page);
    return area.items.find(i => (i[3] || i[0]) === page)?.[1] || area.label;
  }
  const button = (action,label,description,icon='arrow-up-right') => '<button type="button" class="sd-destination" data-action="'+esc(action)+'"><span class="sd-destination-copy"><strong>'+esc(label)+'</strong><span>'+esc(description)+'</span></span><i data-lucide="'+icon+'" aria-hidden="true"></i></button>';
  function hub(page,projects,currentId) {
    if (page === 'projects') return '<section class="sd-project-home" aria-label="Your projects"><div class="sd-home-intro"><span class="sd-label">Your workspace</span><h2>Choose a project to begin.</h2><p>Open a saved design, then choose the engineering or review task you want to work on.</p></div><div class="sd-project-grid">'+projects.map(p=>'<button type="button" class="sd-project-card" data-open-project="'+esc(p.project_id)+'"><span class="sd-label">Saved project'+(p.project_id===currentId?' · Current':'')+'</span><strong>'+esc(p.name||p.project_id)+'</strong><span class="sd-project-meta">Revision R'+esc(p.revision)+'</span><span class="sd-project-open">Open project <i data-lucide="arrow-right" aria-hidden="true"></i></span></button>').join('')+'</div><section class="sd-home-start"><h3>Start something new</h3><div class="sd-destination-grid">'+button('rocket-reference','Try the rocket example','Learn how a design change affects recorded conclusions.')+button('new-project','Create a project','Start empty and define your own supported checks.')+button('import','Import or use a template','Bring a supported file or choose another reference example.')+'</div></section></section>';
    const area = areaFor(page);
    return '<section class="sd-area-home" aria-label="'+esc(area.label)+'"><p class="sd-area-intro">'+esc(area.description)+'</p><div class="sd-destination-grid">'+area.items.map(i=>button(i[0],i[1],i[2])).join('')+'</div><p class="sd-area-note">Opening a tool does not run calculations or start AI. Use its explicit action when you are ready.</p></section>';
  }
  function renderChrome({page,project,revision,system,selected,backEnabled}) {
    const area = areaFor(page), isHub=hubs.has(page), root=document.querySelector('#sixd-workspace');
    root.classList.toggle('sd-navigation-hub',isHub);
    root.classList.toggle('sd-projects-home',page==='projects');
    document.querySelector('#sd-primary-nav').innerHTML=areas.map(a=>'<button type="button" class="sd-area-link" data-action="'+a.id+'"'+(a===area?' aria-current="page"':'')+'><i data-lucide="'+a.icon+'" aria-hidden="true"></i>'+esc(a.label)+'</button>').join('');
    const menu=document.querySelector('#sd-section-menu');
    menu.hidden=!area||!area.items.length||isHub;
    menu.innerHTML=area&&area.items.length?'<span class="sd-label">'+esc(area.label)+'</span>'+area.items.map(i=>'<button type="button" class="sd-section-link" data-action="'+i[0]+'"'+((i[3]||i[0])===page?' aria-current="page"':'')+'>'+esc(i[1])+'</button>').join(''):'';
    document.querySelector('#sd-system-tree-section').hidden=page!=='system';
    document.querySelector('#sd-context-tools').hidden=page!=='system';
    document.querySelector('#sd-analysis-legacy').hidden=true;
    const trail=['<button type="button" data-action="projects">Projects</button>'];
    if(page!=='projects') {
      trail.push('<button type="button" data-action="review-home">'+esc(project.name)+'</button>');
      if(area&&area.id!==page)trail.push('<button type="button" data-action="'+area.id+'">'+esc(area.label)+'</button>');
      trail.push('<span aria-current="page">'+esc(labelFor(page))+'</span>');
      if(page==='system'&&system&&system.id!=='overview')trail.push('<span>'+esc(system.title)+'</span>');
      if(page==='system'&&selected)trail.push('<span class="sd-location-item">'+esc(selected)+'</span>');
    }
    document.querySelector('#sd-location-trail').innerHTML=trail.join('<span class="sd-crumb-separator" aria-hidden="true">/</span>');
    document.querySelector('[data-action="navigation-back"]').disabled=!backEnabled;
    if(isHub) {
      document.querySelector('#sd-page-title').textContent=labelFor(page);
      document.querySelector('#sd-page-description').textContent=page==='projects'?'Your saved projects and a clear place to start.':area.description;
    }
    if(page!=='system') document.querySelector('#sd-page-title').dataset.location=labelFor(page)+' · R'+revision;
    document.title=page==='projects'?'Projects | 6D':labelFor(page)+' · '+project.name+' | 6D';
  }
  window.SixDWorkspaceShell={areas,hubs,areaFor,labelFor,hub,renderChrome};
})();
