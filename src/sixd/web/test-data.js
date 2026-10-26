/* Supplied scalar measurements are recorded evidence, never inferred test validation. */
(() => {
  'use strict';
  let mounted=null;
  const sessions=new Map();
  const mappingFields=['measurement_id','requirement_id','value','unit','tolerance'];
  const fieldLabels={measurement_id:'Measurement ID',requirement_id:'Requirement ID',value:'Measured value',unit:'Unit',tolerance:'Absolute agreement tolerance (optional)'};
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=value=>value===null||value===undefined?'—':typeof value==='number'?(window.SixDUnits?.number(value)??String(value)):String(value);
  const measure=record=>record&&Number.isFinite(record.value)?(window.SixDUnits?.value(record.value,record.unit)??esc(num(record.value)+' '+record.unit)):'No numeric evidence';
  const labels={met:'Meets criterion',not_met:'Does not meet',not_assessed:'Not assessed',within_tolerance:'Within supplied tolerance',outside_tolerance:'Outside supplied tolerance'};
  const badge=status=>'<span class="td-badge td-'+esc(status)+'">'+esc(labels[status]||status)+'</span>';
  const option=(value,label,selected)=>'<option value="'+esc(value)+'" '+(value===selected?'selected':'')+'>'+esc(label)+'</option>';
  const button=(action,label,disabled=false)=>'<button type="button" class="sd-button" data-td="'+action+'" '+(disabled?'disabled':'')+'>'+label+'</button>';
  const blankMapping=()=>Object.fromEntries(mappingFields.map(key=>[key,'']));
  function unmount(){if(mounted){mounted.closed=true;mounted.host.oninput=null;mounted.host.onchange=null;mounted.host.onclick=null;mounted.host.replaceChildren();mounted=null;}}
  function mount(host,ctx){
    unmount();
    const key=ctx.projectId+':'+ctx.revision;
    if(!sessions.has(key)){
      // Memory-only form state: never persist supplied data in browser storage.
      if(sessions.size>=20)sessions.delete(sessions.keys().next().value);
      sessions.set(key,{name:'',source:'',data_kind:'',test_conditions:'',conditions_match:'',filename:'',csv_text:'',mapping:blankMapping(),preview:null,previewSignature:'',selected:'',selectedRow:''});
    }
    if(ctx.comparisonId){sessions.get(key).selected=ctx.comparisonId;sessions.get(key).selectedRow=String(ctx.rowNumber||'');}
    const s={host,ctx,form:sessions.get(key),closed:false,busy:false,error:'',list:null,detail:null,status:null,request:0};
    mounted=s;
    const live=()=>mounted===s&&!s.closed&&host.isConnected;
    const checkedDetail=(detail,id)=>{
      if(detail?.receipt?.project_id!==ctx.projectId||detail.receipt.comparison_id!==id||!Number.isInteger(detail.receipt.revision)||detail.receipt.revision>ctx.revision){s.detail=null;throw Error('This comparison does not belong to the selected project and revision.');}
      return detail;
    };
    const query='?project_id='+encodeURIComponent(ctx.projectId)+'&revision='+ctx.revision;
    function remember(){
      const f=s.form;
      // A textarea normalizes CRLF when HTML is parsed. Preserve the original
      // decoded file text unless an actual edit event changes the CSV field.
      for(const field of ['name','source','data_kind','test_conditions','conditions_match','filename']){
        const el=host.querySelector('[data-td-field="'+field+'"]');if(el)f[field]=el.value;
      }
      host.querySelectorAll('[data-td-map]').forEach(el=>f.mapping[el.dataset.tdMap]=el.value);
    }
    function signature(){const f=s.form;return JSON.stringify([f.filename,f.csv_text,mappingFields.map(key=>f.mapping[key]||'')]);}
    function previewCurrent(){return !!s.form.preview&&s.form.previewSignature===signature();}
    function baselineReason(){
      if(ctx.hasDraft)return 'Save or discard your draft before linking measurements to a saved baseline.';
      if(!ctx.currentRunId)return 'Run baseline checks for this saved revision first.';
      if(s.status?.restart_required)return '6D needs a backend restart before saving a comparison.';
      if(s.list&&s.list.baseline_run_id!==ctx.currentRunId)return 'The baseline changed since this project was opened. '+(typeof ctx.onReload==='function'?'Reload the saved project before comparing.':'Reselect this saved revision in the workspace before comparing; the CSV form remains in memory.');
      return '';
    }
    function ready(){const f=s.form;return !s.busy&&!baselineReason()&&s.status&&s.list&&previewCurrent()&&f.name.trim()&&f.source.trim()&&f.data_kind&&f.test_conditions.trim()&&f.conditions_match;}
    function syncActions(){
      const run=host.querySelector('[data-td="run"]');if(run)run.disabled=!ready();
      const preview=host.querySelector('[data-td="preview"]');if(preview)preview.disabled=s.busy||!s.form.filename.trim()||!s.form.csv_text.trim();
      const stale=host.querySelector('[data-td-preview-stale]');if(stale)stale.hidden=previewCurrent();
      const progress=host.querySelector('[data-td-readiness]');
      if(progress)progress.textContent=!previewCurrent()?'Preview the current CSV and mappings before saving.':!ready()&&!s.busy?'Complete the comparison name, source, data origin, test conditions and condition match. Row gaps remain explicitly unassessed.':'The current preview will be preserved with this comparison.';
    }
    function mapping(){
      const f=s.form,p=f.preview;
      if(!p)return '<p class="sd-small">Read the CSV headers first, then explicitly choose a column for each field. No measurements or mappings are assumed.</p>';
      return '<fieldset class="td-mappings"><legend>Column mappings</legend><div class="td-map-grid">'+mappingFields.map(field=>'<label class="sd-field">'+esc(fieldLabels[field])+'<select class="sd-input" data-td-map="'+field+'">'+option('','Unmapped',f.mapping[field])+p.columns.map(column=>option(column,column,f.mapping[field])).join('')+'</select></label>').join('')+'</div><p class="sd-small">Map each numeric value to its explicit unit. Tolerance is a nonnegative absolute difference in that same unit. Leave it unmapped or blank to keep prediction agreement unassessed.</p></fieldset>';
    }
    function previewTable(){
      const p=s.form.preview;if(!p)return '';
      const issues=p.rows.reduce((count,row)=>count+row.issues.length,0);
      return '<section class="td-preview"><div class="sd-section-heading"><h3>CSV preview</h3><span class="sd-chip">'+p.row_count+' rows · '+issues+' row issue(s)</span></div><div class="sd-notice" data-td-preview-stale '+(previewCurrent()?'hidden':'')+'>CSV text, filename or mappings have changed. This preview belongs to the earlier input; preview again before saving.</div><p class="sd-small">Normalized rows below show all supplied data rows, including gaps. Gaps do not become zero or a failed vehicle finding.</p><div class="td-table-wrap"><table class="sd-table"><thead><tr><th>CSV row</th><th>Measurement / requirement</th><th>Value and unit</th><th>Absolute tolerance</th><th>Input issues</th></tr></thead><tbody>'+p.rows.map(row=>'<tr><td>'+esc(row.row_number)+'</td><td>'+esc(row.measurement_id||'Missing ID')+'<br><small>'+esc(row.requirement_id||'Missing requirement')+'</small></td><td>'+esc(num(row.value)+' '+(row.unit||'(unit missing)'))+'</td><td>'+esc(num(row.tolerance))+'</td><td>'+rowIssues(row)+'</td></tr>').join('')+'</tbody></table></div><details><summary>Original cells · first 10 rows</summary>'+rawTable(p)+'</details><p class="td-identity">CSV SHA-256 '+esc(p.csv_sha256)+'</p></section>';
    }
    function rowIssues(row){return row.issues?.length?'<ul class="td-issues">'+row.issues.map(issue=>'<li>'+esc(issue.field)+': '+esc(issue.message)+'</li>').join('')+'</ul>':'No CSV parsing issues';}
    function rawTable(preview){return '<div class="td-table-wrap"><table class="sd-table"><thead><tr>'+preview.columns.map(column=>'<th>'+esc(column)+'</th>').join('')+'</tr></thead><tbody>'+preview.raw_preview.map(row=>'<tr>'+preview.columns.map(column=>'<td>'+esc(row[column]??'')+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';}
    function form(){
      const f=s.form,reason=baselineReason();
      return '<section class="td-builder"><div class="sd-section-heading"><div><span class="sd-label">Recorded data · saved R'+esc(ctx.revision)+'</span><h2>Compare tests with predictions</h2></div><span class="sd-chip">Local comparison · no AI calls</span></div><p>Import supplied scalar measurements and compare them with this exact saved design. Measurement compliance and prediction agreement are separate findings.</p>'+(reason?'<div class="sd-notice">'+esc(reason)+(!ctx.hasDraft&&!ctx.currentRunId?button('baseline','Run baseline checks'):s.list&&s.list.baseline_run_id!==ctx.currentRunId&&typeof ctx.onReload==='function'?button('reload','Reload saved project'):'')+'</div>':'')+'<div class="td-form-grid"><label class="sd-field">Comparison name<input class="sd-input" maxlength="120" data-td-field="name" value="'+esc(f.name)+'"></label><label class="sd-field">Data origin<select class="sd-input" data-td-field="data_kind">'+option('','Choose explicitly',f.data_kind)+option('measured','Supplied measurements · authenticity not verified',f.data_kind)+option('synthetic','Synthetic / constructed example data',f.data_kind)+'</select></label></div><label class="sd-field">Data source and provenance<textarea class="sd-input" rows="2" maxlength="1200" data-td-field="source">'+esc(f.source)+'</textarea><span class="sd-small">Name the supplied test record, instrument or constructed-data source. This declaration does not authenticate a test.</span></label><div class="td-form-grid"><label class="sd-field">Measurement definition and test conditions<textarea class="sd-input" rows="3" maxlength="2400" data-td-field="test_conditions">'+esc(f.test_conditions)+'</textarea><span class="sd-small">Describe the same observable and aggregation as the prediction: for example, steady equilibrium versus a transient temperature, or an orbital minimum versus one instantaneous radius. Include the model-bound input conditions.</span></label><label class="sd-field">Do the measurement definition and conditions match?<select class="sd-input" data-td-field="conditions_match">'+option('','Choose explicitly',f.conditions_match)+option('declared_match','I declare the measurement definition and conditions match this baseline',f.conditions_match)+option('different','Definition or conditions differ',f.conditions_match)+option('unknown','Match is unknown',f.conditions_match)+'</select><span class="sd-small">Your declaration is recorded, not independently verified. Different or unknown definitions or conditions leave prediction agreement unassessed.</span></label></div><fieldset class="td-intake"><legend>CSV data</legend><p class="sd-small">UTF-8 CSV · at most 1 MiB, 200 data rows and 32 columns. IDs, values, units and any tolerance must be supplied explicitly. Unit conversion and time-series alignment are not performed.</p><label class="sd-field">Choose a local CSV file<input class="sd-input" type="file" accept=".csv,text/csv" data-td-file></label><label class="sd-field">Source filename or pasted-data label<input class="sd-input" maxlength="180" data-td-field="filename" value="'+esc(f.filename)+'"></label><label class="sd-field">CSV text<textarea class="sd-input td-csv" rows="7" maxlength="1048576" spellcheck="false" data-td-field="csv_text">'+esc(f.csv_text)+'</textarea></label>'+mapping()+'<div class="sd-action-row">'+button('preview',s.busy?'Please wait…':f.preview?'Preview current CSV and mappings':'Read headers / preview CSV',s.busy||!f.filename.trim()||!f.csv_text.trim())+'</div><details><summary>Saved requirement IDs and units</summary><p class="sd-small">Use the exact requirement ID and unit. Unsupported baseline predictions remain unassessed.</p><div class="td-table-wrap"><table class="sd-table"><thead><tr><th>ID</th><th>Requirement</th><th>Metric</th><th>Criterion unit</th></tr></thead><tbody>'+ctx.project.requirements.map(row=>'<tr><td>'+esc(row.id)+'</td><td>'+esc(row.title)+'</td><td>'+esc(row.metric)+'</td><td>'+esc(ctx.project.inputs[row.limit_input]?.unit||'Missing limit')+'</td></tr>').join('')+'</tbody></table></div></details></fieldset>'+previewTable()+'<div class="sd-action-row">'+button('run',s.busy?'Please wait…':'Save test comparison',!ready())+'</div><p class="sd-small" data-td-readiness></p><p class="sd-small sd-muted">This comparison records supplied evidence. It does not change project findings, establish model validation, authenticate physical testing or authorize launch.</p></section>';
    }
    function resultCounts(rows){return ['met','not_met','not_assessed'].map(status=>rows.filter(row=>row.measurement_requirement.status===status).length+' '+({met:'measurement criteria met',not_met:'not met',not_assessed:'not assessed'}[status])).join(' · ');}
    function resultTable(receipt){
      return '<div class="td-table-wrap"><table class="sd-table td-results"><thead><tr><th>Measurement / requirement</th><th>Measured / predicted</th><th>Measurement meets requirement</th><th>Prediction agrees within tolerance</th></tr></thead><tbody>'+receipt.row_results.map(row=>{
        const source=receipt.preview.rows.find(item=>item.row_number===row.row_number),finding=row.measurement_requirement,agreement=row.prediction_agreement;
        return '<tr><td>'+esc(row.measurement_id||'CSV row '+row.row_number)+'<br><small>'+esc(row.requirement_id||'No requirement ID')+' · '+esc(row.title||'Unmapped requirement')+'</small><br><button type="button" class="sd-button td-no-print" data-td-row="'+esc(row.row_number)+'">Inspect row '+esc(row.row_number)+'</button></td><td>'+measure(finding.metric||{value:source?.value,unit:source?.unit||''})+'<br><small>Prediction: '+measure(agreement.prediction)+'</small></td><td>'+badge(finding.status)+'<br>'+esc(finding.reason)+'<br><small>'+(finding.limit?esc(finding.operator)+' '+measure(finding.limit):'No usable criterion')+'</small></td><td>'+badge(agreement.status)+'<br>'+esc(agreement.reason)+'<br><small>Absolute discrepancy: '+esc(num(agreement.absolute_difference))+'<br>Tolerance: '+measure(agreement.tolerance)+'</small></td></tr>';
      }).join('')+'</tbody></table></div>';
    }
    function plot(row,source){
      const finding=row.measurement_requirement,agreement=row.prediction_agreement;
      const measured=finding.metric||{value:source?.value,unit:source?.unit||''};
      if(!Number.isFinite(measured.value)||!measured.unit)return '<p>No finite, unit-labelled measurement is available for a plot.</p>';
      const prediction=agreement.prediction&&agreement.prediction.unit===measured.unit&&Number.isFinite(agreement.prediction.value)?agreement.prediction:null;
      const criterion=finding.limit&&finding.limit.unit===measured.unit&&Number.isFinite(finding.limit.value)?finding.limit:null;
      const tolerance=agreement.tolerance?.unit===measured.unit&&Number.isFinite(agreement.tolerance.value)?agreement.tolerance:null;
      const numbers=[measured.value];if(prediction)numbers.push(prediction.value);if(criterion)numbers.push(criterion.value);
      let bounds=null;
      if(prediction&&tolerance&&agreement.status!=='not_assessed'){const lo=prediction.value-tolerance.value,hi=prediction.value+tolerance.value;if(Number.isFinite(lo)&&Number.isFinite(hi)){bounds=[lo,hi];numbers.push(...bounds);}}
      const magnitude=Math.max(...numbers.map(Math.abs))||1,lo=Math.min(...numbers.map(value=>value/magnitude)),hi=Math.max(...numbers.map(value=>value/magnitude));
      const px=value=>hi===lo?390:95+590*(value/magnitude-lo)/(hi-lo);
      const tick=value=>{const [mantissa,exponent]=value.toPrecision(5).split('e');return (mantissa.includes('.')?mantissa.replace(/\.?0+$/,''):mantissa)+(exponent?'e'+exponent:'');};
      return '<svg class="td-chart" viewBox="0 0 780 240" role="img" aria-label="One scalar measurement, compatible saved prediction and its own criterion"><path d="M95 188H685" stroke="#a9b4c4"/>'+(bounds?'<rect x="'+px(bounds[0])+'" y="90" width="'+Math.max(1,px(bounds[1])-px(bounds[0]))+'" height="34" fill="#e5edf9"><title>'+esc('Supplied absolute tolerance around prediction: '+num(tolerance.value)+' '+measured.unit)+'</title></rect>':'')+'<circle cx="'+px(measured.value)+'" cy="60" r="6" fill="#3563cc"><title>'+esc('Measurement: '+num(measured.value)+' '+measured.unit)+'</title></circle><text x="95" y="34">Supplied measurement</text>'+(prediction?'<path d="M'+px(prediction.value)+' 99l7 7-7 7-7-7Z" fill="#576c7e"><title>'+esc('Saved prediction: '+num(prediction.value)+' '+prediction.unit)+'</title></path><text x="95" y="88">Saved prediction'+(bounds?' · supplied tolerance band':'')+'</text>':'<text x="95" y="107">No compatible saved prediction</text>')+(criterion?'<path d="M'+px(criterion.value)+' 145v20" stroke="#b87528" stroke-width="3"><title>'+esc('Criterion: '+finding.operator+' '+num(criterion.value)+' '+criterion.unit)+'</title></path><text x="95" y="143">Own requirement criterion ('+esc(finding.operator)+')</text>':'')+[Math.min(...numbers),Math.max(...numbers)].filter((value,index,array)=>array.indexOf(value)===index).map(value=>'<text x="'+px(value)+'" y="208" text-anchor="middle">'+esc(tick(value))+'</text>').join('')+'<text x="390" y="232" text-anchor="middle">'+esc(measured.unit)+' · this row only</text></svg><p class="sd-small">Exact values are below. '+(agreement.status==='not_assessed'?'Prediction agreement is unassessed: '+esc(agreement.reason)+'. Separately displayed values do not establish a valid test comparison. ':'')+'Any displayed tolerance band is supplied by the user; it is not a confidence interval or a validated operating range.</p>';
    }
    function inspect(receipt,row){
      const source=receipt.preview.rows.find(item=>item.row_number===row.row_number),finding=row.measurement_requirement,agreement=row.prediction_agreement;
      return '<section class="td-row-detail"><h3>Row '+esc(row.row_number)+' · '+esc(row.measurement_id||'Missing measurement ID')+'</h3><p>'+esc(row.title||row.requirement_id||'Requirement not identified')+'</p>'+plot(row,source)+'<div class="td-verdict-grid"><section><h4>Measurement meets requirement</h4>'+badge(finding.status)+'<p>'+esc(finding.reason)+'</p><p>Measurement: '+measure(finding.metric||{value:source?.value,unit:source?.unit||''})+'<br>Criterion: '+(finding.limit?esc(finding.operator)+' '+measure(finding.limit):'No usable criterion')+'</p></section><section><h4>Prediction agrees within tolerance</h4>'+badge(agreement.status)+'<p>'+esc(agreement.reason)+'</p><p>Saved prediction: '+measure(agreement.prediction)+'<br>Measured − predicted: '+esc(num(agreement.signed_difference))+'<br>Absolute discrepancy: '+esc(num(agreement.absolute_difference))+'<br>Supplied tolerance: '+measure(agreement.tolerance)+'</p></section></div><h4>Recorded row issues</h4>'+rowIssues(row)+'<p class="sd-small">Next check: '+esc(nextCheck(row))+'</p></section>';
    }
    function nextCheck(row){
      if(Array.isArray(row.next_steps)&&row.next_steps.length)return row.next_steps.join(' ');
      if(row.issues?.length)return 'Resolve the recorded ID, numeric, unit or tolerance issues against the original test record; then save a separate corrected comparison.';
      if(row.measurement_requirement.status==='not_met')return 'Confirm the measured value, test conditions and requirement criterion with the responsible engineer before investigating causes.';
      if(row.prediction_agreement.status==='outside_tolerance')return 'Check the test setup, baseline inputs, supplied tolerance and model assumptions before attributing the discrepancy to a model or hardware defect.';
      if(row.prediction_agreement.status==='not_assessed')return 'Resolve the stated evidence gap, including condition matching, compatible prediction and an explicit tolerance where needed.';
      return 'Review the original test record and baseline assumptions. Agreement on this scalar result does not validate other conditions, outputs or the whole model.';
    }
    function report(){
      if(!s.detail)return '<section class="td-empty"><h2>Bring measured evidence into the review</h2><p>Preview a supplied CSV or open a saved comparison. Each measurement keeps its own unit, criterion, tolerance and evidence gaps.</p></section>';
      const d=s.detail,r=d.receipt;
      if(!r.row_results.some(row=>String(row.row_number)===s.form.selectedRow))s.form.selectedRow=String(r.row_results[0]?.row_number||'');
      const selected=r.row_results.find(row=>String(row.row_number)===s.form.selectedRow);
      return '<article class="td-report"><div class="sd-section-heading"><div><span class="sd-label">Saved scalar test comparison · R'+esc(r.revision)+'</span><h2>'+esc(r.spec.name)+'</h2></div><span class="sd-chip">'+(d.freshness.historical?'Historical baseline or sources':'Matches selected baseline')+'</span></div><div class="sd-notice">'+(r.spec.data_kind==='synthetic'?'Synthetic / constructed data. These are not physical test results.':'Supplied measurements. Authenticity, calibration and physical test execution are not verified by 6D.')+' This comparison does not replace canonical design findings or establish model validation.'+(d.freshness.historical?' The selected revision, latest baseline run or installed sources differ from this recorded context.':'')+'</div><p><strong>Source:</strong> '+esc(r.spec.source)+'<br><strong>Measurement definition and test conditions:</strong> '+esc(r.spec.test_conditions)+'<br><strong>Condition match:</strong> '+esc({declared_match:'User declares measurement definition and conditions match; not independently verified',different:'Different conditions',unknown:'Match unknown'}[r.spec.conditions_match]||r.spec.conditions_match)+'</p><p class="td-identity">Project '+esc(r.project_id)+' · R'+esc(r.revision)+' · '+esc(r.created_at)+'<br>Comparison '+esc(r.comparison_id)+'<br>Baseline run '+esc(r.baseline.run_id)+'<br>Baseline review '+esc(r.baseline.review.digest)+'<br>Comparison digest '+esc(d.receipt_digest)+'<br>CSV '+esc(r.spec.filename)+' · SHA-256 '+esc(r.preview.csv_sha256)+'</p><div class="sd-action-row td-no-print">'+button('export','Export comparison JSON')+button('print','Print report / Save PDF')+'</div><p>'+esc(resultCounts(r.row_results))+'</p><h3>Two separate questions for every row</h3>'+resultTable(r)+(selected?'<div class="td-selected td-no-print">'+inspect(r,selected)+'</div>':'')+'<details class="td-disclosure td-all-rows"><summary>Every row: plots, evidence gaps and next checks</summary>'+r.row_results.map(row=>inspect(r,row)).join('')+'</details><details class="td-disclosure"><summary>Original CSV, explicit mappings and provenance</summary><h4>CSV as submitted · including any explicit edits</h4><pre>'+esc(r.spec.csv_text)+'</pre><h4>Mappings and source identities</h4><pre>'+esc(JSON.stringify({filename:r.spec.filename,mapping:r.spec.mapping,data_kind:r.spec.data_kind,test_conditions:r.spec.test_conditions,conditions_match:r.spec.conditions_match,sources:r.sources,baseline_run_digest:r.baseline.run_digest,baseline_review_digest:r.baseline.review.digest},null,2))+'</pre></details><details class="td-disclosure"><summary>Frozen baseline inputs, model bindings, assumptions and exclusions</summary>'+(Object.values(r.baseline.review.project.inputs).some(input=>Number.isInteger(input.value)&&!Number.isSafeInteger(input.value))?'<p class="sd-notice">This baseline includes large numeric values that may round in a browser JSON preview. Use the downloaded JSON for their original numeric encoding. Unsupported integer comparison operands remain unassessed.</p>':'')+'<ul>'+r.baseline.review.exclusions.map(item=>'<li>'+esc(item)+'</li>').join('')+'</ul><pre>'+esc(JSON.stringify({baseline_inputs:r.baseline.review.project.inputs,baseline_model_bindings:r.baseline.review.project.models,baseline_evidence:r.baseline.review.evidence},null,2))+'</pre></details><h3>Scope and limitations</h3><ul>'+r.limitations.map(item=>'<li>'+esc(item)+'</li>').join('')+'</ul><p class="sd-small">Execution: recorded scalar comparison. Live model calls: '+esc(r.live_model_calls)+'. Unsigned consistency digests do not authenticate test data or approval.</p></article>';
    }
    function render(){if(!live())return;
      host.innerHTML='<div class="td-workspace" aria-busy="'+s.busy+'"><p class="td-error sd-error" role="alert" '+(!s.error?'hidden':'')+'>'+esc(s.error)+'</p>'+form()+'<section class="td-history"><div class="sd-section-heading"><h2>Saved test comparisons</h2>'+button('refresh','Refresh history',s.busy)+'</div><p class="sd-small">Latest 20 comparisons up to selected R'+esc(ctx.revision)+'. Opening records performs no calculations or model calls.</p><div class="td-history-items">'+(s.list?s.list.comparisons.map(item=>'<button type="button" class="sd-button td-history-item" data-td-open="'+esc(item.comparison_id)+'" aria-pressed="'+(s.detail?.receipt.comparison_id===item.comparison_id)+'"><strong>'+esc(item.name)+'</strong><span>R'+esc(item.revision)+' · '+esc(item.row_count)+' rows · '+esc(item.data_kind)+' · '+(item.freshness.historical?'Historical':'Matches baseline')+'</span></button>').join('')||'<p>No test comparisons saved for this project context.</p>':'<p>Loading saved comparisons…</p>')+'</div></section><div id="td-result">'+report()+'</div></div>';
      if(s.busy)host.querySelectorAll('button,input,select,textarea').forEach(el=>el.disabled=true);
      syncActions();
    }
    async function preview(){remember();const serial=++s.request;s.busy=true;s.error='';render();
      const f=s.form,payload={filename:f.filename,csv_text:f.csv_text,mapping:{...f.mapping}},stamp=signature();
      try{const result=await ctx.api('/api/test-data/preview',payload);if(!live()||serial!==s.request)return;f.preview=result;f.mapping={...result.mapping};f.previewSignature=stamp;}
      catch(error){if(live()&&serial===s.request)s.error=error.message;}
      finally{if(live()&&serial===s.request){s.busy=false;render();}}
    }
    async function readFile(file){
      if(!file)return;remember();const serial=++s.request;s.busy=true;s.error='';render();
      try{
        if(file.size>1048576)throw Error('Choose a UTF-8 CSV no larger than 1 MiB.');
        const text=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(await file.arrayBuffer());
        if(!live()||serial!==s.request)return;
        s.form.filename=file.name;s.form.csv_text=text;s.form.mapping=blankMapping();s.form.preview=null;s.form.previewSignature='';
      }catch(error){if(live()&&serial===s.request)s.error=error instanceof TypeError?'The file is not valid UTF-8. Export a UTF-8 CSV and try again.':error.message;}
      finally{if(live()&&serial===s.request){s.busy=false;render();}}
    }
    async function refresh(){remember();const serial=++s.request;s.busy=true;render();
      try{
        const [list,status]=await Promise.all([ctx.api('/api/test-comparisons'+query),ctx.api('/api/status')]);
        if(!live()||serial!==s.request)return;s.list=list;s.status=status;s.error='';
        if(s.form.selected){const detail=await ctx.api('/api/test-comparisons/'+encodeURIComponent(s.form.selected)+'?revision='+ctx.revision);if(!live()||serial!==s.request)return;s.detail=checkedDetail(detail,s.form.selected);}
      }catch(error){if(live()&&serial===s.request)s.error=error.message;}
      finally{if(live()&&serial===s.request){s.busy=false;render();}}
    }
    async function loadDetail(id){remember();const serial=++s.request;s.busy=true;s.error='';render();
      try{const detail=await ctx.api('/api/test-comparisons/'+encodeURIComponent(id)+'?revision='+ctx.revision);if(!live()||serial!==s.request)return;s.detail=checkedDetail(detail,id);s.form.selected=detail.receipt.comparison_id;}
      catch(error){if(live()&&serial===s.request)s.error=error.message;}
      finally{if(live()&&serial===s.request){s.busy=false;render();}}
    }
    async function save(){remember();if(!ready())return;
      const serial=++s.request;s.busy=true;s.error='';render();const f=s.form;
      const spec={schema:'sixd.test-comparison-spec.v1',name:f.name.trim(),source:f.source.trim(),data_kind:f.data_kind,test_conditions:f.test_conditions.trim(),conditions_match:f.conditions_match,filename:f.filename,csv_text:f.csv_text,mapping:{...f.mapping}};
      try{
        const detail=await ctx.api('/api/test-comparisons',{project_id:ctx.projectId,revision:ctx.revision,baseline_run_id:ctx.currentRunId,spec});
        if(!live()||serial!==s.request)return;s.detail=detail;s.form.selected=detail.receipt.comparison_id;ctx.onSaved?.();
        try{const list=await ctx.api('/api/test-comparisons'+query);if(live()&&serial===s.request)s.list=list;}
        catch(error){if(live()&&serial===s.request)s.error='Comparison saved. History refresh failed: '+error.message;}
      }catch(error){if(live()&&serial===s.request)s.error=error.message;}
      finally{if(live()&&serial===s.request){s.busy=false;render();}}
    }
    host.oninput=event=>{if(event.target.matches('[data-td-field="csv_text"]'))s.form.csv_text=event.target.value;remember();syncActions();};
    host.onchange=event=>{
      if(event.target.matches('[data-td-file]')){void readFile(event.target.files[0]);return;}
      remember();syncActions();
    };
    host.onclick=event=>{
      const el=event.target.closest('button');if(!el||!host.contains(el)||s.busy)return;
      if(el.dataset.tdOpen){void loadDetail(el.dataset.tdOpen);return;}
      if(el.dataset.tdRow){remember();s.form.selectedRow=el.dataset.tdRow;render();host.querySelector('.td-selected')?.scrollIntoView({block:'nearest',behavior:'smooth'});return;}
      const action=el.dataset.td;if(!action)return;remember();
      if(action==='preview'){void preview();return;}if(action==='run'){void save();return;}if(action==='refresh'){void refresh();return;}
      if(action==='baseline'){ctx.onRun?.();return;}if(action==='reload'){ctx.onReload?.();return;}
      if(action==='export'&&s.detail){const anchor=document.createElement('a');anchor.href='/api/test-comparison-export?id='+encodeURIComponent(s.detail.receipt.comparison_id)+'&revision='+ctx.revision;anchor.download='6d-test-comparison-'+s.detail.receipt.comparison_id+'.json';anchor.click();return;}
      if(action==='print'&&s.detail){const details=[...host.querySelectorAll('.td-report details')],opened=details.map(item=>item.open);details.forEach(item=>item.open=true);window.print();details.forEach((item,index)=>item.open=opened[index]);}
    };
    render();void refresh();
  }
  window.SixDTestData={mount,unmount};
})();
