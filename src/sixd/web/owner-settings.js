/* Owner-only controls; server enforcement is separate from this presentation. */
(() => {
  'use strict';
  let current=null;
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money=v=>typeof v==='number'&&Number.isFinite(v)?'$'+v.toFixed(4):'Unavailable';
  const button=(name,label)=>'<button type="button" class="sd-button" data-owner-action="'+name+'">'+label+'</button>';
  function unmount(){if(current){current.closed=true;clearTimeout(current.timer);current.controller.abort();current.host.onclick=null;current=null;}}
  function mount(host,ctx){
    unmount();const s={host,ctx,closed:false,data:null,history:null,ultra:null,error:'',busy:false,timer:null,controller:new AbortController()};current=s;
    const active=()=>current===s&&!s.closed;
    function render(){
      if(!active())return;
      const d=s.data,connection=d?.connection||{},budget=connection.budget||{},latest=s.ultra?.latest,score=s.ultra?.scorecard;
      const stateLabel=value=>value?.key_present?'Connected'+(value.key_remembered?' · remembered':''):'Not connected';
      const rows=s.history?.latest_comparison?.candidate_results||[];
      const history=rows.length?'<details class="sd-owner-disclosure"><summary>Historical model comparison · '+esc(s.history.latest_comparison.created_at?.slice(0,10)||'earlier run')+'</summary><p>These are the outcomes of that dated run, not the current model availability or a general ranking. Untested cases did not fail.</p><div class="sd-table-wrap"><table class="sd-table"><thead><tr><th>Model</th><th>Attempted</th><th>Completed</th><th>Workflow passes</th><th>Failed / blocked</th><th>Not run</th></tr></thead><tbody>'+rows.map(r=>'<tr><th>'+esc(r.name)+'</th><td>'+esc(r.attempted??'Not recorded')+'</td><td>'+esc(r.completed)+'</td><td>'+esc(r.workflow_passes)+'</td><td>'+esc(r.failed??'Not recorded')+'</td><td>'+esc(r.not_run??'Not recorded')+'</td></tr>').join('')+'</tbody></table></div><p>The old Ultra result was two completions, one blocked explanation and three untested cases. Its negation wording check was corrected; the original result remains unchanged.</p></details>':'';
      const fresh=score?'<div class="sd-owner-score"><strong>'+esc(score.workflow_passes??0)+' / '+esc(score.planned??6)+' workflow passes</strong><p>'+esc(score.completed??0)+' completed · '+esc(score.failed??0)+' failed/blocked · '+esc(score.not_run??0)+' not run.</p></div>':'<p>No fresh six-case result is recorded yet.</p>';
      const cases=Array.isArray(score?.cases)?score.cases:Array.isArray(score?.rows)?score.rows:[];
      host.innerHTML='<article id="sd-owner-settings" class="sd-owner-page"><header><span class="sd-label">Owner workspace</span><h2>Connections, usage and verification</h2><p>Manage development services here. These controls are unavailable in the hosted reviewer workspace.</p></header>'+
        (s.error?'<p class="sd-error" role="alert">'+esc(s.error)+'</p>':'')+
        '<section><h3>Service connections</h3><div class="sd-owner-connections">'+[
          ['Nebius',stateLabel(connection),button('nebius','Manage Nebius connection')],
          ['Tavily',stateLabel(d?.research),button('tavily','Manage Tavily connection')],
          ['LangSmith',stateLabel(d?.observability),button('quality','Manage LangSmith connection')]
        ].map(([name,state,action])=>'<div class="sd-owner-connection"><strong>'+name+'</strong><span>'+esc(state)+'</span>'+action+'</div>').join('')+'</div><p>Opening settings, selecting models and connecting keys make no inference calls, searches or uploads.</p></section>'+
        '<section class="sd-owner-accounting"><h3>Development usage</h3><p>This is the approved application allowance, not your provider wallet or a bill.</p><dl class="sd-details-grid"><dt>Approved cumulative allowance</dt><dd>'+money(budget.cap_usd)+'</dd><dt>Conservative reservations</dt><dd>'+money(budget.reserved_usd)+'</dd><dt>Remaining reservation capacity</dt><dd>'+money(budget.remaining_usd)+'</dd></dl></section>'+
        '<section><h3>Fresh Ultra workflow check</h3><p>Six independent constructed cases using the current application. This does not rewrite the historical comparison, change the default model or establish aerospace validity.</p>'+fresh+
        (latest?'<p>Run: '+esc(latest.state)+' · '+esc(latest.created_at?.slice(0,10)||'')+(latest.current_sources_match===false?' · Earlier source version':'')+'</p>':'')+
        (cases.length?'<ul>'+cases.map(row=>'<li>'+esc(row.title||row.case_id||row.id)+' · '+esc(row.state||row.status||'')+'</li>').join('')+'</ul>':'')+
        '<details class="sd-owner-disclosure"><summary>Run settings and explicit approval</summary><p>Up to $2.10 and 36 request reservations inside the existing cumulative allowance; six cases, no automatic retry or default-model change.</p><label class="sd-owner-approval"><input type="checkbox" data-owner-ultra-approve> I approve this bounded live check using the connected Nebius account.</label>'+button('ultra-start','Run six Ultra checks')+'</details>'+button('refresh','Refresh owner status')+'</section>'+history+
        '<details class="sd-owner-disclosure"><summary>Recent investigation diagnostics</summary><p>Details for the investigation history most recently opened in this browser.</p>'+(ctx.records||[]).map(r=>'<p class="sd-receipt">'+esc(r.model)+' · '+esc(r.state)+' · '+esc(r.request_reservations??r.request_attempts??0)+' requests · '+money(r.reserved_usd)+' reserved · '+esc(r.investigation_id)+'</p>').join('')+button('quality','Open qualification and metrics tools')+'</details></article>';
      host.querySelectorAll('button').forEach(b=>b.disabled=s.busy);
      const start=host.querySelector('[data-owner-action="ultra-start"]');if(start)start.disabled=s.busy||!connection.key_present||['queued','running'].includes(latest?.state);
    }
    async function load(){
      if(!active()||s.busy)return;s.busy=true;
      try{const values=await Promise.all([ctx.api('/api/ai-quality/status',undefined,{signal:s.controller.signal}),ctx.api('/api/model-evaluation/status',undefined,{signal:s.controller.signal}),ctx.api('/api/ultra-workflow/status',undefined,{signal:s.controller.signal})]);if(!active())return;[s.data,s.history,s.ultra]=values;s.error='';}
      catch(error){if(active()&&error.name!=='AbortError')s.error=error.message;}
      finally{if(active()){s.busy=false;render();clearTimeout(s.timer);if(['queued','running'].includes(s.ultra?.latest?.state))s.timer=setTimeout(()=>void load(),1200);}}
    }
    host.onclick=async event=>{
      const b=event.target.closest('[data-owner-action]');if(!b||b.disabled||!active())return;
      const action=b.dataset.ownerAction;
      if(action==='nebius'){ctx.onNebius?.();return;}if(action==='tavily'){ctx.onTavily?.();return;}if(action==='quality'){ctx.onNavigate?.('ai-quality');return;}
      if(action==='refresh'){void load();return;}
      if(action==='ultra-start'){
        if(!host.querySelector('[data-owner-ultra-approve]')?.checked){s.error='Approve the stated ceiling before starting this live check.';render();return;}
        s.busy=true;s.error='';render();
        try{await ctx.api('/api/ultra-workflow/start',{allow_spend:true,allowance_usd:2.10});}
        catch(error){s.error=error.message;}
        finally{if(active()){s.busy=false;await load();}}
      }
    };
    render();void load();return unmount;
  }
  window.SixDOwnerSettings={mount,unmount};
})();
