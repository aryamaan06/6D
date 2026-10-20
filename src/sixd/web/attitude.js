/* Saved single-axis control evidence. No browser physics or inference. */
(() => {
  'use strict';
  let mounted=null;
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const finite=v=>typeof v==='number'&&Number.isFinite(v)&&(!Number.isInteger(v)||Number.isSafeInteger(v));
  const exact=v=>finite(v)?String(v):'Value outside browser exact-number range';
  const short=v=>finite(v)?Number(v.toPrecision(4)).toString():'—';
  const human=v=>String(v).replace(/_/g,' ').replace(/^./,c=>c.toUpperCase());
  const labels={final_error:'Final absolute error',final_rate:'Final absolute rate',max_sampled_error:'Full-run maximum sampled absolute error',max_sampled_rate:'Full-run maximum sampled absolute rate',max_assessed_error:'Assessment-window maximum sampled absolute error',max_assessed_rate:'Assessment-window maximum sampled absolute rate',max_sampled_command_torque:'Maximum sampled requested torque magnitude',max_sampled_applied_torque:'Maximum sampled applied torque magnitude',sampled_saturation_fraction:'Fraction of saved samples with clipped command'};
  const list=rows=>'<ul>'+rows.map(s=>'<li>'+esc(s)+'</li>').join('')+'</ul>';
  function table(headers,rows){return '<div class="ac-table-wrap"><table class="sd-table"><thead><tr>'+headers.map(h=>'<th scope="col">'+esc(h)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(c=>'<td>'+c+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';}
  function plot(a,series,unit,title){
    const rows=a.samples,values=rows.flatMap(r=>series.map(s=>r[s.key]));
    if(!values.every(finite)||!rows.every(r=>finite(r.time_s))||!finite(a.parameters.duration))return '<p class="sd-notice">Plot unavailable at this numerical scale; inspect the saved JSON evidence.</p>';
    let min=Math.min(0,...values),max=Math.max(0,...values);
    const span=max-min||1;min-=span*.08;max+=span*.08;
    const x=t=>62+450*(t/a.parameters.duration),y=v=>185-150*((v-min)/(max-min));
    const paths=series.map(s=>'<path d="'+rows.map((r,i)=>(i?'L':'M')+x(r.time_s).toFixed(3)+','+y(r[s.key]).toFixed(3)).join(' ')+'" fill="none" stroke="'+s.color+'" stroke-width="1.7" '+(s.dash?'stroke-dasharray="5 3"':'')+'/>').join('');
    return '<figure class="ac-figure"><figcaption>'+esc(title)+' · '+esc(unit)+'</figcaption><svg class="ac-chart" role="img" aria-label="'+esc(title+' in '+unit+' versus time in seconds; saved samples')+'" viewBox="0 0 540 230"><rect x="'+x(a.parameters.assessment_start)+'" y="35" width="'+(512-x(a.parameters.assessment_start))+'" height="150" fill="#eef3fb"/><path d="M62 35V185H512" fill="none" stroke="#c8d0db"/><path d="M62 '+y(0)+'H512" stroke="#d8dee8" stroke-dasharray="3 3"/>'+paths+'<text x="56" y="40" text-anchor="end">'+esc(short(max))+'</text><text x="56" y="185" text-anchor="end">'+esc(short(min))+'</text><text x="62" y="207">0</text><text x="512" y="207" text-anchor="end">'+esc(short(a.parameters.duration))+' s</text><text x="285" y="225" text-anchor="middle">Time · saved samples</text></svg><div class="ac-legend">'+series.map(s=>'<span><i style="background:'+s.color+'"></i>'+esc(s.label)+'</span>').join('')+'<span>Shaded: declared assessment window</span></div></figure>';
  }
  function sampleTable(rows){return table(['Time · s','Signed error · rad','Rate · rad/s','Requested · N*m','Applied · N*m','Clipped?'],rows.map(r=>[exact(r.time_s),exact(r.error_rad),exact(r.rate_rad_s),exact(r.command_torque_nm),exact(r.applied_torque_nm),r.saturated?'Yes':'No'].map(esc)));}
  function report(result,ctx={}){
    const heading='<h3>Single-axis pointing response</h3>';
    if(ctx.hasDraft)return '<section class="ac-evidence" data-attitude-evidence="'+esc(ctx.modelId)+'">'+heading+'<p class="sd-notice">This draft has no calculated response. Save a revision and run checks. Earlier results are not draft predictions.</p></section>';
    if(!result)return '<section class="ac-evidence" data-attitude-evidence="'+esc(ctx.modelId)+'">'+heading+'<p>No current response for this saved revision. Run checks; historical reviews remain in revision history.</p></section>';
    const a=result.attitude_response;
    if(result.status!=='completed'||!a)return '<section class="ac-evidence" data-attitude-evidence="'+esc(ctx.modelId)+'">'+heading+'<p class="sd-notice">No completed pointing response. This calculation gap is not a failed spacecraft.</p>'+list(result.issues||[])+'</section>';
    const first=a.samples.find(r=>r.time_s>=a.parameters.assessment_start),indices=[0,a.samples.indexOf(first),a.samples.length-1],witnesses=[...new Set(indices)].map(i=>a.samples[i]);
    const d=a.diagnostics;
    return '<section class="ac-evidence" data-attitude-evidence="'+esc(ctx.modelId||result.model_id)+'">'+heading+'<p>Fixed target, one rigid principal axis and continuous PD feedback. Requested torque is clipped by the supplied actuator limit; a separate constant disturbance is then applied.</p><p class="ac-note">Signed error = target − unwrapped angle. No shortest-path angle wrapping. Lines join recorded samples for readability; they do not prove behavior between samples.</p>'+table(['Calculated metric','Saved value','Unit'],Object.entries(result.metrics).map(([key,v])=>[esc(labels[key]||human(key)),esc(exact(v.value)),esc(v.unit)]))+
      '<div class="ac-charts">'+plot(a,[{key:'error_rad',label:'Signed pointing error',color:'#4b67ac'}],'rad','Pointing error')+plot(a,[{key:'rate_rad_s',label:'Signed angular rate',color:'#427f6e'}],'rad/s','Angular rate')+plot(a,[{key:'command_torque_nm',label:'Requested',color:'#b37c3d',dash:true},{key:'applied_torque_nm',label:'Applied actuator',color:'#7860a1'}],'N*m','Requested and applied torque')+'</div>'+
      '<p class="ac-note">Actuator limit: ±'+esc(exact(a.parameters.max_torque))+' N*m. Constant disturbance: '+esc(exact(a.parameters.disturbance_torque))+' N*m. Saturation marks command clipping only, not wheel momentum saturation or a requirement failure by itself.</p>'+
      '<h4>Numerical agreement and assessment window</h4><p>Maximum common-time grid differences: '+esc(exact(d.max_grid_error_difference_rad))+' rad and '+esc(exact(d.max_grid_rate_difference_rad_s))+' rad/s, against supplied tolerances '+esc(exact(a.parameters.angle_numerical_tolerance))+' rad and '+esc(exact(a.parameters.rate_numerical_tolerance))+' rad/s.</p><p class="ac-note">'+esc(d.label)+' Final error does not establish settling. Criterion findings compare recorded values, so near-limit conclusions need finer resolution and independent review.</p><p>Assessment requested from '+esc(exact(a.parameters.assessment_start))+' s to '+esc(exact(a.parameters.duration))+' s. First included sample: '+esc(exact(d.assessment_first_sample_s))+' s; '+esc(d.assessment_sample_count)+' recorded samples in the window.</p>'+
      '<h4>First, assessment-start and final samples</h4>'+sampleTable(witnesses)+'<p class="ac-note">Full '+esc(a.samples.length)+'-sample history is retained in the evidence JSON. These rows are selected witnesses, not the entire response.</p>'+
      '<details class="ac-disclosure"><summary>Assumptions, excluded effects and saved provenance</summary><h4>Assumptions</h4>'+list(a.assumptions)+'<h4>Not assessed</h4>'+list(a.not_assessed)+'<p class="sd-receipt">Project '+esc(ctx.projectId)+' · R'+esc(ctx.revision)+' · Model '+esc(ctx.modelId||result.model_id)+'<br>Run '+esc(ctx.runId)+'<br>Review '+esc(ctx.reviewDigest)+'<br>Evidence '+esc(result.evidence_fingerprint)+'<br>Solver source '+esc(a.source_fingerprint)+'</p>'+(ctx.origin?'<p class="sd-receipt">'+esc(human(ctx.origin.disposition))+' · origin R'+esc(ctx.origin.revision)+' · '+esc(ctx.origin.run_id)+'</p>':'')+'<h4>Recorded input records</h4><pre>'+esc(JSON.stringify(result.inputs||a.parameters,null,2))+'</pre><h4>Solver and verification sources</h4><pre>'+esc(JSON.stringify({solver:a.solver,sources:result.verification_sources},null,2))+'</pre></details></section>';
  }
  function unmount(){if(mounted){mounted.host.onclick=null;mounted.host.oninput=null;mounted=null;}}
  function mount(host,ctx){
    unmount();const session={host};mounted=session;
    const models=(ctx.project.models||[]).filter(m=>m.type==='attitude_control');
    const button=(action,label,disabled=false)=>'<button type="button" class="sd-button" data-ac="'+esc(action)+'" '+(disabled?'disabled':'')+'>'+esc(label)+'</button>';
    host.innerHTML='<article class="ac-workspace"><div class="ac-intro"><span class="sd-label">Guidance & control · bounded pointing model</span><h2>Follow the pointing response.</h2><p>Review how a declared single-axis controller turns toward a fixed target, responds to a constant disturbance and reaches its torque limit.</p><p class="ac-note">This capability models ideal attitude control. Navigation, full three-axis behavior, hardware actuator dynamics and rocket landing remain unassessed.</p><div class="ac-actions">'+button('reference','Open constructed reference',!!ctx.hasDraft)+button('author','Author inputs, model and requirements')+button('run','Run saved checks',ctx.hasDraft||!ctx.project.models?.length||!ctx.project.requirements?.length)+button('report','Open full report')+'</div></div>'+
      (!models.length?'<div class="ac-empty"><h3>No single-axis pointing model is defined.</h3><p>Open the separate constructed reference, or use Author project to bind sourced SI inputs to Single-axis spacecraft pointing and declare its requirements. Existing unsupported control requirements remain unassessed.</p></div>':'')+
      models.map(m=>'<section class="ac-model" data-attitude-model="'+esc(m.id)+'"><h3>'+esc(human(m.id))+'</h3><p>'+esc(m.description||'')+'</p><div class="ac-actions">'+button('inputs:'+m.id,'Inspect or edit inputs')+'</div>'+report(ctx.modelResults[m.id],{...ctx,modelId:m.id,origin:ctx.modelOrigins?.[m.id]})+
        '<h4>Linked requirements</h4>'+(ctx.project.requirements||[]).filter(r=>r.model_id===m.id).map(r=>'<div class="ac-requirement"><strong>'+esc(r.title)+'</strong><span>'+esc(ctx.hasDraft?'Draft · not calculated':ctx.findings?.[r.id]?.status?.replace(/_/g,' ')||'Awaiting checks')+'</span>'+button('requirement:'+r.id,'Inspect finding')+button('investigate:'+r.id,'Investigate',ctx.hasDraft||!ctx.runId)+'</div>').join('')+'</section>').join('')+'</article>';
    host.onclick=event=>{
      const el=event.target.closest('[data-ac]');if(!el||el.disabled||mounted!==session)return;
      const [action,id]=el.dataset.ac.split(':');
      if(action==='reference')ctx.onReference?.();
      else if(action==='author')ctx.onAuthor?.();
      else if(action==='run')ctx.onRun?.();
      else if(action==='report')ctx.onReport?.();
      else if(action==='inputs')ctx.onInputs?.(id);
      else if(action==='requirement'||action==='investigate')ctx.onRequirement?.(id,action==='investigate');
    };
  }
  window.SixDAttitude=Object.freeze({mount,unmount,report});
})();
