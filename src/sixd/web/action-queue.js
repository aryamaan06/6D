/* Explicit engineering work tracking. No action changes a calculated finding. */
(() => {
  'use strict';
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const array=value=>Array.isArray(value)?value:[];
  const copy=value=>JSON.parse(JSON.stringify(value));
  const STATES=['todo','in_progress','ready_for_review','closed'];
  const LABELS={todo:'To do',in_progress:'In progress',ready_for_review:'Ready for review',closed:'Closed'};
  const FIELDS={title:240,next_check:8000,missing_evidence:8000,completion_criteria:4000,note:4000,closure_note:4000};
  const LIMITATION='Closing an action records workflow completion. It does not make a requirement pass, verify a reference or establish engineering approval.';
  let mounted=null;
  const option=(value,label,current)=>'<option value="'+esc(value)+'"'+(value===current?' selected':'')+'>'+esc(label)+'</option>';
  const button=(action,label,extra='')=>'<button type="button" class="aq-button" data-aq-action="'+action+'" '+extra+'>'+esc(label)+'</button>';
  const short=(value,max=130)=>String(value??'').length>max?String(value).slice(0,max-1)+'…':String(value??'');
  const exact=value=>value&&typeof value.value==='number'?esc(String(value.value))+' '+esc(value.unit):'Not supplied';
  const safeURL=value=>{try{const url=new URL(value);return ['http:','https:'].includes(url.protocol)&&!url.username&&!url.password?url.href:null;}catch{return null;}};
  function reviewLabel(value){return {current:'Recorded context matches',needs_review:'Context needs review',origin_unavailable:'Origin unavailable'}[value]||'Context not assessed';}
  function stateBadge(value){return '<span class="aq-state aq-'+(STATES.includes(value)?value:'unknown')+'">'+esc(LABELS[value]||'Unknown workflow state')+'</span>';}
  function reviewBadge(value){return '<span class="aq-review aq-review-'+(['current','needs_review','origin_unavailable'].includes(value)?value:'unknown')+'">'+esc(reviewLabel(value))+'</span>';}
  function scoped(action,options){
    if(!Array.isArray(options.requirementIds)&&!Array.isArray(options.modelIds))return true;
    const origin=action.origin||{};
    const requirementId=origin.requirement_id??(origin.kind==='finding'?origin.id:null);
    return (Array.isArray(options.requirementIds)&&options.requirementIds.includes(requirementId))||(Array.isArray(options.modelIds)&&options.modelIds.includes(origin.model_id));
  }
  function supportFacts(support){
    const snapshot=support.snapshot||{}, url=safeURL(snapshot.url);
    let content='';
    if(support.kind==='source'){
      content='<p class="aq-eyebrow">User-supplied reference · v'+esc(snapshot.version??'?')+'</p><strong>'+esc(snapshot.title||support.label||support.support_id)+'</strong>'+(snapshot.url?'<p class="aq-small aq-wrap">'+(url?'<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">'+esc(snapshot.url)+'</a>':esc(snapshot.url))+'</p>':'')+(snapshot.excerpt?'<blockquote>'+esc(snapshot.excerpt)+'</blockquote>':'')+(snapshot.details?'<p class="aq-small aq-preserve">'+esc(snapshot.details)+'</p>':'');
    }else{
      const finding=snapshot.finding||{};
      content='<p class="aq-eyebrow">Saved finding · '+esc(finding.status||snapshot.status||'Recorded status')+'</p><strong>'+esc(support.label||snapshot.requirement?.title||support.support_id)+'</strong>'+(finding.reason?'<p class="aq-small">'+esc(finding.reason)+'</p>':'')+(finding.evidence?'<dl class="aq-facts"><dt>Recorded metric</dt><dd>'+exact(finding.evidence.metric)+'</dd><dt>Declared limit</dt><dd>'+esc(snapshot.requirement?.operator||finding.evidence.operator||'')+' '+exact(finding.evidence.limit)+'</dd></dl>':'')+(snapshot.run_id?'<p class="aq-identity">Run '+esc(snapshot.run_id)+'</p>':'');
    }
    return '<article class="aq-support-record">'+content+'<p class="aq-identity">'+esc(support.support_id||'')+(support.context_digest?'<br>Context '+esc(support.context_digest):'')+'</p></article>';
  }
  function supports(records,open=false){return array(records).length?'<details class="aq-records"'+(open?' open':'')+'><summary>Saved supporting records ('+records.length+')</summary><div class="aq-support-records">'+records.map(supportFacts).join('')+'</div></details>':'<p class="aq-small">No supporting records are attached.</p>';}
  function reasons(action){return array(action.review_reasons).length?'<ul class="aq-reasons">'+action.review_reasons.map(value=>'<li>'+esc(value)+'</li>').join('')+'</ul>':'';}
  function history(action){
    const versions=array(action.history);
    return versions.length?'<details class="aq-records"><summary>Recorded action history ('+versions.length+')</summary><ol class="aq-history">'+versions.map(item=>'<li><div class="aq-heading"><strong>Version '+esc(item.version)+'</strong>'+stateBadge(item.status)+'</div><p class="aq-small">Saved R'+esc(item.basis_revision??'?')+' · origin context R'+esc(item.origin_basis_revision??item.basis_revision??'?')+(item.created_at?' · '+esc(item.created_at):'')+'</p>'+(item.title?'<p>'+esc(item.title)+'</p>':'')+(item.note?'<p class="aq-small aq-preserve">Note: '+esc(item.note)+'</p>':'')+(item.closure_note?'<p class="aq-small aq-preserve">Completion note: '+esc(item.closure_note)+'</p>':'')+supports(item.supports)+'<p class="aq-identity">'+esc(item.digest||'')+'</p></li>').join('')+'</ol></details>':'';
  }
  function actionDetail(action,includeHistory=false,openSupports=false){
    return '<div class="aq-heading"><strong>'+esc(action.title)+'</strong>'+stateBadge(action.status)+'</div><p class="aq-small aq-wrap">Origin: '+esc(action.origin?.label||action.origin?.target_id||'Recorded origin')+' · context R'+esc(action.origin_basis_revision??action.basis_revision)+'</p><p>'+reviewBadge(action.review_status)+'</p>'+reasons(action)+'<dl class="aq-detail-list"><dt>Next engineering check</dt><dd>'+esc(action.next_check)+'</dd><dt>Missing evidence or information</dt><dd>'+esc(action.missing_evidence||'No missing evidence recorded by the action author.')+'</dd><dt>Declared completion criteria</dt><dd>'+esc(action.completion_criteria)+'</dd></dl>'+(action.note?'<p class="aq-small aq-preserve">Work note: '+esc(action.note)+'</p>':'')+(action.closure_note?'<p class="aq-small aq-preserve">Completion note: '+esc(action.closure_note)+'</p>':'')+supports(action.supports,openSupports)+(includeHistory?history(action):'')+'<p class="aq-identity">Action '+esc(action.action_id)+' · v'+esc(action.version)+' · saved R'+esc(action.basis_revision)+'</p>';
  }
  function render(profile,options={}){
    if(!profile||!Array.isArray(profile.actions))return '<section class="aq-evidence"><h3>Engineering actions</h3><p class="aq-small">Action records are unavailable for this saved configuration.</p></section>';
    const selected=profile.actions.filter(action=>scoped(action,options));
    return '<section class="aq-evidence" aria-label="Linked engineering actions"><div class="aq-heading"><div><span class="aq-eyebrow">Supplemental work records</span><h3>Engineering actions</h3></div><span class="aq-count">'+selected.length+' action'+(selected.length===1?'':'s')+'</span></div><p class="aq-small">'+LIMITATION+'</p>'+(options.hasDraft?'<p class="aq-notice">These records describe saved R'+esc(profile.revision)+'. Draft changes have not been assessed against action context.</p>':'')+(selected.length?'<div class="aq-read-list">'+selected.map(action=>'<article class="aq-read-action">'+actionDetail(action,false,options.variant==='report')+'</article>').join(''):'<p class="aq-empty">No actions have been recorded in this scope. An empty queue does not establish that engineering work is complete.</p>')+'<details class="aq-records"><summary>Action snapshot and limits</summary><p class="aq-identity">Project '+esc(profile.project_id)+' · R'+esc(profile.revision)+'<br>Queue '+esc(profile.digest||'')+'</p><p class="aq-small">'+array(profile.limitations).map(esc).join('<br>')+'</p></details></section>';
  }
  function el(s,selector){return s.host.querySelector(selector);}
  function live(s){return !s.disposed&&mounted===s&&s.host.isConnected;}
  function readOnly(s){return s.ctx.hasDraft||s.ctx.canEdit===false;}
  function checkProfile(s,value){
    if(!value||value.project_id!==s.ctx.projectId||Number(value.revision)!==Number(s.ctx.revision)||value.context!=='saved'||!Array.isArray(value.actions)||!Array.isArray(value.origins)||!Array.isArray(value.support_options)||typeof value.digest!=='string')throw Error('The action queue context changed. Reload this saved project before continuing.');
    return value;
  }
  function blank(s){
    s.record=null;s.dirty=false;s.editorDigest=s.profile?.digest||'';
    s.editor={origin_id:'',title:'',next_check:'',missing_evidence:'',completion_criteria:'',note:'',closure_note:'',support_ids:[],status:'todo'};
  }
  function select(s,action){
    s.record=copy(action);s.dirty=false;s.editorDigest=s.profile.digest;
    s.editor={origin_id:action.origin?.target_id||'',title:action.title,next_check:action.next_check,missing_evidence:action.missing_evidence||'',completion_criteria:action.completion_criteria,note:action.note||'',closure_note:action.closure_note||'',support_ids:array(action.support_ids).length?[...action.support_ids]:array(action.supports).map(support=>support.support_id),status:action.status};
  }
  function transitions(current){
    const allowed={todo:['todo','in_progress'],in_progress:['todo','in_progress','ready_for_review'],ready_for_review:['todo','in_progress','ready_for_review','closed'],closed:['in_progress','closed']};
    return allowed[current]||[];
  }
  function currentOrigin(s){return s.profile?.origins.find(origin=>origin.target_id===s.editor.origin_id);}
  function canSave(s){
    if(s.busy||readOnly(s)||!s.profile||!s.editor.title.trim()||!s.editor.next_check.trim()||!s.editor.completion_criteria.trim())return false;
    if(!s.record)return !!currentOrigin(s);
    if(!transitions(s.record.status).includes(s.editor.status))return false;
    return s.editor.status!=='closed'||(s.record.review_status==='current'&&s.editor.support_ids.length>0&&!!s.editor.closure_note.trim());
  }
  function controls(s){
    if(!live(s))return;
    s.host.querySelectorAll('button,input,textarea,select').forEach(node=>node.disabled=!!s.busy||readOnly(s));
    const refresh=el(s,'[data-aq-action="refresh"]');if(refresh)refresh.disabled=!!s.busy;
    s.host.querySelectorAll('[data-aq-action="select"]').forEach(node=>node.disabled=!!s.busy);
    const save=el(s,'[data-aq-action="save"]');if(save)save.disabled=!canSave(s);
    const suggested=el(s,'[data-aq-action="suggest"]');if(suggested)suggested.disabled=!!s.busy||readOnly(s)||!currentOrigin(s);
    const supportLocked=!!s.record&&s.record.review_status!=='current';
    s.host.querySelectorAll('[data-aq-support]').forEach(node=>node.disabled=!!s.busy||readOnly(s)||supportLocked);
    const review=el(s,'[data-aq-action="review"]');if(review)review.disabled=!!s.busy||readOnly(s)||!s.record?.current_origin;
    const error=el(s,'[data-aq-error]');if(error){error.textContent=s.error;error.hidden=!s.error;}
    const busy=el(s,'[data-aq-busy]');if(busy)busy.textContent=s.busy==='load'?'Loading recorded engineering work…':s.busy?'Saving an explicit action version…':s.notice;
  }
  function board(s){
    return '<section class="aq-board" aria-label="Engineering action workflow">'+STATES.map(state=>{
      const rows=s.profile.actions.filter(action=>action.status===state);
      return '<section class="aq-column aq-column-'+state+'" aria-label="'+LABELS[state]+' actions"><header><span class="aq-state-dot" aria-hidden="true"></span><h3>'+LABELS[state]+'</h3><span class="aq-count">'+rows.length+'</span></header><div class="aq-cards">'+(rows.length?rows.map(action=>'<button type="button" class="aq-card'+(s.record?.action_id===action.action_id?' aq-selected':'')+'" data-aq-action="select" data-aq-id="'+esc(action.action_id)+'" aria-pressed="'+(s.record?.action_id===action.action_id)+'"><strong>'+esc(action.title)+'</strong><span class="aq-small">'+esc(short(action.next_check))+'</span><span class="aq-card-origin">'+esc(short(action.origin?.label||action.origin?.target_id||'Recorded origin',80))+'</span>'+(action.review_status!=='current'?reviewBadge(action.review_status):'')+'<span class="aq-card-meta">Saved R'+esc(action.basis_revision)+' · v'+esc(action.version)+'</span></button>').join(''):'<p class="aq-column-empty">No recorded actions</p>')+'</div></section>';
    }).join('')+'</section>';
  }
  function field(s,name,label,rows=3){
    return '<label class="aq-field">'+esc(label)+(name==='title'?'<input maxlength="'+FIELDS[name]+'" data-aq-field="'+name+'" value="'+esc(s.editor[name])+'">':'<textarea rows="'+rows+'" maxlength="'+FIELDS[name]+'" data-aq-field="'+name+'">'+esc(s.editor[name])+'</textarea>')+'</label>';
  }
  function supportPicker(s){
    const options=s.profile.support_options, selected=new Set(s.editor.support_ids), locked=s.record.review_status!=='current', unavailable=s.editor.support_ids.filter(id=>!options.some(option=>option.support_id===id));
    return '<fieldset class="aq-support-picker"><legend>Supporting findings or references</legend><p class="aq-small">Choose recorded material supporting the declared completion criteria. Relevance and sufficiency remain your judgement. A failing or unassessed finding stays failing or unassessed.</p>'+(locked?'<p class="aq-notice">Review changed context first. Current options are not selected below; the action’s original supporting records stay pinned in Preserved supporting evidence.</p>':'')+(options.length?'<div class="aq-support-options">'+options.map(option=>'<label><input type="checkbox" data-aq-support="'+esc(option.support_id)+'"'+(selected.has(option.support_id)&&!locked?' checked':'')+'><span>'+esc(option.label)+'<small>'+esc(option.kind==='source'?'User-supplied reference':'Recorded finding')+'</small></span></label>').join('')+'</div>':'<p class="aq-empty">No saved finding or reference is available. Add evidence through its existing workflow before closing this action.</p>')+(unavailable.length?'<p class="aq-small aq-wrap">Previously selected records no longer offered in this context: '+unavailable.map(esc).join(', ')+'. Their captured contents remain below.</p>':'')+'</fieldset>';
  }
  function editor(s){
    const record=s.record;
    return '<section class="aq-editor" data-aq-editor aria-labelledby="aq-editor-title"><header class="aq-heading"><div><span class="aq-eyebrow">'+(record?'Recorded action · v'+esc(record.version):'New action · explicit creation')+'</span><h3 id="aq-editor-title">'+(record?'Review and update the work':'Turn a finding into a next step')+'</h3></div>'+(record?button('new','New action'):'')+'</header>'+(record?'<p class="aq-small aq-wrap">Origin: '+esc(record.origin?.label||record.origin?.target_id)+' · context R'+esc(record.origin_basis_revision??record.basis_revision)+'</p><p>'+stateBadge(record.status)+' '+reviewBadge(record.review_status)+'</p>'+reasons(record):'<label class="aq-field">Finding or source-review flag<select data-aq-field="origin_id">'+option('','Choose a recorded origin',s.editor.origin_id)+s.profile.origins.map(origin=>option(origin.target_id,origin.label,s.editor.origin_id)).join('')+'</select></label><div class="aq-actions">'+button('suggest','Use suggested steps')+'</div><p class="aq-small">Suggestions are deterministic review guidance from recorded evidence. Inspect and edit them before creating an action.</p>')+(!record&&!s.profile.origins.length?'<p class="aq-notice">No unmet/unassessed finding or source-review flag is available in this saved context. Run checks or review flagged source links first. An empty origin list is not a mission-completeness assessment.</p>':'')+'<div class="aq-editor-grid"><div>'+field(s,'title','Action title',1)+field(s,'next_check','Next engineering check',4)+field(s,'missing_evidence','Missing evidence or information',3)+'</div><div>'+field(s,'completion_criteria','Declared completion criteria',4)+field(s,'note','Work notes',4)+(record?'<label class="aq-field">Workflow state<select data-aq-field="status">'+transitions(record.status).map(state=>option(state,LABELS[state],s.editor.status)).join('')+'</select></label><p class="aq-small">Advance one stage at a time. Reopening is explicit; workflow state remains separate from the engineering finding.</p>':'')+'</div></div>'+(record?'<section class="aq-completion">'+supportPicker(s)+field(s,'closure_note','Completion note — required to close',3)+'<p class="aq-small">Closing requires Ready for review, a current recorded context, at least one supporting record and your completion note.</p></section>':'')+'<div class="aq-actions">'+button('save',record?'Save action version':'Create action')+(record&&record.review_status!=='current'?button('review',record.status==='closed'||record.status==='ready_for_review'?'Adopt current context and reopen':'Review changed context'):'')+'</div>'+(record&&record.review_status!=='current'?'<p class="aq-small">Reviewing adopts the current origin and clears current support selections and completion note. Prior versions remain in history. A closed or ready action returns to In progress.</p>':'')+'<p class="aq-small">'+LIMITATION+'</p>'+(record?'<section class="aq-pinned"><h4>Preserved supporting evidence</h4>'+supports(record.supports)+history(record)+'<p class="aq-identity">Action '+esc(record.action_id)+'<br>'+esc(record.digest||'')+'</p></section>':'')+'</section>';
  }
  function draw(s){
    if(!live(s))return;
    s.host.innerHTML='<article class="aq-page"><header class="aq-page-header"><div><span class="aq-eyebrow">Engineering action queue · saved R'+esc(s.ctx.revision)+'</span><h2>Move findings into engineering work.</h2><p>Track the next check, the missing evidence and the conditions for completing the task.</p></div><div class="aq-actions">'+button('new','New action')+button('refresh','Refresh queue')+'</div></header><p class="aq-notice">'+(s.ctx.hasDraft?'Save or discard the draft before changing actions. Displayed actions still describe the saved configuration.':s.ctx.canEdit===false?'This historical revision is read-only. Select the latest saved revision to change the queue.':LIMITATION)+'</p><p class="aq-live" data-aq-busy role="status" aria-live="polite"></p><p class="aq-error" data-aq-error role="alert" hidden></p>'+(s.profile?board(s)+editor(s):'<p class="aq-empty">Loading the saved action queue…</p>')+'</article>';
    controls(s);
  }
  async function load(s){
    if(!live(s)||s.busy)return;
    s.busy='load';s.error='';const serial=++s.serial;controls(s);
    try{
      const value=await s.ctx.api('/api/actions?project_id='+encodeURIComponent(s.ctx.projectId)+'&revision='+encodeURIComponent(s.ctx.revision));
      if(!live(s)||serial!==s.serial)return;
      const initial=!s.profile;s.profile=checkProfile(s,value);
      if(initial){blank(s);if(s.ctx.originId&&s.profile.origins.some(origin=>origin.target_id===s.ctx.originId))s.editor.origin_id=s.ctx.originId;}
      s.notice=initial?'Saved work loaded. No action or calculation was started.':'Queue refreshed. Your form is preserved; select an action again or use current suggestions to adopt its latest displayed context.';
    }catch(error){if(live(s)&&serial===s.serial)s.error=error.message||String(error);}
    finally{if(live(s)&&serial===s.serial){s.busy='';draw(s);}}
  }
  async function mutate(s,path,payload,kind){
    if(!live(s)||s.busy||readOnly(s))return;
    s.busy='save';s.error='';s.notice='';const serial=++s.serial, oldIds=new Set(s.profile.actions.map(action=>action.action_id)), id=s.record?.action_id;controls(s);
    try{
      const value=await s.ctx.api(path,{project_id:s.ctx.projectId,revision:s.ctx.revision,expected_digest:s.editorDigest,...payload});
      if(!live(s)||serial!==s.serial)return;
      s.profile=checkProfile(s,value);
      const action=kind==='create'?s.profile.actions.find(action=>!oldIds.has(action.action_id)):s.profile.actions.find(action=>action.action_id===id);
      if(action)select(s,action);else blank(s);
      s.busy='';s.notice=kind==='review'?'Current origin recorded; prior evidence remains in history. Review and select supporting records before completing this task.':'Action version saved. Calculated requirement findings are unchanged.';draw(s);s.ctx.onChange?.(copy(s.profile));
    }catch(error){if(live(s)&&serial===s.serial){s.error=error.message||String(error);s.busy='';controls(s);}}
  }
  function mount(host,ctx){
    unmount();
    const s={host,ctx,disposed:false,profile:null,record:null,editor:null,editorDigest:'',dirty:false,busy:'',error:'',notice:'',serial:0};mounted=s;blank(s);
    const input=event=>{
      const target=event.target;
      if(target.dataset.aqField){
        const name=target.dataset.aqField;s.editor[name]=target.value;s.dirty=true;s.error='';
        if(name==='origin_id')s.editorDigest=s.profile?.digest||'';
        if(name==='status'&&target.value!=='closed'){s.editor.closure_note='';const note=el(s,'[data-aq-field="closure_note"]');if(note)note.value='';}
        controls(s);
      }
      if(target.hasAttribute('data-aq-support')){
        const selected=new Set(s.editor.support_ids);if(target.checked)selected.add(target.dataset.aqSupport);else selected.delete(target.dataset.aqSupport);s.editor.support_ids=[...selected];s.dirty=true;s.error='';controls(s);
      }
    };
    const click=event=>{
      const control=event.target.closest('[data-aq-action]');if(!control||!host.contains(control))return;
      const action=control.dataset.aqAction;
      if(action==='refresh'){void load(s);return;}
      if(s.busy)return;
      if(action==='select'){
        const record=s.profile.actions.find(action=>action.action_id===control.dataset.aqId);if(record){select(s,record);s.error='';s.notice='';draw(s);el(s,'[data-aq-editor]')?.scrollIntoView({block:'start',behavior:'smooth'});}return;
      }
      if(readOnly(s))return;
      if(action==='new'){blank(s);s.error='';s.notice='';draw(s);el(s,'[data-aq-field="origin_id"]')?.focus();return;}
      if(action==='suggest'){
        const origin=currentOrigin(s);if(!origin)return;
        for(const name of ['title','next_check','missing_evidence','completion_criteria'])s.editor[name]=String(origin.suggested?.[name]||'');
        s.editorDigest=s.profile.digest;s.dirty=true;s.error='';s.notice='Suggested steps copied for your review; nothing has been saved.';draw(s);return;
      }
      if(action==='save'){
        if(!canSave(s))return;
        if(!s.record){const spec=Object.fromEntries(['origin_id','title','next_check','missing_evidence','completion_criteria','note'].map(name=>[name,s.editor[name]]));void mutate(s,'/api/actions',{spec},'create');}
        else{const spec=Object.fromEntries(['title','next_check','missing_evidence','completion_criteria','status','note','closure_note','support_ids'].map(name=>[name,copy(s.editor[name])]));void mutate(s,'/api/actions/update',{action_id:s.record.action_id,base_version:s.record.version,spec},'update');}return;
      }
      if(action==='review'&&s.record?.current_origin)void mutate(s,'/api/actions/review',{action_id:s.record.action_id,base_version:s.record.version},'review');
    };
    host.addEventListener('input',input);host.addEventListener('change',input);host.addEventListener('click',click);
    s.dispose=()=>{if(s.disposed)return;s.disposed=true;s.serial++;host.removeEventListener('input',input);host.removeEventListener('change',input);host.removeEventListener('click',click);if(mounted===s)mounted=null;};
    draw(s);void load(s);return s.dispose;
  }
  function unmount(){mounted?.dispose();}
  window.SixDActions=Object.freeze({mount,unmount,render});
})();
