/* Focus Build 2 acceptance on isolated synthetic owner + visitor servers.
 * Run from the repository root: node tools/check_focus_build2_browser.mjs
 * Never opens founder data, credentials or provider networks. */
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdir,mkdtemp,readFile,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';

const root=process.cwd(),output=resolve(root,'work/focus-build2-browser');await mkdir(output,{recursive:true});
const fixture=await mkdtemp(join(output,'fixture-'));
let playwright;try{playwright=await import(process.env.PLAYWRIGHT_MODULE||'playwright');}catch(error){if(process.env.PLAYWRIGHT_MODULE)throw error;playwright=await import('file:///C:/Users/Arya/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs');}
const python=process.env.SIXD_TEST_PYTHON||(process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
const source=`import json,os,sys,socket,threading,time
from pathlib import Path
from dataclasses import asdict
sys.path[:0]=[str(Path.cwd()/'src'),str(Path.cwd()/'tests')]
from sixd.providers import LiveConfig,TokenFactoryProvider
from sixd.project_investigation import ProjectActionAdapter
from sixd.workspace_server import create_server
from sixd.project_examples import example_projects
from sixd.hosted_server import HostedConfig,create_hosted_server
from test_workspace_ai_api import offline_transport
from test_whole_project_investigation import SUMMARY
folder=Path(sys.argv[1]);calls=folder/'calls.jsonl'
for key in ('NEBIUS_API_KEY','TAVILY_API_KEY','LANGSMITH_API_KEY'):os.environ.pop(key,None)
config=LiveConfig('https://api.tokenfactory.nebius.com/v1/','nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B','offline-rocket-browser',29.5,.06,.24,2048,45,'native_no_thinking','forced_action_v1')
(folder/'token-factory.json').write_text(json.dumps({**asdict(config),'account_verified':True,'model_license_reviewed':True,'spend_approved':True}),encoding='utf-8')
def log(value):
 with calls.open('a',encoding='utf-8') as handle:handle.write(json.dumps(value)+'\\n')
def transport(request):
 payload=json.loads(request.data);menu=json.loads(payload['messages'][-1]['content']);actions=[x['action'] for x in menu['available_actions']]
 log({'service':'nemotron','model':payload['model'],'actions':actions})
 if any(x in ('read_project','read_dependencies') for x in actions) or 'project' in menu.get('recorded_evidence_ids',[]):
  action=actions[0];args={'action':action,'evidence_ids':menu['recorded_evidence_ids'] if action=='finish' else [],'summary':SUMMARY if action=='finish' else ''}
  return {'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':None,'tool_calls':[{'id':'offline-rocket-'+action,'type':'function','function':{'name':'select_next_action','arguments':json.dumps(args)}}]}}],'usage':{'prompt_tokens':500,'completion_tokens':60,'total_tokens':560}}
 return offline_transport(request)
def factory(config,ledger,key):return TokenFactoryProvider(config,ledger,api_key=key,transport=transport,action_adapter=ProjectActionAdapter())
def research(key,body):
 log({'service':'tavily','query':body['query']})
 return {'request_id':'synthetic-rocket-search','usage':{'credits':1},'results':[{'title':'Constructed spacecraft reference','url':'https://www.nasa.gov/example/rocket-browser-reference','content':'A synthetic test excerpt, not a verified NASA statement. Review model assumptions independently.','score':.8}]}
def forbidden(*args,**kwargs):raise AssertionError('Rocket acceptance must not upload external metrics')
owner=create_server(port=0,db_path=folder/'owner.sqlite3',ai_local_directory=folder,provider_factory=factory,research_transport=research,observability_transport=forbidden)
p=example_projects()['rocket_review'];p.update(project_id='rocket-review',name='Rocket usability walkthrough (constructed)',revision='1')
owner.store.create_project(p);owner.store.run(p['project_id'],1);owner.store.ensure_default=lambda:p['project_id']
for key in ('orbital_review','guided_ascent_review','staged_ascent_review'):
 extra=example_projects()[key];extra['project_id']='focus-'+key;owner.store.create_project(extra);owner.store.run(extra['project_id'],1)
baseline=owner.store.get(p['project_id'])['run']['run_id']
scenario=owner.scenarios.run(p['project_id'],1,baseline,dict(schema='sixd.scenario-spec.v1',name='Constructed heat cases',source='Synthetic disclosure acceptance, not flight data.',mode='sweep',input_id='heat_input',values=[100,700]))
envelope=owner.scenarios.run(p['project_id'],1,baseline,dict(schema='sixd.envelope-spec.v1',name='Constructed heat grid',source='Synthetic disclosure acceptance, not flight data.',mode='grid',axes=[dict(input_id='heat_input',minimum=100,maximum=700,points=2)]))
owner.ai.connect('synthetic-rocket-key-never-network');owner.research.connect('synthetic-usability-research-key-only',1)
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
visitor_origin='http://127.0.0.1:'+str(port)
visitor=create_hosted_server(HostedConfig(folder/'visitors',visitor_origin,'synthetic-rocket-invitation-no-real-secret',allow_loopback_http=True,get_limit=600,post_limit=100,login_limit=100),port=port)
threads=[threading.Thread(target=server.serve_forever,daemon=True) for server in (owner,visitor)]
for thread in threads:thread.start()
print(json.dumps({'owner':'http://127.0.0.1:'+str(owner.server_port),'visitor':visitor_origin,'project_id':p['project_id'],'scenario_id':scenario['receipt']['study_id'],'envelope_id':envelope['receipt']['study_id']}),flush=True)
try:
 while True:time.sleep(1)
finally:
 for server in (owner,visitor):server.shutdown();server.server_close()
`;
const child=spawn(python,['-u','-c',source,fixture],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
let stderr='';child.stderr.on('data',chunk=>stderr+=chunk);let browser,page,releaseResearchProfile;
const checks=[],errors=[],external=[],failures=[],badResponses=[],posts=[];
const pass=message=>{checks.push(message);console.log('PASS '+message);};
const callLog=async()=>{try{return(await readFile(join(fixture,'calls.jsonl'),'utf8')).trim().split('\n').filter(Boolean).map(line=>JSON.parse(line));}catch(error){if(error.code==='ENOENT')return[];throw error;}};
try{
 const info=await new Promise((yes,no)=>{let raw='';const timer=setTimeout(()=>no(Error('Fixture startup timeout: '+stderr)),90000);child.stdout.on('data',chunk=>{raw+=chunk;try{const data=JSON.parse(raw.split('\n')[0]);clearTimeout(timer);yes(data);}catch{}});child.once('exit',code=>{clearTimeout(timer);no(Error('Fixture exited '+code+': '+stderr));});});
 browser=await playwright.chromium.launch({channel:process.env.SIXD_BROWSER_CHANNEL||'chrome',headless:true,args:['--enable-unsafe-swiftshader']});
 const context=await browser.newContext({viewport:{width:1512,height:1060}}),allowed=new Set([info.owner,info.visitor]);
 await context.route('**/*',route=>{if(!allowed.has(new URL(route.request().url()).origin)){external.push(route.request().url());return route.abort();}return route.continue();});
 const observe=p=>{p.setDefaultTimeout(25000);p.on('pageerror',error=>errors.push(error.stack||error.message));p.on('requestfailed',r=>failures.push({path:new URL(r.url()).pathname,error:r.failure()?.errorText}));p.on('request',r=>{if(r.method()==='POST')posts.push({origin:new URL(r.url()).origin,path:new URL(r.url()).pathname,data:r.postDataJSON()});});p.on('response',r=>{if(allowed.has(new URL(r.url()).origin)&&r.status()>=400)badResponses.push({path:new URL(r.url()).pathname,status:r.status()});});};
 page=await context.newPage();observe(page);
 const api=async(origin,path)=>{const response=await context.request.get(origin+path);assert.equal(response.status(),200,await response.text());return response.json();};
 const savedPath='/api/workspace?project_id='+info.project_id+'&revision=1';
 const sourcePath='/api/sources?project_id='+info.project_id+'&revision=1';
 const before=await api(info.owner,savedPath),beforeSources=await api(info.owner,sourcePath),beforeStatus=await api(info.owner,'/api/ai/status');

 const originalView=value=>{const {latest_revision,revisions,...identity}=value;return identity;};
 const idle=()=>page.locator('#sixd-workspace[aria-busy="false"]').waitFor();
 const click=async action=>{await page.locator('[data-action="'+action+'"]:visible').first().click();await idle();};
 const review=async revision=>{await page.goto(info.owner+'/#/projects/'+info.project_id+'/r/'+revision+'/review-home');await idle();await page.locator('.rw-workspace[aria-busy="false"]').waitFor();};
 await review(1);
 assert.equal(await page.locator('.rw-verdict').isVisible(),true);assert.match(await page.locator('.rw-verdict').innerText(),/check|criteria/);
 assert.equal(await page.locator('[data-rw="edit-thrust"]').isVisible(),true);
 for(const key of ['workflow','reference','meaning','attention','coverage'])assert.equal(await page.locator('[data-rw-disclosure="'+key+'"]').evaluate(node=>node.open),false);
 const topVerdict=await page.locator('.rw-verdict').boundingBox();assert.ok(topVerdict.y<550);
 await page.screenshot({path:join(output,'overview.png')});
 pass('Overview begins with its canonical conclusion, counts and editable current thrust; secondary workflows and explanations are closed');
 const firstCheck=page.locator('[data-rw-requirement="burnout_height"]');await firstCheck.click();
 assert.equal(await page.locator('.rw-inline-detail').isVisible(),true);assert.ok((await page.locator('[data-exact-values]').innerText()).includes(String(before.run.review.findings.burnout_height.evidence.metric.value)));
 await page.locator('[data-rw-disclosure="meaning"] > summary').click();await page.locator('[data-rw="refresh"]').click();await page.locator('.rw-workspace[aria-busy="false"]').waitFor();
 assert.equal(await page.locator('[data-rw-disclosure="meaning"]').evaluate(node=>node.open),true);
 pass('A selected result explains itself immediately below its row with exact values; a same-context refresh retains chosen disclosures');
 await page.locator('[data-rw="edit-thrust"]').click();await page.locator('#sd-thrust-dialog[open]').waitFor();
 for(const value of ['','0','-1']){await page.locator('#sd-thrust-value').fill(value);await page.locator('#sd-thrust-form button[type="submit"]').click();assert.match(await page.locator('#sd-thrust-error').innerText(),/greater than zero/);assert.equal(posts.filter(item=>item.path==='/api/impact').length,0);}
 await page.locator('#sd-thrust-value').fill('17500');await page.locator('#sd-thrust-source').fill('Constructed 17500 N browser change; not measured hardware.');
 page.once('dialog',dialog=>dialog.dismiss());await page.locator('[data-action="close-thrust"]').last().click();assert.equal(await page.locator('#sd-thrust-dialog').evaluate(node=>node.open),true);assert.equal(await page.locator('#sd-thrust-value').inputValue(),'17500');
 const impact=page.waitForResponse(response=>response.url()===info.owner+'/api/impact'&&response.request().method()==='POST');await page.locator('#sd-thrust-form button[type="submit"]').click();assert.equal((await impact).status(),200);
 await page.locator('#sd-thrust-dialog').waitFor({state:'hidden'});await idle();assert.equal(await page.locator('#sd-draft-strip').isVisible(),true);
 assert.equal(posts.filter(item=>['/api/run','/api/revisions'].includes(item.path)).length,0);assert.deepEqual(originalView(await api(info.owner,savedPath)),originalView(before));
 pass('Positive custom thrust and its source stage only an unsaved draft; invalid values and cancelled dismissal preserve the original design');
 const saved=page.waitForResponse(response=>response.url()===info.owner+'/api/revisions'&&response.request().method()==='POST');await click('save');assert.equal((await saved).status(),200);
 assert.equal(await page.locator('#sd-revision-picker').inputValue(),'2');assert.equal(posts.filter(item=>item.path==='/api/run').length,0);
 const run=page.waitForResponse(response=>response.url()===info.owner+'/api/run'&&response.request().method()==='POST');await click('run');assert.equal((await run).status(),200);
 await review(2);const changed=await api(info.owner,'/api/workspace?project_id='+info.project_id+'&revision=2');assert.equal(changed.project.inputs.thrust.value,17500);assert.deepEqual(originalView(await api(info.owner,savedPath)),originalView(before));
 assert.equal(await page.locator('[data-rw="edit-thrust"]').isVisible(),true);assert.match(await page.locator('.rw-thrust').innerText(),/17,500/);assert.equal(changed.run.review.project.inputs.thrust.value,17500);
 pass('Save and recalculate are separate actions; custom thrust remains visible/editable after leaving the prepared example and old evidence is unchanged');
 await click('evidence');await click('report');await page.locator('.sd-reader').waitFor();
 assert.equal(await page.locator('[data-disclosure-key*="report-graphs"]').evaluate(node=>node.open),false);assert.equal(await page.locator('[data-disclosure-key*="report-models"]').evaluate(node=>node.open),false);
 const reportChecks=page.locator('details.sd-result-disclosure');assert.equal(await reportChecks.count(),changed.project.requirements.length);
 await reportChecks.first().locator(':scope > summary').click();assert.ok((await reportChecks.first().innerText()).length>100);
 const closedCount=await page.locator('.sd-reader details:not([open])').count();assert.ok(closedCount>5);
 await page.evaluate(()=>dispatchEvent(new Event('beforeprint')));assert.equal(await page.locator('.sd-reader details:not([open])').count(),0);
 await page.evaluate(()=>dispatchEvent(new Event('afterprint')));assert.equal(await page.locator('.sd-reader details:not([open])').count(),closedCount);
 const projectExport=page.waitForEvent('download');await page.locator('[data-action="export-project"]:visible').first().click();assert.deepEqual(JSON.parse(await readFile(await (await projectExport).path(),'utf8')),changed.project);
 pass('Report results expand individually, full print reveals every nested detail then restores it, and project export retains exact original values');
 await review(1);assert.equal(await page.locator('[data-rw="edit-thrust"]').isEnabled(),false);assert.match(await page.locator('.rw-thrust').innerText(),/read-only/);
 assert.equal((await api(info.owner,'/api/ai/status')).budget.cap_usd,beforeStatus.budget.cap_usd);
 assert.equal(posts.filter(item=>/investigations|research\/search|observability/.test(item.path)).length,0);assert.deepEqual(external,[]);assert.deepEqual(errors,[]);assert.deepEqual(badResponses,[]);
 pass('Historical thrust is read-only and no AI/search/upload or allowance changes occur');
 const savedChecks=await api(info.owner,savedPath);
 for(const [project,prefix,destination] of [[info.project_id,'pf','powered-flight'],['focus-guided_ascent_review','ga','guided-ascent'],['focus-staged_ascent_review','sa','staged-ascent']]){
  await page.goto(info.owner+'/#/projects/'+project+'/r/1/'+destination);await idle();await page.locator('.'+prefix+'-playback').waitFor();
  assert.equal(await page.locator('.'+prefix+'-result-summary').isVisible(),true);
  const graphs=page.locator('.'+prefix+'-page details[data-flight-disclosure="graphs"]');assert.equal(await graphs.evaluate(node=>node.open),false);
  await graphs.locator(':scope > summary').click();const graph=graphs.locator('details').first();await graph.locator(':scope > summary').click();assert.ok((await graph.locator('svg').boundingBox()).width>100);
  const sample=page.locator('.'+prefix+'-page details[data-flight-disclosure="sample-values"]');assert.equal(await sample.evaluate(node=>node.open),false);await sample.locator(':scope > summary').click();
  await page.locator('[data-'+prefix+'-action="cutoff-before"]').click();assert.equal(await sample.evaluate(node=>node.open),true);assert.equal(await graph.evaluate(node=>node.open),true);
  await page.locator('[data-flight-disclosure="exact-sample"] > summary').click();await page.locator('[data-'+prefix+'-action="cutoff-after"]').click();assert.equal(await page.locator('[data-flight-disclosure="exact-sample"]').evaluate(node=>node.open),true);
 }
 pass('Vertical, guided and staged flight retain visible saved outcomes/playback, expand nested graphs, and preserve sample/graph choices through exact event changes');
 await page.goto(info.owner+'/#/projects/focus-orbital_review/r/1/simulation');await idle();await page.locator('#sim-play:enabled').waitFor();
 const history=page.locator('[data-sim-disclosure="history"]');assert.equal(await history.evaluate(node=>node.open),false);await history.locator(':scope > summary').click();
 await page.waitForFunction(()=>{const node=document.querySelector('#sim-chart');return node?.width>100&&node.getBoundingClientRect().width>100;});
 await page.locator('#sim-quantity').selectOption('speed_m_s');assert.equal(await history.evaluate(node=>node.open),true);
 const pixels=await page.locator('#sim-chart').evaluate(canvas=>canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data.some((value,index)=>index%4===3&&value>0));assert.equal(pixels,true);
 await page.locator('[data-sim-mode="exploratory"]').click();await page.locator('#sim-form').waitFor({state:'attached'});assert.equal(await page.locator('[data-sim-disclosure="history"]').evaluate(node=>node.open),false);
 await page.locator('[data-sim-mode="project"]').click();await page.locator('#sim-play:enabled').waitFor();assert.equal(await page.locator('[data-sim-disclosure="history"]').evaluate(node=>node.open),true);
 assert.deepEqual(originalView(await api(info.owner,savedPath)),originalView(savedChecks));assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
 pass('Orbital history draws nonempty pixels after expanding, preserves graph choice for its saved run, and starts collapsed for a different exploratory context');
 for(const [destination,prefix,id] of [['scenarios','sc',info.scenario_id],['envelopes','en',info.envelope_id]]){
  await page.goto(info.owner+'/#/projects/'+info.project_id+'/r/1/'+destination);await idle();await page.locator('[data-'+prefix+'-open="'+id+'"]:enabled').click();await page.locator('.'+prefix+'-report').waitFor();
  const fold=page.locator('.'+prefix+'-report details[data-secondary-key]').first();assert.equal(await fold.evaluate(node=>node.open),false);await fold.locator(':scope > summary').click();assert.equal(await fold.locator('svg').first().isVisible(),true);
  const selector=page.locator('[data-'+prefix+'-requirement]'),current=await selector.inputValue();const choices=await selector.locator('option').evaluateAll(nodes=>nodes.map(node=>node.value));await selector.selectOption(choices.find(value=>value!==current));assert.equal(await fold.evaluate(node=>node.open),false);await selector.selectOption(current);assert.equal(await fold.evaluate(node=>node.open),true);
  await page.evaluate(()=>dispatchEvent(new Event('beforeprint')));assert.equal(await page.locator('.'+prefix+'-report details:not([open])').count(),0);await page.evaluate(()=>dispatchEvent(new Event('afterprint')));
 }
 pass('Saved sweep and sampled-envelope graphs expand on demand and printing reveals their complete recorded evidence');
 await page.goto(info.owner+'/#/projects/'+info.project_id+'/r/2/coverage');await idle();const editor=page.locator('.ec-editor-disclosure');await editor.waitFor();assert.equal(await editor.evaluate(node=>node.open),false);
 await page.locator('[data-ec-row]').first().click();assert.equal(await editor.evaluate(node=>node.open),true);await editor.locator(':scope > summary').click();await page.locator('[data-ec-action="new"]').first().click();assert.equal(await editor.evaluate(node=>node.open),true);
 assert.deepEqual(errors,[]);assert.deepEqual(badResponses,[]);assert.deepEqual(external,[]);assert.equal((await callLog()).length,0);
 pass('Coverage opens its editor only when a check or Add is chosen, including after an explicitly collapsed prior editor');
 const result={schema:'sixd.focus-build2-browser.v1',synthetic_fixture:true,checks,errors,unexpected_responses:badResponses,external_requests:external.length,post_routes:posts.map(item=>item.path),paid_calls:0};await writeFile(join(output,'results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}catch(error){if(page)await page.screenshot({path:join(output,'failure.png'),fullPage:true}).catch(()=>{});console.error(error.stack||error);console.error(JSON.stringify({errors,badResponses,post_routes:posts.map(item=>item.path),stderr}));process.exitCode=1;}
finally{await browser?.close();if(child.exitCode===null){const done=new Promise(resolve=>child.once('exit',resolve));child.kill();await done;}}
