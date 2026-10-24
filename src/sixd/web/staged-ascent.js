/* Playback and plots of retained staged-ascent samples. No browser physics. */
(() => {
  'use strict';
  let active = null;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const human = value => String(value ?? '').replace(/_/g, ' ');
  const list = value => Array.isArray(value) ? value : [];
  const unit = value => String(value ?? '').replace(/\^(-?\d+)/g, (_, power) => [...power].map(c => ({'-':'⁻','0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹'}[c])).join(''));
  const short = value => Number.isFinite(value) ? Number(value.toPrecision(6)).toString() : '—';
  const value = (number, units = '') => '<span title="' + esc(String(number) + (units ? ' ' + units : '')) + '">' + esc(short(number) + (units ? ' ' + unit(units) : '')) + '</span>';
  const table = (headers, rows) => '<div class="sa-table" tabindex="0"><table class="sd-table"><thead><tr>' + headers.map(text => '<th scope="col">' + esc(text) + '</th>').join('') + '</tr></thead><tbody>' + rows.map(row => '<tr>' + row.map(text => '<td>' + text + '</td>').join('') + '</tr>').join('') + '</tbody></table></div>';
  const bullets = items => '<ul>' + list(items).map(text => '<li>' + esc(text) + '</li>').join('') + '</ul>';
  const button = (action, text, disabled = false) => '<button type="button" class="sd-button" data-sa-action="' + action + '"' + (disabled ? ' disabled' : '') + '>' + esc(text) + '</button>';
  const charts = [
    ['Altitude', 'm', [['altitude_m','Altitude','#5267aa']]],
    ['Signed downrange', 'm', [['downrange_m','Launch-surface arc','#397c70']]],
    ['Velocity components and speed', 'm/s', [['radial_velocity_m_s','Radial velocity','#5267aa'],['tangential_velocity_m_s','Tangential velocity','#397c70'],['speed_m_s','Speed','#ad7b41']]],
    ['Declared pitch', 'rad', [['pitch_angle_rad','Pitch from local vertical','#8a689d']]],
    ['Mass and active-stage propellant', 'kg', [['mass_kg','Attached mass','#8a689d'],['stage_propellant_kg','Active-stage propellant','#397c70']]],
    ['Dynamic pressure', 'Pa', [['dynamic_pressure_pa','Dynamic pressure','#ad7b41']]],
    ['Acceleration magnitude', 'm/s²', [['acceleration_m_s2','Acceleration magnitude','#a35767']]],
    ['Force magnitudes', 'N', [['thrust_n','Thrust','#5267aa'],['drag_n','Drag magnitude','#ad7b41']]],
  ];

  const fields = [['dry_mass','Dry mass','kg'],['propellant_mass','Propellant mass','kg'],['specific_impulse','Specific impulse','s'],['separation_delay','Delay after separation','s']];
  const segmentFields = [['duration','Duration','s'],['thrust_start','Start thrust','N'],['thrust_end','End thrust','N']];
  const clone = object => JSON.parse(JSON.stringify(object));
  function profileRows(project,model) {
    const roles = [...Object.keys(model.inputs || {}),...Object.keys(model.links || {})];
    const count = Math.max(0,...roles.map(role => Number(/^stage\.(\d+)\./.exec(role)?.[1] || 0)));
    if (count > 4) throw Error('This editor supports one to four serial stages.');
    const read = role => { const id = model.inputs?.[role], input = project.inputs?.[id];return {id,text:input && typeof input.value === 'number' ? String(input.value) : ''}; };
    return Array.from({length:count},(_,index) => {
      const stage = index+1,prefix = 'stage.'+stage+'.',row = {_refs:{},segments:[]};
      for (const [field] of fields) { const record = read(prefix+field);row[field]=record.text;row._refs[field]=record.id; }
      const segments = Math.max(0,...roles.map(role => Number(new RegExp('^stage\\.'+stage+'\\.segment\\.(\\d+)\\.').exec(role)?.[1] || 0)));
      if (segments > 6) throw Error('This editor supports at most six thrust segments per stage.');
      row.segments=Array.from({length:segments},(_,segment) => {
        const result={_refs:{}};for (const [field] of segmentFields) { const record=read(prefix+'segment.'+(segment+1)+'.'+field);result[field]=record.text;result._refs[field]=record.id; }return result;
      });return row;
    });
  }
  function number(text,label) {
    if (typeof text !== 'string' || !text.trim()) throw Error(label+' is required.');
    const result=Number(text);if (!Number.isFinite(result)) throw Error(label+' must be a finite number.');return result;
  }
  function profileCandidate(project,modelId,rows) {
    if (!Array.isArray(rows) || rows.length<1 || rows.length>4) throw Error('Supply one to four serial stages.');
    const candidate=clone(project),model=candidate.models.find(item=>item.id===modelId);
    if (!model || model.type!=='staged_ascent') throw Error('Choose a staged-ascent model.');
    if (Object.keys(model.links || {}).some(role=>role.startsWith('stage.'))) throw Error('A stage parameter is supplied by a calculated link. Edit that link in Author project instead of replacing it here.');
    const previous={...model.inputs};
    for (const role of Object.keys(model.inputs)) if (role.startsWith('stage.')) delete model.inputs[role];
    const assigned=new Map();
    function bind(role,text,units,oldId,label,allowZero=false) {
      const value=number(text,label);if (value<0 || (!allowZero && value===0)) throw Error(label+' must be '+(allowZero?'nonnegative.':'positive.'));
      let id=oldId;
      if (id && !Object.hasOwn(candidate.inputs,id)) throw Error('Bound input '+id+' is unavailable. Reopen this saved configuration.');
      if (!id) { const stem='staged_'+modelId+'_'+role.replace(/[^a-zA-Z0-9_]/g,'_');id=stem;let index=1;while(Object.hasOwn(candidate.inputs,id))id=stem+'_'+index++;candidate.inputs[id]={value,unit:units,source:'User-supplied draft profile; applicability unverified.'}; }
      if (candidate.inputs[id].unit!==units) throw Error('Input '+id+' requires '+units+'; correct its unit explicitly in the input editor.');
      if (assigned.has(id) && assigned.get(id)!==value) throw Error('Two edited roles share input '+id+' but have different values. Use consistent values or rebind them in Author project.');
      assigned.set(id,value);candidate.inputs[id].value=value;model.inputs[role]=id;
    }
    rows.forEach((row,index)=>{
      const stage=index+1,prefix='stage.'+stage+'.';
      if (!Array.isArray(row.segments) || row.segments.length<1 || row.segments.length>6) throw Error('Stage '+stage+' needs one to six thrust segments.');
      for (const [field,label,units] of fields) bind(prefix+field,field==='separation_delay'&&index===rows.length-1?'0':row[field],units,Object.hasOwn(row,'_refs')?row._refs[field]:previous[prefix+field],'Stage '+stage+' '+label,field==='separation_delay'||field==='dry_mass');
      row.segments.forEach((segment,s)=>{for (const [field,label,units] of segmentFields) bind(prefix+'segment.'+(s+1)+'.'+field,segment[field],units,Object.hasOwn(segment,'_refs')?segment._refs[field]:previous[prefix+'segment.'+(s+1)+'.'+field],'Stage '+stage+', segment '+(s+1)+' '+label,field!=='duration');});
    });
    return candidate;
  }
  function timeline(artifact) {
    const plan=list(artifact?.solver?.stage_plan);
    if(!plan.length)return '<p class="sd-notice">No recorded stage timeline for this configuration.</p>';
    const rows=plan.map(stage=>[esc(stage.stage),value(stage.ignition_time_s,'s'),value(stage.burnout_time_s,'s'),stage.separation_time_s==null?'Final dry stage retained':value(stage.separation_time_s,'s'),stage.next_ignition_time_s==null?'—':value(stage.next_ignition_time_s,'s'),value(stage.initial_mass_kg,'kg'),value(stage.burnout_mass_kg,'kg'),value(stage.post_separation_mass_kg,'kg'),value(stage.planned_profile_duration_s,'s'),value(stage.used_profile_duration_s,'s'),value(stage.unused_profile_duration_s,'s')]);
    return '<section class="sa-timeline"><h3>Recorded stage timeline</h3>'+table(['Stage','Ignition','Burnout','Separation','Next ignition','Initial attached mass','Burnout mass','After separation','Supplied profile span','Used powered span','Unused profile span'],rows)+'<p class="sa-note">Lower-stage dry mass is discarded at ideal separation with no imposed velocity impulse. Any unused thrust-profile tail is retained as supplied configuration, not executed after fuel exhaustion.</p></section>';
  }
  function stageSummary(result,project,model) {
    let definitions;try { definitions=profileRows(project,model); } catch(error) { return '<p class="sd-notice">Stage profile unavailable: '+esc(error.message)+'</p>'; }
    const supplied=definitions.map((stage,index)=>'<details class="sd-source"'+(index===0?' open':'')+'><summary>Stage '+(index+1)+' · supplied mass and thrust profile</summary>'+table(['Dry mass · kg','Propellant · kg','Isp · s','Separation delay · s'],[[esc(stage.dry_mass||'Unspecified'),esc(stage.propellant_mass||'Unspecified'),esc(stage.specific_impulse||'Unspecified'),index===definitions.length-1?'0 · final stage retained':esc(stage.separation_delay||'Unspecified')]])+table(['Segment','Duration · s','Start thrust · N','End thrust · N'],stage.segments.map((segment,i)=>[i+1,esc(segment.duration||'Unspecified'),esc(segment.thrust_start||'Unspecified'),esc(segment.thrust_end||'Unspecified')]))+'</details>').join('');
    return '<section class="sa-stage-summary"><h3>Stages and thrust programme</h3><p class="sa-note">Thrust varies linearly inside each supplied segment. Fuel exhaustion can truncate the remaining profile. Attached mass includes the payload and every attached upper stage; only exhausted nonfinal dry stages are dropped.</p>'+supplied+'</section>';
  }

  function shownRows(artifact) {
    const rows = list(artifact.samples), indices = new Set([0, rows.length - 1]);
    for (const event of list(artifact.events)) indices.add(event.sample_index);
    const stride = Math.max(1, Math.ceil(rows.length / 600));
    for (let index = 0; index < rows.length; index += stride) indices.add(index);
    return [...indices].filter(index => index >= 0 && index < rows.length).sort((a,b) => a-b).map(index => rows[index]);
  }

  function chart(artifact, title, units, series) {
    const rows = artifact.samples, shown = shownRows(artifact), end = rows.at(-1).time_s;
    let low = 0, high = 0;
    for (const row of rows) for (const [key] of series) { low = Math.min(low,row[key]);high = Math.max(high,row[key]); }
    const pad = (high-low || 1)*.07;low -= pad;high += pad;
    const x = time => 68 + 435*time/end, y = number => 181 - 143*(number-low)/(high-low);
    const paths = series.map(([key,,color]) => '<path d="' + shown.map((row,index) => (index?'L':'M') + x(row.time_s).toFixed(2) + ',' + y(row[key]).toFixed(2)).join(' ') + '" fill="none" stroke="' + color + '" stroke-width="1.8"/>').join('');
    const markers = list(artifact.events).filter(event => ['pitch_start','pitch_end','stage_burnout_before','separation_after','ignition_after'].includes(event.event));
    return '<figure class="sa-chart"><figcaption>' + esc(title) + ' · ' + esc(units) + '</figcaption><svg viewBox="0 0 540 225" role="img" aria-label="' + esc(title + ' against time from saved samples') + '"><path d="M68 38V181H503" fill="none" stroke="#cbd0d8"/>' + markers.map(event => '<path d="M' + x(event.time_s) + ' 38V181" stroke="#a1a8b4" stroke-dasharray="4 4"/>').join('') + paths + '<line data-sa-cursor x1="68" x2="68" y1="38" y2="181" stroke="#262b35" stroke-opacity=".5"/><text x="62" y="42" text-anchor="end">' + esc(short(high)) + '</text><text x="62" y="181" text-anchor="end">' + esc(short(low)) + '</text><text x="68" y="204">0 s</text><text x="503" y="204" text-anchor="end">' + esc(short(end)) + ' s</text></svg><div class="sa-legend">' + series.map(([,label,color]) => '<span><i style="background:' + color + '"></i>' + esc(label) + '</span>').join('') + '<span>Dashed: retained pitch / stage events</span></div></figure>';
  }

  function pathScale(artifact) {
    const rows = artifact.samples;
    let minX = 0, maxX = 0, maxY = 0;
    for (const row of rows) { minX = Math.min(minX,row.downrange_m);maxX = Math.max(maxX,row.downrange_m);maxY = Math.max(maxY,row.altitude_m); }
    const spanX = Math.max(maxX-minX, 1), spanY = Math.max(maxY,1);
    const scale = Math.min(430/spanX,220/spanY)*.9;
    const width = spanX*scale;
    const x = number => 70+(430-width)/2+(number-minX)*scale;
    const y = number => 260-number*scale;
    return {x,y,minX,maxX,maxY,scale};
  }

  function pathFigure(artifact) {
    const scale = pathScale(artifact), {x,y} = scale;
    const path = shownRows(artifact).map((row,index) => (index?'L':'M') + x(row.downrange_m).toFixed(2) + ',' + y(row.altitude_m).toFixed(2)).join(' ');
    return '<figure class="sa-path"><figcaption>Recorded ascent path</figcaption><svg viewBox="0 0 560 325" role="img" aria-label="Saved altitude against signed launch-surface downrange, equal distance scales"><path d="M70 35V260H500" fill="none" stroke="#cbd0d8"/><path d="M70 260H500" stroke="#a1aa94" stroke-width="2"/><path d="' + path + '" fill="none" stroke="#5267aa" stroke-width="2"/><circle data-sa-position cx="' + x(0) + '" cy="260" r="5" fill="#5267aa" stroke="#fff" stroke-width="2"/><text x="72" y="24">Altitude · m</text><text x="285" y="313" text-anchor="middle">Signed launch-surface downrange · m</text><text x="66" y="264" text-anchor="end">0</text><text x="66" y="43" text-anchor="end">' + esc(short(220/scale.scale)) + '</text><text x="70" y="284">' + esc(short(scale.minX-(430-(scale.maxX-scale.minX)*scale.scale)/2/scale.scale)) + '</text><text x="500" y="284" text-anchor="end">' + esc(short(scale.minX+(430+(scale.maxX-scale.minX)*scale.scale)/2/scale.scale)) + '</text></svg><p class="sa-note">Surface-arc downrange and altitude projection with equal distance scales. The point is a saved sample, not vehicle geometry. Lines join retained samples.</p></figure>';
  }

  function artifactFrom(result) {
    const artifact = result?.status === 'completed' ? result.staged_response : null;
    return artifact && list(artifact.samples).length > 0 && artifact.diagnostics ? artifact : null;
  }

  function evidence(result, ctx = {}) {
    if (ctx.hasDraft) return '<p class="sd-notice">Unsaved draft changes have no calculated staged-ascent response. Save the revision and run checks.</p>';
    if (!result) return '<p class="sd-notice">No current staged-ascent calculation for this saved revision. Run checks to record its response.</p>';
    const artifact = artifactFrom(result);
    if (!artifact) return '<p class="sd-notice">Staged-ascent response unavailable. A model or input gap does not establish a failed rocket.</p>' + bullets(result.issues);
    const diagnostics = artifact.diagnostics;
    return timeline(artifact)+'<p class="sa-diagnostic" data-sa-agreement="' + String(diagnostics.grid_agreement_met) + '"><strong>' + (diagnostics.grid_agreement_met ? 'Declared grid agreement met' : 'Diagnostic response · grid agreement not met') + '</strong><br>' + esc(diagnostics.reason) + '</p>' +
      table(['Saved metric','Value','Unit','Numerical allowance'],Object.entries(result.metrics || {}).map(([name,quantity]) => [esc(human(name)),value(quantity.value),esc(unit(quantity.unit)),value(diagnostics.metric_allowances?.[name])])) +
      '<p class="sa-note">These are sampled results. Numerical allowances combine declared state tolerances and observed grid differences; they are not rigorous error bounds or validation of the supplied vehicle.</p><div class="sa-charts">' + charts.map(([title,units,series]) => chart(artifact,title,units,series)).join('') + '</div>' +
      table(['Grid pair · steps/segment','Maximum position difference · m','Maximum velocity difference · m/s'],list(diagnostics.level_differences).map(row => [esc(row.coarse_steps + ' → ' + row.fine_steps),value(row.max_position_difference_m),value(row.max_velocity_difference_m_s)])) +
      '<details class="sd-source"><summary>Frame, supplied inputs and retained events</summary><p>Nonrotating body-centered inertial plane. Initial position is (launch radius, 0), initially at rest. Signed downrange is the launch-radius surface arc R × atan2(y, x). Pitch is measured from the local outward radial direction toward the counterclockwise tangent.</p><p>Classical RK4 with analytical piecewise-linear thrust impulse and propellant consumption. Integration segments end at thrust and pitch knots, burnout, separation and ignition events. ' + esc(artifact.samples.length) + ' fine-grid samples retained; intermediate grids remain in exported JSON.</p>' + table(['Parameter','Supplied value'],Object.entries(artifact.parameters || {}).map(([key,number]) => [esc(human(key)),value(number)])) + table(['Event','Sample index','Time · s'],list(artifact.events).map(event => [esc(human(event.event)),esc(event.sample_index),value(event.time_s)])) + '</details>' +
      '<details class="sd-source"><summary>Assumptions and unassessed scope</summary><h4>Assumptions</h4>' + bullets(artifact.assumptions) + '<h4>Not assessed</h4>' + bullets(artifact.not_assessed) + '</details>' +
      '<p class="sd-receipt">Project ' + esc(ctx.projectId || '—') + ' · saved revision R' + esc(ctx.revision ?? '—') + '<br>Run ' + esc(ctx.runId || '—') + '<br>Review ' + esc(ctx.reviewDigest || '—') + '<br>Solver SHA-256 ' + esc(artifact.source_fingerprint) + (ctx.origin ? '<br>' + esc(human(ctx.origin.disposition)) + ' from R' + esc(ctx.origin.revision) + ' · ' + esc(ctx.origin.run_id) : '') + '</p>';
  }

  function report(result, ctx = {}) {
    return '<section class="sa-evidence" data-staged-ascent-evidence="' + esc(ctx.modelId || result?.model_id || '') + '"><h3>Staged-ascent evidence</h3>' + evidence(result,ctx) + '</section>';
  }

  function unmount() {
    if (!active) return;
    active.controller.abort();
    cancelAnimationFrame(active.frame);
    active = null;
  }

  function mount(host, ctx) {
    unmount();
    const state = {host,ctx,controller:new AbortController(),frame:0,index:0,playing:false,editor:null,error:'',busy:false};
    active = state;
    const models = list(ctx.project?.models).filter(model => model.type === 'staged_ascent');
    state.modelId = models.find(item=>item.id===ctx.initialModelId)?.id || models[0]?.id;
    const model = () => models.find(item=>item.id===state.modelId);
    const result = () => ctx.modelResults?.[state.modelId];
    const artifact = () => ctx.hasDraft ? null : artifactFrom(result());
    function openProfile() {
      if (!ctx.hasDraft) {ctx.onEditProfile?.(state.modelId);return;}
      try {
        if (Object.keys(model()?.links || {}).some(role=>role.startsWith('stage.'))) throw Error('Stage parameters supplied by links are read-only here. Use Author project to edit their mappings.');
        state.editor=profileRows(ctx.project,model());state.error='';
      } catch(error) {state.error=error.message;}
      render();
    }
    function field(stage,segment,key,label,units,text,readonly=false) {
      return '<label class="sa-profile-field"><span>'+esc(label)+' · '+esc(unit(units))+'</span><input class="sd-input" type="number" step="any" data-sa-profile-stage="'+stage+'"'+(segment===null?'':' data-sa-profile-segment="'+segment+'"')+' data-sa-profile-key="'+esc(key)+'" value="'+esc(text)+'"'+(readonly?' readonly':' required')+(state.busy?' disabled':'')+'></label>';
    }
    function editor() {
      if (!state.editor) return '';
      return '<form class="sa-profile-editor" data-sa-profile-form><header><h3>Edit stage and thrust profile</h3><p>Changes stay in this form until Apply to draft. Existing input units and source labels are preserved; review their sources after changing values. Shared inputs also affect their other declared consumers. Removed bindings leave input records available elsewhere.</p></header>'+state.editor.map((stage,index)=>'<section class="sa-profile-stage"><div class="sa-profile-stage-heading"><h4>Stage '+(index+1)+'</h4>'+button('remove-stage:'+index,'Remove stage',state.editor.length===1||state.busy)+'</div><div class="sa-profile-fields">'+fields.map(([key,label,units])=>field(index,null,key,label,units,key==='separation_delay'&&index===state.editor.length-1?'0':stage[key],key==='separation_delay'&&index===state.editor.length-1)).join('')+'</div>'+(index===state.editor.length-1?'<p class="sa-note">Final dry stage retained; separation delay is fixed at 0 s.</p>':'')+'<h5>Piecewise-linear thrust segments</h5>'+stage.segments.map((segment,s)=>'<div class="sa-profile-segment"><span>Segment '+(s+1)+'</span><div class="sa-profile-fields">'+segmentFields.map(([key,label,units])=>field(index,s,key,label,units,segment[key])).join('')+'</div>'+button('remove-segment:'+index+':'+s,'Remove segment',stage.segments.length===1||state.busy)+'</div>').join('')+button('add-segment:'+index,'Add thrust segment',stage.segments.length>=6||state.busy)+'</section>').join('')+'<div class="sd-action-row">'+button('add-stage','Add stage',state.editor.length>=4||state.busy)+'<button type="submit" class="sd-button sd-primary"'+(state.busy?' disabled':'')+'>'+(state.busy?'Applying…':'Apply profile to draft')+'</button>'+button('cancel-profile','Cancel form edits',state.busy)+'</div><p class="sa-note">One to four stages and one to six segments per stage. New fields are intentionally blank. Fuel sufficiency, liftoff, numerical support and the physical domain are checked by the maintained calculator.</p></form>';
    }
    function stop() {
      state.playing = false;cancelAnimationFrame(state.frame);
      const play = host.querySelector('[data-sa-action="play"]');if (play) play.textContent = 'Play';
    }
    function sample() {
      const saved = artifact();if (!saved) return;
      const row = saved.samples[state.index], scale = pathScale(saved);
      host.querySelector('[data-sa-slider]').value = String(state.index);
      const point = host.querySelector('[data-sa-position]');point.setAttribute('cx',scale.x(row.downrange_m));point.setAttribute('cy',scale.y(row.altitude_m));
      host.querySelector('[data-sa-sample]').textContent = 'Sample ' + state.index + ' / ' + (saved.samples.length-1) + ' · ' + short(row.time_s) + ' s · stage '+row.stage+' · ' + human(row.event || row.phase);
      const eventPicker=host.querySelector('[data-sa-event]');eventPicker.value=String(state.index);
      host.querySelector('[data-sa-state]').innerHTML = table(['Quantity','Saved value'],[
        ['Active stage',row.stage,''],['Active-stage propellant',row.stage_propellant_kg,'kg'],['Altitude',row.altitude_m,'m'],['Signed downrange',row.downrange_m,'m'],['Speed',row.speed_m_s,'m/s'],
        ['Radial velocity',row.radial_velocity_m_s,'m/s'],['Tangential velocity',row.tangential_velocity_m_s,'m/s'],
        ['Pitch from local vertical',row.pitch_angle_rad,'rad'],['Mass',row.mass_kg,'kg'],['Thrust',row.thrust_n,'N'],
        ['Drag magnitude',row.drag_n,'N'],['Dynamic pressure',row.dynamic_pressure_pa,'Pa'],['Acceleration magnitude',row.acceleration_m_s2,'m/s²'],
      ].map(([label,number,units]) => [esc(label),value(number,units)]));
      const x = 68+435*row.time_s/saved.samples.at(-1).time_s;
      for (const cursor of host.querySelectorAll('[data-sa-cursor]')) { cursor.setAttribute('x1',x);cursor.setAttribute('x2',x); }
    }
    function render() {
      stop();state.index = 0;
      const saved = artifact(), hasModels = models.length > 0;
      host.innerHTML = '<section class="sa-page" aria-label="Staged ascent"><p class="sd-label">Saved R' + esc(ctx.revision) + ' · variable thrust and serial stages</p><h2>Follow the stages and thrust programme.</h2><p class="sd-lead">Replay saved variable-thrust flight, exact fuel cutoff, dry-mass separation and upper-stage ignition.</p><p class="sa-scope">Thrust and pitch programmes are supplied inputs. Nonfinal dry stages separate without a velocity impulse; the final dry stage is retained. One supplied drag coefficient and area remain fixed. Controller tracking, separation mechanics and whole-mission readiness are unassessed.</p><div class="sd-action-row">' + button('reference','Use constructed staged-ascent reference',!!ctx.hasDraft) + button('author','Author project') + (hasModels ? button('profile','Edit stage & thrust profile',ctx.isLatest === false || !ctx.onEditProfile && !ctx.hasDraft) + button('inputs','Other ascent inputs') + button('run','Run checks',!!ctx.hasDraft || ctx.isLatest === false) + button('report','Open full report',!ctx.runId || !!ctx.hasDraft) : '') + '</div>' +
        (!hasModels ? '<div class="sd-notice">This project has no staged-ascent model. Use the constructed reference or add a staged-ascent model through Author project. Creating a new reference preserves existing projects and runs no calculation.</div>' : '<label class="sa-select">Ascent model <select data-sa-model' + (state.editor ? ' disabled' : '') + '>' + models.map(model => '<option value="' + esc(model.id) + '"' + (model.id === state.modelId ? ' selected' : '') + '>' + esc(model.id) + '</option>').join('') + '</select></label>') +
        (state.error ? '<p class="sa-error" role="alert">'+esc(state.error)+'</p>' : '') + editor() + (ctx.hasDraft && hasModels ? '<p class="sd-notice">An unsaved draft is open. Its trajectory has not been calculated; saved playback is hidden until the draft is saved and checked or discarded.</p>' : '') +
        (saved ? '<section class="sa-playback" aria-label="Saved staged-ascent playback">' + pathFigure(saved) + '<div class="sa-playback-controls"><p data-sa-sample aria-live="off"></p><div class="sd-action-row">' + button('play','Play') + button('start','Launch') + button('cutoff-before','Stage cutoff before') + button('cutoff-after','Stage cutoff after',!saved.events.some(event => event.event === 'stage_burnout_after')) + button('previous-event','Previous event') + button('next-event','Next event') + button('end','Last sample') + '</div><label class="sa-event-select">Recorded event<select class="sd-select" data-sa-event><option value="">Choose an exact retained event</option>'+list(saved.events).map(event=>'<option value="'+event.sample_index+'">Stage '+esc(event.stage)+' · '+esc(human(event.event))+' · '+esc(short(event.time_s))+' s</option>').join('')+'</select></label><label class="sa-scrub">Recorded sample<input data-sa-slider type="range" min="0" max="' + (saved.samples.length-1) + '" step="1" value="0" aria-label="Recorded staged-ascent sample"></label><div data-sa-state></div></div></section>' : '') +
        (hasModels ? stageSummary(ctx.hasDraft?null:result(),ctx.project,model()) + evidence(result(),{...ctx,modelId:state.modelId,origin:ctx.modelOrigins?.[state.modelId]}) : '') + (ctx.hasDraft && hasModels ? '<div class="sd-action-row">'+button('preview','Preview affected checks',!!state.editor||state.busy)+button('save','Save revision',!!state.editor||state.busy)+'</div>' : '') +
        (hasModels ? '<h3>Declared requirements</h3>' + table(['Requirement','Finding','Actions'],list(ctx.project.requirements).filter(requirement => requirement.model_id === state.modelId).map(requirement => [esc(requirement.title),esc(ctx.hasDraft ? 'Uncalculated draft' : human(ctx.findings?.[requirement.id]?.status || 'not run')),'<button type="button" class="sd-button" data-sa-requirement="' + esc(requirement.id) + '">Inspect</button> <button type="button" class="sd-button" data-sa-investigate="' + esc(requirement.id) + '"' + (!ctx.runId || ctx.hasDraft ? ' disabled' : '') + '>Investigate</button>'])) : '') + '</section>';
      sample();
    }
    host.addEventListener('input', event => {
      if (event.target.matches('[data-sa-profile-key]') && state.editor && !state.busy) {
        const input=event.target,stage=state.editor[Number(input.dataset.saProfileStage)];
        const row=input.dataset.saProfileSegment===undefined?stage:stage?.segments[Number(input.dataset.saProfileSegment)];
        if(row)row[input.dataset.saProfileKey]=input.value;
        return;
      }
      if (!event.target.matches('[data-sa-slider]')) return;
      stop();state.index = Number(event.target.value);sample();
    },{signal:state.controller.signal});
    host.addEventListener('change', event => {
      if (event.target.matches('[data-sa-event]')) { const index=Number(event.target.value);if(event.target.value!==''&&Number.isInteger(index)&&index>=0&&index<(artifact()?.samples.length||0)){stop();state.index=index;sample();}return; }
      if (!event.target.matches('[data-sa-model]')) return;
      state.modelId = event.target.value;state.editor=null;state.error='';render();
    },{signal:state.controller.signal});
    host.addEventListener('click', event => {
      const requirement = event.target.closest('[data-sa-requirement],[data-sa-investigate]');
      if (requirement && !requirement.disabled) { stop();ctx.onRequirement?.(requirement.dataset.saRequirement || requirement.dataset.saInvestigate,!!requirement.dataset.saInvestigate);return; }
      const target = event.target.closest('[data-sa-action]');if (!target || target.disabled || state.busy) return;
      const action = target.dataset.saAction;
      if (action === 'profile') {stop();openProfile();return;}
      if (action === 'cancel-profile') {state.editor=null;state.error='';ctx.onCloseProfile?.();if(active===state)render();return;}
      if (action === 'add-stage' && state.editor && state.editor.length<4) {state.editor.push({_refs:{},dry_mass:'',propellant_mass:'',specific_impulse:'',separation_delay:'0',segments:[{_refs:{},duration:'',thrust_start:'',thrust_end:''}]});render();return;}
      if (action.startsWith('remove-stage:') && state.editor?.length>1) {state.editor.splice(Number(action.split(':')[1]),1);render();return;}
      if (action.startsWith('add-segment:') && state.editor) {const row=state.editor[Number(action.split(':')[1])];if(row?.segments.length<6)row.segments.push({_refs:{},duration:'',thrust_start:'',thrust_end:''});render();return;}
      if (action.startsWith('remove-segment:') && state.editor) {const [,stage,segment]=action.split(':'),row=state.editor[Number(stage)];if(row?.segments.length>1)row.segments.splice(Number(segment),1);render();return;}
      const callbacks = {reference:ctx.onReference,author:ctx.onAuthor,inputs:()=>ctx.onInputs?.(state.modelId),run:ctx.onRun,report:ctx.onReport,preview:ctx.onPreview,save:ctx.onSave};
      if (callbacks[action]) { stop();callbacks[action]();return; }
      const saved = artifact();if (!saved) return;
      if (action==='previous-event'||action==='next-event') {
        stop();const indices=list(saved.events).map(item=>item.sample_index).sort((a,b)=>a-b);
        state.index=action==='previous-event'?indices.filter(index=>index<state.index).at(-1)??0:indices.find(index=>index>state.index)??saved.samples.length-1;sample();return;
      }
      if (action === 'start' || action === 'end' || action.startsWith('cutoff-')) {
        stop();const stage=saved.samples[state.index].stage;
        state.index = action === 'start' ? 0 : action === 'end' ? saved.samples.length-1 : saved.events.find(item => item.stage===stage && item.event === (action === 'cutoff-before' ? 'stage_burnout_before' : 'stage_burnout_after'))?.sample_index ?? 0;sample();return;
      }
      if (action === 'play') {
        if (state.playing) { stop();return; }
        if (state.index === saved.samples.length-1) state.index = 0;
        state.playing = true;target.textContent = 'Pause';let previous = performance.now(), time = saved.samples[state.index].time_s;
        const tick = now => {
          if (active !== state || !state.playing) return;
          time += (now-previous)/1000*saved.samples.at(-1).time_s/12;previous = now;
          while (state.index < saved.samples.length-1 && saved.samples[state.index+1].time_s <= time) state.index++;
          sample();if (state.index === saved.samples.length-1) stop();else state.frame = requestAnimationFrame(tick);
        };
        state.frame = requestAnimationFrame(tick);
      }
    },{signal:state.controller.signal});
    host.addEventListener('submit',async event=>{
      if(!event.target.matches('[data-sa-profile-form]'))return;event.preventDefault();
      if(state.busy||!state.editor||!ctx.hasDraft)return;
      try {
        if(!ctx.onProfileChange)throw Error('This view cannot apply profile edits. Reopen the latest saved project.');
        const candidate=profileCandidate(ctx.project,state.modelId,state.editor);
        state.busy=true;state.error='';render();await ctx.onProfileChange(candidate);
        if(active!==state)return;state.editor=null;
      }catch(error){if(active===state)state.error=error.message||'The stage profile could not be applied.';}
      finally{if(active===state){state.busy=false;render();}}
    },{signal:state.controller.signal});
    if(ctx.editProfile && ctx.hasDraft && state.modelId) {
      try {if(Object.keys(model().links||{}).some(role=>role.startsWith('stage.')))throw Error('Stage parameters supplied by calculated links are read-only here. Use Author project to edit their mappings.');state.editor=profileRows(ctx.project,model());}
      catch(error){state.error=error.message;}
    }
    render();
  }
  window.SixDStagedAscent = Object.freeze({mount,unmount,evidence,report,profileCandidate,profileRows});
})();
