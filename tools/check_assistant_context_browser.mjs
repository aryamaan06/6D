/* Part 3 context acceptance on an isolated synthetic provider and temporary DB.
 * Run from repository root: node tools/check_assistant_context_browser.mjs
 * This harness never opens owner state or permits browser network off loopback.
 */
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdir,mkdtemp,readFile,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';

const root=process.cwd(),output=resolve(root,'work/assistant-context-browser');await mkdir(output,{recursive:true});
const fixture=await mkdtemp(join(output,'fixture-'));
let playwright;try{playwright=await import(process.env.PLAYWRIGHT_MODULE||'playwright');}catch(error){if(process.env.PLAYWRIGHT_MODULE)throw error;playwright=await import('file:///C:/Users/Arya/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs');}
const python=process.env.SIXD_TEST_PYTHON||(process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
const serverSource=`import json,os,sys,time
from copy import deepcopy
from pathlib import Path
from dataclasses import asdict
sys.path[:0]=[str(Path.cwd()/'src'),str(Path.cwd()/'tests')]
from sixd.providers import LiveConfig,TokenFactoryProvider
from sixd.project_investigation import ProjectActionAdapter
from sixd.workspace_server import create_server
from sixd.project_examples import example_projects
from test_workspace_ai_api import offline_transport
from test_workspace_test_data import spec
folder=Path(sys.argv[1]);calls=folder/'calls.jsonl'
for key in ('NEBIUS_API_KEY','LANGSMITH_API_KEY','TAVILY_API_KEY'):os.environ.pop(key,None)
config=LiveConfig('https://api.tokenfactory.nebius.com/v1/','nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B','offline-assistant-context-browser',29.5,.06,.24,2048,45,'native_no_thinking','forced_action_v1')
(folder/'token-factory.json').write_text(json.dumps({**asdict(config),'account_verified':True,'model_license_reviewed':True,'spend_approved':True}),encoding='utf-8')
def transport(request):
 payload=json.loads(request.data)
 with calls.open('a',encoding='utf-8') as handle:handle.write(json.dumps({'model':payload['model']})+'\\n')
 return offline_transport(request)
def factory(config,ledger,key):return TokenFactoryProvider(config,ledger,api_key=key,transport=transport,action_adapter=ProjectActionAdapter())
def forbidden(*args,**kwargs):raise AssertionError('Context UI must not search or upload metrics')
with create_server(port=0,db_path=folder/'workspace.sqlite3',ai_local_directory=folder,provider_factory=factory,research_transport=forbidden,observability_transport=forbidden) as server:
 server.ai.connect('synthetic-context-key-no-network');server.research.connect('synthetic-context-research-key-no-network',1)
 seed_ids=[]
 for suffix in ('a','b'):
  project=example_projects()['baseline'];project.update(project_id='context-'+suffix,name='Constructed context '+suffix.upper(),revision='1')
  server.store.create_project(project);server.store.run(project['project_id'],1)
  if suffix=='a':
   job=server.ai.start(project['project_id'],1,'thermal_limit','Explain the saved thermal finding.',model_choice='nano');deadline=time.monotonic()+20
   while server.ai._active and time.monotonic()<deadline:time.sleep(.01)
   record=server.ai.get(job['investigation_id'])
   if record['state']!='completed':raise AssertionError(str(record.get('error')))
   seed_ids.append(record['investigation_id'])
   for title,target in [('Check reference','requirement:thermal_limit'),('Finding reference','finding:thermal_limit'),('Model reference','assumption:thermal:0'),('Other check','requirement:drag_limit'),('Unlinked library source',None)]:
    profile=server.sources.save_source(project['project_id'],1,{'source_id':None,'base_version':None,'title':title,'url':'https://example.org/constructed-context','excerpt':'Synthetic context only; no independent engineering validity is claimed.','details':''})
    source=next(item for item in profile['sources'] if item['title']==title)
    if target:server.sources.link_source(project['project_id'],1,{'source_id':source['source_id'],'source_version':source['version'],'target_id':target,'note':'Constructed context browser test.'})
   project=deepcopy(server.store.get(project['project_id'],1)['project']);project['inputs']['heat_input']['value']+=1
   server.store.save_revision(project['project_id'],1,project);view=server.store.run(project['project_id'],2)
   comparison=server.test_data.run(project['project_id'],2,view['run']['run_id'],spec())
   comparison_id=comparison['receipt']['comparison_id'];row_number=comparison['receipt']['row_results'][0]['row_number']
 server.store.ensure_default=lambda:'context-a'
 print(json.dumps({'url':'http://127.0.0.1:'+str(server.server_port),'seed_ids':seed_ids,'comparison_id':comparison_id,'row_number':row_number}),flush=True)
 server.serve_forever()
`;
const child=spawn(python,['-u','-c',serverSource,fixture],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
let stderr='';child.stderr.on('data',chunk=>stderr+=chunk);let browser,page;
const checks=[],errors=[],external=[],failures=[],badResponses=[],posts=[];
const pass=label=>{checks.push(label);console.log('PASS '+label);};
const callLog=async()=>{try{return(await readFile(join(fixture,'calls.jsonl'),'utf8')).trim().split('\n').filter(Boolean).map(line=>JSON.parse(line));}catch(error){if(error.code==='ENOENT')return[];throw error;}};
try{
 const info=await new Promise((yes,no)=>{let raw='';const timer=setTimeout(()=>no(Error('Fixture startup timed out: '+stderr)),90000);child.stdout.on('data',chunk=>{raw+=chunk;try{const data=JSON.parse(raw.split('\n')[0]);clearTimeout(timer);yes(data);}catch{}});child.once('exit',code=>{clearTimeout(timer);no(Error('Fixture exited '+code+': '+stderr));});});
 const origin=info.url;
 browser=await playwright.chromium.launch({channel:process.env.SIXD_BROWSER_CHANNEL||'chrome',headless:true});
 const context=await browser.newContext({viewport:{width:1512,height:1060}});page=await context.newPage();page.setDefaultTimeout(25000);
 await context.route('**/*',route=>{if(new URL(route.request().url()).origin!==origin){external.push(route.request().url());return route.abort();}return route.continue();});
 page.on('pageerror',error=>errors.push(error.stack||error.message));page.on('requestfailed',request=>failures.push({path:new URL(request.url()).pathname,error:request.failure()?.errorText}));
 page.on('response',response=>{if(response.url().startsWith(origin)&&response.status()>=400)badResponses.push({path:new URL(response.url()).pathname,status:response.status()});});
 page.on('request',request=>{if(request.method()==='POST')posts.push({path:new URL(request.url()).pathname,data:request.postDataJSON()});});
 const api=async path=>{const response=await context.request.get(origin+path);assert.equal(response.status(),200,await response.text());return response.json();};
 const saved=(id='context-a',revision=2)=>api('/api/workspace?project_id='+id+'&revision='+revision);
 const beforeA=await saved(),beforeOld=await saved('context-a',1),beforeB=await saved('context-b',1),beforeSources=await api('/api/sources?project_id=context-a&revision=2'),beforeStatus=await api('/api/ai/status'),beforeCalls=(await callLog()).length;
 const seedRecords=await Promise.all(info.seed_ids.map(id=>api('/api/investigations/'+id)));
 const idle=()=>page.locator('#sixd-workspace[aria-busy="false"]').waitFor();
 const click=async action=>{await page.locator('[data-action="'+action+'"]:visible').first().click();await idle();};
 const open=async()=>{await page.locator('#sd-rocket-launcher').click();if(await page.locator('[data-rocket-tab="nemotron"]').getAttribute('aria-selected')!=='true')await page.locator('[data-rocket-tab="nemotron"]').click();await page.locator('#sd-ai-context-summary').waitFor();await page.waitForFunction(()=>document.querySelectorAll('#sd-ai-model option').length===4&&!document.querySelector('#sd-ai-model').disabled);};
 const close=async()=>{await page.locator('#sd-rocket-dialog [data-rocket-close]').click();await page.waitForFunction(()=>!document.querySelector('#sd-rocket-dialog').open);};
 const summary=async()=>{const detail=page.locator('#sd-ai-context-summary .sd-chat-context-details');if(!await detail.evaluate(node=>node.open))await detail.locator(':scope > summary').click();return page.locator('#sd-ai-context-summary').innerText();};
 const assertPage=async()=>{const label=await page.locator('#sd-page-title').innerText();assert.ok((await summary()).length>0,'saved context summary remains visible');assert.ok((await page.locator('#sd-rocket-context').innerText()).includes(label));};
 const selectCheck=async id=>{await page.locator('#sd-ai-scope').selectOption('requirement');await page.locator('#sd-rocket-requirement').selectOption(id);};
 await page.goto(origin+'/#/projects/context-a/r/2/system?view=table&kind=requirement&item=thermal_limit');await idle();
 // Use the actual selected-check control because a route may normalize defaults.
 await page.locator('#sd-view-content [data-kind="requirement"][data-id="thermal_limit"]').first().click();
 await open();assert.equal(await page.locator('#sd-ai-scope').inputValue(),'requirement');assert.equal(await page.locator('#sd-rocket-requirement').inputValue(),'thermal_limit');await assertPage();
 assert.match(await summary(),/Constructed context A/);assert.match(await summary(),/R2/);assert.ok((await summary()).includes(beforeA.project.requirements.find(item=>item.id==='thermal_limit').title));
 pass('System launcher opens the exact selected check with project, saved revision, current page and finding context visible');

 const question='Keep this typed question while I choose the evidence scope.';await page.locator('#sd-ai-question').fill(question);
 await page.locator('#sd-ai-scope').selectOption('project');assert.equal(await page.locator('#sd-ai-question').inputValue(),question);
 await selectCheck('drag_limit');assert.equal(await page.locator('#sd-ai-question').inputValue(),question);
 await close();await open();assert.equal(await page.locator('#sd-rocket-requirement').inputValue(),'drag_limit');assert.equal(await page.locator('#sd-ai-question').inputValue(),question);
 pass('Explicit scope and check changes retain the typed question, and same-page reopen retains the explicit scope');

 await close();await page.locator('[data-view="canvas"]').click();
 await page.locator('#sd-system-tree .sd-tree-item[data-system]').first().click();
 await page.locator('#sd-view-content [data-kind="model"]').first().click();
 await open();assert.equal(await page.locator('#sd-ai-scope').inputValue(),'project');assert.equal(await page.locator('#sd-ai-question').inputValue(),question);
 assert.match(await summary(),/Whole project/);await close();
 await page.locator('#sd-system-tree [data-system="overview"]').click();await page.locator('[data-view="table"]').click();await page.locator('#sd-view-content [data-kind="requirement"][data-id="drag_limit"]').first().click();
 await open();assert.equal(await page.locator('#sd-rocket-requirement').inputValue(),'drag_limit');
 pass('Changing the selected system item resets ordinary launcher scope safely instead of submitting a visually unselected null check');

 const newestQuestion='This newer question must replace the older saved scope draft when the page changes.';await page.locator('#sd-ai-question').fill(newestQuestion);
 for(const pageName of ['review-home','report']){
  await close();if(pageName==='report')await click('evidence');await click(pageName);await open();assert.equal(await page.locator('#sd-ai-scope').inputValue(),'project');assert.equal(await page.locator('#sd-ai-question').inputValue(),newestQuestion);await assertPage();
 }
 pass('Overview and report launcher defaults reset to whole project, preserve the typed question, and show the current page');

 await selectCheck('thermal_limit');
 await page.waitForFunction(()=>/\d+ linked reference/.test(document.querySelector('#sd-ai-context-summary').textContent));
 const refs=beforeSources.links.filter(link=>['requirement:thermal_limit','finding:thermal_limit'].includes(link.target.target_id)||link.target.kind==='model_assumption'&&link.target.id==='thermal');
 const ready=refs.filter(link=>link.status==='linked').length,unresolved=refs.filter(link=>link.status==='needs_review').length;
 assert.match(await summary(),new RegExp(ready+' linked reference'));if(unresolved)assert.match(await summary(),new RegExp(unresolved+' need review'));
 assert.doesNotMatch(await summary(),/Unlinked library source/);
 pass('Visible references use the exact selected check/model scope and separate current links from unresolved links');

 await page.locator('#sd-ai-scope').selectOption('project');await close();
 const hiddenRow=page.locator('[data-test-evidence-investigate="'+info.comparison_id+'"][data-test-evidence-row="'+info.row_number+'"]').first();await hiddenRow.waitFor({state:'attached'});assert.equal(await hiddenRow.isDisabled(),false);
 // The product retains the rocket as its sole ordinary entry. This intentionally
 // invokes the existing hidden exact-row handoff callback, not a visible journey.
 await hiddenRow.evaluate(button=>button.click());await page.locator('#sd-ai-context-summary').waitFor();
 assert.equal(await page.locator('#sd-ai-scope').inputValue(),'requirement');assert.equal(await page.locator('#sd-rocket-requirement').inputValue(),'drag_limit');assert.match(await summary(),new RegExp('row '+info.row_number,'i'));assert.ok((await summary()).includes(info.comparison_id));
 const testQuestion=await page.locator('#sd-ai-question').inputValue();
 await selectCheck('thermal_limit');assert.equal(await page.locator('#sd-ai-question').inputValue(),testQuestion);assert.match(await summary(),/parked|not included/i);
 await selectCheck('drag_limit');assert.equal(await page.locator('#sd-ai-question').inputValue(),testQuestion);assert.match(await summary(),new RegExp('row '+info.row_number,'i'));
 pass('Existing hidden exact-row handoff opens its own requirement from prior project scope; another check parks the row and returning restores it');

 assert.equal((await callLog()).length,beforeCalls);assert.equal(posts.filter(post=>post.path==='/api/investigations'||post.path==='/api/research/search').length,0);
 await page.locator('#sd-ai-model').selectOption('super');
 const started=page.waitForResponse(response=>response.url()===origin+'/api/investigations'&&response.request().method()==='POST');await page.locator('#sd-ai-start').click();const response=await started;assert.equal(response.status(),200);const job=await response.json();
 await page.waitForFunction(()=>!document.querySelector('#sd-ai-model').disabled);const record=await api('/api/investigations/'+job.investigation_id);assert.equal(record.state,'completed');assert.equal(record.requirement_id,'drag_limit');
 const request=posts.find(post=>post.path==='/api/investigations').data;assert.equal(request.requirement_id,'drag_limit');assert.equal(request.test_comparison_id,info.comparison_id);assert.equal(request.test_row_number,info.row_number);assert.equal(request.scope,undefined);
 pass('No context choice triggers a provider request; one explicit synthetic Ask sends exactly the selected requirement and test row');

 await close();await page.locator('#sd-project-picker').selectOption('context-b');await idle();await open();assert.match(await summary(),/Constructed context B/);assert.doesNotMatch(await summary(),new RegExp(info.comparison_id));assert.equal(await page.locator('#sd-ai-question').inputValue(),'');await close();
 await page.locator('#sd-project-picker').selectOption('context-a');await idle();await page.locator('#sd-revision-picker').selectOption('1');await idle();await open();assert.match(await summary(),/R1/);assert.match(await summary(),/historical/i);assert.doesNotMatch(await summary(),new RegExp(info.comparison_id));assert.equal(await page.locator('#sd-ai-question').inputValue(),'');
 await selectCheck('thermal_limit');await page.waitForFunction(()=>document.querySelectorAll('#sd-ai-history [data-ai-resume]').length===1);assert.equal(await page.locator('[data-ai-resume="'+info.seed_ids[0]+'"]').count(),1);
 await page.locator('[data-rocket-tab="research"]').click();await page.locator('#sd-rocket-research-host [data-sr-field="target"]').waitFor();assert.equal(await page.locator('#sd-rocket-research-host [data-sr-action="search"]').isDisabled(),true);assert.match(await page.locator('#sd-rocket-research-host').innerText(),/historical revision.*read-only/i);
 await close();
 pass('Project and historical-revision changes do not attach another context’s question or row; historical answers stay scoped and reference search is blocked');

 await page.locator('#sd-revision-picker').selectOption('2');await idle();await click('setup');await click('author-project');await click('author-edit');await page.locator('#sd-draft-strip').waitFor({state:'visible'});await open();assert.equal(await page.locator('#sd-ai-start').isDisabled(),true);assert.match(await summary(),/draft|saved baseline/i);assert.match(await page.locator('#sd-ai-blocked').innerText(),/Save or discard the draft/i);
 await page.locator('[data-rocket-tab="research"]').click();await page.locator('#sd-rocket-research-host [data-sr-field="target"]').waitFor();assert.equal(await page.locator('#sd-rocket-research-host [data-sr-action="search"]').isDisabled(),true);assert.match(await page.locator('#sd-rocket-research-host').innerText(),/Save or discard the draft/i);await close();await click('discard');
 pass('An open draft describes the saved baseline and blocks Ask and reference search until saved or discarded');

 assert.deepEqual(await saved(),beforeA);assert.deepEqual(await saved('context-a',1),beforeOld);assert.deepEqual(await saved('context-b',1),beforeB);assert.deepEqual(await api('/api/sources?project_id=context-a&revision=2'),beforeSources);
 for(const old of seedRecords)assert.deepEqual(await api('/api/investigations/'+old.investigation_id),old);
 assert.equal((await api('/api/ai/status')).budget.cap_usd,beforeStatus.budget.cap_usd);
 const allowedPosts=new Set(['/api/investigations','/api/authoring/preflight','/api/impact','/api/test-evidence/impact','/api/interfaces/preview']);assert.ok(posts.every(post=>allowedPosts.has(post.path)));assert.equal(posts.filter(post=>post.path==='/api/investigations').length,1);
 assert.deepEqual(external,[]);assert.deepEqual(errors,[]);assert.deepEqual(badResponses,[]);assert.deepEqual(failures.filter(failure=>failure.error!=='net::ERR_ABORTED'),[]);
 pass('Saved designs, reference snapshots, historical receipts and allowance ceiling remain unchanged; no external requests or browser errors occur');
 await page.screenshot({path:join(output,'context-desktop.png'),fullPage:true});
 const result={schema:'sixd.assistant-context-browser-acceptance.v1',synthetic_fixture:true,paid_calls:0,checks,errors,external_requests:external.length,unexpected_responses:badResponses,post_routes:posts.map(post=>post.path),synthetic_provider_requests:(await callLog()).length-beforeCalls,exact_row_callback:'Existing hidden control invoked with DOM click; not claimed as a visible user journey.'};
 await writeFile(join(output,'results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}catch(error){if(page)await page.screenshot({path:join(output,'failure.png'),fullPage:true}).catch(()=>{});console.error(error);console.error(JSON.stringify({url:page?.url(),errors,badResponses,failures,post_routes:posts.map(post=>post.path)},null,2));if(stderr)console.error(stderr);process.exitCode=1;}
finally{if(browser)await browser.close();if(child.exitCode===null){const ended=new Promise(resolve=>child.once('exit',resolve));child.kill();await ended;}}
