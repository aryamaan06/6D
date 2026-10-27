/* Saved assistant context is descriptive only; this module performs no requests. */
(() => {
  'use strict';
  const list=value=>Array.isArray(value)?value:[];
  const label=value=>typeof value==='string'?value:'';
  const human=value=>label(value).replace(/_/g,' ').replace(/^./,character=>character.toUpperCase());
  const exactRequirement=(requirements,id)=>typeof id==='string'?list(requirements).find(requirement=>requirement?.id===id)||null:null;

  function defaultIntent({page,selected,requirements}={}){
    const requirement=page==='system'&&selected?.kind==='requirement'?exactRequirement(requirements,selected.id):null;
    return requirement?{scope:'requirement',requirementId:requirement.id}:{scope:'project',requirementId:null};
  }

  // Match the backend's bounded source_context._relevant rule, rather than
  // inferring relevance from a source title, loose ID prefix or library count.
  function relevant(target,requirement){
    if(!target||!requirement)return false;
    return target.target_id==='requirement:'+requirement.id||target.target_id==='finding:'+requirement.id||
      target.kind==='model_assumption'&&target.id===requirement.model_id&&typeof target.target_id==='string'&&target.target_id.startsWith('assumption:'+requirement.model_id+':');
  }

  function referenceSummary(profile,{projectId,revision,runId,requirements}){
    if(!profile||profile.project_id!==projectId||profile.revision!==revision||profile.context!=='saved'||profile.run_id!==runId||!Array.isArray(profile.links)){
      return {state:'unavailable',availableCount:null,needsReviewCount:null,unavailableCount:null,summary:'Linked references for this saved context are not loaded.'};
    }
    const links=profile.links.filter(link=>requirements.some(requirement=>relevant(link?.target,requirement)));
    const availableCount=links.filter(link=>link.status==='linked').length,needsReviewCount=links.filter(link=>link.status==='needs_review').length,unavailableCount=links.filter(link=>link.status==='target_unavailable').length;
    let summary=availableCount+' linked reference'+(availableCount===1?'':'s')+' available in this scope';
    if(needsReviewCount||unavailableCount)summary+=' · '+needsReviewCount+' need review · '+unavailableCount+' target'+(unavailableCount===1?'':'s')+' unavailable';
    summary+='. Capture limits apply when you ask.';
    return {state:'ready',availableCount,needsReviewCount,unavailableCount,summary};
  }

  function compatibleTest(selection,{projectId,revision,runId,requirement}){
    if(!requirement||!selection||selection.projectId!==projectId||selection.revision!==revision||selection.requirementId!==requirement.id||Object.hasOwn(selection,'runId')&&selection.runId!==runId||typeof selection.comparisonId!=='string'||!selection.comparisonId||!Number.isInteger(selection.rowNumber)||selection.rowNumber<1)return null;
    return {projectId,revision,...(Object.hasOwn(selection,'runId')?{runId}:{}),requirementId:requirement.id,comparisonId:selection.comparisonId,rowNumber:selection.rowNumber};
  }

  function describe({view,page,scope,requirementId,testSelection,sourceProfile,hasDraft=false,latest=true}={}){
    const project=view?.project,projectId=view?.project_id??null,revision=view?.revision??null;
    const requirements=list(project?.requirements),chosenScope=scope==='requirement'?'requirement':'project';
    const requirement=chosenScope==='requirement'?exactRequirement(requirements,requirementId):null;
    const model=requirement?list(project?.models).find(item=>item?.id===requirement.model_id):null;
    const candidate=view?.run;
    const run=candidate&&(candidate.project_id==null||candidate.project_id===projectId)&&(candidate.revision==null||candidate.revision===revision)?candidate:null;
    const runId=run?.run_id??null,finding=requirement?run?.review?.findings?.[requirement.id]:null;
    const findingStatus=['insufficient_accuracy','accuracy_not_assessed'].includes(finding?.assessment_status)?finding.assessment_status:label(finding?.status)||null;
    const compatible=compatibleTest(testSelection,{projectId,revision,runId,requirement});
    return {
      projectId,revision,runId,title:label(project?.name)||label(projectId)||'Choose a project',page:label(page),scope:chosenScope,
      requirementId:requirement?.id??null,requirementTitle:label(requirement?.title)||label(requirement?.id)||null,
      modelId:requirement?.model_id??null,modelTitle:label(model?.title)||human(model?.id)||null,
      findingStatus,hasDraft:hasDraft===true,historical:latest===false,runStale:run?.stale===true,testSelection:compatible,
      historyKey:JSON.stringify([projectId,revision,runId,chosenScope,requirement?.id??null,compatible?.comparisonId??null,compatible?.rowNumber??null]),
      references:referenceSummary(sourceProfile,{projectId,revision,runId,requirements:chosenScope==='project'?requirements:requirement?[requirement]:[]})
    };
  }

  window.SixDAssistantContext=Object.freeze({defaultIntent,describe});
})();
