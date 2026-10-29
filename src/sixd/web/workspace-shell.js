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
  const toolTypes = [
    ['power','power_energy_budget','power_budget'],
    ['attitude','attitude_control','attitude_response'],
    ['vertical-mode','powered_flight','flight_response'],
    ['guided-ascent','guided_ascent','guided_response'],
    ['staged-ascent','staged_ascent','staged_response'],
    ['simulation','orbital_trajectory','simulation']
  ];
  // A display summary of the selected saved view. Receipt validation remains on
  // the server; declarations and older receipts never become completed results.
  function toolSummary(view,{hasDraft=false}={}) {
    if(!view?.project)return null;
    const models=Array.isArray(view.project.models)?view.project.models:[];
    const revision=view.revision,run=view.run;
    const receipt=run?.schema==='sixd.workspace-run.v1'&&run.run_id&&run.review?.digest&&
      run.project_id===view.project_id&&Number(run.revision)===Number(revision)&&!run.stale&&
      run.review.project?.project_id===view.project_id&&Number(run.review.project?.revision)===Number(revision)?run:null;
    const byAction={};
    for(const [action,type,artifact] of toolTypes) {
      const configured=models.filter(model=>model.type===type);
      let recorded=0,blocked=0;
      for(const model of configured) {
        const result=receipt?.model_results?.[model.id];
        if(result?.model_id!==model.id||result?.model_type!==type)continue;
        if(result.status==='completed'&&result[artifact]&&typeof result[artifact]==='object')recorded++;
        else if(['invalid_inputs','not_assessed'].includes(result.status))blocked++;
      }
      const count=configured.length;
      const state=!count?'unconfigured':recorded===count?'recorded':recorded?'partial':blocked?'blocked':'configured';
      const label={unconfigured:'Not configured for this project',configured:'Configured · not calculated',
        blocked:'Configured · calculation blocked',partial:'Recorded calculation · partial',recorded:'Recorded calculation'}[state];
      const navLabel={unconfigured:'Not configured',configured:'Not calculated',blocked:'Calculation blocked',
        partial:'Some recorded',recorded:'Recorded'}[state]+(count?' · R'+revision:'');
      const detail=count?count+' configured '+(count===1?'model':'models')+' · '+recorded+' completed '+(recorded===1?'result':'results')+' in saved R'+revision+'.'+
        (blocked?' '+blocked+' '+(blocked===1?'calculation is':'calculations are')+' blocked or unassessed; open the tool for the recorded reason.':''):
        'Available to configure in this project.';
      byAction[action]={state,label,navLabel,detail,configured:count,recorded,blocked};
    }
    return {projectId:view.project_id,revision,latestRevision:view.latest_revision,
      historical:Number(revision)!==Number(view.latest_revision),hasDraft,byAction,
      priorRevision:!receipt&&view.prior_run?.project_id===view.project_id?view.prior_run.revision:null};
  }
  function scopedTools(tools,projectId,revision) {
    return tools?.projectId===projectId&&(revision===undefined||Number(tools.revision)===Number(revision))?tools:null;
  }
  const toolBadge = (status,compact=false) => status?'<span class="sd-tool-status sd-tool-'+esc(status.state)+'" title="'+esc(status.label+'. '+status.detail)+'">'+esc(compact?status.navLabel:status.label)+'</span>':'';
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
  const button = (action,label,description,icon='arrow-up-right',status=null) => '<button type="button" class="sd-destination" data-action="'+esc(action)+'"><span class="sd-destination-copy"><strong>'+esc(label)+'</strong>'+toolBadge(status)+'<span>'+esc(description)+'</span>'+(status?'<span class="sd-tool-detail">'+esc(status.detail)+'</span>':'')+'</span><i data-lucide="'+icon+'" aria-hidden="true"></i></button>';
  const normalizedProjectName = value => String(value ?? '').trim().replace(/\s+/g,' ').toLowerCase();
  const readableType = value => String(value ?? '').replace(/_/g,' ').trim();
  function projectHint(project) {
    const hints=[];
    if(project.project_type)hints.push('Type: '+readableType(project.project_type));
    if(project.lifecycle_stage)hints.push('Stage: '+readableType(project.lifecycle_stage));
    const types=Array.isArray(project.model_types)?project.model_types:
      Array.isArray(project.models)?project.models.map(model=>model?.type):[];
    const labels=[...new Set(types.filter(type=>typeof type==='string'&&type.trim()).map(readableType))].sort();
    if(labels.length)hints.push('Model '+(labels.length===1?'type: ':'types: ')+labels.join(', '));
    return hints.join(' · ');
  }
  // Display-only identities. Never write the clarified label back to a saved name,
  // or use its suffix as a route/storage key. The server owns unique project IDs.
  function projectChoices(projects) {
    const rows=Array.isArray(projects)?projects:[],names=new Map();
    for(const project of rows) {
      const key=normalizedProjectName(project.name||project.project_id);
      names.set(key,(names.get(key)||0)+1);
    }
    const ids=[...new Set(rows.map(project=>String(project.project_id)))];
    return rows.map(project=>{
      const id=String(project.project_id),name=String(project.name??'').trim()?String(project.name):id;
      let length=Math.min(6,id.length);
      while(length<id.length&&ids.some(other=>other!==id&&other.endsWith(id.slice(-length))))length++;
      const identity_label=(length<id.length?'…':'')+id.slice(-length);
      const duplicate=names.get(normalizedProjectName(project.name||project.project_id))>1;
      return {...project,display_name:name+(duplicate?' · '+identity_label:''),identity_label,project_hint:projectHint(project)};
    });
  }
  function projectCreatedAt(value) {
    if(!value)return '';
    const date=new Date(value);
    return Number.isNaN(date.getTime())?'':'Created '+date.toISOString().slice(0,16).replace('T',' ')+' UTC';
  }
  function projectCard(project,currentId) {
    const id=String(project.project_id),created=projectCreatedAt(project.created_at);
    return '<button type="button" class="sd-project-card" data-open-project="'+esc(id)+'" title="Project ID: '+esc(id)+'" aria-label="'+esc(project.display_name+' · Revision R'+project.revision+' · Project ID: '+id)+'"><span class="sd-label">Saved project'+(project.project_id===currentId?' · Current':'')+'</span><strong>'+esc(project.display_name)+'</strong><span class="sd-project-id">ID '+esc(project.identity_label)+'</span>'+(project.project_hint?'<span class="sd-project-hint">'+esc(project.project_hint)+'</span>':'')+'<span class="sd-project-meta">Revision R'+esc(project.revision)+(created?'<span class="sd-project-created">'+esc(created)+'</span>':'')+'</span><span class="sd-project-open">Open project <i data-lucide="arrow-right" aria-hidden="true"></i></span></button>';
  }
  function hub(page,projects,currentId,tools=null) {
    if (page === 'projects') return '<section class="sd-project-home" aria-label="Your projects"><div class="sd-home-intro"><span class="sd-label">Your workspace</span><h2>Choose a project to begin.</h2><p>Open a saved design, then choose the engineering or review task you want to work on.</p></div><div class="sd-project-grid">'+projectChoices(projects).map(project=>projectCard(project,currentId)).join('')+'</div><section class="sd-home-start"><h3>Start something new</h3><div class="sd-destination-grid">'+button('rocket-reference','Try the rocket example','Rocket reference → Create project → Run checks → Explore & test.')+button('new-project','Create a project','Start empty and define your own supported checks.')+button('import','Import or use a template','Reference templates → Create project → Run checks → Explore & test.')+'</div></section></section>';
    const area = areaFor(page);
    tools=scopedTools(tools,currentId);
    const showTools=tools&&['engineering','analysis'].includes(page);
    const context=showTools?'<p class="sd-tool-context">Saved R'+esc(tools.revision)+(tools.historical?' · Historical revision; latest is R'+esc(tools.latestRevision):' · Selected project')+'. Tool status describes declared models and completed saved calculations.'+(tools.hasDraft?' Draft edits have not been calculated.':'')+(tools.priorRevision!==null?' Earlier calculation for R'+esc(tools.priorRevision)+' is retained in history and is not counted here.':'')+'</p>':'';
    return '<section class="sd-area-home" aria-label="'+esc(area.label)+'"><p class="sd-area-intro">'+esc(area.description)+'</p>'+context+'<div class="sd-destination-grid">'+area.items.map(i=>button(i[0],i[1],i[2],'arrow-up-right',tools?.byAction[i[0]])).join('')+'</div><p class="sd-area-note">Opening a tool does not run calculations or start AI. Use its explicit action when you are ready.</p></section>';
  }
  function renderChrome({page,project,revision,system,selected,backEnabled,tools=null}) {
    const area = areaFor(page), isHub=hubs.has(page), root=document.querySelector('#sixd-workspace');
    tools=scopedTools(tools,project.project_id,revision);
    root.classList.toggle('sd-navigation-hub',isHub);
    root.classList.toggle('sd-projects-home',page==='projects');
    document.querySelector('#sd-primary-nav').innerHTML=areas.map(a=>'<button type="button" class="sd-area-link" data-action="'+a.id+'"'+(a===area?' aria-current="page"':'')+'><i data-lucide="'+a.icon+'" aria-hidden="true"></i>'+esc(a.label)+'</button>').join('');
    const menu=document.querySelector('#sd-section-menu');
    menu.hidden=!area||!area.items.length||isHub;
    menu.innerHTML=area&&area.items.length?'<span class="sd-label">'+esc(area.label)+'</span>'+area.items.map(i=>'<button type="button" class="sd-section-link" data-action="'+i[0]+'"'+((i[3]||i[0])===page?' aria-current="page"':'')+'><span>'+esc(i[1])+'</span>'+toolBadge(tools?.byAction[i[0]],true)+'</button>').join(''):'';
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
  window.SixDWorkspaceShell={areas,hubs,areaFor,labelFor,toolSummary,projectChoices,hub,renderChrome};
})();
