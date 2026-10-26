/* Playback of retained vertical-flight samples. No browser physics. */
(() => {
  'use strict';
  let active=null;
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const human=v=>String(v??'').replace(/_/g,' ');
  const unit=v=>window.SixDUnits.format(v);
  const short=v=>window.SixDUnits.number(v);
  const value=(v,u='')=>window.SixDUnits.value(v,u);
  const table=(headers,rows)=>'<div class="pf-table" tabindex="0"><table class="sd-table"><thead><tr>'+headers.map(x=>'<th scope="col">'+esc(x)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map(x=>'<td>'+x+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';
  const list=rows=>'<ul>'+rows.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>';
  const button=(action,title,disabled=false)=>'<button type="button" class="sd-button" data-pf-action="'+action+'" '+(disabled?'disabled':'')+'>'+esc(title)+'</button>';
  const charts=[['Altitude','m',[['altitude_m','Altitude','#5267aa']]],['Vertical velocity','m/s',[['velocity_m_s','Signed velocity','#397c70']]],['Remaining mass','kg',[['mass_kg','Mass','#8a689d']]],['Dynamic pressure','Pa',[['dynamic_pressure_pa','Dynamic pressure','#ac793f']]],['Upward acceleration','m/s²',[['acceleration_m_s2','Signed acceleration','#a35767']]],['Forces','N',[['thrust_n','Thrust','#5267aa'],['drag_n','Signed drag','#ac793f']]]];
  function chart(a,title,units,series){
    const rows=a.samples,indices=new Set([0,rows.length-1,...a.events.map(e=>e.sample_index)]);
    const stride=Math.max(1,Math.ceil(rows.length/600));for(let i=0;i<rows.length;i+=stride)indices.add(i);
    const shown=[...indices].sort((a,b)=>a-b).map(i=>rows[i]);
    let low=0,high=0;for(const r of rows)for(const [key] of series){low=Math.min(low,r[key]);high=Math.max(high,r[key]);}
    const pad=(high-low||1)*.07;low-=pad;high+=pad;
    const end=rows.at(-1).time_s,x=t=>65+440*t/end,y=v=>183-145*(v-low)/(high-low);
    const paths=series.map(([key,label,color])=>'<path d="'+shown.map((r,i)=>(i?'L':'M')+x(r.time_s).toFixed(2)+','+y(r[key]).toFixed(2)).join(' ')+'" fill="none" stroke="'+color+'" stroke-width="1.8"/>').join('');
    const burnout=a.events.find(e=>e.event==='before_cutoff').time_s;
    return '<figure class="pf-chart"><figcaption>'+esc(title)+' · '+esc(units)+'</figcaption><svg viewBox="0 0 540 225" role="img" aria-label="'+esc(title+' against time, saved samples with burnout marker')+'"><path d="M65 38V183H505" fill="none" stroke="#cbd0d8"/><path d="M'+x(burnout)+' 38V183" stroke="#969aa3" stroke-dasharray="4 4"/>'+paths+'<line data-pf-cursor x1="65" x2="65" y1="38" y2="183" stroke="#262b35" stroke-opacity=".5"/><text x="60" y="42" text-anchor="end">'+short(high)+'</text><text x="60" y="183" text-anchor="end">'+short(low)+'</text><text x="65" y="204">0</text><text x="505" y="204" text-anchor="end">'+short(end)+' s</text></svg><div class="pf-legend">'+series.map(([,label,color])=>'<span><i style="background:'+color+'"></i>'+esc(label)+'</span>').join('')+'<span>Dashed: burnout</span></div></figure>';
  }
  function evidence(result,ctx={}){
    if(ctx.hasDraft)return '<p class="sd-notice">Draft changes have no calculated flight response. Save the revision and run checks.</p>';
    if(!result)return '<p class="sd-notice">No current flight calculation for this revision. Run checks to record its response.</p>';
    const a=result.flight_response;
    if(result.status!=='completed'||!a)return '<p class="sd-notice">Flight response unavailable. This model/input gap does not establish a failed vehicle.</p>'+list(result.issues||[]);
    const d=a.diagnostics;
    return '<p class="pf-diagnostic" data-pf-agreement="'+d.grid_agreement_met+'"><strong>'+ (d.grid_agreement_met?'Declared grid agreement met':'Diagnostic result · grid agreement not met')+'</strong><br>'+esc(d.reason)+'</p>'+table(['Saved metric','Value','Unit','Numerical allowance'],Object.entries(result.metrics).map(([name,q])=>[esc(human(name)),value(q.value),esc(unit(q.unit)),value(d.metric_allowances[name])]))+
      '<p class="pf-note">Values use compact display precision; exact metrics and diagnostics are available below. Allowances combine declared state tolerances and observed grid differences. They are not proven error bounds. Extrema cover saved samples; lines join selected samples for readability.</p><div class="pf-charts">'+charts.map(([title,units,series])=>chart(a,title,units,series)).join('')+'</div>'+table(['Grid pair · steps/segment','Maximum altitude difference · m','Maximum velocity difference · m/s'],d.level_differences.map(row=>[row.coarse_steps+' → '+row.fine_steps,value(row.max_altitude_difference_m),value(row.max_velocity_difference_m_s)]))+
      '<details class="sd-source" data-preserve-notation><summary>Exact saved metrics and numerical diagnostics</summary><pre>'+esc(JSON.stringify({metrics:result.metrics,diagnostics:d},null,2))+'</pre></details>'+
      '<details class="sd-source"><summary>Inputs, method and retained sample events</summary><p>Classical RK4, order 4; analytical mass depletion. Burn and coast have separate grids, joined at exact fuel exhaustion. '+esc(a.samples.length)+' fine-grid samples retained; intermediate grids remain in JSON.</p>'+table(['Parameter','Supplied value'],Object.entries(a.parameters).map(([key,v])=>[esc(human(key)),esc(v)]))+table(['Event','Sample index','Time · s'],a.events.map(e=>[esc(human(e.event)),e.sample_index,esc(e.time_s)]))+'</details><details class="sd-source"><summary>Assumptions and exclusions</summary><h4>Assumptions</h4>'+list(a.assumptions)+'<h4>Not assessed</h4>'+list(a.not_assessed)+'</details><p class="sd-receipt">Project '+esc(ctx.projectId)+' · revision R'+esc(ctx.revision)+'<br>Run '+esc(ctx.runId)+'<br>Review '+esc(ctx.reviewDigest)+'<br>Solver SHA-256 '+esc(a.source_fingerprint)+(ctx.origin?'<br>'+esc(human(ctx.origin.disposition))+' from R'+esc(ctx.origin.revision)+' · '+esc(ctx.origin.run_id):'')+'</p>';
  }
  function report(result,ctx={}){return '<section class="pf-evidence" data-powered-flight-evidence="'+esc(ctx.modelId||result?.model_id)+'"><h3>Powered vertical-flight evidence</h3>'+evidence(result,ctx)+'</section>';}
  function unmount(){if(active){active.controller.abort();cancelAnimationFrame(active.frame);active=null;}}
  function mount(host,ctx){
    unmount();const state={host,ctx,controller:new AbortController(),frame:0,index:0,playing:false};active=state;
    const models=(ctx.project?.models||[]).filter(m=>m.type==='powered_flight');
    state.modelId=models[0]?.id;
    function stop(){state.playing=false;cancelAnimationFrame(state.frame);const b=host.querySelector('[data-pf-action="play"]');if(b)b.textContent='Play';}
    function sample(){
      const a=ctx.hasDraft?null:ctx.modelResults?.[state.modelId]?.flight_response;if(!a)return;
      const row=a.samples[state.index];host.querySelector('[data-pf-slider]').value=state.index;
      const y=260-220*row.altitude_m/Math.max(1,...a.samples.map(r=>r.altitude_m));
      host.querySelector('[data-pf-vehicle]').setAttribute('transform','translate(90 '+y+')');
      host.querySelector('[data-pf-sample]').textContent='Sample '+state.index+' / '+(a.samples.length-1)+' · '+short(row.time_s)+' s · '+human(row.event||row.phase);
      host.querySelector('[data-pf-state]').innerHTML=table(['Quantity','Saved value'],[['Altitude',row.altitude_m,'m'],['Vertical velocity',row.velocity_m_s,'m/s'],['Mass',row.mass_kg,'kg'],['Thrust',row.thrust_n,'N'],['Signed drag',row.drag_n,'N'],['Gravity',row.gravity_m_s2,'m/s²'],['Upward acceleration',row.acceleration_m_s2,'m/s²']].map(([key,v,u])=>[key,value(v,u)]))+'<details class="sd-source" data-preserve-notation><summary>Exact recorded sample</summary><pre>'+esc(JSON.stringify(row,null,2))+'</pre></details>';
      const x=65+440*row.time_s/a.samples.at(-1).time_s;
      for(const line of host.querySelectorAll('[data-pf-cursor]')){line.setAttribute('x1',x);line.setAttribute('x2',x);}
    }
    function render(){
      stop();state.index=0;const result=ctx.modelResults?.[state.modelId],a=!ctx.hasDraft&&result?.status==='completed'?result.flight_response:null;
      host.innerHTML='<section class="pf-page"><p class="sd-label">Saved R'+esc(ctx.revision)+' · bounded vertical ascent</p><h2>Follow the flight through burnout.</h2><p class="sd-lead">Inspect recorded altitude, velocity, mass and forces through a constant-thrust burn and above-surface coast.</p><div class="sd-action-row">'+button('reference','Use constructed flight reference',!!ctx.hasDraft)+button('author','Author project')+(models.length?button('inputs','Edit flight inputs')+button('run','Run checks',!!ctx.hasDraft)+button('report','Open full report',!ctx.runId||!!ctx.hasDraft):'')+'</div>'+(!models.length?'<div class="sd-notice">This project has no powered-flight model. Choose the constructed reference to try this bounded calculation, or add a powered vertical-flight model through Author project. Creating a template is explicit; no existing project is overwritten.</div>':'<label class="pf-select">Flight model <select data-pf-model>'+models.map(m=>'<option value="'+esc(m.id)+'" '+(m.id===state.modelId?'selected':'')+'>'+esc(m.id)+'</option>').join('')+'</select></label>')+
        (a?'<section class="pf-playback" aria-label="Saved vertical flight playback"><div class="pf-path"><svg viewBox="0 0 180 300" role="img" aria-label="Recorded altitude above launch surface, vertical axis only"><line x1="90" x2="90" y1="35" y2="260" stroke="#cbd0d8" stroke-dasharray="4 4"/><path d="M25 260H155" stroke="#9a9f89" stroke-width="3"/><text x="90" y="290" text-anchor="middle">Launch surface</text><text x="90" y="20" text-anchor="middle">'+esc(short(Math.max(...a.samples.map(r=>r.altitude_m))))+' m</text><g data-pf-vehicle><path d="M0 -13L8 9H-8Z" fill="#5267aa"/><circle r="3" fill="white"/></g></svg><p class="pf-note">Vertical position only. Shape is a marker, not vehicle geometry.</p></div><div><p data-pf-sample></p><div class="sd-action-row">'+button('play','Play')+button('cutoff-before','Before cutoff')+button('cutoff-after','After cutoff',!a.parameters.coast_duration)+'</div><label class="pf-scrub">Recorded sample <input data-pf-slider type="range" min="0" max="'+(a.samples.length-1)+'" step="1" value="0" aria-label="Recorded flight sample"></label><div data-pf-state></div></div></section>':'')+
        (models.length?evidence(result,{...ctx,modelId:state.modelId,origin:ctx.modelOrigins?.[state.modelId]}):'')+
        (models.length?'<h3>Declared requirements</h3>'+table(['Requirement','Finding','Actions'],(ctx.project.requirements||[]).filter(r=>r.model_id===state.modelId).map(r=>[esc(r.title),esc(ctx.hasDraft?'Uncalculated draft':human(ctx.findings?.[r.id]?.status||'not run')),'<button class="sd-button" data-pf-requirement="'+esc(r.id)+'">Inspect</button> <button class="sd-button" data-pf-investigate="'+esc(r.id)+'" '+(!ctx.runId||ctx.hasDraft?'disabled':'')+'>Investigate</button>'])):'')+'</section>';
      sample();
    }
    host.addEventListener('input',e=>{if(e.target.matches('[data-pf-slider]')){stop();state.index=Number(e.target.value);sample();}},{signal:state.controller.signal});
    host.addEventListener('change',e=>{if(e.target.matches('[data-pf-model]')){state.modelId=e.target.value;render();}},{signal:state.controller.signal});
    host.addEventListener('click',e=>{
      const req=e.target.closest('[data-pf-requirement],[data-pf-investigate]');if(req){ctx.onRequirement?.(req.dataset.pfRequirement||req.dataset.pfInvestigate,!!req.dataset.pfInvestigate);return;}
      const b=e.target.closest('[data-pf-action]');if(!b||b.disabled)return;const action=b.dataset.pfAction;
      const callbacks={reference:ctx.onReference,author:ctx.onAuthor,inputs:()=>ctx.onInputs?.(state.modelId),run:ctx.onRun,report:ctx.onReport};
      if(callbacks[action]){callbacks[action]();return;}
      const a=ctx.modelResults?.[state.modelId]?.flight_response;if(!a)return;
      if(action.startsWith('cutoff-')){stop();state.index=a.events.find(x=>x.event===(action==='cutoff-before'?'before_cutoff':'after_cutoff'))?.sample_index||0;sample();}
      if(action==='play'){
        if(state.playing){stop();return;}if(state.index===a.samples.length-1)state.index=0;
        state.playing=true;b.textContent='Pause';let previous=performance.now(),time=a.samples[state.index].time_s;
        const tick=now=>{if(active!==state||!state.playing)return;time+=(now-previous)/1000*a.samples.at(-1).time_s/12;previous=now;while(state.index<a.samples.length-1&&a.samples[state.index+1].time_s<=time)state.index++;sample();if(state.index===a.samples.length-1)stop();else state.frame=requestAnimationFrame(tick);};state.frame=requestAnimationFrame(tick);
      }
    },{signal:state.controller.signal});render();
  }
  window.SixDPoweredFlight={mount,unmount,report};
})();
