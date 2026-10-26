/* Tool availability is a saved-project display decision; no server or providers. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../src/sixd/web/workspace-shell.js'),'utf8');
const definitions=[
  ['vertical','powered_flight','flight_response','vertical-mode'],
  ['planar','guided_ascent','guided_response','guided-ascent'],
  ['staged','staged_ascent','staged_response','staged-ascent'],
  ['orbit','orbital_trajectory','simulation','simulation'],
  ['power','power_energy_budget','power_budget','power'],
  ['pointing','attitude_control','attitude_response','attitude']
];
function shell(){
  const elements=new Map();
  const document={title:'',querySelector(selector){
    if(!elements.has(selector))elements.set(selector,{innerHTML:'',textContent:'',hidden:false,disabled:false,dataset:{},classList:{toggle(){}}});
    return elements.get(selector);
  }};
  const window={};vm.runInNewContext(source,{window,document});
  return {api:window.SixDWorkspaceShell,document};
}
function view(id='rocket',rows=[definitions[0]],revision=1){
  return {schema:'sixd.workspace.v1',project_id:id,revision,latest_revision:revision,
    project:{project_id:id,name:id,revision:String(revision),models:rows.map(([id,type])=>({id,type,inputs:{}}))},run:null,prior_run:null};
}
function calculate(data,rows=definitions){
  data.run={schema:'sixd.workspace-run.v1',project_id:data.project_id,revision:data.revision,run_id:'run-'+data.project_id+'-'+data.revision,stale:false,
    review:{digest:'saved-review-digest',project:JSON.parse(JSON.stringify(data.project))},model_results:Object.fromEntries(rows.filter(([id])=>data.project.models.some(model=>model.id===id)).map(([id,type,artifact])=>[id,{model_id:id,model_type:type,status:'completed',[artifact]:{schema:'saved-artifact'}}]))};
  return data;
}
const status=(api,data,action)=>api.toolSummary(data).byAction[action];

test('a vertical project distinguishes saved flight evidence from unconfigured tools and unsupported GNC',()=>{
  const {api}=shell(),data=calculate(view());
  data.project.models.push({id:'launch_guidance',type:'unsupported_closed_loop_gnc',inputs:{}});
  data.run.model_results.launch_guidance={model_id:'launch_guidance',model_type:'unsupported_closed_loop_gnc',status:'not_assessed'};
  assert.equal(status(api,data,'vertical-mode').state,'recorded');
  for(const action of ['guided-ascent','staged-ascent','simulation','power','attitude']){
    assert.equal(status(api,data,action).state,'unconfigured',action);
    assert.equal(status(api,data,action).recorded,0,action);
  }
  const html=api.hub('analysis',[],data.project_id,api.toolSummary(data));
  assert.match(html,/Recorded calculation/);
  assert.match(html,/Not configured for this project/);
  for(const action of ['vertical-mode','guided-ascent','staged-ascent','simulation'])assert.match(html,new RegExp('data-action="'+action+'"'));
  assert.doesNotMatch(html,/ disabled|validated|mission ready/i);
  const engineering=api.hub('engineering',[],data.project_id,api.toolSummary(data));
  assert.equal((engineering.match(/Not configured for this project<\/span>/g)||[]).length,2);
});

test('each supported model is configured before calculation and recorded only with its matching completed result',()=>{
  const {api}=shell(),data=view('mixed',definitions);
  for(const [,,,action] of definitions){
    assert.equal(status(api,data,action).state,'configured',action);
    assert.equal(status(api,data,action).recorded,0,action);
  }
  calculate(data);
  for(const [,,,action] of definitions){
    assert.equal(status(api,data,action).state,'recorded',action);
    assert.equal(status(api,data,action).recorded,1,action);
  }
  delete data.run.model_results.orbit.simulation;
  data.run.model_results.planar.model_type='powered_flight';
  data.run.model_results.pointing.model_id='other';
  for(const action of ['simulation','guided-ascent','attitude'])assert.equal(status(api,data,action).recorded,0,action);
});

test('blocked and partially completed models never advertise all configured models as calculated',()=>{
  const {api}=shell(),data=calculate(view('mixed',definitions));
  data.run.model_results.power={model_id:'power',model_type:'power_energy_budget',status:'invalid_inputs',issues:['Input outside the supported bound.']};
  data.run.model_results.pointing={model_id:'pointing',model_type:'attitude_control',status:'not_assessed',issues:['Upstream result unavailable.']};
  assert.equal(status(api,data,'power').state,'blocked');
  assert.equal(status(api,data,'attitude').state,'blocked');
  data.project.models.push({id:'power_backup',type:'power_energy_budget',inputs:{}});
  data.run.model_results.power_backup={model_id:'power_backup',model_type:'power_energy_budget',status:'completed',power_budget:{schema:'saved-artifact'}};
  const power=status(api,data,'power');
  assert.equal(power.state,'partial');assert.equal(power.configured,2);assert.equal(power.recorded,1);assert.equal(power.blocked,1);
  assert.match(power.detail,/2 configured models · 1 completed result/);
});

test('historical receipt context is retained and older or stale receipts do not count for an uncalculated revision',()=>{
  const {api}=shell(),historical=calculate(view('rocket',definitions,1));
  historical.latest_revision=2;
  assert.equal(api.toolSummary(historical).historical,true);
  const historicalHtml=api.hub('analysis',[],'rocket',api.toolSummary(historical));
  assert.match(historicalHtml,/Saved R1 · Historical revision; latest is R2/);
  assert.equal(status(api,historical,'simulation').recorded,1);
  const latest=view('rocket',definitions,2);latest.prior_run=historical.run;
  const latestSummary=api.toolSummary(latest,{hasDraft:true});
  assert.equal(latestSummary.byAction.simulation.state,'configured');
  const html=api.hub('analysis',[],'rocket',latestSummary);
  assert.match(html,/Earlier calculation for R1 is retained in history and is not counted here/);
  assert.match(html,/Draft edits have not been calculated/);
  latest.run=historical.run;
  assert.equal(status(api,latest,'simulation').recorded,0,'receipt from an earlier revision');
  calculate(latest);latest.run.stale=true;
  assert.equal(status(api,latest,'simulation').recorded,0,'stale receipt');
  latest.run.stale=false;latest.run.project_id='other';
  assert.equal(status(api,latest,'simulation').recorded,0,'receipt from another project');
});

test('project switches replace card and navigation status without retaining previous evidence badges',()=>{
  const {api,document}=shell(),first=calculate(view('first',definitions)),second=view('second',[]);
  const firstSummary=api.toolSummary(first),secondSummary=api.toolSummary(second);
  const chrome=data=>({page:'simulation',project:data.project,revision:data.revision,backEnabled:true,tools:api.toolSummary(data)});
  api.renderChrome(chrome(first));
  assert.match(document.querySelector('#sd-section-menu').innerHTML,/Recorded · R1/);
  api.renderChrome(chrome(second));
  const nav=document.querySelector('#sd-section-menu').innerHTML;
  assert.doesNotMatch(nav,/Recorded ·/);
  assert.match(nav,/Not configured/);
  assert.match(nav,/data-action="simulation" aria-current="page"/);
  const secondHtml=api.hub('analysis',[],'second',secondSummary);
  assert.doesNotMatch(secondHtml,/Recorded calculation/);
  assert.equal((secondHtml.match(/Not configured for this project<\/span>/g)||[]).length,4);
  assert.doesNotMatch(api.hub('analysis',[],'second',firstSummary),/Recorded calculation/,'wrong-project summaries are discarded');
  api.renderChrome({...chrome(second),tools:firstSummary});
  assert.doesNotMatch(document.querySelector('#sd-section-menu').innerHTML,/Recorded ·/);
  api.renderChrome({...chrome(first),revision:2,tools:firstSummary});
  assert.doesNotMatch(document.querySelector('#sd-section-menu').innerHTML,/Recorded ·/,'wrong-revision summaries are discarded');
});
