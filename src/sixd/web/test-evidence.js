/* Read-only projections of immutable test comparisons. This module never fetches,
   recalculates, alters verdicts or starts an investigation. */
(() => {
  'use strict';
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const array=value=>Array.isArray(value)?value:[];
  const labels={
    met:'Meets recorded criterion',not_met:'Does not meet recorded criterion',not_assessed:'Not assessed',
    within_tolerance:'Within supplied tolerance',outside_tolerance:'Outside supplied tolerance',
    exact_baseline:'Exact reviewed baseline',same_dependencies:'Dependencies unchanged',
    needs_review:'Applicability needs review',requirement_removed:'Requirement removed',unmapped:'Unmapped requirement'
  };
  const known=new Set(Object.keys(labels));
  const badge=(status,prefix='')=>'<span class="te-badge te-'+(known.has(status)?status:'unknown')+'">'+esc(prefix+(labels[status]||'Unknown status'))+'</span>';
  function numeric(value){
    if(typeof value!=='number'||!Number.isFinite(value))return 'Not available';
    if(Number.isInteger(value)&&!Number.isSafeInteger(value))return 'Outside browser exact-integer range';
    return window.SixDUnits?.number(value)??String(value);
  }
  function measure(record){
    if(!record||typeof record.value!=='number'||!Number.isFinite(record.value)||typeof record.unit!=='string'||!record.unit)return 'No usable numeric record';
    return esc(numeric(record.value)+' '+record.unit);
  }
  const list=items=>'<ul>'+array(items).map(item=>'<li>'+esc(item)+'</li>').join('')+'</ul>';
  const identity=(label,value)=>'<div><dt>'+esc(label)+'</dt><dd>'+esc(value||'Not available')+'</dd></div>';
  const relation=value=>({declared_match:'Declared matching definition and conditions',different:'Definition or conditions differ',unknown:'Definition or conditions match unknown'}[value]||'No matching-conditions declaration');
  function origin(comparison){
    return comparison.data_kind==='synthetic'?'Synthetic / constructed data':comparison.data_kind==='measured'?'Supplied measurements · authenticity not verified':'Data origin not declared';
  }
  function isApplicable(comparison,row,profile,hasDraft,currentRunFresh=true){
    return !hasDraft&&currentRunFresh!==false&&profile.context==='saved'&&!!profile.current_run_id&&comparison.source_current===true&&
      ['exact_baseline','same_dependencies'].includes(row.applicability?.status);
  }
  function scopeMessage(comparison,row,profile,hasDraft){
    const status=row.applicability?.status;
    if(hasDraft||profile.context==='draft')return 'Draft applicability preview only. Recorded measurements, predictions and criteria still belong to saved R'+comparison.tested_revision+'; no draft result has been calculated or tested.';
    if(comparison.source_current!==true)return 'The recorded comparison uses sources that are no longer current or cannot be confirmed. Its original outcomes are preserved; they do not establish current evidence.';
    if(status==='exact_baseline')return 'Linked to this exact saved review. These remain supplied observations under their original conditions declaration.';
    if(status==='same_dependencies')return 'The linked requirement and model dependencies are unchanged. This is the original test comparison from R'+comparison.tested_revision+', with applicability inferred from recorded dependencies; it is not a repeated physical test.';
    if(status==='requirement_removed')return 'This requirement is absent from the selected configuration. The original comparison is retained as historical evidence.';
    if(status==='unmapped')return 'This row has no applicable requirement mapping. It cannot supply an assessed finding for this configuration.';
    return 'The linked configuration or evidence has changed. Review applicability before relying on this historical test comparison; original outcomes have not been recalculated.';
  }
  function provenance(comparison,row,profile){
    const conditions=row.conditions||{},applicability=row.applicability||{};
    return '<details class="te-provenance sd-source"><summary>Exact records, conditions and applicability</summary>'+
      '<dl class="te-identities">'+identity('Project / selected revision',profile.project_id+' / R'+profile.revision)+
      identity('Selected project digest',profile.project_digest)+identity('Current review run',profile.current_run_id)+identity('Current review digest',profile.current_review_digest)+
      identity('Test comparison',comparison.comparison_id)+identity('Comparison receipt digest',comparison.receipt_digest)+
      identity('Tested revision','R'+comparison.tested_revision)+identity('Original baseline run',comparison.baseline_run_id)+
      identity('Original baseline review digest',comparison.baseline_review_digest)+identity('CSV source',comparison.filename)+
      identity('CSV SHA-256',comparison.csv_sha256)+identity('Measurement / CSV row',(row.measurement_id||'Missing ID')+' / '+row.row_number)+
      identity('Requirement / model',(row.requirement_id||'Unmapped')+' / '+(row.model_id||'Unmapped'))+
      identity('Observable',row.metric)+identity('Data source declaration',comparison.source)+
      identity('Conditions',conditions.description||comparison.test_conditions)+identity('Condition relation',relation(conditions.declared_relation||comparison.conditions_match))+
      identity('Condition verification',conditions.verified===true?'Recorded as verified':'User declaration; not independently verified')+
      identity('Comparison sources',comparison.source_current===true?'Current source hashes match':'Current source identity is not established')+
      identity('Dependency match',applicability.dependencies_match===true?'Recorded dependencies match':applicability.dependencies_match===false?'Recorded dependencies differ':'Not established')+
      '</dl>'+(array(applicability.changed_inputs).length?'<h5>Changed linked inputs</h5>'+list(applicability.changed_inputs):'')+
      (array(applicability.reasons).length?'<h5>Applicability basis</h5>'+list(applicability.reasons):'')+
      (Object.keys(profile.sources||{}).length?'<h5>Projection verification sources</h5><dl class="te-identities">'+Object.entries(profile.sources).map(([file,digest])=>identity(file,digest)).join('')+'</dl>':'')+
      '<p class="te-scope">Receipt digests are unsigned local integrity references. A source declaration does not authenticate physical testing.</p></details>';
  }
  function nextChecks(row){
    return '<section class="te-next"><h5>Engineering next checks</h5>'+
      (array(row.next_steps).length?'<ol>'+row.next_steps.map(step=>'<li>'+esc(step)+'</li>').join('')+'</ol>':'<p>Review the original test record, measurement definition, conditions, units and model assumptions with the responsible engineer before relying on this comparison.</p>')+
      (array(row.issues).length?'<h5>Recorded data issues</h5><ul>'+row.issues.map(issue=>'<li>'+esc(issue.field||'Row')+': '+esc(issue.message||'Unspecified recorded issue')+'</li>').join('')+'</ul>':'')+'</section>';
  }
  function rowCard(comparison,row,profile,options){
    const criterion=row.measurement_requirement||{},agreement=row.prediction_agreement||{},applicability=row.applicability||{};
    const hasDraft=!!options.hasDraft||profile.context==='draft';
    const scopedRequirement=!!row.requirement_id&&row.applicability?.status!=='requirement_removed'&&row.applicability?.status!=='unmapped';
    // A changed-dependency row can be investigated as historical evidence. It
    // must never be promoted to a current passing finding by this action.
    const canInvestigate=!hasDraft&&options.currentRunFresh!==false&&profile.context==='saved'&&!!profile.current_run_id&&comparison.source_current===true&&scopedRequirement&&
      ['exact_baseline','same_dependencies','needs_review'].includes(applicability.status);
    const reason=hasDraft?'Save or discard the draft before starting an investigation.':!profile.current_run_id||options.currentRunFresh===false?'A current saved review is required.':!canInvestigate?'Open the original comparison to inspect its historical scope and applicability.':'';
    const measured=measure(criterion.metric),tolerance=measure(agreement.tolerance),unit=criterion.metric?.unit||agreement.prediction?.unit||'';
    return '<article class="te-row" data-linked-test-row="'+esc(row.row_number)+'" data-linked-test-comparison="'+esc(comparison.comparison_id)+'">'+
      '<header class="te-row-heading"><div><strong>'+esc(row.measurement_id||'CSV row '+row.row_number)+'</strong><span>'+esc(row.title||row.requirement_id||'Unmapped requirement')+'</span></div>'+badge(applicability.status)+'</header>'+
      '<p class="te-context">'+esc(scopeMessage(comparison,row,profile,hasDraft))+'</p>'+
      '<p class="te-canonical">Original design prediction finding: '+badge(row.canonical_status)+'. This is the recorded baseline result, separate from the two supplied-data findings below.</p>'+
      '<div class="te-findings"><section><h5>Measurement meets requirement</h5>'+badge(criterion.status)+
      '<dl class="te-values"><dt>Recorded measurement</dt><dd>'+measured+'</dd><dt>Original own criterion</dt><dd>'+(criterion.limit?esc(criterion.operator)+' '+measure(criterion.limit):'No usable criterion')+'</dd></dl><p>'+esc(criterion.reason||'No recorded assessment reason.')+'</p></section>'+
      '<section><h5>Prediction agrees with measurement</h5>'+badge(agreement.status)+'<dl class="te-values"><dt>Saved prediction</dt><dd>'+measure(agreement.prediction)+'</dd><dt>Measured − predicted</dt><dd>'+esc(numeric(agreement.signed_difference)+(typeof agreement.signed_difference==='number'&&Number.isFinite(agreement.signed_difference)&&unit?' '+unit:''))+'</dd><dt>Absolute discrepancy</dt><dd>'+esc(numeric(agreement.absolute_difference)+(typeof agreement.absolute_difference==='number'&&Number.isFinite(agreement.absolute_difference)&&unit?' '+unit:''))+'</dd><dt>Supplied absolute tolerance</dt><dd>'+tolerance+'</dd></dl><p>'+esc(agreement.reason||'No recorded assessment reason.')+'</p></section></div>'+
      nextChecks(row)+'<div class="te-actions"><button type="button" class="sd-button" data-test-evidence-open="'+esc(comparison.comparison_id)+'" data-test-evidence-row="'+esc(row.row_number)+'">Open original comparison</button>'+
      '<button type="button" class="sd-button" data-test-evidence-investigate="'+esc(comparison.comparison_id)+'" data-test-evidence-row="'+esc(row.row_number)+'" data-test-evidence-requirement="'+esc(row.requirement_id)+'"'+(canInvestigate?'':' disabled')+(reason?' title="'+esc(reason)+'"':'')+'>Investigate comparison</button></div>'+
      (reason?'<p class="te-action-note">'+esc(reason)+'</p>':'<p class="te-action-note">Opens the Assistant with this recorded row selected. A paid investigation starts only when you explicitly request it.</p>')+
      provenance(comparison,row,profile)+'</article>';
  }
  function selectRows(profile,options){
    const variant=options.variant||'report';
    const ids=options.requirementId!==undefined?new Set([options.requirementId]):Array.isArray(options.requirementIds)?new Set(options.requirementIds):null;
    return array(profile.comparisons).map(comparison=>({comparison,rows:array(comparison.rows).filter(row=>variant==='changes'||ids===null||ids.has(row.requirement_id))})).filter(group=>group.rows.length);
  }
  function render(profile,options={}){
    if(!profile||profile.schema!=='sixd.test-evidence.v1')return unavailable('Test evidence has not been loaded for this configuration.');
    const variant=['inspector','report','changes','assistant'].includes(options.variant)?options.variant:'report';
    const groups=selectRows(profile,options),rows=groups.flatMap(group=>group.rows);
    const hasDraft=!!options.hasDraft||profile.context==='draft';
    const applicable=groups.reduce((n,group)=>n+group.rows.filter(row=>isApplicable(group.comparison,row,profile,hasDraft,options.currentRunFresh)).length,0);
    const title=variant==='changes'?'Test evidence affected by this configuration':variant==='assistant'?'Linked test evidence':'Test evidence and predictions';
    const bound=Number.isInteger(profile.history_limit)&&profile.history_limit>0?profile.history_limit:20;
    return '<section class="te-evidence te-'+variant+'" aria-label="'+esc(title)+'"><div class="te-heading"><h3>'+esc(title)+'</h3><span class="te-count">'+rows.length+' linked row'+(rows.length===1?'':'s')+'</span></div>'+
      '<p class="te-scope">Recorded observations retain their original tested revision, conditions and criterion. Measurement compliance and prediction agreement are separate findings; neither changes the canonical design finding.</p>'+
      (hasDraft?'<p class="te-draft">Draft dependency preview. No measurement, prediction or outcome below is a calculated result for this draft.</p>':'')+
      (rows.length?'<p class="te-summary">'+applicable+' row'+(applicable===1?'':'s')+' with a current saved review and matching recorded dependencies; '+(rows.length-applicable)+' requiring historical, unmapped or draft context. These counts are evidence links, not passing requirements.</p>':'<p class="te-empty">No linked test rows for '+(variant==='changes'?'this configuration':'the selected requirements')+' appear in the comparison history window. This does not mean physical testing passed or all test evidence has been supplied.</p>')+
      groups.map(({comparison,rows:linked})=>'<section class="te-comparison"><header class="te-comparison-heading"><h4>'+esc(comparison.name||'Saved test comparison')+'</h4><span>'+esc(origin(comparison))+'</span></header><p class="te-comparison-meta">Tested R'+esc(comparison.tested_revision)+' · '+esc(comparison.created_at)+' · '+esc(comparison.filename)+'</p>'+linked.map(row=>rowCard(comparison,row,profile,options)).join('')+'</section>').join('')+
      '<p class="te-history-note">History window: the latest '+esc(bound)+' comparisons at or before selected R'+esc(profile.revision)+'. '+(profile.history_truncated?'Older comparisons exist outside this projection; open Test data to inspect saved comparison history.':'This projection covers the returned comparison window only.')+' The comparison window is applied before requirement filtering.</p>'+
      '<details class="te-limitations sd-source"><summary>Scope, provenance and limits</summary>'+list(profile.limitations)+'<p>Conditions and data origin are supplied declarations. Applicability checks compare recorded dependencies; they do not validate calibration, physical representativeness, uncertainty or whole-mission readiness. Historical outcomes remain unchanged.</p><dl class="te-identities">'+identity('Project',profile.project_id)+identity('Selected revision','R'+profile.revision)+identity('Selected project digest',profile.project_digest)+identity('Current review run',profile.current_run_id)+identity('Projection context',profile.context)+'</dl></details></section>';
  }
  function unavailable(reason){return '<section class="te-evidence te-unavailable" aria-label="Test evidence unavailable"><h3>Test evidence</h3><p>'+esc(reason||'Unable to load the linked comparisons for this configuration.')+'</p><p class="te-scope">Canonical calculation findings remain separate. Unavailable test evidence is not evidence of a physical failure or a passed test.</p></section>';}
  function loading(){return '<section class="te-evidence te-loading" role="status"><h3>Test evidence</h3><p>Loading recorded comparisons for the selected configuration…</p></section>';}
  window.SixDTestEvidence=Object.freeze({render,unavailable,loading});
})();
