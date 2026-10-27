/* One captured, read-only review of a saved project revision. */
(() => {
  'use strict';
  let mounted = null;
  const disclosureStates=new Map();
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const list = value => Array.isArray(value) ? value : [];
  const integer = value => Number.isSafeInteger(value) && value >= 0 ? value : 0;
  const statusLabel = value => ({met:'Meets criterion',not_met:'Criterion unmet',not_assessed:'Not assessed',not_run:'Not calculated'}[value] || 'Not assessed');
  const unit = value => String(value ?? '').replace(/\^(-?\d+)/g, (_, exponent) => [...exponent].map(c => ({'-':'⁻','0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹'}[c])).join(''));
  const exactQuantity = value => value && typeof value.value === 'number' && Number.isFinite(value.value) ? esc(String(value.value) + (value.unit ? ' ' + unit(value.unit) : '')) : '—';
  const quantity = value => value && typeof value.value === 'number' && Number.isFinite(value.value) ? (window.SixDUnits?.value(value.value,value.unit||'') ?? exactQuantity(value)) : '—';
  const badge = status => '<span class="rw-badge rw-' + esc(status) + '">' + esc(statusLabel(status)) + '</span>';
  const button = (action, text, primary = false, disabled = false) => '<button type="button" class="sd-button' + (primary ? ' sd-primary' : '') + '" data-rw="' + esc(action) + '"' + (disabled ? ' disabled' : '') + '>' + esc(text) + '</button>';
  const navButton = (action, text) => '<button type="button" class="rw-text-link" data-rw-nav="' + esc(action) + '">' + esc(text) + '<span aria-hidden="true"> ↗</span></button>';
  const routes = new Set(['edit','author-project','coverage','systems','simulation','powered-flight','guided-ascent','staged-ascent','attitude','power','chains','envelopes','simulation-imports','scenarios','comparison','actions','sources','report','changes']);
  const coverageKinds = [
    ['applicability_unknown','Model fit not declared','Review whether the model assumptions fit the intended use. Numerical results cannot supply this declaration.'],
    ['outside_assumptions','Outside model assumptions','The supplied model-fit review identifies conditions outside the model assumptions.'],
    ['missing_analysis','Analysis missing or unsupported','A check has no linked supported calculation. Define an applicable analysis and criterion.'],
    ['undecided','Scope undecided','Decide whether the check is required for the declared mission and phase.'],
    ['needs_review','Declaration context changed','Review the declaration against changed requirements, inputs or model context.'],
    ['unassessed','Analysis not assessed','The linked analysis does not supply a current assessed finding. Open coverage for the recorded reason.'],
    ['criterion_unmet','Linked criterion unmet','The linked calculated criterion is unmet; the supplied model-fit declaration is unverified.'],
    ['criterion_met','Criterion met with supplied fit declaration','The calculated criterion is met. The supplied fit declaration remains unverified.'],
    ['excluded','Excluded by supplied rationale','The declared scope excludes this check. Any linked calculated finding remains unchanged.']
  ];
  function coverageSummary(data) {
    const checks = list(data.coverage?.checks);
    const groups = coverageKinds.map(([status,label,reason]) => ({status,label,reason,count:checks.filter(row => row.coverage_status === status).length})).filter(group => group.count);
    const other = checks.filter(row => !coverageKinds.some(([status]) => status === row.coverage_status)).length;
    if (other) groups.push({status:'unavailable',label:'Coverage status unavailable',reason:'Open engineering coverage to inspect the saved check context.',count:other});
    const pending = checks.filter(row => !['criterion_met','excluded'].includes(row.coverage_status)).length;
    const headline = checks.length + ' scope ' + (checks.length === 1 ? 'check' : 'checks') + ' · ' + pending + (pending === 1 ? ' needs' : ' need') + ' attention';
    return {checks,groups,pending,headline};
  }

  function unmount() {
    if (!mounted) return;
    mounted.closed = true;
    mounted.controller?.abort();
    mounted.host.removeEventListener('toggle',mounted.onToggle,true);
    mounted.host.onclick = null;
    mounted.host.oninput = null;
    mounted.host.replaceChildren();
    mounted = null;
  }

  function mount(host, ctx) {
    unmount();
    const state = {host, closed:false, controller:null, request:0, data:null, loading:true, error:'', filter:'all', query:'', selected:null};
    const captured = {projectId:ctx.projectId, revision:ctx.revision, hasDraft:Boolean(ctx.hasDraft), runId:ctx.currentRunId};
    mounted = state;
    const live = () => mounted === state && !state.closed;
    const historical = data => data.revision !== data.latest_revision;
    const hasRun = data => Boolean(data.run_id);
    const findingStatus = (data, finding) => hasRun(data) ? finding.status : 'not_run';
    const isDraft = () => captured.hasDraft;

    const detailKey=id=>JSON.stringify([captured.projectId,captured.revision,captured.runId||null,id]);
    function fold(id,title,body,note=''){
      const key=detailKey(id);
      return '<details class="rw-disclosure" data-rw-disclosure="'+esc(id)+'" data-rw-detail-key="'+esc(key)+'"'+(disclosureStates.get(key)?' open':'')+'><summary>'+esc(title)+(note?'<span class="rw-caption">'+esc(note)+'</span>':'')+'</summary><div class="rw-disclosure-body">'+body+'</div></details>';
    }
    state.onToggle=event=>{const node=event.target;if(!live()||!node.matches?.('details[data-rw-detail-key]'))return;disclosureStates.set(node.dataset.rwDetailKey,node.open);if(disclosureStates.size>250)disclosureStates.delete(disclosureStates.keys().next().value);};
    host.addEventListener('toggle',state.onToggle,true);
    function verdict(data){
      const failed=integer(data.counts?.not_met),unknown=integer(data.counts?.not_assessed),met=integer(data.counts?.met);
      const heading=isDraft()?'Your draft has not been calculated.':!hasRun(data)?'Calculate this revision to see its results.':failed?failed+' '+(failed===1?'check misses':'checks miss')+' the stated limit.':unknown?met+' checks meet their criteria; '+unknown+' '+(unknown===1?'needs':'need')+' more evidence.':'The calculated checks meet their stated criteria.';
      const note=isDraft()?'The results below belong to saved R'+data.revision+'.':!hasRun(data)?'Earlier saved results do not assess this revision.':'These are bounded calculation results, not a complete mission assessment.';
      return '<section class="rw-verdict" aria-label="Review conclusion"><strong>'+esc(heading)+'</strong><p>'+esc(note)+'</p></section>';
    }
    function thrustCard(data){
      const inputs=list(ctx.thrustInputs);if(!inputs.length)return '';
      return '<section class="rw-thrust" aria-label="Editable thrust"><div><span class="rw-eyebrow">'+(isDraft()?'Unsaved draft':'Saved design')+'</span><h2>Engine thrust</h2>'+inputs.map(item=>'<p><strong>'+quantity({value:item.value,unit:item.unit})+'</strong>'+(inputs.length>1?' · '+esc(item.label):'')+(item.previous?'<span class="rw-caption">Previous saved R'+esc(item.previous.revision)+': '+quantity(item.previous)+'</span>':'')+'</p>').join('')+'<p class="rw-caption">Thrust is the engine’s pushing force. You can choose your own value.</p></div>'+button('edit-thrust','Edit thrust',true,historical(data)||!ctx.onEditThrust)+(historical(data)?'<p class="rw-caption">Historical values are read-only. Select the latest revision to edit.</p>':'')+'</section>';
    }

    function context(data) {
      return '<div class="rw-context" aria-label="Captured evidence context">' +
        '<span class="rw-context-kind">Saved revision ' + esc(data.revision) + '</span>' +
        '<span>' + (historical(data) ? 'Historical · latest is revision ' + esc(data.latest_revision) : 'Latest saved revision') + '</span>' +
        '<span>' + (hasRun(data) ? 'Calculation recorded' : 'No current calculation') + '</span>' + (hasRun(data) ? '<details class="rw-context-identity"><summary>Calculation identity</summary><code>'+esc(data.run_id)+'</code></details>' : '') + '</div>' +
        (data.prior_review && !hasRun(data) ? '<p class="rw-caption rw-prior-note">Earlier calculation ' + esc(data.prior_review.run_id) + ' is retained in history and is not counted here.' + (list(data.prior_review.stale_reasons).length ? ' ' + esc(data.prior_review.stale_reasons.join(' ')) : '') + '</p>' : '');
    }

    function nextStep(data) {
      const failed = integer(data.counts?.not_met), unknown = integer(data.counts?.not_assessed);
      if (isDraft()) return '<div class="rw-next rw-draft"><div><span class="rw-eyebrow">Draft changes are open</span><h2>Review the draft before recalculating.</h2><p>This page shows saved revision ' + esc(data.revision) + '. Its results do not assess your unsaved changes.</p></div>' + button('draft','Review draft changes',true) + '</div>';
      if (!list(data.models).length || !list(data.findings).length) return '<div class="rw-next"><div><span class="rw-eyebrow">Next step</span><h2>Supply a reviewable design.</h2><p>Add explicit inputs, supported model bindings and requirements before calculating findings.</p></div>'+navButton('author-project','Open design & requirements')+'</div>';
      if (!hasRun(data)) return '<div class="rw-next"><div><span class="rw-eyebrow">Next step</span><h2>Calculate this saved configuration.</h2><p>No current calculation is available for this revision. Run the affected checks to populate its findings and recorded simulations.</p></div>' + button('run','Run affected checks',true,!ctx.onRun) + '</div>';
      if (failed) return '<div class="rw-next"><div><span class="rw-eyebrow">Next step</span><h2>Inspect ' + failed + ' unmet ' + (failed === 1 ? 'criterion' : 'criteria') + '.</h2><p>Read the calculated values, stated limits and assumptions. Use follow-up actions to record the next engineering check.</p></div>' + button('filter-unmet','Review unmet criteria',true) + '</div>';
      if (unknown) return '<div class="rw-next"><div><span class="rw-eyebrow">Next step</span><h2>Resolve ' + unknown + ' unassessed ' + (unknown === 1 ? 'requirement' : 'requirements') + '.</h2><p>Missing evidence or model limitations leave these requirements unresolved. Open a finding to see the recorded reason.</p></div>' + button('filter-unassessed','Review evidence gaps',true) + '</div>';
      return '<div class="rw-next"><div><span class="rw-eyebrow">Next step</span><h2>Review the coverage behind these results.</h2><p>The calculated criteria meet their declared limits. Review model-fit declarations, scope and missing analyses before sharing the report.</p></div>' + button('coverage','Open engineering coverage',true) + '</div>';
    }

    function journey(data){
      return '<nav id="sd-project-journey" class="sd-project-journey" aria-label="Project review workflow">'+navButton('author-project','1. Design')+button('run','2. Calculate',false,!ctx.onRun||isDraft()||!list(data.models).length||!list(data.findings).length)+navButton('edit','3. Change inputs')+button('run','4. Recalculate',false,!ctx.onRun||isDraft()||!list(data.models).length||!list(data.findings).length)+navButton('changes','5. Review changes')+navButton('report','6. Report')+'</nav>';
    }
    function resultLegend(){
      return '<section id="sd-result-legend" class="sd-result-legend" aria-labelledby="sd-result-legend-title"><h3 id="sd-result-legend-title">What the results mean</h3><div class="sd-legend-explanations"><div>'+badge('met')+'<p>The saved calculation satisfies the declared condition for its stated model and inputs. Model applicability is reviewed separately.</p></div><div>'+badge('not_met')+'<p>The saved calculation misses the declared condition. Inspect its value, limit and assumptions.</p></div><div>'+badge('not_assessed')+'<p>There is not enough applicable evidence to decide. Missing analysis or numerical uncertainty is not a failed design.</p></div></div><p class="rw-caption">Not calculated means this saved revision still needs its checks run. Save draft changes before recalculating.</p></section>';
    }
    function rocketReference(data) {
      const ref = data.rocket_reference;
      if (!ref?.recognized&&list(ctx.thrustInputs).length)return '';
      if (!ref?.recognized) return '<section class="rw-reference-entry" aria-label="Rocket reference"><div><strong>Explore a rocket change review</strong><p>Five supported calculations, one saved design. Follow a baseline, a thrust reduction and a correction.</p></div>' + button('rocket-open','Create rocket reference',false,isDraft()) + '</section>';
      const burnout = list(data.findings).find(row => row.requirement_id === 'burnout_height');
      const stage = ['baseline','reduced','corrected'].indexOf(ref.stage);
      const stages = ['Example start · 20,000 N','Example reduction · 11,000 N','Example restoration · 20,000 N'];
      const names = {propulsion:'Ideal propulsion',vertical_flight:'Vertical flight',atmospheric_load:'Atmospheric load screen',mount:'Static structure',thermal:'Steady thermal'};
      const describe = ids => list(ids).map(id => names[id] || id).join(', ') || 'None';
      const shownQuantity = quantity;
      const provenance = hasRun(data) ? '<p class="rw-caption"><strong>Recalculated:</strong> ' + esc(describe(ref.executed_model_ids)) + '. <strong>Reused:</strong> ' + esc(describe(ref.reused_model_ids)) + '. Original execution origins remain in the saved receipt.</p>' : '';
      let controls = '';
      if (isDraft()) controls = button('draft','Review staged changes',true);
      else if (historical(data)) controls = '<p class="rw-caption">Historical revision: select the latest saved revision to stage another change.</p>';
      else if (!hasRun(data)) controls = button('run','Calculate this revision',true,!ctx.onRun);
      else if (ref.can_stage) controls = button('rocket-stage',ref.action_label || 'Stage the next thrust change',true,!!state.error || state.loading);
      else if (ref.stage === 'corrected') controls = navButton('comparison','Compare saved revisions') + navButton('report','Open evidence report');
      return '<section class="rw-rocket" aria-labelledby="rw-rocket-title"><span class="rw-eyebrow">Optional prepared example · five supported calculations</span><h2 id="rw-rocket-title">' + esc(ref.title) + '</h2><ol class="rw-rocket-stages" aria-label="Rocket review stages">' + stages.map((label,index) => '<li' + (index === stage ? ' aria-current="step"' : '') + '><span>' + (index + 1) + '</span>' + esc(label) + '</li>').join('') + '</ol><p class="sd-teaching-note">Teaching example: thrust is the engine’s pushing force, measured in newtons (N). The prepared path reduces it from 20,000 to 11,000 N, then restores it. These are example values; choose Change inputs to edit a different value.</p><p>' + esc(ref.reason) + '</p>' + (isDraft() ? '<p class="sd-notice" role="status">These results assess saved revision R' + esc(data.revision) + '; unsaved draft changes have not been calculated.</p>' : '') + (burnout && hasRun(data) ? '<div class="rw-rocket-result"><strong>Burnout altitude</strong><span>' + shownQuantity(burnout.metric) + ' <span aria-hidden="true">/</span> minimum ' + shownQuantity(burnout.limit) + '</span>' + badge(burnout.status) + '</div>' : '') + provenance + '<div class="rw-rocket-actions">' + controls + navButton('powered-flight','Flight graphs & playback') + navButton('chains','Inspect calculation links') + '</div><details><summary>What this reference covers</summary><p>Shared mass, thrust and specific impulse feed ideal propulsion and vertical flight. The maximum sampled speed feeds a separate reference-density drag screen, then a declared transverse static cantilever load. The steady radiator is independent and can be reused after thrust changes.</p><p>The ideal required-burn duration differs from full-propellant flight burnout. The load screen is not actual flight maximum drag. These one-way scalar links do not provide simultaneous physics or feedback. The beam does not verify the rocket body, and the radiator does not predict ascent aeroheating.</p><p>Launch guidance stays unassessed. Navigation, stability, staging, reentry and landing remain outside this constructed case. This is not a historical launch or mission approval.</p></details></section>';
    }

    function countCard(data, key, title, note) {
      const value = hasRun(data) ? integer(data.counts?.[key]) : '—';
      return '<button type="button" class="rw-count rw-count-' + key + '" data-rw-filter="' + key + '"' + (!hasRun(data) ? ' disabled' : '') + '><span class="rw-count-value">' + value + '</span><span><strong>' + esc(title) + '</strong><small>' + esc(note) + '</small></span></button>';
    }

    function coverageContext(data) {
      const summary = coverageSummary(data);
      return '<section class="rw-coverage-context" aria-labelledby="rw-coverage-title"><div class="rw-section-heading"><div><h2 id="rw-coverage-title">Coverage and model applicability</h2><p>' + summary.headline + '</p></div>' + navButton('coverage','Review declarations & model fit') + '</div><p class="rw-coverage-explanation">Criterion counts above describe calculated requirements. Coverage records whether a check is included and whether its model assumptions fit the intended use. A met numerical criterion cannot resolve a missing model-fit declaration.</p>' +
        (summary.groups.length ? '<dl class="rw-coverage-breakdown">' + summary.groups.map(group => '<div data-rw-coverage-status="' + esc(group.status) + '"><dt><span>' + group.count + '</span> ' + esc(group.label) + '</dt><dd>' + esc(group.reason) + '</dd></div>').join('') + '</dl>' : '<p class="rw-caption">No scope checks are recorded in this snapshot.</p>') +
        '<p class="rw-caption">Coverage can include additional declared checks, so its total may differ from requirement findings. Fit declarations and exclusions are supplied, unverified context; they do not change calculated findings. These counts are not a mission-completeness measure.</p></section>';
    }

    function map(data) {
      const models = list(data.models), scope = coverageSummary(data), actions = list(data.actions?.actions);
      const sims = data.simulations || {}, imports = list(sims.imports), envelopes = list(sims.envelopes), scenarios = list(sims.scenarios);
      const openActions = actions.filter(item => item.status !== 'closed').length;
      const savedSimulations = integer(sims.canonical_orbits) + integer(sims.canonical_flights);
      const links = list(data.sources?.links);
      const entry = (number, title, text, linksHtml) => '<section class="rw-map-step"><span class="rw-step-number">' + number + '</span><h3>' + title + '</h3><p>' + esc(text) + '</p><div class="rw-step-links">' + linksHtml + '</div></section>';
      let playbackLinks = '';
      if (models.some(m => m.has_orbit)) playbackLinks += navButton('simulation','Orbit playback');
      if (models.some(m => m.has_flight && !m.has_guided && !m.has_staged)) playbackLinks += navButton('powered-flight','Vertical flight');
      if (models.some(m => m.has_guided)) playbackLinks += navButton('guided-ascent','Ascent & steering');
      if (models.some(m => m.has_staged)) playbackLinks += navButton('staged-ascent','Variable thrust & staging');
      if (models.some(m => m.has_attitude)) playbackLinks += navButton('attitude','Attitude history');
      if (models.some(m => m.has_power)) playbackLinks += navButton('power','Power history');
      playbackLinks += navButton('simulation-imports', 'Simulation imports');
      return '<section class="rw-section" aria-labelledby="rw-map-title"><div class="rw-section-heading"><div><h2 id="rw-map-title">Review map</h2><p>Move from declared design to traceable evidence.</p></div></div><div class="rw-map">' +
        entry('01','Design',models.length + ' configured ' + (models.length === 1 ? 'model' : 'models'),navButton('author-project','Design & requirements')) +
        entry('02','Coverage',scope.headline,navButton('coverage','Engineering coverage')) +
        entry('03','Calculations',hasRun(data) ? list(data.findings).length + ' recorded findings' : 'No current calculation',navButton('systems','Systems canvas') + navButton('chains','Linked calculations')) +
        entry('04','Simulation',savedSimulations + ' recorded trajectories · ' + imports.length + ' imports',playbackLinks) +
        entry('05','Studies',envelopes.length + ' envelope studies · ' + scenarios.length + ' scenario studies',navButton('envelopes','Envelope studies') + navButton('scenarios','Scenario studies') + navButton('comparison','Compare designs')) +
        entry('06','Follow-up',openActions + ' open actions · ' + links.length + ' source links',navButton('actions','Review actions') + navButton('sources','Source library')) +
        entry('07','Report','Saved findings, context and supplemental evidence',navButton('report','Open review report')) +
        '</div><p class="rw-caption">' + (integer(sims.imports_history?.omitted_count) || integer(sims.scenarios_history?.omitted_count) ? esc(integer(sims.imports_history?.omitted_count) + ' import records and ' + integer(sims.scenarios_history?.omitted_count) + ' study records are omitted from this bounded preview. Open their dedicated histories. ') : '') + 'Counts describe records available in this captured revision. Historical studies and imports retain their original context; they do not update its requirement findings.</p></section>';
    }

    function attention(data) {
      const scope = coverageSummary(data), checks = scope.checks;
      const changedChecks = checks.filter(item => item.needs_review).length;
      const unresolved = scope.groups.filter(group => !['criterion_met','excluded'].includes(group.status)).map(group => group.count + ' ' + group.label.toLocaleLowerCase()).join('; ');
      const actions = list(data.actions?.actions), changedActions = actions.filter(item => item.review_status && item.review_status !== 'current').length;
      const openActions = actions.filter(item => item.status !== 'closed').length;
      const links = list(data.sources?.links), changedLinks = links.filter(item => item.status && item.status !== 'linked').length;
      const line = (name, explanation, action, label) => '<li><div><strong>' + esc(name) + '</strong><p>' + esc(explanation) + '</p></div>' + navButton(action,label) + '</li>';
      return '<section class="rw-section rw-attention" aria-labelledby="rw-attention-title"><div class="rw-section-heading"><div><h2 id="rw-attention-title">What needs attention</h2><p>Declarations and follow-up stay separate from calculated findings.</p></div></div><ul>' +
        line('Engineering coverage',scope.pending + (scope.pending === 1 ? ' scope check needs attention' : ' scope checks need attention') + (unresolved ? ': ' + unresolved : '') + '. ' + changedChecks + ' declarations flagged for changed context. This does not add to or change the calculated criterion counts.','coverage','Review coverage') +
        line('Follow-up actions',openActions + ' open actions; ' + changedActions + ' actions with changed or unavailable context. Closing an action does not change a calculation.','actions','Open actions') +
        line('Source context',links.length + ' pinned source links; ' + changedLinks + ' need review or have unavailable targets. A link is not independent verification.','sources','Inspect sources') +
        '</ul></section>';
    }

    function filtered(data) {
      const query = state.query.trim().toLocaleLowerCase();
      return list(data.findings).filter(item => (state.filter === 'all' || findingStatus(data,item) === state.filter) && (!query || [item.title,item.requirement_id,item.model_id,item.model_type,item.reason,...list(item.not_assessed)].join(' ').toLocaleLowerCase().includes(query)));
    }

    function findingDetails(item) {
      return '<section class="rw-finding-detail" aria-label="Finding details"><h3>' + esc(item.title || item.requirement_id) + '</h3><p>' + esc(item.reason || 'No calculation reason was recorded.') + '</p><h4>Exact recorded values</h4><dl class="rw-exact-values" data-exact-values><dt>Calculated value</dt><dd>'+exactQuantity(item.metric)+'</dd><dt>Declared criterion</dt><dd>'+esc(item.operator||'')+' '+exactQuantity(item.limit)+'</dd></dl><div class="rw-detail-columns"><div><h4>Recorded assumptions</h4>' + (list(item.assumptions).length ? '<ul>' + item.assumptions.map(text => '<li>' + esc(text) + '</li>').join('') + '</ul>' : '<p>No assumptions recorded for this finding.</p>') + '</div><div><h4>Not assessed</h4>' + (list(item.not_assessed).length ? '<ul>' + item.not_assessed.map(text => '<li>' + esc(text) + '</li>').join('') + '</ul>' : '<p>No exclusions listed here. Inspect model scope and engineering coverage for additional gaps.</p>') + '</div></div>' + (isDraft() ? '<p>These are saved-revision details. Review or discard the draft before opening the current requirement inspector.</p>' : button('inspect:' + item.requirement_id,'Open requirement inspector')) + '</section>';
    }

    function renderFindings() {
      if (!live() || !state.data) return;
      const data = state.data, items = filtered(data), target = host.querySelector('[data-rw-findings]');
      if (!target) return;
      host.querySelectorAll('[data-rw-filter]').forEach(el => el.setAttribute('aria-pressed',String(el.dataset.rwFilter === state.filter)));
      const counter = host.querySelector('[data-rw-match-count]');
      if (counter) counter.textContent = items.length + ' of ' + list(data.findings).length + ' requirements';
      if (!items.length) {
        target.innerHTML = '<div class="rw-empty"><strong>' + (list(data.findings).length ? 'No requirements match this filter.' : 'No requirements are available.') + '</strong><p>' + (list(data.findings).length ? 'Choose All requirements or try another search.' : 'Add requirements in Design & requirements to begin a review.') + '</p></div>';
        return;
      }
      target.innerHTML = '<p class="rw-caption">Values are rounded for reading. Open a check for exact values and its reason.</p><div class="rw-table-scroll"><table class="rw-findings-table"><caption class="rw-sr-only">Saved requirement findings for revision ' + esc(data.revision) + '</caption><thead><tr><th scope="col">Requirement</th><th scope="col">Finding</th><th scope="col">Calculated value</th><th scope="col">Declared criterion</th><th scope="col">Meaning</th></tr></thead><tbody>' + items.map(item => '<tr' + (state.selected === item.requirement_id ? ' class="rw-selected"' : '') + '><th scope="row"><button type="button" class="rw-requirement" data-rw-requirement="' + esc(item.requirement_id) + '" aria-expanded="' + String(state.selected === item.requirement_id) + '">' + esc(item.title || item.requirement_id) + '</button><small>' + esc(item.model_id || item.model_type || 'No model mapping') + '</small></th><td>' + badge(findingStatus(data,item)) + '</td><td class="rw-quantity">' + quantity(item.metric) + '</td><td class="rw-quantity">' + (item.limit ? esc(({le:'≤',ge:'≥',lt:'<',gt:'>',eq:'='}[item.operator] || item.operator || '')) + ' ' + quantity(item.limit) : '—') + '</td><td><p class="rw-reason">' + esc(!hasRun(data)?'Not calculated':item.status==='met'?'Within the stated limit':item.status==='not_met'?'Outside the stated limit':'More evidence needed') + '</p></td></tr>'+(state.selected===item.requirement_id?'<tr class="rw-inline-detail"><td colspan="5">'+findingDetails(item)+'</td></tr>':'')).join('') + '</tbody></table></div>';
    }

    function render() {
      if (!live()) return;
      const data = state.data;
      host.innerHTML = '<article class="rw-workspace" aria-label="Review workspace" aria-busy="' + String(state.loading) + '"><header class="rw-header"><div><span class="rw-eyebrow">Review workspace</span><h1>' + esc(data?.project_name || 'Project review') + '</h1><p>See the result. Open a check to understand why.</p></div><div>' + button('refresh',state.loading ? 'Refreshing…' : 'Refresh snapshot',false,state.loading) + '</div></header>' +
        (state.error ? '<div class="rw-error" role="alert"><strong>Review snapshot unavailable.</strong><p>' + esc(state.error) + '</p>' + (data ? '<p>The previously captured snapshot remains below. Refresh to check for newer evidence.</p>' : '') + button('refresh','Try again') + button('reload','Reload saved context') + '</div>' : '') +
        (!data ? (state.loading ? '<div class="rw-loading" role="status"><span class="rw-loading-mark" aria-hidden="true"></span><strong>Reading the saved revision…</strong><p>Collecting calculations, coverage and supplemental evidence in one snapshot.</p></div>' : '') : context(data) + verdict(data) +
          '<section class="rw-counts" aria-label="Canonical requirement findings">' + countCard(data,'met','Meet their criteria','Calculated values within declared limits') + countCard(data,'not_met','Criteria unmet','Calculated limits exceeded') + countCard(data,'not_assessed','Not assessed','Evidence or model gaps') + '</section>' +
          '<p class="rw-caption rw-count-caption">' + (hasRun(data) ? 'Model fit and missing analysis are reviewed separately in Coverage below.' : integer(data.counts?.not_run) + ' requirements not calculated. No results are counted until this saved revision has a current calculation.') + '</p>' +
          nextStep(data) + thrustCard(data) +
          '<section class="rw-section" aria-labelledby="rw-findings-title"><div class="rw-section-heading"><div><h2 id="rw-findings-title">Requirement findings</h2><p>Exact recorded values and limits. Select a requirement for its assumptions and exclusions.</p></div><span class="rw-caption" data-rw-match-count></span></div><div class="rw-findings-toolbar"><div class="rw-filters" role="group" aria-label="Filter requirements"><button type="button" data-rw-filter="all" aria-pressed="true">All requirements</button><button type="button" data-rw-filter="not_met" aria-pressed="false">Criteria unmet</button><button type="button" data-rw-filter="not_assessed" aria-pressed="false">Not assessed</button></div><label class="rw-search"><span class="rw-sr-only">Search requirements</span><input type="search" placeholder="Search requirements or reasons…" value="' + esc(state.query) + '" data-rw-search></label></div><div data-rw-findings></div></section>' +
          '<section class="rw-coverage-brief"><h2>Coverage &amp; model fit</h2><p>'+esc(coverageSummary(data).headline)+'</p><p class="rw-caption">'+esc(coverageSummary(data).groups.map(group=>group.count+' '+group.label.toLowerCase()).join(' · ')||'No scope declarations recorded')+'</p>'+navButton('coverage','Review model fit & gaps')+fold('coverage','Why these coverage checks need attention',coverageContext(data))+'</section>'+fold('workflow','Review workflow',journey(data)+map(data))+fold('reference','Prepared rocket example',rocketReference(data),'Optional teaching sequence; your thrust values are editable')+fold('meaning','What the result labels mean',resultLegend())+fold('attention','Follow-up and supporting records',attention(data)) +
          '<footer class="rw-footer"><details><summary>Snapshot identity and assessment limits</summary><dl><div><dt>Saved revision</dt><dd>' + esc(data.revision) + '</dd></div><div><dt>Calculation</dt><dd>' + esc(data.run_id || 'No current calculation') + '</dd></div><div><dt>Review digest</dt><dd>' + esc(data.review_digest || 'Unavailable') + '</dd></div><div><dt>Snapshot digest</dt><dd>' + esc(data.digest || 'Unavailable') + '</dd></div></dl><ul>' + list(data.limitations).map(text => '<li>' + esc(text) + '</li>').join('') + '</ul></details><p>Read-only snapshot · actions open the corresponding workspace · refresh explicitly after changes</p></footer>') + '</article>';
      renderFindings();
    }

    async function refresh() {
      if (!live()) return;
      state.controller?.abort();
      state.controller = new AbortController();
      const request = ++state.request;
      state.loading = true;
      state.data = null;
      state.error = '';
      render();
      try {
        const data = await ctx.api('/api/review-workspace?project_id=' + encodeURIComponent(captured.projectId) + '&revision=' + encodeURIComponent(captured.revision),undefined,{signal:state.controller.signal});
        if (!live() || request !== state.request) return;
        if (data?.schema !== 'sixd.review-workspace.v1' || data.project_id !== captured.projectId || data.revision !== captured.revision) throw new Error('The response does not match this project revision. Reload the project before reviewing evidence.');
        if (captured.runId !== undefined && (data.run_id || null) !== (captured.runId || null)) throw new Error('The saved calculation changed while this review was open. Reload the project to capture the matching calculation.');
        state.data = data;
      } catch (error) {
        if (live() && request === state.request && error.name !== 'AbortError') state.error = error.message || 'The review snapshot could not be loaded.';
      } finally {
        if (live() && request === state.request) { state.loading = false;render(); }
      }
    }

    function filter(value) {
      state.filter = value;
      state.selected = null;
      renderFindings();
    }

    host.oninput = event => {
      if (!event.target.matches('[data-rw-search]')) return;
      state.query = event.target.value;
      state.selected = null;
      renderFindings();
    };
    host.onclick = event => {
      const element = event.target.closest('button');
      if (!element || !host.contains(element) || element.disabled) return;
      if (element.dataset.rwNav && routes.has(element.dataset.rwNav)) { ctx.onNavigate?.(element.dataset.rwNav);return; }
      if (element.dataset.rwFilter) { filter(element.dataset.rwFilter);return; }
      if (element.dataset.rwRequirement) {
        state.selected = state.selected === element.dataset.rwRequirement ? null : element.dataset.rwRequirement;
        renderFindings();
        return;
      }
      const action = element.dataset.rw;
      if (action === 'edit-thrust'&&!historical(state.data)) {ctx.onEditThrust?.();return;}
      if (action === 'reload') { ctx.onReload?.();return; }
      if (action === 'rocket-open' && !isDraft()) { ctx.onRocketOpen?.();return; }
      if (action === 'rocket-stage' && !isDraft() && state.data?.rocket_reference?.can_stage && !state.error && !state.loading) { ctx.onRocketStage?.();return; }
      if (action === 'refresh') { void refresh();return; }
      if (action === 'run' && !isDraft() && state.data && !state.loading && ctx.onRun) { void ctx.onRun();return; }
      if (action === 'draft') { ctx.onNavigate?.('changes');return; }
      if (action === 'coverage') { ctx.onNavigate?.('coverage');return; }
      if (action?.startsWith('inspect:') && !isDraft()) { ctx.onSelectRequirement?.(action.slice(8));return; }
      if (action === 'filter-unmet' || action === 'filter-unassessed') {
        filter(action === 'filter-unmet' ? 'not_met' : 'not_assessed');
        host.querySelector('#rw-findings-title')?.scrollIntoView({block:'start',behavior:'smooth'});
      }
    };
    render();
    void refresh();
  }
  window.SixDReviewWorkspace = {mount,unmount};
})();
