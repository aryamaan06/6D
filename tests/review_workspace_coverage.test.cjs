/* Overview count semantics against captured read-only summaries. No server or service calls. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../src/sixd/web/review-workspace.js'),'utf8');
const unitsSource=fs.readFileSync(path.join(__dirname,'../src/sixd/web/units.js'),'utf8');

function snapshot(counts,checks){
  const findings=[];
  for(const [status,count] of Object.entries(counts))for(let i=0;i<count;i++)findings.push({requirement_id:status+'-'+i,title:status+' criterion '+i,status,model_id:'model',reason:'Saved calculation reason.'});
  return {schema:'sixd.review-workspace.v1',project_id:'coverage-case',project_name:'Constructed coverage case',revision:1,latest_revision:1,run_id:'saved-run',counts,findings,models:[{id:'model'}],coverage:{checks},actions:{actions:[]},sources:{links:[]},simulations:{},limitations:[]};
}
async function render(data,extra={}){
  const window={},targets=new Map([['[data-rw-findings]',{innerHTML:''}],['[data-rw-match-count]',{textContent:''}]]);
  const host={addEventListener(){},removeEventListener(){},innerHTML:'',querySelector:selector=>targets.get(selector)||null,querySelectorAll:()=>[],contains:()=>true,replaceChildren(){this.innerHTML='';}};
  const navigation=[],requests=[];
  vm.runInNewContext(unitsSource,{window});
  vm.runInNewContext(source,{window,AbortController,encodeURIComponent});
  window.SixDReviewWorkspace.mount(host,{projectId:data.project_id,revision:data.revision,currentRunId:data.run_id,onNavigate:route=>navigation.push(route),onRun:()=>{},api:async(...args)=>{requests.push(args[0]);return data;},...extra});
  await new Promise(resolve=>setImmediate(resolve));
  const click=dataset=>{const element={dataset,disabled:false};host.onclick({target:{closest:()=>element}});};
  return {host,navigation,requests,click,findings:targets.get('[data-rw-findings]'),unmount:()=>window.SixDReviewWorkspace.unmount()};
}
function count(html,status){
  const result=html.match(new RegExp('class="rw-count rw-count-'+status+'"[^>]*><span class="rw-count-value">([^<]+)</span>'));
  assert.ok(result,'Missing canonical '+status+' count');return result[1];
}
const coveragePanel=html=>html.match(/<section class="rw-coverage-context"[\s\S]*?<\/section>/)?.[0]||'';

test('rounded equal-looking values retain the original unmet finding and expandable exact evidence',async()=>{
  const data=snapshot({met:0,not_met:1,not_assessed:0,not_run:0},[]),row=data.findings[0];
  row.metric={value:1.00000004,unit:'m^2'};row.limit={value:1,unit:'m^2'};row.operator='<=';
  const before=JSON.stringify(data),view=await render(data);
  assert.match(view.findings.innerHTML,/rw-not_met/);assert.match(view.findings.innerHTML,/1 m²/);
  assert.match(view.findings.innerHTML,/Values are rounded for reading/);
  view.click({rwRequirement:row.requirement_id});
  const exact=view.findings.innerHTML.match(/data-exact-values>[\s\S]*?<\/dl>/)?.[0]||'';
  assert.match(exact,/1\.00000004 m²/);assert.match(exact,/1 m²/);assert.equal(JSON.stringify(data),before);view.unmount();
});

test('nine met criteria and ten missing fit declarations remain distinct with an actionable reason',async()=>{
  const checks=Array.from({length:10},(_,i)=>({row_id:'requirement:'+i,coverage_status:'applicability_unknown',criterion_status:i===9?'not_assessed':'met',reason:'Model applicability has not been declared. A numerical result cannot resolve this gap.'}));
  const data=snapshot({met:9,not_met:0,not_assessed:1,not_run:0},checks),before=JSON.stringify(data),view=await render(data);
  assert.equal(count(view.host.innerHTML,'met'),'9');assert.equal(count(view.host.innerHTML,'not_met'),'0');assert.equal(count(view.host.innerHTML,'not_assessed'),'1');
  const panel=coveragePanel(view.host.innerHTML);
  assert.match(panel,/10 scope checks · 10 need attention/);
  assert.match(panel,/data-rw-coverage-status="applicability_unknown"><dt><span>10<\/span> Model fit not declared/);
  assert.match(panel,/A met numerical criterion cannot resolve a missing model-fit declaration/);
  assert.match(panel,/Review whether the model assumptions fit the intended use/);
  assert.match(panel,/data-rw-nav="coverage"/);
  view.click({rwNav:'coverage'});assert.deepEqual(view.navigation,['coverage']);
  assert.equal(view.requests.length,1);assert.match(view.requests[0],/^\/api\/review-workspace\?/);assert.equal(JSON.stringify(data),before);
  view.unmount();
});

test('supplied exclusion and outside-assumptions context never remove or manufacture numerical findings',async()=>{
  const data=snapshot({met:1,not_met:1,not_assessed:0,not_run:0},[
    {coverage_status:'excluded',criterion_status:'not_met',reason:'Excluded by supplied rationale; finding unchanged.'},
    {coverage_status:'outside_assumptions',criterion_status:'met',reason:'Transient conditions are outside this steady model.'}
  ]),view=await render(data),panel=coveragePanel(view.host.innerHTML);
  assert.equal(count(view.host.innerHTML,'met'),'1');assert.equal(count(view.host.innerHTML,'not_met'),'1');assert.equal(count(view.host.innerHTML,'not_assessed'),'0');
  assert.match(panel,/2 scope checks · 1 needs attention/);
  assert.match(panel,/data-rw-coverage-status="outside_assumptions"><dt><span>1<\/span> Outside model assumptions/);
  assert.match(panel,/data-rw-coverage-status="excluded"><dt><span>1<\/span> Excluded by supplied rationale/);
  assert.match(panel,/Any linked calculated finding remains unchanged/);
  assert.doesNotMatch(panel,/data-rw-coverage-status="applicability_unknown"/);
  assert.match(view.findings.innerHTML,/rw-not_met/);assert.match(view.findings.innerHTML,/rw-met/);
  view.unmount();
});

test('fit declarations are unverified context and additional checks explain unequal totals',async()=>{
  const data=snapshot({met:1,not_met:0,not_assessed:0,not_run:0},[
    {coverage_status:'criterion_met',criterion_status:'met'},
    {coverage_status:'missing_analysis',criterion_status:null},
    {coverage_status:'undecided',criterion_status:null},
    {coverage_status:'needs_review',criterion_status:'met',needs_review:true}
  ]),view=await render(data),panel=coveragePanel(view.host.innerHTML);
  assert.equal(count(view.host.innerHTML,'met'),'1');assert.match(panel,/4 scope checks · 3 need attention/);
  assert.match(panel,/Criterion met with supplied fit declaration/);assert.match(panel,/The supplied fit declaration remains unverified/);
  assert.match(panel,/Analysis missing or unsupported/);assert.match(panel,/Scope undecided/);assert.match(panel,/Declaration context changed/);
  assert.match(panel,/total may differ from requirement findings/);assert.match(panel,/not a mission-completeness measure/);
  view.unmount();
});

test('an uncalculated revision retains no numerical counts and the explicit run callback',async()=>{
  const data=snapshot({met:0,not_met:0,not_assessed:0,not_run:1},[{coverage_status:'applicability_unknown',criterion_status:null}]);data.run_id=null;
  let runs=0;const view=await render(data,{onRun:()=>runs++});
  assert.equal(count(view.host.innerHTML,'met'),'—');assert.equal(count(view.host.innerHTML,'not_assessed'),'—');
  assert.match(view.host.innerHTML,/1 requirements not calculated/);assert.match(coveragePanel(view.host.innerHTML),/1 scope check · 1 needs attention/);
  view.click({rw:'run'});assert.equal(runs,1);assert.equal(view.requests.length,1);
  view.unmount();
});
