/* Explicit sequential power/energy budgets. Browser displays saved arithmetic only. */
(() => {
  'use strict';
  let mounted=null;
  const sessions=new Map();
  const arr=value=>Array.isArray(value)?value:[];
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const clone=value=>JSON.parse(JSON.stringify(value));
  const own=(value,key)=>Object.prototype.hasOwnProperty.call(value||{},key);
  const safe=(value,max=32)=>typeof value==='string'&&new RegExp('^[A-Za-z][A-Za-z0-9_-]{0,'+(max-1)+'}$').test(value)&&!['__proto__','prototype','constructor'].includes(value);
  const finite=value=>typeof value==='number'&&Number.isFinite(value)&&(!Number.isInteger(value)||Number.isSafeInteger(value));
  const valueText=value=>finite(value)?String(value):'Exact value unavailable in browser';
  const sourceJson=value=>JSON.stringify(value,(_key,item)=>typeof item==='number'&&!finite(item)?'Exact numeric value unavailable in browser; inspect original evidence JSON':item,2);
  const measure=(value,unit)=>finite(value)?window.SixDUnits.value(value,unit):esc(valueText(value)+' '+window.SixDUnits.format(unit));
  const option=(value,label,selected)=>'<option value="'+esc(value)+'" '+(value===selected?'selected':'')+'>'+esc(label)+'</option>';
  const button=(action,label,disabled=false)=>'<button type="button" class="sd-button" data-pb="'+esc(action)+'" '+(disabled?'disabled':'')+'>'+esc(label)+'</button>';
  const textList=values=>'<ul>'+arr(values).map(value=>'<li>'+esc(typeof value==='string'?value:value.message||value.code||'Unspecified issue')+'</li>').join('')+'</ul>';
  const globals=[['usable_battery_energy','Usable battery energy','J'],['max_battery_power','Maximum battery output power','W'],['bus_power_limit','Bus power capacity','W']];
  const definitions={usable_battery_energy:'Bus-delivered usable energy, already adjusted for your reserve and loss assumptions. No charging credit is applied.',max_battery_power:'Maximum bus-delivered battery power available throughout the declared sequence.',bus_power_limit:'Maximum total equipment demand the electrical bus can carry in any declared mode.'};
  const metricLabels={minimum_power_margin:'Minimum combined power margin',minimum_bus_power_margin:'Minimum bus power margin',minimum_battery_power_margin:'Minimum battery power margin',battery_energy_margin:'Energy budget margin',total_duration:'Sequence duration',total_load_energy:'Total equipment energy',total_generated_energy:'Total declared generated energy',battery_energy_required:'Total battery energy required',peak_load_power:'Maximum equipment power',max_battery_power_required:'Maximum required battery power',minimum_generation_margin:'Minimum generation-only margin',surplus_generation_energy:'Uncredited surplus generation energy'};
  function metricTable(metrics){return '<div class="pb-table-wrap"><table class="sd-table"><thead><tr><th>Saved metric</th><th>Value</th></tr></thead><tbody>'+Object.entries(metrics||{}).map(([name,record])=>'<tr><td>'+esc(metricLabels[name]||name.replace(/_/g,' '))+'</td><td>'+measure(record?.value,record?.unit||'')+'</td></tr>').join('')+'</tbody></table></div>';}
  function plot(modes,series,unit,title){
    const rows=modes.map((mode,index)=>({mode,index,values:series.map(item=>mode[item.key])}));
    if(!rows.length||rows.some(row=>row.values.some(value=>!finite(value))))return '<p class="pb-note">The '+esc(title.toLowerCase())+' chart is unavailable because a saved number cannot be displayed without loss of precision. Inspect the exported source JSON.</p>';
    const values=[0,...rows.flatMap(row=>row.values)],mag=Math.max(...values.map(Math.abs))||1,lo=Math.min(...values.map(value=>value/mag)),hi=Math.max(...values.map(value=>value/mag));
    const y=value=>hi===lo?125:220-170*((value/mag-lo)/(hi-lo));
    const x=index=>rows.length===1?390:68+650*index/(rows.length-1);
    const tick=value=>window.SixDUnits.number(value);
    return '<figure class="pb-figure"><figcaption>'+esc(title)+' · '+esc(unit)+'</figcaption><svg class="pb-chart" viewBox="0 0 790 285" role="img" aria-label="'+esc(title+' in '+unit+'; discrete saved mode results, no interpolated predictions')+'"><path d="M68 38V220H735" fill="none" stroke="#c3cad6"/><path d="M68 '+y(0)+'H735" stroke="#bac5d7" stroke-dasharray="4 4"/>'+[Math.min(...values),Math.max(...values)].filter((value,index,all)=>all.indexOf(value)===index).map(value=>'<text x="60" y="'+(y(value)+4)+'" text-anchor="end">'+esc(tick(value))+'</text>').join('')+rows.map(row=>'<g>'+series.map((item,index)=>'<circle cx="'+(x(row.index)+(index-(series.length-1)/2)*8)+'" cy="'+y(row.values[index])+'" r="4.5" fill="'+item.color+'"><title>'+esc(row.mode.id+' / '+item.label+': '+String(row.values[index])+' '+unit)+'</title></circle>').join('')+'<text x="'+x(row.index)+'" y="245" text-anchor="middle">M'+(row.index+1)+'</text></g>').join('')+'<text x="395" y="276" text-anchor="middle">Declared mode order · values after each mode where applicable</text></svg><div class="pb-legend">'+series.map(item=>'<span><i style="background:'+item.color+'"></i>'+esc(item.label)+'</span>').join('')+'</div><p class="pb-note">M1, M2, … follow the mode table. Points show recorded values only; spacing does not represent duration.</p></figure>';
  }
  function report(result,options={}){
    const heading='<div class="pb-heading"><div><span class="pb-eyebrow">Saved electrical budget</span><h3>Power & energy evidence</h3></div><span class="sd-chip">'+esc(options.modelId||result?.model_id||'Power budget')+'</span></div>';
    if(options.hasDraft)return '<section class="pb-evidence">'+heading+'<p class="sd-notice">Draft configuration. Save the revision and run checks to calculate its power and energy budgets. Earlier results are not draft predictions.</p></section>';
    if(!result)return '<section class="pb-evidence">'+heading+'<p>No current saved calculation is available for this model. Run checks for the saved revision.</p></section>';
    const p=result.power_budget;
    if(result.status!=='completed'||p?.schema!=='sixd.power-energy-budget.v1'||!Array.isArray(p.modes))return '<section class="pb-evidence">'+heading+'<p>Power and energy are not assessed for this saved result.</p>'+textList(result.issues)+'<p class="pb-note">Missing inputs or a calculation limitation are not a passing budget.</p></section>';
    const modes=p.modes;
    return '<section class="pb-evidence" data-power-evidence="'+esc(options.modelId||result.model_id||'')+'">'+heading+'<p>Equipment operates simultaneously and continuously within each explicit sequential mode. Constant generation first serves that mode’s demand; surplus is not stored or credited to later modes.</p><p class="pb-note">These are supplied-value budgets, not electrical transients, battery state of charge, hardware qualification or a complete spacecraft power simulation.</p>'+
      '<h4>Power capacity and energy sufficiency</h4><p class="pb-note">Values use compact display precision. Exact saved metrics and modes are available below.</p>'+metricTable(result.metrics)+'<p class="pb-note">Power margins use W. Energy margins use J. The combined power margin checks bus capacity and generation plus battery capability; the battery margin separately checks only the generation shortfall. A negative generation-only margin may be covered by the battery. Negative capacity or energy margins are budget shortfalls. Requirement verdicts use your separately declared criteria.</p>'+
      '<div class="pb-charts">'+plot(modes,[{key:'bus_power_margin_w',label:'Bus power margin',color:'#4264b5'},{key:'battery_power_margin_w',label:'Battery power margin',color:'#b16d35'},{key:'power_margin_w',label:'Limiting power margin',color:'#8059ac'}],'W','Power margins by mode')+plot(modes,[{key:'remaining_energy_budget_j',label:'Remaining usable energy budget',color:'#3e856e'}],'J','Remaining energy budget')+'</div>'+
      '<h4>Saved mode sequence</h4><div class="pb-table-wrap"><table class="sd-table pb-modes"><thead><tr><th>Mode / interval</th><th>Equipment demand</th><th>Declared generation</th><th>Required battery power</th><th>Bus / battery / limiting power margins</th><th>Required battery energy</th><th>Cumulative battery energy</th><th>Remaining energy budget</th></tr></thead><tbody>'+modes.map((mode,index)=>'<tr data-power-mode="'+esc(mode.id)+'"><td>M'+(index+1)+' · '+esc(mode.id)+'<br><small>'+measure(mode.start_s,'s')+' → '+measure(mode.end_s,'s')+'<br>Duration '+measure(mode.duration_s,'s')+'</small></td><td>'+measure(mode.load_power_w,'W')+'</td><td>'+measure(mode.generation_power_w,'W')+'</td><td>'+measure(mode.battery_power_required_w,'W')+'</td><td>'+measure(mode.bus_power_margin_w,'W')+'<br>'+measure(mode.battery_power_margin_w,'W')+'<br>'+measure(mode.power_margin_w,'W')+'</td><td>'+measure(mode.battery_energy_required_j,'J')+'</td><td>'+measure(mode.cumulative_battery_energy_required_j,'J')+'</td><td>'+measure(mode.remaining_energy_budget_j,'J')+'</td></tr>').join('')+'</tbody></table></div>'+
      '<details class="pb-disclosure"><summary>Equipment, generated energy and uncredited surplus by mode</summary>'+modes.map(mode=>'<section class="pb-equipment"><h4>'+esc(mode.id)+'</h4><div class="pb-table-wrap"><table class="sd-table"><thead><tr><th>Equipment</th><th>Each unit</th><th>Count</th><th>Saved simultaneous demand</th></tr></thead><tbody>'+arr(mode.loads).map(load=>'<tr><td>'+esc(load.id)+'</td><td>'+measure(load.power_w,'W')+'</td><td>'+esc(valueText(load.count))+'</td><td>'+measure(load.load_power_w,'W')+'</td></tr>').join('')+'</tbody></table></div><p class="pb-note">Equipment energy '+measure(mode.load_energy_j,'J')+' · Declared generation energy '+measure(mode.generated_energy_j,'J')+' · Uncredited surplus '+measure(mode.surplus_energy_j,'J')+'.</p></section>').join('')+'</details>'+
      '<details class="pb-disclosure"><summary>Budget assumptions, exclusions and saved provenance</summary><h4>Exact saved metrics and mode sequence</h4><pre data-preserve-notation>'+esc(sourceJson({metrics:result.metrics,power_budget:p}))+'</pre><h4>Declared limits</h4><dl>'+[['Usable battery energy','usable_battery_energy_j','J'],['Maximum battery power','max_battery_power_w','W'],['Bus capacity','bus_power_limit_w','W']].map(([label,key,unit])=>'<dt>'+esc(label)+'</dt><dd>'+measure(p.limits?.[key],unit)+'</dd>').join('')+'</dl><h4>Assumptions</h4>'+textList(p.assumptions||result.assumptions)+'<h4>Not assessed</h4>'+textList(p.not_assessed||result.not_assessed)+'<dl>'+[['Project',options.projectId],['Revision',options.revision===undefined?undefined:'R'+options.revision],['Saved run',options.runId||options.currentRunId],['Review digest',options.reviewDigest],['Model',options.modelId||result.model_id],['Adapter version',result.model_version],['Evidence fingerprint',result.evidence_fingerprint]].filter(([,value])=>value!==undefined&&value!==null).map(([label,value])=>'<dt>'+esc(label)+'</dt><dd>'+esc(value)+'</dd>').join('')+'</dl><pre>'+esc(sourceJson({inputs:result.inputs,verification_sources:result.verification_sources,execution_origin:options.origin||null}))+'</pre><p class="pb-note">The displayed numbers are saved adapter results. Unsigned local identities are not proof of hardware performance or authenticated approval.</p></details></section>';
  }
  function unmount(){if(mounted){mounted.closed=true;mounted.host.oninput=null;mounted.host.onchange=null;mounted.host.onclick=null;mounted.host.onsubmit=null;mounted.host.replaceChildren();mounted=null;}}
  function mount(host,ctx){
    unmount();const key=ctx.projectId+':'+ctx.revision,cached=sessions.get(key);
    const restore=ctx.hasDraft&&cached&&(!cached.oldId?!arr(ctx.project.models).some(model=>model.id===cached.form.id):JSON.stringify(arr(ctx.project.models).find(model=>model.id===cached.oldId))===cached.baseDefinition);
    const state={host,ctx,key,closed:false,editor:restore?clone(cached):null,error:'',busy:false};mounted=state;
    const live=()=>mounted===state&&!state.closed&&host.isConnected;
    const editable=()=>!!ctx.hasDraft&&ctx.isLatest!==false;
    const models=()=>arr(ctx.project.models).filter(model=>model.type==='power_energy_budget');
    const inputs=()=>ctx.project.inputs||{};
    const field=(label,name,value='',attributes='')=>'<label class="sd-field">'+esc(label)+'<input class="sd-input" name="'+esc(name)+'" value="'+esc(value)+'" '+attributes+'></label>';
    function binding(label,name,selected,unit){
      const records=Object.entries(inputs()).filter(([,record])=>record.unit===unit),missing=selected&&!records.some(([id])=>id===selected);
      return '<label class="sd-field">'+esc(label+' · '+unit)+'<select class="sd-input" name="'+esc(name)+'" required>'+option('','Choose an existing '+unit+' input',selected)+records.map(([id,record])=>option(id,id+' · '+valueText(record.value)+' '+unit,selected)).join('')+(missing?option(selected,selected+' · missing input or wrong unit',selected):'')+'</select></label>';
    }
    function parse(model){
      const result={id:model?.id||'',description:model?.description||'',bindings:{},modes:[],unparsed:[]};
      const rows=new Map();
      for(const [role,id]of Object.entries(model?.inputs||{})){
        if(globals.some(([name])=>name===role)){result.bindings[role]=id;continue;}
        const match=/^mode\.([1-9]\d*)\.([A-Za-z][A-Za-z0-9_-]{0,31})\.(duration|generation|load\.([A-Za-z][A-Za-z0-9_-]{0,31})\.(power|count))$/.exec(role);
        if(!match){result.unparsed.push(role);continue;}
        const index=Number(match[1]);if(index>16){result.unparsed.push(role);continue;}
        if(rows.has(index)&&rows.get(index).id!==match[2]){result.unparsed.push(role);continue;}
        if(!rows.has(index))rows.set(index,{id:match[2],duration:'',generation:'',loads:[],index});
        const mode=rows.get(index);
        if(match[3]==='duration'||match[3]==='generation')mode[match[3]]=id;
        else{let load=mode.loads.find(load=>load.id===match[4]);if(!load){load={id:match[4],power:'',count:''};mode.loads.push(load);}load[match[5]]=id;}
      }
      result.modes=[...rows.values()].sort((a,b)=>a.index-b.index);
      if(result.modes.some((mode,index)=>mode.index!==index+1))result.unparsed.push('Non-contiguous mode ordering');
      if(!model)result.modes=[{id:'',duration:'',generation:'',loads:[{id:'',power:'',count:''}]}];
      return result;
    }
    function editor(){
      const e=state.editor;if(!e)return '';
      return '<section class="pb-editor pb-no-print"><h3>'+(e.oldId?'Edit':'Add')+' power & energy budget</h3>'+ (e.form.unparsed.length?'<p class="sd-notice">This imported model has unsupported or non-contiguous bindings: '+esc(e.form.unparsed.join(', '))+'. Guided editing is disabled to preserve those definitions. Repair them in the project JSON or use a new model.</p>':'')+'<form data-pb-form><div class="pb-form-grid">'+field('Stable model ID','model-id',e.form.id,'required maxlength="80" '+(e.oldId?'readonly':''))+'</div><label class="sd-field">Model context and assumptions<textarea class="sd-input" name="description" rows="3" maxlength="4096">'+esc(e.form.description)+'</textarea></label><h4>Available capacity</h4><div class="pb-form-grid">'+globals.map(([role,label,unit])=>'<div>'+binding(label,'global:'+role,e.form.bindings[role]||'',unit)+'<p class="pb-note">'+esc(definitions[role])+'</p></div>').join('')+'</div><h4>Sequential operating modes</h4><p class="pb-note">List modes in execution order. Every equipment row operates for the full duration of its mode. Repeated equipment across modes must be declared in each mode. No recharge, duty cycle or illumination is inferred.</p>'+e.form.modes.map((mode,index)=>'<fieldset class="pb-mode"><legend>Mode '+(index+1)+'</legend><div class="pb-form-grid">'+field('Mode ID','mode:'+index+':id',mode.id,'required maxlength="32"')+binding('Duration','mode:'+index+':duration',mode.duration,'s')+binding('Constant generation','mode:'+index+':generation',mode.generation,'W')+'</div><div class="pb-loads">'+mode.loads.map((load,j)=>'<fieldset class="pb-load"><legend>Simultaneous equipment '+(j+1)+'</legend><div class="pb-form-grid">'+field('Equipment ID in this mode','load:'+index+':'+j+':id',load.id,'required maxlength="32"')+binding('Power per equipment unit','load:'+index+':'+j+':power',load.power,'W')+binding('Count · whole number, including explicit zero','load:'+index+':'+j+':count',load.count,'1')+'</div>'+button('remove-load:'+index+':'+j,'Remove equipment row',mode.loads.length===1)+'</fieldset>').join('')+'</div><div class="pb-actions">'+button('add-load:'+index,'Add simultaneous equipment',e.form.modes.reduce((n,m)=>n+m.loads.length,0)>=128)+button('up:'+index,'Move mode earlier',index===0)+button('down:'+index,'Move mode later',index===e.form.modes.length-1)+button('remove-mode:'+index,'Remove mode',e.form.modes.length===1)+'</div></fieldset>').join('')+'<div class="pb-actions">'+button('add-mode','Add sequential mode',e.form.modes.length>=16)+'</div><p class="pb-note">A blank binding is not zero. If the exact input or limit is missing, author its value, unit and source in the shared project first. This form adds model bindings; requirements are separate explicit criteria.</p><div class="pb-actions">'+button('inputs','Author inputs and limits')+'<button type="submit" class="sd-button sd-primary" '+(!editable()||e.form.unparsed.length||state.busy?'disabled':'')+'>Apply model to shared draft</button>'+button('cancel','Cancel')+'</div></form></section>';
    }
    function resultFor(id){return Array.isArray(ctx.modelResults)?ctx.modelResults.find(result=>result.model_id===id):ctx.modelResults?.[id];}
    function modelCard(model){
      const rows=arr(ctx.project.requirements).filter(req=>req.model_id===model.id),owners=arr(ctx.project.systems).filter(system=>arr(system.model_ids).includes(model.id));
      return '<section class="pb-model" data-power-model="'+esc(model.id)+'"><div class="pb-heading"><div><h3>'+esc(model.id)+'</h3><p>'+esc(model.description||'No model context supplied.')+'</p></div><span class="sd-chip">'+rows.length+' declared criteria</span></div><p class="pb-note">System ownership: '+esc(owners.map(system=>system.title||system.id).join(', ')||'Unassigned')+'. '+(rows.length?'Each requirement has its own metric, limit and finding.':'No criteria have been declared. Calculated margins alone do not constitute a requirement review.')+'</p><div class="pb-actions pb-no-print">'+button('edit:'+model.id,'Edit budget',!editable())+button('remove:'+model.id,'Remove model',!editable())+button('requirements','Author requirements')+button('select:'+model.id,'Inspect in workspace')+'</div>'+report(!ctx.hasDraft&&ctx.currentRunId?resultFor(model.id):null,{projectId:ctx.projectId,revision:ctx.revision,modelId:model.id,runId:ctx.currentRunId,reviewDigest:ctx.reviewDigest,hasDraft:ctx.hasDraft,origin:ctx.modelOrigins?.[model.id]})+'</section>';
    }
    function render(){if(!live())return;host.innerHTML='<article class="pb-workspace" aria-busy="'+state.busy+'"><header class="pb-page-heading"><div><span class="pb-eyebrow">Electrical budgets · R'+esc(ctx.revision)+'</span><h2>Power & energy</h2><p>Check simultaneous power demand and energy required across a declared operating sequence.</p></div><span class="sd-chip">'+(ctx.hasDraft?'Shared draft':'Saved configuration')+'</span></header><div class="pb-actions pb-no-print">'+(ctx.hasDraft?button('save','Save shared revision',ctx.isLatest===false):button('draft','Edit in shared draft',ctx.isLatest===false))+button('new','Add power budget',!editable())+button('run','Run saved checks',!!ctx.hasDraft)+button('reference','Open constructed reference')+'</div>'+(ctx.isLatest===false?'<p class="sd-notice">Historical revisions are read-only. Select the latest revision to edit its model definitions.</p>':'')+(state.error?'<div class="pb-error" role="alert">'+esc(state.error)+'</div>':'')+'<section class="pb-intro"><h3>Declare a budget, then review its evidence</h3><p>Supply usable battery energy, maximum battery output power, bus capacity, and named operating modes. Bind each mode’s duration, generation, equipment power and equipment count to explicitly sourced inputs.</p><p class="pb-note">This bounded calculation excludes recharge credit, battery degradation, electrical transients, solar geometry and environmental qualification. Watts and joules answer different questions and remain separate.</p><div class="pb-actions pb-no-print">'+button('inputs','Author inputs and limits')+button('requirements','Author requirements')+'</div></section>'+editor()+(models().map(modelCard).join('')||'<section class="pb-empty"><h3>No power budget has been defined</h3><p>Start a shared draft and add your explicit operating modes, or inspect the constructed reference. Reference values demonstrate arithmetic; they are not mission requirements.</p></section>')+'</article>';if(state.busy)host.querySelectorAll('button,input,select,textarea').forEach(el=>el.disabled=true);}
    function remember(){
      const e=state.editor;if(!e)return;
      host.querySelectorAll('[name]').forEach(el=>{const parts=el.name.split(':');if(el.name==='model-id')e.form.id=el.value;else if(el.name==='description')e.form.description=el.value;else if(parts[0]==='global')e.form.bindings[parts[1]]=el.value;else if(parts[0]==='mode'&&e.form.modes[Number(parts[1])])e.form.modes[Number(parts[1])][parts[2]]=el.value;else if(parts[0]==='load'&&e.form.modes[Number(parts[1])]?.loads[Number(parts[2])])e.form.modes[Number(parts[1])].loads[Number(parts[2])][parts[3]]=el.value;});
      sessions.set(key,clone(e));
    }
    function checkedBinding(id,unit,label,{count=false,positive=false}={}){
      if(!id||!own(inputs(),id))throw Error('Choose an explicit existing input for '+label+'.');
      const record=inputs()[id];if(record.unit!==unit)throw Error(label+' must use the exact unit '+unit+'.');
      if(!finite(record.value))throw Error(label+' needs a finite value that the browser can represent precisely. Inspect or replace the original input through Author inputs.');
      if(record.value<0||(positive&&record.value<=0)||(count&&!Number.isInteger(record.value)))throw Error(label+' must be '+(positive?'positive':count?'a nonnegative whole number':'nonnegative')+'.');
      if(count&&record.value>1000000)throw Error(label+' must be a whole number from 0 to 1000000 for this bounded model.');
      return id;
    }
    function candidateModel(){
      remember();const e=state.editor,f=e.form;
      if(!safe(f.id,80))throw Error('Model ID must start with a letter and contain at most 80 letters, digits, underscores or hyphens. Reserved prototype names are unavailable.');
      if(!e.oldId&&arr(ctx.project.models).some(model=>model.id===f.id))throw Error('That model ID already exists. Choose a unique ID.');
      if(e.oldId&&e.oldId!==f.id)throw Error('An existing model’s stable ID cannot change.');
      if(e.oldId&&JSON.stringify(arr(ctx.project.models).find(model=>model.id===e.oldId))!==e.baseDefinition)throw Error('This model definition changed while the form was open. Reopen the budget editor before applying it.');
      if(f.unparsed.length)throw Error('Repair unsupported imported bindings before using this guided editor.');
      if(f.modes.length<1||f.modes.length>16)throw Error('Declare between one and sixteen sequential modes.');
      const bindings={};for(const [role,label,unit]of globals)bindings[role]=checkedBinding(f.bindings[role],unit,label);
      const modeIds=new Set();let loadCount=0;
      for(const [index,mode]of f.modes.entries()){
        if(!safe(mode.id)||modeIds.has(mode.id))throw Error('Every mode needs a unique ID: a letter followed by at most 31 letters, digits, underscores or hyphens.');modeIds.add(mode.id);
        const prefix='mode.'+(index+1)+'.'+mode.id+'.';bindings[prefix+'duration']=checkedBinding(mode.duration,'s','duration for '+mode.id,{positive:true});bindings[prefix+'generation']=checkedBinding(mode.generation,'W','generation for '+mode.id);
        if(!mode.loads.length)throw Error('Declare at least one equipment row per mode.');const loadIds=new Set();
        for(const load of mode.loads){if(!safe(load.id)||loadIds.has(load.id))throw Error('Equipment IDs must be unique within each mode and contain a letter followed by at most 31 letters, digits, underscores or hyphens.');loadIds.add(load.id);loadCount++;bindings[prefix+'load.'+load.id+'.power']=checkedBinding(load.power,'W','equipment power for '+load.id);bindings[prefix+'load.'+load.id+'.count']=checkedBinding(load.count,'1','equipment count for '+load.id,{count:true});}
      }
      if(loadCount>128)throw Error('A power budget supports at most 128 declared equipment rows.');
      return {id:f.id,type:'power_energy_budget',...(f.description.trim()?{description:f.description.trim()}:{}),inputs:bindings};
    }
    async function apply(candidate){if(!editable())throw Error('Start a shared draft on the latest revision before editing.');if(typeof ctx.onChange!=='function')throw Error('The shared draft editor is unavailable.');state.busy=true;state.error='';sessions.delete(key);render();try{await ctx.onChange(candidate);if(live()){ctx.project=clone(candidate);state.editor=null;}}catch(error){if(live()&&state.editor)sessions.set(key,clone(state.editor));throw error;}finally{if(live())state.busy=false;}}
    function removeReason(id){const users=[...arr(ctx.project.requirements).filter(req=>req.model_id===id).map(req=>'requirement '+req.id),...arr(ctx.project.systems).filter(system=>arr(system.model_ids).includes(id)).map(system=>'system '+system.id),...arr(ctx.project.interfaces).filter(link=>link.source?.model_id===id).map(link=>'interface '+link.id)];return users.length?'Remove or remap these dependent records first: '+users.join(', ')+'.':'';}
    host.oninput=remember;host.onchange=remember;
    host.onclick=async event=>{
      const target=event.target.closest('[data-pb]');if(!target||target.disabled||!live()||state.busy)return;
      remember();const [action,id,j]=target.dataset.pb.split(':');state.error='';
      try{
        if(action==='draft')await ctx.onEdit?.();else if(action==='save')await ctx.onSave?.();else if(action==='run')await ctx.onRun?.();else if(action==='inputs')await ctx.onAuthorInputs?.();else if(action==='requirements')await ctx.onAuthorRequirements?.();else if(action==='reference')await ctx.onReference?.();else if(action==='select')await ctx.onSelectModel?.(id);
        else if(action==='cancel'){state.editor=null;sessions.delete(key);}
        else if(action==='new'){if(!editable())throw Error('Start a shared draft before adding a model.');state.editor={oldId:null,form:parse(null)};}
        else if(action==='edit'){if(!editable())throw Error('Start a shared draft before editing a model.');const model=models().find(model=>model.id===id);if(!model)throw Error('This model is no longer present.');state.editor={oldId:id,baseDefinition:JSON.stringify(model),form:parse(model)};}
        else if(action==='remove'){const reason=removeReason(id);if(reason)throw Error(reason);const next=clone(ctx.project);next.models=arr(next.models).filter(model=>model.id!==id);await apply(next);}
        else if(state.editor&&editable()){
          const modes=state.editor.form.modes,index=Number(id),mode=modes[index];
          if(state.editor.form.unparsed.length)throw Error('Repair unsupported imported bindings before editing their mode structure.');
          if(action==='add-mode'&&modes.length<16)modes.push({id:'',duration:'',generation:'',loads:[{id:'',power:'',count:''}]});
          else if(action==='remove-mode'&&mode&&modes.length>1)modes.splice(index,1);
          else if(action==='up'&&mode&&index>0)[modes[index-1],modes[index]]=[modes[index],modes[index-1]];
          else if(action==='down'&&mode&&index<modes.length-1)[modes[index+1],modes[index]]=[modes[index],modes[index+1]];
          else if(action==='add-load'&&mode&&modes.reduce((sum,m)=>sum+m.loads.length,0)<128)mode.loads.push({id:'',power:'',count:''});
          else if(action==='remove-load'&&mode&&mode.loads.length>1)mode.loads.splice(Number(j),1);
        }
      }catch(error){if(live())state.error=error.message;}if(live())render();
    };
    host.onsubmit=async event=>{if(!event.target.matches('[data-pb-form]'))return;event.preventDefault();if(state.busy||!live())return;try{const model=candidateModel(),next=clone(ctx.project),e=state.editor;if(e.oldId){const index=arr(next.models).findIndex(model=>model.id===e.oldId);if(index<0)throw Error('This model is no longer present.');next.models[index]=model;}else next.models.push(model);await apply(next);}catch(error){if(live()){state.error=error.message;state.busy=false;}}if(live())render();};
    render();
  }
  window.SixDPowerBudget=Object.freeze({mount,unmount,report});
})();
