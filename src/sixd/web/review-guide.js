/* Read-only walkthrough state; actions reuse explicit workspace controls. */
(() => {
  'use strict';
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function evaluate(p){
    const view=p.view,project=p.draft||view?.project;
    const ready=!!project?.models?.length&&!!project?.requirements?.length;
    const fresh=!!view?.run&&!view.run.stale;
    const previous=!!view?.prior_run&&view.prior_run.revision<view.revision;
    const key=view?.run?JSON.stringify([view.project_id,view.revision,view.run.run_id]):null;
    let phase='open',step=0,title='Open a project',body='Start with a constructed reference template or select an existing saved project.',action='guided-reference',button='Use a reference template',disabled=false;
    if(view&&!ready){phase='setup';title='Supply a reviewable setup';body='Add explicit inputs, supported model bindings and requirements. An empty project has no calculated findings.';action='author-project';button='Open Author project';}
    else if(ready&&p.isLatest===false){phase='latest';title='Select the latest saved revision';body='Earlier evidence stays inspectable. Use the latest revision to create the next draft.';action='guided-latest';button='Open latest revision';}
    else if(ready&&p.draft){phase='draft';step=2;title=p.dirty?'Review the draft change':'Edit an explicit input';body=p.dirty?'The draft has changed. Preview its dependencies, then save a revision. Draft values are not calculated findings.':'Use the editable Table fields to change an input value, unit or source. Preserve justified requirement limits.';action=p.dirty?(p.impactVerified?'save':'impact'):'guided-inputs';button=p.dirty?(p.impactVerified?'Save revision':'Preview affected checks'):'Open editable inputs';disabled=!p.dirty&&p.page==='system'&&p.viewMode==='table';}
    else if(ready&&!fresh){phase=previous?'rerun':'baseline';step=previous?3:1;title=previous?'Calculate the saved revision':'Calculate a baseline';body=view?.run?.stale?'This review uses older calculation sources. Run supported checks before relying on current evidence.':previous?'The revision is saved, but it has no current review. Rerun affected checks; unchanged results may be reused with provenance.':'Inspect the supplied inputs and limits, then run the supported local checks. Unsupported requirements remain unassessed.';action='run';button=previous?'Rerun affected checks':'Run baseline checks';}
    else if(ready&&!previous){phase='revise';step=2;title='Create a reviewable change';body='A baseline review is recorded. Create a draft, change a sourced input, preview affected checks and save the next revision.';action='edit';button='Edit draft';}
    else if(ready&&fresh&&previous){
      step=4;
      if(p.page!=='report'){phase='report';title='Compare the recorded outcomes';body='The new review is saved. Inspect what changed, which models ran or reused evidence, and the remaining unassessed scope.';action='report';button='Open evidence report';}
      else if(p.exportedRun!==key){phase='export';title='Export this reviewed configuration';body='Read the findings and limits, then export the saved evidence. The report is a bounded engineering review, not whole-mission approval.';action='export';button='Export evidence JSON';}
      else{phase='complete';title='Review walkthrough completed';body='An evidence export was requested for this exact saved run. Keep unresolved requirements and model limitations with the result; AI interpretation is optional.';action='changes';button='Revisit changes';}
    }
    return {phase,step,title,body,action,button,disabled:!!p.busy||disabled,runKey:key,
      stages:['Project','Baseline','Draft change','Recalculate','Evidence'],projectName:project?.name||'No project selected',revision:view?.revision||null};
  }
  function render(p){
    const s=evaluate(p);
    const sample=p.view?.project?.models?.some(m=>m.type==='radiative_equilibrium'&&m.inputs?.heat_input==='heat_input')&&/constructed/i.test(p.view.project.inputs?.heat_input?.source||'');
    return '<div class="sd-review-guide-heading"><div><span class="sd-label">Guided engineering review</span><h2>'+esc(s.title)+'</h2></div><button type="button" class="sd-icon-button" data-action="guided-close" aria-label="Close guided review">×</button></div><ol class="sd-review-guide-stages" aria-label="Review stages">'+s.stages.map((label,i)=>'<li'+(i===s.step?' aria-current="step"':'')+'>'+esc(label)+'</li>').join('')+'</ol><p>'+esc(s.body)+'</p><p class="sd-small sd-muted">'+esc(s.projectName)+(s.revision?' · saved R'+esc(s.revision):'')+' · Opening this guide runs no calculation or AI request.</p>'+(sample&&['draft','revise'].includes(s.phase)?'<p class="sd-small sd-review-guide-example">Constructed thermal walkthrough only: set Heat input to 700 W to demonstrate an unmet temperature criterion. This illustrative change is not a recommendation for a real design.</p>':'')+'<div class="sd-action-row"><button type="button" class="sd-button sd-primary" data-action="'+esc(s.action)+'" '+(s.disabled?'disabled':'')+'>'+esc(s.button)+'</button><button type="button" class="sd-button" data-action="guided-inputs" '+(p.busy?'disabled':'')+'>Inspect inputs</button><button type="button" class="sd-button sd-quiet" data-action="guided-reference" '+(p.draft||p.busy?'disabled':'')+'>New reference project</button></div>';
  }
  window.SixDReviewGuide=Object.freeze({evaluate,render});
})();
