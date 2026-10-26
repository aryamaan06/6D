/* Recorded design evidence only. Selection never runs a calculation or inference. */
(() => {
  'use strict';
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const list=value=>Array.isArray(value)?value:[];
  const clone=value=>JSON.parse(JSON.stringify(value));
  const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
  const title=value=>String(value??'').replace(/_/g,' ').replace(/^./,c=>c.toUpperCase());
  const quantity=value=>value&&typeof value==='object'?(value.display_value!==undefined?esc(value.display_value)+' '+esc(window.SixDUnits?.format(value.unit??'')??value.unit??''):window.SixDUnits?.value(value.value,value.unit??'')??esc(String(value.value??'—'))+' '+esc(value.unit??'')):'—';
  const stateLabels={met:'Meets declared criterion',not_met:'Does not meet criterion',not_assessed:'Not assessed'};
  const trendLabels={improved:'Improved criterion margin',worsened:'Reduced criterion margin',unchanged:'Unchanged margin',criterion_changed:'Criterion changed',not_comparable:'Not comparable',added:'Added requirement',removed:'Removed requirement'};
  const badge=(value,labels,kind='')=>'<span class="dc-badge dc-'+esc(kind)+esc(String(value??'unknown').replace(/[^a-z_]/g,''))+'">'+esc(labels[value]||title(value)||'Not supplied')+'</span>';
  const button=(action,label,extra='')=>'<button type="button" class="dc-button" data-dc-action="'+action+'" '+extra+'>'+esc(label)+'</button>';
  const safeURL=value=>{try{const url=new URL(value);return ['http:','https:'].includes(url.protocol)&&!url.username&&!url.password?url.href:null;}catch{return null;}};
  const limitation='Margin trends describe recorded criteria under supplied conditions. They do not select a best design, prove cause or establish mission readiness.';
  let mounted=null;
  function active(s){return mounted===s&&!s.disposed&&s.host.isConnected;}
  function find(s,selector){return s.host.querySelector(selector);}
  function selection(s,side){
    if(s[side]===''||!/^\d+$/.test(s[side]))return null;
    return s.catalog?.options[Number(s[side])]??null;
  }
  function ready(s){const a=selection(s,'left'),b=selection(s,'right');return !!a&&!!b&&!same(a.selection,b.selection);}
  function resultCurrent(s){return !!s.result&&same(s.result.left?.selection,selection(s,'left')?.selection)&&same(s.result.right?.selection,selection(s,'right')?.selection);}
  function controls(s){
    if(!active(s))return;
    s.host.querySelectorAll('[data-dc-side]').forEach(node=>node.disabled=s.busy==='catalog');
    s.host.querySelectorAll('[data-dc-action="compare"]').forEach(node=>node.disabled=!!s.busy||!ready(s));
    s.host.querySelectorAll('[data-dc-action="export"],[data-dc-action="print"]').forEach(node=>node.disabled=!!s.busy||!resultCurrent(s));
    const refresh=find(s,'[data-dc-action="refresh"]');if(refresh)refresh.disabled=s.busy==='catalog';
    const error=find(s,'[data-dc-error]');if(error){error.hidden=!s.error;error.textContent=s.error;}
    const status=find(s,'[data-dc-status]');if(status)status.textContent=s.busy==='catalog'?'Reading recorded revisions and scenarios…':s.busy==='compare'?'Comparing the selected recorded evidence…':s.notice;
  }
  function selector(s,side,label){
    const options=list(s.catalog?.options);
    return '<label class="dc-field"><span>'+label+'</span><select data-dc-side="'+side+'"><option value="">Choose a recorded result</option>'+options.map((item,index)=>'<option value="'+index+'"'+(String(index)===s[side]?' selected':'')+'>'+esc(item.label)+(item.hypothetical?' · Hypothetical':'')+'</option>').join('')+'</select></label>';
  }
  function freshness(value){
    if(value?.current_implementation===false)return '<span class="dc-badge dc-limited">Historical implementation</span>';
    return '';
  }
  function side(value,name){
    return '<section class="dc-side"><span class="dc-eyebrow">'+name+' · '+(value.hypothetical?'Hypothetical scenario':'Recorded project review')+'</span><h3>'+esc(value.label)+'</h3>'+freshness(value.freshness)+'<p class="dc-small">'+(value.hypothetical?'Scenario evidence is exploratory and does not replace a saved project revision.':'This is the selected immutable run, including its own declared requirements and assumptions.')+'</p>'+(value.freshness?.note?'<p class="dc-small">'+esc(value.freshness.note)+'</p>':'')+'<dl class="dc-identity"><dt>Project revision</dt><dd>'+esc(value.project_revision??value.project?.revision??'—')+'</dd>'+(value.run_id?'<dt>Run</dt><dd>'+esc(value.run_id)+'</dd>':'')+(value.study_id?'<dt>Study / case</dt><dd>'+esc(value.study_id)+' / '+esc(value.case_index)+'</dd>':'')+(value.baseline_run_id?'<dt>Scenario baseline run</dt><dd>'+esc(value.baseline_run_id)+'</dd>':'')+'<dt>Review digest</dt><dd>'+esc(value.review_digest||value.review?.digest||'')+'</dd><dt>Record digest</dt><dd>'+esc(value.record_digest||'')+'</dd></dl></section>';
  }
  function inputTable(rows,label){
    if(!rows.length)return '<p class="dc-small">No '+esc(label.toLowerCase())+' in this comparison.</p>';
    return '<div class="dc-table-wrap"><table class="dc-table dc-input-table"><caption>'+esc(label)+'</caption><thead><tr><th scope="col">Input</th><th scope="col">A · recorded value / source</th><th scope="col">B · recorded value / source</th><th scope="col">Change</th></tr></thead><tbody>'+rows.map(row=>'<tr><th scope="row">'+esc(row.id)+'</th><td>'+quantity(row.left)+'<small>'+esc(row.left?.source||'Not present')+'</small></td><td>'+quantity(row.right)+'<small>'+esc(row.right?.source||'Not present')+'</small></td><td><strong>'+esc(title(row.change))+'</strong>'+(row.value_delta?'<small>B − A: '+quantity(row.value_delta)+'</small>':'')+(row.reason?'<small>'+esc(row.reason)+'</small>':'')+'</td></tr>').join('')+'</tbody></table></div>';
  }
  function findingSide(value){
    if(!value)return '<p class="dc-small">Requirement not present in this record.</p>';
    return badge(value.finding?.status,stateLabels)+'<dl class="dc-cell-facts"><dt>'+esc(value.metric_assessed===false?'Diagnostic output':'Result')+'</dt><dd>'+quantity(value.metric)+'</dd><dt>Criterion</dt><dd>'+esc(value.requirement?.operator||value.finding?.evidence?.operator||'')+' '+quantity(value.limit)+'</dd><dt>'+esc(value.margin?.kind==='absolute_difference'?'Exact-target difference':'Signed margin')+'</dt><dd>'+quantity(value.margin)+'</dd></dl>'+(value.metric?.note?'<p class="dc-small">'+esc(value.metric.note)+'</p>':'')+(value.finding?.reason?'<p class="dc-small">'+esc(value.finding.reason)+'</p>':'')+(value.margin?.definition?'<p class="dc-small">'+esc(value.margin.definition)+'</p>':'');
  }
  function reference(value){
    if(typeof value==='string')return '<li>'+esc(value)+'</li>';
    if(!value||typeof value!=='object')return '';
    const url=safeURL(value.url);
    return '<li>'+(url?'<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">'+esc(value.title||value.url)+'</a>':esc(value.title||value.url||'Recorded source'))+(value.note?'<p>'+esc(value.note)+'</p>':'')+'</li>';
  }
  function sideEvidence(value,label){
    if(!value)return '<section><h5>'+label+'</h5><p class="dc-small">No corresponding requirement.</p></section>';
    const model=value.model_context||{}, finding=value.finding||{};
    const assumptions=list(finding.assumptions).length?finding.assumptions:list(model.assumptions);
    const exclusions=list(finding.not_assessed).length?finding.not_assessed:list(model.not_assessed);
    const references=[...list(model.references),...list(model.applicability?.references)];
    return '<section><h5>'+label+' · evidence and scope</h5><p class="dc-small">'+esc(value.requirement?.model_id||model.model_id||'')+' · '+esc(value.requirement?.metric||finding.metric||'')+'</p>'+(assumptions.length?'<h6>Recorded assumptions</h6><ul>'+assumptions.map(item=>'<li>'+esc(item)+'</li>').join('')+'</ul>':'')+(exclusions.length?'<h6>Not assessed</h6><ul>'+exclusions.map(item=>'<li>'+esc(item)+'</li>').join('')+'</ul>':'')+(references.length?'<h6>Recorded reference context</h6><ul>'+references.map(reference).join('')+'</ul>':'')+'<details class="dc-record"><summary>Exact recorded model and source identities</summary><pre>'+esc(value.context_display??JSON.stringify({model_context:model,source_identity:value.source_identity},null,2))+'</pre></details></section>';
  }
  function requirementTable(rows){
    if(!rows.length)return '<p class="dc-empty">No declared requirement rows are available in these records.</p>';
    return '<div class="dc-table-wrap"><table class="dc-table dc-requirement-table"><caption>Declared requirement evidence · A and B retain their own criteria</caption><thead><tr><th scope="col">Requirement</th><th scope="col">A · recorded finding</th><th scope="col">B · recorded finding</th><th scope="col">Comparison</th></tr></thead><tbody>'+rows.map(row=>'<tr><th scope="row">'+esc(row.title||row.requirement_id)+'<small>'+esc(row.requirement_id)+'</small></th><td>'+findingSide(row.left)+'</td><td>'+findingSide(row.right)+'</td><td>'+badge(row.trend,trendLabels,'trend-')+(row.metric_delta?'<p class="dc-small">Metric B − A: '+quantity(row.metric_delta)+'</p>':'')+(row.margin_delta?'<p class="dc-small">Margin B − A: '+quantity(row.margin_delta)+'</p>':'')+([...list(row.comparability?.reasons),...list(row.notes)].length?'<ul class="dc-reasons">'+[...new Set([...list(row.comparability?.reasons),...list(row.notes)])].map(item=>'<li>'+esc(item)+'</li>').join('')+'</ul>':'')+'</td></tr><tr class="dc-detail-row"><td colspan="4"><details class="dc-evidence-details"><summary>Inspect assumptions, exclusions and source identities · '+esc(row.requirement_id)+'</summary><div class="dc-evidence-grid">'+sideEvidence(row.left,'A')+sideEvidence(row.right,'B')+'</div></details></td></tr>').join('')+'</tbody></table></div>';
  }
  function renderResult(value){
    const changed=list(value.inputs).filter(row=>row.change!=='unchanged'),unchanged=list(value.inputs).filter(row=>row.change==='unchanged');
    const compatible=value.compatibility?.status||'limited';
    return '<section class="dc-result" aria-label="Captured design comparison"><div class="dc-heading"><div><span class="dc-eyebrow">Captured evidence comparison</span><h3>A and B, in context.</h3></div>'+badge(compatible,{compatible:'Comparable within declared scope',limited:'Comparison has limits',incompatible:'Incompatible comparison scope'})+'</div><p class="dc-notice">'+limitation+'</p>'+ (list(value.compatibility?.reasons).length?'<ul class="dc-reasons">'+value.compatibility.reasons.map(item=>'<li>'+esc(item)+'</li>').join(''):'')+'<div class="dc-sides">'+side(value.left,'A')+side(value.right,'B')+'</div><section class="dc-section"><h3>Changed inputs</h3><p class="dc-small">Exact supplied units and provenance are retained. No unit conversion or causal explanation is inferred.</p>'+inputTable(changed,'Changed input records')+(unchanged.length?'<details class="dc-record dc-unchanged"><summary>Unchanged input records ('+unchanged.length+')</summary>'+inputTable(unchanged,'Unchanged input records')+'</details>':'')+'</section><section class="dc-section"><h3>Requirement tradeoffs</h3><p class="dc-small">Improved means more margin against an unchanged criterion, or a smaller exact-target difference for equality. A changed criterion, scope or implementation is labelled separately. Unassessed evidence is not a calculated failure.</p>'+requirementTable(list(value.requirements))+'</section>'+(list(value.models).length?'<details class="dc-record"><summary>Recorded model comparison ('+value.models.length+')</summary><pre>'+esc(value.models_display??JSON.stringify(value.models,null,2))+'</pre></details>':'')+'<footer class="dc-result-footer"><h4>Captured scope and reproduction identities</h4><p class="dc-identity">Comparison '+esc(value.digest||'')+'</p><ul class="dc-small">'+list(value.limitations).map(item=>'<li>'+esc(item)+'</li>').join('')+'</ul></footer></section>';
  }
  function draw(s){
    const options=list(s.catalog?.options), enough=options.length>=2;
    const unreviewed=list(s.catalog?.unreviewed_revisions);
    s.host.innerHTML='<article class="dc-page"><header class="dc-page-header"><div><span class="dc-eyebrow">Saved evidence · project R'+esc(s.ctx.revision)+'</span><h2>Compare the engineering tradeoffs.</h2><p>Select two recorded reviews or scenario cases. Explore their inputs, criteria and evidence without rerunning anything.</p></div>'+button('refresh','Refresh recorded choices')+'</header>'+(s.ctx.hasDraft?'<p class="dc-notice">This comparison uses saved records through R'+esc(s.ctx.revision)+'. Unsaved draft values are excluded.</p>':'')+'<div class="dc-selector-card">'+selector(s,'left','A · reference record')+selector(s,'right','B · comparison record')+'<div class="dc-actions">'+button('compare','Compare recorded designs')+'</div></div><p class="dc-live" data-dc-status role="status" aria-live="polite"></p><p class="dc-error" data-dc-error role="alert" hidden></p>'+(!s.catalog?'<p class="dc-empty">Reading the recorded comparison choices…</p>':!enough?'<section class="dc-empty"><h3>Two recorded results are needed.</h3><p>Save and review another revision, or calculate a hypothetical study through Scenarios. This screen does not create a result for you.</p><div class="dc-actions">'+(s.ctx.onRun?button('project','Go to project checks'):'')+(s.ctx.onScenarios?button('scenarios','Open scenarios'):'')+'</div></section>':'')+(unreviewed.length?'<details class="dc-record dc-no-print"><summary>Saved revisions awaiting recorded checks ('+unreviewed.length+')</summary><ul>'+unreviewed.map(item=>'<li>R'+esc(item.revision)+' · '+esc(item.reason)+'</li>').join('')+'</ul></details>':'')+(s.catalog?'<details class="dc-record dc-no-print"><summary>Recorded-choice scope and limits</summary><pre>'+esc(JSON.stringify(s.catalog.limits||{},null,2))+'</pre><ul class="dc-small">'+list(s.catalog.limitations).map(item=>'<li>'+esc(item)+'</li>').join('')+'</ul></details>':'')+'<div class="dc-output-actions dc-actions">'+button('export','Export captured comparison JSON')+button('print','Print comparison / Save PDF')+'</div><div data-dc-result>'+(resultCurrent(s)?renderResult(s.result):'<p class="dc-placeholder">Choose A and B, then compare. Selecting or refreshing records does not start a calculation, create a revision or call an AI model.</p>')+'</div></article>';
    if(s.catalog?.history_truncated){
      const notice=document.createElement('p');notice.className='dc-notice dc-no-print';
      notice.textContent='Recorded history is truncated to the catalog limits. Older runs or studies may not appear in these choices.';
      find(s,'.dc-selector-card').insertAdjacentElement('afterend',notice);
    }
    controls(s);
  }
  function invalidate(s){s.serial++;s.controller?.abort();s.result=null;s.resultRaw=null;s.busy='';s.error='';s.notice='Selection changed. Compare the current recorded choices before exporting.';draw(s);}
  function validCatalog(s,value){
    if(!value||value.project_id!==s.ctx.projectId||value.revision!==s.ctx.revision||!Array.isArray(value.options))throw Error('The recorded-choice context changed. Reopen this saved project.');
    if(value.options.some(item=>!item||!item.selection||!['run','scenario'].includes(item.selection.kind)))throw Error('A recorded choice has an unsupported selector. Refresh the saved project.');
    return value;
  }
  async function load(s){
    const serial=++s.serial;s.controller?.abort();s.controller=new AbortController();s.catalog=null;s.left='';s.right='';s.result=null;s.resultRaw=null;s.busy='catalog';s.error='';s.notice='';draw(s);
    try{
      const value=await s.ctx.api('/api/design-comparison/catalog?project_id='+encodeURIComponent(s.ctx.projectId)+'&revision='+encodeURIComponent(s.ctx.revision),undefined,{signal:s.controller.signal});
      if(!active(s)||serial!==s.serial)return;
      s.catalog=validCatalog(s,value);s.notice='Recorded choices loaded. Select A and B explicitly.';
    }catch(error){if(active(s)&&serial===s.serial&&error.name!=='AbortError')s.error=error.message||String(error);}
    finally{if(active(s)&&serial===s.serial){s.busy='';draw(s);}}
  }
  async function compare(s){
    if(s.busy||!ready(s))return;
    const left=clone(selection(s,'left').selection),right=clone(selection(s,'right').selection),serial=++s.serial;
    s.controller?.abort();s.controller=new AbortController();s.busy='compare';s.error='';s.result=null;s.resultRaw=null;s.notice='';draw(s);
    try{
      const body={project_id:s.ctx.projectId,revision:s.ctx.revision,left,right},options={signal:s.controller.signal};
      const captured=s.ctx.compareRaw?await s.ctx.compareRaw(body,options):{payload:await s.ctx.api('/api/design-comparison',body,options)};
      const value=captured.payload;
      if(!active(s)||serial!==s.serial)return;
      if(value?.project_id!==s.ctx.projectId||value.revision!==s.ctx.revision||!same(value.left?.selection,left)||!same(value.right?.selection,right))throw Error('The comparison did not match the selected recorded evidence. Select the records again.');
      s.result=clone(value);s.resultRaw=typeof captured.raw==='string'?captured.raw:null;s.notice='Captured comparison loaded. No calculation or stored finding was changed.';
    }catch(error){if(active(s)&&serial===s.serial&&error.name!=='AbortError')s.error=error.message||String(error);}
    finally{if(active(s)&&serial===s.serial){s.busy='';draw(s);}}
  }
  function exportJSON(s){
    if(!resultCurrent(s)||s.busy)return;
    const blob=new Blob([s.resultRaw??JSON.stringify(s.result,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');
    link.href=url;link.download='6d-design-comparison-'+String(s.result.digest||'captured').slice(0,12)+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function mount(host,ctx){
    unmount();
    const s={host,ctx,catalog:null,left:'',right:'',result:null,resultRaw:null,busy:'',error:'',notice:'',serial:0,controller:null,disposed:false,printDetails:[]};mounted=s;
    const change=event=>{const side=event.target.dataset.dcSide;if(!['left','right'].includes(side))return;s[side]=event.target.value;invalidate(s);};
    const click=event=>{const control=event.target.closest('[data-dc-action]');if(!control||!host.contains(control))return;const action=control.dataset.dcAction;if(action==='refresh'){void load(s);return;}if(action==='compare'){void compare(s);return;}if(action==='export'){exportJSON(s);return;}if(action==='print'){if(resultCurrent(s)&&!s.busy)window.print();return;}if(action==='project')ctx.onRun?.();if(action==='scenarios')ctx.onScenarios?.();};
    const beforePrint=()=>{if(!active(s)||s.printing)return;s.printing=true;s.printDetails=[...host.querySelectorAll('.dc-result details:not([open])')];s.printDetails.forEach(node=>node.open=true);};
    const afterPrint=()=>{s.printDetails.forEach(node=>{if(node.isConnected)node.open=false;});s.printDetails=[];s.printing=false;};
    host.addEventListener('change',change);host.addEventListener('click',click);window.addEventListener('beforeprint',beforePrint);window.addEventListener('afterprint',afterPrint);
    s.dispose=()=>{if(s.disposed)return;afterPrint();s.disposed=true;s.serial++;s.controller?.abort();host.removeEventListener('change',change);host.removeEventListener('click',click);window.removeEventListener('beforeprint',beforePrint);window.removeEventListener('afterprint',afterPrint);if(mounted===s)mounted=null;};
    draw(s);void load(s);return s.dispose;
  }
  function unmount(){mounted?.dispose();}
  window.SixDComparison=Object.freeze({mount,unmount});
})();
