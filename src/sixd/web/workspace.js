/* Connected local workspace. Quantitative findings come only from saved server receipts. */
(() => {
  'use strict';
  const $ = s => document.querySelector(s);
  const root = $('#sixd-workspace');
  window.SixDDisclosureScroll.install(root);
  const state = {data:null, projects:[], templates:[], draft:null, impact:null, system:'overview', selected:null, view:'canvas', page:'review-home', panel:'details', busy:false, importing:null, trajectory:null, camera:{x:15,y:35,scale:1}, request:0};
  let navigation=null, navigationStarting=true;
  let renderedPageContext=null;
  const author = {catalog:null, preflight:null, snapshot:'', serial:0, loading:false, error:'', timer:null, editor:null};
  // Credentials are never assigned to application state or persistent browser storage.
  const ai = {scope:'requirement',status:null, statusError:'', statusLoading:false, evaluation:null, evaluationError:'', evaluationLoading:false, requirementId:null, question:'', records:[], error:'', loading:false, loadedContext:'', starting:false, connecting:false, context:'', generation:0, timer:null, controller:null};
  ai.testSelection=null;
  // Selection belongs to an explicitly chosen chat, never the server default or
  // a preference left by an earlier browser session.
  ai.modelChoice=null;
  state.hosted=true;
  const editedDialogs=new WeakSet();
  let rocket=null;
  const rocketUI={threadHeads:new Map(),modelSelections:new Map(),attachmentController:null,rendered:'',questionDrafts:new Map(),researchDrafts:new Map(),researchKey:'',researchDispose:null,researchBusy:false,openIntent:null,launchContext:'',notice:'',parkedTests:new Map(),handoffSerial:0};
  const reviewGuide={open:false,exportedRun:null};
  try{reviewGuide.open=localStorage.getItem('sixd.review-guide.open')==='yes';}catch{}
  const testLinks={key:'',pending:'',profile:null,error:'',serial:0,controller:null,timer:null};
  const interfaceLinks={key:'',pending:'',profile:null,error:'',serial:0,controller:null,timer:null};
  const sourceLinks={key:'',pending:'',profile:null,error:'',serial:0,controller:null,dispose:null};
  const actionLinks={key:'',pending:'',profile:null,error:'',serial:0,controller:null,dispose:null,originId:null};
  const comparisonView={dispose:null};
  const researchView={dispose:null};
  const coverageLinks={key:'',pending:'',profile:null,error:'',serial:0,controller:null,dispose:null};
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const copy = value => JSON.parse(JSON.stringify(value));
  const same = (a,b) => JSON.stringify(a) === JSON.stringify(b);
  const human = value => String(value ?? '').replace(/_/g,' ').replace(/^./,s=>s.toUpperCase());
  const num = value => window.SixDUnits?.number(value) ?? (typeof value === 'number' && Number.isFinite(value) ? String(value) : '—');
  const measure = item => item && typeof item.value === 'number' ? (window.SixDUnits?.value(item.value,item.unit) ?? num(item.value)+' '+esc(window.SixDUnits?.format(item.unit)??item.unit)) : '—';
  const icon = name => '<i data-lucide="'+name+'" aria-hidden="true"></i>';
  const project = () => state.draft || state.data?.project;
  function testLinkKey(){return state.data?JSON.stringify([state.data.project_id,state.data.revision,currentRun()?.run_id||null,project()]):'';}
  function sourceLinkKey(){return state.data?JSON.stringify([state.data.project_id,state.data.revision,currentRun()?.run_id||null,!!state.draft]):'';}
  function actionLinkKey(){return sourceLinkKey();}
  const seriesLinks={key:'',pending:'',profile:null,error:'',serial:0};
  function seriesSlot(){queueMicrotask(()=>void refreshSeries());return '<section data-series-slot>Loading imported simulation evidence…</section>';}
  function hydrateSeries(){
    const p=seriesLinks.key===testLinkKey()?seriesLinks.profile:null;
    root.querySelectorAll('[data-series-slot]').forEach(el=>{
      el.innerHTML='<h3>Imported simulation evidence</h3>'+(p?'<p>Recorded time histories are supplemental evidence. They do not alter requirement findings.</p>'+((p.imports||[]).map(d=>{const r=d.receipt||d;return '<details class="sd-source"><summary>'+esc(r.spec?.name||r.name||r.import_id)+' · R'+esc(r.revision)+(d.freshness?.historical?' · Historical':'')+'</summary><p>'+esc(r.spec?.source||'')+'</p><p>Frame: '+esc(r.spec?.frame||'')+' · time origin: '+esc(r.spec?.time_origin||'')+'</p><p>Configuration: '+esc(r.spec?.configuration||'')+'</p><pre>'+esc(JSON.stringify(r.comparisons||[],null,2))+'</pre><p class="sd-receipt">Import '+esc(r.import_id)+' · '+esc(d.receipt_digest||'')+'</p></details>';}).join('')||'<p>No imported time histories in this context.</p>')+'<p class="sd-small">History limit '+esc(p.history_limit||20)+(p.history_truncated?' · Additional records omitted; export individual imports.':'')+'</p>':'<p class="sd-notice">'+esc(seriesLinks.error||'Loading imported evidence…')+'</p>')+'<button type="button" class="sd-button" data-action="simulation-imports">Open simulation imports</button>';
    });
    hydrateTestLinks();
  }
  async function refreshSeries(force=false){
    if(!state.data)return;const key=testLinkKey();
    if(!force&&(seriesLinks.key===key||seriesLinks.pending===key)){hydrateSeries();return;}
    const serial=++seriesLinks.serial;seriesLinks.pending=key;seriesLinks.error='';
    try{const p=await api('/api/simulation-import-summary'+query(state.data.project_id,state.data.revision));if(serial!==seriesLinks.serial||key!==testLinkKey())return;seriesLinks.profile=p;seriesLinks.key=key;}
    catch(e){if(serial===seriesLinks.serial&&key===testLinkKey()){seriesLinks.profile=null;seriesLinks.key=key;seriesLinks.error=e.message;}}
    finally{if(serial===seriesLinks.serial){seriesLinks.pending='';hydrateSeries();}}
  }
  const envelopeLinks={key:'',pending:'',profile:null,error:'',serial:0};
  function envelopeSlot(){queueMicrotask(()=>void refreshEnvelopes());return '<section data-envelope-slot>Loading sampled operating studies…</section>';}
  function hydrateEnvelopes(){
    const p=envelopeLinks.key===testLinkKey()?envelopeLinks.profile:null;
    root.querySelectorAll('[data-envelope-slot]').forEach(el=>{
      el.innerHTML='<h3>Sampled operating studies</h3><p>Only the declared combinations were calculated. Worst observed margins do not establish behavior between samples.</p>'+(p?((p.studies||[]).map(d=>{const r=d.receipt||d;return '<details class="sd-source"><summary>'+esc(r.spec?.name||r.name||r.study_id)+' · R'+esc(r.revision)+(d.freshness?.historical?' · Historical':'')+'</summary><p>'+esc(r.spec?.source||'')+'</p><pre>'+esc(JSON.stringify(r.envelope_summary||{},null,2))+'</pre><p class="sd-receipt">Study '+esc(r.study_id)+' · '+esc(d.receipt_digest||'')+'</p></details>';}).join('')||'<p>No sampled operating studies saved in this context.</p>')+'<p class="sd-small">History limit '+esc(p.history_limit||20)+(p.history_truncated?' · Additional studies omitted; export individual records.':'')+'</p>':'<p class="sd-notice">'+esc(envelopeLinks.error||'Loading recorded studies…')+'</p>')+'<button type="button" class="sd-button" data-action="envelopes">Open envelope studies</button>';
    });hydrateTestLinks();
  }
  async function refreshEnvelopes(force=false){
    if(!state.data)return;const key=testLinkKey();
    if(!force&&(envelopeLinks.key===key||envelopeLinks.pending===key)){hydrateEnvelopes();return;}
    const serial=++envelopeLinks.serial;envelopeLinks.pending=key;envelopeLinks.error='';
    try{const p=await api('/api/envelopes/summary'+query(state.data.project_id,state.data.revision));if(serial!==envelopeLinks.serial||key!==testLinkKey())return;envelopeLinks.profile=p;envelopeLinks.key=key;}
    catch(e){if(serial===envelopeLinks.serial&&key===testLinkKey()){envelopeLinks.profile=null;envelopeLinks.key=key;envelopeLinks.error=e.message;}}
    finally{if(serial===envelopeLinks.serial){envelopeLinks.pending='';hydrateEnvelopes();}}
  }
  function coverageSlot(){
    queueMicrotask(()=>void refreshCoverage());
    return '<div data-coverage-slot>Reading engineering coverage…</div>';
  }
  function hydrateCoverage(){
    const profile=coverageLinks.key===sourceLinkKey()?coverageLinks.profile:null;
    root.querySelectorAll('[data-coverage-slot]').forEach(el=>{
      el.innerHTML=(state.draft?'<p class="sd-notice">Coverage below belongs to saved R'+state.data.revision+'. Draft applicability has not been assessed.</p>':'')+(profile?window.SixDCoverage.render(profile):'<p class="sd-notice">'+esc(coverageLinks.error||'Loading coverage for this saved revision…')+'</p>')+'<button type="button" class="sd-mini-action te-no-print" data-action="coverage">Open engineering coverage</button>';
    });
    hydrateTestLinks();
  }
  async function refreshCoverage(force=false){
    if(!state.data)return;const key=sourceLinkKey();
    if(!force&&(coverageLinks.key===key||coverageLinks.pending===key)){hydrateCoverage();return;}
    coverageLinks.controller?.abort();const serial=++coverageLinks.serial;coverageLinks.pending=key;coverageLinks.error='';coverageLinks.controller=new AbortController();
    const id=state.data.project_id,revision=state.data.revision,runId=currentRun()?.run_id||null;
    try{
      const profile=await api('/api/coverage'+query(id,revision),undefined,{signal:coverageLinks.controller.signal});
      if(serial!==coverageLinks.serial||key!==sourceLinkKey())return;
      if(profile.project_id!==id||profile.revision!==revision||profile.run_id!==runId)throw Error('Coverage context changed. Reload the saved project.');
      coverageLinks.profile=profile;coverageLinks.key=key;
    }catch(error){if(error.name!=='AbortError'&&serial===coverageLinks.serial&&key===sourceLinkKey()){coverageLinks.profile=null;coverageLinks.key=key;coverageLinks.error=error.message;}}
    finally{if(serial===coverageLinks.serial){coverageLinks.pending='';hydrateCoverage();}}
  }
  function actionSlot(variant,requirementIds=null,modelIds=null){
    queueMicrotask(()=>void refreshActionLinks());
    return '<div data-action-queue-slot="'+variant+'" data-queue-requirements="'+esc(JSON.stringify(requirementIds))+'" data-queue-models="'+esc(JSON.stringify(modelIds))+'">Reading engineering actions…</div>';
  }
  function hydrateActionLinks(){
    const profile=actionLinks.key===actionLinkKey()?actionLinks.profile:null;
    root.querySelectorAll('[data-action-queue-slot]').forEach(el=>{
      el.innerHTML=profile?window.SixDActions.render(profile,{variant:el.dataset.actionQueueSlot,requirementIds:JSON.parse(el.dataset.queueRequirements),modelIds:JSON.parse(el.dataset.queueModels),hasDraft:!!state.draft}):'<p class="sd-notice">'+esc(actionLinks.error||'Loading actions for this saved revision…')+'</p>';
      el.insertAdjacentHTML('beforeend','<button type="button" class="sd-mini-action te-no-print" data-action="actions">Open engineering actions</button>');
    });
    hydrateTestLinks();
  }
  async function refreshActionLinks(force=false){
    if(!state.data)return;const key=actionLinkKey();
    if(!force&&(actionLinks.key===key||actionLinks.pending===key)){hydrateActionLinks();return;}
    actionLinks.controller?.abort();const serial=++actionLinks.serial;actionLinks.pending=key;actionLinks.error='';actionLinks.controller=new AbortController();
    const id=state.data.project_id,revision=state.data.revision,runId=currentRun()?.run_id||null;
    try{
      const profile=await api('/api/actions'+query(id,revision),undefined,{signal:actionLinks.controller.signal});
      if(serial!==actionLinks.serial||key!==actionLinkKey())return;
      if(profile.project_id!==id||profile.revision!==revision||profile.context!=='saved'||profile.run_id!==runId)throw Error('The engineering action context changed. Reload this saved project.');
      actionLinks.profile=profile;actionLinks.key=key;
    }catch(error){if(error.name!=='AbortError'&&serial===actionLinks.serial&&key===actionLinkKey()){actionLinks.profile=null;actionLinks.key=key;actionLinks.error=error.message;}}
    finally{if(serial===actionLinks.serial){actionLinks.pending='';hydrateActionLinks();}}
  }
  function sourceSlot(variant,requirementIds=null,modelIds=null){
    queueMicrotask(()=>void refreshSourceLinks());
    return '<div data-source-slot="'+variant+'" data-source-requirements="'+esc(JSON.stringify(requirementIds))+'" data-source-models="'+esc(JSON.stringify(modelIds))+'">Reading project references…</div>';
  }
  function hydrateSourceLinks(){
    const profile=sourceLinks.key===sourceLinkKey()?sourceLinks.profile:null;
    root.querySelectorAll('[data-source-slot]').forEach(el=>{
      el.innerHTML=profile?window.SixDSources.render(profile,{variant:el.dataset.sourceSlot,requirementIds:JSON.parse(el.dataset.sourceRequirements),modelIds:JSON.parse(el.dataset.sourceModels),hasDraft:!!state.draft}):'<p class="sd-notice">'+esc(sourceLinks.error||'Loading references for this saved revision…')+'</p>';
      el.insertAdjacentHTML('beforeend','<button type="button" class="sd-mini-action te-no-print" data-action="sources">Open source library</button>');
    });
    hydrateTestLinks();
  }
  async function refreshSourceLinks(force=false){
    if(!state.data)return;const key=sourceLinkKey();
    if(!force&&(sourceLinks.key===key||sourceLinks.pending===key)){hydrateSourceLinks();return;}
    sourceLinks.controller?.abort();const serial=++sourceLinks.serial;sourceLinks.pending=key;sourceLinks.error='';sourceLinks.controller=new AbortController();
    const id=state.data.project_id,revision=state.data.revision,runId=currentRun()?.run_id||null;
    try{
      const profile=await api('/api/sources'+query(id,revision),undefined,{signal:sourceLinks.controller.signal});
      if(serial!==sourceLinks.serial||key!==sourceLinkKey())return;
      if(profile.project_id!==id||profile.revision!==revision||profile.context!=='saved'||profile.run_id!==runId)throw Error('The source-library context changed. Reload the saved project.');
      sourceLinks.profile=profile;sourceLinks.key=key;
    }catch(error){if(error.name!=='AbortError'&&serial===sourceLinks.serial&&key===sourceLinkKey()){sourceLinks.profile=null;sourceLinks.key=key;sourceLinks.error=error.message;}}
    finally{if(serial===sourceLinks.serial){sourceLinks.pending='';hydrateSourceLinks();renderAssistantContextSummary();renderAiHistory();}}
  }
  function interfaceSlot(variant,modelIds=null){
    queueMicrotask(()=>void refreshInterfaceLinks());
    return '<div data-interface-slot="'+variant+'" data-interface-models="'+esc(JSON.stringify(modelIds))+'">Reading system interfaces…</div>';
  }
  function hydrateInterfaces(){
    const profile=interfaceLinks.key===testLinkKey()?interfaceLinks.profile:null;
    root.querySelectorAll('[data-interface-slot]').forEach(el=>{
      if(!profile){el.innerHTML='<p class="sd-notice">'+esc(interfaceLinks.error||'Loading interface checks for this configuration…')+'</p><button type="button" class="sd-mini-action te-no-print" data-action="refresh-interfaces">Refresh interface evidence</button>';return;}
      let scoped=profile;const ids=JSON.parse(el.dataset.interfaceModels||'null');
      if(Array.isArray(ids)){
        const inputs=new Set(ids.flatMap(id=>Object.values(model(id)?.inputs||{})));
        allReqs().filter(r=>ids.includes(r.model_id)).forEach(r=>inputs.add(r.limit_input));
        const owners=new Set((project().systems||[]).filter(s=>s.model_ids.some(id=>ids.includes(id))).map(s=>s.id));
        scoped={...profile,checks:{...profile.checks,rows:profile.checks.rows.filter(r=>ids.includes(r.source?.model_id)||r.dependency_input_ids.some(id=>inputs.has(id))||owners.has(r.from_system)||owners.has(r.to_system))}};
      }
      const scope=Array.isArray(ids)?{scopeTotal:profile.checks.rows.length,scopeLabel:'Selected model and requirement dependencies'}:{};
      el.innerHTML=el.dataset.interfaceSlot==='changes'?window.SixDSystems.impact(profile)+window.SixDSystems.report(scoped,scope):window.SixDSystems.report(scoped,scope);
      if(Array.isArray(ids)&&ids.some(id=>profile.impact.interface_review_model_ids.includes(id)))el.insertAdjacentHTML('afterbegin','<p class="sd-notice">Declared interfaces flag these connected model and requirement records for review. Their standalone calculation findings remain separate; no downstream model input was automatically changed.</p>');
    });
    const reviewModels=new Set(profile?.impact?.interface_review_model_ids||[]),reviewRequirements=new Set(profile?.impact?.interface_review_requirement_ids||[]);
    root.querySelectorAll('.sd-node').forEach(node=>{const button=node.querySelector('[data-kind]');const marked=button&&(button.dataset.kind==='model'?reviewModels.has(button.dataset.id):button.dataset.kind==='requirement'&&reviewRequirements.has(button.dataset.id));node.classList.toggle('sd-interface-review',!!marked);node.querySelector('.sd-interface-review-note')?.remove();if(marked)button.insertAdjacentHTML('beforeend','<span class="sd-interface-review-note">Interface dependency · review</span>');});
    root.querySelectorAll('[data-status-for]').forEach(cell=>{cell.querySelector('.sd-interface-review-note')?.remove();if(reviewRequirements.has(cell.dataset.statusFor))cell.insertAdjacentHTML('beforeend','<small class="sd-interface-review-note">Interface dependency · review</small>');});
    hydrateTestLinks();
  }
  async function refreshInterfaceLinks(force=false){
    if(!state.data)return;const key=testLinkKey();
    if(!force&&(interfaceLinks.key===key||interfaceLinks.pending===key)){hydrateInterfaces();return;}
    interfaceLinks.controller?.abort();const serial=++interfaceLinks.serial;interfaceLinks.pending=key;interfaceLinks.error='';interfaceLinks.controller=new AbortController();
    const id=state.data.project_id,revision=state.data.revision,draft=state.draft?copy(state.draft):null,runId=currentRun()?.run_id||null;
    try{
      const p=await api(draft?'/api/interfaces/preview':'/api/interfaces'+query(id,revision),draft?{project_id:id,base_revision:revision,project:draft}:undefined,{signal:interfaceLinks.controller.signal});
      if(serial!==interfaceLinks.serial||key!==testLinkKey())return;
      if(p.project_id!==id||p.revision!==revision||p.context!==(draft?'draft':'saved')||p.run_id!==runId)throw Error('Interface context changed. Reload this saved project.');
      interfaceLinks.profile=p;interfaceLinks.key=key;
    }catch(error){if(error.name!=='AbortError'&&serial===interfaceLinks.serial&&key===testLinkKey()){interfaceLinks.profile=null;interfaceLinks.key=key;interfaceLinks.error=error.message;}}
    finally{if(serial===interfaceLinks.serial){interfaceLinks.pending='';hydrateInterfaces();}}
  }
  function testEvidenceSlot(variant,ids){
    queueMicrotask(()=>void refreshTestLinks());
    return '<div class="sd-linked-tests" data-test-evidence-slot="'+variant+'" data-test-evidence-requirements="'+esc(JSON.stringify(ids??null))+'">Reading linked test evidence…</div>';
  }
  function invalidateTestLinks(){testLinks.serial++;testLinks.controller?.abort();testLinks.pending='';testLinks.key='';testLinks.profile=null;testLinks.error='';clearTimeout(testLinks.timer);queueMicrotask(()=>void refreshTestLinks());}
  function hydrateTestLinks(){
    const current=testLinks.key===testLinkKey()&&testLinks.profile;
    root.querySelectorAll('[data-test-evidence-slot]').forEach(el=>{
      const ids=JSON.parse(el.dataset.testEvidenceRequirements||'[]');
      let profile=current;
      if(profile&&el.dataset.testEvidenceSlot==='assistant'&&ai.testSelection){profile={...profile,comparisons:profile.comparisons.filter(c=>c.comparison_id===ai.testSelection.comparisonId).map(c=>({...c,rows:c.rows.filter(r=>r.row_number===ai.testSelection.rowNumber)}))};}
      el.innerHTML=profile?window.SixDTestEvidence.render(profile,{requirementIds:ids,variant:el.dataset.testEvidenceSlot,hasDraft:!!state.draft,currentRunFresh:!!currentRun()&&!currentRun().stale}):testLinks.error?window.SixDTestEvidence.unavailable(testLinks.error):window.SixDTestEvidence.loading();
      el.insertAdjacentHTML('beforeend','<button type="button" class="sd-mini-action te-no-print" data-action="refresh-test-evidence">Refresh linked evidence</button>');
      const interfaceProfile=interfaceLinks.key===testLinkKey()?interfaceLinks.profile:null;
      const reviewIds=interfaceProfile?.impact?.interface_review_requirement_ids||[];
      if(reviewIds.length&&(!Array.isArray(ids)||ids.some(id=>reviewIds.includes(id))))el.insertAdjacentHTML('afterbegin','<p class="sd-notice">Declared interfaces flag connected requirement evidence for review. The scalar test-applicability labels below still describe their original model and criterion dependencies; they do not resolve this separate interface review.</p>');
    });
    const interfacesReady=interfaceLinks.key===testLinkKey()&&interfaceLinks.profile;
    const sourcesReady=sourceLinks.key===sourceLinkKey()&&sourceLinks.profile;
    const actionsReady=actionLinks.key===actionLinkKey()&&actionLinks.profile;
    root.querySelectorAll('[data-action="export-review"],[data-action="print-report"]').forEach(el=>el.disabled=!current||!interfacesReady||!sourcesReady||!actionsReady||envelopeLinks.key!==testLinkKey()||!envelopeLinks.profile||seriesLinks.key!==testLinkKey()||!seriesLinks.profile||coverageLinks.key!==sourceLinkKey()||!coverageLinks.profile||!!state.draft||!currentRun());
  }
  async function refreshTestLinks(force=false){
    if(!state.data)return;const key=testLinkKey();
    if(!force&&(testLinks.key===key||testLinks.pending===key)){hydrateTestLinks();return;}
    testLinks.controller?.abort();const serial=++testLinks.serial;testLinks.pending=key;testLinks.error='';testLinks.controller=new AbortController();hydrateTestLinks();
    const projectId=state.data.project_id,revision=state.data.revision,draft=state.draft?copy(state.draft):null,runId=currentRun()?.run_id||null;
    try{
      const profile=await api(draft?'/api/test-evidence/impact':'/api/test-evidence'+query(projectId,revision),draft?{project_id:projectId,base_revision:revision,project:draft}:undefined,{signal:testLinks.controller.signal});
      if(serial!==testLinks.serial||key!==testLinkKey())return;
      if(profile.project_id!==projectId||profile.revision!==revision||profile.current_run_id!==runId||profile.context!==(draft?'draft':'saved'))throw Error('The linked evidence context changed. Reload the saved project before relying on this view.');
      testLinks.profile=profile;testLinks.key=key;
    }catch(error){if(error.name!=='AbortError'&&serial===testLinks.serial&&key===testLinkKey()){testLinks.profile=null;testLinks.key=key;testLinks.error=error.message;}}
    finally{if(serial===testLinks.serial){testLinks.pending='';hydrateTestLinks();}}
  }
  const systems = () => graph().systems;
  function graph() {
    if(!state.draft)return state.data?.graph || {systems:[],links:[]};
    const groups=new Map(),links=[];
    for(const m of allModels()){
      const id='system:'+m.type;
      if(!groups.has(id))groups.set(id,{id,title:state.data.graph?.systems.find(s=>s.id===id)?.title || (m.type==='power_energy_budget'?'Electrical power':null) || author.catalog?.models.find(c=>c.type===m.type)?.title || human(m.type),model_ids:[],requirement_ids:[]});
      const group=groups.get(id);group.model_ids.push(m.id);
      for(const inputId of new Set(Object.values(m.inputs)))links.push({source:'input:'+inputId,target:'model:'+m.id,type:'input'});
      for(const [role,l]of Object.entries(m.links||{}))links.push({source:'model:'+l.model_id,target:'model:'+m.id,type:'calculation',parameter:role,metric:l.metric,unit:l.unit});
      for(const r of allReqs().filter(r=>r.model_id===m.id)){group.requirement_ids.push(r.id);links.push({source:'model:'+m.id,target:'requirement:'+r.id,type:'evidence'},{source:'input:'+r.limit_input,target:'requirement:'+r.id,type:'limit'});}
    }
    const declared=project().systems||[],owned=new Set(declared.flatMap(s=>s.model_ids)),explicit=declared.map(s=>{
      const descendants=new Set([s.id]);let previous;
      do{previous=descendants.size;declared.filter(child=>descendants.has(child.parent_id)).forEach(child=>descendants.add(child.id));}while(previous!==descendants.size);
      const modelIds=declared.filter(child=>descendants.has(child.id)).flatMap(child=>child.model_ids);
      return {id:'subsystem:'+s.id,title:s.title,description:s.description,parent_id:s.parent_id?'subsystem:'+s.parent_id:null,model_ids:modelIds,own_model_ids:s.model_ids,requirement_ids:allReqs().filter(r=>modelIds.includes(r.model_id)).map(r=>r.id),declared:true};
    });
    const unassigned=[...groups.values()].map(s=>({...s,model_ids:s.model_ids.filter(id=>!owned.has(id)),requirement_ids:s.requirement_ids.filter(id=>!owned.has(req(id)?.model_id))})).filter(s=>s.model_ids.length);
    return {systems:[...explicit,...unassigned],links,system_links:(project().interfaces||[]).map(i=>({source:'subsystem:'+i.from_system,target:'subsystem:'+i.to_system,type:'interface',interface_id:i.id,title:i.title}))};
  }
  const activeSystem = () => systems().find(s=>s.id===state.system);
  const owningSystem = id => systems().find(s=>s.own_model_ids?.includes(id))||systems().find(s=>s.model_ids.includes(id));
  const allModels = () => project()?.models || [];
  const allReqs = () => project()?.requirements || [];
  const selectedModels = () => state.system === 'overview' ? allModels() : allModels().filter(m=>activeSystem()?.model_ids.includes(m.id));
  const selectedReqs = () => state.system === 'overview' ? allReqs() : allReqs().filter(r=>activeSystem()?.model_ids.includes(r.model_id));
  const selectedInputs = () => {
    if (state.system === 'overview') return Object.keys(project()?.inputs || {});
    const ids = new Set(selectedModels().flatMap(m=>Object.values(m.inputs)));
    selectedReqs().forEach(r=>ids.add(r.limit_input));
    return [...ids];
  };
  const model = id => allModels().find(m=>m.id===id);
  const req = id => allReqs().find(r=>r.id===id);
  const currentRun = () => state.data?.run || null;
  const priorRun = () => state.data?.prior_run || null;
  const finding = id => state.draft ? null : currentRun()?.review?.findings?.[id] || null;
  const priorFinding = id => priorRun()?.review?.findings?.[id] || null;
  const result = id => state.draft ? null : currentRun()?.model_results?.[id] || null;
  const dirty = () => !!state.draft && !same(state.draft,state.data.project);
  const latest = () => state.data?.revision === (state.data?.latest_revision || Math.max(...state.data.revisions.map(r=>r.revision)));
  function message(text) { $('#sd-message').textContent=text; $('#sd-message').hidden=!text; }
  function showError(error) { $('#sd-error').textContent=typeof error==='string'?error:error.message || 'The request could not be completed.'; $('#sd-error').hidden=false; }
  function clearError() { $('#sd-error').hidden=true; $('#sd-error').textContent=''; }
  function icons() { if (window.lucide) window.lucide.createIcons(); }
  async function api(url, body, options={}) {
    const response = await fetch(url,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),cache:'no-store',signal:options.signal});
    let payload,raw;
    try { if(options.raw){raw=await response.text();payload=JSON.parse(raw);}else payload=await response.json(); } catch { throw new Error('The local server returned an unreadable response. Reload the application.'); }
    if (!response.ok) throw new Error(payload.error?.message || payload.error || payload.message || 'The request failed ('+response.status+').');
    return options.raw?{payload,raw}:payload;
  }
  function setBusy(busy) {
    state.busy=busy; root.setAttribute('aria-busy',String(busy));
    root.querySelectorAll('button,input,select,textarea').forEach(el=>{ if(busy){el.dataset.wasDisabled=String(el.disabled);el.disabled=true;}else if(el.dataset.wasDisabled!==undefined){el.disabled=el.dataset.wasDisabled==='true';delete el.dataset.wasDisabled;} });
  }
  async function perform(work,success) {
    if(state.busy)return;
    clearError();setBusy(true);
    try { await work(); if(success)message(success); }
    catch(error){showError(error);}
    finally {setBusy(false); if(state.data)render();}
  }
  async function refreshProjects() {
    const payload=await api('/api/projects'); state.projects=payload.projects || [];
  }
  function query(projectId,revision) { return '?project_id='+encodeURIComponent(projectId)+(revision!==undefined?'&revision='+encodeURIComponent(revision):''); }
  async function load(projectId,revision) {
    stopInvestigationPolling();
    const serial=++state.request;
    const data=await api('/api/workspace'+(projectId?query(projectId,revision):''));
    if(serial!==state.request)return;
    state.data=data;state.draft=null;state.impact=null;state.trajectory=null;state.testEvidenceTarget=null;invalidatePreflight();
    if(!systems().some(s=>s.id===state.system))state.system='overview';
    if(!state.selected || !validSelection(state.selected))state.selected=defaultSelection();
    await refreshProjects();if(serial!==state.request)return;
    try{localStorage.setItem('sixd.workspace.last-project',data.project_id);}catch{}
    resetCamera();render();
    if(state.panel==='assistant')void openAssistant(state.selected?.kind==='requirement'?state.selected.id:null);
  }
  function validSelection(selected) {return selected.kind==='input'?Object.hasOwn(project().inputs,selected.id):selected.kind==='requirement'?!!req(selected.id):selected.kind==='model'?!!model(selected.id):false;}
  function defaultSelection() { const r=selectedReqs()[0],m=selectedModels()[0],id=selectedInputs()[0];return r?{kind:'requirement',id:r.id}:m?{kind:'model',id:m.id}:id?{kind:'input',id}:null; }
  function editErrors() {
    const errors=[];
    if(!project().name.trim())errors.push('Provide a project name.');
    if(!project().description.trim())errors.push('Describe the project purpose and assumptions.');
    for(const [id,input] of Object.entries(project().inputs)){
      if(typeof input.value!=='number'||!Number.isFinite(input.value))errors.push(human(id)+' requires a finite number.');
      if(!input.unit.trim())errors.push(human(id)+' requires an explicit unit.');
      if(!input.source.trim())errors.push(human(id)+' requires a source.');
    }
    return errors;
  }
  function localImpact() {
    if(!state.draft)return state.data.impact || {changed_inputs:[],affected_model_ids:[],affected_requirement_ids:[]};
    const before=state.data.run?.review?.project || state.data.prior_run?.review?.project || state.data.project;
    const after=project();const changed=[...new Set([...Object.keys(after.inputs),...Object.keys(before.inputs)])].filter(id=>!same(after.inputs[id],before.inputs[id]));
    const changedModels=after.models.filter(m=>!same(m,before.models.find(old=>old.id===m.id))).map(m=>m.id);
    const changedReqs=after.requirements.filter(r=>!same(r,before.requirements.find(old=>old.id===r.id))).map(r=>r.id);
    const modelIds=after.models.filter(m=>changedModels.includes(m.id)||Object.values(m.inputs).some(id=>changed.includes(id))).map(m=>m.id);
    for(let i=0;i<after.models.length;i++){
      const newlyAffected=after.models.filter(m=>!modelIds.includes(m.id)&&Object.values(m.links||{}).some(link=>modelIds.includes(link.model_id)));
      if(!newlyAffected.length)break;
      modelIds.push(...newlyAffected.map(m=>m.id));
    }
    const reqIds=after.requirements.filter(r=>modelIds.includes(r.model_id)||changed.includes(r.limit_input)||changedReqs.includes(r.id)).map(r=>r.id);
    return {changed_inputs:changed,changed_models:changedModels,changed_requirements:changedReqs,added_models:after.models.filter(m=>!before.models.some(old=>old.id===m.id)).map(m=>m.id),removed_models:before.models.filter(m=>!after.models.some(item=>item.id===m.id)).map(m=>m.id),added_requirements:after.requirements.filter(r=>!before.requirements.some(old=>old.id===r.id)).map(r=>r.id),removed_requirements:before.requirements.filter(r=>!after.requirements.some(item=>item.id===r.id)).map(r=>r.id),affected_model_ids:modelIds,affected_requirement_ids:reqIds};
  }
  const impact = () => {
    if(state.impact)return state.impact;
    if(!state.draft&&currentRun()&&state.data.comparison){
      const comparison=state.data.comparison;
      return {...comparison,affected_model_ids:[...new Set([...(comparison.changed_models||[]),...(comparison.changed_evidence||[])])],affected_requirement_ids:[...(comparison.previous_evidence_needs_rechecking||[]),...(comparison.added_requirements||[])]};
    }
    return localImpact();
  };
  function reqStatus(id) {
    if(state.draft)return 'draft';
    if(!currentRun())return priorRun()?'stale':'pending';
    return findingStatus(finding(id));
  }
  function findingStatus(f) {return ['insufficient_accuracy','accuracy_not_assessed'].includes(f?.assessment_status)?f.assessment_status:f?.status || 'not_assessed';}
  function chip(status) {
    const labels={met:'Met',not_met:'Not met',not_assessed:'Not assessed',insufficient_accuracy:'Insufficient accuracy',accuracy_not_assessed:'Accuracy not assessed',supported:'Grid agreement supported',stale:'Needs recheck',pending:'Not run',draft:'Draft · needs recheck',completed:'Calculated',invalid_inputs:'Invalid inputs'};
    const cls=status==='met'||status==='completed'?'sd-met':status==='not_met'||status==='invalid_inputs'?'sd-fail':['stale','draft','pending','insufficient_accuracy','accuracy_not_assessed'].includes(status)?'sd-pending':'';
    const meanings={met:'The saved calculation meets the declared condition within its model scope.',not_met:'The saved calculation misses the declared condition. Inspect its value, limit and assumptions.',not_assessed:'There is not enough applicable evidence to decide; this is not automatically a failed design.',pending:'Run checks for this saved revision before drawing a conclusion.'};
    return '<span class="sd-chip '+cls+'"'+(meanings[status]?' title="'+esc(meanings[status])+'"':'')+'>'+esc(labels[status]||human(status))+'</span>';
  }
  function modelStatus(r) {return r?.status==='completed'&&r.numerical_accuracy&&r.numerical_accuracy.status!=='supported'?(r.numerical_accuracy.status==='insufficient_accuracy'?'insufficient_accuracy':'accuracy_not_assessed'):r?.status||'pending';}
  function historicalAccuracyNotice(modelId,run=currentRun()) {
    if(state.draft&&run===currentRun())return '';
    const r=run?.model_results?.[modelId];
    if(!r?.simulation||r.numerical_accuracy)return '';
    return '<p class="sd-accuracy-warning">Historical accuracy not assessed. The original criterion result is retained as recorded; it does not establish numerical accuracy.</p>';
  }
  function historicalAccuracyBadge(modelId) {return historicalAccuracyNotice(modelId)?'<span class="sd-history-accuracy">Historical · accuracy not assessed</span>':'';}
  function selectionButton(kind,id,title,cls='sd-row-title') { return '<button type="button" class="'+cls+'" data-kind="'+kind+'" data-id="'+esc(id)+'">'+esc(title)+'</button>'; }
  function inputField(id,field,table=false) {
    const input=project().inputs[id];if(!input)return '<span class="sd-muted">No input mapped</span>';
    if(field==='unit'&&!state.draft)return '<span class="sd-display-unit" data-unit-raw="'+esc(input.unit)+'">'+esc(window.SixDUnits?.format(input.unit)??input.unit)+'</span>';
    return '<input class="'+(table?'sd-table-input ':'sd-input ')+(field==='source'?'sd-input-source':field==='unit'?'sd-input-unit':'')+'" '+(field==='value'?'type="number" step="any"':'type="text"')+' data-input="'+esc(id)+'" data-field="'+field+'" value="'+esc(input[field])+'" aria-label="'+esc(human(id)+' '+field)+'" '+(!state.draft?'disabled':'')+'>';
  }
  const setupKey = () => state.data ? JSON.stringify([state.data.project_id,state.data.revision,project()]) : '';
  const hasSetup = () => allModels().length>0 && allReqs().length>0;
  const catalogModel = type => author.catalog?.models.find(m=>m.type===type);
  const option = (value,label,selected,disabled=false) => '<option value="'+esc(value)+'" '+(value===selected?'selected ':'')+(disabled?'disabled':'')+'>'+esc(label)+'</option>';
  function invalidatePreflight() {author.preflight=null;author.snapshot='';author.error='';author.serial++;author.loading=false;clearTimeout(author.timer);}
  async function loadCatalog() {
    if(author.catalog)return;
    author.catalog=await api('/api/model-catalog');
  }
  async function refreshPreflight() {
    if(!state.data)return;
    const key=setupKey(),serial=++author.serial,payload=copy(project());author.loading=true;author.error='';updatePreflight();
    try{const response=await api('/api/authoring/preflight',{project:payload});if(serial!==author.serial||key!==setupKey())return;author.preflight=response;author.snapshot=key;}
    catch(error){if(serial!==author.serial||key!==setupKey())return;author.error=error.message;}
    finally{if(serial===author.serial){author.loading=false;updatePreflight();}}
  }
  function preflightMarkup() {
    const current=author.snapshot===setupKey()?author.preflight:null;
    return '<div class="sd-section-heading"><h3>Setup validation</h3><button type="button" class="sd-button" data-action="validate-setup" '+(author.loading?'disabled':'')+'>Validate setup</button></div><p class="sd-small sd-muted">Checks mappings, required units and supported metrics without calculating. Input and numerical-domain guards are checked when you run. Physical model applicability still requires external engineering evidence.</p>'+(author.loading?'<p role="status">Checking setup…</p>':author.error?'<p class="sd-error" role="alert">'+esc(author.error)+'</p>':!current?'<p class="sd-notice">Validate this configuration before running its checks.</p>':'<p class="sd-notice">'+(current.can_run?'Mappings are ready for a calculation. No engineering verdict has been produced by validation.':'Complete the setup issues below before running from this page.')+'</p><ul class="sd-setup-issues">'+current.issues.map(issue=>'<li class="sd-setup-'+esc(issue.severity)+'"><strong>'+esc(human(issue.severity))+'</strong> '+esc(issue.message)+'<small>'+esc(issue.path)+'</small></li>').join('')+'</ul>')+'<button type="button" class="sd-button sd-primary" data-action="author-run" '+(state.draft||!current?.can_run||author.loading?'disabled':'')+'>Run supported checks</button>'+(state.draft?'<p class="sd-small sd-muted">Save this draft before running calculations.</p>':'');
  }
  function updatePreflight() {const el=$('#sd-setup-validation');if(el){el.innerHTML=preflightMarkup();icons();$('#sd-run-trigger').disabled=!!state.draft||state.busy||author.loading||author.snapshot!==setupKey()||!author.preflight?.can_run;}}
  function repairContext() {
    if(!systems().some(s=>s.id===state.system))state.system='overview';
    if(!state.selected||!validSelection(state.selected))state.selected=defaultSelection();
    if(ai.requirementId&&!req(ai.requirementId)){stopInvestigationPolling();ai.requirementId=null;ai.loadedContext='';state.panel='details';}
    if(state.trajectory&&!model(state.trajectory.modelId))state.trajectory=null;
  }
  function draftChanged(full=true) {
    state.impact=null;invalidatePreflight();repairContext();
    if(full)render();else{renderDraft();$('#sd-save-state').textContent='Unsaved draft · saved revision preserved';updatePreflight();}
    author.timer=setTimeout(()=>void refreshPreflight(),250);
    clearTimeout(testLinks.timer);testLinks.timer=setTimeout(()=>void refreshTestLinks(),300);hydrateTestLinks();
    clearTimeout(interfaceLinks.timer);interfaceLinks.timer=setTimeout(()=>void refreshInterfaceLinks(),300);
  }
  function thrustInputs(){
    if(!state.data)return [];
    const p=project(),savedBefore=priorRun()?.review?.project||state.data.configuration_base?.project;
    const ids=[...new Set((p.models||[]).map(item=>item.inputs?.thrust).filter(id=>typeof id==='string'&&Object.hasOwn(p.inputs,id)))];
    return ids.map(id=>{const input=p.inputs[id],previous=savedBefore?.inputs?.[id];return {id,label:human(id),value:input.value,unit:input.unit,source:input.source,previous:previous&&typeof previous.value==='number'?{value:previous.value,unit:previous.unit,revision:priorRun()?.revision||state.data.configuration_base?.revision}:null};});
  }
  function thrustEditKey(){return JSON.stringify([state.data?.project_id,state.data?.revision,state.data?.latest_revision,currentRun()?.run_id||null,state.draft]);}
  function thrustError(text){const node=$('#sd-thrust-error');node.textContent=text;node.hidden=!text;}
  function fillThrustEditor(id){
    const item=state.thrustEdit?.inputs.find(input=>input.id===id);if(!item)return;
    $('#sd-thrust-value').value=String(item.value);$('#sd-thrust-source').value=item.source||'';
    $('#sd-thrust-unit').textContent='Saved unit: '+item.unit+' · input '+item.id;
    thrustError(item.unit==='N'?'':'This input does not use newtons. Correct its unit in Design & requirements; no implicit conversion is applied.');
  }
  function openThrustEditor(){
    if(!latest()){message('Historical values are preserved. Select the latest revision to edit thrust.');return;}
    if(state.stagedProfileEdit){message('Apply or cancel the open staged profile before editing another input.');return;}
    const inputs=thrustInputs();if(!inputs.length){message('No supported constant-thrust input is bound in this design. Open Design & requirements to configure it.');return;}
    state.thrustEdit={key:thrustEditKey(),inputs};
    $('#sd-thrust-input').innerHTML=inputs.map(item=>'<option value="'+esc(item.id)+'">'+esc(item.label)+'</option>').join('');
    $('#sd-thrust-input-group').hidden=inputs.length===1;
    $('#sd-thrust-context').textContent=project().name+' · '+(state.draft?'Existing unsaved draft based on ':'Saved ')+'R'+state.data.revision;
    fillThrustEditor(inputs[0].id);$('#sd-thrust-dialog').showModal();$('#sd-thrust-value').focus();
  }
  async function stageThrust(event){
    event.preventDefault();if(state.busy)return;
    const capture=state.thrustEdit,id=$('#sd-thrust-input').value,item=capture?.inputs.find(input=>input.id===id),text=$('#sd-thrust-value').value.trim(),value=Number(text),source=$('#sd-thrust-source').value.trim();
    if(!capture||capture.key!==thrustEditKey()||!latest()){thrustError('The saved design changed. Close and reopen this editor before staging.');return;}
    if(!item||item.unit!=='N'){thrustError('Choose a bound thrust input in newtons.');return;}
    if(!text||!Number.isFinite(value)||value<=0){thrustError('Enter a finite thrust greater than zero, in newtons.');return;}
    if(!source||source.length>2000){thrustError('Provide a source or rationale of at most 2,000 characters.');return;}
    const candidate=copy(project());candidate.inputs[id]={...candidate.inputs[id],value,source};
    const projectId=state.data.project_id,revision=state.data.revision;
    thrustError('');
    await perform(async()=>{
      try{
        const preview=await api('/api/impact',{project_id:projectId,base_revision:revision,project:candidate});
        if(state.thrustEdit!==capture||capture.key!==thrustEditKey()||!$('#sd-thrust-dialog').open)return;
        state.draft=candidate;state.impact=preview.impact;invalidatePreflight();state.page='changes';state.panel='details';state.selected={kind:'input',id};
        $('#sd-thrust-dialog').close();state.thrustEdit=null;stopInvestigationPolling();
        message('Thrust change staged. Review its effects, save a revision, then recalculate. No result has changed yet.');
      }catch(error){if(state.thrustEdit===capture)thrustError(error.message||'The thrust change could not be staged. Your saved design is unchanged.');}
    });
  }
  function beginDraft() {if(state.draft)return true;if(!latest()){message('Select the latest revision before creating a draft.');return false;}state.draft=copy(state.data.project);state.impact=null;invalidatePreflight();return true;}
  function inputConsumers(id) {return [...allModels().filter(m=>Object.values(m.inputs).includes(id)).map(m=>'Model '+m.id),...allReqs().filter(r=>r.limit_input===id).map(r=>'Requirement '+r.id),...(project().interfaces||[]).filter(i=>i.target_input===id||i.source.input_id===id).map(i=>'Interface '+i.id)];}
  function deletionReason(kind,id) {const users=kind==='input'?inputConsumers(id):kind==='model'?[...allModels().filter(m=>Object.values(m.links||{}).some(l=>l.model_id===id)).map(m=>'Calculation '+m.id),...allReqs().filter(r=>r.model_id===id).map(r=>'Requirement '+r.id),...(project().systems||[]).filter(s=>s.model_ids.includes(id)).map(s=>'System '+s.id),...(project().interfaces||[]).filter(i=>i.source.model_id===id).map(i=>'Interface '+i.id)]:[];return users.length?'Used by '+users.join(', ')+'. Remove or remap these dependents first.':'';}
  function recordActions(kind,id) {
    const reason=deletionReason(kind,id);
    return '<div class="sd-action-row"><button type="button" class="sd-button" data-author-edit="'+kind+'" data-id="'+esc(id)+'" '+(!state.draft?'disabled':'')+'>Edit</button><button type="button" class="sd-button sd-quiet" data-author-remove="'+kind+'" data-id="'+esc(id)+'" '+(!state.draft||reason?'disabled':'')+' title="'+esc(reason)+'">Remove</button></div>'+(reason&&state.draft?'<p class="sd-small sd-muted">'+esc(reason)+'</p>':'');
  }
  // Disclosure state is presentation-only and scoped to this saved page context.
  // It never writes a project, a draft, or browser storage.
  const pageDisclosures=new Map();
  function disclosureKey(id) {return JSON.stringify([state.data.project_id,state.data.revision,state.page,state.system,id]);}
  function rememberDisclosures() {
    root.querySelectorAll('details[data-disclosure-key]').forEach(el=>pageDisclosures.set(el.dataset.disclosureKey,el.open));
  }
  function disclosure(id,title,body,{className='sd-context-disclosure',open=false,summary=''}={}) {
    const key=disclosureKey(id),expanded=pageDisclosures.has(key)?pageDisclosures.get(key):open;
    return '<details class="'+className+'" data-disclosure-key="'+esc(key)+'"'+(expanded?' open':'')+'><summary>'+title+(summary?'<span class="sd-disclosure-meta">'+summary+'</span>':'')+'</summary><div class="sd-disclosure-body">'+body+'</div></details>';
  }
  function projectDescription() {
    const description=project().description;
    return description?disclosure('project-description','Project purpose, assumptions and scope','<p class="sd-preserve">'+esc(description)+'</p>',{summary:'Read the supplied project context'}):'';
  }
  function authorGroup(id,title,count,body,actions='') {
    return disclosure('author-group:'+id,'<h2>'+title+'</h2>','<div class="sd-action-row">'+actions+'</div>'+body,{className:'sd-author-section sd-author-group',open:!count,summary:count+' '+(count===1?'record':'records')});
  }
  function authorRecord(kind,id,title,summary,body) {
    return disclosure('author-record:'+kind+':'+id,'<span class="sd-author-record-title">'+esc(title)+'</span>',body+recordActions(kind,id),{className:'sd-author-record',summary});
  }
  function authoring() {
    const p=project(),disabled=!state.draft?'disabled':'',inputs=Object.entries(p.inputs),requirements=allReqs(),models=allModels();
    const limits=new Set(requirements.map(r=>r.limit_input));
    const inputRecords=entries=>entries.map(([id,input])=>authorRecord('input',id,human(id),measure(input),'<p class="sd-small sd-muted">Input ID '+esc(id)+'</p><p class="sd-small sd-preserve"><strong>Source</strong><br>'+esc(input.source)+'</p>')).join('');
    const inputGroups=inputs.length?[
      ['parameters','Model inputs',inputs.filter(([id])=>!limits.has(id))],
      ['limits','Requirement limits',inputs.filter(([id])=>limits.has(id))]
    ].filter(([, ,entries])=>entries.length).map(([id,title,entries])=>disclosure('author-inputs:'+id,'<h3>'+title+'</h3>',inputRecords(entries),{className:'sd-author-input-group',open:true,summary:entries.length+' '+(entries.length===1?'input':'inputs')})).join(''):'<p class="sd-empty-record">No inputs yet. Add your supplied parameters and requirement limits.</p>';
    const inputSection=authorGroup('inputs','Inputs and limits',inputs.length,'<p class="sd-small sd-muted">Enter every value, exact unit and source explicitly. A blank value is never interpreted as zero. Limit records may also be bound to models.</p>'+inputGroups,'<button type="button" class="sd-button" data-author-add="input" '+disabled+'>Add input</button>');
    const modelSection=authorGroup('models','Model definitions',models.length,'<p class="sd-small sd-muted">Select a maintained model and bind supplied input records using its exact units. Missing parameters may be saved for later completion.</p>'+(models.map(m=>authorRecord('model',m.id,human(m.id),esc(catalogModel(m.type)?.title || human(m.type)),'<p class="sd-small sd-muted">Model ID '+esc(m.id)+'</p><p class="sd-small sd-preserve">'+esc(m.description || '')+'</p><ul class="sd-scope-list">'+Object.entries(m.inputs).map(([parameter,id])=>'<li>'+esc(human(parameter))+' → '+esc(id)+' · '+measure(p.inputs[id])+'</li>').join('')+'</ul>'+(!Object.keys(m.inputs).length&&!Object.keys(m.links||{}).length?'<p class="sd-small sd-muted">No parameter bindings yet.</p>':'')+Object.entries(m.links||{}).map(([role,l])=>'<p class="sd-small">'+esc(role)+' ← '+esc(l.model_id+'.'+l.metric)+' · '+esc(window.SixDUnits?.format(l.unit)??l.unit)+'</p>').join(''))).join('') || '<p class="sd-empty-record">No models yet. Add a supported model to declare its input bindings.</p>'),'<button type="button" class="sd-button" data-action="chains">Calculation chains</button><button type="button" class="sd-button" data-author-add="model" '+(!state.draft||!author.catalog?'disabled':'')+'>Add model</button>');
    const requirementSection=authorGroup('requirements','Requirements',requirements.length,'<p class="sd-small sd-muted">Add a model and a supplied limit input first. Criteria use a named metric, operator and limit; criticality is explicit.</p>'+(requirements.map(r=>authorRecord('requirement',r.id,r.title,esc(r.critical?'Critical':'Noncritical'),'<p class="sd-small sd-muted">Requirement ID '+esc(r.id)+'</p><p>'+esc(r.model_id)+' · '+esc(catalogModel(model(r.model_id)?.type)?.metrics.find(m=>m.name===r.metric)?.label || r.metric)+' '+esc(r.operator)+' '+esc(r.limit_input)+' · '+measure(p.inputs[r.limit_input])+'</p>')).join('') || '<p class="sd-empty-record">No requirements yet. Declare a criterion to assess against calculated evidence.</p>'),'<button type="button" class="sd-button" data-author-add="requirement" '+(!state.draft||!models.length||!inputs.length?'disabled':'')+'>Add requirement</button>');
    return '<article class="sd-authoring"><div class="sd-notice">'+(state.draft?'Authoring the shared draft. Save revision records these changes; calculations run only when requested.':'Saved configuration R'+state.data.revision+'. Choose Edit draft to change its setup.')+'</div>'+(!state.draft?'<button type="button" class="sd-button" data-action="author-edit" '+(!latest()?'disabled':'')+'>Edit draft</button>':'')+'<section class="sd-author-section"><h2>Project details</h2><p class="sd-small sd-muted">Project ID '+esc(p.project_id)+' is fixed.</p><label class="sd-field">Project name<input class="sd-input" data-project-field="name" value="'+esc(p.name)+'" required '+disabled+'></label><label class="sd-field">Lifecycle stage<select class="sd-input" data-project-field="lifecycle_stage" '+disabled+'>'+ (author.catalog?.lifecycle_stages || ['design','simulation','physical_test','operation']).map(stage=>option(stage,human(stage),p.lifecycle_stage)).join('')+'</select></label>'+disclosure('author-description','Purpose, assumptions and intended scope','<label class="sd-field">Purpose and assumptions<textarea class="sd-input" data-project-field="description" rows="4" required '+disabled+'>'+esc(p.description)+'</textarea></label>',{open:!p.description.trim(),summary:'Read or edit the supplied context'})+'<p class="sd-small sd-muted">The stage records your context. Physical-test and operational evidence integrations are not supplied by these calculators.</p></section>'+inputSection+modelSection+requirementSection+'<section class="sd-author-section" id="sd-setup-validation" aria-live="polite">'+preflightMarkup()+'</section><div class="sd-action-row"><button type="button" class="sd-button" data-action="export-project">Export project JSON</button><button type="button" class="sd-button sd-quiet" data-action="back">Return to systems</button></div></article>';
  }
  function editorError(error) {$('#sd-author-error').textContent=error.message || String(error);$('#sd-author-error').hidden=false;}
  function editorField(label,name,value='',attributes='') {return '<label class="sd-field">'+label+'<input class="sd-input" name="'+name+'" value="'+esc(value)+'" '+attributes+'></label>';}
  function inputOptions(unit,selected='') {
    let choices=option('','Select a supplied input',selected);
    for(const [id,input] of Object.entries(project().inputs))choices+=option(id,id+' · '+(window.SixDUnits?.format(input.unit)??input.unit)+(unit&&input.unit!==unit?' · incompatible unit':''),selected,!!unit&&input.unit!==unit);
    return choices;
  }
  function renderEditor(kind,id,values={}) {
    const old=kind==='input'?project().inputs[id]:kind==='model'?model(id):req(id),v={...old,...values};
    let body=editorField('Unique ID','id',id || values.id || '',(id?'readonly':'required')+' autocomplete="off"');
    if(kind==='input')body+=editorField('Value','value',v.value ?? '', 'type="number" step="any" required')+editorField('Exact unit','unit',v.unit || '', 'required')+editorField('Source','source',v.source || '', 'required')+'<p class="sd-small sd-muted">Use 1 for a dimensionless unit. Supply the actual provenance; no source is inferred.</p>';
    if(kind==='model'){
      const type=v.type || '',c=catalogModel(type);
      body+='<label class="sd-field">Supported model<select class="sd-input" name="type" '+(id?'disabled':'required')+'>'+option('','Select a model',type)+(author.catalog?.models || []).map(m=>option(m.type,m.title+(m.type==='power_energy_budget'?' · use Power & energy':''),type,m.type==='power_energy_budget'&&!id)).join('')+(!c&&type?option(type,human(type)+' · unsupported import',type):'')+'</select></label><p class="sd-small sd-muted">The ID and selected adapter remain fixed after adding. To replace an adapter, add another model and explicitly remap its requirements.</p><label class="sd-field">Model context and assumptions<textarea class="sd-input" name="description" rows="3">'+esc(v.description || '')+'</textarea></label>';
      if(v.links&&Object.keys(v.links).length)body+='<p class="sd-notice">Calculated parameter bindings are retained below. Edit or remove them in <button type="button" class="sd-mini-action" data-action="chains">Calculation chains</button>.</p>';
      if(c)body+='<p>'+esc(c.description)+' <span class="sd-small sd-muted">Adapter '+esc(c.version)+'</span></p><h3>Parameter bindings</h3><p class="sd-small sd-muted">Only inputs with the exact required unit can be selected. Leave a parameter unbound to complete it later.</p>'+c.parameters.map(parameter=>v.links?.[parameter.name]?'<div class="sd-field"><strong>'+esc(human(parameter.name))+' · '+esc(window.SixDUnits?.format(parameter.unit)??parameter.unit)+'</strong><p>Calculated from '+esc(v.links[parameter.name].model_id+'.'+v.links[parameter.name].metric)+'</p></div>':'<label class="sd-field">'+esc(human(parameter.name))+' · '+esc(window.SixDUnits?.format(parameter.unit)??parameter.unit)+'<select class="sd-input" name="binding:'+esc(parameter.name)+'">'+inputOptions(parameter.unit,v.inputs?.[parameter.name])+'</select></label>').join('')+'<h3>Assumptions</h3><ul class="sd-scope-list">'+c.assumptions.map(s=>'<li>'+esc(s)+'</li>').join('')+'</ul><h3>Not assessed</h3><ul class="sd-scope-list">'+c.not_assessed.map(s=>'<li>'+esc(s)+'</li>').join('')+'</ul>';
      if(type==='orbital_trajectory')body+='<fieldset class="sd-accuracy-editor"><legend>Declared orbital numerical accuracy</legend><p class="sd-small sd-muted">Optional, user-supplied accuracy criteria. Enter both positive tolerances and their source, or leave all three blank. No default tolerance is inferred. Grid agreement is checked at aligned saved samples; it is not a true error bound or physical validation.</p>'+editorField('Position tolerance · m','accuracy_position_m',values.accuracy_position_m??v.accuracy?.position_tolerance_m??'','type="number" step="any" min="0"')+editorField('Velocity tolerance · m/s','accuracy_velocity_m_s',values.accuracy_velocity_m_s??v.accuracy?.velocity_tolerance_m_s??'','type="number" step="any" min="0"')+editorField('Accuracy criteria source / rationale','accuracy_source',values.accuracy_source??v.accuracy?.source??'')+'</fieldset>';
      if(c?.applicability)body+=applicabilityMarkup(c.applicability,'Current model catalog context; no run is being validated in this editor.');
      body+=c?.profile?.editor==='staged_ascent'?'<p class="sd-small">Stage masses and thrust rows are authored in <button type="button" class="sd-mini-action" data-action="staged-ascent">Variable thrust &amp; staging</button>.</p>':'<p class="sd-small">Named power modes and equipment rows are authored in <button type="button" class="sd-mini-action" data-action="power">Power &amp; energy</button>.</p>';
      const extras=Object.entries(v.inputs || {}).filter(([name])=>!c?.parameters.some(p=>p.name===name));
      body+=extras.map(([name,inputId])=>'<label class="sd-field">'+esc(name)+' · '+(c?.profile?(c.profile.editor==='staged_ascent'?'Stage profile binding':'Operating mode binding'):c?'unrecognized parameter':'imported binding')+'<select class="sd-input" name="binding:'+esc(name)+'">'+inputOptions(null,inputId)+'</select></label>').join('');
    }
    if(kind==='requirement'){
      const modelId=v.model_id || '',c=catalogModel(model(modelId)?.type),metric=v.metric || '',known=c?.metrics.find(m=>m.name===metric);
      body+=editorField('Requirement title','title',v.title || '', 'required')+'<label class="sd-field">Model<select class="sd-input" name="model_id" required>'+option('','Select a model',modelId)+allModels().map(m=>option(m.id,m.id+' · '+(catalogModel(m.type)?.title || human(m.type)),modelId)).join('')+'</select></label><label class="sd-field">Metric<select class="sd-input" name="metric" required>'+option('','Select a metric',metric)+(c?.metrics || []).map(m=>option(m.name,m.label+' · '+(window.SixDUnits?.format(m.unit)??m.unit),metric)).join('')+(!known&&metric?option(metric,metric+' · unknown metric',metric):'')+'</select></label>'+(!c&&modelId?'<p class="sd-notice">This imported model has no supported metric catalog. Existing criteria remain unassessed until mapped to a supported model.</p>':'')+'<label class="sd-field">Operator<select class="sd-input" name="operator" required>'+option('','Select an operator',v.operator || '')+(author.catalog?.operators || ['<=','>=','==']).map(op=>option(op,op,v.operator)).join('')+'</select></label><label class="sd-field">Limit input'+(known?' · '+esc(window.SixDUnits?.format(known.unit)??known.unit):'')+'<select class="sd-input" name="limit_input" required>'+inputOptions(known?.unit,v.limit_input)+'</select></label><label class="sd-field">Critical requirement<select class="sd-input" name="critical" required>'+option('','Select criticality',v.critical===undefined?'':String(v.critical))+option('true','Yes',String(v.critical))+option('false','No',String(v.critical))+'</select></label>';
    }
    $('#sd-author-title').textContent=(id?'Edit ':'Add ')+kind;$('#sd-author-fields').innerHTML=body;$('#sd-author-error').hidden=true;
  }
  function openEditor(kind,id='') {
    if(!state.draft)return;
    author.editor={kind,id,projectId:state.data.project_id,revision:state.data.revision,draft:state.draft};renderEditor(kind,id);$('#sd-author-dialog').showModal();
  }
  function saveEditor() {
    const context=author.editor;if(!context||context.projectId!==state.data.project_id||context.revision!==state.data.revision||context.draft!==state.draft){editorError(new Error('This draft changed. Close the editor and reopen it.'));return;}
    const form=$('#sd-author-form');if(!form.reportValidity())return;
    const values=Object.fromEntries(new FormData(form));form.querySelectorAll('select[name]').forEach(el=>{values[el.name]=el.value;});
    const id=values.id.trim(),kind=context.kind,p=state.draft;
    try{
      if(!id)throw new Error('Provide a unique ID.');
      if(!context.id&&['__proto__','constructor','prototype'].includes(id))throw new Error('Choose a different ID; this name is reserved.');
      if(!context.id&&(Object.hasOwn(p.inputs,id)||p.models.some(m=>m.id===id)||p.requirements.some(r=>r.id===id)))throw new Error('This ID already exists. Choose a unique ID.');
      if(kind==='input'){
        if(values.value.trim()===''||!Number.isFinite(Number(values.value)))throw new Error('Provide a finite value; blank is not zero.');
        if(!values.unit.trim()||!values.source.trim())throw new Error('Provide an explicit unit and source.');
        Object.defineProperty(p.inputs,id,{value:{value:Number(values.value),unit:values.unit.trim(),source:values.source.trim()},writable:true,enumerable:true,configurable:true});
      }else if(kind==='model'){
        const old=model(context.id),type=old?.type || values.type;if(!type)throw new Error('Select a supported model.');
        const inputs=Object.fromEntries(Object.entries(values).filter(([key,value])=>key.startsWith('binding:')&&value).map(([key,value])=>[key.slice(8),value]));
        const entry={id,type,inputs};if(old?.links){entry.links=copy(old.links);for(const role of Object.keys(entry.links))delete entry.inputs[role];}if(values.description.trim())entry.description=values.description.trim();
        if(type==='orbital_trajectory'){
          const position=(values.accuracy_position_m||'').trim(),velocity=(values.accuracy_velocity_m_s||'').trim(),source=(values.accuracy_source||'').trim();
          if(position||velocity||source){
            if(!position||!velocity||!source||!Number.isFinite(Number(position))||Number(position)<=0||!Number.isFinite(Number(velocity))||Number(velocity)<=0)throw new Error('Supply positive finite position and velocity tolerances and their source, or leave all accuracy fields blank.');
            entry.accuracy={position_tolerance_m:Number(position),velocity_tolerance_m_s:Number(velocity),source};
          }
        }
        if(old)p.models[p.models.findIndex(m=>m.id===id)]=entry;else p.models.push(entry);
      }else{
        if(!values.title.trim()||!values.model_id||!values.metric||!values.limit_input||!values.operator||!values.critical)throw new Error('Provide the title, model, metric, operator, supplied limit and criticality.');
        const entry={id,title:values.title.trim(),model_id:values.model_id,metric:values.metric,operator:values.operator,limit_input:values.limit_input,critical:values.critical==='true'};
        const index=p.requirements.findIndex(r=>r.id===id);if(index>=0)p.requirements[index]=entry;else p.requirements.push(entry);
      }
      $('#sd-author-dialog').close();author.editor=null;state.selected={kind,id};draftChanged();message(human(kind)+' '+id+' updated in the shared draft. Save revision to retain it.');
    }catch(error){editorError(error);}
  }
  function renderCalculationFeedback(){
    const host=$('#sd-calculation-feedback'),entry=state.calculationFeedback;
    host.hidden=!entry||entry.projectId!==state.data?.project_id||entry.revision!==state.data?.revision||state.page==='projects';
    if(host.hidden)return;
    host.textContent=entry.text;host.dataset.phase=entry.phase;host.setAttribute('aria-busy',String(entry.phase==='working'));
  }
  function renderReviewGuide(){
    const host=$('#sd-review-guide');if(!host||!window.SixDReviewGuide)return;
    host.hidden=!reviewGuide.open;root.classList.toggle('sd-guide-visible',reviewGuide.open);root.querySelector('[data-action="guided-toggle"]')?.setAttribute('aria-expanded',String(reviewGuide.open));
    if(!reviewGuide.open)return;
    if(state.page==='projects'){host.innerHTML='<div class="sd-guide-intro"><strong>Start with one project</strong><p>Choose a project below. Then calculate its saved design, change an input, recalculate and compare the results. Ask the rocket whenever you need an explanation.</p><button type="button" class="sd-mini-action" data-action="guided-close">Close guide</button></div>';delete host.dataset.rendered;return;}
    const html=window.SixDReviewGuide.render({view:state.data,draft:state.draft,dirty:dirty(),isLatest:latest(),busy:state.busy,impactVerified:!!state.impact,page:state.page,viewMode:state.view,exportedRun:reviewGuide.exportedRun});
    if(host.dataset.rendered!==html){host.innerHTML=html;host.dataset.rendered=html;}
  }
  function locationSnapshot() {
    if(state.page==='projects')return {page:'projects'};
    return {projectId:state.data.project_id,revision:state.data.revision,page:state.page,
      system:state.system,view:state.view,panel:state.panel,
      ...(state.page==='system'&&state.selected?{selected:{...state.selected}}:{}),
      ...(state.panel==='assistant'?{aiScope:ai.scope}:{}),
      ...(state.page==='simulation'&&state.trajectory?{trajectory:{...state.trajectory}}:{})};
  }
  function selectedLocationLabel() {
    const item=state.selected;
    return !item?null:item.kind==='requirement'?req(item.id)?.title:item.kind==='model'?model(item.id)?.title||human(item.id):human(item.id);
  }
  function renderLocation() {
    if(!state.data)return;
    window.SixDWorkspaceShell.renderChrome({page:state.page,project:project(),revision:state.data.revision,
      system:activeSystem(),selected:selectedLocationLabel(),backEnabled:navigation?.canBack,
      tools:window.SixDWorkspaceShell.toolSummary(state.data,{hasDraft:!!state.draft})});
    root.querySelectorAll('[data-owner-only],[data-action="owner-settings"],[data-action="ai-quality"]').forEach(el=>el.hidden=state.hosted);
    root.querySelectorAll('[data-investigate],[data-test-evidence-investigate],[data-action="project-investigate"],[data-action="investigate"]').forEach(el=>{if(!el.closest('#sd-rocket-dialog'))el.hidden=true;});
    icons();
  }
  function pageContextKey(){
    return state.page==='projects'?'projects':JSON.stringify([state.data?.project_id,state.data?.revision,state.page]);
  }
  function renderPagePosition(){
    const key=pageContextKey();
    if(key===renderedPageContext)return;
    renderedPageContext=key;
    // A new work page starts at its heading. Same-page selections/refreshes
    // retain position; cancelled navigation never changes this context key.
    window.scrollTo({left:0,top:0,behavior:'instant'});
  }
  function closeNavigationDialogs() {
    for(const dialog of root.querySelectorAll('dialog[open]'))dialog.close();
    author.editor=null;$('#sd-ai-key').value='';
  }
  async function restoreLocation(route,initial=false) {
    if(state.busy&&!initial){message('Wait for the current operation to finish before navigating.');return false;}
    if(state.stagedProfileEdit){message('Apply or cancel the open thrust-profile edit before navigating. Your edits are still open.');return false;}
    if(author.editor&&!window.confirm('Leave the open record editor? Changes not applied to the draft will be lost.'))return false;
    const switching=route.page!=='projects'&&(state.data?.project_id!==route.projectId||state.data?.revision!==route.revision);
    if(switching&&dirty()&&!window.confirm('Discard unsaved draft changes and open this saved project revision?'))return false;
    closeNavigationDialogs();
    if(!initial)setBusy(true);
    try{
    if(switching)await load(route.projectId,route.revision);
    if(!state.data)return false;
    stopInvestigationPolling();
    state.page=route.page;
    if(route.page!=='projects'){
      state.system=systems().some(s=>s.id===route.system)?route.system:'overview';
      state.view=route.view||'canvas';state.panel=route.panel||'details';
      state.selected=route.selected&&validSelection(route.selected)?route.selected:defaultSelection();
      ai.scope=route.aiScope||'requirement';ai.testSelection=null;
      state.trajectory=route.page==='simulation'&&route.trajectory?{...route.trajectory}:null;
      state.testEvidenceTarget=null;state.stagedProfileEdit=null;
    }
    resetCamera();render();
    if(state.page==='authoring')void loadCatalog().then(()=>{if(state.page==='authoring')render();}).catch(showError);
    if(state.page==='system'&&state.panel==='assistant')void refreshAiStatus();
    return true;
    }finally{if(!initial){setBusy(false);if(state.data)render();}}
  }
  function unmountWorkspaceViews() {
    for(const name of ['SixDReviewWorkspace','SixDEnvelopes','SixDSimulationImports','SixDPoweredFlight','SixDGuidedAscent','SixDStagedAscent','SixDSimulation','SixDTestData','SixDScenarios','SixDActions','SixDSources','SixDChains','SixDAttitude','SixDPowerBudget','SixDSystems','SixDAIQuality','SixDOwnerSettings'])window[name]?.unmount?.();
    for(const context of [coverageLinks,comparisonView,researchView,actionLinks,sourceLinks]){context.dispose?.();context.dispose=null;}
  }
  // The shell owns the single page heading and lead. Module introductions retain
  // their controls, revision/status badges, and all distinct applicability notes.
  const pagePresentation={
    report:['Review report','Requirements, calculated evidence and unresolved scope for this saved configuration.'],
    changes:['Changes','A changed input identifies dependencies needing review. New calculation outcomes appear only after checks run.'],
    coverage:['Engineering coverage','Connect mission phases to engineering checks. Keep calculated findings, model assumptions and missing analysis visible together.'],
    comparison:['Compare designs','Select two recorded reviews or scenario cases. Explore their inputs, criteria and evidence without rerunning anything.'],
    actions:['Engineering actions','Track the next check, the missing evidence and the conditions for completing the task.'],
    sources:['Source library','Keep the passages behind your project decisions, then connect them to the checks they support.'],
    chains:['Calculation chains','Connect a calculated scalar to a declared parameter. Upstream calculations run first; the saved evidence shows which values were passed along.'],
    'powered-flight':['Vertical flight','Inspect recorded altitude, velocity, mass and forces through a constant-thrust burn and above-surface coast.'],
    'guided-ascent':['Planar ascent','Replay recorded horizontal motion and altitude through a declared pitch programme, burnout and above-surface coast.'],
    'staged-ascent':['Variable thrust & staging','Replay saved variable-thrust flight, exact fuel cutoff, dry-mass separation and upper-stage ignition.'],
    attitude:['Guidance & control','Review how a declared single-axis controller turns toward a fixed target, responds to a constant disturbance and reaches its torque limit.'],
    power:['Power & energy','Check simultaneous power demand and energy required across a declared operating sequence.'],
    systems:['Systems & interfaces','Organize the actual project and declare the scalar contracts between its systems.'],
    simulation:['Orbital simulation','Explore recorded position and velocity in three dimensions, then inspect the evidence at any instant.'],
    scenarios:['Scenarios','Compare explicit hypothetical inputs against a saved baseline, with calculated findings and traceable margins.'],
    'ai-quality':['AI quality & tools','Current-model qualification, retained results and explicit optional metrics export.'],
    'review-home':['Overview','Understand the saved design, examine its evidence and follow the unresolved work.'],
    envelopes:['Envelope studies','Explore explicit combinations of model parameters against the saved revision. Preview the exact samples before running the study.'],
    'simulation-imports':['Simulation imports','Inspect imported simulation or measurement histories, then compare compatible samples against a frozen project calculation.'],
    'test-data':['Test data','Import supplied scalar measurements and compare them with this exact saved design. Measurement compliance and prediction agreement are separate findings.'],
    authoring:['Author project','Supply inputs, connect supported models and declare the criteria you want to assess.']
  };
  function renderPageHeading() {
    const presentation=pagePresentation[state.page] || [activeSystem()?.title || 'Systems workspace','Explore declared inputs, model mappings, requirements and their evidence.'];
    $('#sd-breadcrumb-current').textContent=presentation[0];
    $('#sd-page-title').textContent=presentation[0];
    $('#sd-page-description').textContent=presentation[1];
  }
  function render() {
    if(!state.data)return; const p=project();
    repairContext();
    root.classList.toggle('sd-review-home',state.page==='review-home');
    root.querySelectorAll('.sd-sidebar [data-action]').forEach(el=>{if(el.dataset.action===state.page)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
    root.classList.toggle('sd-simulation-open',['simulation','envelopes','simulation-imports','scenarios','test-data','systems','power','attitude','powered-flight','guided-ascent','staged-ascent','chains','comparison','coverage','ai-quality'].includes(state.page));
    try{localStorage.setItem('sixd.workspace.last-project',state.data.project_id);}catch{}
    const picker=$('#sd-project-picker');picker.innerHTML=window.SixDWorkspaceShell.projectChoices(state.projects).map(item=>'<option value="'+esc(item.project_id)+'" title="'+esc(item.project_id)+'" '+(item.project_id===state.data.project_id?'selected':'')+'>'+esc(item.display_name)+'</option>').join('');
    $('#sd-revision-picker').innerHTML=state.data.revisions.map(r=>'<option value="'+r.revision+'" '+(r.revision===state.data.revision?'selected':'')+'>R'+r.revision+' · '+(r.has_current_run?'review recorded':'awaiting checks')+'</option>').join('');
    $('#sd-project-note').textContent=p.lifecycle_stage+' · '+allModels().length+' model mappings';
    $('#sd-project-name').textContent=p.name;
    renderPageHeading();
    root.querySelector('[data-action="scenarios"]').setAttribute('aria-pressed',String(state.page==='scenarios'));
    root.querySelector('[data-action="test-data"]').setAttribute('aria-pressed',String(state.page==='test-data'));
    $('#sd-edit-trigger').hidden=['simulation','envelopes','simulation-imports','scenarios','test-data','systems','power','attitude','powered-flight','guided-ascent','staged-ascent','chains','comparison','coverage'].includes(state.page);
    $('#sd-run-trigger').hidden=['simulation','envelopes','simulation-imports','scenarios','test-data','systems','power','attitude','powered-flight','guided-ascent','staged-ascent','chains','comparison','coverage'].includes(state.page);
    root.querySelector('[data-action="simulation"]').setAttribute('aria-pressed',String(state.page==='simulation'));
    $('#sd-scope-chip').textContent=(state.draft?'Draft from ':'')+'R'+state.data.revision+(currentRun()?' · Reviewed':' · Needs checks');
    $('#sd-save-state').textContent=state.draft?'Unsaved draft · saved revision preserved':'R'+state.data.revision+' saved locally · '+(currentRun()?'calculated evidence recorded':'awaiting checks');
    $('#sd-edit-trigger').disabled=!!state.draft || !latest() || state.busy;
    $('#sd-edit-trigger').title=!latest()?'Select the latest revision to create a draft.':'';
    $('#sd-run-trigger').disabled=!!state.draft || state.busy || !hasSetup() || (state.page==='review-home'&&!latest()) || (state.page==='authoring'&&(author.snapshot!==setupKey()||!author.preflight?.can_run||author.loading));
    $('#sd-run-trigger').title=!hasSetup()?'Open Author project and add a model and requirement before running checks.':state.page==='authoring'?'Validate setup and resolve its errors before running here.':'';
    $('#sd-run-trigger').innerHTML=icon('play')+(currentRun()?'Run checks again':'Run checks');
    root.querySelectorAll('[data-view]').forEach(button=>button.setAttribute('aria-selected',String(button.dataset.view===state.view && state.page==='system')));
    $('#sd-view-content').setAttribute('aria-labelledby',state.page==='system'?'sd-tab-'+state.view:'sd-page-title');
    renderTree();renderDraft();renderMain();renderPanel();renderLocation();renderRocket();renderCalculationFeedback();icons();
    if(!navigationStarting)navigation?.sync();
    renderPagePosition();
    rocket?.refreshPlacement?.();
  }
  function systemDepth(s){let n=0,parent=s.parent_id,seen=new Set([s.id]);while(parent&&!seen.has(parent)){seen.add(parent);n++;parent=systems().find(row=>row.id===parent)?.parent_id;}return n;}
  function orderedSystems(){const rows=systems(),ordered=[],seen=new Set();function visit(parent){for(const s of rows.filter(row=>(row.parent_id||null)===parent)){if(seen.has(s.id))continue;seen.add(s.id);ordered.push(s);visit(s.id);}}visit(null);rows.filter(s=>!seen.has(s.id)).forEach(s=>ordered.push(s));return ordered;}
  function renderTree() {
    $('#sd-system-tree').innerHTML='<button type="button" class="sd-tree-root" data-system="overview" aria-current="'+(state.system==='overview')+'">'+icon('orbit')+'All systems<span class="sd-tree-count">'+systems().length+'</span></button>'+orderedSystems().map(s=>'<button type="button" class="sd-tree-item" style="padding-left:'+(12+Math.min(6,systemDepth(s))*12)+'px" data-system="'+esc(s.id)+'" aria-current="'+(state.system===s.id)+'"><span class="sd-dot"></span>'+esc(s.title)+'<span class="sd-tree-count">'+s.requirement_ids.length+'</span></button>'+(state.system===s.id?'<div class="sd-tree-child">'+allReqs().filter(r=>s.requirement_ids.includes(r.id)).map(r=>'<button type="button" data-kind="requirement" data-id="'+esc(r.id)+'" aria-current="'+(state.selected?.kind==='requirement'&&state.selected.id===r.id)+'"><span>'+esc(r.title)+'</span></button>').join('')+'</div>':'')).join('');
  }
  function renderDraft() {
    renderReviewGuide();
    const bar=$('#sd-draft-strip');bar.hidden=!state.draft;
    if(!state.draft)return;
    const invalid=editErrors();const info=impact();
    bar.innerHTML='<span><strong>Draft changes</strong> · '+(dirty()?(info.changed_inputs?.length||0)+' inputs changed · '+(info.affected_requirement_ids?.length||0)+' requirements need review':'Edit project details, inputs, models or requirements.')+(invalid.length?' · '+esc(invalid[0]):'')+'</span><div class="sd-draft-actions"><button type="button" class="sd-button" data-action="author-project">Author project</button><button type="button" class="sd-button" data-action="impact" '+(!dirty()||invalid.length?'disabled':'')+'>Preview impact</button><button type="button" class="sd-button sd-primary" data-action="save" '+(!dirty()||invalid.length?'disabled':'')+'>Save revision</button><button type="button" class="sd-button sd-quiet" data-action="discard">Discard draft</button></div>';
  }
  function node(kind,id,title,x,y,body,affected=false) {
    const selected=state.selected?.kind===kind&&state.selected.id===id;
    return '<div class="sd-node '+(selected?'sd-selected ':'')+(affected?'sd-needs':'')+'" style="left:'+x+'px;top:'+y+'px"><button type="button" class="sd-node-main" data-kind="'+kind+'" data-id="'+esc(id)+'" aria-pressed="'+selected+'"><span class="sd-node-label">'+icon(kind==='input'?'braces':kind==='requirement'?'square-check':'function-square')+human(kind)+'</span><strong>'+esc(title)+'</strong>'+body+'</button>'+'</div>';
  }
  function canvas() {
    if(!allModels().length&&!systems().length)return '<div class="sd-empty"><h2>Define your first model</h2><p>This configuration has '+Object.keys(project().inputs).length+' inputs and no model mappings. Open Author project to add supplied inputs, a supported model and its requirements.</p><button type="button" class="sd-button sd-primary" data-action="author-project">Author project</button><button type="button" class="sd-button" data-action="import">Use a reference template</button></div>';
    let content='',width=920,height=650;
    if(state.system==='overview'){
      const positions={}; const columns=2;let y=25;
      for(let start=0;start<systems().length;start+=columns){
        const row=systems().slice(start,start+columns);let maxHeight=0;
        row.forEach((s,col)=>{const reqs=allReqs().filter(r=>s.requirement_ids.includes(r.id));const x=30+col*330,cardHeight=105+reqs.reduce((total,r)=>total+82+(historicalAccuracyBadge(r.model_id)?22:0),0);positions[s.id]={x,y,h:cardHeight};
          content+='<section class="sd-system-overview" style="left:'+x+'px;top:'+y+'px;width:280px"><h3>'+icon('box')+'<button type="button" data-system="'+esc(s.id)+'">'+esc(s.title)+'</button></h3><p class="sd-small sd-muted">'+s.model_ids.length+' model mapping'+(s.model_ids.length===1?'':'s')+'</p>'+reqs.map(r=>'<button type="button" class="sd-overview-row" data-kind="requirement" data-id="'+esc(r.id)+'" aria-pressed="'+(state.selected?.kind==='requirement'&&state.selected.id===r.id)+'">'+esc(r.title)+'<small>'+chip(reqStatus(r.id))+'</small>'+historicalAccuracyBadge(r.model_id)+'</button>').join('')+'</section>';
          maxHeight=Math.max(maxHeight,cardHeight);
        });y+=maxHeight+35;
      }
      width=660;height=Math.max(550,y);
      const systemLinks=[...(graph().system_links||[]),...systems().filter(s=>s.parent_id).map(s=>({source:s.parent_id,target:s.id,type:'hierarchy',title:'Parent / child organization'}))];
      const lines=systemLinks.filter(link=>positions[link.source]&&positions[link.target]).map(link=>{
        const a=positions[link.source],b=positions[link.target],x1=a.x+280,y1=a.y+30,x2=b.x===a.x?b.x+280:b.x,y2=b.y+30;
        const bend=b.x===a.x?40:25;
        return '<path class="'+(link.type==='hierarchy'?'sd-hierarchy-line':'sd-interface-line')+'" d="M'+x1+' '+y1+' C'+(x1+bend)+' '+y1+' '+(x2+(b.x===a.x?bend:-bend))+' '+y2+' '+x2+' '+y2+'"><title>'+esc(link.title)+(link.interface_id?' · '+esc(link.interface_id):'')+'</title></path>';
      }).join('');
      if(lines)content='<svg class="sd-graph-lines" style="width:'+width+'px;height:'+height+'px" viewBox="0 0 '+width+' '+height+'" aria-label="Declared system interfaces and parent relationships">'+lines+'</svg>'+content;
    }else{
      const inputs=selectedInputs();const models=selectedModels();const reqs=selectedReqs();const coords=new Map();
      width=800;height=Math.max(550,inputs.length*127+35,reqs.length*192+35,models.length*190+35);
      inputs.forEach((id,i)=>{const input=project().inputs[id];coords.set('input:'+id,{x:20,y:30+i*127,w:200,h:108});content+=node('input',id,human(id),20,30+i*127,'<span class="sd-node-value">'+measure(input)+'</span><span class="sd-node-foot">'+(state.draft?'Draft input':'Supplied input')+'</span>',!!state.draft&&impact().changed_inputs?.includes(id));});
      models.forEach((m,i)=>{const y=Math.max(50,(height/(models.length+1))*(i+1)-65);coords.set('model:'+m.id,{x:285,y,w:210,h:125});content+=node('model',m.id,human(m.id),285,y,'<span class="sd-node-foot">'+esc(human(m.type))+'</span>'+chip(modelStatus(result(m.id)))+historicalAccuracyBadge(m.id),impact().affected_model_ids?.includes(m.id)&&(!currentRun()||!!state.draft));});
      reqs.forEach((r,i)=>{const y=30+i*192;coords.set('requirement:'+r.id,{x:565,y,w:210,h:145});const f=finding(r.id);content+=node('requirement',r.id,r.title,565,y,'<span class="sd-node-value">'+(f?.evidence?measure(f.evidence.metric):'—')+'</span>'+chip(reqStatus(r.id))+historicalAccuracyBadge(r.model_id),['draft','stale'].includes(reqStatus(r.id)));});
      const lines=(graph().links||[]).filter(link=>coords.has(link.source)&&coords.has(link.target)).map(link=>{const a=coords.get(link.source),b=coords.get(link.target),x1=a.x+a.w,y1=a.y+a.h/2,x2=b.x,y2=b.y+b.h/2;const affected=link.target.startsWith('model:')?impact().affected_model_ids?.includes(link.target.slice(6)):impact().affected_requirement_ids?.includes(link.target.slice(12));return '<path class="'+((state.draft||!currentRun())&&affected?'sd-affected-line':'')+'" d="M'+x1+' '+y1+' C'+(x1+45)+' '+y1+' '+(x2-45)+' '+y2+' '+x2+' '+y2+'"/>';}).join('');
      content='<svg class="sd-graph-lines" style="width:'+width+'px;height:'+height+'px" viewBox="0 0 '+width+' '+height+'" aria-hidden="true">'+lines+'</svg>'+content;
    }
    return '<div class="sd-canvas" id="sd-canvas" aria-label="Interactive declared dependency canvas"><span class="sd-canvas-meta">'+(state.system==='overview'?'Declared systems · '+systems().length:'Inputs → model → requirements')+'</span><div class="sd-graph-stage" id="sd-graph-stage" style="width:'+width+'px;height:'+height+'px" data-width="'+width+'" data-height="'+height+'">'+content+'</div><div class="sd-legend"><span><span class="sd-dot sd-green"></span>Met</span><span><span class="sd-dot sd-amber"></span>Needs review</span><span>Drag canvas to pan</span><button type="button" class="sd-mini-action" data-action="chains">Calculation chains</button></div><div class="sd-zoom"><button type="button" class="sd-icon-button" data-action="zoom-out" aria-label="Zoom out">−</button><span id="sd-zoom-value">100%</span><button type="button" class="sd-icon-button" data-action="zoom-in" aria-label="Zoom in">+</button><button type="button" class="sd-icon-button" data-action="fit" aria-label="Fit graph">'+icon('maximize')+'</button></div></div><div class="sd-canvas-caption"><span>Explicit input bindings feed models. Calculation chains connect model results; interface contracts remain review comparisons.</span><button type="button" class="sd-mini-action" data-action="investigate">Inspect selected evidence '+icon('arrow-up-right')+'</button></div>';
  }
  function requirementTable(requirements,editable=false) {
    if(!requirements.length)return '<div class="sd-notice">No requirements are declared in this view. Add a criterion in <button type="button" class="sd-mini-action" data-action="author-project">Author project</button> before producing requirement evidence.</div>';
    return '<div class="sd-table-wrap"><table class="sd-table"><thead><tr><th>Requirement</th><th>Status</th><th>Calculated result</th><th>Declared limit</th><th>Action</th></tr></thead><tbody>'+requirements.map(r=>{
      const f=finding(r.id),input=project().inputs[r.limit_input];const selected=state.selected?.kind==='requirement'&&state.selected.id===r.id;
      const exact=comparisonNeedsExact(f?.evidence);
      return '<tr class="'+(selected?'sd-row-selected':'')+'"><td>'+selectionButton('requirement',r.id,r.title)+'<div class="sd-small sd-muted">'+esc(r.id)+'</div></td><td data-status-for="'+esc(r.id)+'">'+chip(reqStatus(r.id))+(['insufficient_accuracy','accuracy_not_assessed'].includes(reqStatus(r.id))?'<small class="sd-status-reason">'+esc(f?.reason)+'</small>':'')+historicalAccuracyNotice(r.model_id)+'</td><td>'+(f?.evidence?plotMeasure(f.evidence.metric,exact):'—')+'</td><td>'+esc(r.operator)+' '+(editable&&state.draft?inputField(r.limit_input,'value',true)+' '+esc(input.unit):plotMeasure(input,exact))+'</td><td>'+trajectoryButton(r.model_id)+'</td></tr>';
    }).join('')+'</tbody></table></div>';
  }
  function table() {
    return '<div class="sd-table-content"><div class="sd-section-heading"><h2>Requirements</h2><span class="sd-small sd-muted">'+selectedReqs().length+' linked</span></div>'+requirementTable(selectedReqs(),true)+'<div class="sd-section-heading" style="margin-top:30px"><h2>Design inputs and limits</h2><span class="sd-small sd-muted">'+(state.draft?'Draft editing':'Saved values')+'</span></div><div class="sd-table-wrap"><table class="sd-table"><thead><tr><th>Parameter</th><th>Value</th><th>Unit</th><th>Source</th></tr></thead><tbody>'+selectedInputs().map(id=>'<tr><td>'+selectionButton('input',id,human(id))+'</td><td>'+inputField(id,'value',true)+'</td><td>'+inputField(id,'unit',true)+'</td><td>'+inputField(id,'source',true)+'</td></tr>').join('')+'</tbody></table></div><p class="sd-table-note">'+(state.draft?'All values, units and sources are editable. Units are explicit; no implicit conversions occur. Save a revision before running its checks.':'Choose Edit draft to change an input, its source or a requirement limit. Original saved revisions remain available.')+'</p><h2 style="font-size:15px;margin:28px 0 13px">Model mappings</h2>'+selectedModels().map(m=>'<details class="sd-source"><summary>'+esc(human(m.id))+' · '+esc(human(m.type))+'</summary><p>'+esc(m.description || 'Explicit mapping supplied in project JSON.')+'</p><ul class="sd-scope-list">'+Object.entries(m.inputs).map(([parameter,id])=>'<li>'+esc(human(parameter))+' → '+selectionButton('input',id,human(id),'sd-mini-action')+'</li>').join('')+'</ul></details>').join('')+'</div>';
  }
  function statusCounts(requirements=allReqs()) { return requirements.reduce((counts,r)=>{const status=reqStatus(r.id);counts[status]=(counts[status]||0)+1;return counts;},{}); }
  function stats(requirements) { const counts=statusCounts(requirements);return '<div class="sd-evidence-grid"><div><strong>'+ (counts.met||0)+'</strong><span class="sd-small sd-muted">Requirements met</span></div><div><strong>'+(counts.not_met||0)+'</strong><span class="sd-small sd-muted">Requirements not met</span></div><div><strong>'+requirements.filter(r=>!['met','not_met'].includes(reqStatus(r.id))).length+'</strong><span class="sd-small sd-muted">Unassessed / pending</span></div></div>'; }
  function plottable(f) {
    const e=f?.evidence;
    return ['met','not_met'].includes(findingStatus(f)) && e &&
      Number.isFinite(e.metric?.value) && Number.isFinite(e.limit?.value) &&
      typeof e.metric.unit==='string' && e.metric.unit.length>0 && e.metric.unit===e.limit.unit &&
      ['<=','>=','=='].includes(e.operator);
  }
  const plotMeasure = (item,exact=false) => item && Number.isFinite(item.value) ? (exact?esc(String(item.value))+' '+esc(window.SixDUnits?.format(item.unit)??item.unit):measure(item)) : '—';
  function comparisonNeedsExact(e) {
    return Number.isFinite(e?.metric?.value) && Number.isFinite(e?.limit?.value) &&
      (e.operator==='==' || (e.metric.value!==e.limit.value && num(e.metric.value)===num(e.limit.value)));
  }
  function plotRecord(row) {
    const e=row.finding.evidence;
    // Keep ordinary records readable, but never round distinct values into an
    // apparently identical comparison. Full saved values remain in the sources.
    const exact=comparisonNeedsExact(e);
    return '<div class="sd-plot-record"><span>'+esc(row.label)+'</span><strong title="Saved value: '+esc(String(e.metric.value))+'">'+plotMeasure(e.metric,exact)+'</strong><span>Limit '+esc(e.operator)+' '+plotMeasure(e.limit,exact)+'</span>'+chip(findingStatus(row.finding))+'</div>';
  }
  function plotRows(requirementId) {
    const f=finding(requirementId),before=priorFinding(requirementId);
    if(state.draft || !currentRun() || currentRun().stale || !plottable(f))return [];
    const rows=[{label:'Current R'+state.data.revision,finding:f,run:currentRun()}];
    // A prior threshold belongs to its own finding, never to the current design.
    if(plottable(before) && before.model_id===f.model_id && before.metric===f.metric &&
        before.evidence.metric.unit===f.evidence.metric.unit)
      rows.push({label:(priorRun().revision===state.data.revision?'Earlier run R':'Previous R')+priorRun().revision,finding:before,run:priorRun()});
    return rows;
  }
  function plotComparisonNote(rows) {
    const changed=rows[1] && (!same(rows[0].run.review.verification_sources,rows[1].run.review.verification_sources) || !same(rows[0].run.review.adapter_versions,rows[1].run.review.adapter_versions));
    return changed?'<p class="sd-plot-note">Verification sources or adapter versions changed between these runs. A result difference cannot be attributed to design edits alone.</p>':'';
  }
  function chart(requirementId) {
    const rows=plotRows(requirementId);if(!rows.length)return '';
    const unit=rows[0].finding.evidence.metric.unit;
    const values=[0,...rows.flatMap(row=>[row.finding.evidence.metric.value,row.finding.evidence.limit.value])];
    // Normalize before subtracting, so finite values near numeric extremes cannot
    // overflow the SVG axis. Each requirement keeps its own scale and unit.
    const magnitude=Math.max(...values.map(Math.abs)) || 1;
    const min=Math.min(...values.map(value=>value/magnitude));
    const max=Math.max(...values.map(value=>value/magnitude));
    const pad=(max-min || 1)*.12;
    const x=value=>120+(value/magnitude-min+pad)/(max-min+2*pad)*300;
    const height=rows.length*46+42;
    const low=Math.min(...values),high=Math.max(...values);
    const ticks=low===high?'<text x="'+x(low)+'" y="'+(height-7)+'" text-anchor="middle" class="sd-plot-axis">'+esc(num(low))+' '+esc(unit)+'</text>':'<text x="'+x(low)+'" y="'+(height-7)+'" text-anchor="middle" class="sd-plot-axis">'+esc(num(low))+'</text><text x="'+x(high)+'" y="'+(height-7)+'" text-anchor="middle" class="sd-plot-axis">'+esc(num(high))+' '+esc(unit)+'</text>';
    const description=rows.map(row=>row.label+': result '+String(row.finding.evidence.metric.value)+' '+unit+', criterion '+row.finding.evidence.operator+' '+String(row.finding.evidence.limit.value)+' '+unit+', '+human(findingStatus(row.finding))).join('. ');
    return '<div class="sd-mini-chart"><svg viewBox="0 0 460 '+height+'" role="img" aria-label="'+esc(description)+'"><title>'+esc(human(rows[0].finding.metric)+' ('+unit+')')+'</title>'+rows.map((row,i)=>{
      const y=26+i*46,e=row.finding.evidence;
      return '<text x="5" y="'+(y+4)+'" class="sd-plot-axis">'+esc(row.label)+'</text><line x1="120" x2="420" y1="'+y+'" y2="'+y+'" class="sd-plot-track"/><line x1="'+x(0)+'" x2="'+x(0)+'" y1="'+(y-5)+'" y2="'+(y+5)+'" class="sd-plot-zero"/><line x1="'+x(e.limit.value)+'" x2="'+x(e.limit.value)+'" y1="'+(y-12)+'" y2="'+(y+12)+'" class="sd-plot-limit"/><circle cx="'+x(e.metric.value)+'" cy="'+y+'" r="5" class="sd-plot-result '+(findingStatus(row.finding)==='met'?'sd-plot-met':'sd-plot-exceeded')+'"/>';
    }).join('')+ticks+'</svg><div class="sd-plot-records">'+rows.map(plotRecord).join('')+'</div>'+plotComparisonNote(rows)+'</div>';
  }
  function engineeringPlots(requirements) {
    const heading='<section class="sd-engineering-plots" aria-label="Engineering result plots"><h3>Results against limits</h3>';
    if(state.draft || !currentRun() || currentRun().stale)
      return heading+'<div class="sd-notice">'+(state.draft?'Save the draft and run affected checks to plot its results.':'Run checks for this saved revision to plot its results.')+' Earlier evidence remains in the revision history.</div></section>';
    const plotted=requirements.filter(r=>plotRows(r.id).length);
    const unplotted=requirements.filter(r=>!plotRows(r.id).length);
    return heading+'<p class="sd-plot-intro">Saved calculation results, with each revision’s own limit. Each chart has its own scale and unit. These charts compare saved scalar results. Orbital time histories are available through View trajectory.</p><div class="sd-plot-legend"><span><i class="sd-plot-dot" aria-hidden="true"></i>Calculated result</span><span><i class="sd-plot-tick" aria-hidden="true"></i>Declared limit</span></div>'+(plotted.length?'<div class="sd-plot-grid">'+plotted.map(r=>{
      const rows=plotRows(r.id),f=rows[0].finding;
      const incompatible=priorFinding(r.id) && !rows[1];
      return '<section class="sd-result-plot" data-requirement="'+esc(r.id)+'" aria-label="'+esc(r.title)+' result plot"><div class="sd-plot-heading"><h4>'+esc(r.title)+'</h4>'+selectionButton('requirement',r.id,'Inspect evidence','sd-mini-action')+'</div><p class="sd-small sd-muted">'+esc(human(f.metric))+' · '+esc(human(f.model_id))+'</p>'+chart(r.id)+(incompatible?'<p class="sd-plot-note">Earlier evidence has no comparable result for this model, metric and unit.</p>':'')+'<details class="sd-plot-sources"><summary>Recorded sources and full values</summary>'+rows.map(row=>'<p class="sd-receipt">'+esc(row.label)+' · Saved result '+plotMeasure(row.finding.evidence.metric,true)+'<br>Limit '+esc(row.finding.evidence.operator)+' '+plotMeasure(row.finding.evidence.limit,true)+'<br>Run '+esc(row.run.run_id)+'<br>Review '+esc(row.run.review.digest)+'</p>').join('')+'</details></section>';
    }).join('')+'</div>':'<p>No requirements in this view have comparable numeric result and limit evidence.</p>')+(unplotted.length?'<div class="sd-unplotted"><h4>Without numeric plot evidence</h4><p class="sd-small sd-muted">These requirements remain listed separately; missing evidence is not a passing result.</p>'+unplotted.map(r=>'<div>'+selectionButton('requirement',r.id,r.title,'sd-mini-action')+chip(reqStatus(r.id))+'<p>'+esc(finding(r.id)?.reason || 'No recorded numeric result and matching limit are available.')+'</p></div>').join('')+'</div>':'')+'</section>';
  }
  function receiptInfo() {
    const run=currentRun();
    if(!run)return '<div class="sd-notice">'+(priorRun()?'Previous evidence is preserved from R'+priorRun().revision+'. It does not constitute a review of this saved revision.':'This project has no calculated evidence yet.')+' Run checks to produce a review for R'+state.data.revision+'.</div>';
    return '<div class="sd-run-summary">Recorded '+esc(new Date(run.created_at).toLocaleString())+' · '+run.executed_model_ids.length+' model adapters executed · '+run.reused_model_ids.length+' results reused after dependency verification.<br>AI calls: 0 · Maintained deterministic adapters.<br><span class="sd-receipt">Run '+esc(run.run_id)+'</span></div>';
  }
  function readerFindings(requirements){
    return requirements.map(r=>{
      const f=finding(r.id),status=reqStatus(r.id),title=window.SixDSourceTargets?.shortLabel({label:r.title,target_id:'requirement:'+r.id})||r.title;
      const meaning=status==='met'?'The saved calculation is within your stated limit.':status==='not_met'?'The saved calculation is outside your stated limit.':status==='not_assessed'?'The available model and evidence do not decide this check.':'Calculate the saved revision before assessing this check.';
      const values=f?.evidence?'<p><strong>Calculated:</strong> '+measure(f.evidence.metric)+' · <strong>Criterion:</strong> '+esc(r.operator)+' '+measure(f.evidence.limit)+'</p>':'';
      return disclosure('result:'+r.id+':'+(currentRun()?.run_id||'unrun'),title,'<p>'+esc(meaning)+'</p><p>'+esc(f?.reason||'No current calculation reason is available.')+'</p>'+values+'<p class="sd-small sd-muted">'+esc(r.title)+' · '+esc(r.id)+'</p>'+disclosure('result-graph:'+r.id,'View comparison graph',chart(r.id))+modelContext(r.model_id,true),{className:'sd-context-disclosure sd-result-disclosure',summary:chip(status)});
    }).join('');
  }
  function reader(report=false) {
    const requirements=report?allReqs():selectedReqs(),models=report?allModels():selectedModels(),p=project();
    const counts={met:0,not_met:0,not_assessed:0};requirements.forEach(r=>{const status=reqStatus(r.id);if(Object.hasOwn(counts,status))counts[status]++;});
    const conclusion=state.draft?'Draft changes have not been calculated.':!currentRun()||currentRun().stale?'This revision needs current calculations.':counts.not_met?counts.not_met+' checks miss their stated limits.':counts.not_assessed?counts.met+' checks meet their criteria; '+counts.not_assessed+' need more evidence.':'The calculated checks meet their stated criteria.';
    const id=currentRun()?.run_id||'unrun';
    const traces=models.filter(m=>result(m.id)?.simulation).map(m=>'<h3>'+esc(human(m.id))+' trajectory evidence</h3>'+trajectoryContext(m.id)).join('');
    const modelsMarkup=models.map(m=>{const r=result(m.id);return '<details class="sd-source"><summary>'+esc(human(m.id))+' · '+(r?esc(human(r.status)):'Not run')+'</summary>'+modelEvidence(m.id)+powerEvidence(m.id)+attitudeEvidence(m.id)+flightEvidence(m.id)+'</details>';}).join('');
    const supplemental=interfaceSlot('report',report?null:models.map(m=>m.id))+sourceSlot('report',report?null:requirements.map(r=>r.id),report?null:models.map(m=>m.id))+actionSlot('report',report?null:requirements.map(r=>r.id),report?null:models.map(m=>m.id))+testEvidenceSlot('report',report?null:requirements.map(r=>r.id))+(report?coverageSlot()+seriesSlot()+envelopeSlot():'');
    const scope='<ul class="sd-scope-list">'+(currentRun()?.review?.exclusions||['Only explicitly bound models and supplied requirements can be assessed.','Physical tests, operational performance and whole-mission readiness are not verified.']).map(item=>'<li>'+esc(item)+'</li>').join('')+'</ul>';
    return '<article class="sd-reader"><span class="sd-label">'+(report?'Saved project · engineering review':esc(p.lifecycle_stage)+' · system reader')+'</span><h2>'+esc(report?p.name:activeSystem()?.title||p.name)+'</h2><section class="rw-verdict" aria-label="Report conclusion"><strong>'+esc(conclusion)+'</strong><p class="sd-accuracy-warning">Results apply to the declared calculations and criteria, not a complete mission assessment.</p></section>'+(state.draft?'<div class="sd-notice">Displayed evidence belongs to saved R'+state.data.revision+'; unsaved values are not calculated findings.</div>':'')+stats(requirements)+'<h3>Requirement findings</h3><p class="sd-small sd-muted">Scan the result, then open a requirement for its reason and exact evidence.</p>'+readerFindings(requirements)+disclosure('report-table:'+id,'View full numerical table',requirementTable(requirements))+
      disclosure('report-graphs:'+id,'View graphs and trajectory comparisons',engineeringPlots(requirements)+traces)+
      disclosure('report-models:'+id,'Calculation methods and evidence',modelsMarkup,{summary:models.length+' configured models'})+
      disclosure('report-support:'+id,'References, tests and follow-up',supplemental)+
      disclosure('report-scope:'+id,'Scope, assumptions and exclusions',scope)+
      disclosure('report-context:'+id,'Project context and receipt identity',projectDescription()+receiptInfo()+(currentRun()?'<p class="sd-receipt">Review '+esc(currentRun().review.digest)+'</p>'+Object.entries(currentRun().review.verification_sources||{}).map(([file,digest])=>'<p class="sd-receipt">'+esc(file)+': '+esc(digest)+'</p>').join(''):''))+
      '<div class="sd-action-row">'+(report?'<button type="button" class="sd-button sd-primary" data-action="export" '+(!currentRun()||currentRun().stale||state.draft?'disabled':'')+'>'+icon('download')+'Export evidence JSON</button><button type="button" class="sd-button" data-action="export-review" disabled>Export combined review JSON</button><button type="button" class="sd-button" data-action="print-report" '+(!currentRun()||currentRun().stale||state.draft?'disabled':'')+'>'+icon('printer')+'Print report / Save PDF</button>':'<button type="button" class="sd-button" data-action="report">Open full report</button>')+'<button type="button" class="sd-button" data-action="export-project">Export project JSON</button></div></article>';
  }
  function changeRecords() {
    const before=state.draft?state.data.project:priorRun()?.review?.project || state.data.configuration_base?.project;
    if(!before)return [];
    const after=project();const rows=[];
    for(const id of new Set([...Object.keys(before.inputs),...Object.keys(after.inputs)])){
      if(!same(before.inputs[id],after.inputs[id]))rows.push({title:human(id),before:before.inputs[id],after:after.inputs[id]});
    }
    return rows;
  }
  function structuralChanges(info) {
    const before=state.draft?state.data.project:priorRun()?.review?.project || state.data.configuration_base?.project,after=project(),groups=[];
    for(const [key,label] of [['models','model'],['requirements','requirement']]){
      const added=before?after[key].filter(item=>!before[key].some(old=>old.id===item.id)).map(item=>item.id):(info['added_'+key] || []);
      const removed=before?before[key].filter(item=>!after[key].some(now=>now.id===item.id)).map(item=>item.id):(info['removed_'+key] || []);
      const edited=before?after[key].filter(item=>before[key].some(old=>old.id===item.id&&!same(old,item))).map(item=>item.id):info['changed_'+key] || [];
      for(const [verb,ids] of [['Added',added],['Removed',removed],['Edited',edited]])if(ids.length)groups.push('<p><strong>'+verb+' '+label+(ids.length===1?'':'s')+':</strong> '+ids.map(esc).join(', ')+'</p>');
    }
    const metadata=before&&['name','description','lifecycle_stage'].filter(key=>!same(before[key],after[key]));
    if(metadata?.length)groups.push('<p><strong>Project details changed:</strong> '+metadata.map(key=>esc(human(key))).join(', ')+'</p>');
    return groups.length?'<section class="sd-change-card" aria-label="Definition changes"><h3>Definition changes</h3>'+groups.join('')+'<p class="sd-small sd-muted">Removed records do not erase earlier saved evidence. Earlier reviews retain their original configuration and scope.</p></section>':'';
  }
  function changes() {
    const rows=changeRecords(),info=impact();
    return '<article class="sd-reader"><span class="sd-label">'+(state.draft?'R'+state.data.revision+' → draft':'Revision R'+state.data.revision)+'</span><h2>Review the difference.</h2><p class="sd-lead">A changed input identifies dependencies needing review. New calculation outcomes appear only after checks run.</p>'+(!state.draft&&priorRun()?'<p class="sd-table-note">Compared with the nearest earlier recorded review: R'+priorRun().revision+'.</p>':!state.draft&&state.data.configuration_base?'<p class="sd-table-note">Compared with saved configuration R'+state.data.configuration_base.revision+'. This comparison describes supplied record changes only.</p>':'')+structuralChanges(info)+(rows.length?rows.map(row=>'<div class="sd-change-card"><strong>'+esc(row.title)+'</strong><div class="sd-change-values"><span class="sd-before">'+measure(row.before)+'</span><span>→</span><span class="sd-after">'+measure(row.after)+'</span></div>'+(row.before?.unit!==row.after?.unit?'<p class="sd-small sd-muted">Unit changed; no implicit conversion.</p>':'')+(!same(row.before?.source,row.after?.source)?'<p class="sd-small sd-muted">Source: '+esc(row.before?.source || '—')+' → '+esc(row.after?.source || '—')+'</p>':'')+'</div>').join(''):'<div class="sd-notice">No changed input records in this comparison. '+(!state.draft?'Create a draft from the latest revision to review a new change.':'Edit any input value, unit or source.')+'</div>')+interfaceSlot('changes')+sourceSlot('changes')+actionSlot('changes')+testEvidenceSlot('changes',[])+'<h3>Calculator dependency impact</h3><p>'+(state.draft?(state.impact?'Server-checked draft preview.':'Local draft preview; use Preview impact to validate with the server.'):'Saved revision dependency comparison.')+'</p><div class="sd-affected-list">'+(info.affected_model_ids||[]).map(id=>'<button type="button" data-kind="model" data-id="'+esc(id)+'">'+esc(human(id))+'<span class="sd-chip sd-pending">Model dependency</span></button>').join('')+(info.affected_requirement_ids||[]).map(id=>'<button type="button" data-kind="requirement" data-id="'+esc(id)+'">'+esc(req(id)?.title || id)+chip(reqStatus(id))+'</button>').join('')+'</div>'+(!(info.affected_requirement_ids||[]).length?'<p>No calculator requirement dependencies are affected by the supplied edits. Interface review flags are shown separately above.</p>':'')+receiptInfo()+'<div class="sd-action-row">'+(state.draft?'<button type="button" class="sd-button sd-primary" data-action="save" '+(!dirty()||editErrors().length?'disabled':'')+'>Save revision</button>':!currentRun()?'<button type="button" class="sd-button sd-primary" data-action="run">Rerun affected checks</button>':'<button type="button" class="sd-button" data-action="report">Open revised report</button>')+'<button type="button" class="sd-button sd-quiet" data-action="back">Return to system</button></div></article>';
  }
  function renderMain() {
    rememberDisclosures();
    if(state.page==='review-home')delete $('#sd-view-content').dataset.shellTitle;
    else $('#sd-view-content').dataset.shellTitle='true';
    window.SixDOwnerSettings?.unmount();
    if(state.hosted&&['owner-settings','ai-quality'].includes(state.page)){
      unmountWorkspaceViews();$('#sd-view-content').innerHTML='<article class="sd-reader"><h2>Owner settings are unavailable here.</h2><p>This is an isolated reviewer workspace. Its owner manages connections, usage and diagnostics.</p><button class="sd-button" data-action="review-home">Return to overview</button></article>';return;
    }
    if(state.page==='owner-settings'){
      unmountWorkspaceViews();$('#sd-view-content').innerHTML='<div id="sd-owner-host"></div>';
      window.SixDOwnerSettings.mount($('#sd-owner-host'),{api,records:ai.records,onNebius:()=>void action('manage-nebius'),onTavily:()=>void action('manage-tavily'),onNavigate:name=>void action(name)});return;
    }
    if(window.SixDWorkspaceShell.hubs.has(state.page)){
      unmountWorkspaceViews();
      $('#sd-view-content').innerHTML=window.SixDWorkspaceShell.hub(state.page,state.projects,state.data.project_id,
        window.SixDWorkspaceShell.toolSummary(state.data,{hasDraft:!!state.draft}));
      return;
    }
    window.SixDGuidedAscent?.unmount();window.SixDStagedAscent?.unmount();
    window.SixDAIQuality?.unmount();
    if(state.page==='ai-quality'){
      window.SixDReviewWorkspace?.unmount();window.SixDEnvelopes?.unmount();window.SixDSimulationImports?.unmount();window.SixDPoweredFlight?.unmount();window.SixDSimulation?.unmount();window.SixDTestData?.unmount();window.SixDScenarios?.unmount();
      coverageLinks.dispose?.();coverageLinks.dispose=null;comparisonView.dispose?.();comparisonView.dispose=null;researchView.dispose?.();researchView.dispose=null;actionLinks.dispose?.();actionLinks.dispose=null;sourceLinks.dispose?.();sourceLinks.dispose=null;
      window.SixDActions?.unmount();window.SixDSources?.unmount();window.SixDChains?.unmount();window.SixDAttitude?.unmount();window.SixDPowerBudget?.unmount();window.SixDSystems?.unmount();
      $('#sd-view-content').innerHTML='<div id="sd-ai-quality"></div>';
      window.SixDAIQuality.mount($('#sd-ai-quality'),{api,onSources:()=>void action('sources')});return;
    }
    window.SixDReviewWorkspace?.unmount();
    if(state.page==='review-home'){
      window.SixDEnvelopes?.unmount();window.SixDSimulationImports?.unmount();window.SixDPoweredFlight?.unmount();window.SixDSimulation?.unmount();window.SixDTestData?.unmount();window.SixDScenarios?.unmount();
      coverageLinks.dispose?.();coverageLinks.dispose=null;comparisonView.dispose?.();comparisonView.dispose=null;researchView.dispose?.();researchView.dispose=null;actionLinks.dispose?.();actionLinks.dispose=null;sourceLinks.dispose?.();sourceLinks.dispose=null;
      window.SixDActions?.unmount();window.SixDSources?.unmount();window.SixDChains?.unmount();window.SixDAttitude?.unmount();window.SixDPowerBudget?.unmount();window.SixDSystems?.unmount();
      const projectId=state.data.project_id,revision=state.data.revision,runId=currentRun()?.run_id||null,draftKey=JSON.stringify(state.draft);
      const current=()=>state.data?.project_id===projectId&&state.data?.revision===revision&&(currentRun()?.run_id||null)===runId&&JSON.stringify(state.draft)===draftKey;
      $('#sd-view-content').innerHTML='<div id="sd-review-workspace"></div>';
      window.SixDReviewWorkspace.mount($('#sd-review-workspace'),{projectId,revision,currentRunId:runId,hasDraft:!!state.draft,api,
        onNavigate:name=>{if(current())void action(name);},
        onRocketOpen:()=>{if(current()&&!state.draft)void action('rocket-reference');},
        onRocketStage:()=>{if(current()&&!state.draft)void action('rocket-stage');},
        thrustInputs:thrustInputs(),onEditThrust:latest()?()=>{if(current())openThrustEditor();}:undefined,
        onSelectRequirement:id=>{if(!current()||state.draft||!req(id))return;state.page='system';state.view='reader';state.system=owningSystem(req(id).model_id)?.id||'overview';state.panel='evidence';select('requirement',id,false);},
        onRun:latest()&&!state.draft?()=>{if(current())return action('run');}:undefined,
        onReload:()=>{if(current())void perform(()=>load(projectId,revision));}
      });return;
    }
    window.SixDEnvelopes?.unmount();
    if(state.page==='envelopes'){
      window.SixDSimulationImports?.unmount();window.SixDPoweredFlight?.unmount();window.SixDSimulation?.unmount();window.SixDTestData?.unmount();window.SixDScenarios?.unmount();
      coverageLinks.dispose?.();coverageLinks.dispose=null;comparisonView.dispose?.();comparisonView.dispose=null;researchView.dispose?.();researchView.dispose=null;actionLinks.dispose?.();actionLinks.dispose=null;sourceLinks.dispose?.();sourceLinks.dispose=null;
      window.SixDActions?.unmount();window.SixDSources?.unmount();window.SixDChains?.unmount();window.SixDAttitude?.unmount();window.SixDPowerBudget?.unmount();window.SixDSystems?.unmount();
      $('#sd-view-content').innerHTML='<div id="sd-envelopes"></div>';
      window.SixDEnvelopes.mount($('#sd-envelopes'),{projectId:state.data.project_id,revision:state.data.revision,project:state.data.project,hasDraft:!!state.draft,canEdit:state.data.revision===state.data.latest_revision,currentRunId:currentRun()?.run_id,api,onRun:()=>void action('run'),onReload:()=>void perform(()=>load(state.data.project_id,state.data.revision)),onSaved:()=>{envelopeLinks.key='';}});return;
    }
    window.SixDSimulationImports?.unmount();
    if(state.page==='simulation-imports'){
      window.SixDPoweredFlight?.unmount();window.SixDSimulation?.unmount();window.SixDTestData?.unmount();window.SixDScenarios?.unmount();
      coverageLinks.dispose?.();coverageLinks.dispose=null;comparisonView.dispose?.();comparisonView.dispose=null;researchView.dispose?.();researchView.dispose=null;
      window.SixDActions?.unmount();window.SixDSources?.unmount();window.SixDChains?.unmount();window.SixDAttitude?.unmount();window.SixDPowerBudget?.unmount();window.SixDSystems?.unmount();
      $('#sd-view-content').innerHTML='<div id="sd-simulation-imports"></div>';
      window.SixDSimulationImports.mount($('#sd-simulation-imports'),{projectId:state.data.project_id,revision:state.data.revision,project:state.data.project,hasDraft:!!state.draft,canEdit:state.data.revision===state.data.latest_revision,staleServer:!!ai.status?.restart_required,currentRunId:currentRun()?.run_id,api,onRun:()=>void action('run'),onReload:()=>void perform(()=>load(state.data.project_id,state.data.revision)),onSaved:()=>{seriesLinks.key='';}});
      return;
    }
    window.SixDPoweredFlight?.unmount();
    coverageLinks.dispose?.();coverageLinks.dispose=null;
    if(state.page==='coverage'){
      researchView.dispose?.();researchView.dispose=null;comparisonView.dispose?.();comparisonView.dispose=null;actionLinks.dispose?.();actionLinks.dispose=null;
      window.SixDActions?.unmount();window.SixDSources?.unmount();window.SixDChains?.unmount();window.SixDAttitude?.unmount();window.SixDPowerBudget?.unmount();window.SixDSystems?.unmount();window.SixDSimulation?.unmount();window.SixDScenarios?.unmount();window.SixDTestData?.unmount();
      $('#sd-view-content').innerHTML='<div id="sd-engineering-coverage"></div>';
      const projectId=state.data.project_id,revision=state.data.revision;
      coverageLinks.key='';
      coverageLinks.dispose=window.SixDCoverage.mount($('#sd-engineering-coverage'),{api,projectId,revision,draft:!!state.draft,onOpenRequirement:id=>{
        if(state.data?.project_id!==projectId||state.data?.revision!==revision||!req(id))return;
        state.page='system';state.system='overview';state.view='table';select('requirement',id,false);
      }});return;
    }
    researchView.dispose?.();researchView.dispose=null;
    comparisonView.dispose?.();comparisonView.dispose=null;
    if(state.page==='comparison'){
      window.SixDActions?.unmount();window.SixDSources?.unmount();window.SixDChains?.unmount();window.SixDAttitude?.unmount();window.SixDPowerBudget?.unmount();window.SixDSystems?.unmount();window.SixDSimulation?.unmount();window.SixDScenarios?.unmount();window.SixDTestData?.unmount();
      $('#sd-view-content').innerHTML='<div id="sd-design-comparison"></div>';
      const projectId=state.data.project_id,revision=state.data.revision;
      const current=()=>state.data?.project_id===projectId&&state.data?.revision===revision;
      comparisonView.dispose=window.SixDComparison.mount($('#sd-design-comparison'),{api,projectId,revision,hasDraft:!!state.draft,
        compareRaw:(body,options)=>api('/api/design-comparison',body,{...options,raw:true}),
        onScenarios:()=>{if(current())void action('scenarios');},
        onRun:()=>{if(!current())return;state.page='system';state.view='table';render();message('Use Run checks on the saved project to create a new recorded result. Draft changes remain separate.');}
      });return;
    }
    actionLinks.dispose?.();actionLinks.dispose=null;
    if(state.page==='actions'){
      window.SixDSources?.unmount();window.SixDChains?.unmount();window.SixDAttitude?.unmount();window.SixDPowerBudget?.unmount();window.SixDSystems?.unmount();window.SixDSimulation?.unmount();window.SixDScenarios?.unmount();window.SixDTestData?.unmount();
      $('#sd-view-content').innerHTML='<div id="sd-action-queue"></div>';
      const projectId=state.data.project_id,revision=state.data.revision,originId=actionLinks.originId;actionLinks.originId=null;
      actionLinks.dispose=window.SixDActions.mount($('#sd-action-queue'),{api,projectId,revision,hasDraft:!!state.draft,canEdit:latest(),originId,onChange:profile=>{
        if(state.data?.project_id!==projectId||state.data?.revision!==revision)return;
        actionLinks.serial++;actionLinks.controller?.abort();actionLinks.pending='';actionLinks.profile=profile;actionLinks.key=actionLinkKey();actionLinks.error='';hydrateActionLinks();
      }});return;
    }
    sourceLinks.dispose?.();sourceLinks.dispose=null;
    if(state.page==='sources'){
      window.SixDChains?.unmount();window.SixDAttitude?.unmount();window.SixDPowerBudget?.unmount();window.SixDSystems?.unmount();window.SixDSimulation?.unmount();window.SixDScenarios?.unmount();window.SixDTestData?.unmount();
      $('#sd-view-content').innerHTML='<div id="sd-source-library"></div>';
      const projectId=state.data.project_id,revision=state.data.revision,runId=currentRun()?.run_id||null,mountKey=sourceLinkKey();
      sourceLinks.dispose=window.SixDSources.mount($('#sd-source-library'),{api,projectId,revision,runId,hasDraft:!!state.draft,canEdit:latest(),onChange:profile=>{
        if(mountKey!==sourceLinkKey()||profile.project_id!==projectId||profile.revision!==revision||profile.context!=='saved'||profile.run_id!==runId)return;
        sourceLinks.serial++;sourceLinks.controller?.abort();sourceLinks.pending='';sourceLinks.profile=profile;sourceLinks.key=mountKey;sourceLinks.error='';hydrateSourceLinks();renderAssistantContextSummary();renderAiHistory();void refreshActionLinks(true);
      },onAskLinkedReference:selection=>askLinkedReference(selection,mountKey)});
      return;
    }
    window.SixDChains?.unmount();
    if(state.page==='chains'){
      window.SixDAttitude?.unmount();window.SixDPowerBudget?.unmount();window.SixDSystems?.unmount();window.SixDSimulation?.unmount();window.SixDScenarios?.unmount();window.SixDTestData?.unmount();
      $('#sd-view-content').innerHTML='<div id="sd-chains"></div>';
      const projectId=state.data.project_id,revision=state.data.revision,draft=state.draft;
      const current=()=>state.data?.project_id===projectId&&state.data?.revision===revision&&state.draft===draft;
      window.SixDChains.mount($('#sd-chains'),{projectId,revision,project:project(),catalog:author.catalog,hasDraft:!!draft,isLatest:latest(),stale:!!currentRun()?.stale,results:state.draft?{}:currentRun()?.model_results||{},runId:currentRun()?.run_id,
        onReference:()=>{if(current()&&!draft)void showImport('chain_review');},
        onEdit:()=>{if(current()&&beginDraft()){state.page='chains';render();}},
        onChange:async candidate=>{
          if(!current()||!draft)throw Error('This calculation-link draft changed. Reopen Calculation chains.');
          const submitted=JSON.stringify(draft),validation=await api('/api/authoring/preflight',{project:candidate});
          if(!current()||JSON.stringify(state.draft)!==submitted)throw Error('The draft changed while validating this link. Your newer edits are preserved.');
          const error=validation.issues.find(i=>i.severity==='error'&&i.code==='invalid_project');if(error)throw Error(error.message);
          state.draft=copy(candidate);draftChanged();
        },onSave:()=>{if(current())void action('save');},onRun:()=>{if(current()&&!draft)void action('run');},onReport:()=>{if(current())void action('report');},
        onInspect:id=>{if(current()&&model(id)){state.system=owningSystem(id)?.id||'overview';state.selected={kind:'model',id};state.page='system';state.panel='evidence';render();}}
      });return;
    }
    window.SixDAttitude?.unmount();
    window.SixDPowerBudget?.unmount();
    window.SixDSystems?.unmount();
    window.SixDSimulation?.unmount();
    window.SixDScenarios?.unmount();
    window.SixDTestData?.unmount();
    if(['powered-flight','guided-ascent','staged-ascent'].includes(state.page)){
      const guided=state.page==='guided-ascent',staged=state.page==='staged-ascent';
      const hostId=staged?'sd-staged-ascent':guided?'sd-guided-ascent':'sd-powered-flight';
      $('#sd-view-content').innerHTML='<div class="sd-flight-modes" role="group" aria-label="Flight model mode"><button type="button" class="sd-button" data-action="vertical-mode" aria-pressed="'+(!guided&&!staged)+'">Vertical ascent</button><button type="button" class="sd-button" data-action="guided-ascent" aria-pressed="'+guided+'">Planar ascent & steering</button><button type="button" class="sd-button" data-action="staged-ascent" aria-pressed="'+staged+'">Variable thrust & staging</button></div><div id="'+hostId+'"></div>';
      const projectId=state.data.project_id,revision=state.data.revision,draft=state.draft,runId=currentRun()?.run_id;
      const current=()=>state.data?.project_id===projectId&&state.data?.revision===revision&&state.draft===draft;
      (staged?window.SixDStagedAscent:guided?window.SixDGuidedAscent:window.SixDPoweredFlight).mount($('#'+hostId),{projectId,revision,isLatest:latest(),initialModelId:state.stagedProfileEdit,editProfile:staged&&!!state.stagedProfileEdit,project:project(),hasDraft:!!draft,runId,reviewDigest:currentRun()?.review?.digest,modelResults:Object.fromEntries(allModels().map(m=>[m.id,powerResult(m.id)])),modelOrigins:currentRun()?.model_origins||{},findings:currentRun()?.review?.findings||{},
        onReference:()=>{if(current()&&!draft)void showImport(staged?'staged_ascent_review':guided?'guided_ascent_review':'powered_flight_review');},
        onEditProfile:id=>{if(!current()||!latest()||!model(id)||!beginDraft())return;state.stagedProfileEdit=id;state.page='staged-ascent';render();},
        onCloseProfile:()=>{if(current())state.stagedProfileEdit=null;},
        onProfileChange:async candidate=>{
          if(!current()||!draft)throw Error('This stage-profile draft changed. Reopen the current saved project.');
          const submitted=JSON.stringify(draft),validation=await api('/api/authoring/preflight',{project:candidate});
          if(!current()||JSON.stringify(state.draft)!==submitted)throw Error('The shared draft changed during profile validation. Newer edits are preserved.');
          const error=validation.issues.find(item=>item.severity==='error');if(error)throw Error(error.message);
          state.draft=copy(candidate);state.impact=null;state.stagedProfileEdit=null;invalidatePreflight();render();message('Stage profile applied to the shared draft. Preview, save and rerun before using a new result.');
        },
        onPreview:()=>{if(current()&&draft)void action('impact');},onSave:()=>{if(current()&&draft)void action('save');},
        onAuthor:()=>{if(current())void action('author-project');},onRun:()=>{if(current()&&!draft)void action('run');},onReport:()=>{if(current())void action('report');},
        onInputs:id=>{if(!current()||!model(id))return;state.system=owningSystem(id)?.id||'overview';state.selected={kind:'model',id};state.page='system';state.view='table';state.panel='details';render();},
        onRequirement:(id,assistant)=>{if(!current()||!req(id)||assistant&&(draft||runId!==currentRun()?.run_id))return;state.system=owningSystem(req(id).model_id)?.id||'overview';state.page='system';state.view='reader';state.panel=assistant?'assistant':'evidence';select('requirement',id,assistant);}
      });return;
    }
    if(state.page==='attitude'){
      $('#sd-view-content').innerHTML='<div id="sd-attitude"></div>';
      const projectId=state.data.project_id,revision=state.data.revision,draft=state.draft,runId=currentRun()?.run_id;
      const current=()=>state.data?.project_id===projectId&&state.data?.revision===revision&&state.draft===draft;
      window.SixDAttitude.mount($('#sd-attitude'),{projectId,revision,project:project(),hasDraft:!!draft,runId,reviewDigest:currentRun()?.review?.digest,modelResults:Object.fromEntries(allModels().map(m=>[m.id,powerResult(m.id)])),modelOrigins:currentRun()?.model_origins||{},findings:currentRun()?.review?.findings||{},
        onReference:()=>{if(current()&&!draft)void showImport('attitude_review');},
        onAuthor:()=>{if(current())void action('author-project');},onRun:()=>{if(current()&&!draft)void action('run');},onReport:()=>{if(current())void action('report');},
        onInputs:id=>{if(!current()||!model(id))return;state.system=owningSystem(id)?.id||'overview';state.selected={kind:'model',id};state.page='system';state.view='table';state.panel='details';render();},
        onRequirement:(id,assistant)=>{if(!current()||!req(id)||assistant&&(draft||runId!==currentRun()?.run_id))return;state.system=owningSystem(req(id).model_id)?.id||'overview';state.page='system';state.view='reader';state.panel=assistant?'assistant':'evidence';select('requirement',id,assistant);}
      });return;
    }
    if(state.page==='power'){
      $('#sd-view-content').innerHTML='<div id="sd-power-budget"></div>';
      const projectId=state.data.project_id,revision=state.data.revision,draft=state.draft;
      const stillCurrent=()=>state.data?.project_id===projectId&&state.data?.revision===revision&&state.draft===draft;
      window.SixDPowerBudget.mount($('#sd-power-budget'),{projectId,revision,project:project(),hasDraft:!!draft,isLatest:latest(),currentRunId:currentRun()?.run_id,runId:currentRun()?.run_id,reviewDigest:currentRun()?.review?.digest,modelResults:Object.fromEntries(allModels().map(m=>[m.id,powerResult(m.id)])),modelOrigins:currentRun()?.model_origins||{},api,
        onEdit:()=>{if(stillCurrent()&&beginDraft()){state.page='power';render();}},
        onChange:async candidate=>{
          if(!stillCurrent()||!draft)throw Error('This power draft changed. Reopen Power & energy.');
          const submittedSnapshot=JSON.stringify(draft);
          for(const old of draft.models.filter(m=>m.type==='power_energy_budget'&&Object.keys(m.links||{}).length)){const next=candidate.models.find(m=>m.id===old.id);if(!next||JSON.stringify(next.links)!==JSON.stringify(old.links))throw Error('Edit or remove this model’s calculation links in Calculation chains before replacing its power profile.');}
          const validation=await api('/api/authoring/preflight',{project:candidate});
          if(!stillCurrent()||JSON.stringify(state.draft)!==submittedSnapshot)throw Error('The project or draft changed while applying this profile. Your newer edits are preserved.');
          const powerPaths=candidate.models.map((m,i)=>m.type==='power_energy_budget'?'project.models['+i+']':null).filter(Boolean);
          const error=validation.issues.find(issue=>issue.severity==='error'&&(issue.code==='invalid_project'||powerPaths.some(path=>issue.path.startsWith(path))));
          if(error)throw Error(error.message);
          state.draft=copy(candidate);draftChanged();
        },
        onSave:()=>{if(stillCurrent())void action('save');},onRun:()=>{if(stillCurrent())void action('run');},
        onAuthorInputs:()=>{if(stillCurrent())void action('author-project');},onAuthorRequirements:()=>{if(stillCurrent())void action('author-project');},
        onSelectModel:id=>{if(stillCurrent()&&model(id)){state.system=owningSystem(id)?.id||'overview';state.selected={kind:'model',id};state.page='system';state.panel='evidence';render();}},
        onReference:()=>{if(stillCurrent())void showImport('power_budget');}
      });return;
    }
    if(state.page==='systems'){
      $('#sd-view-content').innerHTML='<div id="sd-systems"></div>';
      const projectId=state.data.project_id,revision=state.data.revision,draft=state.draft;
      const stillCurrent=()=>state.data?.project_id===projectId&&state.data?.revision===revision&&state.draft===draft;
      window.SixDSystems.mount($('#sd-systems'),{projectId,revision,project:project(),hasDraft:!!draft,isLatest:latest(),api,
        onEdit:()=>{if(stillCurrent()&&beginDraft()){state.page='systems';render();}},
        onChange:async candidate=>{
          if(!stillCurrent()||!draft)throw Error('This draft changed. Reopen Systems & interfaces.');
          const submittedSnapshot=JSON.stringify(draft);
          const preview=await api('/api/interfaces/preview',{project_id:projectId,base_revision:revision,project:candidate});
          if(!stillCurrent()||JSON.stringify(state.draft)!==submittedSnapshot)throw Error('The project or draft changed before this edit was applied. Your newer edits are preserved; reopen the architecture editor.');
          state.draft=copy(candidate);interfaceLinks.profile=preview;interfaceLinks.key=testLinkKey();interfaceLinks.error='';draftChanged();
        },
        onSave:()=>{if(stillCurrent())void action('save');},onRun:()=>{if(stillCurrent())void action('run');},
        onSelectSystem:id=>{if(!stillCurrent())return;state.system='subsystem:'+id;state.page='system';state.selected=defaultSelection();render();}
      });return;
    }
    if(state.page==='test-data'){
      $('#sd-view-content').innerHTML='<div id="sd-test-data"></div>';
      window.SixDTestData.mount($('#sd-test-data'),{projectId:state.data.project_id,revision:state.data.revision,project:state.data.project,hasDraft:!!state.draft,currentRunId:currentRun()?.run_id,api,onRun:()=>void action('run'),onReload:()=>void perform(()=>load(state.data.project_id,state.data.revision)),onSaved:invalidateTestLinks,comparisonId:state.testEvidenceTarget?.projectId===state.data.project_id&&state.testEvidenceTarget?.revision===state.data.revision?state.testEvidenceTarget.comparisonId:null,rowNumber:state.testEvidenceTarget?.rowNumber});
      return;
    }
    if(state.page==='scenarios'){
      $('#sd-view-content').innerHTML='<div id="sd-scenarios"></div>';
      window.SixDScenarios.mount($('#sd-scenarios'),{projectId:state.data.project_id,revision:state.data.revision,project:state.data.project,hasDraft:!!state.draft,currentRunId:currentRun()?.run_id,api,onRun:()=>void action('run')});
      return;
    }
    if(state.page==='authoring'){$('#sd-view-content').innerHTML=authoring();return;}
    if(state.page==='simulation'){
      $('#sd-view-content').innerHTML='<div id="sd-simulation"></div>';
      const projectId=state.data.project_id,revision=state.data.revision;
      const stillSelected=()=>state.data?.project_id===projectId&&state.data?.revision===revision;
      window.SixDSimulation.mount($('#sd-simulation'),{projectId,revision,hasDraft:!!state.draft,api,
        modelId:state.trajectory?.modelId,workspaceRunId:state.trajectory?.runId,
        currentRunId:currentRun()?.run_id,canEdit:latest(),
        onReference:()=>{if(stillSelected())void showImport('orbital_review');},
        onInputs:modelId=>{if(!stillSelected())return;state.system=owningSystem(modelId)?.id||'overview';state.selected={kind:'model',id:modelId};state.page='system';state.view='table';state.panel='details';render();},
        onRun:modelId=>{if(!stillSelected())return;state.trajectory=modelId?{modelId,runId:currentRun()?.run_id}:null;void action('run');},
        onRequirement:(id,runId,assistant)=>{if(!stillSelected()||state.draft||runId!==currentRun()?.run_id||!req(id))return;state.page='system';state.view='reader';state.panel=assistant?'assistant':'evidence';select('requirement',id,assistant);}
      });
      return;
    }
    $('#sd-view-content').innerHTML=(state.page==='system'&&state.view!=='reader'?'<div class="sd-system-context">'+projectDescription()+'</div>':'')+(state.page==='report'?reader(true):state.page==='changes'?changes():state.view==='canvas'?canvas():state.view==='table'?table():reader());
    if(state.page==='system'&&state.view==='canvas'){applyCamera();bindPan();}
  }
  function trajectoryButton(modelId,run=currentRun(),label='View trajectory') {
    if(state.draft&&run===currentRun())return '';
    if(!run?.model_results?.[modelId]?.simulation)return '';
    return '<button type="button" class="sd-mini-action" data-trajectory-model="'+esc(modelId)+'" data-trajectory-run="'+esc(run.run_id)+'">'+icon('orbit')+esc(label)+'</button>';
  }
  function contextList(value) {
    if(!value)return '';
    const rows=Array.isArray(value)?value:[value];
    return '<ul class="sd-scope-list">'+rows.map(item=>'<li>'+esc(typeof item==='object'?JSON.stringify(item):item)+'</li>').join('')+'</ul>';
  }
  function applicabilityMarkup(applicability,context) {
    if(!applicability)return '<p class="sd-notice">Physical applicability has not been established. This record has no model-applicability reference context.</p>';
    return '<section class="sd-applicability"><h3>Model applicability and references</h3><p class="sd-small sd-muted">'+esc(context)+'</p><p class="sd-accuracy-warning">Physical applicability is not established by a completed calculation or a reference benchmark.</p><h4>Modeled scope</h4>'+contextList(applicability.scope)+'<h4>Enforced checks</h4>'+contextList(applicability.checks)+'<h4>Requires external evidence</h4>'+contextList(applicability.requires_external_evidence)+'<h4>Reference context</h4><p class="sd-small">These sources support model equations or bounded reference checks. They do not validate this project run, its supplied inputs or the real vehicle.</p><ul class="sd-reference-list">'+(applicability.references||[]).map(reference=>{
      const title=esc(reference.title||reference.url||'Reference'),url=reference.url||'',link=/^https?:\/\//i.test(url)?'<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">'+title+'</a>':title;
      return '<li>'+link+'<span class="sd-small">'+esc(human(reference.kind))+'</span>'+(reference.note?'<p>'+esc(reference.note)+'</p>':'')+'</li>';
    }).join('')+'</ul></section>';
  }
  function modelContext(modelId,includeAssumptions=false) {
    const m=model(modelId),r=result(modelId),catalog=catalogModel(m?.type),frozen=r?.applicability||(!state.draft?currentRun()?.review?.evidence?.[modelId]?.applicability:null),applicability=frozen||catalog?.applicability;
    return (includeAssumptions?'<h3>Model assumptions</h3>'+contextList(r?.assumptions||catalog?.assumptions||['No maintained model assumptions are available for this definition.']):'')+applicabilityMarkup(applicability,frozen?'Frozen applicability context recorded with this model result.':'Current model catalog context only; this was not recorded as proof for the displayed historical run or uncalculated definition.');
  }
  function accuracyMarkup(modelId,run=currentRun()) {
    if(state.draft&&run===currentRun())return '';
    const r=run?.model_results?.[modelId],accuracy=r?.numerical_accuracy;
    if(!accuracy)return historicalAccuracyNotice(modelId,run);
    const criteria=accuracy.criteria,orders=accuracy.observed_orders||{},status=accuracy.status==='supported'?'supported':accuracy.status==='insufficient_accuracy'?'insufficient_accuracy':'accuracy_not_assessed';
    return '<section class="sd-numerical-accuracy" aria-label="Orbital numerical accuracy"><h3>Orbital numerical accuracy</h3>'+chip(status)+'<p>'+esc(accuracy.reason)+'</p><p class="sd-small sd-accuracy-warning">This checks agreement between numerical grids at aligned saved samples. It is not a bound on true error, a continuous-time guarantee or physical validation.</p>'+(criteria?'<dl class="sd-details-grid"><dt>Declared position tolerance</dt><dd>'+esc(String(criteria.position_tolerance_m))+' m</dd><dt>Declared velocity tolerance</dt><dd>'+esc(String(criteria.velocity_tolerance_m_s))+' m/s</dd><dt>Criteria source</dt><dd>'+esc(criteria.source)+'</dd></dl>':'<p>No user-supplied position and velocity accuracy criteria were declared. No numerical accuracy pass is inferred.</p>')+'<div class="sd-table-wrap"><table class="sd-table sd-accuracy-table"><thead><tr><th>Grid steps</th><th>Aligned samples</th><th>Max position difference · m</th><th>Max velocity difference · m/s</th></tr></thead><tbody>'+(accuracy.comparisons||[]).map(row=>'<tr><td>'+esc(row.coarse_steps)+' → '+esc(row.fine_steps)+'</td><td>'+esc(row.aligned_sample_count)+'</td><td>'+esc(num(row.max_position_difference_m))+'</td><td>'+esc(num(row.max_velocity_difference_m_s))+'</td></tr>').join('')+'</tbody></table></div>'+(!accuracy.comparisons?.length?'<p class="sd-small">No aligned-grid comparison is recorded.</p>':'')+'<dl class="sd-details-grid"><dt>Observed position order</dt><dd>'+esc(Number.isFinite(orders.position)?num(orders.position):'Unresolved')+'</dd><dt>Observed velocity order</dt><dd>'+esc(Number.isFinite(orders.velocity)?num(orders.velocity):'Unresolved')+'</dd><dt>Accepted refinement order</dt><dd>'+esc(accuracy.method?.accepted_order_min)+'–'+esc(accuracy.method?.accepted_order_max)+'</dd></dl>'+(accuracy.reference_failure?'<p class="sd-accuracy-warning">Reference grid '+esc(accuracy.reference_failure.steps)+': '+esc(accuracy.reference_failure.message)+'</p>':'')+contextList(accuracy.limitations)+'</section>';
  }
  function declaredAccuracy(modelId) {
    const m=model(modelId);if(m?.type!=='orbital_trajectory')return '';
    const a=m.accuracy;
    return '<section class="sd-declared-accuracy"><h3>Declared orbital accuracy criteria</h3>'+(a?'<p>Position '+esc(String(a.position_tolerance_m))+' m · Velocity '+esc(String(a.velocity_tolerance_m_s))+' m/s</p><p class="sd-small">Source: '+esc(a.source)+'</p>':'<p class="sd-notice">No numerical accuracy criteria declared. Supply both tolerances and their source; blank values do not become defaults.</p>')+(state.draft?'<button type="button" class="sd-button" data-author-edit="model" data-id="'+esc(modelId)+'">Edit model and accuracy criteria</button>':'<p class="sd-small sd-muted">Choose Edit draft, then edit this model to declare or revise accuracy criteria.</p>')+'</section>';
  }
  function trajectoryContext(modelId,run=currentRun()) {
    if(state.draft&&run===currentRun())return '';
    const simulation=run?.model_results?.[modelId]?.simulation;if(!simulation)return '';
    return '<div class="sd-trajectory-context"><p class="sd-small">Recorded orbital trajectory · R'+run.revision+' · '+simulation.samples.length+' samples over '+esc(String(simulation.spec.duration_s))+' s. Minimum/maximum metrics cover saved samples only; final metrics use the last sample. They do not establish continuous-time bounds.</p><p class="sd-receipt">Run '+esc(run.run_id)+'<br>Review '+esc(run.review.digest)+'</p>'+accuracyMarkup(modelId,run)+trajectoryButton(modelId,run)+'</div>';
  }
  function modelEvidence(modelId) {
    if(state.draft)return '<p class="sd-notice">Draft model definitions have no calculated evidence. Save and run this configuration. Earlier evidence remains in the saved revision history.</p>'+declaredAccuracy(modelId)+modelContext(modelId,true);
    const r=result(modelId);
    if(!r){const old=priorRun()?.model_results?.[modelId];return '<p>No current result for this revision.</p>'+declaredAccuracy(modelId)+modelContext(modelId,true)+(old?'<p class="sd-notice">Previous R'+priorRun().revision+' evidence is preserved but has not been adopted as this revision’s review.</p>'+trajectoryButton(modelId,priorRun(),'View historical trajectory'):'');}
    const origin=currentRun()?.model_origins?.[modelId];
    return '<div style="margin-top:10px">'+chip(modelStatus(r))+'</div>'+(r.issues?.length?'<ul class="sd-scope-list">'+r.issues.map(item=>'<li>'+esc(item)+'</li>').join('')+'</ul>':'')+(Object.keys(r.metrics||{}).length?'<dl class="sd-details-grid">'+Object.entries(r.metrics).map(([name,value])=>'<dt>'+esc(human(name))+'</dt><dd>'+measure(value)+'</dd>').join('')+'</dl>':'')+declaredAccuracy(modelId)+trajectoryContext(modelId)+window.SixDChains.evidence(model(modelId),r,{hasDraft:!!state.draft,stale:!!currentRun()?.stale})+'<h3>Model assumptions</h3><ul class="sd-scope-list">'+(r.assumptions||[]).map(item=>'<li>'+esc(item)+'</li>').join('')+'</ul>'+modelContext(modelId)+'<h3>Not assessed</h3><ul class="sd-scope-list">'+(r.not_assessed||[]).map(item=>'<li>'+esc(item)+'</li>').join('')+'</ul>'+(origin?'<p class="sd-receipt">'+esc(human(origin.disposition))+' · source revision R'+origin.revision+'<br>Origin run '+esc(origin.run_id)+'</p>':'');
  }
  function powerResult(modelId){
    const saved=result(modelId),receipt=currentRun()?.review?.evidence?.[modelId];
    return saved?{...saved,inputs:receipt?.input_records,verification_sources:receipt?.verification_sources,evidence_fingerprint:receipt?.fingerprint}:null;
  }
  function flightEvidence(modelId){
    if(model(modelId)?.type==='staged_ascent')return window.SixDStagedAscent.report(powerResult(modelId),{projectId:state.data.project_id,revision:state.data.revision,modelId,runId:currentRun()?.run_id,reviewDigest:currentRun()?.review?.digest,hasDraft:!!state.draft,origin:currentRun()?.model_origins?.[modelId]});
    if(model(modelId)?.type==='guided_ascent')return window.SixDGuidedAscent.report(powerResult(modelId),{projectId:state.data.project_id,revision:state.data.revision,modelId,runId:currentRun()?.run_id,reviewDigest:currentRun()?.review?.digest,hasDraft:!!state.draft,origin:currentRun()?.model_origins?.[modelId]});
    if(model(modelId)?.type!=='powered_flight')return '';
    return window.SixDPoweredFlight.report(powerResult(modelId),{projectId:state.data.project_id,revision:state.data.revision,modelId,runId:currentRun()?.run_id,reviewDigest:currentRun()?.review?.digest,hasDraft:!!state.draft,origin:currentRun()?.model_origins?.[modelId]});
  }
  function attitudeEvidence(modelId){
    if(model(modelId)?.type!=='attitude_control')return '';
    return window.SixDAttitude.report(powerResult(modelId),{projectId:state.data.project_id,revision:state.data.revision,modelId,runId:currentRun()?.run_id,reviewDigest:currentRun()?.review?.digest,hasDraft:!!state.draft,origin:currentRun()?.model_origins?.[modelId]});
  }
  function powerEvidence(modelId){
    if(model(modelId)?.type!=='power_energy_budget')return '';
    return window.SixDPowerBudget.report(powerResult(modelId),{projectId:state.data.project_id,revision:state.data.revision,modelId,runId:currentRun()?.run_id,reviewDigest:currentRun()?.review?.digest,hasDraft:!!state.draft,origin:currentRun()?.model_origins?.[modelId]});
  }
  function renderPanel() {
    const legacyAssistant=state.panel==='assistant';
    if(legacyAssistant){state.panel='details';queueMicrotask(()=>openRocket({scope:ai.scope}));}
    const center=$('#sd-selected-context');center.hidden=state.page!=='system'||!state.selected;
    // Full-width pages have their own evidence; do not construct hidden plots.
    if(center.hidden){$('#sd-panel-context').replaceChildren();$('#sd-panel-body').replaceChildren();return;}
    const selected=state.selected;
    root.querySelectorAll('[data-panel]').forEach(el=>el.setAttribute('aria-selected',String(el.dataset.panel===state.panel)));
    $('#sd-panel-body').setAttribute('aria-labelledby','sd-tab-'+state.panel);
    if(!selected){$('#sd-panel-context').innerHTML='<h2>Select an item</h2>';$('#sd-panel-body').innerHTML='<p>Choose a requirement, model or input to inspect it.</p>';return;}
    const object=selected.kind==='requirement'?req(selected.id):selected.kind==='model'?model(selected.id):project().inputs[selected.id];
    if(!object)return;
    const title=selected.kind==='requirement'?object.title:human(selected.id);
    $('#sd-panel-context').innerHTML='<span class="sd-label">'+esc(selected.kind)+' · R'+state.data.revision+'</span><h2>'+esc(title)+'</h2><span class="sd-small sd-muted">'+esc(selected.id)+'</span>'+(selected.kind==='requirement'?'<div style="margin-top:9px">'+chip(reqStatus(selected.id))+'</div>':'');
    let body='';
    if(selected.kind==='input'){
      const users=allModels().filter(m=>Object.values(m.inputs).includes(selected.id));const limits=allReqs().filter(r=>r.limit_input===selected.id);
      body='<label class="sd-field">Value'+inputField(selected.id,'value')+'</label><label class="sd-field">Explicit unit'+inputField(selected.id,'unit')+'</label><label class="sd-field">Source'+inputField(selected.id,'source')+'</label><p>Sources are supplied provenance labels; their accuracy is not independently established.</p><h3>Declared consumers</h3><div class="sd-affected-list">'+users.map(m=>'<button type="button" data-kind="model" data-id="'+esc(m.id)+'">'+esc(human(m.id))+icon('arrow-up-right')+'</button>').join('')+limits.map(r=>'<button type="button" data-kind="requirement" data-id="'+esc(r.id)+'">'+esc(r.title)+icon('arrow-up-right')+'</button>').join('')+'</div>';
    }else if(selected.kind==='model'){
      body='<p>'+esc(object.description || human(object.type))+'</p><h3>Input bindings</h3><div class="sd-affected-list">'+Object.entries(object.inputs).map(([name,id])=>'<button type="button" data-kind="input" data-id="'+esc(id)+'"><span>'+esc(human(name))+'<br><small>'+measure(project().inputs[id])+'</small></span>'+icon('arrow-up-right')+'</button>').join('')+'</div>'+modelEvidence(selected.id)+powerEvidence(selected.id)+attitudeEvidence(selected.id)+flightEvidence(selected.id);
    }else{
      const f=finding(selected.id),old=priorFinding(selected.id),limit=project().inputs[object.limit_input];
      if(state.panel==='evidence')body+='<p class="sd-small sd-muted">Recorded calculation evidence. Ask the rocket to explain it.</p>';
      body+=(state.draft?'<div class="sd-notice">Draft values have not been calculated. Recorded evidence belongs to saved R'+state.data.revision+'.</div>':'')+(f?'<p>'+esc(f.reason)+'</p>':'<p>No review has been recorded for this revision.</p>')+(f?.evidence?'<div class="sd-finding-value">'+(comparisonNeedsExact(f.evidence)?esc(String(f.evidence.metric.value)):num(f.evidence.metric.value))+' <span>'+esc(f.evidence.metric.unit)+'</span></div>'+disclosure('finding-plot:'+selected.id,'View comparison graph',chart(selected.id)):old?.evidence?'<div class="sd-notice">Historical R'+priorRun().revision+': '+measure(old.evidence.metric)+'. This is not a current result.</div>':'')+'<dl class="sd-details-grid"><dt>Model</dt><dd>'+selectionButton('model',object.model_id,human(object.model_id),'sd-mini-action')+'</dd><dt>Comparison</dt><dd>'+esc(object.operator)+'</dd><dt>Declared limit</dt><dd>'+plotMeasure(limit,comparisonNeedsExact(f?.evidence))+'</dd><dt>Critical requirement</dt><dd>'+(object.critical?'Yes':'No')+'</dd></dl><label class="sd-field">Requirement limit'+inputField(object.limit_input,'value')+'</label><label class="sd-field">Limit unit'+inputField(object.limit_input,'unit')+'</label><label class="sd-field">Limit source'+inputField(object.limit_input,'source')+'</label>';
      if(state.draft)body+='<label class="sd-field">Comparison operator<select class="sd-input" data-requirement="'+esc(object.id)+'" data-req-field="operator">'+['<=','>=','=='].map(op=>'<option '+(object.operator===op?'selected':'')+' value="'+esc(op)+'">'+esc(op)+'</option>').join('')+'</select></label><label class="sd-field">Critical<select class="sd-input" data-requirement="'+esc(object.id)+'" data-req-field="critical"><option value="true" '+(object.critical?'selected':'')+'>Yes</option><option value="false" '+(!object.critical?'selected':'')+'>No</option></select></label>';
      if(state.panel==='evidence')body+='<h3>What was checked?</h3><p>The maintained adapter’s recorded '+esc(human(object.metric))+' is compared with the declared '+esc(object.operator)+' limit in the same unit. A requirement can remain unassessed when its model or inputs are unsupported.</p>'+modelEvidence(object.model_id);
      if(state.panel!=='evidence')body+=declaredAccuracy(object.model_id)+modelContext(object.model_id,true);
      body+=trajectoryContext(object.model_id)+powerEvidence(object.model_id)+attitudeEvidence(object.model_id)+flightEvidence(object.model_id)+interfaceSlot('inspector',[object.model_id])+testEvidenceSlot('inspector',[object.id]);
      if(f)body+='<details class="sd-source"><summary>Requirement evidence identity</summary><p class="sd-receipt">Dependency '+esc(f.dependency_fingerprint)+'</p><p>Inputs: '+esc((f.dependencies?.input_ids||[]).join(', '))+'</p></details>';
    }
    if(!state.draft&&latest())body+='<button type="button" class="sd-button" data-action="edit">'+icon('pencil')+'Edit draft</button>';
    if(!currentRun()&&!state.draft)body+='<button type="button" class="sd-button sd-primary" data-action="run">Run supported checks</button>';
    if(selected.kind==='model')body+=sourceSlot('inspector',allReqs().filter(r=>r.model_id===selected.id).map(r=>r.id),[selected.id]);
    if(selected.kind==='requirement')body+=sourceSlot('inspector',[selected.id],[object.model_id]);
    if(selected.kind==='model')body+=actionSlot('inspector',allReqs().filter(r=>r.model_id===selected.id).map(r=>r.id),[selected.id]);
    if(selected.kind==='requirement'){
      body+=actionSlot('inspector',[selected.id],[object.model_id]);
      if(!state.draft&&['not_met','not_assessed'].includes(finding(selected.id)?.status))body+='<button type="button" class="sd-button" data-track-action="'+esc('finding:'+selected.id)+'">Track engineering action</button>';
    }
    $('#sd-panel-body').innerHTML=body;compactItemContext(selected);hydrateSourceLinks();hydrateActionLinks();
  }
  function compactItemContext(selected){
    const host=$('#sd-panel-body');
    if(selected.kind!=='requirement')return;
    const fields=[...host.children].filter(node=>node.matches('label.sd-field'));
    const lastField=fields.at(-1);
    if(lastField){
      const summaryGrid=document.createElement('div');summaryGrid.className='sd-context-summary';
      const findingSummary=document.createElement('section'),criterionSummary=document.createElement('section');
      findingSummary.setAttribute('aria-label','Calculated finding');criterionSummary.setAttribute('aria-label','Declared criterion');
      for(const node of [...host.children]){if(node===fields[0])break;(node.matches('dl.sd-details-grid')?criterionSummary:findingSummary).append(node);}
      if(findingSummary.children.length&&criterionSummary.children.length){summaryGrid.append(findingSummary,criterionSummary);host.prepend(summaryGrid);}
      else host.prepend(...findingSummary.childNodes,...criterionSummary.childNodes);
      const technical=document.createElement('details');technical.className='sd-context-technical';
      const summary=document.createElement('summary');summary.textContent='Assumptions and supporting evidence';technical.append(summary);
      let node=lastField.nextSibling;
      while(node){const next=node.nextSibling;technical.append(node);node=next;}
      if(technical.children.length>1)host.append(technical);
      const fieldGroup=document.createElement('div');fieldGroup.className='sd-context-fields';
      fields[0].before(fieldGroup);fields.forEach(field=>fieldGroup.append(field));
      if(!state.draft){
        const editable=document.createElement('details');editable.className='sd-context-inputs';
        const heading=document.createElement('summary');heading.textContent='Declared limit and source';editable.append(heading,fieldGroup);host.insertBefore(editable,technical.isConnected?technical:null);
      }
    }
  }
  function disposeRocketResearch(){
    rocketUI.researchDispose?.();rocketUI.researchDispose=null;rocketUI.researchKey='';
  }
  function pageAssistantIntent(){return window.SixDAssistantContext.defaultIntent({page:state.page,selected:state.selected,requirements:allReqs()});}
  function assistantLaunchKey(){return JSON.stringify([state.data?.project_id,state.data?.revision,currentRun()?.run_id||null,state.page,state.selected?.kind||null,state.selected?.id||null]);}
  function assistantDescriptor(){return window.SixDAssistantContext.describe({view:state.data,page:state.page,scope:ai.scope,requirementId:ai.rocketRequirementId,testSelection:ai.testSelection,sourceProfile:sourceLinks.key===sourceLinkKey()?sourceLinks.profile:null,hasDraft:!!state.draft,latest:latest()});}
  function testParkKey(requirementId){return JSON.stringify([state.data?.project_id,state.data?.revision,currentRun()?.run_id||null,requirementId]);}
  function changeAssistantContext({scope,requirementId,testSelection}={},preserveQuestion=false){
    const question=ai.question;
    if(ai.testSelection&&ai.testSelection.projectId===state.data.project_id&&ai.testSelection.revision===state.data.revision&&ai.testSelection.runId===(currentRun()?.run_id||null)){
      rocketUI.parkedTests.set(testParkKey(ai.testSelection.requirementId),ai.testSelection);
      if(rocketUI.parkedTests.size>50)rocketUI.parkedTests.delete(rocketUI.parkedTests.keys().next().value);
    }
    ai.scope=scope==='requirement'?'requirement':'project';
    ai.rocketRequirementId=ai.scope==='requirement'&&req(requirementId)?requirementId:null;
    ai.testSelection=testSelection||rocketUI.parkedTests.get(testParkKey(ai.rocketRequirementId))||null;
    syncAssistantContext();
    if(preserveQuestion&&question){ai.question=question;rocketUI.notice='Your question was kept. Review the selected evidence before asking.';}
    else rocketUI.notice='';
    rocketUI.launchContext=assistantLaunchKey();
  }
  function mountRocket(){
    rocket=window.SixDRocketAssistant.mount({
      onOpen:()=>{
        const intent=rocketUI.openIntent;rocketUI.openIntent=null;
        if(intent)changeAssistantContext(intent,intent.preserveQuestion===true);
        else if(rocketUI.launchContext!==assistantLaunchKey()){
          const previous=rocketUI.launchContext?JSON.parse(rocketUI.launchContext):[];
          const next=JSON.parse(assistantLaunchKey());
          changeAssistantContext(pageAssistantIntent(),previous.length>0&&same(previous.slice(0,3),next.slice(0,3)));
        }
        renderRocket(true);void refreshAiStatus();
      },
      onTabChange:()=>{renderRocket(true);},
      onClose:()=>{if(ai.context)rocketUI.questionDrafts.set(ai.context,ai.question);stopInvestigationPolling();}
    });
    $('#sd-rocket-nemotron-host').innerHTML='<div id="sd-rocket-ai-context"></div><div id="sd-rocket-ai-body"></div>';
  }
  function openRocket({scope,requirementId,tab='nemotron',preserveQuestion=false,testSelection}={}){
    if(!rocket||!state.data)return;
    if(scope){
      if(scope==='requirement'&&!req(requirementId))requirementId=req(ai.rocketRequirementId)?.id||pageAssistantIntent().requirementId||allReqs()[0]?.id;
      rocketUI.openIntent={scope,requirementId,preserveQuestion,testSelection};
    }
    rocket.open(tab);
  }
  async function askLinkedReference(selection,mountKey){
    if(mountKey!==sourceLinkKey()||state.draft||!latest()||sourceLinks.key!==mountKey)return false;
    const profile=sourceLinks.profile;
    const link=profile?.links?.find(item=>item.source_id===selection.source_id&&item.target?.target_id===selection.target_id&&item.status==='linked');
    if(!link)return false;
    const target=link.target;
    const requirement=allReqs().find(item=>['requirement:'+item.id,'finding:'+item.id].includes(target.target_id))||
      (target.kind==='model_assumption'?allReqs().find(item=>item.model_id===target.id):null);
    openRocket({scope:requirement?'requirement':'project',requirementId:requirement?.id,preserveQuestion:true});
    if(!ai.question.trim())ai.question='Explain how this linked reference supports the selected saved evidence, identify limitations, and suggest the next engineering check. Preserve the recorded findings.';
    rocketUI.notice='Reference '+selection.source_id+' is linked in this scope. Review your question, then choose Ask Nemotron. Capture limits apply; nothing has been sent.';
    renderRocket(true);return true;
  }
  async function copyRocketReference(source,context,projectId,revision,runId){
    const capturedKey=JSON.stringify([projectId,revision,runId,false]),serial=++rocketUI.handoffSerial;
    const refused=reason=>{message(reason);rocket.announce(reason);return {copied:false,reason};};
    const valid=()=>serial===rocketUI.handoffSerial&&sourceLinkKey()===capturedKey&&!state.draft&&latest();
    if(!valid())return refused('The saved project changed. Return to the search context before copying this preview.');
    if(state.page!=='sources'){state.page='sources';state.panel='details';render();}
    const expected={projectId,revision,runId},deadline=performance.now()+5000;
    while(performance.now()<deadline){
      if(!valid()||state.page!=='sources')return refused('The source destination changed. The preview remains in the rocket; nothing was saved.');
      const availability=window.SixDSources.prefillAvailability(expected);
      if(availability.ready&&window.SixDSources.prefill(source,context?.target_id,expected)){
        rocket.close();$('#sd-source-library').scrollIntoView({block:'start'});
        message('Reference copied into an unsaved source form. Review it, then save and link it explicitly.');return true;
      }
      if(availability.state!=='loading'){
        return refused((availability.reason||'The source form is unavailable.')+' Your preview remains in the rocket; nothing was saved.');
      }
      await new Promise(resolve=>setTimeout(resolve,50));
    }
    return refused('The source form is still loading. Your preview remains in the rocket; no source was saved. Try again after it loads.');
  }
  function renderRocket(force=false){
    if(!rocket||!state.data)return;
    rocket.setBusy(!!(ai.starting||ai.status?.investigation_active||rocketUI.researchBusy));
    rocket.setContext(project().name+' · Saved R'+state.data.revision+' · '+window.SixDWorkspaceShell.labelFor(state.page));
    if(!rocket.isOpen())return;
    if(state.page==='projects'){
      if(rocketUI.researchBusy&&rocket.tab()==='research'){rocket.setContext('Finishing the reference request in its captured project. Choose a project after it completes.');return;}
      if(!rocketUI.researchBusy)disposeRocketResearch();
      $('#sd-rocket-ai-context').textContent='Choose your project first';
      $('#sd-rocket-ai-body').innerHTML='<p>Open a project from the Projects page, then ask me about its saved design, a requirement or what to check next.</p><p class="sd-small sd-muted">I explain recorded engineering evidence. Opening the rocket never sends a question automatically.</p>';
      if(rocket.tab()==='research')$('#sd-rocket-research-host').innerHTML='<p>Open a project first so reference searches have a clear engineering context.</p>';
      rocketUI.rendered='';return;
    }
    if(rocket.tab()==='research'){
      const key=JSON.stringify([state.data.project_id,state.data.revision,currentRun()?.run_id||null,!!state.draft,latest()]);
      if(key!==rocketUI.researchKey||!rocketUI.researchDispose){
        if(rocketUI.researchBusy){rocket.setContext('Finishing the reference request in its captured project context.');return;}
        disposeRocketResearch();const projectId=state.data.project_id,revision=state.data.revision,runId=currentRun()?.run_id||null;
        const draftKey=JSON.stringify([projectId,revision]),draft=rocketUI.researchDrafts.get(draftKey)||{};
        rocketUI.researchKey=key;
        rocketUI.researchDispose=window.SixDResearch.mount($('#sd-rocket-research-host'),{
          api,projectId,revision,hasDraft:!!state.draft,canEdit:latest(),inAssistant:true,
          initialQuery:draft.query,initialTarget:draft.target,
          onDraftChange:value=>{rocketUI.researchDrafts.set(draftKey,value);if(rocketUI.researchDrafts.size>50)rocketUI.researchDrafts.delete(rocketUI.researchDrafts.keys().next().value);},
          onBusyChange:busy=>{rocketUI.researchBusy=busy;rocket.setBusy(!!(busy||ai.starting||ai.status?.investigation_active));if(!busy&&rocket.isOpen())queueMicrotask(()=>renderRocket());},
          onUseReference:(source,context)=>copyRocketReference(source,context,projectId,revision,runId)
        });
      }
      return;
    }
    syncAssistantContext();
    const signature=JSON.stringify([ai.context,!!state.draft,state.page,latest()]);
    if(force||rocketUI.rendered!==signature){
      rocketUI.rendered=signature;renderAssistant();compactRocketAssistant();
    }else{
      renderAssistantContextSummary();updateAiControls();if(ai.loadedContext!==ai.context&&!ai.loading)void loadInvestigations();
    }
  }
  function compactRocketAssistant(){
    const owner=$('#sd-rocket-ai-body [data-action="ai-settings"]');if(owner)owner.hidden=state.hosted;
  }
  function resetCamera() {state.camera={x:18,y:35,scale:0.9};}
  function applyCamera() {const stage=$('#sd-graph-stage');if(!stage)return;stage.style.transform='translate('+state.camera.x+'px,'+state.camera.y+'px) scale('+state.camera.scale+')';const label=$('#sd-zoom-value');if(label)label.textContent=Math.round(state.camera.scale*100)+'%';}
  function fit() {const canvas=$('#sd-canvas'),stage=$('#sd-graph-stage');if(!canvas||!stage)return;state.camera.scale=Math.max(.3,Math.min(1,(canvas.clientWidth-40)/Number(stage.dataset.width),(canvas.clientHeight-90)/Number(stage.dataset.height)));state.camera.x=(canvas.clientWidth-Number(stage.dataset.width)*state.camera.scale)/2;state.camera.y=40;applyCamera();}
  function bindPan() {const canvas=$('#sd-canvas');if(!canvas)return;let drag=null;canvas.addEventListener('pointerdown',event=>{if(event.target.closest('button,input,select')||window.innerWidth<=570)return;drag={x:event.clientX,y:event.clientY,cx:state.camera.x,cy:state.camera.y};canvas.setPointerCapture(event.pointerId);});canvas.addEventListener('pointermove',event=>{if(!drag)return;state.camera.x=drag.cx+event.clientX-drag.x;state.camera.y=drag.cy+event.clientY-drag.y;applyCamera();});const end=()=>{drag=null;};canvas.addEventListener('pointerup',end);canvas.addEventListener('pointercancel',end);}
  function select(kind,id,investigate=false) {
    ai.rocketRequirementId=kind==='requirement'?id:null;
    state.selected={kind,id};if(investigate){ai.scope='requirement';ai.rocketRequirementId=id;state.panel='assistant';}
    if(kind==='requirement'){const r=req(id),s=owningSystem(r?.model_id);if(s&&state.system!=='overview'&&!activeSystem()?.model_ids.includes(r?.model_id))state.system=s.id;}
    render();
    if(investigate&&kind==='requirement')void refreshAiStatus();
    else if(state.page==='system'&&!$('#sd-selected-context').hidden)$('#sd-selected-context').scrollIntoView({block:'nearest'});
  }
  const investigationId = record => record.investigation_id;
  const investigationActive = record => ['queued','running'].includes(record.state);
  const dollars = value => typeof value==='number'&&Number.isFinite(value)?'$'+value.toFixed(4):'Unavailable';
  const providerModelLabel = id => ({
    'nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B':'NVIDIA Nemotron 3 Nano',
    'nvidia/nemotron-3-super-120b-a12b':'NVIDIA Nemotron 3 Super',
    'nvidia/Nemotron-3-Ultra-550b-a55b':'NVIDIA Nemotron 3 Ultra'
  })[id] || (typeof id==='string'&&id?id:'the configured NVIDIA Nemotron model');
  function modelChoices() {return Array.isArray(ai.status?.available_models)?ai.status.available_models.filter(row=>['nano','super','ultra'].includes(row.id)):[];}
  function selectedAIModel() {return modelChoices().find(row=>row.id===ai.modelChoice)||null;}
  function modelChoiceMarkup() {
    return '<div class="sd-ai-model-picker"><label class="sd-field" for="sd-ai-model">Model<select class="sd-input" id="sd-ai-model" aria-describedby="sd-ai-model-help"></select></label><p id="sd-ai-model-help" class="sr-only"></p></div>';
  }
  function updateModelChoiceControls() {
    const select=$('#sd-ai-model');if(!select)return;
    const rows=modelChoices(),chosen=selectedAIModel();
    select.innerHTML='<option value=""'+(!chosen?' selected':'')+'>'+(rows.length?'Choose a model':'Reading available models…')+'</option>'+rows.map(row=>'<option value="'+esc(row.id)+'"'+(row.id===chosen?.id?' selected':'')+'>'+esc(window.SixDAssistantConversation.modelOptionLabel(row.id))+'</option>').join('');
    select.disabled=!rows.length||ai.starting||ai.status?.investigation_active||ai.records.some(investigationActive)||state.busy;
    $('#sd-ai-model-help').textContent=window.SixDAssistantConversation.modelHint(chosen?.id);
    const consent=$('#sd-ai-consent-model');if(consent)consent.textContent=chosen?providerModelLabel(chosen.model):'you choose';
  }
  function stopInvestigationPolling() {
    ai.generation++;clearTimeout(ai.timer);ai.timer=null;clearTimeout(ai.statusTimer);ai.statusTimer=null;ai.controller?.abort();ai.controller=null;ai.loading=false;ai.loadedContext='';
  }
  function syncAssistantContext() {
    const descriptor=assistantDescriptor(),old=ai.context;
    if(ai.testSelection&&!descriptor.testSelection){
      // Preserve the row under its original saved context, never attach it to a new check.
      ai.testSelection=null;
    }
    ai.requirementId=descriptor.scope==='project'?'__project__':descriptor.requirementId;
    const next=descriptor.historyKey;
    if(next!==old){
      if(old)rocketUI.questionDrafts.set(old,ai.question);
      if(old)rocketUI.modelSelections.set(old,ai.modelChoice);
      if(rocketUI.questionDrafts.size>50)rocketUI.questionDrafts.delete(rocketUI.questionDrafts.keys().next().value);
      stopInvestigationPolling();ai.context=next;ai.question=rocketUI.questionDrafts.get(next)||'';ai.records=[];ai.error='';ai.loading=false;ai.loadedContext='';ai.starting=false;
      ai.modelChoice=rocketUI.modelSelections.get(next)||null;
      if(rocketUI.modelSelections.size>50)rocketUI.modelSelections.delete(rocketUI.modelSelections.keys().next().value);
    }
  }
  function renderAssistantContextSummary(){
    const host=$('#sd-ai-context-summary');if(!host||!state.data)return;
    const context=assistantDescriptor(),parked=[...rocketUI.parkedTests.keys()].some(key=>key.startsWith(JSON.stringify([context.projectId,context.revision,context.runId]).slice(0,-1)+','));
    let reference=context.references.summary;
    if(context.references.state!=='ready')reference=sourceLinks.error?'References could not be loaded. Open saved references or refresh before relying on them.':'Loading linked references for this saved context…';
    const scopeTitle=context.scope==='project'?'Whole project':window.SixDSourceTargets?.shortLabel({label:context.requirementTitle||'No check selected',target_id:'requirement:'+context.requirementId})||context.requirementTitle;
    host.innerHTML='<details class="sd-chat-context-details"><summary><strong>'+esc(scopeTitle)+'</strong> · saved R'+esc(context.revision)+(context.findingStatus?' · '+esc(human(context.findingStatus)):'')+'</summary><p><strong>'+esc(context.title)+' · R'+esc(context.revision)+'</strong></p><p>'+esc(context.requirementTitle||'Whole project')+'</p><p class="sd-small sd-muted">'+esc(context.runId?'Saved calculation '+context.runId:'No saved calculation in this revision')+'</p><p class="sd-small">'+esc(reference)+'</p>'+(context.testSelection?'<p class="sd-small">Selected test row '+esc(context.testSelection.rowNumber)+' from comparison '+esc(context.testSelection.comparisonId)+'.</p><button type="button" class="sd-mini-action" data-action="clear-test-selection">Clear selected test row</button>':parked?'<p class="sd-small sd-notice">A test row is parked for another check; it is not included.</p>':'')+'<button type="button" class="sd-mini-action" data-action="ai-use-page-context">Use this page’s context</button></details>'+(context.hasDraft?'<p class="sd-notice">Your draft is not calculated. This conversation uses the saved revision.</p>':'')+(context.historical?'<p class="sd-notice">Historical saved revision. Reference changes are disabled.</p>':'')+(context.runStale?'<p class="sd-notice">The saved calculation needs rechecking against current sources.</p>':'')+(rocketUI.notice?'<p class="sd-small" role="status">'+esc(rocketUI.notice)+'</p>':'');
  }
  function aiStatusMarkup(owner=false) {
    const s=ai.status;if(!s)return '<p class="sd-small sd-muted">Reading AI connection status…</p>';
    const name=selectedAIModel()?providerModelLabel(selectedAIModel().model):owner?providerModelLabel(s.model):'Choose a model before asking';
    const basic='<div class="sd-ai-connection"><span class="sd-dot '+(s.key_present?'sd-green':'sd-amber')+'"></span><strong>'+(s.key_present?'AI connected':'AI not connected')+'</strong></div><p class="sd-small sd-muted">'+esc(name)+' · Nebius Token Factory</p>';
    if(!owner)return basic+(!s.configured?'<p class="sd-notice">AI is unavailable. Your saved calculations and evidence remain accessible.</p>':'')+(s.provider_mode&&s.provider_mode!=='live_token_factory'?'<p class="sd-notice">Offline test provider · no live inference.</p>':'');
    return basic+'<p class="sd-small">'+(s.key_remembered?'The key is remembered in encrypted local storage.':'The connection is managed for this server session.')+'</p><dl class="sd-details-grid sd-ai-budget"><dt>Approved development allowance</dt><dd>'+dollars(s.budget?.cap_usd)+'</dd><dt>Cumulative reservations</dt><dd>'+dollars(s.budget?.reserved_usd)+'</dd><dt>Reservation capacity remaining</dt><dd>'+dollars(s.budget?.remaining_usd)+'</dd></dl><p class="sd-small">These are conservative application reservations, not your Nebius wallet balance or bill.</p>';
  }
  async function refreshAiStatus() {
    if(ai.statusLoading)return;
    ai.statusLoading=true;
    try{ai.status=await api('/api/ai/status');ai.statusError='';}
    catch(error){ai.status=null;ai.statusError='AI configuration could not be read. Local calculation records remain available.';}
    finally{ai.statusLoading=false;}
    $('#sd-ai-header-status').textContent=ai.status?.key_present?'Local records · AI on request':'Local records · AI key not connected';
    $('#sd-ai-connect-label').textContent='Owner settings';
    const status=$('#sd-ai-status');if(status)status.innerHTML=aiStatusMarkup();
    const settings=$('#sd-ai-settings-status');if(settings)settings.innerHTML=aiStatusMarkup(true);
    updateModelChoiceControls();
    $('#sd-ai-disconnect-button').disabled=(!ai.status?.key_present&&!ai.status?.key_remembered)||ai.connecting;
    $('#sd-ai-disconnect-button').textContent=ai.status?.key_remembered?'Disconnect & forget':'Disconnect key';
    $('#sd-ai-forget-button').disabled=!ai.status?.key_remembered||ai.connecting;
    $('#sd-ai-remember').disabled=!ai.status?.remember_supported||ai.connecting;
    $('#sd-ai-remember-hint').textContent=ai.status?.remember_supported?'Optional: save an encrypted copy for this Windows account and restore it when 6D starts. Forget removes the saved copy but keeps the current session connected. Disconnect also removes the saved copy.':'Remembering is available on Windows. This connection stays in server memory only.';
    updateAiControls();
    clearTimeout(ai.statusTimer);
    if(ai.status?.investigation_active&&rocket?.isOpen())ai.statusTimer=setTimeout(()=>void refreshAiStatus(),1000);
  }
  function evaluationStatusMarkup() {
    const s=ai.evaluation;
    if(!s)return '<p class="sd-small sd-muted">'+esc(ai.evaluationError || 'Reading model evaluation status…')+'</p>';
    const stages={prepared:'Prepared',comparison_pending:'Comparison pending',running:'Comparison running',evaluated:'Results recorded'};
    const comparison=s.latest_comparison;
    const results=comparison?.candidate_results;
    const recorded=Array.isArray(results)?'<ul class="sd-ai-model-list">'+results.map(row=>'<li>'+esc(row.name)+'<span class="sd-small">'+esc(row.completed)+'/'+esc(row.total)+' completed · '+esc(row.workflow_passes)+' workflow passes</span></li>').join('')+'</ul><p class="sd-small sd-muted">Workflow passes check protocol and recorded evidence. Explanation accuracy requires manual review.</p>':'';
    const report=comparison&&/^[a-f0-9]{32}$/.test(comparison.comparison_id)?'<p class="sd-small"><a href="/api/model-evaluation/comparisons/'+comparison.comparison_id+'" target="_blank" rel="noopener">Open saved comparison evidence JSON</a></p>':'';
    const capturedLimits=comparison?'<p class="sd-small sd-muted">Captured comparison policy: '+esc(comparison.policy_version || 'Original recorded policy')+(typeof comparison.batch_cap_usd==='number'?' · batch ceiling '+dollars(comparison.batch_cap_usd):'')+(typeof comparison.max_request_reservations==='number'?' · up to '+esc(comparison.max_request_reservations)+' request reservations':'')+'. Reserved for this comparison: '+dollars(comparison.reserved_usd)+'. Historical scores stay attached to their recorded policy.</p>':'';
    const decision=comparison?.model_decision;
    const decisionNote=typeof decision==='string'?decision:decision&&(decision.note || decision.reason || decision.summary);
    const reviewedDecision=decision?'<details class="sd-source"><summary>Recorded model decision</summary>'+(typeof decisionNote==='string'?'<p class="sd-small">'+esc(decisionNote)+'</p>':'')+'<pre>'+esc(typeof decision==='string'?decision:JSON.stringify(decision,null,2))+'</pre></details>':'<p class="sd-small sd-muted">This historical comparison does not change the model you choose for a new investigation.</p>';
    const nextLimits=typeof s.batch_cap_usd==='number'?'<p class="sd-small sd-muted">Prepared next comparison ceiling: '+dollars(s.batch_cap_usd)+' and up to '+esc(s.max_request_reservations ?? 'the configured number of')+' request reservations within the approved cumulative allowance. Opening these settings sends no model requests.</p>':'';
    return '<div class="sd-section-heading"><h3>Historical default-selection comparison</h3><span class="sd-chip">'+esc(stages[s.stage] || human(s.stage || 'pending'))+'</span></div><p class="sd-small">Recorded default model: <strong>'+esc(s.active_model?.name || ai.status?.model || 'Not configured')+'</strong></p><ul class="sd-ai-model-list">'+(Array.isArray(s.candidates)?s.candidates:[]).map(candidate=>'<li><div><strong>'+esc(candidate.name || candidate.id)+'</strong><span class="sd-small sd-muted">'+esc(candidate.reason || (candidate.enabled?'Existing baseline':'Not enabled'))+'</span></div><span class="sd-chip">'+(candidate.enabled?'Default at this checkpoint':'Not selected as default')+'</span></li>').join('')+'</ul>'+(comparison?'<p class="sd-small sd-muted">Latest comparison: '+esc(human(comparison.state))+' · '+esc(comparison.completed_cases ?? 0)+'/'+esc(comparison.total_cases ?? s.case_count ?? 0)+' investigations completed.</p>':'')+capturedLimits+recorded+reviewedDecision+report+nextLimits+'<p class="sd-small sd-muted">'+esc(s.note || 'The comparison is prepared. Live evaluation is pending; no stronger model is enabled by preparation alone.')+'</p>';
  }
  async function refreshEvaluationStatus() {
    if(ai.evaluationLoading)return;
    ai.evaluationLoading=true;
    try{[ai.evaluation,ai.workflowEvaluation,ai.ultraDiagnostic,ai.evidenceEvaluation]=await Promise.all([api('/api/model-evaluation/status'),api('/api/workflow-evaluation/status'),api('/api/ultra-diagnostic/status'),api('/api/evidence-evaluation/status').catch(()=>null)]);ai.evaluationError='';}
    catch{ai.evaluation=null;ai.evaluationError='Model comparison status could not be read. The active investigation configuration has not been changed.';}
    finally{ai.evaluationLoading=false;}
    const target=$('#sd-ai-evaluation-status');if(target)target.innerHTML=evaluationStatusMarkup()+evidenceEvaluationMarkup()+workflowEvaluationMarkup()+ultraDiagnosticMarkup();
  }
  function evidenceEvaluationMarkup() {
    const s=ai.evidenceEvaluation;if(!s)return '';
    const r=s.latest,rows=Array.isArray(s.scorecard?.candidates)?s.scorecard.candidates:[];
    const olderContract=!!s.scorecard&&s.scorecard.explanation_policy!==s.explanation_policy;
    const link=r&&/^[a-f0-9]{32}$/.test(r.comparison_id)?'<p><a href="/api/evidence-evaluation/runs/'+r.comparison_id+'" target="_blank" rel="noopener">Open saved evidence-linked comparison JSON</a></p>':'';
    const table=rows.length?'<div class="sd-table-wrap"><table class="sd-table"><thead><tr><th>Model</th><th>Completed</th><th>Workflow passes</th><th>Fact-contract passes</th><th>With fact links</th><th>Untested</th><th>Reserved</th></tr></thead><tbody>'+rows.map(row=>'<tr><td>'+esc(row.label)+'</td><td>'+esc(row.completed)+' / '+esc(row.planned)+'</td><td>'+esc(row.workflow_passes)+'</td><td>'+esc(row.fact_contract_passes)+'</td><td>'+esc(row.linked_explanations??0)+'</td><td>'+esc(row.untested)+'</td><td>'+dollars(row.reserved_usd)+'</td></tr>').join('')+'</tbody></table></div>':'';
    const stops=rows.flatMap(row=>(row.stopped_cases||[]).map(item=>'<p class="sd-small">'+esc(row.label)+' · '+esc(item.case_id)+': '+esc(item.reason||item.error_code||'Investigation stopped')+'</p>')).join('');
    return '<section class="sd-source" id="sd-evidence-evaluation"><h3>Evidence-linked explanation comparison</h3><p class="sd-small">'+esc(s.case_count)+' identical constructed cases for Nano, Super and Ultra · '+esc(s.planned_tasks)+' planned investigations. Numerical roles and explanation-contract checks are recorded separately.</p>'+(olderContract?'<p class="sd-notice">This saved batch used the earlier explanation contract. The updated application-owned numerical contract has not been verified by this historical result.</p>':'')+'<p class="sd-small">'+(r?esc(human(r.state))+' batch · '+dollars(r.reserved_usd)+' reserved · '+esc(r.request_reservations)+' requests.':'Prepared; no live comparison is recorded yet.')+'</p>'+table+stops+link+'<p class="sd-small sd-muted">Ceiling '+dollars(s.batch_cap_usd)+' and at most '+esc(s.max_request_reservations)+' request reservations within the cumulative allowance. Fact-contract passes check source binding; they do not establish semantic accuracy or independent engineering validation. No model is enabled automatically.</p><button type="button" class="sd-button" data-action="workflow-evaluation-refresh">Refresh recorded comparison</button></section>';
  }
  function ultraDiagnosticMarkup() {
    const s=ai.ultraDiagnostic;if(!s)return '';
    const r=s.latest,d=r?.diagnostic;
    const detail=d?'<p class="sd-small">Rejection: '+esc(d.selection_rejection||'No precise selection rejection recorded')+'</p><pre>'+esc(JSON.stringify(d,null,2))+'</pre>':'';
    const link=r&&/^[a-f0-9]{32}$/.test(r.comparison_id)?'<p><a href="/api/ultra-diagnostic/runs/'+r.comparison_id+'" target="_blank" rel="noopener">Download targeted diagnostic</a></p>':'';
    return '<section class="sd-source" id="sd-ultra-diagnostic"><h3>Ultra compatibility diagnostic</h3><p class="sd-small">One fresh constructed orbital case, separate from the original comparison. Ceiling '+dollars(s.cap_usd)+' and '+esc(s.max_requests)+' requests within the existing allowance. No automatic retry or model activation.</p><p class="sd-small">'+(r?esc(human(r.state))+' batch · '+dollars(r.reserved_usd)+' reserved · '+esc(r.request_reservations)+' requests.':'Prepared; no targeted live result recorded.')+'</p>'+(r?.error?'<p class="sd-small">'+esc(r.error)+'</p>':'')+detail+link+'<button type="button" class="sd-button" data-action="workflow-evaluation-refresh">Refresh recorded results</button><p class="sd-small sd-muted">A successful new case cannot establish the exact cause of the unretained historical response or qualify the remaining Ultra cases. Reading this panel sends no model requests.</p></section>';
  }
  function workflowEvaluationMarkup() {
    const s=ai.workflowEvaluation;if(!s)return '';
    const latest=s.latest,card=s.scorecard;
    const rows=card?.candidates||[];
    const link=latest&&/^[a-f0-9]{32}$/.test(latest.comparison_id)?'<p><a href="/api/workflow-evaluation/runs/'+latest.comparison_id+'" target="_blank" rel="noopener">Download full workflow evaluation and responses</a></p>':'';
    const table=rows.length?'<div class="sd-table-wrap"><table class="sd-table"><thead><tr><th>Model</th><th>Attempted</th><th>Completed</th><th>Workflow passes</th><th>Untested</th><th>Reserved</th><th>Elapsed</th></tr></thead><tbody>'+rows.map(row=>'<tr><td>'+esc(row.label)+'</td><td>'+esc(row.attempted)+'</td><td>'+esc(row.completed)+' / '+esc(row.planned)+'</td><td>'+esc(row.workflow_passes)+'</td><td>'+esc(row.untested??(row.planned-row.attempted))+'</td><td>'+dollars(row.reserved_usd)+'</td><td>'+esc(Number(row.elapsed_seconds).toFixed(1))+' s</td></tr>').join('')+'</tbody></table></div>':'';
    const stops=rows.flatMap(row=>(row.stopped_cases||[]).map(item=>'<p class="sd-small">'+esc(row.label)+' · '+esc(item.case_id)+' · '+esc(item.error_code||'stopped')+': '+esc(item.reason||'No completed explanation was accepted.')+'</p>')).join('');
    return '<section class="sd-source" id="sd-workflow-evaluation"><h3>Engineering workflow evaluation</h3><p class="sd-small">Ten constructed scenarios across Nano, Super and Ultra. Checks include orbital accuracy gaps, near-limit criteria, linked changes and power capacity. This is separate from the original six-case model-selection evidence.</p><p class="sd-small">'+(latest?'Batch '+esc(human(latest.state))+' · '+dollars(latest.reserved_usd)+' reserved · '+esc(latest.request_reservations||0)+' requests.':'Prepared; live results are not recorded yet.')+'</p>'+table+stops+link+'<button type="button" class="sd-button" data-action="workflow-evaluation-refresh">Refresh workflow evaluation</button><p class="sd-small sd-muted">Ceiling '+dollars(s.batch_cap_usd)+' within the existing cumulative allowance. Skipped cases are untested. Reservations are not billed cost; elapsed time is observed for these cases only. Workflow passes describe action and evidence handling; explanations can still contain factual errors. Independent human engineering review remains pending. No model is automatically enabled.</p></section>';
  }
  function aiBlockedReason() {
    if(state.draft)return 'Save or discard the draft, then run its supported checks before investigating.';
    if(ai.scope==='requirement'&&!req(ai.requirementId))return 'Choose an engineering check or use the whole-project scope before asking.';
    if(!currentRun())return 'Run checks for this saved revision before starting an investigation.';
    if(!ai.status)return 'Read the AI configuration before starting.';
    if(!ai.status.key_present)return 'Connect your Nebius key to enable a live investigation.';
    if(!ai.status.configured)return 'Live provider setup is not ready.';
    if(!selectedAIModel())return 'Choose an available investigation model before starting.';
    if(!(typeof ai.status.spend_available==='boolean'?ai.status.spend_available:ai.status.budget?.remaining_usd>0))return 'AI usage is currently paused by the workspace limits.';
    if(ai.status.investigation_active)return 'An AI investigation is running. Wait for it to finish before starting another.';
    if(ai.records.some(investigationActive))return 'An investigation is still running for this scope.';
    if(ai.loading)return 'Reading saved investigations before allowing a new request.';
    if(conversationHead()&&!conversationSource())return 'Reading the current references before continuing this conversation.';
    return '';
  }
  function updateAiControls() {
    rocket?.setBusy(!!(rocketUI.researchBusy||ai.starting||ai.status?.investigation_active||ai.records.some(investigationActive)));
    updateModelChoiceControls();
    const button=$('#sd-ai-start');if(!button)return;
    const attachment=rocketUI.attachmentController?.snapshot();const composed=questionPayload();const blocked=aiBlockedReason()||(rocketUI.attachmentController?.isBusy()?'Checking the local image before sending…':'')||(attachment?.present&&!attachment.description.trim()?'Describe or transcribe the image first. The selected model receives text, not pixels.':'')||(composed.length>2000?'Shorten the question and image notes to 2,000 characters together.':'');button.disabled=!!blocked||ai.starting||state.busy||!ai.question.trim();
    button.textContent=ai.starting?'Asking…':ai.status?.investigation_active?'Investigation running…':'Ask Nemotron';
    const presence=$('#sd-ai-presence');if(presence)presence.textContent=ai.status?.key_present?'Connected · Nebius':'AI connection unavailable';
    $('#sd-ai-blocked').textContent=blocked;$('#sd-ai-blocked').hidden=!blocked;
    $('#sd-ai-question-count').textContent=composed.length+'/2000';$('#sd-ai-question').disabled=ai.starting||!!ai.status?.investigation_active;const attachmentsDisabled=ai.starting||!!ai.status?.investigation_active;if(ai.attachmentsDisabled!==attachmentsDisabled){ai.attachmentsDisabled=attachmentsDisabled;rocketUI.attachmentController?.setDisabled(attachmentsDisabled);}
  }
  function renderProjectAssistant() {renderUnifiedAssistant(null);}
  function renderUnifiedAssistant(requirement){
    rocketUI.attachmentController?.dispose();rocketUI.attachmentController=null;ai.attachmentsDisabled=null;
    const isProject=ai.scope==='project',requirements=allReqs();
    const shortTitle=r=>window.SixDSourceTargets?.shortLabel({label:r.title,target_id:'requirement:'+r.id})||r.title;
    $('#sd-rocket-ai-context').innerHTML='<div class="sd-assistant-scope-row"><label class="sd-field" for="sd-ai-scope">Discuss<select id="sd-ai-scope" class="sd-input"><option value="project"'+(isProject?' selected':'')+'>Whole project</option><option value="requirement"'+(!isProject?' selected':'')+(requirements.length?'':' disabled')+'>One engineering check</option></select></label>'+(!isProject&&requirements.length?'<label class="sd-field" for="sd-rocket-requirement">Check<select id="sd-rocket-requirement" class="sd-input">'+requirements.map(r=>'<option value="'+esc(r.id)+'"'+(r.id===ai.requirementId?' selected':'')+'>'+esc(shortTitle(r))+'</option>').join('')+'</select></label>':'')+modelChoiceMarkup()+'</div>';
    const context=isProject?'Whole-project questions use saved findings, dependencies and revision changes. Unselected tests, imports, studies and unlinked sources are not included.':requirement?'Selected check: '+requirement.title+' ('+requirement.id+'). The saved finding stays authoritative.':'Choose a saved project or engineering check.';
    $('#sd-rocket-ai-body').innerHTML='<section id="sd-ai-context-summary" class="sd-assistant-context-summary" aria-label="Selected saved evidence"></section><div class="sd-conversation-toolbar"><span id="sd-ai-thread-note" class="sd-small sd-muted"></span><button type="button" class="sd-mini-action" data-action="ai-new-conversation">New conversation</button><button type="button" class="sd-mini-action" data-action="ai-refresh">Refresh</button></div><div id="sd-ai-transcript"></div><section class="sd-assistant-compose sd-conversation-compose" aria-label="Ask about saved evidence"><label class="sd-field" for="sd-ai-question"><span class="sr-only">Your question</span><textarea id="sd-ai-question" class="sd-input sd-ai-question" rows="2" maxlength="2000" spellcheck="true" lang="en" autocorrect="off" autocapitalize="sentences" placeholder="Ask anything about this saved design…">'+esc(ai.question)+'</textarea></label><p class="sd-small sd-muted sd-conversation-key-hint">Enter to send · Shift + Enter for a new line</p><div id="sd-ai-attachments"></div><div class="sd-assistant-suggestions" aria-label="Draft a question"><button type="button" class="sd-mini-action" data-action="ai-simple-question">Explain simply</button><button type="button" class="sd-mini-action" data-action="ai-next-question">What next?</button><button type="button" class="sd-mini-action" data-action="ai-project-question">What changed?</button></div><p id="sd-ai-blocked" class="sd-notice" hidden></p><div class="sd-assistant-send-row"><span id="sd-ai-presence" class="sd-small"></span><span id="sd-ai-question-count" class="sd-small sd-muted"></span><button type="button" id="sd-ai-start" class="sd-button sd-primary" data-action="ai-start">Ask Nemotron</button></div><p class="sd-assistant-consent sd-small sd-muted">Your question, image notes and saved evidence go to Nebius. Images stay local.</p></section><div class="sd-chat-extra"><details id="sd-ai-advanced" class="sd-ai-advanced"><summary>Context, sources and settings</summary><div id="sd-ai-status">'+aiStatusMarkup()+'</div><div class="sd-ai-scope"><p>'+esc(context)+'</p><p class="sd-small sd-muted">'+esc(project().name)+' · R'+state.data.revision+'</p></div><p class="sd-small sd-ai-consent">The selected model <span id="sd-ai-consent-model">'+esc(providerModelLabel(selectedAIModel()?.model||ai.status?.model))+'</span> receives scoped saved inputs, findings, model definitions and pinned reference excerpts. A follow-up also includes bounded prior conversation text from this same evidence context. Opening or choosing makes no request.</p><p class="sd-small">Spelling suggestions use your browser settings. Right-click an underlined word to choose a correction; 6D never rewrites your question automatically.</p><div class="sd-action-row"><button type="button" class="sd-button" data-action="ai-source-question">Draft a reference question</button><button type="button" class="sd-button" data-action="sources">Open saved references</button><button type="button" class="sd-mini-action" data-action="ai-settings">Connection settings</button></div></details><details id="sd-ai-history-disclosure" class="sd-ai-history-disclosure"><summary>Saved conversations</summary><div id="sd-ai-history" class="sd-ai-history"></div></details></div>';
    const capturedContext=ai.context,disclosure=$('#sd-ai-history-disclosure');
    rocketUI.historyOpen??=new Map();disclosure.open=rocketUI.historyOpen.get(capturedContext)||false;
    disclosure.addEventListener('toggle',()=>{rocketUI.historyOpen.set(capturedContext,disclosure.open);if(rocketUI.historyOpen.size>50)rocketUI.historyOpen.delete(rocketUI.historyOpen.keys().next().value);});
    rocketUI.attachmentController=window.SixDAssistantAttachments.mount($('#sd-ai-attachments'),{contextKey:capturedContext,onChange:()=>updateAiControls()});
    if(ai.testSelection&&requirement){
      $('#sd-rocket-ai-body .sd-ai-scope').insertAdjacentHTML('beforeend','<p class="sd-small">Selected test row '+esc(ai.testSelection.rowNumber)+' from comparison <span class="sd-receipt">'+esc(ai.testSelection.comparisonId)+'</span>.</p><button type="button" class="sd-mini-action" data-action="clear-test-selection">Clear selected test row</button>'+testEvidenceSlot('assistant',[requirement.id]));hydrateTestLinks();
    }
    renderAssistantContextSummary();void refreshSourceLinks();renderAiHistory();updateAiControls();
    if(ai.loadedContext!==ai.context&&!ai.loading)void loadInvestigations();
  }
  function wholeProjectEvidenceMarkup(record) {
    const findings=record.canonical_findings||{}, rows=record.priorities||[], deps=record.evidence?.dependencies, changes=record.evidence?.changes;
    const context=(deps?'<p class="sd-small"><strong>Calculated:</strong> '+esc((deps.executed_model_ids||[]).join(', ')||'None')+'<br><strong>Reused:</strong> '+esc((deps.reused_model_ids||[]).join(', ')||'None')+'</p>':'')+(changes?'<details class="sd-source"><summary>Application-owned revision changes</summary><p>'+esc(changes.note)+'</p>'+(changes.comparison?'<p>Changed inputs: '+esc(changes.comparison.changed_inputs.join(', ')||'None')+'<br>Findings needing recheck after the change: '+esc(changes.comparison.previous_evidence_needs_rechecking.join(', ')||'None')+'</p>':'')+Object.entries(changes.requirement_directions||{}).map(([id,c])=>'<details><summary>'+esc(id)+'</summary>'+c.comparisons.filter(r=>r.direction!=='unchanged').map(r=>'<p><strong>'+esc(r.label)+'</strong> · '+esc(human(r.direction))+'<br>'+measure(r.before)+' → '+measure(r.after)+'</p>').join('')+'</details>').join('')+'</details>':'');
    return '<section class="sd-source"><h3>Application-owned project evidence</h3><p class="sd-small">'+esc(record.priority_policy||'Review queue; not a failure-risk ranking.')+'</p>'+rows.map(row=>'<details class="sd-source"><summary>'+chip(row.status)+' '+esc(row.title||row.requirement_id)+'</summary><p>'+esc(findings[row.requirement_id]?.reason||'')+'</p><dl class="sd-details-grid"><dt>Saved metric</dt><dd>'+measure(findings[row.requirement_id]?.evidence?.metric)+'</dd><dt>Declared criterion</dt><dd>'+esc(findings[row.requirement_id]?.evidence?.operator||'')+' '+measure(findings[row.requirement_id]?.evidence?.limit)+'</dd></dl>'+row.review_actions.map(a=>'<p><strong>'+esc(a.title)+'</strong><br>'+esc(a.action)+'</p>').join('')+'</details>').join('')+context+'<p class="sd-small sd-muted">Limited explanation guards do not establish semantic correctness. Independent human review remains pending.</p></section>';
  }
  function renderAssistant() {
    syncAssistantContext();if(ai.scope==='project'){renderProjectAssistant();return;}
    renderUnifiedAssistant(req(ai.requirementId));
  }
  function citationMarkup(id,record) {
    let label=id;const separator=id.indexOf(':'),kind=separator<0?id:id.slice(0,separator),item=separator<0?'':id.slice(separator+1);
    if(kind==='requirement')label=req(item)?.title || id;
    if(kind==='model')label='Model: '+human(item);
    if(kind==='recheck')label='Fresh calculation recheck: '+human(item);
    if(kind==='changes')label='Saved revision changes';
    if(record.scope==='project'&&id==='project')label='Captured project findings and references';
    if(record.scope==='project'&&id==='dependencies')label='Saved model scope and dependencies';
    return '<button type="button" class="sd-ai-citation" data-citation="'+esc(id)+'" data-investigation-record="'+esc(investigationId(record))+'">'+icon('file-check-2')+esc(label)+'</button>';
  }
  function guidanceMarkup(record) {
    const guidance=record.guidance;
    if(!guidance)return investigationActive(record)?'':'<p class="sd-small sd-muted">Evidence-based guidance is unavailable for this saved record. Its recorded finding and original interpretation remain available below.</p>';
    const gaps=Array.isArray(guidance.missing_information)?guidance.missing_information:[],steps=Array.isArray(guidance.review_actions)?guidance.review_actions:[],limits=Array.isArray(guidance.limitations)?guidance.limitations:[],ids=Array.isArray(guidance.evidence_ids)?guidance.evidence_ids:[];
    const basis=paths=>Array.isArray(paths)&&paths.length?'<details class="sd-ai-guidance-basis"><summary>Saved review basis</summary>'+paths.map(path=>'<p class="sd-receipt">'+esc(path)+'</p>').join('')+'</details>':'';
    const origin=record.guidance_origin==='current_app_read_only_projection'?'Generated by the current app from this investigation’s preserved review. The original investigation text is unchanged.':'Recorded with this investigation.';
    return '<section class="sd-ai-guidance" aria-label="Evidence-based guidance"><span class="sd-label">Evidence-based guidance · saved records</span>'+(guidance.canonical_assessment?.meaning?'<p>'+esc(guidance.canonical_assessment.meaning)+'</p>':'')+'<p class="sd-small sd-muted">'+esc(origin)+'</p>'+(steps.length?'<h4>Recommended next checks</h4><ol class="sd-ai-next-steps">'+steps.map(step=>'<li><strong>'+esc(step.title)+'</strong><p>'+esc(step.action)+'</p>'+basis(step.basis)+(Array.isArray(step.evidence_ids)&&step.evidence_ids.length?'<div class="sd-ai-citations">'+step.evidence_ids.map(id=>citationMarkup(id,record)).join('')+'</div>':'')+'</li>').join('')+'</ol>':'')+(gaps.length?'<h4>Information to obtain or verify</h4><ul class="sd-ai-gap-list">'+gaps.map(gap=>'<li><strong>'+esc(gap.item)+'</strong><p>'+esc(gap.why)+'</p>'+basis(gap.basis)+'</li>').join('')+'</ul>':'')+(limits.length?'<details class="sd-source"><summary>Scope and limits</summary><ul>'+limits.map(limit=>'<li>'+esc(limit)+'</li>').join('')+'</ul></details>':'')+(ids.length?'<div class="sd-ai-citations">'+ids.map(id=>citationMarkup(id,record)).join('')+'</div>':'')+'</section>';
  }
  function interpretationCaveatMarkup(record) {
    const flags=Array.isArray(record.explanation_quality?.flags)?record.explanation_quality.flags:[];
    const flagged=flags.filter(flag=>['warning','error'].includes(flag.severity)).map(flag=>flag.message).filter(Boolean);
    const caveat=record.interpretation_caveat || (flagged.length?flagged.join(' '):'This is the original model text. Use the recorded finding and evidence-based guidance to interpret it; it cannot establish additional engineering facts.');
    return '<p class="sd-ai-interpretation-caveat">'+esc(caveat)+'</p>'+(flags.length?'<details class="sd-ai-quality-flags"><summary>Explanation needs review · '+flags.length+' '+(flags.length===1?'flag':'flags')+'</summary><ul>'+flags.map(flag=>'<li>'+esc(flag.message)+'</li>').join('')+'</ul><p class="sd-small sd-muted">These limited checks can miss errors or flag acceptable wording. They do not establish semantic accuracy.</p></details>':'');
  }
  function investigationFailureMarkup(record) {
    if(!record.error&&record.state!=='failed')return '';
    const meanings={
      case_budget_exhausted:'This AI investigation reached its spending reservation ceiling before completing its explanation.',
      batch_budget_exhausted:'The comparison reached its spending reservation ceiling before this investigation completed.',
      cumulative_budget_exhausted:'The approved cumulative inference allowance has no remaining reservation capacity.',
      request_limit:'This AI investigation reached its request limit before completing the required workflow.',
      provider_transport_error:'A connection or provider request problem stopped this AI investigation.',
      provider_response_invalid:'The provider response did not match the accepted response format.',
      provider_output_limit:'The provider reached its output limit before returning a complete response.',
      invalid_action_response:'The model returned an unavailable or invalid investigation action.',
      explanation_rejected:'6D rejected the proposed AI explanation because it did not pass the evidence checks.',
      verification_sources_changed:'The calculation sources changed during this investigation. Run the supported checks again for the current sources.',
      recheck_mismatch:'The fresh calculation did not reproduce the saved result. Review its inputs, source versions and calculation evidence.',
      session_changed:'The private AI connection changed while this investigation was running.',
      budget_ledger_error:'The local reservation record could not be read or updated safely.',
      budget_approval_mismatch:'The configured allowance and saved approval record need review before another request.',
      budget_reservation_invalid:'The proposed request reservation was invalid and was stopped before sending.',
      configuration_error:'The provider configuration needs review before another investigation can start.',
      action_limit:'The investigation reached its bounded action limit before finishing.'
    };
    const meaning=meanings[record.error_code] || record.error || 'This AI investigation stopped before completion.';
    return '<div class="sd-error"><strong>AI investigation stopped</strong><p>'+esc(meaning)+'</p><p class="sd-small">The recorded engineering finding is shown separately below. Partial investigation evidence is preserved; no automatic retry followed.</p>'+(record.error_code?'<p class="sd-receipt">Reason: '+esc(record.error_code)+'</p>':'')+(record.error&&record.error!==meaning?'<details><summary>Recorded diagnostic</summary><p class="sd-small">'+esc(record.error)+'</p></details>':'')+'</div>';
  }
  // Fact values are rendered from captured records, never from model-authored HTML.
  // These links deliberately stay within the investigation's preserved snapshot.
  function capturedPointer(payload,pointer) {
    if(pointer==='')return {found:true,value:payload};
    if(typeof pointer!=='string'||!pointer.startsWith('/'))return {found:false};
    let value=payload;
    for(const raw of pointer.slice(1).split('/')){
      if(/~(?![01])/u.test(raw))return {found:false};
      const key=raw.replace(/~1/g,'/').replace(/~0/g,'~');
      if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {found:false};
      value=value[key];
    }
    return {found:true,value};
  }
  function recordedFacts(record) {
    const bundle=record.evidence_facts,all=Array.isArray(bundle?.facts)?bundle.facts:[];
    if(bundle?.schema!=='sixd.evidence-facts.v1')return {facts:[],byId:new Map(),invalid:0};
    if(['project_id','revision','run_id','review_digest','requirement_id'].some(key=>Object.hasOwn(record,key)&&record[key]!==bundle.scope?.[key])||(record.canonical_finding?.model_id&&record.canonical_finding.model_id!==bundle.scope?.model_id))return {facts:[],byId:new Map(),invalid:all.length};
    const counts=new Map();all.forEach(f=>{if(f&&typeof f.id==='string')counts.set(f.id,(counts.get(f.id)||0)+1);});
    const facts=all.filter(f=>{
      if(!f||!/^f[a-f0-9]{24}$/.test(f.id)||counts.get(f.id)!==1||typeof f.label!=='string'||!f.label||!['number','string','boolean'].includes(typeof f.value)||typeof f.value==='number'&&!Number.isFinite(f.value)||!(f.unit===null||typeof f.unit==='string')||typeof f.evidence_id!=='string'||typeof f.evidence_digest!=='string'||!Object.hasOwn(record.evidence||{},f.evidence_id))return false;
      const source=capturedPointer(record.evidence[f.evidence_id],f.pointer);
      return source.found&&Object.is(source.value,f.value);
    });
    return {facts,byId:new Map(facts.map(f=>[f.id,f])),invalid:all.length-facts.length};
  }
  const exactFact = fact => String(fact.value)+(fact.unit?' '+fact.unit:'');
  function factLink(fact,record,label) {
    return '<button type="button" class="sd-ai-fact-link" data-evidence-fact="'+esc(fact.id)+'" data-investigation-record="'+esc(investigationId(record))+'">'+esc(label||fact.label+' · '+exactFact(fact))+'</button>';
  }
  const factScopeNotes = bundle => (Array.isArray(bundle?.scope_notes)?bundle.scope_notes:[]).map(note=>'<p class="sd-small sd-muted">'+esc(note)+'</p>').join('');
  function factScopeMarkup(scope) {
    const labels={project_id:'Project',revision:'Saved revision',run_id:'Captured run',review_digest:'Review digest',requirement_id:'Requirement',model_id:'Model'};
    return '<dl class="sd-details-grid sd-ai-fact-scope">'+Object.entries(labels).map(([key,label])=>'<dt>'+label+'</dt><dd>'+esc(scope?.[key]??'Not recorded')+'</dd>').join('')+'</dl>';
  }
  function evidenceFactsMarkup(record) {
    const bundle=record.evidence_facts,{facts,invalid}=recordedFacts(record);
    if(!bundle)return investigationActive(record)?'':'<p class="sd-small sd-muted sd-ai-legacy-notice">Linked numerical facts are unavailable for this saved investigation. '+esc(record.evidence_facts_unavailable||'Its original text and captured evidence remain unchanged.')+'</p>';
    const origin=record.evidence_facts_origin==='current_app_read_only_projection'?'Read-only projection from this investigation’s captured evidence by the current app. The original receipt and explanation are unchanged.':'Facts recorded with this investigation.';
    const rows=facts.map(f=>'<tr><th scope="row">'+esc(f.label)+'<br>'+factLink(f,record,'Open captured source')+(f.context&&Object.keys(f.context).length?'<details class="sd-ai-fact-context"><summary>Saved context</summary><pre>'+esc(JSON.stringify(f.context,null,2))+'</pre></details>':'')+'</th><td class="sd-ai-fact-value">'+esc(exactFact(f))+'</td></tr>').join('');
    return '<section class="sd-ai-facts" aria-label="Recorded numerical evidence"><div class="sd-section-heading"><h4>Recorded numerical evidence</h4><span class="sd-chip">Deterministic saved values</span></div><p class="sd-small">These values come from captured records. AI interpretation is shown separately below.</p><p class="sd-small sd-muted">'+esc(origin)+'</p><details class="sd-source sd-ai-fact-provenance"><summary>Full saved scope and identity · R'+esc(bundle.scope?.revision??'unknown')+'</summary>'+factScopeMarkup(bundle.scope)+factScopeNotes(bundle)+'<p class="sd-receipt">Fact catalogue digest '+esc(bundle.digest||'Not recorded')+'</p>'+(bundle.coverage?'<p class="sd-small">'+esc(bundle.coverage)+'</p>':'')+'</details>'+(bundle.omitted_fact_count>0?'<p class="sd-notice">'+esc(bundle.omitted_fact_count)+' additional quantities are outside this bounded fact table. Inspect the full captured JSON for those records.</p>':'')+(invalid?'<p class="sd-notice">'+esc(invalid)+' fact '+(invalid===1?'entry was':'entries were')+' withheld because the captured source or identifier could not be matched. No replacement value was inferred.</p>':'')+(facts.length?'<div class="sd-table-wrap sd-ai-facts-scroll" tabindex="0" role="region" aria-label="Recorded numerical evidence table"><table class="sd-table"><caption>Exact captured values · select a source to inspect its saved context</caption><thead><tr><th scope="col">Recorded quantity and source</th><th scope="col">Exact value and unit</th></tr></thead><tbody>'+rows+'</tbody></table></div>':'<p class="sd-notice">No matched numerical facts are available for this captured evidence.</p>')+'</section>';
  }
  const numericalRoleLabels={calculated_metric:'Calculated requirement metric',declared_limit:'Declared requirement limit',position_grid_tolerance:'Declared position grid tolerance',velocity_grid_tolerance:'Declared velocity grid tolerance',position_difference_coarse_to_middle:'Position difference · coarse to middle',velocity_difference_coarse_to_middle:'Velocity difference · coarse to middle',position_difference_middle_to_fine:'Position difference · middle to fine',velocity_difference_middle_to_fine:'Velocity difference · middle to fine',same_adapter_reproduced:'Same-adapter reproducibility only',test_observation:'Original test observation',original_test_limit:'Original test criterion',original_test_prediction:'Original test prediction',test_agreement_tolerance:'Original test agreement tolerance',test_absolute_difference:'Original test absolute difference'};
  function rolePointer(role){
    const p='/recorded_evidence/numerical_accuracy/';
    const paths={calculated_metric:'/finding/evidence/metric/value',declared_limit:'/limit/value',position_grid_tolerance:p+'criteria/position_tolerance_m',velocity_grid_tolerance:p+'criteria/velocity_tolerance_m_s',same_adapter_reproduced:'/matches_saved_result',test_observation:'/selected_test_evidence/recorded/row/measurement_requirement/metric/value',original_test_limit:'/selected_test_evidence/recorded/row/measurement_requirement/limit/value',original_test_prediction:'/selected_test_evidence/recorded/row/prediction_agreement/prediction/value',test_agreement_tolerance:'/selected_test_evidence/recorded/row/prediction_agreement/tolerance/value',test_absolute_difference:'/selected_test_evidence/recorded/row/prediction_agreement/absolute_difference'};
    const m=role.match(/^(position|velocity)_difference_(coarse_to_middle|middle_to_fine)$/);
    return paths[role]||(m?p+'comparisons/'+(m[2]==='coarse_to_middle'?0:1)+'/'+(m[1]==='position'?'max_position_difference_m':'max_velocity_difference_m_s'):null);
  }
  function evidenceRolesMarkup(record){
    const roles=record.evidence_roles,{byId}=recordedFacts(record);
    if(roles?.schema!=='sixd.evidence-roles.v1'||roles.catalog_digest!==record.evidence_facts?.digest||['project_id','revision','run_id','review_digest','requirement_id','model_id'].some(k=>roles.scope?.[k]!==record.evidence_facts?.scope?.[k]))return '<p class="sd-notice">Application-owned numerical roles are unavailable for this captured investigation. No current source was substituted.</p>';
    const counts=new Map();for(const item of roles.roles||[])counts.set(item.role,(counts.get(item.role)||0)+1);
    const rows=(roles.roles||[]).flatMap(item=>{const fact=byId.get(item.fact_id);return fact&&counts.get(item.role)===1&&rolePointer(item.role)===fact.pointer?[{item,fact}]:[];});
    return '<section class="sd-ai-facts sd-ai-roles" aria-label="Application-owned numerical evidence"><h4>Numerical evidence · assigned by 6D</h4><p class="sd-small">Metric, limit and grid roles come from saved sources. The AI cannot select or edit these values.</p><p class="sd-small">Recorded criterion: '+esc(human(roles.canonical_status))+(roles.operator?' · '+esc(roles.operator):'')+' · R'+esc(roles.scope.revision)+'</p>'+(!rows.some(row=>row.item.role==='calculated_metric')?'<p class="sd-notice">No assessable calculated requirement metric is recorded. A declared limit alone does not establish satisfaction.</p>':'')+'<div class="sd-table-wrap"><table class="sd-table"><thead><tr><th>Recorded role</th><th>Saved value</th></tr></thead><tbody>'+rows.map(({item,fact})=>'<tr><th scope="row">'+esc(numericalRoleLabels[item.role])+'<br><span class="sd-small">'+esc(fact.label)+'</span><br>'+factLink(fact,record,'Open captured source')+'</th><td>'+esc(exactFact(fact))+'</td></tr>').join('')+'</tbody></table></div>'+((roles.roles||[]).length!==rows.length?'<p class="sd-notice">One or more inconsistent role bindings were withheld.</p>':'')+'<p class="sd-small sd-muted">These are recorded bounded-model results. Source binding and reproducibility do not establish physical validity.</p></section>';
  }
  function evidenceChangesMarkup(record){
    // Historical receipts keep their original interpretation; never derive a new
    // passing assessment for them from the currently selected revision.
    if(record.change_commentary_policy!=='application_changes_v1')return '';
    const context=record.evidence_change_context,source=record.evidence?.changes;
    if(context==null&&source==null)return '';
    const unavailable='<p class="sd-notice">Captured change directions are unavailable or inconsistent. No current-revision evidence was substituted.</p>';
    if(context?.schema!=='sixd.change-context.v1'||typeof context.available!=='boolean')return unavailable;
    if(!source||source.id!=='changes'||source.kind!=='changes'||context.source_evidence_id!=='changes'||!context.scope||!Array.isArray(context.comparisons)||!/^[a-f0-9]{64}$/.test(context.source_digest||''))return unavailable;
    if(['project_id','revision','run_id','review_digest'].some(key=>Object.hasOwn(record,key)&&(source[key]!==record[key]||context.scope[key]!==record[key])))return unavailable;
    if(!context.available)return source.comparison===null&&context.comparisons.length===0?'<section class="sd-ai-facts sd-ai-changes" aria-label="Captured revision changes"><h4>Revision changes · assigned by 6D</h4><p class="sd-small">No comparable before-and-after quantities are captured for this investigation. No change direction is inferred.</p></section>':unavailable;
    const comparison=source.comparison;
    if(!comparison||comparison.scope?.requirement_id!==record.requirement_id||comparison.scope?.model_id!==record.canonical_finding?.model_id||context.scope.requirement_id!==comparison.scope.requirement_id||context.scope.model_id!==comparison.scope.model_id||String(comparison.to_revision)!==String(record.revision)||context.scope.from_revision!==comparison.from_revision||context.scope.to_revision!==comparison.to_revision)return unavailable;
    const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
    const equal=(a,b)=>JSON.stringify(canonical(a))===JSON.stringify(canonical(b));
    const quantity=value=>value&&typeof value==='object'&&!Array.isArray(value)&&typeof value.value==='number'&&Number.isFinite(value.value)&&typeof value.unit==='string'&&value.unit.length>0;
    const exact=value=>quantity(value)?String(value.value)+' '+value.unit:'Unavailable';
    const directions={increased:'Increased',decreased:'Decreased',unchanged:'Unchanged',not_comparable:'Not comparable'};
    const beforeFinding=comparison.before?.finding,afterFinding=comparison.after?.finding;
    const counts=new Map();context.comparisons.forEach(row=>counts.set(row?.subject,(counts.get(row?.subject)||0)+1));
    const rows=context.comparisons.filter(row=>{
      if(!row||typeof row.subject!=='string'||counts.get(row.subject)!==1||row.source_evidence_id!=='changes'||!Object.hasOwn(directions,row.direction))return false;
      let suffix;
      if(row.subject==='declared_limit')suffix='/finding/evidence/limit';
      else if(row.subject==='calculated_metric')suffix='/finding/evidence/metric';
      else if(row.subject.startsWith('input:')&&row.subject.length>6)suffix='/input_records/'+row.subject.slice(6).replace(/~/g,'~0').replace(/\//g,'~1');
      else return false;
      if(row.before_pointer!=='/comparison/before'+suffix||row.after_pointer!=='/comparison/after'+suffix)return false;
      const before=capturedPointer(source,row.before_pointer),after=capturedPointer(source,row.after_pointer);
      if(!(before.found?equal(before.value,row.before):row.before===null)||!(after.found?equal(after.value,row.after):row.after===null))return false;
      const identityChanged=!row.subject.startsWith('input:')&&(beforeFinding?.metric==null||['metric','model_id'].some(key=>beforeFinding?.[key]!==afterFinding?.[key]));
      const operatorChanged=row.subject==='declared_limit'&&(beforeFinding?.evidence?.operator==null||beforeFinding.evidence.operator!==afterFinding?.evidence?.operator);
      const comparable=quantity(row.before)&&quantity(row.after)&&row.before.unit===row.after.unit&&!identityChanged&&!operatorChanged;
      const expected=comparable?(row.after.value>row.before.value?'increased':row.after.value<row.before.value?'decreased':'unchanged'):'not_comparable';
      return expected===row.direction;
    });
    return '<section class="sd-ai-facts sd-ai-changes" aria-label="Captured revision changes"><h4>Revision changes · assigned by 6D</h4><p class="sd-small">Exact before-and-after values and direction come from this investigation’s captured revision comparison. AI commentary cannot edit them. Numerical direction alone does not establish a physical cause.</p><div class="sd-ai-citations">'+citationMarkup('changes',record)+'</div>'+(rows.length?'<div class="sd-table-wrap" tabindex="0" role="region" aria-label="Captured before-and-after comparison"><table class="sd-table"><thead><tr><th scope="col">Recorded quantity</th><th scope="col">Before</th><th scope="col">After</th><th scope="col">Direction</th></tr></thead><tbody>'+rows.map(row=>'<tr><th scope="row">'+esc(row.subject==='declared_limit'?'Declared requirement limit':row.subject==='calculated_metric'?'Calculated requirement metric':row.label||row.subject)+'<details class="sd-source"><summary>Captured source paths</summary><p class="sd-receipt">'+esc(row.before_pointer)+' → '+esc(row.after_pointer)+'</p></details></th><td>'+esc(exact(row.before))+'</td><td>'+esc(exact(row.after))+'</td><td>'+esc(directions[row.direction])+'</td></tr>').join('')+'</tbody></table></div>':'<p class="sd-notice">No source-matched change rows are available.</p>')+(rows.length!==context.comparisons.length?'<p class="sd-notice">Inconsistent change rows were withheld. No replacement values or directions were inferred.</p>':'')+'<p class="sd-small sd-muted">Not comparable means the captured quantities cannot support a numeric direction, for example after a unit or metric identity change, or a changed limit operator. No unit conversion is assumed.</p><details class="sd-source"><summary>Captured comparison identity</summary>'+factScopeMarkup(context.scope)+'<p class="sd-receipt">Captured changes digest '+esc(context.source_digest)+'</p></details></section>';
  }
  function evidenceInterpretationMarkup(text,record) {
    if(record.evidence_facts_prose_policy==='application_roles_v1')return '<p class="sd-small sd-muted">Qualitative AI interpretation. Exact numerical roles are supplied separately by 6D.</p><p class="sd-ai-summary-text">'+esc(text)+'</p>';
    const {byId}=recordedFacts(record);let offset=0,html='',unknown=false,linked=false;
    // Only this narrow token syntax becomes a button. Every other character is escaped.
    for(const match of String(text).matchAll(/\[\[fact:([^\]\r\n]*)\]\]/g)){
      html+=esc(String(text).slice(offset,match.index));const fact=byId.get(match[1]);
      if(fact){html+=factLink(fact,record);linked=true;}
      else{html+='<span class="sd-ai-fact-unavailable">'+esc(match[0])+'</span>';unknown=true;}
      offset=match.index+match[0].length;
    }
    html+=esc(String(text).slice(offset));
    return (unknown?'<p class="sd-notice">An AI fact reference could not be matched to this investigation’s captured evidence. Its original token is shown unchanged; no other source was substituted.</p>':'')+(!linked?'<p class="sd-small sd-ai-legacy-notice">'+(record.evidence_facts_prose_policy?'This prose has no matched fact links.':'This original prose predates the linked-fact policy and has no matched fact links.')+' Numerical statements in it are not bound to the recorded values; inspect the captured sources.</p>':'')+'<p class="sd-ai-summary-text">'+html+'</p>';
  }
  function factSourceMarkup(record,factId) {
    const fact=recordedFacts(record).byId.get(factId);if(!fact)return '<p class="sd-notice">The requested fact cannot be matched to this investigation’s captured evidence. No current-revision source was substituted.</p>';
    const payload=record.evidence[fact.evidence_id],source=capturedPointer(payload,fact.pointer);
    return '<p class="sd-small">Captured evidence only. This source belongs to the saved investigation below; later project edits do not change it.</p><h3>'+esc(fact.label)+'</h3><p class="sd-ai-source-value">'+esc(exactFact(fact))+'</p>'+factScopeMarkup(record.evidence_facts.scope)+factScopeNotes(record.evidence_facts)+'<dl class="sd-details-grid sd-ai-fact-scope"><dt>Investigation</dt><dd>'+esc(investigationId(record))+'</dd><dt>Evidence identifier</dt><dd>'+esc(fact.evidence_id)+'</dd><dt>JSON pointer</dt><dd>'+esc(fact.pointer||'(payload root)')+'</dd><dt>Captured source digest</dt><dd>'+esc(fact.evidence_digest)+'</dd><dt>Fact identifier</dt><dd>'+esc(fact.id)+'</dd></dl>'+(fact.context&&Object.keys(fact.context).length?'<h4>Saved context</h4><pre>'+esc(JSON.stringify(fact.context,null,2))+'</pre>':'')+'<section class="sd-ai-exact-source" tabindex="-1" aria-label="Exact captured source value"><h4>Exact value at the captured pointer</h4><pre>'+esc(JSON.stringify(source.value,null,2))+'</pre></section><details class="sd-source" open><summary>Full captured evidence payload</summary><pre>'+esc(JSON.stringify(payload,null,2))+'</pre></details><p class="sd-small sd-muted">A source link establishes where this value was recorded. It does not establish the accuracy of the underlying physical model or the surrounding AI interpretation.</p>';
  }
  function showFactSource(record,factId) {
    let dialog=$('#sd-ai-fact-dialog');
    if(!dialog){dialog=document.createElement('dialog');dialog.id='sd-ai-fact-dialog';dialog.setAttribute('aria-labelledby','sd-ai-fact-title');root.append(dialog);}
    dialog.innerHTML='<div class="sd-dialog-header"><h2 id="sd-ai-fact-title">Captured fact source</h2><form method="dialog"><button type="submit" class="sd-button" aria-label="Close captured fact source">Close</button></form></div>'+factSourceMarkup(record,factId);
    if(!dialog.open)dialog.showModal();dialog.querySelector('.sd-ai-exact-source')?.focus({preventScroll:true});dialog.scrollTop=0;
  }
  // Pure escaped renderers also support isolated browser checks without API writes.
  window.SixDEvidenceFacts=Object.freeze({render:evidenceFactsMarkup,roles:evidenceRolesMarkup,changes:evidenceChangesMarkup,interpretation:evidenceInterpretationMarkup,source:factSourceMarkup,openSource:showFactSource});
  function rejectedInterpretationMarkup(record) {
    const rejected=record.rejected_interpretation;
    if(!rejected||typeof rejected.summary!=='string'||!rejected.summary)return '';
    const ids=Array.isArray(rejected.citations)?rejected.citations.filter(id=>typeof id==='string'&&Object.hasOwn(record.evidence || {},id)):[];
    const reasons=Array.isArray(rejected.reason_codes)?rejected.reason_codes.filter(code=>typeof code==='string'):[];
    const reasonMeanings={unbound_numeric_literal:'The explanation included a number without an exact captured fact link.',fact_catalog_mismatch:'The fact catalogue did not match the captured evidence and saved scope.',unknown_fact_reference:'An explanation reference did not identify a fact in this captured evidence.',change_direction_contradiction:'The explanation’s change description contradicted the captured before-and-after evidence.',change_context_mismatch:'The application-owned change context did not match this investigation’s captured revision evidence.'};
    return '<details class="sd-source sd-ai-rejected"><summary>Rejected AI explanation · inspect original text</summary><p class="sd-notice">This text was rejected by 6D’s evidence checks. Use the recorded engineering finding and evidence-based guidance above.</p>'+(reasons.length?'<p class="sd-small sd-muted">Checks: '+esc(reasons.map(code=>reasonMeanings[code]||human(code)).join(' · '))+'</p>':'')+'<div class="sd-ai-interpretation">'+evidenceInterpretationMarkup(rejected.summary,record)+'</div>'+(ids.length?'<h4>Evidence identifiers supplied with rejected text</h4><div class="sd-ai-citations">'+ids.map(id=>citationMarkup(id,record)).join('')+'</div>':'')+'<p class="sd-small sd-muted">These identifiers open the captured evidence. Their presence alone does not support every claim in the rejected explanation.</p></details>';
  }
  function frozenTestMarkup(record) {
    const bundle=record.test_evidence;if(!bundle)return '';
    const selected=bundle.selection||{},original=bundle.recorded||{},row=original.row||{},criterion=row.measurement_requirement||{},agreement=row.prediction_agreement||{};
    const exact=item=>item&&typeof item.value==='number'&&Number.isFinite(item.value)&&(!Number.isInteger(item.value)||Number.isSafeInteger(item.value))?esc(String(item.value)+' '+item.unit):'Unavailable';
    return '<section class="te-evidence sd-ai-frozen-test" aria-label="Captured test row"><h4>Captured test row · '+esc(row.measurement_id||'CSV row '+selected.row_number)+'</h4><p class="sd-small">Frozen with this investigation. Later revisions and comparisons do not update this evidence.</p><dl class="sd-details-grid"><dt>Original design finding</dt><dd>'+esc(human(row.canonical_status))+'</dd><dt>Measurement meets requirement</dt><dd>'+esc(human(criterion.status))+'</dd><dt>Prediction agreement</dt><dd>'+esc(human(agreement.status))+'</dd><dt>Recorded measurement</dt><dd>'+exact(criterion.metric)+'</dd><dt>Original criterion</dt><dd>'+esc(criterion.operator)+' '+exact(criterion.limit)+'</dd><dt>Saved prediction</dt><dd>'+exact(agreement.prediction)+'</dd><dt>Absolute tolerance</dt><dd>'+exact(agreement.tolerance)+'</dd><dt>Applicability at investigation</dt><dd>'+esc(human(bundle.applicability?.status))+'</dd></dl><p class="sd-small">Tested R'+esc(original.tested_revision)+' · '+esc(original.data_kind)+' · '+esc(original.source)+'</p><p class="sd-small">'+esc(original.test_conditions)+' Conditions relation: '+esc(original.conditions_match)+'. This declaration is unverified.</p><details class="sd-source"><summary>Captured row citation</summary><p class="sd-receipt">Comparison '+esc(selected.comparison_id)+'<br>'+esc(selected.pointer)+' · CSV row '+esc(selected.row_number)+'<br>Receipt '+esc(selected.receipt_digest)+'<br>CSV SHA-256 '+esc(selected.csv_sha256)+'<br>Original baseline run '+esc(original.baseline_run_id)+'<br>Original review '+esc(original.baseline_review_digest)+'<br>Scoped context '+esc(bundle.context_digest)+'</p></details><button type="button" class="sd-mini-action te-no-print" data-test-evidence-open="'+esc(selected.comparison_id)+'" data-test-evidence-row="'+esc(selected.row_number)+'">Open original comparison</button></section>';
  }
  function investigationMarkup(record) {
    const historical=record.review_digest!==currentRun()?.review?.digest;
    const events=Array.isArray(record.events)?record.events:[],citations=Array.isArray(record.citations)?record.citations:[];
    const evidence=Object.entries(record.evidence || {}),identity=investigationId(record);
    const activity=events.map(event=>'<li><strong>'+esc(human(event.action || event.state || 'Recorded update'))+'</strong>'+(Array.isArray(event.evidence_ids)&&event.evidence_ids.length?'<span>'+esc(event.evidence_ids.join(', '))+'</span>':'')+((event.at || event.timestamp)?'<small>'+esc(new Date(event.at || event.timestamp).toLocaleTimeString())+'</small>':'')+'</li>').join('');
    const captured=evidence.map(([id,value])=>'<details class="sd-ai-evidence" data-evidence-id="'+esc(id)+'" data-evidence-record="'+esc(identity)+'"><summary>'+esc(id)+'</summary><pre>'+esc(JSON.stringify(value,null,2))+'</pre></details>').join('');
    return '<article class="sd-ai-record">'+frozenTestMarkup(record)+capturedReferencesMarkup(record)+
      '<div class="sd-section-heading"><strong>'+esc(record.state==='failed'?'Investigation stopped':human(record.state))+'</strong><span class="sd-small sd-muted">'+(record.started_at?esc(new Date(record.started_at).toLocaleString()):'Queued')+'</span></div>'+
      '<p class="sd-ai-record-question">'+esc(record.question)+'</p>'+
      '<p class="sd-small sd-muted">Recorded model: '+esc(record.model?providerModelLabel(record.model):'Not recorded')+'</p>'+
      (record.provider_mode&&record.provider_mode!=='live_token_factory'?'<p class="sd-notice">Offline test provider · this is not a live NVIDIA response.</p>':'')+
      (historical?'<p class="sd-notice">This investigation refers to an earlier review receipt for this revision. Its evidence is preserved; it does not replace the current review.</p>':'')+
      (investigationActive(record)?'<p class="sd-ai-progress" role="status"><span class="sd-dot sd-amber"></span>'+esc(record.state==='queued'?'Queued on this local server.':'Investigation running. Recorded actions appear below.')+'</p>':'')+
      investigationFailureMarkup(record)+
      (record.canonical_finding?'<div class="sd-ai-verdict"><span class="sd-label">Recorded requirement finding</span>'+chip(findingStatus(record.canonical_finding))+'<p>'+esc(record.canonical_finding.reason)+'</p></div>':'')+
      (record.scope==='project'?wholeProjectEvidenceMarkup(record):guidanceMarkup(record))+
      (record.scope==='project'?'':record.evidence_facts_prose_policy==='application_roles_v1'?evidenceRolesMarkup(record)+'<details class="sd-source"><summary>All captured numerical facts</summary>'+evidenceFactsMarkup(record)+'</details>':evidenceFactsMarkup(record))+
      evidenceChangesMarkup(record)+
      rejectedInterpretationMarkup(record)+
      (record.summary?'<div class="sd-ai-interpretation"><span class="sd-label">Original AI interpretation · not a kernel verdict</span>'+interpretationCaveatMarkup(record)+(record.scope==='project'?'<p>'+esc(record.summary)+'</p>':evidenceInterpretationMarkup(record.summary,record))+'</div>':'')+
      (citations.length?'<h4>Evidence cited</h4><div class="sd-ai-citations">'+citations.map(id=>citationMarkup(id,record)).join('')+'</div>':'')+
      (evidence.length?'<details class="sd-source sd-ai-captured"><summary>Captured evidence records</summary>'+captured+'</details>':'')+
      (events.length?'<details class="sd-source" '+(investigationActive(record)?'open':'')+'><summary>Recorded activity · '+events.length+' events</summary><ol class="sd-ai-events">'+activity+'</ol></details>':'')+
      '<p class="sd-receipt">'+esc(identity)+'<br>Review '+esc(record.review_digest || 'Not available')+'<br>Accepted live responses: '+esc(record.live_model_calls ?? 0)+' · Request attempts: '+esc(record.request_attempts ?? 0)+'</p>'+
      '<button type="button" class="sd-mini-action" data-ai-download="'+esc(identity)+'">Download investigation JSON '+icon('download')+'</button></article>';
  }
  function capturedReferencesMarkup(record){
    const captured=record.project_sources;if(!captured)return '';
    if(captured.schema!=='sixd.assistant-sources.v1'||captured.project_id!==record.project_id||captured.revision!==record.revision||captured.requirement_id!==record.requirement_id||captured.review_digest!==record.review_digest||!Array.isArray(captured.links))return '<p class="sd-notice">The captured reference scope is inconsistent. No current references were substituted.</p>';
    const modelId=record.canonical_finding?.model_id;
    const current=record.review_digest===currentRun()?.review?.digest&&record.run_id===currentRun()?.run_id&&!state.draft&&latest()&&!investigationActive(record);
    const track=current&&['not_met','not_assessed'].includes(record.canonical_finding?.status)?'<button type="button" class="sd-mini-action" data-track-action="'+esc('finding:'+record.requirement_id)+'">Track follow-up for this finding</button>':'';
    return '<details class="sd-source sd-ai-reference-snapshot"><summary>References captured for this investigation ('+captured.links.length+')</summary><p class="sd-small">These are pinned supplemental references. Later library edits do not replace them, and their contents do not change the numerical finding.</p>'+window.SixDSources.render({...captured,context:'saved'},{requirementIds:[record.requirement_id],modelIds:modelId?[modelId]:[captured.model_id]})+(captured.omitted_links?'<p class="sd-notice">'+esc(captured.omitted_links)+' relevant links were omitted by the captured context bound.</p>':'')+'<p class="sd-receipt">Original library '+esc(captured.library_digest)+'<br>Captured context '+esc(captured.digest)+'</p>'+track+'</details>';
  }
  function conversationSource(){
    const profile=sourceLinks.key===sourceLinkKey()?sourceLinks.profile:null;
    return profile?.context==='saved'&&profile.project_id===state.data?.project_id&&profile.revision===state.data?.revision&&profile.run_id===currentRun()?.run_id?profile:null;
  }
  function conversationContext(){return {projectId:state.data?.project_id,revision:state.data?.revision,runId:currentRun()?.run_id,reviewDigest:currentRun()?.review?.digest,scope:ai.scope,requirementId:ai.scope==='project'?'__project__':ai.requirementId,testSelection:assistantDescriptor().testSelection,sourceDigest:conversationSource()?.digest,requirementIds:allReqs().map(item=>item.id)};}
  function compatibleConversation(record){return window.SixDAssistantConversation.compatibleParent(record,conversationContext());}
  function matchingConversation(record){return window.SixDAssistantConversation.matchesContext(record,conversationContext());}
  function conversationHead(){
    if(!rocketUI.threadHeads.has(ai.context)&&ai.loadedContext===ai.context&&(!ai.records.length||conversationSource())){
      const record=ai.records.find(item=>compatibleConversation(item)||investigationActive(item)&&matchingConversation(item));rocketUI.threadHeads.set(ai.context,record?investigationId(record):null);
    }
    return ai.records.find(record=>investigationId(record)===rocketUI.threadHeads.get(ai.context))||null;
  }
  function conversationRecords(){
    const head=conversationHead();if(!head)return [];
    const records=new Map(ai.records.map(record=>[investigationId(record),record])),seen=new Set(),rows=[];
    let record=head;
    while(record&&!seen.has(investigationId(record))&&rows.length<50){seen.add(investigationId(record));rows.unshift(record);record=records.get(record.conversation_context?.parent_investigation_id);}
    return rows;
  }
  function conversationParent(){return conversationRecords().filter(record=>compatibleConversation(record)).at(-1)||null;}
  function questionPayload(){
    const attachment=rocketUI.attachmentController?.snapshot();
    return ai.question.trim()+(attachment?.description?.trim()?'\n\nUser-supplied image notes (unverified text; the model has not seen the image):\n'+attachment.description.trim():'');
  }
  function renderAiHistory() {
    const container=$('#sd-ai-history'),transcript=$('#sd-ai-transcript');if(!container||!transcript)return;
    const summary=$('#sd-ai-history-disclosure > summary');if(summary)summary.textContent='Saved conversations ('+ai.records.length+' recorded turns)';
    const rows=conversationRecords();
    const turns=rows.map(record=>{
      const current=matchingConversation(record);
      let canonical='';
      if(record.canonical_finding){const f=record.canonical_finding;canonical='<span>Saved criterion: '+chip(findingStatus(f))+'</span>'+(f.evidence?'<p>'+measure(f.evidence.metric)+' compared with '+esc(f.evidence.operator)+' '+measure(f.evidence.limit)+'</p>':'');}
      else if(record.scope==='project'){const values=Object.values(record.canonical_findings||{});canonical='<span>Saved project: '+values.filter(f=>f.status==='met').length+' criteria met · '+values.filter(f=>f.status==='not_met').length+' unmet · '+values.filter(f=>f.status==='not_assessed').length+' not assessed.</span>';}
      const answer=record.summary?(record.scope==='project'?'<p class="sd-ai-summary-text">'+esc(record.summary)+'</p>':record.evidence_facts_prose_policy==='application_roles_v1'?'<p class="sd-ai-summary-text">'+esc(record.summary)+'</p>':evidenceInterpretationMarkup(record.summary,record)):'';
      return {id:investigationId(record),question:record.question,modelLabel:providerModelLabel(record.model),timeLabel:record.created_at?new Date(record.created_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}):'',state:record.state,answerHtml:answer,canonicalHtml:canonical,detailsHtml:investigationMarkup(record),failureHtml:investigationFailureMarkup(record),notice:!current?'This saved answer uses a different test or reference context. Your next question starts fresh with the selected saved evidence.':record.provider_mode&&record.provider_mode!=='live_token_factory'?'Offline test provider; not a live model response.':''};
    });
    const openIds=new Set([...transcript.querySelectorAll('details[data-conversation-details][open]')].map(node=>node.dataset.conversationDetails));
    const last=turns.at(-1),turnKey=last?last.id+':'+last.state:'';const previousTurn=transcript.dataset.lastTurn;
    const html=(ai.error?'<p class="sd-error" role="alert">'+esc(ai.error)+'</p>':'')+window.SixDAssistantConversation.render({turns,emptyMessage:ai.loading?'Reading your saved conversations…':'Ask about a result, an engineering term or the next check. You can follow up in the same conversation.'});
    if(transcript.dataset.rendered!==html){transcript.innerHTML=html;transcript.dataset.rendered=html;transcript.querySelectorAll('details[data-conversation-details]').forEach(node=>{if(openIds.has(node.dataset.conversationDetails))node.open=true;});icons();}
    transcript.dataset.lastTurn=turnKey;
    const suggestions=$('#sd-rocket-ai-body .sd-assistant-suggestions');if(suggestions)suggestions.hidden=rows.length>0;
    if(last?.state==='completed'&&turnKey!==previousTurn&&!openIds.size)requestAnimationFrame(()=>{const answer=transcript.querySelector('.sd-conversation-turn:last-child .sd-conversation-answer');if(answer)transcript.scrollTop+=answer.getBoundingClientRect().top-transcript.getBoundingClientRect().top;});
    const note=$('#sd-ai-thread-note');if(note)note.textContent=rows.length?(conversationParent()?'Follow up below · same saved evidence'+(conversationHead()?.conversation_context?.omitted_turn_count?' · recent turns sent':''):'Saved conversation · next question starts fresh'):'New conversation · same saved evidence';
    const archive=ai.records.map(record=>'<button type="button" class="sd-saved-conversation" data-ai-resume="'+esc(investigationId(record))+'"><strong>'+esc((record.question||'Saved question').slice(0,140))+'</strong><span>'+esc(providerModelLabel(record.model))+' · '+esc(human(record.state))+'</span></button>').join('');
    if(container.dataset.rendered!==archive){container.innerHTML=archive;container.dataset.rendered=archive;}
    updateAiControls();
  }
  async function openAssistant(requirementId) {
    openRocket({scope:'requirement',requirementId});
  }
  async function loadInvestigations() {
    if(!state.data||!ai.requirementId)return;
    stopInvestigationPolling();const generation=ai.generation,context=ai.context;
    ai.loading=true;ai.error='';renderAiHistory();ai.controller=new AbortController();
    try{
      const payload=await api('/api/investigations'+query(state.data.project_id,state.data.revision)+(ai.scope==='project'?'&scope=project':'&scope=requirement&requirement_id='+encodeURIComponent(ai.requirementId)),undefined,{signal:ai.controller.signal});
      if(generation!==ai.generation||context!==ai.context)return;
      ai.records=Array.isArray(payload.investigations)?payload.investigations:[];
    }catch(error){if(error.name!=='AbortError'&&generation===ai.generation)ai.error='Saved investigations could not be read. '+error.message;}
    finally{if(generation===ai.generation){ai.loading=false;ai.loadedContext=context;renderAiHistory();scheduleInvestigationPoll(generation,context);}}
  }
  function scheduleInvestigationPoll(generation,context) {
    clearTimeout(ai.timer);
    if(ai.records.some(investigationActive))ai.timer=setTimeout(()=>void pollInvestigations(generation,context),1200);
  }
  async function pollInvestigations(generation,context) {
    if(generation!==ai.generation||context!==ai.context)return;
    const active=ai.records.filter(investigationActive);ai.controller=new AbortController();
    try{
      const updates=await Promise.all(active.map(record=>api('/api/investigations/'+encodeURIComponent(investigationId(record)),undefined,{signal:ai.controller.signal})));
      if(generation!==ai.generation||context!==ai.context)return;
      ai.records=ai.records.map(record=>updates.find(update=>investigationId(update)===investigationId(record)) || record);ai.error='';renderAiHistory();
      if(!ai.records.some(investigationActive))await refreshAiStatus();
      scheduleInvestigationPoll(generation,context);
    }catch(error){if(error.name!=='AbortError'&&generation===ai.generation){ai.error='Status updates paused. The server may still be working; choose Refresh to read the saved state. '+error.message;renderAiHistory();}}
  }
  async function startInvestigation() {
    syncAssistantContext();const blocked=aiBlockedReason();
    if(blocked||ai.starting||rocketUI.attachmentController?.isBusy()||!ai.question.trim()||questionPayload().length>2000||rocketUI.attachmentController?.snapshot().present&&!rocketUI.attachmentController.snapshot().description.trim()){updateAiControls();return;}
    const context=ai.context;ai.starting=true;ai.error='';updateAiControls();
    try{
      const selection=ai.testSelection;
      const chosen=selectedAIModel();
      if(!chosen)throw Error('Choose an available investigation model before starting.');
      const record=await api('/api/investigations',{project_id:state.data.project_id,revision:state.data.revision,...(ai.scope==='project'?{scope:'project'}:{requirement_id:ai.requirementId}),question:questionPayload(),model_choice:chosen.id,...(conversationParent()?{parent_investigation_id:investigationId(conversationParent())}:{}),...(selection?{test_comparison_id:selection.comparisonId,test_row_number:selection.rowNumber}:{})});
      if(context!==ai.context)return;
      rocketUI.threadHeads.set(context,investigationId(record));ai.question='';rocketUI.questionDrafts.set(context,'');const question=$('#sd-ai-question');if(question)question.value='';rocketUI.attachmentController?.clear();ai.records=[record,...ai.records.filter(item=>investigationId(item)!==investigationId(record))];renderAiHistory();
      scheduleInvestigationPoll(ai.generation,context);await refreshAiStatus();
    }catch(error){if(context===ai.context){ai.error='The investigation was not started or could not be confirmed. Refresh saved investigations before trying again. '+error.message;renderAiHistory();}}
    finally{if(context===ai.context){ai.starting=false;updateAiControls();}}
  }
  function openTavilySettings(){
    if(rocketUI.researchBusy){message('Wait for the current reference operation before changing its connection.');return;}
    disposeRocketResearch();
    let dialog=$('#sd-tavily-dialog');
    if(!dialog){dialog=document.createElement('dialog');dialog.id='sd-tavily-dialog';dialog.setAttribute('aria-label','Owner Tavily connection');dialog.innerHTML='<div class="sd-dialog-header"><h2>Tavily connection</h2><button type="button" class="sd-icon-button" data-tavily-close aria-label="Close Tavily connection">×</button></div><div id="sd-tavily-settings"></div>';root.append(dialog);dialog.querySelector('[data-tavily-close]').onclick=()=>dialog.close();dialog.addEventListener('close',()=>{window.SixDResearch.unmount();$('#sd-tavily-settings').replaceChildren();});}
    window.SixDResearch.mount($('#sd-tavily-settings'),{api,connectionOnly:true,projectId:state.data.project_id,revision:state.data.revision,hasDraft:!!state.draft,canEdit:latest()});dialog.showModal();
  }
  async function showAiSettings() {
    $('#sd-ai-key').value='';$('#sd-ai-remember').checked=false;$('#sd-ai-connect-error').hidden=true;$('#sd-ai-evaluation-status').innerHTML=evaluationStatusMarkup();$('#sd-ai-connect-dialog').showModal();await Promise.all([refreshAiStatus(),refreshEvaluationStatus()]);
  }
  async function connectAi(disconnect=false,forget=false) {
    if(ai.connecting)return;
    const input=$('#sd-ai-key');if(!disconnect&&!forget&&!input.value.trim()){$('#sd-ai-connect-error').textContent='Enter the key privately in this field.';$('#sd-ai-connect-error').hidden=false;return;}
    ai.connecting=true;$('#sd-ai-connect-button').disabled=true;$('#sd-ai-disconnect-button').disabled=true;$('#sd-ai-forget-button').disabled=true;$('#sd-ai-remember').disabled=true;$('#sd-ai-connect-error').hidden=true;
    try{
      const pending=api(forget?'/api/ai/forget':disconnect?'/api/ai/disconnect':'/api/ai/connect',disconnect||forget?{}:{api_key:input.value.trim(),remember:$('#sd-ai-remember').checked});input.value='';
      ai.status=await pending;await refreshAiStatus();message(forget?(ai.status?.key_present?'Saved key forgotten. The current server session remains connected.':'Saved key forgotten. No key is connected.'):disconnect?'Nebius key disconnected and any remembered copy removed.':ai.status?.key_remembered?'Nebius key connected and remembered on this device. No inference request was made.':'Nebius key connected for this session. No inference request was made.');
    }catch{input.value='';$('#sd-ai-connect-error').textContent=forget?'The saved copy could not be removed. Refresh connection settings.':disconnect?'The disconnect could not be confirmed. Refresh connection settings.':'The key could not be connected. Check your local provider configuration and key, then try again. No key value is shown or saved in the browser.';$('#sd-ai-connect-error').hidden=false;}
    finally{ai.connecting=false;$('#sd-ai-connect-button').disabled=false;$('#sd-ai-disconnect-button').disabled=(!ai.status?.key_present&&!ai.status?.key_remembered);$('#sd-ai-forget-button').disabled=!ai.status?.key_remembered;$('#sd-ai-remember').disabled=!ai.status?.remember_supported;updateAiControls();}
  }
  function openCitation(id,recordId) {
    const record=ai.records.find(item=>investigationId(item)===recordId);if(!record)return;
    const payload=record.evidence?.[id],split=id.indexOf(':'),kind=payload?.kind || (split<0?id:id.slice(0,split)),item=payload?.requirement?.id || payload?.model?.id || payload?.model_id || (split<0?'':id.slice(split+1));
    if(record.scope==='project'||record.review_digest!==currentRun()?.review?.digest || kind==='recheck'){
      const captured=[...root.querySelectorAll('[data-evidence-id]')].find(el=>el.dataset.evidenceId===id&&el.dataset.evidenceRecord===recordId);
      if(captured){captured.closest('.sd-ai-captured').open=true;captured.open=true;captured.querySelector('summary').focus();captured.scrollIntoView({block:'nearest'});}
      else message('The citation is preserved in the investigation JSON.');
      return;
    }
    if(kind==='changes'){state.page='changes';render();return;}
    if(kind==='requirement'&&req(item)){state.panel='evidence';select('requirement',item);return;}
    if((kind==='model'||kind==='recheck')&&model(item)){state.panel='evidence';select('model',item);return;}
    if(kind==='recheck'&&req(item)){state.panel='evidence';select('requirement',item);return;}
    message('The cited record is preserved under Captured evidence records in this investigation.');
  }
  async function showImport(preferredTemplate) {
    if(state.draft){message('Save or discard the current draft before importing another project.');return;}
    clearError();const dialog=$('#sd-import-dialog');$('#sd-import-error').hidden=true;
    $('#sd-template-list').innerHTML='<p class="sd-small sd-muted">Loading templates…</p>';dialog.showModal();
    try{const payload=await api('/api/templates');state.templates=payload.templates || [];$('#sd-template-list').innerHTML=state.templates.map((item,i)=>'<button type="button" class="sd-button" data-template="'+i+'"><span>'+esc(item.name || item.id)+'</span>'+icon('arrow-up-right')+'</button>').join('');if(preferredTemplate){const template=state.templates.find(item=>item.id===preferredTemplate);if(template)stageImport(template.project,true);}icons();}catch(error){importError(error);}
  }
  function importError(error) {$('#sd-import-error').textContent=error.message || String(error);$('#sd-import-error').hidden=false;}
  function showSpreadsheetImport() {
    if(state.draft){message('Save or discard the current draft before importing another project.');return;}
    $('#sd-import-dialog').close();
    window.SixDSpreadsheetIntake.open({api,onCreated:async view=>{
      state.data=view;state.request++;state.draft=null;state.impact=null;invalidatePreflight();
      state.system='overview';state.selected=defaultSelection();state.page='system';state.panel='details';
      await refreshProjects();resetCamera();render();
      message('Spreadsheet project saved locally. Run checks to calculate its engineering evidence.');
    }});
  }
  function stageImport(candidate,fromTemplate=false) {
    if(!candidate || candidate.schema!=='sixd.project.v1')throw new Error('Select a sixd.project.v1 project JSON file.');
    state.importing=copy(candidate);$('#sd-import-staging').hidden=false;
    let id=candidate.project_id || 'my-space-project';if(fromTemplate || state.projects.some(item=>item.project_id===id)){let index=1;while(state.projects.some(item=>item.project_id===id+'-'+index))index++;id+='-'+index;}
    $('#sd-import-id').value=id;$('#sd-import-name').value=candidate.name || 'Space engineering project';$('#sd-import-summary').textContent=Object.keys(candidate.inputs || {}).length+' input records · '+(candidate.models?.length||0)+' model mappings · '+(candidate.requirements?.length||0)+' requirements. Calculations will run after creation.';$('#sd-import-error').hidden=true;
  }
  async function download(url,filename) {
    const payload=await api(url);const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});saveBlob(blob,filename);
  }
  function saveBlob(blob,filename) {const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  async function showNewProject() {
    if(dirty()&&!window.confirm('Discard unsaved draft changes to create a new project?'))return;
    state.draft=null;state.impact=null;invalidatePreflight();render();
    $('#sd-new-form').reset();$('#sd-new-error').hidden=true;
    $('#sd-new-id').value='space-project-'+(window.crypto?.randomUUID?.().slice(0,8) || Date.now().toString(36));
    $('#sd-new-stage').innerHTML=option('','Select a stage','')+['design','simulation','physical_test','operation'].map(stage=>option(stage,human(stage),'')).join('');
    $('#sd-new-dialog').showModal();
    try{await loadCatalog();if($('#sd-new-dialog').open){const selected=$('#sd-new-stage').value;$('#sd-new-stage').innerHTML=option('','Select a stage',selected)+author.catalog.lifecycle_stages.map(stage=>option(stage,human(stage),selected)).join('');}}
    catch(error){$('#sd-new-error').textContent=error.message;$('#sd-new-error').hidden=false;}
  }
  async function createEmptyProject() {
    const form=$('#sd-new-form');if(!form.reportValidity())return;
    const fields=Object.fromEntries(new FormData(form));for(const key of Object.keys(fields))fields[key]=fields[key].trim();
    if(!fields.project_id||!fields.name||!fields.description||!fields.lifecycle_stage){$('#sd-new-error').textContent='Provide the project ID, name, purpose and assumptions, and an explicit lifecycle stage.';$('#sd-new-error').hidden=false;return;}
    if(state.projects.some(p=>p.project_id===fields.project_id)){$('#sd-new-error').textContent='This project ID is already saved. Choose a unique ID.';$('#sd-new-error').hidden=false;return;}
    const candidate={schema:'sixd.project.v1',...fields,revision:'1',inputs:{},models:[],requirements:[]};
    await perform(async()=>{
      try{const data=await api('/api/projects',{project:candidate});stopInvestigationPolling();state.request++;state.data=data;state.draft=null;state.impact=null;state.system='overview';state.selected=null;state.page='authoring';state.panel='details';state.trajectory=null;invalidatePreflight();await refreshProjects();$('#sd-new-dialog').close();resetCamera();void refreshPreflight();}
      catch(error){$('#sd-new-error').textContent=error.message;$('#sd-new-error').hidden=false;throw error;}
    },'Empty R1 saved locally. Choose Edit draft to add your explicit engineering setup.');
  }
  async function action(name) {
    if(rocket?.isOpen()&&['sources','actions','owner-settings','ai-settings'].includes(name))rocket.close();
    const pageAction=['projects','engineering','analysis','evidence','setup','owner-settings','ai-settings','system','review-home','guided-overview','guided-table','guided-latest','report','changes','back','systems','chains','attitude','powered-flight','vertical-mode','guided-ascent','staged-ascent','power','sources','actions','coverage','comparison','simulation','scenarios','envelopes','simulation-imports','test-data','author-project','project-investigate','new-project','import','rocket-reference','ai-quality'];
    if(state.stagedProfileEdit&&pageAction.includes(name)){message('Apply or cancel the open thrust-profile edit before navigating. Your edits are still open.');return;}
    if(name==='navigation-back'){if(navigation?.canBack)navigation.back();return;}
    if(['projects','engineering','analysis','evidence','setup','system'].includes(name)){
      state.page=name;state.panel='details';stopInvestigationPolling();root.classList.remove('sd-tree-open');render();return;
    }
    root.querySelectorAll('details.sd-tool-menu[open]').forEach(el=>el.open=false);
    if(name==='ai-quality'){state.page='ai-quality';stopInvestigationPolling();render();return;}
    if(name==='review-home'){state.page='review-home';stopInvestigationPolling();render();return;}
    if(name==='guided-toggle'||name==='guided-close'){
      reviewGuide.open=name==='guided-close'?false:!reviewGuide.open;
      try{localStorage.setItem('sixd.review-guide.dismissed',reviewGuide.open?'no':'yes');}catch{}
      try{localStorage.setItem('sixd.review-guide.open',reviewGuide.open?'yes':'no');}catch{}
      render();if(reviewGuide.open)$('#sd-review-guide').scrollIntoView({block:'nearest'});return;
    }
    if(name==='guided-reference'){await showImport('baseline');return;}
    if(name==='guided-inputs'){state.page='system';state.system='overview';state.view='table';state.panel='details';stopInvestigationPolling();render();$('#sd-view-content').scrollIntoView({block:'start'});return;}
    if(name==='guided-latest'){await perform(()=>load(state.data.project_id));return;}

    if(name==='tree'){window.SixDSidebar.toggle();return;}
    if(name==='new-project'){await showNewProject();return;}
    if(name==='close-new'){window.SixDOverlayDismiss.requestClose($('#sd-new-dialog'),'close-button');return;}
    if(name==='close-author-editor'){window.SixDOverlayDismiss.requestClose($('#sd-author-dialog'),'close-button');return;}
    if(name==='close-import'){$('#sd-import-dialog').close();return;}
    if(name==='owner-settings'||name==='ai-settings'){state.page='owner-settings';state.panel='details';stopInvestigationPolling();render();return;}
    if(name==='manage-nebius'){if(!state.hosted)await showAiSettings();return;}
    if(name==='manage-tavily'){if(!state.hosted)openTavilySettings();return;}
    if(name==='ai-source-question'){
      syncAssistantContext();if(!req(ai.requirementId))return;
      ai.question='Explain this saved finding and how its linked references relate to the declared requirement and model assumptions. Identify stale links, missing support and a concrete next engineering check. Treat references as unverified supplemental context; preserve the recorded finding.';
      const input=$('#sd-ai-question');if(input){input.value=ai.question;input.focus();}updateAiControls();return;
    }
    if(name==='workflow-evaluation-refresh'){await refreshEvaluationStatus();return;}
    if(name==='ai-close-settings'){$('#sd-ai-key').value='';$('#sd-ai-connect-dialog').close();return;}
    if(name==='ai-connect'||name==='ai-disconnect'||name==='ai-forget'){await connectAi(name==='ai-disconnect',name==='ai-forget');return;}
    if(name==='refresh-test-evidence'){await refreshTestLinks(true);return;}
    if(name==='refresh-interfaces'){await refreshInterfaceLinks(true);return;}
    if(name==='sources'){state.page='sources';state.panel='details';stopInvestigationPolling();render();return;}
    if(name==='actions'){state.page='actions';state.panel='details';stopInvestigationPolling();render();return;}
    if(name==='coverage'){state.page='coverage';state.panel='details';stopInvestigationPolling();render();return;}
    if(name==='comparison'){state.page='comparison';state.panel='details';stopInvestigationPolling();render();return;}
    if(name==='systems'){state.page='systems';state.panel='details';stopInvestigationPolling();render();return;}
    if(name==='chains'){
      if($('#sd-author-dialog').open){$('#sd-author-dialog').close();author.editor=null;}
      state.page='chains';state.panel='details';stopInvestigationPolling();render();
      try{await loadCatalog();if(state.page==='chains')renderMain();}catch(error){showError(error);}
      return;
    }
    if(name==='attitude'){if($('#sd-author-dialog').open){$('#sd-author-dialog').close();author.editor=null;}state.page='attitude';state.panel='details';stopInvestigationPolling();render();return;}
    if(['powered-flight','vertical-mode','guided-ascent','staged-ascent'].includes(name)){if($('#sd-author-dialog').open){$('#sd-author-dialog').close();author.editor=null;}state.stagedProfileEdit=null;state.page=name==='staged-ascent'||name==='powered-flight'&&allModels().some(m=>m.type==='staged_ascent')?'staged-ascent':name==='guided-ascent'||name==='powered-flight'&&allModels().some(m=>m.type==='guided_ascent')?'guided-ascent':'powered-flight';state.panel='details';stopInvestigationPolling();render();return;}
    if(name==='power'){if($('#sd-author-dialog').open){$('#sd-author-dialog').close();author.editor=null;}state.page='power';state.panel='details';stopInvestigationPolling();render();return;}
    if(name==='clear-test-selection'){const question=ai.question;rocketUI.parkedTests.delete(testParkKey(ai.requirementId));ai.testSelection=null;syncAssistantContext();ai.question=question;rocketUI.notice='Test row removed. Your question was kept; review it before asking.';renderRocket(true);return;}
    if(name==='ai-use-page-context'){changeAssistantContext(pageAssistantIntent(),true);renderRocket(true);return;}
    if(name==='export-review'){
      if(state.draft||!currentRun()||testLinks.key!==testLinkKey()||!testLinks.profile||interfaceLinks.key!==testLinkKey()||!interfaceLinks.profile||sourceLinks.key!==sourceLinkKey()||!sourceLinks.profile||actionLinks.key!==actionLinkKey()||!actionLinks.profile||envelopeLinks.key!==testLinkKey()||!envelopeLinks.profile||seriesLinks.key!==testLinkKey()||!seriesLinks.profile||coverageLinks.key!==sourceLinkKey()||!coverageLinks.profile){showError(Error('Wait for current coverage and evidence, references and actions before exporting the combined review.'));return;}
      const key=testLinkKey(),projectId=state.data.project_id,revision=state.data.revision,profile=testLinks.profile;
      const interfaceProfile=interfaceLinks.profile,sourceProfile=sourceLinks.profile,actionProfile=actionLinks.profile,coverageProfile=coverageLinks.profile,seriesProfile=seriesLinks.profile,envelopeProfile=envelopeLinks.profile;
      await perform(async()=>{const snapshot=await api('/api/engineering-review-export'+query(projectId,revision));if(key!==testLinkKey()||!same(snapshot.test_evidence,profile)||(snapshot.workspace.system_interfaces&&snapshot.workspace.system_interfaces.digest!==interfaceProfile.digest)||snapshot.project_sources?.digest!==sourceProfile.digest||snapshot.engineering_actions?.digest!==actionProfile.digest||snapshot.engineering_coverage?.digest!==coverageProfile.digest||snapshot.simulation_imports?.digest!==seriesProfile.digest||snapshot.operating_envelopes?.digest!==envelopeProfile.digest){void refreshEnvelopes(true);void refreshSeries(true);void refreshCoverage(true);void refreshSourceLinks(true);void refreshActionLinks(true);throw Error('Evidence, references or actions changed. Refresh the report before exporting.');}saveBlob(new Blob([JSON.stringify(snapshot,null,2)],{type:'application/json'}),'6d-combined-review-r'+revision+'.json');});return;
    }
    if(name==='project-investigate'){openRocket({scope:'project'});return;}
    if(name==='requirement-investigate'){openRocket({scope:'requirement'});return;}
    if(name==='ai-simple-question'||name==='ai-next-question'||name==='ai-project-question'){ai.question=name==='ai-simple-question'?'Explain this saved evidence in simple words.':name==='ai-next-question'?'What should I check next, based on this saved evidence?':'What changed in this saved design, and why does it matter?';$('#sd-ai-question').value=ai.question;updateAiControls();return;}
    if(name==='ai-new-conversation'){if(ai.starting||ai.records.some(investigationActive))return;rocketUI.threadHeads.set(ai.context,null);ai.modelChoice=null;rocketUI.modelSelections.set(ai.context,null);ai.question='';rocketUI.questionDrafts.set(ai.context,'');$('#sd-ai-question').value='';rocketUI.attachmentController?.clear();renderAiHistory();$('#sd-ai-model').focus();return;}
    if(name==='ai-start'){await startInvestigation();return;}
    if(name==='ai-refresh'){await Promise.allSettled([refreshAiStatus(),loadInvestigations()]);return;}
    if(name==='rocket-reference'){await showImport('rocket_review');return;}
    if(name==='import'){await showImport();return;}
    if(name==='spreadsheet-import'){showSpreadsheetImport();return;}
    if(name==='create-project'){
      if(!state.importing)return;const isRocketReference=state.importing.project_id==='constructed-rocket-review',isGuidedReference=state.importing.project_id==='constructed-guided-ascent-review',isStagedReference=state.importing.project_id==='constructed-staged-ascent-review';const candidate=copy(state.importing);candidate.project_id=$('#sd-import-id').value.trim();candidate.name=$('#sd-import-name').value.trim();
      if(!candidate.project_id||!candidate.name){importError(new Error('Provide a project ID and name.'));return;}
      await perform(async()=>{try{state.data=await api('/api/projects',{project:candidate});state.request++;state.draft=null;state.impact=null;invalidatePreflight();state.system='overview';state.selected=defaultSelection();state.stagedProfileEdit=null;state.page=isRocketReference?'review-home':isStagedReference?'staged-ascent':isGuidedReference?'guided-ascent':'system';await refreshProjects();try{localStorage.setItem('sixd.workspace.last-project',state.data.project_id);}catch{}$('#sd-import-dialog').close();resetCamera();}catch(error){importError(error);throw error;}},'Project saved locally. Run checks to calculate its evidence.');return;
    }
    if(!state.data)return;
    if(name==='author-project'||name==='author-edit'){
      if(name==='author-edit'&&!beginDraft())return;
      state.page='authoring';state.panel='details';stopInvestigationPolling();render();
      try{await loadCatalog();if(state.page==='authoring')renderMain();}catch(error){showError(error);}
      await refreshPreflight();return;
    }
    if(name==='validate-setup'){await refreshPreflight();return;}
    if(name==='author-run'){
      if(state.draft){message('Save this draft before running.');return;}
      if(author.snapshot!==setupKey()||!author.preflight?.can_run){await refreshPreflight();message('Resolve setup errors before running from Author project.');return;}
      await action('run');return;
    }
    if(name==='envelopes'){state.page='envelopes';stopInvestigationPolling();render();return;}
    if(name==='simulation-imports'){state.page='simulation-imports';stopInvestigationPolling();render();return;}
    if(name==='test-data'){state.testEvidenceTarget=null;invalidateTestLinks();state.page='test-data';stopInvestigationPolling();render();return;}
    if(name==='scenarios'){state.page='scenarios';stopInvestigationPolling();render();return;}
    if(name==='simulation'){state.trajectory=null;state.page='simulation';stopInvestigationPolling();render();return;}
    if(name==='report'){envelopeLinks.key='';seriesLinks.key='';sourceLinks.key='';actionLinks.key='';coverageLinks.key='';state.page='report';render();return;}
    if(name==='print-report'){
      if(state.draft || !currentRun() || currentRun().stale || testLinks.key!==testLinkKey() || !testLinks.profile || interfaceLinks.key!==testLinkKey() || !interfaceLinks.profile || sourceLinks.key!==sourceLinkKey() || !sourceLinks.profile || actionLinks.key!==actionLinkKey() || !actionLinks.profile || envelopeLinks.key!==testLinkKey() || !envelopeLinks.profile || seriesLinks.key!==testLinkKey() || !seriesLinks.profile || coverageLinks.key!==sourceLinkKey() || !coverageLinks.profile){showError(Error('Load current coverage and evidence, references and actions before printing the report.'));return;}
      if(state.page!=='report'){state.page='report';render();}
      window.print();return;
    }
    if(name==='changes'){state.page='changes';render();return;}
    if(name==='back'){state.page='system';render();return;}
    if(name==='investigate'){if(state.selected)select(state.selected.kind,state.selected.id,true);return;}
    if(name==='zoom-in'||name==='zoom-out'){state.camera.scale=Math.max(.3,Math.min(1.8,state.camera.scale+(name==='zoom-in'?.1:-.1)));applyCamera();return;}
    if(name==='fit'){fit();return;}
    if(name==='close-thrust'){window.SixDOverlayDismiss.requestClose($('#sd-thrust-dialog'),'cancel-button');return;}
    if(name==='edit-thrust'){openThrustEditor();return;}
    if(name==='rocket-stage'){
      if(state.draft||!latest()||!currentRun())return;
      const projectId=state.data.project_id,revision=state.data.revision,runId=currentRun().run_id;
      const current=()=>state.data?.project_id===projectId&&state.data?.revision===revision&&currentRun()?.run_id===runId&&!state.draft;
      await perform(async()=>{
        const snapshot=await api('/api/review-workspace'+query(projectId,revision));
        if(!current())return;
        const reference=snapshot.rocket_reference;
        if(snapshot.run_id!==runId||!reference?.recognized||!reference.can_stage||![11000,20000].includes(reference.next_thrust))throw Error('The reference context changed. Reload the latest saved revision before staging this change.');
        const candidate=copy(state.data.project);candidate.inputs.thrust.value=reference.next_thrust;
        const preview=await api('/api/impact',{project_id:projectId,base_revision:revision,project:candidate});
        if(!current())return;
        state.draft=candidate;state.impact=preview.impact;invalidatePreflight();state.page='changes';state.panel='details';
        stopInvestigationPolling();
      },'Thrust change staged and dependencies previewed. Review it, save a revision, then rerun affected checks.');return;
    }
    if(name==='edit'){
      if(!beginDraft())return;
      if(state.page!=='authoring'){state.page='system';state.view='table';}state.panel='details';message('Draft editing enabled. Changes are unsaved until you choose Save revision.');render();if(state.page==='authoring')void refreshPreflight();return;
    }
    if(name==='discard'){state.stagedProfileEdit=null;state.draft=null;state.impact=null;invalidatePreflight();repairContext();message('Draft discarded. The saved revision is preserved.');render();if(state.page==='authoring')void refreshPreflight();return;}
    if(name==='impact'){
      if(!state.draft)return;const errors=editErrors();if(errors.length){showError(errors[0]);return;}
      const projectId=state.data.project_id,revision=state.data.revision,draft=state.draft;
      await perform(async()=>{const response=await api('/api/impact',{project_id:projectId,base_revision:revision,project:copy(draft)});if(state.data.project_id!==projectId||state.data.revision!==revision||state.draft!==draft)return;state.impact=response.impact;state.page='changes';},'Dependency preview validated. No calculations were run.');return;
    }
    if(name==='save'){
      if(!state.draft||!dirty())return;const errors=editErrors();if(errors.length){showError(errors[0]);return;}
      const wasAuthoring=state.page==='authoring',projectId=state.data.project_id,revision=state.data.revision,draft=state.draft;
      await perform(async()=>{const data=await api('/api/revisions',{project_id:projectId,base_revision:revision,project:copy(draft)});if(state.data.project_id!==projectId||state.data.revision!==revision||state.draft!==draft)return;state.data=data;state.request++;state.draft=null;state.impact=null;invalidatePreflight();repairContext();state.page=wasAuthoring?'authoring':'changes';await refreshProjects();if(wasAuthoring)void refreshPreflight();},'New revision saved. Previous evidence is preserved; rerun checks for the new configuration.');return;
    }
    if(name==='run'){
      if(state.draft){message('Save or discard the draft before running checks.');return;}
      if(!hasSetup()){state.page='authoring';render();message('Add a model and requirement in Author project before running checks.');return;}
      if(state.page==='authoring'&&(author.snapshot!==setupKey()||!author.preflight?.can_run)){await refreshPreflight();message('Resolve setup errors before running from Author project.');return;}
      const projectId=state.data.project_id,revision=state.data.revision;
      let completed=false;
      state.calculationFeedback={projectId,revision,phase:'working',text:'Calculating saved revision R'+revision+'… Local engineering checks only; no AI request.'};renderCalculationFeedback();
      root.querySelectorAll('[data-rw="run"],[data-action="run"]').forEach(button=>{button.textContent='Calculating…';});
      await perform(async()=>{const data=await api('/api/run',{project_id:projectId,revision});if(state.data.project_id!==projectId||state.data.revision!==revision||state.draft)return;state.data=data;state.impact=null;repairContext();if(state.page==='simulation'){const modelId=state.trajectory?.modelId||allModels().find(m=>m.type==='orbital_trajectory')?.id;state.trajectory=modelId?{modelId,runId:state.data.run?.run_id}:null;}await refreshProjects();completed=true;},'Checks completed and saved. Inspect findings and remaining unassessed requirements.');
      state.calculationFeedback={projectId,revision,phase:completed?'done':'error',text:completed?'Calculation complete for R'+revision+'. Results are saved below; unchanged inputs can produce the same values.':'Calculation did not complete. Review the error message before trying again.'};renderCalculationFeedback();return;
    }
    if(name==='export'){if(state.draft||!hasSetup()||!currentRun()||currentRun().stale){message('Save a complete setup and run its checks before exporting review evidence. Project JSON remains available.');return;}await perform(async()=>{const key=JSON.stringify([state.data.project_id,state.data.revision,currentRun().run_id]);await download('/api/export'+query(state.data.project_id,state.data.revision),'6d-'+state.data.project_id+'-r'+state.data.revision+'-evidence.json');reviewGuide.exportedRun=key;},'Saved evidence export requested.');return;}
    if(name==='export-project'){saveBlob(new Blob([JSON.stringify(project(),null,2)],{type:'application/json'}),'6d-'+state.data.project_id+'-r'+state.data.revision+(state.draft?'-draft':'')+'-project.json');message('Project JSON downloaded'+(state.draft?' with unsaved draft edits.':'.'));return;}
  }
  // Expand evidence disclosures for the printed report, then restore the user's
  // on-screen disclosure state. Printing never changes saved project records.
  let printDisclosures=[];
  window.addEventListener('beforeprint',()=>{
    printDisclosures=[...root.querySelectorAll('#sd-view-content details,#sd-panel-body details')].map(el=>({el,open:el.open}));
    printDisclosures.forEach(({el})=>{el.open=true;});
  });
  window.addEventListener('afterprint',()=>{
    printDisclosures.forEach(({el,open})=>{el.open=open;});printDisclosures=[];
  });
  root.addEventListener('click',event=>{
    const button=event.target.closest('button');if(!button||button.disabled||state.busy)return;
    if(button.dataset.openProject){
      if(state.stagedProfileEdit){message('Apply or cancel the open thrust-profile edit before changing projects.');return;}
      const id=button.dataset.openProject;
      if(id===state.data?.project_id){state.page='review-home';state.panel='details';root.classList.remove('sd-tree-open');render();return;}
      if(id!==state.data?.project_id&&dirty()&&!window.confirm('Discard unsaved draft changes and open this project?'))return;
      void perform(async()=>{await load(id);state.page='review-home';state.panel='details';root.classList.remove('sd-tree-open');render();});return;
    }
    if(button.dataset.aiResume){if(ai.starting||ai.records.some(investigationActive))return;rocketUI.threadHeads.set(ai.context,button.dataset.aiResume);renderAiHistory();$('#sd-ai-history-disclosure').open=false;$('#sd-ai-question').focus();return;}
    if(button.dataset.authorAdd){openEditor(button.dataset.authorAdd);return;}
    if(button.dataset.authorEdit){openEditor(button.dataset.authorEdit,button.dataset.id);return;}
    if(button.dataset.authorRemove){
      if(!state.draft)return;const kind=button.dataset.authorRemove,id=button.dataset.id,reason=deletionReason(kind,id);if(reason){showError(reason);return;}
      if(kind==='input')delete state.draft.inputs[id];else if(kind==='model')state.draft.models=allModels().filter(m=>m.id!==id);else state.draft.requirements=allReqs().filter(r=>r.id!==id);
      draftChanged();message(human(kind)+' '+id+' removed from the shared draft. Previous revisions remain available.');return;
    }
    if(button.dataset.testEvidenceOpen){state.testEvidenceTarget={projectId:state.data.project_id,revision:state.data.revision,comparisonId:button.dataset.testEvidenceOpen,rowNumber:Number(button.dataset.testEvidenceRow)};state.page='test-data';stopInvestigationPolling();render();return;}
    if(button.dataset.testEvidenceInvestigate){
      const requirementId=button.dataset.testEvidenceRequirement,comparisonId=button.dataset.testEvidenceInvestigate,rowNumber=Number(button.dataset.testEvidenceRow);
      if(state.draft||!currentRun()||!req(requirementId)||testLinks.key!==testLinkKey())return;
      const row=testLinks.profile?.comparisons.find(c=>c.comparison_id===comparisonId)?.rows.find(r=>r.row_number===rowNumber&&r.requirement_id===requirementId);if(!row)return;
      state.selected={kind:'requirement',id:requirementId};state.page='system';state.panel='details';render();openRocket({scope:'requirement',requirementId,testSelection:{projectId:state.data.project_id,revision:state.data.revision,runId:currentRun()?.run_id||null,requirementId,comparisonId,rowNumber},preserveQuestion:true});if(!ai.question.trim())ai.question='Review this test comparison, distinguish its measured requirement result from prediction agreement, and explain any applicability gaps.';renderRocket(true);return;
    }
    if(button.dataset.trajectoryModel){state.trajectory={modelId:button.dataset.trajectoryModel,runId:button.dataset.trajectoryRun};state.page='simulation';stopInvestigationPolling();render();return;}
    if(button.dataset.trackAction){actionLinks.originId=button.dataset.trackAction;void action('actions');return;}
    if(button.dataset.action){void action(button.dataset.action);return;}
    if(button.dataset.evidenceFact){const record=ai.records.find(item=>investigationId(item)===button.dataset.investigationRecord);if(record)showFactSource(record,button.dataset.evidenceFact);return;}
    if(button.dataset.citation){openCitation(button.dataset.citation,button.dataset.investigationRecord);return;}
    if(button.dataset.aiDownload){
      const record=ai.records.find(item=>investigationId(item)===button.dataset.aiDownload);
      if(record)saveBlob(new Blob([JSON.stringify(record,null,2)],{type:'application/json'}),'6d-investigation-'+investigationId(record)+'.json');
      return;
    }
    if(button.dataset.template!==undefined){try{stageImport(state.templates[Number(button.dataset.template)].project,true);}catch(error){importError(error);}return;}
    if(button.dataset.view){if(state.stagedProfileEdit){message('Apply or cancel the open thrust-profile edit before changing views.');return;}state.view=button.dataset.view;state.page='system';render();return;}
    if(button.dataset.panel){
      if(button.dataset.panel==='assistant'){void openAssistant(state.selected?.kind==='requirement'?state.selected.id:null);return;}
      stopInvestigationPolling();ai.loadedContext='';state.panel=button.dataset.panel;renderPanel();navigation?.sync();icons();return;
    }
    if(button.dataset.system){if(state.stagedProfileEdit){message('Apply or cancel the open thrust-profile edit before changing systems.');return;}state.system=button.dataset.system;state.page='system';state.selected=defaultSelection();resetCamera();render();return;}
    if(button.dataset.investigate){select('requirement',button.dataset.investigate,true);return;}
    if(button.dataset.kind)select(button.dataset.kind,button.dataset.id);
  });
  root.addEventListener('keydown',event=>{
    if(event.target.id==='sd-ai-question'&&event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();if(!$('#sd-ai-start')?.disabled)void startInvestigation();}
  });
  root.addEventListener('input',event=>{
    if(state.busy)return;
    const el=event.target;
    const dialog=el.closest('dialog');if(dialog)editedDialogs.add(dialog);
    if(el.id==='sd-ai-question'){ai.question=el.value;updateAiControls();return;}
    if(state.draft&&el.dataset.projectField){state.draft[el.dataset.projectField]=el.value;draftChanged(false);return;}
    if(!state.draft||!el.dataset.input)return;
    const input=state.draft.inputs[el.dataset.input];if(!input)return;
    input[el.dataset.field]=el.dataset.field==='value'?(el.value.trim()===''?'':Number(el.value)):el.value;draftChanged(false);
    // Keep the active editor mounted. Synchronize other editors without stealing focus.
    root.querySelectorAll('input[data-input]').forEach(other=>{if(other!==el&&other.dataset.input===el.dataset.input&&other.dataset.field===el.dataset.field)other.value=el.value;});
    renderDraft();root.querySelectorAll('[data-status-for]').forEach(cell=>{cell.innerHTML=chip(reqStatus(cell.dataset.statusFor));});$('#sd-save-state').textContent='Unsaved draft · saved revision preserved';
  });
  root.addEventListener('toggle',event=>{const el=event.target;if(el.matches?.('details[data-disclosure-key]')&&el.isConnected)pageDisclosures.set(el.dataset.disclosureKey,el.open);},true);
  root.addEventListener('change',event=>{
    if(state.busy)return;
    const el=event.target;
    if(el.id==='sd-ai-scope'){if(['project','requirement'].includes(el.value))openRocket({scope:el.value,preserveQuestion:true});return;}
    if(el.id==='sd-rocket-requirement'){if(req(el.value)){changeAssistantContext({scope:'requirement',requirementId:el.value},true);renderRocket(true);}return;}
    if(el.id==='sd-ai-model'){
      if(ai.starting||ai.status?.investigation_active||ai.records.some(investigationActive)){updateModelChoiceControls();return;}
      if(!el.value||modelChoices().some(row=>row.id===el.value)){ai.modelChoice=el.value||null;rocketUI.modelSelections.set(ai.context,ai.modelChoice);const status=$('#sd-ai-status');if(status)status.innerHTML=aiStatusMarkup();updateAiControls();}
      return;
    }
    if(el.closest('#sd-author-form')&&el.matches('select[name="type"],select[name="model_id"],select[name="metric"]')){
      const values=Object.fromEntries(new FormData($('#sd-author-form'))),context=author.editor;
      if(context?.kind==='requirement'&&el.name==='model_id'){values.metric='';values.limit_input='';}
      if(context?.kind==='requirement'&&el.name==='metric'){const unit=catalogModel(model(values.model_id)?.type)?.metrics.find(m=>m.name===values.metric)?.unit;if(project().inputs[values.limit_input]?.unit!==unit)values.limit_input='';}
      if(context)renderEditor(context.kind,context.id,values);return;
    }
    if(state.draft&&el.dataset.projectField){state.draft[el.dataset.projectField]=el.value;draftChanged(false);return;}
    if(state.draft&&el.dataset.requirement){const r=req(el.dataset.requirement);r[el.dataset.reqField]=el.dataset.reqField==='critical'?el.value==='true':el.value;draftChanged(false);return;}
    if(el.id==='sd-project-picker'||el.id==='sd-revision-picker'){
      if(state.stagedProfileEdit){message('Apply or cancel the open thrust-profile edit before switching saved records.');el.value=el.id==='sd-project-picker'?state.data.project_id:String(state.data.revision);return;}
      if(dirty()&&!window.confirm('Discard unsaved draft changes and switch the saved project view?')){render();return;}
      const changingProject=el.id==='sd-project-picker';
      void perform(async()=>{if(changingProject){state.page='review-home';state.system='overview';state.panel='details';}await load(changingProject?el.value:state.data.project_id,changingProject?undefined:Number(el.value));});
    }
    if(el.id==='sd-import-file'){
      const file=el.files[0];if(!file)return;if(file.size>2*1024*1024){importError(new Error('Project JSON must be no larger than 2 MiB.'));return;}
      void file.text().then(text=>stageImport(JSON.parse(text))).catch(error=>importError(new Error(error instanceof SyntaxError?'The file is not valid JSON.':error.message)));
    }
  });
  $('#sd-new-form').addEventListener('submit',event=>{event.preventDefault();if(!state.busy)void createEmptyProject();});
  $('#sd-author-form').addEventListener('submit',event=>{event.preventDefault();if(!state.busy)saveEditor();});
  root.addEventListener('keydown',event=>{
    if(!event.target.matches('[role="tab"]')||!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
    const tabs=[...event.target.closest('[role="tablist"]').querySelectorAll('[role="tab"]')];let index=tabs.indexOf(event.target);index=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:tabs.length-1))%tabs.length;event.preventDefault();tabs[index].focus();tabs[index].click();
  });
  window.addEventListener('beforeunload',event=>{if(dirty()||author.editor||state.stagedProfileEdit){event.preventDefault();event.returnValue='';}});
  root.addEventListener('sixd:before-dismiss',event=>{
    const dialog=event.target;
    if((dialog.id==='sd-author-dialog'||dialog.id==='sd-new-dialog'||dialog.id==='sd-thrust-dialog')&&editedDialogs.has(dialog)&&!window.confirm('Close this form and discard its unapplied entries? Saved project data and applied draft changes remain intact.'))event.preventDefault();
  });
  for(const dialog of root.querySelectorAll('dialog'))dialog.addEventListener('close',()=>{editedDialogs.delete(dialog);if(dialog.id==='sd-author-dialog')author.editor=null;});
  $('#sd-ai-connect-dialog').addEventListener('cancel',()=>{$('#sd-ai-key').value='';});
  $('#sd-ai-connect-dialog').addEventListener('close',()=>{$('#sd-ai-key').value='';});
  $('#sd-thrust-form').addEventListener('submit',stageThrust);
  $('#sd-thrust-input').addEventListener('change',event=>fillThrustEditor(event.target.value));
  $('#sd-thrust-dialog').addEventListener('close',()=>{state.thrustEdit=null;thrustError('');});
  async function init() {
    window.SixDSidebar.mount(root);
    mountRocket();
    navigation=window.SixDNavigation.create({read:locationSnapshot,apply:restoreLocation,onError:showError,onChange:renderLocation});
    try{state.hosted=(await api('/api/hosted/status')).hosted!==false;}catch{state.hosted=true;}
    icons();let last=null;try{last=localStorage.getItem('sixd.workspace.last-project');}catch{}
    let initial=null;
    try{initial=navigation.getInitial();}catch(error){showError(error);}
    await perform(async()=>{
      if(initial&&initial.page!=='projects'){
        try{await load(initial.projectId,initial.revision);await restoreLocation(initial,true);}
        catch(error){state.page='projects';await load(last||undefined);showError(error);}
      }else{state.page='projects';try{await load(last||undefined);}catch(error){if(!last)throw error;await load();}}
    });
    navigationStarting=false;
    if(state.data){navigation.start();renderLocation();icons();}
    try{await loadCatalog();if(state.data)render();}catch{message('Current model catalog context is unavailable. Saved evidence remains readable; no catalog reference proof is inferred.');}
    await refreshAiStatus();
    try{const status=await api('/api/status');$('#sd-build').textContent='Build '+status.build_id+' · Updated '+new Date(status.updated_at).toLocaleString();}catch{$('#sd-build').textContent='Build identity unavailable';}
  }
  root.addEventListener('keydown',event=>{if(event.key==='Escape'){const menu=event.target.closest('details.sd-tool-menu[open]');if(menu){menu.open=false;menu.querySelector('summary').focus();}}});
  document.addEventListener('click',event=>{root.querySelectorAll('details.sd-tool-menu[open]').forEach(menu=>{if(!menu.contains(event.target))menu.open=false;});});
  window.SixDUnits?.observe(root);
  void init();
})();
