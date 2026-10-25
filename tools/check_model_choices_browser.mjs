/* Three-model UI acceptance, exclusively on an isolated synthetic provider.
 * Run from repo root: node tools/check_model_choices_browser.mjs
 * No founder configuration, credentials, ledger or service network is used.
 */
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdir,mkdtemp,readFile,writeFile,unlink} from 'node:fs/promises';
import {resolve,join} from 'node:path';
const root=process.cwd(),output=resolve(root,'work/model-choices-browser');await mkdir(output,{recursive:true});
const isolated=await mkdtemp(join(output,'fixture-'));
let module;try{module=await import(process.env.PLAYWRIGHT_MODULE||'playwright');}catch(error){if(process.env.PLAYWRIGHT_MODULE)throw error;module=await import('file:///C:/Users/Arya/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs');}
const python=process.env.SIXD_TEST_PYTHON||(process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
const serverSource=`import json,os,sys,time
from pathlib import Path
from dataclasses import asdict
sys.path[:0]=[str(Path.cwd()/'src'),str(Path.cwd()/'tests')]
from sixd.providers import LiveConfig,TokenFactoryProvider
from sixd.project_investigation import ProjectActionAdapter
from sixd.workspace_server import create_server
from test_workspace_ai_api import offline_transport
from test_whole_project_investigation import SUMMARY
folder=Path(sys.argv[1]);calls=folder/'calls.jsonl'
for k in ('NEBIUS_API_KEY','LANGSMITH_API_KEY','TAVILY_API_KEY'):os.environ.pop(k,None)
config=LiveConfig('https://api.tokenfactory.nebius.com/v1/','nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B','offline-browser-model-choices',29.5,.06,.24,2048,45,'native_no_thinking','forced_action_v1')
(folder/'token-factory.json').write_text(json.dumps({**asdict(config),'account_verified':True,'model_license_reviewed':True,'spend_approved':True}),encoding='utf-8')
def transport(request):
 payload=json.loads(request.data);menu=json.loads(payload['messages'][-1]['content'])
 with calls.open('a',encoding='utf-8') as handle:handle.write(json.dumps({'model':payload['model'],'actions':[x['action'] for x in menu['available_actions']]})+'\\n')
 if (folder/'block').exists():
  (folder/'entered').write_text('waiting',encoding='utf-8');deadline=time.monotonic()+30
  while (folder/'block').exists() and time.monotonic()<deadline:time.sleep(.01)
  if (folder/'block').exists():raise AssertionError('Synthetic request gate timed out')
 actions=[x['action'] for x in menu['available_actions']]
 if any(x in ('read_project','read_dependencies') for x in actions) or 'project' in menu.get('recorded_evidence_ids',[]):
  action=actions[0];args={'action':action,'evidence_ids':menu['recorded_evidence_ids'] if action=='finish' else [],'summary':SUMMARY if action=='finish' else ''}
  return {'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':None,'tool_calls':[{'id':'offline-browser-'+action,'type':'function','function':{'name':'select_next_action','arguments':json.dumps(args)}}]}}],'usage':{'prompt_tokens':500,'completion_tokens':60,'total_tokens':560}}
 return offline_transport(request)
def factory(config,ledger,key):return TokenFactoryProvider(config,ledger,api_key=key,transport=transport,action_adapter=ProjectActionAdapter())
def forbidden(*args,**kwargs):raise AssertionError('Navigation must not call search or metrics services')
with create_server(port=0,db_path=folder/'workspace.sqlite3',ai_local_directory=folder,provider_factory=factory,research_transport=forbidden,observability_transport=forbidden) as server:
 identity=server.store.ensure_default();server.ai.connect('synthetic-browser-model-key-no-network')
 ids=[]
 for choice in ('nano','super','ultra'):
  job=server.ai.start(identity,1,'thermal_limit','Explain the saved thermal finding.',model_choice=choice);deadline=time.monotonic()+15
  while server.ai._active and time.monotonic()<deadline:time.sleep(.01)
  record=server.ai.get(job['investigation_id'])
  if record['state']!='completed':raise AssertionError(str(record.get('error')))
  ids.append(job['investigation_id'])
 print(json.dumps({'url':'http://127.0.0.1:'+str(server.server_port),'project_id':identity,'seed_ids':ids}),flush=True)
 server.serve_forever()
`;
const child=spawn(python,['-u','-c',serverSource,isolated],{windowsHide:true,cwd:root,stdio:['ignore','pipe','pipe']});
let stderr='';child.stderr.on('data',c=>stderr+=c);let browser,page;
const checks=[],errors=[],external=[],failures=[],badResponses=[],posts=[];const pass=label=>{checks.push(label);console.log('PASS '+label);};
const callLog=async()=>{try{return(await readFile(join(isolated,'calls.jsonl'),'utf8')).trim().split('\n').filter(Boolean).map(x=>JSON.parse(x));}catch(e){if(e.code==='ENOENT')return[];throw e;}};
try{
 const info=await new Promise((yes,no)=>{let raw='';const timer=setTimeout(()=>no(Error('Isolated server did not start: '+stderr)),90000);child.stdout.on('data',chunk=>{raw+=chunk;try{const data=JSON.parse(raw.split('\n')[0]);clearTimeout(timer);yes(data);}catch{}});child.once('exit',code=>{clearTimeout(timer);no(Error('Isolated server exited '+code+': '+stderr));});});
 const origin=info.url,identity=info.project_id;
 browser=await module.chromium.launch({channel:process.env.SIXD_BROWSER_CHANNEL||'chrome',headless:true});
 const context=await browser.newContext({viewport:{width:1512,height:1060}});page=await context.newPage();page.setDefaultTimeout(20000);
 page.on('pageerror',e=>errors.push(e.stack||e.message));page.on('requestfailed',r=>failures.push({url:r.url(),error:r.failure()?.errorText}));
 page.on('response',r=>{if(r.url().startsWith(origin)&&r.status()>=400)badResponses.push({path:new URL(r.url()).pathname,status:r.status()});});
 page.on('request',r=>{if(r.method()==='POST')posts.push({path:new URL(r.url()).pathname,data:r.postDataJSON()});});
 await context.route('**/*',route=>{if(new URL(route.request().url()).origin!==origin){external.push(route.request().url());return route.abort();}return route.continue();});
 const api=async path=>{const r=await context.request.get(origin+path);assert.equal(r.status(),200,await r.text());return r.json();};
 const savedView=()=>api('/api/workspace?project_id='+encodeURIComponent(identity)+'&revision=1');
 const idle=()=>page.locator('#sixd-workspace[aria-busy="false"]').waitFor();
 const click=async action=>{await page.locator('[data-action="'+action+'"]:visible').first().click();await idle();};
 const waitChoices=()=>page.waitForFunction(()=>document.querySelectorAll('#sd-ai-model option').length===3&&!document.querySelector('#sd-ai-model').disabled);
 const countCalls=async()=> (await callLog()).length;
 const labels=['NVIDIA Nemotron 3 Nano','NVIDIA Nemotron 3 Super','NVIDIA Nemotron 3 Ultra'];
 const exactModels=['nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B','nvidia/nemotron-3-super-120b-a12b','nvidia/Nemotron-3-Ultra-550b-a55b'];
 const beforeView=await savedView(),beforeStatus=await api('/api/ai/status');
 const seededRecords=await Promise.all(info.seed_ids.map(id=>api('/api/investigations/'+id)));
 const beforeCalls=await countCalls();
 await page.goto(origin);await idle();await page.locator('[data-open-project="'+identity+'"]').click();await idle();
 await click('engineering');await click('system');await page.locator('#sd-tab-table').click();
 await page.locator('#sd-view-content [data-kind="requirement"][data-id="thermal_limit"]').first().click();
 await page.locator('[data-panel="assistant"]').click();await waitChoices();
 await page.waitForFunction(()=>document.querySelectorAll('#sd-ai-history .sd-ai-record').length===3);
 const choices=await page.locator('#sd-ai-model option').evaluateAll(nodes=>nodes.map(n=>n.value));assert.deepEqual(choices,['nano','super','ultra']);
 const historicalBefore=await page.locator('#sd-ai-history .sd-ai-record').allTextContents();
 for(const label of labels)assert.ok(historicalBefore.some(text=>text.includes('Recorded model: '+label)));
 pass('Requirement Assistant offers Nano, Super and Ultra; retained records name their actual models');
 const question='Explain this saved finding and the next evidence checks.';await page.locator('#sd-ai-question').fill(question);
 for(let n=0;n<choices.length;n++){
  await page.locator('#sd-ai-model').selectOption(choices[n]);assert.equal(await page.locator('#sd-ai-question').inputValue(),question);
  assert.equal(await page.locator('#sd-ai-consent-model').innerText(),labels[n]);
 }
 assert.equal(await countCalls(),beforeCalls);assert.equal(posts.length,0);assert.deepEqual(await page.locator('#sd-ai-history .sd-ai-record').allTextContents(),historicalBefore);
 pass('Choosing every model retains the question and history, updates consent, and makes no POST or provider request');
 // Observe the running state with a synthetic transport paused before its first response.
 await writeFile(join(isolated,'block'),'hold');
 const started=page.waitForResponse(r=>r.url()===origin+'/api/investigations'&&r.request().method()==='POST');
 await page.locator('#sd-ai-start').click();const startedResponse=await started;assert.equal(startedResponse.status(),200);const job=await startedResponse.json();
 const deadline=Date.now()+10000;while(Date.now()<deadline){try{await readFile(join(isolated,'entered'));break;}catch{await new Promise(r=>setTimeout(r,30));}}
 assert.equal(job.model_choice,'ultra');assert.equal(job.model,exactModels[2]);
 await page.waitForFunction(()=>document.querySelector('#sd-ai-model')?.disabled===true);assert.equal(await page.locator('#sd-ai-start').isDisabled(),true);
 await page.evaluate(()=>{const select=document.querySelector('#sd-ai-model');select.value='nano';select.dispatchEvent(new Event('change',{bubbles:true}));});
 assert.equal(await page.locator('#sd-ai-model').inputValue(),'ultra');assert.equal(posts.filter(p=>p.path==='/api/investigations').length,1);
 await click('project-investigate');
 await page.waitForFunction(()=>document.querySelectorAll('#sd-ai-model option').length===3&&document.querySelector('#sd-ai-model').disabled);
 assert.match(await page.locator('#sd-panel-context').innerText(),/Whole-project/);
 assert.equal(await page.locator('#sd-ai-start').isDisabled(),true);
 assert.equal(posts.filter(p=>p.path==='/api/investigations').length,1);
 pass('Changing investigation scope while a requirement job runs retains the global busy guard without another POST');
 await unlink(join(isolated,'block'));await waitChoices();
 const complete=await api('/api/investigations/'+job.investigation_id);assert.equal(complete.state,'completed');assert.equal(complete.model,exactModels[2]);
 assert.equal(posts.find(p=>p.path==='/api/investigations').data.model_choice,'ultra');
 pass('Explicit requirement start reaches Ultra; switching is disabled while running and never creates a second request');
 for(const old of seededRecords)assert.deepEqual(await api('/api/investigations/'+old.investigation_id),old);
 await click('requirement-investigate');await waitChoices();
 await page.screenshot({path:join(output,'requirement-desktop.png'),fullPage:true});
 pass('A new chosen-model job does not rewrite historical Nano, Super or Ultra receipts');
 await click('project-investigate');await waitChoices();assert.match(await page.locator('#sd-panel-context').innerText(),/Whole-project/);
 const projectQuestion='Review the related findings and unresolved evidence.';await page.locator('#sd-ai-question').fill(projectQuestion);
 const priorWholeCalls=await countCalls();for(const choice of choices){await page.locator('#sd-ai-model').selectOption(choice);assert.equal(await page.locator('#sd-ai-question').inputValue(),projectQuestion);}
 assert.equal(await countCalls(),priorWholeCalls);
 await page.locator('#sd-ai-model').selectOption('nano');
 const projectStarted=page.waitForResponse(r=>r.url()===origin+'/api/investigations'&&r.request().method()==='POST');await page.locator('#sd-ai-start').click();
 const projectResponse=await projectStarted;assert.equal(projectResponse.status(),200);const projectJob=await projectResponse.json();await waitChoices();
 const projectComplete=await api('/api/investigations/'+projectJob.investigation_id);
 assert.equal(projectComplete.state,'completed');assert.equal(projectComplete.scope,'project');assert.equal(projectComplete.model_choice,'nano');assert.equal(projectComplete.model,exactModels[0]);
 const request=posts.filter(p=>p.path==='/api/investigations').at(-1).data;assert.equal(request.scope,'project');assert.equal(request.model_choice,'nano');assert.equal(request.requirement_id,undefined);
 pass('Whole-project Assistant retains all choices and sends the explicitly selected Nano with project scope');
 const type=await page.evaluate(()=>({body:parseFloat(getComputedStyle(document.querySelector('#sixd-workspace')).fontSize),helper:parseFloat(getComputedStyle(document.querySelector('#sd-ai-model-help')).fontSize),question:parseFloat(getComputedStyle(document.querySelector('#sd-ai-question')).fontSize)}));
 assert.ok(type.body>=14.5);assert.ok(type.helper>=13);assert.ok(type.question>=13);
 await page.screenshot({path:join(output,'project-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 const mobileType=await page.locator('#sd-ai-question').evaluate(el=>parseFloat(getComputedStyle(el).fontSize));assert.ok(mobileType>=16);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
 await page.screenshot({path:join(output,'project-mobile.png'),fullPage:true});
 pass('Assistant body and helper type meet readable sizes; mobile fields are at least sixteen pixels without page overflow');
 assert.deepEqual(await savedView(),beforeView);
 const afterStatus=await api('/api/ai/status');assert.equal(afterStatus.budget.cap_usd,beforeStatus.budget.cap_usd);assert.ok(afterStatus.budget.reserved_usd>beforeStatus.budget.reserved_usd);
 assert.deepEqual(external,[]);assert.deepEqual(errors,[]);assert.deepEqual(badResponses,[]);assert.deepEqual(failures.filter(r=>r.error!=='net::ERR_ABORTED'),[]);
 assert.equal(posts.length,2);assert.ok(posts.every(p=>p.path==='/api/investigations'));
 const logged=await callLog();assert.ok(logged.slice(beforeCalls).some(c=>c.model===exactModels[2]));assert.ok(logged.slice(beforeCalls).some(c=>c.model===exactModels[0]));
 pass('Shared synthetic allowance is preserved, canonical engineering unchanged, and only the two explicit investigation POSTs occur');
 const result={schema:'sixd.model-choice-browser-acceptance.v1',synthetic_fixture:true,live_provider_calls:0,checks,errors,external_requests:external.length,unexpected_responses:badResponses,post_routes:posts.map(p=>p.path),seed_models:seededRecords.map(r=>r.model),new_models:[complete.model,projectComplete.model],typography:type,mobile_field_px:mobileType};
 await writeFile(join(output,'results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}catch(error){if(page)await page.screenshot({path:join(output,'failure.png'),fullPage:true}).catch(()=>{});console.error(error);console.error(JSON.stringify({url:page?.url(),errors,badResponses,failures,post_routes:posts.map(p=>p.path)},null,2));if(stderr)console.error(stderr);process.exitCode=1;}
finally{await unlink(join(isolated,'block')).catch(()=>{});if(browser)await browser.close();if(child.exitCode===null){const done=new Promise(r=>child.once('exit',r));child.kill();await done;}}
