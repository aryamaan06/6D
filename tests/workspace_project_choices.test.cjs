/* Project labels clarify saved identities without changing records or routes. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../src/sixd/web/workspace-shell.js'),'utf8');
function shell(){const window={};vm.runInNewContext(source,{window});return window.SixDWorkspaceShell;}
const plain=value=>JSON.parse(JSON.stringify(value));
const project=(project_id,name='Rocket reference',extra={})=>({project_id,name,revision:3,...extra});

test('exact, case and whitespace name collisions receive distinct actual-ID labels',()=>{
  const api=shell(),rows=[project('record-one-123456'),project('record-two-123456','rocket REFERENCE'),
    project('record-three-123456','  Rocket   reference  '),project('unique-record','Other design')];
  const choices=api.projectChoices(rows);
  assert.equal(new Set(choices.map(row=>row.display_name.trim().toLowerCase())).size,rows.length);
  for(let index=0;index<3;index++){
    const row=choices[index],suffix=row.identity_label.replace(/^…/,'');
    assert.ok(row.project_id.endsWith(suffix));
    assert.ok(suffix.length>6,'the common last six ID characters cannot distinguish these records');
    assert.equal(row.display_name,rows[index].name+' · '+row.identity_label);
  }
  assert.equal(choices[3].display_name,'Other design');
});

test('ID suffix collisions extend deterministically and do not depend on list order',()=>{
  const api=shell(),rows=[project('abc-abcdef'),project('xyz-abcdef'),project('abcdef')];
  const forward=api.projectChoices(rows),reverse=api.projectChoices([...rows].reverse());
  const labels=Object.fromEntries(forward.map(row=>[row.project_id,row.display_name]));
  assert.deepEqual(Object.fromEntries(reverse.map(row=>[row.project_id,row.display_name])),labels);
  assert.equal(new Set(forward.map(row=>row.identity_label)).size,3);
  assert.equal(forward.find(row=>row.project_id==='abcdef').identity_label,'abcdef','a short complete ID stays accessible');
  for(const row of forward)assert.ok(row.project_id.endsWith(row.identity_label.replace(/^…/,'')));
  assert.deepEqual(plain(forward.map(row=>row.project_id)),rows.map(row=>row.project_id),'returned order stays unchanged');
});

test('display metadata leaves original project fields and nested model records unchanged',()=>{
  const api=shell(),rows=[project('frozen-id-a','Preserved name',{created_at:'2026-10-26T12:34:56Z',models:[{id:'flight',type:'powered_flight'}]}),
    project('frozen-id-b','Preserved name')];
  const before=plain(rows);
  for(const row of rows){if(row.models){Object.freeze(row.models[0]);Object.freeze(row.models);}Object.freeze(row);}
  Object.freeze(rows);
  const choices=api.projectChoices(rows);
  assert.deepEqual(plain(rows),before);
  for(let index=0;index<rows.length;index++){
    assert.notEqual(choices[index],rows[index]);
    for(const field of Object.keys(rows[index]))assert.equal(choices[index][field],rows[index][field],field);
  }
  assert.equal(choices[0].name,'Preserved name');
  assert.equal(choices[0].revision,3);
  assert.equal(choices[0].project_id,'frozen-id-a');
});

test('cards render supplied hints only and retain IDs, revisions, current selection and start actions',()=>{
  const api=shell(),rows=[project('powered-reference-a','Repeated test',{created_at:'2026-10-26T12:34:56+00:00',
    project_type:'space_vehicle',lifecycle_stage:'design',model_types:['powered_flight','drag_load','powered_flight']}),
    project('powered-reference-b','Repeated test'),project('plain-design','Only a name',{created_at:'not a timestamp'})];
  const html=api.hub('projects',rows,'powered-reference-b');
  assert.equal((html.match(/class="sd-project-card"/g)||[]).length,rows.length);
  for(const row of rows){
    assert.ok(html.includes('data-open-project="'+row.project_id+'"'));
    assert.ok(html.includes('title="Project ID: '+row.project_id+'"'));
    assert.ok(html.includes('Project ID: '+row.project_id+'"'));
  }
  assert.equal((html.match(/Saved project · Current/g)||[]).length,1);
  assert.equal((html.match(/Revision R3<|Revision R3 ·/g)||[]).length,6);
  assert.match(html,/Type: space vehicle · Stage: design · Model types: drag load, powered flight/);
  assert.match(html,/Created 2026-10-26 12:34 UTC/);
  assert.equal((html.match(/class="sd-project-hint"/g)||[]).length,1,'missing payload hints stay absent');
  assert.doesNotMatch(html,/Invalid Date|not a timestamp|calculated|verified|archive|delete/i);
  for(const action of ['rocket-reference','new-project','import'])assert.ok(html.includes('data-action="'+action+'"'));
});

test('project names, IDs and optional model hints are escaped in card text and attributes',()=>{
  const api=shell(),id='record-"<id>&\'',name='<script>alert("saved")</script> & \'design\'';
  const html=api.hub('projects',[project(id,name,{models:[{type:'<model_type> & "fit"'}]})],id);
  assert.doesNotMatch(html,/<script>|<id>|<model/);
  assert.ok(html.includes('data-open-project="record-&quot;&lt;id&gt;&amp;&#39;"'));
  assert.ok(html.includes('title="Project ID: record-&quot;&lt;id&gt;&amp;&#39;"'));
  assert.ok(html.includes('&lt;script&gt;alert(&quot;saved&quot;)&lt;/script&gt; &amp; &#39;design&#39;'));
  assert.ok(html.includes('Model type: &lt;model type&gt; &amp; &quot;fit&quot;'));
});

test('missing or blank names use the actual ID and empty project lists keep new-project actions',()=>{
  const api=shell(),choices=api.projectChoices([project('complete-identity',''),project('second-identity','  ')]);
  assert.equal(choices[0].display_name,'complete-identity');
  assert.equal(choices[1].display_name,'second-identity');
  const html=api.hub('projects',[],null);
  assert.doesNotMatch(html,/class="sd-project-card"/);
  assert.match(html,/data-action="new-project"/);
});
