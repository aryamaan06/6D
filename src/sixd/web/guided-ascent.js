/* Playback and plots of retained guided-ascent samples. No browser physics. */
(() => {
  'use strict';
  let active = null;
  const disclosureStates = new Map();
  function disclosure(ctx,id,title,body,extra='') {
    const key=JSON.stringify([ctx.projectId??null,ctx.revision??null,ctx.runId??null,ctx.modelId??null,!!ctx.hasDraft]);
    return '<details class="sd-source" data-flight-disclosure="'+id+'" data-flight-context="'+esc(key)+'"'+(disclosureStates.get(key)?.get(id)?' open':'')+extra+'><summary>'+esc(title)+'</summary>'+body+'</details>';
  }
  function bindDisclosures(host,signal) {
    host.addEventListener('toggle',event=>{
      const item=event.target;if(!item.matches?.('details[data-flight-disclosure]')||!host.contains(item))return;
      const key=item.dataset.flightContext;if(!disclosureStates.has(key))disclosureStates.set(key,new Map());
      disclosureStates.get(key).set(item.dataset.flightDisclosure,item.open);
      if(disclosureStates.size>50)disclosureStates.delete(disclosureStates.keys().next().value);
    },{capture:true,signal});
  }
  function outcome(result,ctx) {
    const requirements=(ctx.project?.requirements||[]).filter(item=>item.model_id===ctx.modelId);
    if(ctx.hasDraft)return '<p class="sd-notice">Draft not calculated. Save the revision and run its checks.</p>';
    if(!result||result.status!=='completed')return '<p class="sd-notice">Flight not assessed: no completed calculation for this saved context. Inspect the issues below.</p>';
    const counts={met:0,not_met:0,not_assessed:0,not_run:0};
    for(const requirement of requirements){const finding=ctx.findings?.[requirement.id],status=['insufficient_accuracy','accuracy_not_assessed'].includes(finding?.assessment_status)?'not_assessed':finding?.status||'not_run';counts[Object.hasOwn(counts,status)?status:'not_assessed']++;}
    const response=result.flight_response||result.guided_response||result.staged_response;
    const accuracy=response?.diagnostics;
    return '<section class="ga-result-summary" aria-label="Saved flight check results"><strong>Saved checks</strong><p>'+ (requirements.length?counts.met+' meet criteria · '+counts.not_met+' criteria unmet · '+counts.not_assessed+' not assessed'+(counts.not_run?' · '+counts.not_run+' not calculated':''):'No requirements are linked to this flight model.')+'</p><p class="ga-note">These results concern the supplied model and saved inputs, not a complete rocket or mission.</p>'+(accuracy?.grid_agreement_met===false?'<p class="sd-notice"><strong>Numerical agreement not met.</strong> '+esc(accuracy.reason)+'</p>':'')+'</section>';
  }
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const human = value => String(value ?? '').replace(/_/g, ' ');
  const list = value => Array.isArray(value) ? value : [];
  const unit = value => window.SixDUnits.format(value);
  const short = value => window.SixDUnits.number(value);
  const value = (number, units = '') => window.SixDUnits.value(number,units);
  const table = (headers, rows) => '<div class="ga-table" tabindex="0"><table class="sd-table"><thead><tr>' + headers.map(text => '<th scope="col">' + esc(text) + '</th>').join('') + '</tr></thead><tbody>' + rows.map(row => '<tr>' + row.map(text => '<td>' + text + '</td>').join('') + '</tr>').join('') + '</tbody></table></div>';
  const bullets = items => '<ul>' + list(items).map(text => '<li>' + esc(text) + '</li>').join('') + '</ul>';
  const button = (action, text, disabled = false) => '<button type="button" class="sd-button" data-ga-action="' + action + '"' + (disabled ? ' disabled' : '') + '>' + esc(text) + '</button>';
  const charts = [
    ['Altitude', 'm', [['altitude_m','Altitude','#5267aa']]],
    ['Signed downrange', 'm', [['downrange_m','Launch-surface arc','#397c70']]],
    ['Velocity components and speed', 'm/s', [['radial_velocity_m_s','Radial velocity','#5267aa'],['tangential_velocity_m_s','Tangential velocity','#397c70'],['speed_m_s','Speed','#ad7b41']]],
    ['Declared pitch', 'rad', [['pitch_angle_rad','Pitch from local vertical','#8a689d']]],
    ['Remaining mass', 'kg', [['mass_kg','Mass','#8a689d']]],
    ['Dynamic pressure', 'Pa', [['dynamic_pressure_pa','Dynamic pressure','#ad7b41']]],
    ['Acceleration magnitude', 'm/s²', [['acceleration_m_s2','Acceleration magnitude','#a35767']]],
    ['Force magnitudes', 'N', [['thrust_n','Thrust','#5267aa'],['drag_n','Drag magnitude','#ad7b41']]],
  ];

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
    const markers = list(artifact.events).filter(event => ['pitch_start','pitch_end','before_cutoff'].includes(event.event));
    return '<figure class="ga-chart"><figcaption>' + esc(title) + ' · ' + esc(units) + '</figcaption><svg viewBox="0 0 540 225" role="img" aria-label="' + esc(title + ' against time from saved samples') + '"><path d="M68 38V181H503" fill="none" stroke="#cbd0d8"/>' + markers.map(event => '<path d="M' + x(event.time_s) + ' 38V181" stroke="#a1a8b4" stroke-dasharray="4 4"/>').join('') + paths + '<line data-ga-cursor x1="68" x2="68" y1="38" y2="181" stroke="#262b35" stroke-opacity=".5"/><text x="62" y="42" text-anchor="end">' + esc(short(high)) + '</text><text x="62" y="181" text-anchor="end">' + esc(short(low)) + '</text><text x="68" y="204">0 s</text><text x="503" y="204" text-anchor="end">' + esc(short(end)) + ' s</text></svg><div class="ga-legend">' + series.map(([,label,color]) => '<span><i style="background:' + color + '"></i>' + esc(label) + '</span>').join('') + '<span>Dashed: retained pitch / burnout events</span></div></figure>';
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
    return '<figure class="ga-path"><figcaption>Recorded ascent path</figcaption><svg viewBox="0 0 560 325" role="img" aria-label="Saved altitude against signed launch-surface downrange, equal distance scales"><path d="M70 35V260H500" fill="none" stroke="#cbd0d8"/><path d="M70 260H500" stroke="#a1aa94" stroke-width="2"/><path d="' + path + '" fill="none" stroke="#5267aa" stroke-width="2"/><circle data-ga-position cx="' + x(0) + '" cy="260" r="5" fill="#5267aa" stroke="#fff" stroke-width="2"/><text x="72" y="24">Altitude · m</text><text x="285" y="313" text-anchor="middle">Signed launch-surface downrange · m</text><text x="66" y="264" text-anchor="end">0</text><text x="66" y="43" text-anchor="end">' + esc(short(220/scale.scale)) + '</text><text x="70" y="284">' + esc(short(scale.minX-(430-(scale.maxX-scale.minX)*scale.scale)/2/scale.scale)) + '</text><text x="500" y="284" text-anchor="end">' + esc(short(scale.minX+(430+(scale.maxX-scale.minX)*scale.scale)/2/scale.scale)) + '</text></svg><p class="ga-note">Surface-arc downrange and altitude projection with equal distance scales. The point is a saved sample, not vehicle geometry. Lines join retained samples.</p></figure>';
  }

  function artifactFrom(result) {
    const artifact = result?.status === 'completed' ? result.guided_response : null;
    return artifact && list(artifact.samples).length > 0 && artifact.diagnostics ? artifact : null;
  }

  function evidence(result,ctx={}) {
    if(ctx.hasDraft)return '<p class="sd-notice">Draft changes have no calculated flight response. Save the revision and run checks.</p>';
    if(!result)return '<p class="sd-notice">No current flight calculation for this saved revision. Run checks to record its response.</p>';
    const artifact=artifactFrom(result);
    if(!artifact)return '<p class="sd-notice">Flight response unavailable. This model/input gap does not establish a failed vehicle.</p>'+bullets(result.issues);
    const diagnostics=artifact.diagnostics;
    const metrics=table(['Saved metric','Value','Unit','Numerical allowance'],Object.entries(result.metrics||{}).map(([name,quantity])=>[esc(human(name)),value(quantity.value),esc(unit(quantity.unit)),value(diagnostics.metric_allowances?.[name])]));
    const grids=table(['Grid pair · steps/segment','Maximum position difference · m','Maximum velocity difference · m/s'],(diagnostics.level_differences||[]).map(row=>[esc(row.coarse_steps+' → '+row.fine_steps),value(row.max_position_difference_m),value(row.max_velocity_difference_m_s)]));
    const exactEvidence={metrics:result.metrics,diagnostics};
    return '<p class="ga-diagnostic" data-ga-agreement="'+String(diagnostics.grid_agreement_met)+'"><strong>'+(diagnostics.grid_agreement_met?'Declared grid agreement met':'Diagnostic response · grid agreement not met')+'</strong><br>'+esc(diagnostics.reason)+'</p><p class="ga-note">Sampled model output. Grid agreement is not a physical validation or a rigorous error bound.</p>'+
      disclosure(ctx,'metrics','View saved metrics and numerical comparison',metrics+'<p class="ga-note">Values use compact display precision. Allowances combine declared state tolerances and observed grid differences. Extrema concern retained samples only.</p>'+grids)+
      disclosure(ctx,'graphs','View graphs ('+charts.length+')',charts.map(([title,units,series],index)=>disclosure(ctx,'graph-'+index,title,chart(artifact,title,units,series))).join(''))+

      disclosure(ctx,'exact-metrics','Exact saved metrics and numerical diagnostics','<pre>'+esc(JSON.stringify(exactEvidence,null,2))+'</pre>',' data-preserve-notation')+
      disclosure(ctx,'method','Inputs, method and retained events','<p>Initial position is (launch radius, 0), initially at rest. Signed downrange is the launch-radius surface arc R × atan2(y, x). Pitch is measured from the local outward radial direction toward the counterclockwise tangent. Classical RK4 in a nonrotating body-centered inertial plane, with analytical mass depletion and separate retained event boundaries. '+esc(artifact.samples.length)+' fine-grid samples retained; intermediate grids remain in exported JSON.</p>'+table(['Parameter','Supplied value'],Object.entries(artifact.parameters||{}).map(([key,number])=>[esc(human(key)),esc(number)]))+table(['Event','Sample index','Time · s'],(artifact.events||[]).map(event=>[esc(human(event.event)),esc(event.sample_index),esc(event.time_s)])),' data-preserve-notation')+
      disclosure(ctx,'assumptions','Assumptions and unassessed scope','<h4>Assumptions</h4>'+bullets(artifact.assumptions)+'<h4>Not assessed</h4>'+bullets(artifact.not_assessed))+
      disclosure(ctx,'identity','Calculation identity and execution origin','<p class="sd-receipt">Project '+esc(ctx.projectId||'—')+' · saved revision R'+esc(ctx.revision??'—')+'<br>Run '+esc(ctx.runId||'—')+'<br>Review '+esc(ctx.reviewDigest||'—')+'<br>Solver SHA-256 '+esc(artifact.source_fingerprint)+(ctx.origin?'<br>'+esc(human(ctx.origin.disposition))+' from R'+esc(ctx.origin.revision)+' · '+esc(ctx.origin.run_id):'')+'</p>');
  }
  function report(result, ctx = {}) {
    return '<section class="ga-evidence" data-guided-ascent-evidence="' + esc(ctx.modelId || result?.model_id || '') + '"><h3>Guided-ascent evidence</h3>' + evidence(result,ctx) + '</section>';
  }

  function unmount() {
    if (!active) return;
    active.controller.abort();
    cancelAnimationFrame(active.frame);
    active = null;
  }

  function mount(host, ctx) {
    unmount();
    const state = {host,ctx,controller:new AbortController(),frame:0,index:0,playing:false};
    active = state;
    const models = list(ctx.project?.models).filter(model => model.type === 'guided_ascent');
    state.modelId = models[0]?.id;
    const result = () => ctx.modelResults?.[state.modelId];
    const artifact = () => ctx.hasDraft ? null : artifactFrom(result());
    function stop() {
      state.playing = false;cancelAnimationFrame(state.frame);
      const play = host.querySelector('[data-ga-action="play"]');if (play) play.textContent = 'Play';
    }
    function sample() {
      const saved = artifact();if (!saved) return;
      const row = saved.samples[state.index], scale = pathScale(saved);
      host.querySelector('[data-ga-slider]').value = String(state.index);
      const point = host.querySelector('[data-ga-position]');point.setAttribute('cx',scale.x(row.downrange_m));point.setAttribute('cy',scale.y(row.altitude_m));
      host.querySelector('[data-ga-sample]').textContent = 'Sample ' + state.index + ' / ' + (saved.samples.length-1) + ' · ' + short(row.time_s) + ' s · ' + human(row.event || row.phase);
      host.querySelector('[data-ga-state]').innerHTML = table(['Quantity','Saved value'],[
        ['Altitude',row.altitude_m,'m'],['Signed downrange',row.downrange_m,'m'],['Speed',row.speed_m_s,'m/s'],
        ['Radial velocity',row.radial_velocity_m_s,'m/s'],['Tangential velocity',row.tangential_velocity_m_s,'m/s'],
        ['Pitch from local vertical',row.pitch_angle_rad,'rad'],['Mass',row.mass_kg,'kg'],['Thrust',row.thrust_n,'N'],
        ['Drag magnitude',row.drag_n,'N'],['Dynamic pressure',row.dynamic_pressure_pa,'Pa'],['Acceleration magnitude',row.acceleration_m_s2,'m/s²'],
      ].map(([label,number,units]) => [esc(label),value(number,units)])) + disclosure({...ctx,modelId:state.modelId},'exact-sample','Exact recorded sample','<pre>'+esc(JSON.stringify(row,null,2))+'</pre>',' data-preserve-notation');
      const x = 68+435*row.time_s/saved.samples.at(-1).time_s;
      for (const cursor of host.querySelectorAll('[data-ga-cursor]')) { cursor.setAttribute('x1',x);cursor.setAttribute('x2',x); }
    }
    function render() {
      stop();state.index = 0;
      const saved = artifact(), hasModels = models.length > 0;
      host.innerHTML = '<section class="ga-page" aria-label="Guided ascent"><p class="sd-label">Saved R' + esc(ctx.revision) + ' · bounded planar ascent</p><h2>Follow the ascent and its steering programme.</h2><p class="sd-lead">Replay recorded horizontal motion and altitude through a declared pitch programme, burnout and above-surface coast.</p><p class="ga-scope">Prescribed steering is an input. This calculation does not verify closed-loop guidance, navigation, attitude stability or a complete launch-to-orbit mission.</p><div class="sd-action-row">' + button('reference','Use constructed guided-ascent reference',!!ctx.hasDraft) + button('author','Author project') + (hasModels ? button('inputs','Edit ascent inputs') + button('run','Run checks',!!ctx.hasDraft || ctx.isLatest === false) + button('report','Open full report',!ctx.runId || !!ctx.hasDraft) : '') + '</div>' +
        (!hasModels ? '<div class="sd-notice">This project has no guided-ascent model. Use the constructed reference or add a guided-ascent model through Author project. Creating a new reference preserves existing projects and runs no calculation.</div>' : '<label class="ga-select">Ascent model <select data-ga-model>' + models.map(model => '<option value="' + esc(model.id) + '"' + (model.id === state.modelId ? ' selected' : '') + '>' + esc(model.id) + '</option>').join('') + '</select></label>') +
        (ctx.hasDraft && hasModels ? '<p class="sd-notice">An unsaved draft is open. Its trajectory has not been calculated; saved playback is hidden until the draft is saved and checked or discarded.</p>' : '') +
        (hasModels ? outcome(result(),{...ctx,modelId:state.modelId}) : '') +
        (saved ? '<section class="ga-playback" aria-label="Saved guided-ascent playback">' + pathFigure(saved) + '<div class="ga-playback-controls"><p data-ga-sample aria-live="off"></p><div class="sd-action-row">' + button('play','Play') + button('start','Launch') + button('cutoff-before','Before cutoff') + button('cutoff-after','After cutoff',!saved.events.some(event => event.event === 'after_cutoff')) + button('end','Last sample') + '</div><label class="ga-scrub">Recorded sample<input data-ga-slider type="range" min="0" max="' + (saved.samples.length-1) + '" step="1" value="0" aria-label="Recorded guided-ascent sample"></label>'+disclosure({...ctx,modelId:state.modelId},'sample-values','View sample values','<div data-ga-state></div>')+'</div></section>' : '') +
        (hasModels ? evidence(result(),{...ctx,modelId:state.modelId,origin:ctx.modelOrigins?.[state.modelId]}) : '') +
        (hasModels ? '<h3>Declared requirements</h3>' + table(['Requirement','Finding','Actions'],list(ctx.project.requirements).filter(requirement => requirement.model_id === state.modelId).map(requirement => [esc(requirement.title),esc(ctx.hasDraft ? 'Uncalculated draft' : human(ctx.findings?.[requirement.id]?.status || 'not run')),'<button type="button" class="sd-button" data-ga-requirement="' + esc(requirement.id) + '">Inspect</button> <button type="button" class="sd-button" data-ga-investigate="' + esc(requirement.id) + '"' + (!ctx.runId || ctx.hasDraft ? ' disabled' : '') + '>Investigate</button>'])) : '') + '</section>';
      sample();
    }
    bindDisclosures(host,state.controller.signal);
    host.addEventListener('input', event => {
      if (!event.target.matches('[data-ga-slider]')) return;
      stop();state.index = Number(event.target.value);sample();
    },{signal:state.controller.signal});
    host.addEventListener('change', event => {
      if (!event.target.matches('[data-ga-model]')) return;
      state.modelId = event.target.value;render();
    },{signal:state.controller.signal});
    host.addEventListener('click', event => {
      const requirement = event.target.closest('[data-ga-requirement],[data-ga-investigate]');
      if (requirement && !requirement.disabled) { stop();ctx.onRequirement?.(requirement.dataset.gaRequirement || requirement.dataset.gaInvestigate,!!requirement.dataset.gaInvestigate);return; }
      const target = event.target.closest('[data-ga-action]');if (!target || target.disabled) return;
      const action = target.dataset.gaAction;
      const callbacks = {reference:ctx.onReference,author:ctx.onAuthor,inputs:()=>ctx.onInputs?.(state.modelId),run:ctx.onRun,report:ctx.onReport};
      if (callbacks[action]) { stop();callbacks[action]();return; }
      const saved = artifact();if (!saved) return;
      if (action === 'start' || action === 'end' || action.startsWith('cutoff-')) {
        stop();state.index = action === 'start' ? 0 : action === 'end' ? saved.samples.length-1 : saved.events.find(item => item.event === (action === 'cutoff-before' ? 'before_cutoff' : 'after_cutoff'))?.sample_index ?? 0;sample();return;
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
    render();
  }
  window.SixDGuidedAscent = Object.freeze({mount,unmount,evidence,report});
})();
