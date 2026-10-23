/* Declared engineering scope and current evidence. No physics is inferred from a phase. */
(() => {
  'use strict';
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const list=value=>Array.isArray(value)?value:[];
  const clone=value=>JSON.parse(JSON.stringify(value));
  const COVERAGE={excluded:'Declared out of scope',undecided:'Applicability undecided',needs_review:'Context needs review',missing_analysis:'Analysis not linked',outside_assumptions:'Outside model assumptions',applicability_unknown:'Model fit not established',unassessed:'Calculation unresolved',criterion_unmet:'Criterion unmet',criterion_met:'Criterion met · declared fit'};
  const APPLICATION={required:'Required for this review',excluded:'Excluded with rationale',undecided:'Applicability undecided'};
  const FIT={declared_fit:'User declares model fit',outside_assumptions:'Outside model assumptions',unknown:'Model fit not established'};
  const CALC={not_run:'Checks not recorded',stale:'Recorded calculation is stale',unsupported:'No supported calculation',not_assessed:'Calculation unresolved',assessed:'Calculation assessed'};
  const CRITERION={met:'Criterion met',not_met:'Criterion unmet',not_assessed:'Criterion unassessed'};
  const LIMITATION='This map covers the checks declared in this project. It does not establish a complete mission checklist, physical validity or permission to launch.';
  const FIELDS=['title','phase','discipline','requirement_id','applicability','applicability_note','model_fit','fit_note','next_step'];
  let mounted=null,instance=0;
  const option=(value,label,current)=>'<option value="'+esc(value)+'"'+(value===current?' selected':'')+'>'+esc(label)+'</option>';
  const button=(action,label,extra='')=>'<button type="button" class="ec-button" data-ec-action="'+action+'" '+extra+'>'+esc(label)+'</button>';
  const label=(values,value,fallback)=>values[value]||fallback;
  const rowId=row=>row.row_id||(row.check_id?'check:'+row.check_id:'requirement:'+row.requirement_id);
  const badge=row=>'<span class="ec-badge ec-'+(Object.hasOwn(COVERAGE,row.coverage_status)?row.coverage_status:'unassessed')+'">'+esc(label(COVERAGE,row.coverage_status,'Scope unresolved'))+'</span>';
  const bullet=values=>list(values).length?'<ul>'+values.map(value=>'<li>'+esc(value)+'</li>').join(''):'<p class="ec-small">None recorded in this context.</p>';
  function facts(row){
    return '<dl class="ec-facts"><dt>Declared applicability</dt><dd>'+esc(label(APPLICATION,row.applicability,'Undecided'))+'</dd><dt>Declared model fit</dt><dd>'+esc(label(FIT,row.model_fit,'Not established'))+'</dd><dt>Calculation</dt><dd>'+esc(label(CALC,row.calculation_status,'Not assessed'))+'</dd><dt>Requirement criterion</dt><dd>'+esc(label(CRITERION,row.criterion_status,'No current finding'))+'</dd></dl>';
  }
  function details(row,withHistory=false){
    const model=row.model||{};
    return '<p class="ec-small ec-preserve">'+esc(row.reason||'Inspect the declared scope and recorded evidence.')+'</p>'+facts(row)+(row.needs_review?'<div class="ec-notice"><strong>Review this declaration against the current context.</strong>'+bullet(row.review_reasons)+'</div>':'')+(row.applicability_note?'<p class="ec-small ec-preserve"><strong>Applicability rationale:</strong> '+esc(row.applicability_note)+'</p>':'')+(row.fit_note?'<p class="ec-small ec-preserve"><strong>Model-fit rationale:</strong> '+esc(row.fit_note)+'</p>':'')+'<p class="ec-next"><strong>Next engineering step</strong><span>'+esc(row.next_step||'No next step has been recorded.')+'</span></p>'+(row.requirement_id?'<p class="ec-small">Linked requirement: '+esc(row.requirement_id)+'</p>':'')+(model.id?'<details class="ec-record"><summary>Model scope and assumptions · '+esc(model.id)+'</summary><p class="ec-small">'+esc(model.scope||model.type||'Recorded model')+'</p><p class="ec-small">A phase assignment does not extend this model’s physical scope. A model-fit declaration is a user judgment.</p><h5>Recorded assumptions</h5>'+bullet(model.assumptions)+'<h5>Not assessed by this model</h5>'+bullet(model.not_assessed)+'</details>':'')+(withHistory&&list(row.history).length?'<details class="ec-record"><summary>Declaration history ('+row.history.length+')</summary><ol class="ec-history">'+row.history.map(item=>'<li><strong>Version '+esc(item.version)+' · saved R'+esc(item.basis_revision)+'</strong><p>'+esc(item.title||row.title)+'</p><p class="ec-small">'+esc(item.phase||'Unassigned')+' · '+esc(item.discipline||'Unassigned')+' · '+esc(label(APPLICATION,item.applicability,'Undecided'))+' · '+esc(label(FIT,item.model_fit,'Not established'))+'</p>'+(item.applicability_note?'<p class="ec-small ec-preserve">Applicability: '+esc(item.applicability_note)+'</p>':'')+(item.fit_note?'<p class="ec-small ec-preserve">Model fit: '+esc(item.fit_note)+'</p>':'')+(item.next_step?'<p class="ec-small ec-preserve">Next step: '+esc(item.next_step)+'</p>':'')+'<p class="ec-identity">'+esc(item.created_at||'')+'<br>'+esc(item.digest||'')+'</p></li>').join('')+'</ol></details>':'')+(row.check_id?'<p class="ec-identity">Declaration '+esc(row.check_id)+' · v'+esc(row.version)+' · saved R'+esc(row.basis_revision)+'</p>':'<p class="ec-small">This requirement appears automatically because no coverage declaration maps it yet.</p>');
  }
  function render(profile){
    if(!profile||!Array.isArray(profile.checks))return '<section class="ec-evidence"><h3>Engineering coverage</h3><p class="ec-small">Coverage is unavailable for this saved revision.</p></section>';
    return '<section class="ec-evidence" aria-label="Engineering coverage"><h3>Engineering coverage</h3><p class="ec-small">'+LIMITATION+'</p><p class="ec-small">Saved project R'+esc(profile.revision)+' · '+profile.checks.length+' declared or unmapped requirement checks. Criteria and model applicability are distinct.</p><div class="ec-report-list">'+profile.checks.map(row=>'<article class="ec-report-row"><div class="ec-heading"><h4>'+esc(row.title)+'</h4>'+badge(row)+'</div><p class="ec-eyebrow">'+esc(row.phase||'Unassigned')+' · '+esc(row.discipline||'Unassigned')+'</p>'+details(row)+'</article>').join('')+'</div>'+(!profile.checks.length?'<p class="ec-empty">No checks or requirements are declared. An empty map provides no coverage claim.</p>':'')+'<details class="ec-record"><summary>Coverage snapshot and limitations</summary><p class="ec-identity">Project '+esc(profile.project_id)+' · R'+esc(profile.revision)+'<br>Snapshot '+esc(profile.digest||'')+'</p>'+bullet(profile.limitations)+'</details></section>';
  }
  const active=s=>!s.disposed&&mounted===s&&s.host.isConnected;
  const readOnly=s=>Boolean(s.ctx.draft||s.ctx.hasDraft||s.profile?.can_edit===false||s.ctx.canEdit===false);
  function validate(s,profile){
    if(!profile||profile.schema!=='sixd.engineering-coverage.v1'||profile.project_id!==s.ctx.projectId||profile.revision!==s.ctx.revision||!Array.isArray(profile.checks)||!Array.isArray(profile.requirements)||!/^[a-f0-9]{64}$/.test(profile.digest||''))throw Error('The coverage response does not match this saved project. Reopen the selected revision.');
    return profile;
  }
  function blank(s){
    s.editor={check_id:null,base_version:null,title:'',phase:'',discipline:'',requirement_id:null,applicability:'undecided',applicability_note:'',model_fit:'unknown',fit_note:'',next_step:''};
    s.editorDigest=s.profile?.digest||'';s.dirty=false;s.selected='';
  }
  function choose(s,row){
    if(s.busy||s.dirty)return;
    s.selected=rowId(row);s.editor={check_id:row.check_id||null,base_version:row.check_id?row.version:null};
    FIELDS.forEach(field=>{s.editor[field]=row[field]??(field==='requirement_id'?null:'');});
    s.editorDigest=s.profile.digest;s.dirty=false;s.notice='';s.error='';draw(s);
    s.host.querySelector('.ec-editor')?.scrollIntoView({block:'start'});
  }
  function field(s,key,text,{max=2000,rows=0,hint='',required=false,extra=''}={}){
    const id=s.uid+'-'+key,value=s.editor[key]??'';
    return '<label class="ec-field" for="'+id+'">'+esc(text)+(rows?'<textarea id="'+id+'" data-ec-field="'+key+'" rows="'+rows+'" maxlength="'+max+'"'+(required?' required':'')+'>'+esc(value)+'</textarea>':'<input id="'+id+'" data-ec-field="'+key+'" value="'+esc(value)+'" maxlength="'+max+'"'+(required?' required':'')+' '+extra+'>')+(hint?'<small>'+esc(hint)+'</small>':'')+'</label>';
  }
  function selectField(s,key,text,values,hint=''){
    return '<label class="ec-field" for="'+s.uid+'-'+key+'">'+esc(text)+'<select id="'+s.uid+'-'+key+'" data-ec-field="'+key+'">'+Object.entries(values).map(([value,name])=>option(value,name,s.editor[key]??'')).join('')+'</select>'+(hint?'<small>'+esc(hint)+'</small>':'')+'</label>';
  }
  function editor(s){
    if(!s.profile)return '';
    const row=s.profile.checks.find(item=>rowId(item)===s.selected), choices={'':'No linked calculation requirement'};
    s.profile.requirements.forEach(req=>{choices[req.id]=req.title+' · '+req.model_id;});
    if(s.editor.requirement_id&&!Object.hasOwn(choices,s.editor.requirement_id))choices[s.editor.requirement_id]=s.editor.requirement_id+' · unavailable in this revision';
    return '<section class="ec-editor" aria-label="Coverage declaration"><div class="ec-heading"><div><span class="ec-eyebrow">'+(s.editor.check_id?'Versioned declaration':'New declaration')+'</span><h3>'+esc(s.editor.check_id?'Review the engineering scope.':'Define a check that matters.')+'</h3></div>'+button('new','New check')+'</div>'+(row?'<div class="ec-selected-detail"><div class="ec-heading"><h4>'+esc(row.title)+'</h4>'+badge(row)+'</div>'+details(row,true)+(row.requirement_id&&s.ctx.onOpenRequirement?button('requirement','Open linked requirement'):'')+'</div>':'<p class="ec-small">Name an engineering question, choose its mission phase and record what analysis is needed. A declared check can remain unlinked while that capability is missing.</p>')+(readOnly(s)?'<p class="ec-notice">'+(s.ctx.draft||s.ctx.hasDraft?'This map describes the saved revision. Save or discard the project draft before editing coverage.':'This revision is read-only. Open the latest saved revision to edit coverage.')+'</p>':'')+'<form data-ec-form><div class="ec-form-grid">'+field(s,'title','Engineering check',{max:240,required:true})+field(s,'phase','Mission phase',{max:80,required:true,extra:'list="'+s.uid+'-phases"'})+field(s,'discipline','Engineering discipline',{max:80,required:true})+selectField(s,'requirement_id','Linked requirement',choices,'Linking makes its current recorded finding visible. It does not prove that the model represents this mission phase.')+'</div><datalist id="'+s.uid+'-phases">'+list(s.profile.phases).map(phase=>'<option value="'+esc(phase)+'"></option>').join('')+'</datalist><div class="ec-form-grid">'+selectField(s,'applicability','Is this check required?',APPLICATION,'An excluded check remains visible with its rationale and any recorded unmet criterion.')+selectField(s,'model_fit','Does the model fit this use?',FIT,'This records your engineering judgment; a passing criterion cannot establish model fit.')+field(s,'applicability_note','Applicability rationale',{rows:3,hint:'Required when excluding a check. Explain why it belongs in or outside this review.'})+field(s,'fit_note','Model-fit rationale',{rows:3,hint:'Required for a declared fit or an outside-assumptions judgment. State the relevant assumptions and evidence.'})+'</div>'+field(s,'next_step','Next engineering step',{rows:3,hint:'Describe the missing analysis, measurements, model changes or evidence to obtain.'})+'<p class="ec-small">Saving records a new declaration version against the current linked dependencies. It does not run calculations or change requirement findings.</p><div class="ec-actions">'+button('save',s.editor.check_id?'Save reviewed declaration':'Save new check')+button('discard','Discard unsaved form changes')+'<span class="ec-small" data-ec-dirty></span></div></form></section>';
  }
  function board(s){
    const all=list(s.profile?.checks),rows=all.filter(row=>(!s.filter.discipline||row.discipline===s.filter.discipline)&&(!s.filter.status||row.coverage_status===s.filter.status));
    const disciplines=[...new Set(all.map(row=>row.discipline||'Unassigned'))].sort();
    const phases=[...new Set(rows.map(row=>row.phase||'Unassigned'))];
    return '<div class="ec-filters"><label>Discipline<select data-ec-filter="discipline">'+option('','All disciplines',s.filter.discipline)+disciplines.map(value=>option(value,value,s.filter.discipline)).join('')+'</select></label><label>Coverage state<select data-ec-filter="status">'+option('','All states',s.filter.status)+Object.entries(COVERAGE).map(([value,name])=>option(value,name,s.filter.status)).join('')+'</select></label><span class="ec-small">'+rows.length+' of '+all.length+' checks shown</span></div><div class="ec-board">'+phases.map(phase=>'<section class="ec-phase"><header><h3>'+esc(phase)+'</h3><span>'+rows.filter(row=>(row.phase||'Unassigned')===phase).length+'</span></header><div class="ec-cards">'+rows.filter(row=>(row.phase||'Unassigned')===phase).map(row=>'<button type="button" class="ec-card'+(rowId(row)===s.selected?' ec-selected':'')+'" data-ec-row="'+esc(rowId(row))+'"><span class="ec-eyebrow">'+esc(row.discipline||'Unassigned')+'</span><strong>'+esc(row.title)+'</strong>'+badge(row)+'<span class="ec-card-facts">'+esc(label(CRITERION,row.criterion_status,'No current finding'))+'<br>'+esc(label(FIT,row.model_fit,'Not established'))+'</span><span class="ec-card-origin">'+(row.origin==='requirement'?'Requirement awaiting scope mapping':'Declaration v'+esc(row.version))+'</span></button>').join('')+'</div></section>').join('')+'</div>'+(!rows.length?'<p class="ec-empty">'+(all.length?'No checks match these filters.':'No checks or requirements are declared. Add the first engineering check below.')+'</p>':'');
  }
  function draw(s){
    const rows=list(s.profile?.checks),counts=s.profile?.counts||{};
    s.host.innerHTML='<article class="ec-page"><header class="ec-page-header"><div><span class="ec-eyebrow">Engineering scope · saved R'+esc(s.ctx.revision)+'</span><h2>See what the evidence covers.</h2><p>Connect mission phases to engineering checks. Keep calculated findings, model assumptions and missing analysis visible together.</p></div><div class="ec-actions">'+button('refresh','Refresh coverage')+button('export','Export coverage JSON')+'</div></header><p class="ec-notice">'+LIMITATION+'</p><div class="ec-summary" aria-label="Coverage counts"><div><strong>'+rows.length+'</strong><span>Declared / unmapped checks</span></div><div><strong>'+rows.filter(row=>row.needs_review).length+'</strong><span>Context reviews needed</span></div><div><strong>'+rows.filter(row=>row.criterion_status==='not_met').length+'</strong><span>Rows with unmet criteria</span></div><div><strong>'+rows.filter(row=>row.model_fit==='unknown').length+'</strong><span>Model-fit judgments missing</span></div></div><p class="ec-small">Counts describe displayed checks and may include multiple checks linked to one requirement. They are not a mission-completeness score.</p><p class="ec-live" data-ec-status role="status" aria-live="polite">'+esc(s.notice)+'</p><p class="ec-error" data-ec-error role="alert"'+(s.error?'':' hidden')+'>'+esc(s.error)+'</p>'+(s.profile?board(s)+editor(s)+'<details class="ec-record"><summary>Coverage scope and limitations</summary>'+bullet(s.profile.limitations)+'<p class="ec-identity">Snapshot '+esc(s.profile.digest)+'</p></details>':'<p class="ec-empty">'+(s.busy?'Reading saved coverage…':'Coverage could not be loaded. Refresh to try again.')+'</p>')+'</article>';
    controls(s);
  }
  function controls(s){
    const locked=readOnly(s)||!!s.busy||!s.profile;
    s.host.querySelectorAll('[data-ec-field]').forEach(node=>{node.disabled=locked;});
    s.host.querySelectorAll('[data-ec-row]').forEach(node=>{node.disabled=!!s.busy||s.dirty;});
    s.host.querySelectorAll('[data-ec-action]').forEach(node=>{
      const action=node.dataset.ecAction;
      node.disabled=!!s.busy||(['save','new','discard'].includes(action)&&locked)||(['refresh','new','export'].includes(action)&&s.dirty)||(action==='export'&&!s.profile)||(action==='discard'&&!s.dirty);
    });
    const dirty=s.host.querySelector('[data-ec-dirty]');if(dirty)dirty.textContent=s.dirty?'Unsaved changes · save or discard before switching checks.':'';
    const application=s.host.querySelector('[data-ec-field="applicability_note"]'),fit=s.host.querySelector('[data-ec-field="fit_note"]');
    if(application)application.required=s.editor.applicability==='excluded';if(fit)fit.required=s.editor.model_fit!=='unknown';
  }
  async function load(s){
    if(s.busy||s.dirty)return;
    const serial=++s.serial;s.controller?.abort();s.controller=new AbortController();s.busy='load';s.error='';s.notice='';s.profile=null;draw(s);
    try{const value=await s.ctx.api('/api/coverage?project_id='+encodeURIComponent(s.ctx.projectId)+'&revision='+encodeURIComponent(s.ctx.revision),undefined,{signal:s.controller.signal});if(!active(s)||serial!==s.serial)return;s.profile=validate(s,value);blank(s);s.notice='Saved coverage loaded. Select a check or define a new one.';}
    catch(error){if(active(s)&&serial===s.serial&&error.name!=='AbortError')s.error=error.message||String(error);}
    finally{if(active(s)&&serial===s.serial){s.busy='';draw(s);}}
  }
  async function save(s){
    if(s.busy||readOnly(s)||!s.profile)return;
    const form=s.host.querySelector('[data-ec-form]');if(!form?.reportValidity())return;
    const spec=clone(s.editor),serial=++s.serial;s.controller?.abort();s.controller=new AbortController();s.busy='save';s.error='';s.notice='Saving the explicit scope declaration…';draw(s);
    try{
      const value=await s.ctx.api('/api/coverage/save',{project_id:s.ctx.projectId,revision:s.ctx.revision,expected_digest:s.editorDigest,spec},{signal:s.controller.signal});
      if(!active(s)||serial!==s.serial)return;s.profile=validate(s,value);s.dirty=false;s.selected='';s.editorDigest=s.profile.digest;blank(s);s.notice='Coverage declaration saved. Calculated findings are unchanged.';
    }catch(error){if(active(s)&&serial===s.serial&&error.name!=='AbortError'){s.error=error.message||String(error);s.notice='Your form values are retained. If the context changed, copy any needed notes, discard this form and refresh before reviewing again.';}}
    finally{if(active(s)&&serial===s.serial){s.busy='';draw(s);}}
  }
  function exportJSON(s){
    if(!s.profile||s.busy||s.dirty)return;
    const url=URL.createObjectURL(new Blob([JSON.stringify(s.profile,null,2)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download='6d-engineering-coverage-r'+s.ctx.revision+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function mount(host,ctx){
    mounted?.dispose();
    const s={host,ctx,uid:'ec-'+(++instance),profile:null,editor:{},editorDigest:'',selected:'',dirty:false,filter:{discipline:'',status:''},busy:'',error:'',notice:'',serial:0,controller:null,disposed:false};mounted=s;blank(s);
    const input=event=>{const key=event.target.dataset.ecField;if(!FIELDS.includes(key)||readOnly(s)||s.busy)return;s.editor[key]=key==='requirement_id'?(event.target.value||null):event.target.value;s.dirty=true;controls(s);};
    const change=event=>{if(event.target.dataset.ecField)input(event);const key=event.target.dataset.ecFilter;if(!['discipline','status'].includes(key)||s.busy)return;s.filter[key]=event.target.value;draw(s);};
    const click=event=>{const node=event.target.closest('[data-ec-action],[data-ec-row]');if(!node||!host.contains(node)||node.disabled)return;if(node.dataset.ecRow){const row=s.profile?.checks.find(item=>rowId(item)===node.dataset.ecRow);if(row)choose(s,row);return;}const action=node.dataset.ecAction;if(action==='refresh'){void load(s);return;}if(action==='save'){void save(s);return;}if(action==='export'){exportJSON(s);return;}if(action==='new'){if(!readOnly(s)&&!s.busy&&!s.dirty){blank(s);draw(s);}return;}if(action==='discard'){if(s.busy)return;const row=s.profile?.checks.find(item=>rowId(item)===s.selected);s.dirty=false;if(row)choose(s,row);else{blank(s);draw(s);}return;}if(action==='requirement'){const row=s.profile?.checks.find(item=>rowId(item)===s.selected);if(row?.requirement_id&&!s.dirty)s.ctx.onOpenRequirement?.(row.requirement_id);}};
    const submit=event=>{if(event.target.matches('[data-ec-form]')){event.preventDefault();void save(s);}};
    host.addEventListener('input',input);host.addEventListener('change',change);host.addEventListener('click',click);host.addEventListener('submit',submit);
    s.dispose=()=>{if(s.disposed)return;s.disposed=true;s.serial++;s.controller?.abort();host.removeEventListener('input',input);host.removeEventListener('change',change);host.removeEventListener('click',click);host.removeEventListener('submit',submit);if(mounted===s)mounted=null;};
    draw(s);void load(s);return s.dispose;
  }
  window.SixDCoverage=Object.freeze({mount,render,unmount:()=>mounted?.dispose()});
})();
