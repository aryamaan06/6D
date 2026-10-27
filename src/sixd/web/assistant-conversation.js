/* Conversation presentation only. No provider calls, evidence changes or routing.
 * *Html properties must be preescaped application-generated markup. Model text
 * belongs in the host's existing guarded/escaped answer renderer, never raw HTML.
 */
(() => {
  'use strict';
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const html=value=>typeof value==='string'?value:'';
  const hints={
    nano:'Nano suits a short explanation or one narrow evidence question.',
    super:'Super suits ordinary investigations and follow-up checks.',
    ultra:'Ultra suits a deeper review of related findings or conflicting evidence.'
  };
  function modelHint(id){
    return (Object.hasOwn(hints,id)?hints[id]:'Choose a model for this question.')+' Suggested use, not a guarantee of accuracy.';
  }
  function modelOptionLabel(id){const labels={nano:'Nemotron 3 Nano — Quick explanations',super:'Nemotron 3 Super — Everyday review',ultra:'Nemotron 3 Ultra — Deeper reasoning'};return Object.hasOwn(labels,id)?labels[id]:'Choose a model';}
  function matchesContext(record,context){
    if(!record||!context)return false;
    const scope=context.scope==='project'?'project':context.scope==='requirement'?'requirement':null;
    if(!scope||typeof context.projectId!=='string'||!context.projectId||!Number.isSafeInteger(context.revision)||context.revision<1||typeof context.runId!=='string'||!context.runId||typeof context.reviewDigest!=='string'||!context.reviewDigest||typeof context.sourceDigest!=='string'||!/^[a-f0-9]{64}$/.test(context.sourceDigest))return false;
    const requirement=scope==='project'?'__project__':context.requirementId;
    if(typeof requirement!=='string'||!requirement||record.project_id!==context.projectId||record.revision!==context.revision||record.run_id!==context.runId||record.review_digest!==context.reviewDigest||(record.scope||'requirement')!==scope||record.requirement_id!==requirement)return false;
    const selected=context.testSelection;
    if(selected){
      if(scope==='project'||typeof selected.comparisonId!=='string'||!selected.comparisonId||!Number.isSafeInteger(selected.rowNumber)||selected.rowNumber<2||record.test_evidence?.selection?.comparison_id!==selected.comparisonId||record.test_evidence.selection.row_number!==selected.rowNumber)return false;
    }else if(record.test_evidence!=null)return false;
    if(scope==='requirement')return record.project_sources?.library_digest===context.sourceDigest;
    const expected=context.requirementIds===undefined?Object.keys(record.canonical_findings||{}):context.requirementIds;
    if(!Array.isArray(expected)||expected.some(id=>typeof id!=='string'||!id)||new Set(expected).size!==expected.length)return false;
    const findingIds=[...expected].sort();if(!findingIds.length)return false;
    const captures=record.evidence?.project?.linked_sources;
    if(captures==null&&['queued','running'].includes(record.state)){
      const queued=record.queued_reference_context,ids=queued?.requirement_ids;
      if(queued?.schema!=='sixd.queued-reference-context.v1'||queued.library_digest!==context.sourceDigest||!Array.isArray(ids)||ids.some(id=>typeof id!=='string'||!id)||new Set(ids).size!==ids.length)return false;
      const capturedIds=[...ids].sort();return capturedIds.length===findingIds.length&&findingIds.every((id,index)=>id===capturedIds[index]);
    }
    if(!captures||typeof captures!=='object'||Array.isArray(captures)||!Object.keys(captures).length)return false;
    const captureIds=Object.keys(captures).sort();
    if(!findingIds.length||findingIds.length!==captureIds.length||findingIds.some((id,index)=>id!==captureIds[index]))return false;
    return captureIds.every(id=>captures[id]?.library_digest===context.sourceDigest);
  }
  function compatibleParent(record,context){
    return !!record&&record.state==='completed'&&typeof record.summary==='string'&&!!record.summary.trim()&&record.explanation_acceptance?.accepted!==false&&matchesContext(record,context);
  }
  function turnMarkup(turn){
    const id=esc(turn.id),state=['queued','running','completed','failed'].includes(turn.state)?turn.state:'failed';
    let answer;
    if(state==='queued'||state==='running'){
      answer='<p class="sd-conversation-progress" role="status"><span aria-hidden="true"></span>'+(state==='queued'?'Your question is queued.':'Nemotron is checking the captured evidence…')+'</p>';
    }else if(state==='failed'){
      answer='<p class="sd-conversation-unavailable"><strong>Answer not completed.</strong> No accepted answer was saved.</p>'+html(turn.failureHtml);
    }else{
      answer=html(turn.answerHtml)||'<p class="sd-conversation-unavailable">This saved record has no accepted conversational answer. Its recorded evidence remains available below.</p>';
    }
    return '<article class="sd-conversation-turn" data-conversation-turn="'+id+'" data-conversation-state="'+state+'">'+
      '<div class="sd-conversation-user"><span class="sd-conversation-speaker">You</span><p class="sd-conversation-question">'+esc(turn.question)+'</p></div>'+
      '<section class="sd-conversation-answer" aria-label="Nemotron response"><header class="sd-conversation-answer-header"><strong>'+esc(turn.modelLabel||'Nemotron')+'</strong>'+(turn.timeLabel?'<span>'+esc(turn.timeLabel)+'</span>':'')+'</header>'+
      '<div class="sd-conversation-answer-body">'+answer+'</div>'+
      (turn.canonicalHtml?'<div class="sd-conversation-recorded">'+html(turn.canonicalHtml)+'</div>':'')+
      (turn.notice?'<p class="sd-conversation-notice">'+esc(turn.notice)+'</p>':'')+
      (turn.detailsHtml?'<details class="sd-conversation-details" data-conversation-details="'+id+'"><summary>Evidence and investigation details</summary><div class="sd-conversation-details-body">'+html(turn.detailsHtml)+'</div></details>':'')+'</section></article>';
  }
  function render({turns=[],emptyMessage}={}){
    const rows=Array.isArray(turns)?turns.filter(turn=>turn&&typeof turn==='object'):[];
    return '<div class="sd-conversation-log" role="log" aria-label="Conversation with Nemotron" aria-live="polite" aria-relevant="additions text">'+
      (rows.length?rows.map(turnMarkup).join(''):'<div class="sd-conversation-empty"><span class="sd-conversation-empty-mark" aria-hidden="true">6D</span><h3>Ask in your own words.</h3><p>'+esc(emptyMessage||'Ask about this project, a result you do not understand, or what to check next.')+'</p></div>')+'</div>';
  }
  window.SixDAssistantConversation=Object.freeze({render,modelHint,modelOptionLabel,matchesContext,compatibleParent});
})();
