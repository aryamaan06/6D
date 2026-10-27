import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../src/sixd/web/assistant-conversation.js',import.meta.url),'utf8');
function api(window={}){vm.runInNewContext(source,{window});return window.SixDAssistantConversation;}
const renderer=api();
const sample=extra=>({id:'turn-a',question:'Why is this unresolved?',modelLabel:'Nemotron 3 Super',timeLabel:'Today',state:'completed',answerHtml:'<p class="accepted">The saved evidence does not decide this check.</p>',canonicalHtml:'<span>Not assessed</span>',detailsHtml:'<p>Exact recorded evidence</p>',...extra});

test('question and accepted answer appear before closed evidence, without changing supplied chronology',()=>{
  const html=renderer.render({turns:[sample(),sample({id:'turn-b',question:'What should I supply?'})]});
  assert.ok(html.indexOf('Why is this unresolved?')<html.indexOf('class="accepted"'));
  assert.ok(html.indexOf('class="accepted"')<html.indexOf('Not assessed'));
  assert.ok(html.indexOf('class="accepted"')<html.indexOf('Exact recorded evidence'));
  assert.ok(html.indexOf('data-conversation-turn="turn-a"')<html.indexOf('data-conversation-turn="turn-b"'));
  assert.match(html,/<details class="sd-conversation-details" data-conversation-details="turn-a"><summary>/);
  assert.doesNotMatch(html,/<details[^>]*\bopen(?:[ >])/);
  assert.equal((html.match(/role="log"/g)||[]).length,1);
  assert.equal((html.match(/aria-live="polite"/g)||[]).length,1);
});

test('plain question, identities, labels, notices and empty copy are escaped',()=>{
  const attack='<img src=x onerror="bad()">';
  const html=renderer.render({turns:[sample({id:'" onclick="bad()',question:attack,modelLabel:attack,timeLabel:attack,notice:attack})]});
  assert.doesNotMatch(html,/<img| onclick="|onerror="/);
  assert.match(html,/&lt;img src=x onerror=&quot;bad\(\)&quot;&gt;/);
  assert.match(html,/data-conversation-turn="&quot; onclick=&quot;bad\(\)/);
  assert.doesNotMatch(renderer.render({emptyMessage:attack}),/<img/);
});

test('failed, unknown and active states never display a supplied accepted answer',()=>{
  for(const state of ['failed','queued','running','unknown']){
    const html=renderer.render({turns:[sample({state,failureHtml:'<p>Provider unavailable</p>'})]});
    assert.doesNotMatch(html,/class="accepted"/);
    if(['failed','unknown'].includes(state)){assert.match(html,/Answer not completed/);assert.match(html,/Provider unavailable/);}
    else{assert.match(html,/role="status"/);assert.doesNotMatch(html,/Provider unavailable/);}
  }
  assert.match(renderer.render({turns:[sample({answerHtml:''})]}),/no accepted conversational answer/);
});

test('empty and malformed collections stay inviting rather than inventing an answer',()=>{
  for(const turns of [undefined,null,{},[],[null,undefined]]){
    const html=renderer.render({turns});assert.match(html,/Ask in your own words/);assert.doesNotMatch(html,/sd-conversation-turn"/);
  }
  assert.match(renderer.render(),/what to check next/);
});

test('model hints describe tasks without guaranteeing quality or triggering routing',()=>{
  assert.match(renderer.modelHint('nano'),/short explanation|narrow/);
  assert.match(renderer.modelHint('super'),/ordinary|follow-up/);
  assert.match(renderer.modelHint('ultra'),/deeper|related/);
  for(const id of ['nano','super','ultra','unknown','toString'])assert.match(renderer.modelHint(id),/not a guarantee of accuracy/);
  assert.match(renderer.modelHint('toString'),/^Choose a model/);
});

test('model choice labels are task guidance and never read an old browser preference',()=>{
  const unavailable=api(Object.defineProperty({},'localStorage',{get(){throw Error('No preference may select a model');}}));
  assert.equal(unavailable.modelOptionLabel('nano'),'Nemotron 3 Nano — Quick explanations');
  assert.equal(unavailable.modelOptionLabel('super'),'Nemotron 3 Super — Everyday review');
  assert.equal(unavailable.modelOptionLabel('ultra'),'Nemotron 3 Ultra — Deeper reasoning');
  for(const value of [null,'','unknown','toString','__proto__'])assert.equal(unavailable.modelOptionLabel(value),'Choose a model');
  assert.equal(unavailable.readModelPreference,undefined);assert.equal(unavailable.writeModelPreference,undefined);
});

const digest='a'.repeat(64),otherDigest='b'.repeat(64);
const savedContext=extra=>({projectId:'vehicle',revision:3,runId:'run-current',reviewDigest:'review-current',scope:'requirement',requirementId:'temperature',testSelection:null,sourceDigest:digest,...extra});
const savedTurn=extra=>({project_id:'vehicle',revision:3,run_id:'run-current',review_digest:'review-current',requirement_id:'temperature',state:'completed',summary:'Review the supplied thermal assumptions.',project_sources:{library_digest:digest},...extra});

test('conversation parents require accepted completed prose and the exact saved numerical scope',()=>{
  const record=savedTurn(),context=savedContext(),before=JSON.stringify({record,context});
  assert.equal(renderer.compatibleParent(record,context),true,'legacy turn can continue when its evidence matches');
  assert.equal(renderer.compatibleParent(savedTurn({explanation_acceptance:{accepted:true}}),context),true);
  for(const changed of [{state:'failed'},{state:'running'},{summary:''},{summary:'   '},{summary:null},{explanation_acceptance:{accepted:false}},{project_id:'other'},{revision:2},{run_id:'older-run'},{review_digest:'older-review'},{scope:'project'},{requirement_id:'pressure'}])assert.equal(renderer.compatibleParent(savedTurn(changed),context),false,JSON.stringify(changed));
  for(const changed of [{projectId:null},{revision:'3'},{revision:0},{runId:null},{reviewDigest:null},{scope:'other'},{requirementId:null}])assert.equal(renderer.compatibleParent(record,savedContext(changed)),false,JSON.stringify(changed));
  assert.equal(JSON.stringify({record,context}),before,'compatibility is read-only');
});

test('same run with different test selection or linked-reference snapshot starts fresh',()=>{
  const selected={comparisonId:'comparison-current',rowNumber:2};
  const record=savedTurn({test_evidence:{selection:{comparison_id:'comparison-current',row_number:2}}});
  assert.equal(renderer.compatibleParent(record,savedContext({testSelection:selected})),true);
  assert.equal(renderer.compatibleParent(record,savedContext()),false);
  assert.equal(renderer.compatibleParent(savedTurn(),savedContext({testSelection:selected})),false);
  for(const testSelection of [{...selected,comparisonId:'other'},{...selected,rowNumber:3},{...selected,rowNumber:'2'},{...selected,rowNumber:0},{}])assert.equal(renderer.compatibleParent(record,savedContext({testSelection})),false);
  for(const sourceDigest of [null,'',otherDigest,'not-a-digest'])assert.equal(renderer.compatibleParent(savedTurn(),savedContext({sourceDigest})),false);
  assert.equal(renderer.compatibleParent(savedTurn({project_sources:null}),savedContext()),false);
  assert.equal(renderer.compatibleParent(savedTurn({project_sources:{library_digest:otherDigest}}),savedContext()),false);
});

test('project parents require matching reference captures for every canonical requirement',()=>{
  const context=savedContext({scope:'project',requirementId:null});
  const record=savedTurn({scope:'project',requirement_id:'__project__',canonical_findings:{temperature:{status:'met'},pressure:{status:'not_assessed'}},evidence:{project:{linked_sources:{temperature:{library_digest:digest},pressure:{library_digest:digest}}}}});
  const before=JSON.stringify(record);assert.equal(renderer.compatibleParent(record,context),true);
  for(const linked_sources of [null,{},[],{temperature:{library_digest:digest}},{temperature:{library_digest:digest},pressure:{library_digest:otherDigest}},{temperature:{library_digest:digest},pressure:{library_digest:digest},extra:{library_digest:digest}}])assert.equal(renderer.compatibleParent({...record,evidence:{project:{linked_sources}}},context),false);
  assert.equal(renderer.compatibleParent({...record,canonical_findings:{}},context),false);
  assert.equal(renderer.compatibleParent(record,{...context,testSelection:{comparisonId:'test',rowNumber:2}}),false);
  assert.equal(JSON.stringify(record),before);
});

test('active turns can match current evidence for display but never become accepted parents',()=>{
  for(const state of ['queued','running']){
    const record=savedTurn({state,summary:''});
    assert.equal(renderer.matchesContext(record,savedContext()),true);
    assert.equal(renderer.compatibleParent(record,savedContext()),false);
    assert.equal(renderer.matchesContext({...record,run_id:'other'},savedContext()),false);
    assert.equal(renderer.matchesContext({...record,project_sources:{library_digest:otherDigest}},savedContext()),false);
    assert.equal(renderer.matchesContext({...record,test_evidence:{selection:{comparison_id:'test',row_number:2}}},savedContext()),false);
  }
  assert.equal(renderer.matchesContext(null,savedContext()),false);
  assert.equal(renderer.matchesContext(savedTurn(),null),false);
});

test('explicit project requirement identities validate an active head before canonical findings exist',()=>{
  const captures={temperature:{library_digest:digest},pressure:{library_digest:digest}};
  const context=savedContext({scope:'project',requirementId:null,requirementIds:['temperature','pressure']});
  const record=savedTurn({scope:'project',requirement_id:'__project__',state:'running',summary:'',evidence:{project:{linked_sources:captures}}});
  const before=JSON.stringify(context);
  assert.equal(renderer.matchesContext(record,context),true);
  assert.equal(renderer.compatibleParent(record,context),false);
  for(const requirementIds of [null,[],['temperature'],['temperature','pressure','other'],['temperature','temperature'],['temperature',null]])assert.equal(renderer.matchesContext(record,{...context,requirementIds}),false);
  assert.equal(renderer.matchesContext(record,{...context,sourceDigest:otherDigest}),false);
  assert.equal(JSON.stringify(context),before);
});

test('queued project snapshot supports only active exact-context display without full evidence',()=>{
  const context=savedContext({scope:'project',requirementId:null,requirementIds:['pressure','temperature']});
  const queued={schema:'sixd.queued-reference-context.v1',library_digest:digest,requirement_ids:['temperature','pressure']};
  const record=savedTurn({scope:'project',requirement_id:'__project__',state:'queued',summary:'',evidence:{},queued_reference_context:queued});
  for(const state of ['queued','running']){
    assert.equal(renderer.matchesContext({...record,state},context),true);
    assert.equal(renderer.compatibleParent({...record,state},context),false);
  }
  for(const state of ['completed','failed'])assert.equal(renderer.matchesContext({...record,state,summary:'A summary.'},context),false);
  for(const changed of [{schema:'wrong'},{library_digest:otherDigest},{requirement_ids:['temperature']},{requirement_ids:['temperature','temperature']},{requirement_ids:['pressure',null]},{requirement_ids:['pressure','temperature','extra']}])assert.equal(renderer.matchesContext({...record,queued_reference_context:{...queued,...changed}},context),false);
  assert.equal(renderer.matchesContext(record,{...context,sourceDigest:otherDigest}),false);
  assert.equal(renderer.matchesContext({...record,evidence:{project:{linked_sources:{}}}},context),false,'present invalid evidence cannot fall back to queue metadata');
});
