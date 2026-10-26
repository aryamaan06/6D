/* Rocket/central-context acceptance on isolated synthetic owner + visitor servers.
 * Run from the repository root: node tools/check_rocket_browser.mjs
 * Never opens founder data, credentials or provider networks. */
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdir,mkdtemp,readFile,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';

const root=process.cwd(),output=resolve(root,'work/rocket-browser');await mkdir(output,{recursive:true});
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
p=example_projects()['missing_evidence'];p.update(project_id='rocket-review',name='Rocket companion review (constructed)',revision='1')
owner.store.create_project(p);owner.store.run(p['project_id'],1);owner.store.ensure_default=lambda:p['project_id']
owner.ai.connect('synthetic-rocket-key-never-network');owner.research.connect('tvly-synthetic-rocket-no-network',1)
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
visitor_origin='http://127.0.0.1:'+str(port)
visitor=create_hosted_server(HostedConfig(folder/'visitors',visitor_origin,'synthetic-rocket-invitation-no-real-secret',allow_loopback_http=True,get_limit=600,post_limit=100,login_limit=100),port=port)
threads=[threading.Thread(target=server.serve_forever,daemon=True) for server in (owner,visitor)]
for thread in threads:thread.start()
print(json.dumps({'owner':'http://127.0.0.1:'+str(owner.server_port),'visitor':visitor_origin,'project_id':p['project_id']}),flush=True)
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
 browser=await playwright.chromium.launch({channel:process.env.SIXD_BROWSER_CHANNEL||'chrome',headless:true});
 const context=await browser.newContext({viewport:{width:1512,height:1060}}),allowed=new Set([info.owner,info.visitor]);
 await context.route('**/*',route=>{if(!allowed.has(new URL(route.request().url()).origin)){external.push(route.request().url());return route.abort();}return route.continue();});
 const observe=p=>{p.setDefaultTimeout(25000);p.on('pageerror',error=>errors.push(error.stack||error.message));p.on('requestfailed',r=>failures.push({path:new URL(r.url()).pathname,error:r.failure()?.errorText}));p.on('request',r=>{if(r.method()==='POST')posts.push({origin:new URL(r.url()).origin,path:new URL(r.url()).pathname,data:r.postDataJSON()});});p.on('response',r=>{if(allowed.has(new URL(r.url()).origin)&&r.status()>=400)badResponses.push({path:new URL(r.url()).pathname,status:r.status()});});};
 page=await context.newPage();observe(page);
 const api=async(origin,path)=>{const response=await context.request.get(origin+path);assert.equal(response.status(),200,await response.text());return response.json();};
 const snapshot=()=>api(info.owner,'/api/workspace?project_id='+info.project_id+'&revision=1');
 const before=await snapshot(),beforeStatus=await api(info.owner,'/api/ai/status');
 const idle=()=>page.locator('#sixd-workspace[aria-busy="false"]').waitFor();
 const click=async action=>{await page.locator('[data-action="'+action+'"]:visible').first().click();await idle();};
 const waitChoices=()=>page.waitForFunction(()=>document.querySelectorAll('#sd-ai-model option').length===3&&!document.querySelector('#sd-ai-model').disabled);
 const openRocket=async(tab='nemotron')=>{if(!await page.locator('#sd-rocket-dialog').evaluate(d=>d.open))await page.locator('#sd-rocket-launcher').click();if(await page.locator('[data-rocket-tab="'+tab+'"]').getAttribute('aria-selected')!=='true')await page.locator('[data-rocket-tab="'+tab+'"]').click();};
 const closeRocket=async()=>{await page.locator('#sd-rocket-dialog [data-rocket-close]').click();await page.waitForFunction(()=>!document.querySelector('#sd-rocket-dialog').open);};
 for(const route of ['projects','review-home','system','guided-ascent','staged-ascent','sources']){
  const fragment=route==='projects'?'#/projects':'#/projects/'+info.project_id+'/r/1/'+route;
  await page.goto(info.owner+'/'+fragment);await idle();
  assert.equal(await page.locator('#sd-rocket-launcher:visible').count(),1,route);
  assert.equal(await page.locator('#sd-rocket-dialog').count(),1,route);
  assert.equal(await page.locator('[data-panel="assistant"]:visible').count(),0,route);
  assert.equal(await page.locator('.sd-toolbar [data-action="project-investigate"]:visible').count(),0,route);
  const specialized=await page.locator('#sd-view-content').evaluate(host=>[...host.querySelectorAll('*')].filter(node=>[...node.attributes].some(attribute=>attribute.name==='data-investigate'||attribute.name.startsWith('data-')&&attribute.name.endsWith('-investigate'))).map(node=>({name:node.tagName,visible:!!(node.getClientRects().length&&getComputedStyle(node).visibility!=='hidden')})));
  assert.ok(specialized.every(node=>!node.visible),JSON.stringify({route,specialized}));
 }
 // Late-rendered model and evidence controls must also stay out of ordinary UI.
 const hiddenLateControls=await page.evaluate(()=>{
  const host=document.createElement('div');host.id='rocket-late-investigation-fixture';
  for(const name of ['data-investigate','data-test-evidence-investigate','data-ga-investigate','data-sa-investigate','data-pf-investigate','data-sim-investigate']){const button=document.createElement('button');button.setAttribute(name,'thermal_limit');button.textContent='Late investigation';host.append(button);}
  document.querySelector('#sd-view-content').append(host);
  const hidden=[...host.children].every(node=>getComputedStyle(node).display==='none');host.remove();return hidden;
 });assert.equal(hiddenLateControls,true);
 assert.equal((await callLog()).length,0);assert.equal(posts.length,0);
 const animation=await page.locator('.sd-rocket-flame-outer').evaluate(el=>getComputedStyle(el).animationName);assert.notEqual(animation,'none');
 pass('One animated rocket is available on Projects, overview, systems, planar/staged analysis and sources without standalone AI tabs or service calls');
 await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await page.locator('.sd-rocket-art').evaluate(el=>getComputedStyle(el).animationName),'none');await page.emulateMedia({reducedMotion:'no-preference'});
 pass('Rocket exhaust and hover honor reduced-motion preferences');
 await click('engineering');await click('system');await page.locator('#sd-tab-table').click();
 await page.locator('#sd-view-content [data-kind="requirement"][data-id="thermal_limit"]').first().click();
 await page.locator('.sd-main > .sd-inspector #sd-panel-body').waitFor();
 const geometry=await page.evaluate(()=>{const main=document.querySelector('.sd-main').getBoundingClientRect(),inspector=document.querySelector('.sd-inspector').getBoundingClientRect();return{main:{x:main.x,right:main.right},inspector:{x:inspector.x,right:inspector.right,width:inspector.width},columns:getComputedStyle(document.querySelector('.sd-shell')).gridTemplateColumns.split(' ').length};});
 assert.equal(geometry.columns,2);assert.ok(geometry.inspector.x>=geometry.main.x&&geometry.inspector.right<=geometry.main.right+1&&geometry.inspector.width>600);
 assert.match(await page.locator('#sd-panel-body').innerText(),/320\s*K/);
 const technical=page.locator('#sd-panel-body details');assert.ok(await technical.count()>0);assert.equal(await technical.first().evaluate(el=>el.open),false);
 pass('Requirement facts are centred in the main workspace with technical detail folded, and the third/right column is gone');
 await page.screenshot({path:join(output,'centered-inspector-desktop.png'),fullPage:true});
 await openRocket();await waitChoices();
 assert.deepEqual(await page.locator('[data-rocket-tab]').allTextContents(),['Ask Nemotron','Find references']);
 let bounds=await page.locator('#sd-rocket-dialog').boundingBox();assert.ok(Math.abs(bounds.x+bounds.width/2-756)<2);
 assert.equal(await page.locator('#sd-rocket-nemotron-host #sd-ai-question').count(),1);
 assert.doesNotMatch(await page.locator('#sd-rocket-nemotron-host').innerText(),/Approved development allowance|Cumulative reservations|Reservation capacity remaining|\$\d/);
 assert.deepEqual(await page.locator('#sd-ai-model option').evaluateAll(nodes=>nodes.map(n=>n.value)),['nano','super','ultra']);
 pass('Nemotron opens in the centred rocket conversation with all three models and no ordinary financial accounting');
 const question='Explain this saved thermal finding and the next evidence checks.';await page.locator('#sd-ai-question').fill(question);
 for(const choice of ['nano','super','ultra']){await page.locator('#sd-ai-model').selectOption(choice);assert.equal(await page.locator('#sd-ai-question').inputValue(),question);}
 assert.equal(posts.length,0);assert.equal((await callLog()).length,0);
 await closeRocket();await openRocket();await waitChoices();assert.equal(await page.locator('#sd-ai-question').inputValue(),question);assert.equal(await page.locator('#sd-ai-model').inputValue(),'ultra');
 await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.querySelector('#sd-rocket-dialog').open);await openRocket();
 bounds=await page.locator('#sd-rocket-dialog').boundingBox();await page.mouse.click(Math.max(2,bounds.x-10),Math.max(2,bounds.y-10));await page.waitForFunction(()=>!document.querySelector('#sd-rocket-dialog').open);
 await openRocket();assert.equal(await page.locator('#sd-ai-question').inputValue(),question);
 pass('Model choice, close/reopen, Escape and outside dismissal preserve the unsent question without making requests');
 const started=page.waitForResponse(r=>r.url()===info.owner+'/api/investigations'&&r.request().method()==='POST');await page.locator('#sd-ai-start').click();
 const response=await started;assert.equal(response.status(),200);const requirementJob=await response.json();assert.equal(requirementJob.model_choice,'ultra');await waitChoices();
 const requirementReceipt=await api(info.owner,'/api/investigations/'+requirementJob.investigation_id);assert.equal(requirementReceipt.state,'completed');assert.equal(requirementReceipt.requirement_id,'thermal_limit');
 assert.equal(posts.filter(p=>p.path==='/api/investigations').length,1);
 pass('Only explicit Start invokes the chosen Ultra model through the unchanged requirement evidence workflow');
 await click('project-investigate');await waitChoices();assert.match(await page.locator('#sd-rocket-ai-context').innerText(),/Whole-project/i);
 await page.locator('#sd-ai-model').selectOption('nano');await page.locator('#sd-ai-question').fill('Review the related findings and unresolved evidence.');
 const wholeStarted=page.waitForResponse(r=>r.url()===info.owner+'/api/investigations'&&r.request().method()==='POST');await page.locator('#sd-ai-start').click();const wholeResponse=await wholeStarted;assert.equal(wholeResponse.status(),200);const wholeJob=await wholeResponse.json();await waitChoices();
 const wholeReceipt=await api(info.owner,'/api/investigations/'+wholeJob.investigation_id);assert.equal(wholeReceipt.state,'completed');assert.equal(wholeReceipt.scope,'project');assert.equal(wholeReceipt.model_choice,'nano');
 assert.equal(posts.filter(p=>p.path==='/api/investigations').length,2);
 pass('Whole-project review remains accessible inside the same rocket, retaining explicit model choice and one request start');
 let profileEntered;const entered=new Promise(resolve=>profileEntered=resolve),profileGate=new Promise(resolve=>releaseResearchProfile=resolve);
 let profileDelayed=false;
 const delayedProfile=async route=>{
  if(!profileDelayed&&route.request().method()==='GET'&&new URL(route.request().url()).pathname==='/api/research'){
   profileDelayed=true;profileEntered();await profileGate;
  }
  await route.continue();
 };
 await page.route('**/api/research?*',delayedProfile);
 await page.locator('[data-rocket-tab="research"]').click();await entered;
 await closeRocket();await click('projects');await openRocket('research');
 assert.match(await page.locator('#sd-rocket-context').innerText(),/captured project|Finishing the reference request/i);
 const pendingControls=page.locator('#sd-rocket-research-host [data-sr-field="target"],#sd-rocket-research-host [data-sr-field="query"],#sd-rocket-research-host [data-sr-action="search"]');
 assert.ok(await pendingControls.evaluateAll(nodes=>nodes.every(node=>node.disabled)),'A pending captured context must not expose any enabled old research controls.');
 assert.equal(posts.filter(p=>p.path==='/api/research/search').length,0);
 releaseResearchProfile();releaseResearchProfile=null;
 await page.waitForFunction(()=>/Open a project first/.test(document.querySelector('#sd-rocket-research-host')?.textContent||'')&&!document.querySelector('#sd-rocket-research-host [data-sr-field="query"]'));
 await page.unroute('**/api/research?*',delayedProfile);
 await closeRocket();await page.locator('[data-open-project="'+info.project_id+'"]').click();await idle();await openRocket('research');
 await page.locator('#sd-rocket-research-host [data-sr-field="target"]').waitFor();
 pass('A delayed Tavily profile stays bound to its captured project; reopening on Projects cannot activate the old form and resolves to a choose-project notice');
 assert.equal((await callLog()).filter(c=>c.service==='tavily').length,0);
 await page.locator('#sd-rocket-research-host [data-sr-field="target"]').selectOption('requirement:thermal_limit');
 await page.locator('#sd-rocket-research-host [data-sr-field="query"]').fill('spacecraft steady radiative equilibrium assumptions');
 assert.equal(posts.filter(p=>p.path==='/api/research/search').length,0);
 const searchStarted=page.waitForResponse(r=>r.url()===info.owner+'/api/research/search'&&r.request().method()==='POST');await page.locator('#sd-rocket-research-host [data-sr-action="search"]').click();assert.equal((await searchStarted).status(),200);
 await page.locator('#sd-rocket-research-host [data-sr-action="preview"]').click();await page.locator('#sd-rocket-research-host [data-sr-action="use"]').waitFor();
 assert.equal((await callLog()).filter(c=>c.service==='tavily').length,1);assert.equal(posts.filter(p=>p.path==='/api/research/search').length,1);assert.equal(posts.filter(p=>p.path==='/api/sources').length,0);
 await page.locator('#sd-rocket-research-host [data-sr-action="use"]').click();await page.waitForFunction(()=>document.querySelector('[data-sl-field="title"]')?.value==='Constructed spacecraft reference');assert.equal(await page.locator('[data-sl-field="title"]').inputValue(),'Constructed spacecraft reference');
 assert.equal(posts.filter(p=>p.path==='/api/sources').length,0);
 pass('Tavily requires one explicit search; preview and copy hand off to an unsaved Source library form without automatic source saving');
 await openRocket('research');await page.locator('#sd-rocket-research-host [data-sr-field="query"]').waitFor();
 await page.setViewportSize({width:390,height:844});bounds=await page.locator('#sd-rocket-dialog').boundingBox();assert.ok(bounds.x>=0&&bounds.x+bounds.width<=391&&bounds.height<=825);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);assert.equal(await page.locator('#sd-rocket-dialog').evaluate(el=>el.scrollWidth>el.clientWidth+1),false);
 await page.screenshot({path:join(output,'rocket-mobile.png'),fullPage:true});await closeRocket();
 pass('The centred rocket dialog fits a narrow mobile viewport without horizontal overflow');
 const viewer=await context.newPage();observe(viewer);await viewer.goto(info.visitor);await viewer.locator('#hosted-access-code').fill('synthetic-rocket-invitation-no-real-secret');await viewer.locator('#hosted-open').click();await viewer.locator('#sixd-workspace[aria-busy="false"]').waitFor();await viewer.waitForFunction(()=>document.documentElement.classList.contains('sixd-hosted'));
 assert.equal(await viewer.locator('#sd-rocket-launcher:visible').count(),1);
 await viewer.locator('[data-open-project]').first().click();await viewer.locator('#sixd-workspace[aria-busy="false"]').waitFor();
 await viewer.locator('#sd-rocket-launcher').click();assert.ok(await viewer.locator('#sd-rocket-dialog[open]').isVisible());assert.equal(await viewer.locator('[data-action="owner-settings"]:visible,[data-action="ai-settings"]:visible').count(),0);
 const visitorAI=await api(info.visitor,'/api/ai/status');assert.equal(Object.hasOwn(visitorAI,'budget'),false);assert.equal(typeof visitorAI.spend_available,'boolean');
 for(const path of ['/api/ai-quality/status','/api/ultra-workflow/status'])assert.equal((await context.request.get(info.visitor+path)).status(),403);
 for(const path of ['/api/ai/connect','/api/shutdown','/api/research/search'])assert.equal((await context.request.post(info.visitor+path,{data:{},headers:{Origin:info.visitor}})).status(),403);
 pass('Hosted reviewers get the rocket while owner controls, financial amounts and administrative service routes remain protected');
 assert.deepEqual(await snapshot(),before);const afterStatus=await api(info.owner,'/api/ai/status');assert.equal(afterStatus.budget.cap_usd,beforeStatus.budget.cap_usd);assert.ok(afterStatus.budget.reserved_usd>beforeStatus.budget.reserved_usd);
 assert.equal(posts.filter(p=>p.path==='/api/investigations').length,2);assert.equal(posts.filter(p=>p.path==='/api/research/search').length,1);
 assert.ok(posts.every(p=>['/api/investigations','/api/research/search','/api/hosted/login','/api/impact','/api/interfaces/preview','/api/test-evidence/impact'].includes(p.path)),JSON.stringify(posts.map(p=>p.path)));
 assert.deepEqual(external,[]);assert.deepEqual(errors,[]);assert.deepEqual(badResponses,[]);assert.deepEqual(failures.filter(r=>r.error!=='net::ERR_ABORTED'),[]);
 pass('Canonical engineering and the shared cap remain unchanged; only deliberate synthetic investigations/search and visitor login posted');
 const result={schema:'sixd.rocket-browser-acceptance.v1',synthetic_fixture:true,checks,errors,external_requests:external.length,unexpected_responses:badResponses,post_routes:posts.map(p=>p.path),synthetic_nemotron_starts:2,synthetic_tavily_searches:1,live_provider_calls:0,canonical_unchanged:true,allowance_unchanged:true};
 await writeFile(join(output,'results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}catch(error){if(page)await page.screenshot({path:join(output,'failure.png'),fullPage:true}).catch(()=>{});console.error(error.stack||error);console.error(JSON.stringify({errors,badResponses,failures,post_routes:posts.map(p=>p.path),stderr}));process.exitCode=1;}
finally{releaseResearchProfile?.();await browser?.close();if(child.exitCode===null){const done=new Promise(yes=>child.once('exit',yes));child.kill();await done;}}
