/* Hypothetical evidence is separate from saved revision findings. No inference. */
(() => {
  'use strict';
  let mounted=null;
  const sessions=new Map();
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=v=>v===null||v===undefined?'—':String(v);
  const label=s=>({met:'Meets criterion',not_met:'Does not meet',not_assessed:'Not assessed'}[s]||s);
  const measure=r=>r?esc(num(r.value)+' '+r.unit):'No numeric evidence';
  const badge=s=>'<span class="sc-badge sc-'+esc(s)+'">'+esc(label(s))+'</span>';
  const option=(v,l,selected)=>'<option value="'+esc(v)+'" '+(v===selected?'selected':'')+'>'+esc(l)+'</option>';
  const button=(action,text,disabled=false)=>'<button type="button" class="sd-button" data-sc="'+action+'" '+(disabled?'disabled':'')+'>'+text+'</button>';
  function unmount(){if(mounted){mounted.closed=true;mounted.host.replaceChildren();mounted=null;}}
  function mount(host,ctx){
    unmount();
    const key=ctx.projectId+':'+ctx.revision;
    if(!sessions.has(key))sessions.set(key,{name:'',source:'',mode:'sweep',input:'',values:'',cases:[{name:'',changes:[{input:'',value:''}]}],selected:'',requirement:''});
    const s={host,ctx,form:sessions.get(key),closed:false,busy:false,error:'',list:null,detail:null,request:0,status:null};
    mounted=s;
    const live=()=>mounted===s&&!s.closed&&host.isConnected;
    const query='?project_id='+encodeURIComponent(ctx.projectId)+'&revision='+ctx.revision;
    const inputs=Object.entries(ctx.project.inputs);
    function role(id){
      const models=ctx.project.models.filter(m=>Object.values(m.inputs).includes(id)).map(m=>m.id);
      const criteria=ctx.project.requirements.filter(r=>r.limit_input===id).map(r=>r.id);
      return [models.length?'Model parameter: '+models.join(', '):'',criteria.length?'Criterion: '+criteria.join(', '):''].filter(Boolean).join(' · ')||'Unreferenced input; no calculation dependency declared';
    }
    function inputOptions(selected){return option('','Choose a baseline input',selected)+inputs.map(([id,r])=>option(id,id+' ('+r.unit+')',selected)).join('');}
    function remember(){
      const f=s.form;
      for(const field of ['name','source','mode','input','values']){const el=host.querySelector('[data-sc-field="'+field+'"]');if(el)f[field]=el.value;}
      host.querySelectorAll('[data-case-name]').forEach(el=>{f.cases[Number(el.dataset.caseName)].name=el.value;});
      host.querySelectorAll('[data-change-input]').forEach(el=>{const [i,j]=el.dataset.changeInput.split(':').map(Number);f.cases[i].changes[j].input=el.value;});
      host.querySelectorAll('[data-change-value]').forEach(el=>{const [i,j]=el.dataset.changeValue.split(':').map(Number);f.cases[i].changes[j].value=el.value;});
    }
    function canRun(){return !s.busy&&!ctx.hasDraft&&ctx.currentRunId&&s.list?.baseline_run_id===ctx.currentRunId&&s.status&&!s.status.restart_required;}
    function numeric(text){
      const value=String(text).trim();
      if(!/^-?(0|[1-9]\d*)(\.\d+)?([eE][+-]?\d+)?$/.test(value)||!Number.isFinite(Number(value)))throw Error('Enter finite decimal numbers explicitly. Empty values are not zero.');
      return Number(value);
    }
    function specification(){
      remember();const f=s.form;
      const value={schema:'sixd.scenario-spec.v1',name:f.name.trim(),source:f.source.trim(),mode:f.mode};
      if(!value.name||!value.source)throw Error('Enter a study name and the source or justification for these hypothetical values.');
      if(f.mode==='sweep'){
        if(!ctx.project.inputs[f.input])throw Error('Choose a baseline input.');
        const values=f.values.split(',').map(numeric);
        if(values.length<2||values.length>16||new Set(values).size!==values.length)throw Error('Supply 2–16 distinct comma-separated values.');
        return {...value,input_id:f.input,values};
      }
      return {...value,cases:f.cases.map(c=>{
        if(!c.name.trim())throw Error('Give every alternative a name.');
        const changes={};
        for(const row of c.changes){if(!ctx.project.inputs[row.input])throw Error('Choose an input for every change.');if(row.input in changes)throw Error('An alternative cannot change the same input twice.');changes[row.input]=numeric(row.value);}
        return {name:c.name.trim(),changes};
      })};
    }
    function alternatives(){return s.form.cases.map((c,i)=>'<fieldset class="sc-case"><legend>Alternative '+(i+1)+'</legend><label class="sd-field">Case name<input class="sd-input" data-case-name="'+i+'" value="'+esc(c.name)+'" maxlength="120"></label>'+c.changes.map((row,j)=>'<div class="sc-change"><label class="sd-field">Baseline input<select class="sd-input" data-change-input="'+i+':'+j+'">'+inputOptions(row.input)+'</select></label><label class="sd-field">New value · '+esc(ctx.project.inputs[row.input]?.unit||'select input')+'<input class="sd-input" inputmode="decimal" data-change-value="'+i+':'+j+'" value="'+esc(row.value)+'"></label>'+button('remove-change:'+i+':'+j,'Remove change',c.changes.length===1)+'</div>').join('')+'<div class="sd-action-row">'+button('add-change:'+i,'Add input change',c.changes.length>=8)+button('remove-case:'+i,'Remove alternative',s.form.cases.length===1)+'</div></fieldset>').join('')+button('add-case','Add alternative',s.form.cases.length>=16);}
    function form(){
      const f=s.form,reason=ctx.hasDraft?'Save or discard your draft before studying a saved baseline.':!ctx.currentRunId?'Run checks for this saved revision first.':s.status?.restart_required?'6D needs a backend restart before new calculations.':s.list&&s.list.baseline_run_id!==ctx.currentRunId?'The baseline changed since this project was opened. Reload the saved project to select its current run.':'';
      return '<section class="sc-builder"><div class="sd-section-heading"><h2>Create a study</h2><span class="sd-chip">Local calculations · no model calls</span></div><p>Vary supplied values while keeping saved R'+ctx.revision+' unchanged. Only declared model bindings propagate effects.</p>'+(reason?'<div class="sd-notice">'+esc(reason)+(!ctx.hasDraft&&!ctx.currentRunId?button('baseline','Run baseline checks'):ctx.currentRunId&&s.list&&s.list.baseline_run_id!==ctx.currentRunId?button('reload','Reload saved project'): '')+'</div>':'')+'<div class="sc-form-grid"><label class="sd-field">Study name<input class="sd-input" maxlength="120" data-sc-field="name" value="'+esc(f.name)+'"></label><label class="sd-field">Study type<select class="sd-input" data-sc-field="mode">'+option('sweep','Single-input sweep',f.mode)+option('alternatives','Named alternatives',f.mode)+'</select></label></div><label class="sd-field">Source and assumptions<textarea class="sd-input" rows="2" maxlength="1200" data-sc-field="source">'+esc(f.source)+'</textarea></label>'+(f.mode==='sweep'?'<div class="sc-form-grid"><label class="sd-field">Baseline input<select class="sd-input" data-sc-field="input">'+inputOptions(f.input)+'</select></label><label class="sd-field">Explicit values · '+esc(ctx.project.inputs[f.input]?.unit||'select input')+'<input class="sd-input" data-sc-field="values" value="'+esc(f.values)+'" aria-describedby="sc-values-note"></label></div><p id="sc-values-note" class="sd-small">Enter 2–16 distinct decimal values, separated by commas. No values are generated or assumed.</p>'+(f.input?'<p class="sd-small sc-role">Baseline: '+measure(ctx.project.inputs[f.input])+'. '+esc(role(f.input))+'.</p>':''):alternatives())+'<div class="sd-action-row">'+button('run',s.busy?'Calculating…':'Run and save study',!canRun())+'</div><p class="sd-small sd-muted">A study does not create a project revision, change canonical findings, or establish an optimum or safe operating range.</p></section>';
    }
    function findingTable(rows){return '<div class="sc-table-wrap"><table class="sd-table"><thead><tr><th>Requirement</th><th>Result</th><th>Criterion</th><th>Margin / exact difference</th><th>Finding</th></tr></thead><tbody>'+rows.map(r=>'<tr><td>'+esc(r.title)+'<br><small>'+esc(r.requirement_id)+'</small></td><td>'+measure(r.evidence?.metric)+'</td><td>'+(r.evidence?esc(r.evidence.operator)+' '+measure(r.evidence.limit):'Unassessed')+'</td><td>'+measure(r.margin)+'</td><td>'+badge(r.status)+'</td></tr>').join('')+'</tbody></table></div>';}
    function plot(receipt,rows){
      const sweep=receipt.spec.mode==='sweep';
      const points=rows.map((r,i)=>({r,x:sweep?receipt.spec.values[i]:i,index:i})).filter(p=>p.r.evidence);
      if(!points.length)return '<p>No numeric evidence for this requirement in the tested cases.</p>';
      const base=rows[0].baseline_evidence;
      const xs=points.map(p=>p.x),ys=points.flatMap(p=>[p.r.evidence.metric.value,p.r.evidence.limit.value]);
      if(base)ys.push(base.metric.value);
      // Normalize before subtracting so finite extreme values cannot overflow chart geometry.
      const scale=values=>{const mag=Math.max(...values.map(Math.abs))||1,lo=Math.min(...values.map(v=>v/mag)),hi=Math.max(...values.map(v=>v/mag));return v=>hi===lo?.5:(v/mag-lo)/(hi-lo);};
      const x=scale(xs),y=scale(ys),px=v=>65+640*x(v),py=v=>225-180*y(v);
      const tick=v=>{const [m,e]=Number(v).toPrecision(5).split('e');return (m.includes('.')?m.replace(/\.?0+$/,''):m)+(e?'e'+e:'');};
      return '<svg class="sc-chart" viewBox="0 0 780 290" role="img" aria-label="Tested case results and each case criterion; no interpolated predictions"><path d="M65 35V225H720" fill="none" stroke="#b4becb"/>'+[Math.min(...ys),Math.max(...ys)].map(v=>'<text x="57" y="'+(py(v)+4)+'" text-anchor="end">'+esc(tick(v))+'</text>').join('')+(base?'<path d="M65 '+py(base.metric.value)+'H720" stroke="#8c98a8" stroke-dasharray="4 4"/>':'')+points.map(p=>'<g><circle cx="'+px(p.x)+'" cy="'+py(p.r.evidence.metric.value)+'" r="5" fill="#3563cc"><title>'+esc(receipt.cases[p.index].name+': '+num(p.r.evidence.metric.value)+' '+p.r.evidence.metric.unit)+'</title></circle><path d="M'+(px(p.x)-5)+' '+py(p.r.evidence.limit.value)+'h10" stroke="#be7725" stroke-width="3"><title>'+esc('Own criterion: '+p.r.evidence.operator+' '+num(p.r.evidence.limit.value))+'</title></path><text x="'+px(p.x)+'" y="248" text-anchor="middle">'+esc(sweep?tick(p.x):'C'+(p.index+1))+'</text></g>').join('')+'<text x="390" y="279" text-anchor="middle">'+esc(sweep?receipt.spec.input_id+' ('+receipt.baseline.review.project.inputs[receipt.spec.input_id].unit+')':'Named case (C1, C2, …)')+'</text><text x="65" y="20">'+esc(rows[0].metric+' ('+points[0].r.evidence.metric.unit+')')+'</text></svg><p class="sc-legend"><span>● Calculated result</span><span>━ Each case criterion</span><span>┄ Baseline result</span></p><p class="sd-small">Points show tested values only. '+(rows.length-points.length)+' unassessed case(s) have no plotted result. Exact numbers are in the table.</p>';
    }
    function report(){
      if(!s.detail)return '<section class="sc-empty"><h2>Compare evidence, not guesses</h2><p>Run an explicit study or open a saved record. Results will show which criteria change and which calculations are reused.</p></section>';
      const d=s.detail,r=d.receipt;
      if(!r.cases[0].findings.some(f=>f.requirement_id===s.form.requirement))s.form.requirement=r.cases[0].findings[0]?.requirement_id||'';
      const rows=r.cases.map(c=>c.findings.find(f=>f.requirement_id===s.form.requirement));
      const baseline=r.baseline.review.project;
      return '<article class="sc-report"><div class="sd-section-heading"><div><span class="sd-label">Saved hypothetical study · R'+r.revision+'</span><h2>'+esc(r.spec.name)+'</h2></div><span class="sd-chip">'+(d.freshness.historical?'Historical baseline or sources':'Matches selected baseline')+'</span></div><p>'+esc(r.spec.source)+'</p><p class="sc-identity">Project '+esc(r.project_id)+' · '+esc(r.created_at)+'<br>Study '+esc(r.study_id)+'<br>Baseline run '+esc(r.baseline.run_id)+'<br>Baseline review '+esc(r.baseline.review.digest)+'<br>Study digest '+esc(d.receipt_digest)+'</p><div class="sd-notice">These are hypothetical cases against saved R'+r.revision+'. They do not replace its findings or authorize launch.'+(d.freshness.historical?' The selected revision, latest baseline run or installed sources differ; inspect the recorded context.':'')+'</div><div class="sd-action-row sc-no-print">'+button('export','Export study JSON')+button('print','Print report / Save PDF')+'</div><label class="sd-field sc-no-print">Compare a requirement<select class="sd-input" data-sc-requirement>'+r.cases[0].findings.map(f=>option(f.requirement_id,f.title,s.form.requirement)).join('')+'</select></label><h3>'+esc(rows[0].title)+'</h3><p>Baseline: '+measure(rows[0].baseline_evidence?.metric)+' · '+(rows[0].baseline_evidence?esc(rows[0].baseline_evidence.operator)+' '+measure(rows[0].baseline_evidence.limit):'No numeric evidence')+' · '+badge(rows[0].baseline_status)+'</p>'+plot(r,rows)+'<div class="sc-table-wrap"><table class="sd-table sc-comparison"><thead><tr><th>Tested case / changes</th><th>Result / change</th><th>Own criterion</th><th>Margin / exact difference</th><th>Baseline → case</th></tr></thead><tbody>'+rows.map((f,i)=>'<tr><td>C'+(i+1)+' · '+esc(r.cases[i].name)+'<br>'+Object.entries(r.cases[i].changes).map(([id,c])=>esc(id)+': '+measure(c.before)+' → '+measure(c.after)).join('<br>')+'</td><td>'+measure(f.evidence?.metric)+'<br><small>Δ '+esc(num(f.metric_change))+' '+esc(f.evidence?.metric.unit||'')+'</small></td><td>'+(f.evidence?esc(f.evidence.operator)+' '+measure(f.evidence.limit):'Unassessed')+'</td><td>'+measure(f.margin)+'<br><small>'+esc(f.margin?.definition||'No margin calculated')+'</small></td><td>'+badge(f.baseline_status)+' → '+badge(f.status)+'</td></tr>').join('')+'</tbody></table></div><h3>Case evidence and next checks</h3>'+r.cases.map((c,i)=>{
        const f=rows[i];return '<section class="sc-result-case"><h4>C'+(i+1)+' · '+esc(c.name)+'</h4><p>'+c.counts.met+' criteria met · '+c.counts.not_met+' not met · '+c.counts.not_assessed+' not assessed</p><p class="sd-small">Calculated models: '+esc(c.executed_model_ids.join(', ')||'none')+'. Reused baseline models: '+esc(c.reused_model_ids.join(', ')||'none')+'.</p><p><strong>'+esc(f.title)+':</strong> '+esc(f.reason)+'</p><p><strong>Next check:</strong> '+esc(f.next_step)+'</p><details class="sc-disclosure"><summary>All criteria, assumptions and exclusions for C'+(i+1)+'</summary>'+findingTable(c.findings)+c.findings.map(row=>'<h4>'+esc(row.requirement_id)+'</h4><p>'+esc(row.reason)+'</p><p>'+esc(row.next_step)+'</p><ul>'+[...row.assumptions,...row.not_assessed].map(text=>'<li>'+esc(text)+'</li>').join('')+'</ul>').join('')+'<h4>Review exclusions</h4><ul>'+c.review.exclusions.map(text=>'<li>'+esc(text)+'</li>').join('')+'</ul><p class="sc-identity">Case review '+esc(c.review.digest)+'</p></details></section>';
      }).join('')+'<details class="sc-disclosure"><summary>Exact inputs, study specification and calculation provenance</summary><pre>'+esc(JSON.stringify({spec:r.spec,baseline_inputs:baseline.inputs,baseline_model_origins:r.baseline.model_origins,cases:r.cases.map(c=>({name:c.name,changes:c.changes,executed_model_ids:c.executed_model_ids,reused_model_origins:c.reused_model_origins,review_digest:c.review.digest})),sources:r.sources},null,2))+'</pre></details><h3>Scope and limitations</h3><ul>'+r.limitations.map(text=>'<li>'+esc(text)+'</li>').join('')+'</ul><p class="sd-small">Execution: local maintained adapters. Live model calls: '+r.live_model_calls+'. Unsigned consistency digests do not authenticate approval.</p></article>';
    }
    function render(){if(!live())return;
      host.innerHTML='<div class="sc-workspace" aria-busy="'+s.busy+'"><p class="sc-error sd-error" role="alert" '+(!s.error?'hidden':'')+'>'+esc(s.error)+'</p>'+form()+'<section class="sc-history"><div class="sd-section-heading"><h2>Saved studies</h2>'+button('refresh','Refresh',s.busy)+'</div><p class="sd-small">Latest 20 studies up to selected R'+ctx.revision+'. Opening records runs no calculations.</p><div class="sc-history-items">'+(s.list?s.list.studies.map(item=>'<button type="button" class="sd-button sc-history-item" data-sc-open="'+esc(item.study_id)+'" aria-pressed="'+(s.detail?.receipt.study_id===item.study_id)+'"><strong>'+esc(item.name)+'</strong><span>R'+item.revision+' · '+item.case_count+' cases · '+esc(item.mode)+' · '+(item.freshness.historical?'Historical':'Matches baseline')+'</span></button>').join('')||'<p>No studies saved for this project context.</p>':'<p>Loading saved studies…</p>')+'</div></section><div id="sc-result">'+report()+'</div></div>';
      if(s.busy)host.querySelectorAll('button,input,select,textarea').forEach(el=>el.disabled=true);
    }
    async function loadDetail(id){const serial=++s.request;s.busy=true;s.error='';remember();render();
      try{const detail=await ctx.api('/api/scenarios/'+encodeURIComponent(id)+'?revision='+ctx.revision);if(!live()||serial!==s.request)return;s.detail=detail;s.form.selected=id;}
      catch(error){if(live()&&serial===s.request)s.error=error.message;}
      finally{if(live()&&serial===s.request){s.busy=false;render();}}
    }
    async function refresh(){const serial=++s.request;s.busy=true;remember();render();
      try{const [list,status]=await Promise.all([ctx.api('/api/scenarios'+query),ctx.api('/api/status')]);if(!live()||serial!==s.request)return;s.list=list;s.status=status;s.error='';
        if(s.form.selected){const detail=await ctx.api('/api/scenarios/'+encodeURIComponent(s.form.selected)+'?revision='+ctx.revision);if(!live()||serial!==s.request)return;s.detail=detail;}
      }catch(error){if(live()&&serial===s.request)s.error=error.message;}
      finally{if(live()&&serial===s.request){s.busy=false;render();}}
    }
    async function run(){if(!canRun())return;let spec;try{spec=specification();}catch(error){s.error=error.message;render();return;}
      const serial=++s.request;s.busy=true;s.error='';render();
      try{const detail=await ctx.api('/api/scenarios',{project_id:ctx.projectId,revision:ctx.revision,baseline_run_id:ctx.currentRunId,spec});if(!live()||serial!==s.request)return;s.detail=detail;s.form.selected=detail.receipt.study_id;
        try{const list=await ctx.api('/api/scenarios'+query);if(live()&&serial===s.request)s.list=list;}catch(error){if(live())s.error='Study saved. History refresh failed: '+error.message;}
      }catch(error){if(live()&&serial===s.request)s.error=error.message;}
      finally{if(live()&&serial===s.request){s.busy=false;render();}}
    }
    host.oninput=()=>remember();
    host.onchange=event=>{remember();if(event.target.matches('[data-sc-requirement]')){s.form.requirement=event.target.value;render();}else if(event.target.matches('select'))render();};
    host.onclick=event=>{const el=event.target.closest('button');if(!el||!host.contains(el)||s.busy)return;
      if(el.dataset.scOpen){void loadDetail(el.dataset.scOpen);return;}
      const action=el.dataset.sc;if(!action)return;remember();
      if(action==='run'){void run();return;}if(action==='refresh'){void refresh();return;}if(action==='baseline'){ctx.onRun();return;}if(action==='reload'){window.location.reload();return;}
      if(action==='export'&&s.detail){const a=document.createElement('a');a.href='/api/scenario-export?id='+encodeURIComponent(s.detail.receipt.study_id)+'&revision='+ctx.revision;a.download='6d-scenario-'+s.detail.receipt.study_id+'.json';a.click();return;}
      if(action==='print'&&s.detail){const details=[...host.querySelectorAll('.sc-report details')],opened=details.map(d=>d.open);details.forEach(d=>d.open=true);window.print();details.forEach((d,i)=>d.open=opened[i]);return;}
      const [name,i,j]=action.split(':');if(name==='add-case'&&s.form.cases.length<16)s.form.cases.push({name:'',changes:[{input:'',value:''}]});
      if(name==='remove-case'&&s.form.cases.length>1)s.form.cases.splice(Number(i),1);
      if(name==='add-change'&&s.form.cases[i].changes.length<8)s.form.cases[i].changes.push({input:'',value:''});
      if(name==='remove-change'&&s.form.cases[i].changes.length>1)s.form.cases[i].changes.splice(Number(j),1);
      render();
    };
    render();void refresh();
  }
  window.SixDScenarios={mount,unmount};
})();
