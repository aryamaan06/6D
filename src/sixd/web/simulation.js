/* Recorded 3D state playback. The browser never integrates orbital physics. */
(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = value => Number.isFinite(value) ? Number(value).toLocaleString('en-US', {maximumSignificantDigits:7}) : '—';
  const exact = value => Number.isFinite(value) ? String(value) : '—';
  const clone = value => JSON.parse(JSON.stringify(value));
  const sessions = new Map();
  let active = null;
  function unmount() {
    if (!active) return;
    active.closed = true;
    cancelAnimationFrame(active.raf);
    active.resize?.disconnect();
    active.abort.abort();
    active = null;
  }
  function mount(host, options) {
    unmount();
    const key = options.projectId + ':' + options.revision;
    if (!sessions.has(key)) sessions.set(key, {spec:null,runId:null,mode:null,modelId:null,index:0,projection:'3d',yaw:-.65,pitch:.45,zoom:1});
    const session = sessions.get(key);
    const a = active = {host, options, session, closed:false, abort:new AbortController(), raf:0, playing:false, speed:300, detail:null, baseline:null, comparison:null, list:[], running:false, request:0};
    host.innerHTML = '<div class="sim-loading">Reading simulation records…</div>';
    const q = '?project_id=' + encodeURIComponent(options.projectId) + '&revision=' + options.revision;
    Promise.all([options.api('/api/simulations' + q),options.api('/api/status')]).then(async ([payload,status]) => {
      if (a.closed) return;
      a.list = payload.simulations || []; a.projectModels=payload.project_models || [];a.defaultSpec = payload.default_spec; a.staleServer = !!status.restart_required;
      if (!session.spec) session.spec = clone(a.defaultSpec);
      if(options.modelId){session.mode='project';session.modelId=options.modelId;}
      if(!session.mode)session.mode=a.projectModels.length||!a.list.length?'project':'exploratory';
      if(!a.projectModels.some(m=>m.model_id===session.modelId))session.modelId=a.projectModels[0]?.model_id||null;
      const records=modeRuns(a),requested=options.modelId&&options.workspaceRunId;
      const currentModel=a.projectModels.find(m=>m.model_id===session.modelId);
      const selected=requested?records.find(r=>r.model_id===options.modelId&&r.workspace_run_id===options.workspaceRunId):options.modelId?records.find(r=>r.simulation_id===currentModel?.simulation_id):records.find(r=>r.simulation_id===session.runId)||records.find(r=>r.simulation_id===currentModel?.simulation_id)||records.find(r=>r.revision===options.revision);
      if (selected) a.detail = await options.api('/api/simulations/' + encodeURIComponent(selected.simulation_id)+'?revision='+options.revision);
      if (a.closed) return;
      if(a.detail){session.runId = a.detail.receipt.simulation_id;if(projectReceipt(a.detail.receipt))session.modelId=a.detail.receipt.model_id;}
      else session.runId=null;
      render(a);
      if(requested&&!selected)error(a,'The requested saved trajectory is not available in this project/revision history. No other run was substituted.');
    }).catch(error=>{if(!a.closed)host.innerHTML='<p class="sd-error" role="alert">'+esc(error.message)+'</p>';});
  }
  const result = a => a.detail?.receipt.result;
  const samples = a => result(a)?.samples || [];
  const hasDraft = a => a.options.hasDraft;
  const projectReceipt = r => r?.binding_kind==='project_model';
  const modeRuns = a => a.list.filter(r=>projectReceipt(r)===(a.session.mode==='project'));
  function runName(item) {return (projectReceipt(item)?'Project evidence':'Exploratory')+' · R'+item.revision+' · '+item.spec.name+' · '+new Date(item.created_at).toLocaleString()+' · '+item.simulation_id.slice(0,12);}
  function projectWorkflow(a) {
    if(a.session.mode!=='project')return '<p class="sim-caption">Exploratory scenarios keep their own inputs. Their trajectories do not change project requirement findings. Use Project evidence for inputs and criteria managed through the engineering workflow.</p>';
    if(!a.projectModels.length)return '<section class="sim-project-guide"><span class="sd-label">Start a connected orbital review</span><h3>Connect a trajectory to engineering requirements.</h3><p>This project has no orbital model mapping. The reference project includes explicit starting conditions, sampled orbital limits and an independent thermal check. Create it, run its checks, then inspect or revise the evidence.</p><button type="button" class="sd-button sd-primary" id="sim-reference" '+(hasDraft(a)?'disabled':'')+'>Open orbital review template</button><p class="sim-caption">Constructed reference data for exploring the workflow. Creating a project does not run calculations.</p></section>';
    return '<section class="sim-project-guide"><div class="sim-section-title"><h3>Orbital models in saved R'+a.options.revision+'</h3><span class="sd-small sd-muted">Inputs → checks → trajectory → requirements</span></div><div class="sim-project-models">'+a.projectModels.map(m=>{
      const status=hasDraft(a)?'Draft · saved evidence only':({current:'Evidence recorded',not_run:'Needs calculation',not_assessed:'Not assessed',historical:'Needs recheck'}[m.status]||m.status);
      return '<div class="sim-project-model '+(a.session.modelId===m.model_id?'sim-project-selected':'')+'"><div><strong>'+esc(m.name||m.model_id)+'</strong><span class="sd-chip">'+esc(status)+'</span></div><p class="sim-caption">'+esc(m.model_id)+' · '+m.requirement_ids.length+' linked requirements</p><div class="sd-action-row"><button type="button" class="sd-button" data-sim-model="'+esc(m.model_id)+'" '+(!m.simulation_id?'disabled':'')+'>View saved trajectory</button><button type="button" class="sd-button" data-sim-inputs="'+esc(m.model_id)+'">Review / edit inputs</button></div></div>';
    }).join('')+'</div><div class="sd-action-row"><button type="button" class="sd-button sd-primary" id="sim-project-run" '+(hasDraft(a)||a.staleServer?'disabled':'')+'>Run affected checks</button></div><p class="sim-caption">Edit values and limits in the project Table or Inspector, preview the affected dependencies, save a revision, then run checks. Unchanged model results retain their recorded execution origin. '+(!a.options.canEdit?'Select the latest revision to create a new draft.':'')+'</p></section>';
  }
  function relatedFindings(a) {
    const r=a.detail?.receipt;if(!projectReceipt(r))return '';
    const current=!hasDraft(a)&&r.revision===a.options.revision&&r.workspace_run_id===a.options.currentRunId&&a.detail.freshness.source_current&&a.detail.freshness.selected_run_matches!==false;
    const labels={met:'Requirement met',not_met:'Requirement failed',not_assessed:'Not assessed',insufficient_accuracy:'Insufficient accuracy',accuracy_not_assessed:'Accuracy not assessed'};
    return '<section class="sim-related"><div class="sim-section-title"><h3>Requirements linked to this saved review</h3><span class="sd-chip">'+(current?'Selected saved review':'Historical / saved evidence')+'</span></div><p class="sim-caption">Each finding below belongs to the exact review and trajectory shown. Extrema apply only to stored samples over 0–'+esc(exact(r.spec.duration_s))+' s; final metrics apply at the last sample. No continuous-time safety bound is claimed.</p><div class="sd-table-wrap"><table class="sd-table"><thead><tr><th>Requirement</th><th>Finding</th><th>Recorded evidence</th><th>Review</th></tr></thead><tbody>'+(r.findings||[]).map(f=>{
      const e=f.evidence,title=r.project_snapshot?.requirements?.find(q=>q.id===f.requirement_id)?.title||f.requirement_id;
      return '<tr><th>'+esc(title)+'<div class="sd-small sd-muted">'+esc(f.metric)+'</div></th><td><span class="sd-chip '+(f.status==='met'?'sd-met':f.status==='not_met'?'sd-fail':'')+'">'+esc(labels[f.status]||f.status)+'</span></td><td>'+(e?esc(exact(e.metric.value))+' '+esc(e.metric.unit)+' '+esc(e.operator)+' '+esc(exact(e.limit.value))+' '+esc(e.limit.unit):esc(f.reason))+'</td><td><button type="button" class="sd-mini-action" data-sim-requirement="'+esc(f.requirement_id)+'" '+(!current?'disabled':'')+'>Inspect</button><button type="button" class="sd-mini-action" data-sim-investigate="'+esc(f.requirement_id)+'" '+(!current?'disabled':'')+'>Investigate</button></td></tr>';
    }).join('')+'</tbody></table></div>'+(!current?'<p class="sim-caption">These recorded findings stay inspectable here. Open their saved revision and current review before starting an investigation; a historical trajectory never changes the active requirement context.</p>':'')+'<p class="sim-binding">Workspace run '+esc(r.workspace_run_id)+'<br>Review '+esc(r.review_digest)+'<br>Model '+esc(r.model_id)+' · '+esc(r.model_origin?.disposition||'recorded')+' · execution origin R'+esc(r.model_origin?.revision)+' / '+esc(r.model_origin?.run_id)+'</p></section>';
  }
  function field(name,label,value,type='number',extra='') {
    return '<label class="sd-field">'+label+'<input class="sd-input" name="'+name+'" type="'+type+'" '+(type==='number'?'step="any"':'')+' value="'+esc(value)+'" required '+extra+'></label>';
  }
  function accuracyPanel(r) {
    if(!r)return '';
    if(!projectReceipt(r))return '<section class="sim-related" id="sim-accuracy"><h3>Numerical accuracy not assessed</h3><p class="sim-caption">This exploratory scenario has no project accuracy criteria or three-grid assessment. Its trajectory and conservation diagnostics do not establish numerical accuracy or change project findings.</p></section>';
    const q=r.numerical_accuracy,p=r.applicability;
    if(!q)return '<section class="sim-related" id="sim-accuracy"><h3>Historical accuracy evidence unavailable</h3><p class="sim-caption">This saved project review predates the explicit numerical accuracy assessment. Its original findings and samples are preserved; no current accuracy pass is inferred. Create a new reviewed revision with declared tolerances to assess accuracy.</p></section>';
    const labels={supported:'Refinement criteria supported',insufficient_accuracy:'Insufficient accuracy',not_assessed:'Accuracy not assessed'},c=q.criteria;
    let text='<section class="sim-related" id="sim-accuracy"><div class="sim-section-title"><h3>Numerical accuracy</h3><span class="sd-chip">'+esc(labels[q.status]||q.status)+'</span></div><p class="sim-caption">'+esc(q.reason)+'</p>';
    text+=c?'<dl class="sim-diagnostics"><dt>Declared position tolerance · m</dt><dd>'+esc(exact(c.position_tolerance_m))+'</dd><dt>Declared velocity tolerance · m/s</dt><dd>'+esc(exact(c.velocity_tolerance_m_s))+'</dd><dt>Accuracy requirement source</dt><dd>'+esc(c.source)+'</dd></dl>':'<p class="sim-caption">No position and velocity accuracy criteria were declared.</p>';
    if(q.comparisons?.length)text+='<div class="sd-table-wrap"><table class="sd-table"><thead><tr><th>Aligned grids · steps</th><th>Compared samples</th><th>Worst position difference · m</th><th>Worst velocity difference · m/s</th></tr></thead><tbody>'+q.comparisons.map(row=>'<tr><td>'+esc(row.coarse_steps)+' → '+esc(row.fine_steps)+'</td><td>'+esc(row.aligned_sample_count)+'</td><td>'+esc(exact(row.max_position_difference_m))+'</td><td>'+esc(exact(row.max_velocity_difference_m_s))+'</td></tr>').join('')+'</tbody></table></div><p class="sim-caption">Observed order: position '+esc(exact(q.observed_orders?.position))+'; velocity '+esc(exact(q.observed_orders?.velocity))+'. Accepted interval: '+esc(q.method?.accepted_order_min)+'–'+esc(q.method?.accepted_order_max)+'. Differences are not rigorous bounds on true trajectory error.</p>';
    if(p)text+='<h4>Physical applicability not assessed</h4><p class="sim-caption">'+esc(p.scope)+' '+esc(p.reference_disclosure)+'</p><h4>Enforced input and numerical checks</h4><ul class="sd-scope-list">'+(p.checks||[]).map(item=>'<li>'+esc(item)+'</li>').join('')+'</ul><h4>Requires external evidence</h4><ul class="sd-scope-list">'+(p.requires_external_evidence||[]).map(item=>'<li>'+esc(item)+'</li>').join('')+'</ul>';
    return text+'<details><summary>Accuracy limitations and retained evidence</summary><ul class="sd-scope-list">'+(q.limitations||[]).map(item=>'<li>'+esc(item)+'</li>').join('')+'</ul><p class="sim-caption">'+esc(r.accuracy_evidence_note)+'</p></details></section>';
  }
  function render(a) {
    stop(a); a.resize?.disconnect();
    const {host,session:s}=a, spec=s.spec, r=a.detail?.receipt,records=modeRuns(a);
    host.innerHTML = '<div class="sim-workspace">'+
      '<div class="sim-intro"><div><span class="sd-label">Simulation lab · orbital motion</span><h2>Follow the calculated path.</h2><p>Explore recorded position and velocity in three dimensions, then inspect the evidence at any instant.</p></div><span class="sd-chip">Local physics · no AI calls</span></div>'+
      '<div class="sim-workflow-tabs" role="group" aria-label="Simulation workflow"><button type="button" class="sd-button" data-sim-mode="project" aria-pressed="'+(s.mode==='project')+'">Project evidence</button><button type="button" class="sd-button" data-sim-mode="exploratory" aria-pressed="'+(s.mode==='exploratory')+'">Exploratory scenarios</button></div>'+
      (hasDraft(a)?'<p class="sd-notice">Unsaved project draft. Playback below belongs to a saved revision; save or discard your project draft before creating a simulation.</p>':'')+
      (a.staleServer?'<p class="sd-error" role="alert">Application code changed. Restart 6D before running a simulation. Saved histories remain readable.</p>':'')+
      projectWorkflow(a)+
      '<div class="sim-runbar"><label class="sd-field">Saved run<select class="sd-select" id="sim-run-picker"><option value="">Select a recorded run</option>'+records.map(item=>'<option value="'+esc(item.simulation_id)+'" '+(r?.simulation_id===item.simulation_id?'selected':'')+'>'+esc(runName(item))+'</option>').join('')+'</select></label><label class="sd-field">Compare with<select class="sd-select" id="sim-compare-picker" '+(!r?'disabled':'')+'><option value="">No comparison</option>'+a.list.filter(item=>item.simulation_id!==r?.simulation_id).map(item=>'<option value="'+esc(item.simulation_id)+'">'+esc(runName(item))+'</option>').join('')+'</select></label>'+
      '<button class="sd-button" id="sim-export" '+(!r?'disabled':'')+'>Export run JSON</button></div>'+
      '<p class="sim-binding" id="sim-binding">'+(r?(projectReceipt(r)?'Project evidence':'Exploratory scenario')+' · Recorded R'+r.revision+' · '+esc(r.spec.name)+' · '+esc(r.simulation_id)+(r.revision!==a.options.revision?' · Historical run; selected workspace is R'+a.options.revision:projectReceipt(r)&&a.detail.freshness.selected_run_matches===false?' · Historical review; not the selected revision’s current assessment':'')+(!a.detail.freshness.source_current?' · Calculation sources have changed; historical evidence only':''):'No recorded simulation selected. '+(s.mode==='project'?'Run the orbital model’s project checks above, or select preserved evidence from the history.':'Configure an exploratory scenario below.'))+'</p>'+
      '<div id="sim-error" class="sd-error" role="alert" hidden></div><div id="sim-comparison-note" class="sd-notice" hidden></div>'+
      accuracyPanel(r)+
      relatedFindings(a)+
      '<div class="sim-stage"><div class="sim-stage-header"><div class="sim-modes" role="group" aria-label="Trajectory projection">'+['3d','xy','xz','yz'].map(mode=>'<button class="sd-button" data-sim-projection="'+mode+'" aria-pressed="'+(s.projection===mode)+'">'+mode.toUpperCase()+'</button>').join('')+'</div><div class="sim-modes"><button class="sd-button" id="sim-zoom-out" aria-label="Zoom simulation out">−</button><button class="sd-button" id="sim-zoom-in" aria-label="Zoom simulation in">+</button><button class="sd-button" id="sim-reset-camera">Reset view</button></div></div>'+
      '<canvas id="sim-scene" tabindex="0" aria-label="Recorded three-dimensional orbital trajectory. Drag or use arrow keys to rotate; use zoom buttons to change scale."></canvas>'+
      '<div class="sim-scene-note"><span><span class="sim-dot"></span>Selected run <span id="sim-baseline-legend" hidden><span class="sim-dot sim-amber"></span>Comparison</span></span><span id="sim-camera-note">'+(r?'Drag to rotate · axes share one spatial scale':'Run a scenario to calculate its trajectory')+'</span></div></div>'+
      '<div class="sim-playback"><button class="sd-button sd-primary" id="sim-play" '+(!r?'disabled':'')+'>Play</button><button class="sd-button" id="sim-rewind" '+(!r?'disabled':'')+' aria-label="Return to first sample">↤</button><label class="sim-scrub">Recorded time<input id="sim-timeline" aria-label="Recorded time" type="range" min="0" max="'+Math.max(0,samples(a).length-1)+'" step="1" value="0" '+(!r?'disabled':'')+'></label><label class="sd-field sim-rate">Playback rate<select class="sd-select" id="sim-speed"><option value="60">60×</option><option value="300" selected>300×</option><option value="1000">1,000×</option></select></label><output id="sim-time">—</output></div>'+
      '<p class="sim-caption">Playback selects stored samples without interpolation. Lines connect those samples. The shaded sphere marks the supplied exclusion radius; the object marker is enlarged for visibility.</p>'+
      '<div class="sim-metrics" id="sim-metrics"></div>'+
      '<section class="sim-history"><div class="sim-section-title"><h3>Time history</h3><label class="sd-field"><span class="sr-only">Plotted quantity</span><select class="sd-select" id="sim-quantity" aria-label="Plotted quantity"><option value="radius_m">Radius · m</option><option value="speed_m_s">Speed · m/s</option><option value="position_m">Position · x, y, z · m</option><option value="specific_energy_j_kg">Specific orbital energy · J/kg</option></select></label></div><canvas id="sim-chart" aria-label="Time history from recorded samples" role="img"></canvas><p class="sim-caption">Elapsed time in seconds. Vertical scale adjusts to the recorded range; small numerical variations may appear magnified. Click the chart to select a saved sample.</p></section>'+
      '<details class="sim-details" id="sim-sample-details"><summary>Exact recorded sample</summary><div id="sim-sample-values"></div></details>'+
      (s.mode==='exploratory'?'<details class="sim-details" id="sim-setup" '+(!r?'open':'')+'><summary>Configure a new exploratory scenario</summary><p class="sim-caption">These are separate orbital scenario inputs attached to saved R'+a.options.revision+'. They do not replace bound project inputs or assess project requirements. Edit them explicitly to represent your orbital case. The reference preset is synthetic.</p>'+
      '<form id="sim-form"><div class="sim-form-grid">'+field('name','Scenario name',spec.name,'text','maxlength="120"')+field('mu_m3_s2','Gravity parameter μ · m³/s²',spec.mu_m3_s2)+field('exclusion_radius_m','Exclusion radius · m',spec.exclusion_radius_m)+field('duration_s','Duration · s',spec.duration_s)+field('steps','Integration steps',spec.steps,'number','min="16" max="4096"')+'</div>'+
      '<fieldset><legend>Initial position · m</legend><div class="sim-vector">'+spec.position_m.map((v,i)=>field('p'+i,['X','Y','Z'][i],v)).join('')+'</div></fieldset><fieldset><legend>Initial velocity · m/s</legend><div class="sim-vector">'+spec.velocity_m_s.map((v,i)=>field('v'+i,['X','Y','Z'][i],v)).join('')+'</div></fieldset>'+field('source','Input source and assumptions',spec.source,'text','maxlength="2000"')+
      '<p class="sim-caption">Frame: body-centered, nonrotating inertial XYZ. Time starts at the supplied state (t = 0); no ephemeris date is assumed. Elliptic trajectories only; the solver checks supported bounds and time resolution before running.</p>'+
      '<div class="sd-action-row"><button class="sd-button sd-primary" type="submit" id="sim-run" '+(hasDraft(a)||a.staleServer?'disabled':'')+'>Calculate & save run</button><button class="sd-button" type="button" id="sim-default">Use reference inputs</button><button class="sd-button" type="button" id="sim-copy" '+(!r?'disabled':'')+'>Copy selected run inputs</button></div><p id="sim-run-status" role="status" class="sim-caption"></p></form></details>':'')+
      '<details class="sim-details" id="sim-provenance"><summary>Numerical diagnostics, sources & coverage</summary>'+provenance(a)+'</details>'+
      '<p class="sim-scope">This model calculates unpowered point-mass orbital motion. Project-bound results assess only explicitly linked supported orbital criteria. Exploratory runs do not change requirement findings. Engines, atmosphere, heating, structural response, vehicle attitude and launch readiness are not established by this simulation.</p></div>';
    const on=(selector,event,fn)=>host.querySelector(selector)?.addEventListener(event,fn,{signal:a.abort.signal});
    host.querySelectorAll('[data-sim-mode]').forEach(button=>button.addEventListener('click',()=>{s.mode=button.dataset.simMode;s.index=0;const model=a.projectModels.find(m=>m.model_id===s.modelId);const rows=modeRuns(a);void selectRun(a,rows.find(r=>r.simulation_id===model?.simulation_id)?.simulation_id||rows.find(r=>r.revision===a.options.revision)?.simulation_id||'');},{signal:a.abort.signal}));
    host.querySelectorAll('[data-sim-model]').forEach(button=>button.addEventListener('click',()=>{s.modelId=button.dataset.simModel;void selectRun(a,a.projectModels.find(m=>m.model_id===s.modelId)?.simulation_id||'');},{signal:a.abort.signal}));
    host.querySelectorAll('[data-sim-inputs]').forEach(button=>button.addEventListener('click',()=>a.options.onInputs?.(button.dataset.simInputs),{signal:a.abort.signal}));
    host.querySelectorAll('[data-sim-requirement],[data-sim-investigate]').forEach(button=>button.addEventListener('click',()=>{const id=button.dataset.simRequirement||button.dataset.simInvestigate;a.options.onRequirement?.(id,r.workspace_run_id,!!button.dataset.simInvestigate);},{signal:a.abort.signal}));
    on('#sim-reference','click',()=>a.options.onReference?.());
    on('#sim-project-run','click',()=>a.options.onRun?.(s.modelId));
    on('#sim-form','submit',event=>{event.preventDefault();void run(a);});
    on('#sim-form','input',()=>{a.session.spec=readForm(a);});
    on('#sim-default','click',()=>{s.spec=clone(a.defaultSpec);render(a);host.querySelector('#sim-setup').open=true;});
    on('#sim-copy','click',()=>{if(a.detail){s.spec=clone(a.detail.receipt.spec);render(a);host.querySelector('#sim-setup').open=true;}});
    on('#sim-run-picker','change',event=>void selectRun(a,event.target.value));
    on('#sim-compare-picker','change',event=>void compare(a,event.target.value));
    on('#sim-export','click',()=>void exportRun(a));
    on('#sim-play','click',()=>{a.playing?stop(a):play(a);});
    on('#sim-rewind','click',()=>{stop(a);setIndex(a,0);});
    on('#sim-timeline','input',event=>{stop(a);setIndex(a,Number(event.target.value));});
    a.host.querySelector('#sim-speed').value=String(a.speed);
    on('#sim-speed','change',event=>{a.speed=Number(event.target.value);});
    on('#sim-quantity','change',()=>drawChart(a));
    host.querySelectorAll('[data-sim-projection]').forEach(button=>button.addEventListener('click',()=>{s.projection=button.dataset.simProjection;host.querySelectorAll('[data-sim-projection]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));drawScene(a);},{signal:a.abort.signal}));
    on('#sim-zoom-in','click',()=>{s.zoom=Math.min(3,s.zoom*1.2);drawScene(a);});
    on('#sim-zoom-out','click',()=>{s.zoom=Math.max(.3,s.zoom/1.2);drawScene(a);});
    on('#sim-reset-camera','click',()=>{s.yaw=-.65;s.pitch=.45;s.zoom=1;drawScene(a);});
    bindCamera(a);
    on('#sim-chart','click',event=>{const rect=event.target.getBoundingClientRect(),f=Math.max(0,Math.min(1,(event.clientX-rect.left-70)/(rect.width-92)));const rows=samples(a);if(!rows.length)return;const duration=rows.at(-1).time_s,tmax=Math.max(duration,a.baseline?.receipt.result.samples.at(-1).time_s||0);stop(a);setIndex(a,Math.round(Math.min(duration,f*tmax)/duration*(rows.length-1)));});
    a.resize = new ResizeObserver(()=>{drawScene(a);drawChart(a);});a.resize.observe(host.querySelector('.sim-stage'));
    a.baseline=null;a.comparison=null;
    setIndex(a,s.index);
  }
  function readForm(a) {
    const data=new FormData(a.host.querySelector('#sim-form'));
    const number=name=>data.get(name)?.trim()===''?null:Number(data.get(name));
    return {schema:'sixd.orbit-scenario.v1',name:String(data.get('name')),source:String(data.get('source')),frame:'body_centered_inertial_3d',mu_m3_s2:number('mu_m3_s2'),exclusion_radius_m:number('exclusion_radius_m'),duration_s:number('duration_s'),steps:number('steps'),position_m:[0,1,2].map(i=>number('p'+i)),velocity_m_s:[0,1,2].map(i=>number('v'+i))};
  }
  function error(a,message) {const el=a.host.querySelector('#sim-error');if(el){el.hidden=!message;el.textContent=message || '';}}
  async function run(a) {
    if(a.running || hasDraft(a) || a.staleServer || a.closed || a.session.mode!=='exploratory')return;
    a.session.spec=readForm(a);a.running=true;stop(a);error(a,'');
    const serial=++a.request;
    a.host.querySelector('#sim-run-status').textContent='Calculating the supplied initial state and saving its receipt…';
    a.host.querySelectorAll('button,input,select').forEach(el=>{el.dataset.simDisabled=String(el.disabled);el.disabled=true;});
    try {
      const detail=await a.options.api('/api/simulations',{project_id:a.options.projectId,revision:a.options.revision,spec:a.session.spec});
      if(a.closed || serial!==a.request)return;
      let listing,historyError='';
      try{listing=await a.options.api('/api/simulations?project_id='+encodeURIComponent(a.options.projectId)+'&revision='+a.options.revision);}
      catch(e){historyError='This run was saved, but refreshing the history list failed. Reopen Simulation to refresh it. '+e.message;}
      if(a.closed || serial!==a.request)return;
      // Commit the selected receipt and all rendered identity labels together,
      // even if the secondary history request fails after a successful save.
      a.detail=detail;a.session.runId=detail.receipt.simulation_id;a.session.index=0;
      a.list=listing?.simulations || [{simulation_id:detail.receipt.simulation_id,revision:detail.receipt.revision,created_at:detail.receipt.created_at,spec:detail.receipt.spec,binding_kind:'standalone'},...a.list];
      if(listing)a.projectModels=listing.project_models||[];
      render(a);if(historyError)error(a,historyError);
      a.host.querySelector('#sim-run-status').textContent='Calculated and saved locally. No project requirement verdict was changed.';
    } catch(e){if(!a.closed){error(a,e.message);a.host.querySelector('#sim-run-status').textContent='New run was not displayed. Any trajectory above remains the earlier saved run.';}}
    finally{a.running=false;if(!a.closed)a.host.querySelectorAll('[data-sim-disabled]').forEach(el=>{el.disabled=el.dataset.simDisabled==='true';delete el.dataset.simDisabled;});}
  }
  async function selectRun(a,id) {
    stop(a);const serial=++a.request;error(a,'');
    a.detail=null;a.baseline=null;a.session.runId=null;a.session.index=0;
    render(a);
    if(!id)return;
    try{const detail=await a.options.api('/api/simulations/'+encodeURIComponent(id)+'?revision='+a.options.revision);if(a.closed||serial!==a.request)return;a.detail=detail;a.session.runId=id;if(projectReceipt(detail.receipt))a.session.modelId=detail.receipt.model_id;render(a);}catch(e){if(!a.closed&&serial===a.request)error(a,e.message);}
  }
  async function compare(a,id) {
    stop(a);const serial=++a.request;a.baseline=null;a.comparison=null;error(a,'');
    const note=a.host.querySelector('#sim-comparison-note');note.hidden=true;
    a.host.querySelector('#sim-baseline-legend').hidden=true;setIndex(a,a.session.index);
    if(!id||!a.detail)return;
    try {
      const [comparison,baseline]=await Promise.all([a.options.api('/api/simulation-comparison?left_id='+encodeURIComponent(a.detail.receipt.simulation_id)+'&right_id='+encodeURIComponent(id)),a.options.api('/api/simulations/'+encodeURIComponent(id)+'?revision='+a.options.revision)]);
      if(a.closed||serial!==a.request)return;
      a.comparison=comparison;note.hidden=false;
      if(!comparison.compatible){note.textContent='Comparison unavailable: '+comparison.reasons.join(' ');return;}
      a.baseline=baseline;
      const changes=comparison.changed_spec_fields || [];
      note.textContent='Comparison R'+baseline.receipt.revision+' · '+baseline.receipt.spec.name+'. Same elapsed-time origin, not a calendar rendezvous. '+(changes.length?'Changed scenario fields: '+changes.join(', ')+'. ':'Scenario inputs are identical. ')+(!baseline.freshness.source_current||!a.detail.freshness.source_current?'Historical calculation sources differ from the current implementation. ':'')+'Each marker uses its own nearest saved sample; its exact time is shown below. '+(projectReceipt(a.detail.receipt)?'Project trajectories use the explicitly bound inputs in each saved review.':'Exploratory inputs are separate from the project’s requirement checks.');
      a.host.querySelector('#sim-baseline-legend').hidden=false;setIndex(a,a.session.index);
    }catch(e){if(!a.closed&&serial===a.request)error(a,e.message);}
  }
  async function exportRun(a) {
    if(!a.detail)return;
    const identity=a.detail.receipt.simulation_id;
    try{const payload=await a.options.api('/api/simulation-export?id='+encodeURIComponent(identity)+'&revision='+a.options.revision);if(a.closed)return;const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download='6d-orbit-'+identity+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){if(!a.closed)error(a,e.message);}
  }
  function stop(a) {a.playing=false;cancelAnimationFrame(a.raf);const button=a.host.querySelector('#sim-play');if(button)button.textContent='Play';}
  function play(a) {
    const rows=samples(a);if(!rows.length)return;
    if(a.session.index>=rows.length-1)setIndex(a,0);
    a.playing=true;a.host.querySelector('#sim-play').textContent='Pause';
    let previous=performance.now(),elapsed=rows[a.session.index].time_s;
    function tick(now){if(a.closed||!a.playing)return;elapsed+=(now-previous)/1000*a.speed;previous=now;const duration=rows.at(-1).time_s;setIndex(a,Math.min(rows.length-1,Math.floor(elapsed/duration*(rows.length-1))));if(elapsed>=duration){stop(a);return;}a.raf=requestAnimationFrame(tick);}
    a.raf=requestAnimationFrame(tick);
  }
  function baselineSample(a,time) {
    const rows=a.baseline?.receipt.result.samples;if(!rows?.length||time<rows[0].time_s||time>rows.at(-1).time_s)return null;
    return rows[Math.max(0,Math.min(rows.length-1,Math.round(time/rows.at(-1).time_s*(rows.length-1))))];
  }
  function setIndex(a,index) {
    if(a.closed)return;
    const rows=samples(a);a.session.index=Math.max(0,Math.min(rows.length-1,Number.isFinite(index)?index:0));
    const row=rows[a.session.index],base=row?baselineSample(a,row.time_s):null;
    a.host.querySelector('#sim-timeline').value=String(a.session.index);
    a.host.querySelector('#sim-time').textContent=row?fmt(row.time_s)+' / '+fmt(rows.at(-1).time_s)+' s':'No samples';
    a.host.querySelector('#sim-metrics').innerHTML=row?[['Elapsed',row.time_s,'s'],['Radius',row.radius_m/1000,'km'],['Speed',row.speed_m_s/1000,'km/s'],['Z coordinate',row.position_m[2]/1000,'km']].map(([label,value,unit])=>'<div><span>'+label+'</span><strong>'+fmt(value)+' <small>'+unit+'</small></strong></div>').join(''):'';
    const quantities=row?[['time_s','Time','s',row.time_s,base?.time_s],...['X','Y','Z'].map((axis,i)=>['position_'+axis,axis+' position','m',row.position_m[i],base?.position_m[i]]),...['X','Y','Z'].map((axis,i)=>['velocity_'+axis,axis+' velocity','m/s',row.velocity_m_s[i],base?.velocity_m_s[i]]),['radius_m','Radius','m',row.radius_m,base?.radius_m],['speed_m_s','Speed','m/s',row.speed_m_s,base?.speed_m_s],['specific_energy_j_kg','Specific orbital energy','J/kg',row.specific_energy_j_kg,base?.specific_energy_j_kg]]:[];
    a.host.querySelector('#sim-sample-values').innerHTML=row?'<p class="sim-caption">Sample '+a.session.index+' of '+(rows.length-1)+' intervals. Values below preserve the stored numbers.'+(a.baseline&&!base?' Comparison has no sample at this elapsed time.':'')+'</p><div class="sd-table-wrap"><table class="sd-table"><thead><tr><th>Quantity</th><th>Selected run</th>'+(a.baseline?'<th>Comparison sample</th>':'')+'<th>Unit</th></tr></thead><tbody>'+quantities.map(([key,label,unit,value,b])=>'<tr><th>'+label+'</th><td data-sim-value="'+key+'">'+exact(value)+'</td>'+(a.baseline?'<td data-sim-baseline="'+key+'">'+exact(b)+'</td>':'')+'<td>'+unit+'</td></tr>').join('')+'</tbody></table></div>':'<p>No recorded sample selected.</p>';
    drawScene(a);drawChart(a);
  }
  function surface(canvas) {
    const rect=canvas.getBoundingClientRect(),width=Math.max(1,rect.width),height=Math.max(1,rect.height),ratio=Math.min(window.devicePixelRatio||1,2);
    if(canvas.width!==Math.round(width*ratio)||canvas.height!==Math.round(height*ratio)){canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);}
    const ctx=canvas.getContext('2d');ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,width,height);return {ctx,width,height};
  }
  // Orthographic projection of all THREE stored coordinates. A camera transform
  // changes only presentation; no transformed coordinates enter saved evidence.
  function transform(p,s) {
    if(s.projection==='xy')return [p[0],p[1],p[2]];
    if(s.projection==='xz')return [p[0],p[2],-p[1]];
    if(s.projection==='yz')return [p[1],p[2],p[0]];
    const cy=Math.cos(s.yaw),sy=Math.sin(s.yaw),cp=Math.cos(s.pitch),sp=Math.sin(s.pitch);
    const x=cy*p[0]-sy*p[1],y=sy*p[0]+cy*p[1];
    return [x,cp*y-sp*p[2],sp*y+cp*p[2]];
  }
  function drawScene(a) {
    const canvas=a.host.querySelector('#sim-scene');if(!canvas)return;
    const {ctx,width:w,height:h}=surface(canvas),rows=samples(a),s=a.session;
    ctx.fillStyle='#f6f8fc';ctx.fillRect(0,0,w,h);
    ctx.fillStyle='#dce3ed';for(let x=16;x<w;x+=24)for(let y=16;y<h;y+=24){ctx.beginPath();ctx.arc(x,y,.65,0,Math.PI*2);ctx.fill();}
    if(!rows.length){ctx.fillStyle='#5d6a7d';ctx.font='14px system-ui';ctx.textAlign='center';ctx.fillText('Your calculated trajectory will appear here',w/2,h/2);return;}
    const other=a.baseline?.receipt.result.samples || [],radius=a.detail.receipt.spec.exclusion_radius_m;
    const extent=Math.max(...rows.map(p=>p.radius_m),...other.map(p=>p.radius_m),radius)*1.18;
    const scale=Math.min(w,h)*.43/extent*s.zoom,cx=w/2,cy=h/2;
    const project=p=>{const t=transform(p,s);return [cx+t[0]*scale,cy-t[1]*scale,t[2]*scale];};
    const line=(points,color,width=1,dash=[])=>{ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);ctx.beginPath();points.forEach((p,i)=>{const v=project(p);i?ctx.lineTo(v[0],v[1]):ctx.moveTo(v[0],v[1]);});ctx.stroke();ctx.setLineDash([]);};
    [['X',[extent,0,0],'#b66d76'],['Y',[0,extent,0],'#56877a'],['Z',[0,0,extent],'#7d72ba']].forEach(([label,p,color])=>{line([p.map(n=>-n),p],color+'66',1,[4,5]);const end=project(p);ctx.fillStyle=color;ctx.font='12px system-ui';ctx.textAlign='center';ctx.fillText(label,end[0]+9,end[1]-7);});
    function path(data,color){line(data.map(p=>p.position_m),color,2);}
    if(other.length)path(other,'#bb8a39');path(rows,'#3768d5');
    // Translucency preserves visibility of the far side; this is an exclusion
    // sphere, not supplied terrain or a claim of physical vehicle geometry.
    const pr=radius*scale;const gradient=ctx.createRadialGradient(cx-pr*.3,cy-pr*.35,0,cx,cy,Math.max(.001,pr));gradient.addColorStop(0,'rgba(224,233,246,.92)');gradient.addColorStop(1,'rgba(162,183,213,.68)');ctx.fillStyle=gradient;ctx.beginPath();ctx.arc(cx,cy,pr,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#8ea7ca';ctx.lineWidth=1;ctx.stroke();
    for(const lat of [-Math.PI/3,-Math.PI/6,0,Math.PI/6,Math.PI/3])line(Array.from({length:97},(_,i)=>{const t=i/96*2*Math.PI;return [radius*Math.cos(lat)*Math.cos(t),radius*Math.cos(lat)*Math.sin(t),radius*Math.sin(lat)];}),'#849dc044',.7);
    for(const lon of [0,Math.PI/3,2*Math.PI/3])line(Array.from({length:97},(_,i)=>{const t=i/96*2*Math.PI;return [radius*Math.cos(t)*Math.cos(lon),radius*Math.cos(t)*Math.sin(lon),radius*Math.sin(t)];}),'#849dc044',.7);
    function front(data,color){let drawing=false;ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=2.4;data.forEach(row=>{const p=project(row.position_m),infront=p[2]>=0 || Math.hypot(p[0]-cx,p[1]-cy)>pr;if(infront){drawing?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]);drawing=true;}else drawing=false;});ctx.stroke();}
    if(other.length)front(other,'#bb8a39');front(rows,'#3768d5');
    function marker(row,color){if(!row)return;const p=project(row.position_m);ctx.beginPath();ctx.arc(p[0],p[1],6,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();ctx.strokeStyle='white';ctx.lineWidth=2;ctx.stroke();}
    const row=rows[s.index];marker(baselineSample(a,row.time_s),'#bb8a39');marker(row,'#2855bf');
    ctx.fillStyle='#5f6b7e';ctx.font='11px system-ui';ctx.textAlign='left';ctx.fillText(s.projection==='3d'?'3D · orthographic view':s.projection.toUpperCase()+' projection',16,h-17);
    const bar=w*.14,metres=bar/scale;ctx.strokeStyle='#73839b';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(w-24-bar,h-30);ctx.lineTo(w-24,h-30);ctx.stroke();ctx.textAlign='right';ctx.fillText(fmt(metres/1000)+' km',w-24,h-12);
    a.host.querySelector('#sim-camera-note').textContent=s.projection==='3d'?'Drag to rotate · arrow keys also rotate':'Fixed '+s.projection.toUpperCase()+' projection · equal spatial scale';
  }
  function drawChart(a) {
    const canvas=a.host.querySelector('#sim-chart');if(!canvas)return;
    const {ctx,width:w,height:h}=surface(canvas),rows=samples(a);if(!rows.length){ctx.fillStyle='#7c8593';ctx.font='12px system-ui';ctx.fillText('No recorded history yet.',20,36);return;}
    const key=a.host.querySelector('#sim-quantity').value,other=a.baseline?.receipt.result.samples || [];
    const channels=key==='position_m'?[0,1,2]:[null],colors=['#3768d5','#4d8b7f','#9470bb'];
    const value=(p,c)=>c===null?p[key]:p.position_m[c];
    let lo=Infinity,hi=-Infinity;for(const p of [...rows,...other])for(const c of channels){lo=Math.min(lo,value(p,c));hi=Math.max(hi,value(p,c));}
    const margin=Math.max((hi-lo)*.08,Math.max(Math.abs(lo),Math.abs(hi),1)*1e-8);lo-=margin;hi+=margin;
    const x0=70,x1=w-22,y0=25,y1=h-32,tmax=Math.max(rows.at(-1).time_s,other.at(-1)?.time_s || 0);
    const px=t=>x0+t/tmax*(x1-x0),py=v=>y1-(v-lo)/(hi-lo)*(y1-y0);
    ctx.font='10px system-ui';ctx.fillStyle='#728093';ctx.textAlign='right';ctx.strokeStyle='#e7ecf3';ctx.lineWidth=1;
    for(let i=0;i<=3;i++){const v=lo+(hi-lo)*i/3,y=py(v);ctx.beginPath();ctx.moveTo(x0,y);ctx.lineTo(x1,y);ctx.stroke();ctx.fillText(Number(v.toPrecision(6)).toLocaleString('en-US',{maximumSignificantDigits:6}),x0-8,y+3);}
    ctx.textAlign='center';for(let i=0;i<=4;i++){const t=tmax*i/4;ctx.fillText(fmt(t),px(t),h-12);}
    channels.forEach((c,j)=>{for(const [data,baseline] of [[other,true],[rows,false]]){if(!data.length)continue;ctx.strokeStyle=baseline?(key==='position_m'?colors[j]:'#bb8a39'):colors[j];ctx.setLineDash(baseline?[5,4]:[]);ctx.lineWidth=baseline?1.3:1.8;ctx.beginPath();data.forEach((p,i)=>{i?ctx.lineTo(px(p.time_s),py(value(p,c))):ctx.moveTo(px(p.time_s),py(value(p,c)));});ctx.stroke();}ctx.setLineDash([]);if(c!==null){ctx.fillStyle=colors[j];ctx.textAlign='left';ctx.fillText(['X','Y','Z'][c],x0+j*26,14);}});
    const row=rows[a.session.index],x=px(row.time_s);ctx.strokeStyle='#303f57';ctx.setLineDash([3,3]);ctx.beginPath();ctx.moveTo(x,y0);ctx.lineTo(x,y1);ctx.stroke();ctx.setLineDash([]);
    channels.forEach((c,j)=>{ctx.fillStyle=colors[j];ctx.beginPath();ctx.arc(x,py(value(row,c)),3,0,Math.PI*2);ctx.fill();});
    canvas.setAttribute('aria-label','Recorded '+key.replaceAll('_',' ')+' versus elapsed seconds. Selected sample time '+exact(row.time_s)+' s. Exact values are in the recorded sample table.');
  }
  function bindCamera(a) {
    const el=a.host.querySelector('#sim-scene');let drag=null;
    const on=(event,fn,options={})=>el.addEventListener(event,fn,{...options,signal:a.abort.signal});
    on('pointerdown',event=>{if(a.session.projection!=='3d')return;drag={x:event.clientX,y:event.clientY};el.setPointerCapture(event.pointerId);});
    on('pointermove',event=>{if(!drag)return;a.session.yaw+=(event.clientX-drag.x)*.008;a.session.pitch=Math.max(-1.5,Math.min(1.5,a.session.pitch+(event.clientY-drag.y)*.008));drag={x:event.clientX,y:event.clientY};drawScene(a);});
    on('pointerup',()=>drag=null);on('pointercancel',()=>drag=null);
    on('wheel',event=>{event.preventDefault();a.session.zoom=Math.max(.3,Math.min(3,a.session.zoom*Math.exp(-event.deltaY*.001)));drawScene(a);},{passive:false});
    on('keydown',event=>{if(a.session.projection!=='3d'||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;event.preventDefault();a.session.yaw+=(event.key==='ArrowRight'?.15:event.key==='ArrowLeft'?-.15:0);a.session.pitch=Math.max(-1.5,Math.min(1.5,a.session.pitch+(event.key==='ArrowDown'?.15:event.key==='ArrowUp'?-.15:0)));drawScene(a);});
  }
  function provenance(a) {
    if(!a.detail)return '<p class="sim-caption">Run a scenario to record its solver settings, sources and diagnostics.</p>';
    const {receipt:r,receipt_digest:d}=a.detail,s=r.result.summary;
    return '<p class="sim-caption">Velocity Verlet · fixed time step '+esc(exact(r.result.method.time_step_s))+' s · '+r.spec.steps+' steps. Diagnostics describe numerical behavior; they do not establish physical model accuracy or mission success.</p><dl class="sim-diagnostics">'+[
      ['Maximum relative energy drift',s.max_relative_energy_error],['Maximum relative angular momentum drift',s.max_relative_angular_momentum_error],['Sampled minimum radius · m',s.min_radius_m],['Sampled maximum radius · m',s.max_radius_m],['Analytic orbital period · s',s.orbital_period_s],['Initial-state eccentricity',s.eccentricity]
    ].map(([label,value])=>'<dt>'+label+'</dt><dd>'+esc(exact(value))+'</dd>').join('')+'</dl><h4>Recorded initial conditions</h4><pre class="sim-json">'+esc(JSON.stringify(r.spec,null,2))+'</pre><h4>Run identity</h4><p class="sim-caption">Project '+esc(r.project_id)+' · saved R'+r.revision+' · '+esc(r.created_at)+'. Local receipt digests detect accidental changes; they are not authenticated signatures.</p><pre class="sim-json">Receipt: '+esc(d)+'\nProject snapshot: '+esc(r.project_snapshot_digest)+'\nSources: '+esc(JSON.stringify(r.sources,null,2))+'</pre><h4>Model coverage</h4><ul class="sd-scope-list">'+r.result.limitations.map(item=>'<li>'+esc(item)+'</li>').join('')+'</ul>';
  }
  window.SixDSimulation={mount,unmount};
})();
