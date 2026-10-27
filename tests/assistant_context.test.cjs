/* Context and reference summaries are pure saved-evidence projections. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../src/sixd/web/assistant-context.js'),'utf8');
const window={};vm.runInNewContext(source,{window});
const {defaultIntent,describe}=window.SixDAssistantContext;
const plain=value=>JSON.parse(JSON.stringify(value));
const requirements=[{id:'thermal',title:'Tank temperature',model_id:'tank'},{id:'thermal_backup',title:'Backup temperature',model_id:'tank_backup'},{id:'tank_margin',title:'Tank margin',model_id:'tank'}];
function saved(){return {project_id:'rocket',revision:3,latest_revision:3,project:{name:'Saved vehicle',requirements:plain(requirements),models:[{id:'tank',title:'Tank thermal model'},{id:'tank_backup'}]},run:{project_id:'rocket',revision:3,run_id:'run-3',review:{findings:{thermal:{status:'not_met'},thermal_backup:{status:'not_assessed'},tank_margin:{status:'met',assessment_status:'insufficient_accuracy'}}}}};}
function profile(){return {project_id:'rocket',revision:3,run_id:'run-3',context:'saved',sources:[{source_id:'unlinked-library-item'}],links:[
  {link_id:'r',target:{target_id:'requirement:thermal',kind:'requirement',id:'thermal'},status:'linked'},
  {link_id:'f',target:{target_id:'finding:thermal',kind:'finding',id:'thermal',run_id:'old-run'},status:'needs_review'},
  {link_id:'a',target:{target_id:'assumption:tank:0',kind:'model_assumption',id:'tank'},status:'target_unavailable'},
  {link_id:'backup',target:{target_id:'requirement:thermal_backup',kind:'requirement',id:'thermal_backup'},status:'linked'},
  {link_id:'backup-model',target:{target_id:'assumption:tank_backup:0',kind:'model_assumption',id:'tank_backup'},status:'linked'},
  {link_id:'wrong-kind',target:{target_id:'assumption:tank:1',kind:'requirement',id:'tank'},status:'linked'},
  {link_id:'wrong-model',target:{target_id:'assumption:tank:2',kind:'model_assumption',id:'tank_backup'},status:'linked'},
  {link_id:'unknown',target:{target_id:'requirement:missing',kind:'requirement',id:'missing'},status:'linked'}]};}
function selection(){return {projectId:'rocket',revision:3,requirementId:'thermal',comparisonId:'comparison-3',rowNumber:7};}
function context(extra={}){return describe({view:saved(),page:'system',scope:'requirement',requirementId:'thermal',testSelection:selection(),sourceProfile:profile(),hasDraft:false,latest:true,...extra});}
function freeze(value){if(value&&typeof value==='object'){for(const item of Object.values(value))freeze(item);Object.freeze(value);}return value;}

test('ordinary opening uses an exact selected system check and defaults other pages to whole project',()=>{
  assert.deepEqual(plain(defaultIntent({page:'system',selected:{kind:'requirement',id:'thermal'},requirements})),{scope:'requirement',requirementId:'thermal'});
  for(const page of ['report','review-home','projects','overview','sources'])assert.deepEqual(plain(defaultIntent({page,selected:{kind:'requirement',id:'thermal'},requirements})),{scope:'project',requirementId:null});
  for(const selected of [null,{kind:'model',id:'thermal'},{kind:'requirement',id:'missing'},{kind:'requirement',id:'therm'}])assert.equal(defaultIntent({page:'system',selected,requirements}).scope,'project');
  assert.equal(defaultIntent().scope,'project');
});

test('description reports the saved project, exact check, model and authoritative finding',()=>{
  const result=context({hasDraft:true,latest:false});
  assert.equal(result.projectId,'rocket');assert.equal(result.revision,3);assert.equal(result.runId,'run-3');assert.equal(result.title,'Saved vehicle');
  assert.equal(result.requirementId,'thermal');assert.equal(result.requirementTitle,'Tank temperature');assert.equal(result.modelId,'tank');assert.equal(result.modelTitle,'Tank thermal model');
  assert.equal(result.findingStatus,'not_met');assert.equal(result.hasDraft,true);assert.equal(result.historical,true);
  assert.equal(context({requirementId:'tank_margin'}).findingStatus,'insufficient_accuracy');
  const missing=context({requirementId:'missing'});assert.equal(missing.requirementId,null);assert.equal(missing.modelId,null);assert.equal(missing.findingStatus,null);assert.equal(missing.references.availableCount,0);
});

test('test summaries include only an exact compatible row and never mutate the selected test',()=>{
  const row=freeze(selection()),result=context({testSelection:row});
  assert.deepEqual(plain(result.testSelection),selection());assert.notEqual(result.testSelection,row);
  for(const changed of [{projectId:'other'},{revision:2},{runId:'old-run'},{requirementId:'thermal_backup'},{comparisonId:''},{rowNumber:0},{rowNumber:1.5},{rowNumber:'7'}])assert.equal(context({testSelection:{...selection(),...changed}}).testSelection,null);
  assert.equal(context({testSelection:{...selection(),runId:'run-3'}}).testSelection.runId,'run-3');
  assert.equal(context({testSelection:{...selection(),runId:'run-3'},view:{...saved(),run:{...saved().run,run_id:'new-run'}}}).testSelection,null,'a selected row is not carried into a replacement calculation');
  assert.equal(context({scope:'project'}).testSelection,null);
  assert.equal(context({requirementId:'thermal_backup'}).testSelection,null);
});

test('reference counts use exact backend targets and separate unresolved links from available references',()=>{
  const result=context().references;
  assert.equal(result.state,'ready');assert.equal(result.availableCount,1);assert.equal(result.needsReviewCount,1);assert.equal(result.unavailableCount,1);
  assert.match(result.summary,/1 linked reference available in this scope/);assert.match(result.summary,/1 need review/);assert.match(result.summary,/Capture limits apply/);
  assert.doesNotMatch(result.summary,/all.*sent|all.*included/i);
  assert.equal(context({scope:'project'}).references.availableCount,3,'shared model links count once, and unresolved/unlinked sources or unknown targets do not count');
  assert.equal(context({requirementId:'thermal_backup'}).references.availableCount,2,'similar requirement and model IDs cannot leak into scope');
});

test('stale project, revision, run and non-saved source profiles never become a current count',()=>{
  for(const changed of [{project_id:'other'},{revision:2},{run_id:'old-run'},{context:'draft'},{links:null}]){
    const result=context({sourceProfile:{...profile(),...changed}}).references;
    assert.equal(result.state,'unavailable');assert.equal(result.availableCount,null);assert.equal(result.needsReviewCount,null);assert.match(result.summary,/not loaded/);
  }
  assert.equal(context({sourceProfile:null}).references.state,'unavailable');
});

test('page changes and draft display do not change evidence history identity',()=>{
  const original=context(),moved=context({page:'report',hasDraft:true,latest:false});
  assert.equal(original.historyKey,moved.historyKey);assert.notEqual(original.page,moved.page);
  for(const extra of [{scope:'project'},{requirementId:'thermal_backup'},{testSelection:null},{view:{...saved(),revision:4}},{view:{...saved(),run:{...saved().run,run_id:'new-run'}}}])assert.notEqual(original.historyKey,context(extra).historyKey);
});

test('describing frozen snapshots and repeated reads leaves all supplied records unchanged',()=>{
  const input={view:saved(),page:'system',scope:'requirement',requirementId:'thermal',testSelection:selection(),sourceProfile:profile(),hasDraft:true,latest:false};
  const before=plain(input);freeze(input);
  const first=describe(input),second=describe(input);assert.deepEqual(plain(first),plain(second));assert.deepEqual(plain(input),before);
  first.testSelection.rowNumber=999;first.references.availableCount=999;assert.deepEqual(plain(input),before);assert.equal(describe(input).testSelection.rowNumber,7);
});

test('missing or mismatched saved runs disclose absence rather than borrowing another receipt',()=>{
  for(const run of [null,{...saved().run,project_id:'other'},{...saved().run,revision:2}]){
    const result=context({view:{...saved(),run}});assert.equal(result.runId,null);assert.equal(result.findingStatus,null);assert.equal(result.references.state,'unavailable');
  }
  const empty=describe();assert.equal(empty.projectId,null);assert.equal(empty.title,'Choose a project');assert.equal(empty.testSelection,null);assert.equal(empty.references.state,'unavailable');
});
