/* Build 3 acceptance against isolated owner AND protected visitor servers.
 * Run from the repository root: node tools/check_clarity_browser.mjs
 * No founder data, real key, provider/search/upload transport or cloud host used.
 */
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdir,mkdtemp,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';

const root=process.cwd(),output=resolve(root,'work/clarity-browser');await mkdir(output,{recursive:true});
const fixture=await mkdtemp(join(output,'fixture-'));
let playwright;try{playwright=await import(process.env.PLAYWRIGHT_MODULE||'playwright');}catch(error){if(process.env.PLAYWRIGHT_MODULE)throw error;playwright=await import('file:///C:/Users/Arya/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs');}
const python=process.env.SIXD_TEST_PYTHON||(process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
const source=`import json,os,sys,socket,threading,time
from pathlib import Path
from dataclasses import asdict
sys.path[:0]=[str(Path.cwd()/'src'),str(Path.cwd()/'tests')]
from sixd.providers import LiveConfig
from sixd.workspace_server import create_server
from sixd.project_examples import example_projects
from sixd.hosted_server import HostedConfig,create_hosted_server
from test_workspace_ai_api import offline_factory
folder=Path(sys.argv[1])
for key in ('NEBIUS_API_KEY','TAVILY_API_KEY','LANGSMITH_API_KEY'):os.environ.pop(key,None)
config=LiveConfig('https://api.tokenfactory.nebius.com/v1/','nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B','offline-clarity-browser',29.5,.06,.24,2048,45,'native_no_thinking','forced_action_v1')
(folder/'token-factory.json').write_text(json.dumps({**asdict(config),'account_verified':True,'model_license_reviewed':True,'spend_approved':True}),encoding='utf-8')
def forbidden(*args,**kwargs):raise AssertionError('Clarity navigation must not call external services')
owner=create_server(port=0,db_path=folder/'owner.sqlite3',ai_local_directory=folder,provider_factory=offline_factory,research_transport=forbidden,observability_transport=forbidden)
p=example_projects()['missing_evidence'];p.update(project_id='clarity-review',name='Clarity review (constructed)',revision='1')
owner.store.create_project(p);owner.store.run(p['project_id'],1);owner.store.ensure_default=lambda:p['project_id']
owner.ai.connect('synthetic-clarity-key-never-network')
job=owner.ai.start(p['project_id'],1,'thermal_limit','Explain the saved thermal finding.',model_choice='nano')
deadline=time.monotonic()+20
while owner.ai._active and time.monotonic()<deadline:time.sleep(.01)
if owner.ai.get(job['investigation_id'])['state']!='completed':raise AssertionError('Synthetic seed investigation failed')
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
visitor_origin='http://127.0.0.1:'+str(port)
visitor=create_hosted_server(HostedConfig(folder/'visitors',visitor_origin,'synthetic-clarity-invitation-no-real-secret',allow_loopback_http=True,get_limit=600,post_limit=100,login_limit=100),port=port)
threads=[threading.Thread(target=server.serve_forever,daemon=True) for server in (owner,visitor)]
for thread in threads:thread.start()
print(json.dumps({'owner':'http://127.0.0.1:'+str(owner.server_port),'visitor':visitor_origin,'project_id':p['project_id'],'seed_id':job['investigation_id']}),flush=True)
try:
 while True:time.sleep(1)
finally:
 for server in (owner,visitor):server.shutdown();server.server_close()
`;
const child=spawn(python,['-u','-c',source,fixture],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
let stderr='';child.stderr.on('data',chunk=>stderr+=chunk);let browser,page;
const checks=[],errors=[],external=[],failures=[],badResponses=[],posts=[];
const pass=message=>{checks.push(message);console.log('PASS '+message);};
try{
 const info=await new Promise((yes,no)=>{let raw='';const timer=setTimeout(()=>no(Error('Fixture startup timeout: '+stderr)),90000);child.stdout.on('data',chunk=>{raw+=chunk;try{const data=JSON.parse(raw.split('\n')[0]);clearTimeout(timer);yes(data);}catch{}});child.once('exit',code=>{clearTimeout(timer);no(Error('Fixture exited '+code+': '+stderr));});});
 browser=await playwright.chromium.launch({channel:process.env.SIXD_BROWSER_CHANNEL||'chrome',headless:true});
 const context=await browser.newContext({viewport:{width:1512,height:1060}});
 const allowed=new Set([info.owner,info.visitor]);
 await context.route('**/*',route=>{if(!allowed.has(new URL(route.request().url()).origin)){external.push(route.request().url());return route.abort();}return route.continue();});
 const observe=p=>{p.setDefaultTimeout(25000);p.on('pageerror',error=>errors.push(error.stack||error.message));p.on('requestfailed',r=>failures.push({path:new URL(r.url()).pathname,error:r.failure()?.errorText}));p.on('request',r=>{if(r.method()==='POST')posts.push({origin:new URL(r.url()).origin,path:new URL(r.url()).pathname});});p.on('response',r=>{if(allowed.has(new URL(r.url()).origin)&&r.status()>=400)badResponses.push({path:new URL(r.url()).pathname,status:r.status()});});};
 page=await context.newPage();observe(page);
 const api=async(origin,path)=>{const response=await context.request.get(origin+path);assert.equal(response.status(),200,await response.text());return response.json();};
 const snapshot=()=>api(info.owner,'/api/workspace?project_id='+info.project_id+'&revision=1');
 const before=await snapshot(),beforeStatus=await api(info.owner,'/api/ai/status');
 const idle=()=>page.locator('#sixd-workspace[aria-busy="false"]').waitFor();
 const click=async action=>{await page.locator('[data-action="'+action+'"]:visible').first().click();await idle();};
 await page.goto(info.owner+'/#/projects/'+info.project_id+'/r/1/review-home');await idle();
 await page.locator('.rw-workspace[aria-busy="false"]').waitFor();
 // Root maintains these two semantic surfaces as the compact main journey.
 await page.locator('#sd-result-legend').waitFor();
 const legend=await page.locator('#sd-result-legend').innerText();
 assert.match(legend,/met|meet/i);assert.match(legend,/unmet|not met/i);assert.match(legend,/not assessed|unassessed/i);assert.match(legend,/evidence|analysis|model/i);
 assert.ok(await page.locator('#sd-project-journey').isVisible());
 const overview=await page.locator('.rw-workspace').innerText();assert.match(overview,/next|inspect|review/i);
 assert.match(overview,/320/);assert.match(overview,/K/);
 pass('Overview explains all three result meanings and the main journey while preserving engineering values');
 await page.screenshot({path:join(output,'overview-desktop.png'),fullPage:true});
 await click('evidence');await click('report');
 await page.waitForFunction(()=>document.querySelector('#sd-page-title').textContent.includes('Engineering review'));
 const report=await page.locator('#sd-view-content').innerText();assert.match(report,/320\s*K/);assert.match(report,/not assessed|unassessed/i);
 pass('Review report retains quantitative criteria and unassessed scope without changing their meaning');
 await click('engineering');await click('system');await page.locator('#sd-tab-table').click();
 await page.locator('#sd-view-content [data-kind="requirement"][data-id="thermal_limit"]').first().click();
 await page.locator('#sd-rocket-launcher').click();
 await page.waitForFunction(()=>document.querySelectorAll('#sd-ai-model option').length===3);
 await page.waitForFunction(()=>document.querySelectorAll('#sd-ai-history .sd-ai-record').length===1);
 const assistant=await page.locator('#sd-rocket-ai-body').innerText();
 assert.doesNotMatch(assistant,/Approved development allowance|Cumulative reservations|Reservation capacity remaining|\$\d/);
 assert.ok(await page.locator('#sd-ai-model').isVisible());assert.equal(await page.locator('#sd-ai-question').inputValue(),'');
 pass('Normal requirement investigation keeps all models and history without visible financial accounting');
 await click('project-investigate');await page.waitForFunction(()=>document.querySelectorAll('#sd-ai-model option').length===3);
 assert.doesNotMatch(await page.locator('#sd-rocket-ai-body').innerText(),/Approved development allowance|Cumulative reservations|Reservation capacity remaining|\$\d/);
 pass('Whole-project investigation also keeps owner accounting out of the working view');
 await page.locator('#sd-rocket-dialog [data-rocket-close]').click();await page.waitForFunction(()=>!document.querySelector('#sd-rocket-dialog').open);
 await click('owner-settings');
 const ownerPanel=page.locator('#sd-owner-settings');
 await ownerPanel.waitFor();
 assert.match(await ownerPanel.innerText(),/owner workspace/i);
 await page.waitForFunction(()=>/\$29\.50/.test(document.querySelector('#sd-owner-settings').textContent));
 assert.match(await ownerPanel.textContent(),/allowance|reservation|spending|budget/i);
 pass('Detailed connection and spend controls remain available in the explicit owner surface');
 await page.screenshot({path:join(output,'owner-settings-desktop.png'),fullPage:true});
 await page.locator('[data-owner-action="nebius"]').click();
 const dialog=page.locator('#sd-ai-connect-dialog[open]');await dialog.waitFor();
 if(await dialog.count()){
  await page.locator('#sd-ai-key').fill('synthetic-unsaved-key-must-clear');
  const bounds=await dialog.boundingBox();await page.mouse.click(Math.max(2,bounds.x-12),Math.max(2,bounds.y-12));
  await page.waitForFunction(()=>!document.querySelector('#sd-ai-connect-dialog').open);
  assert.equal(await page.locator('#sd-ai-key').inputValue(),'');
  pass('Clicking outside owner connection dialog dismisses it and clears the unsaved key field');
 }
 await page.locator('[data-owner-action="tavily"]').click();
 const tavily=page.locator('#sd-tavily-dialog[open]');await tavily.waitFor();
 await tavily.locator('[data-sr-field="key"]').fill('synthetic-unsaved-tavily-key-never-sent');
 let bounds=await tavily.boundingBox();await page.mouse.click(Math.max(2,bounds.x-12),Math.max(2,bounds.y-12));
 await page.waitForFunction(()=>!document.querySelector('#sd-tavily-dialog').open&&!document.querySelector('#sd-tavily-settings input[type="password"]'));
 assert.equal(await page.locator('#sd-tavily-settings input[type="password"]').count(),0);
 await page.locator('[data-owner-action="tavily"]').click();await tavily.waitFor();
 assert.equal(await tavily.locator('[data-sr-field="key"]').inputValue(),'');
 bounds=await tavily.boundingBox();await page.mouse.click(Math.max(2,bounds.x-12),Math.max(2,bounds.y-12));
 await page.waitForFunction(()=>!document.querySelector('#sd-tavily-dialog').open);
 pass('Dynamically created Tavily settings dismiss outside, destroy the private field and reopen empty without connecting');
 await page.locator('details.sd-project-actions > summary').click();await click('new-project');
 const newProject=page.locator('#sd-new-dialog[open]');await newProject.waitFor();
 await page.locator('#sd-new-name').fill('Unapplied clarity form entry');
 bounds=await newProject.boundingBox();
 page.once('dialog',dialog=>dialog.dismiss());await page.mouse.click(Math.max(2,bounds.x-12),Math.max(2,bounds.y-12));
 assert.equal(await page.locator('#sd-new-dialog').evaluate(dialog=>dialog.open),true);
 assert.equal(await page.locator('#sd-new-name').inputValue(),'Unapplied clarity form entry');
 page.once('dialog',dialog=>dialog.dismiss());await page.locator('#sd-new-dialog [data-action="close-new"]').click();
 assert.equal(await newProject.evaluate(dialog=>dialog.open),true);
 assert.equal(await page.locator('#sd-new-name').inputValue(),'Unapplied clarity form entry');
 page.once('dialog',dialog=>dialog.dismiss());await page.keyboard.press('Escape');
 assert.equal(await newProject.evaluate(dialog=>dialog.open),true);
 assert.equal(await page.locator('#sd-new-name').inputValue(),'Unapplied clarity form entry');
 page.once('dialog',dialog=>dialog.accept());await page.mouse.click(Math.max(2,bounds.x-12),Math.max(2,bounds.y-12));
 await page.waitForFunction(()=>!document.querySelector('#sd-new-dialog').open);
 pass('Outside, close-button and Escape dismissal preserve edited project-form entries when declined; explicit discard closes the form');
 await page.setViewportSize({width:390,height:844});await click('review-home');await page.locator('.rw-workspace[aria-busy="false"]').waitFor();
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
 await page.screenshot({path:join(output,'overview-mobile.png'),fullPage:true});
 pass('Clear overview and result explanations fit a narrow mobile viewport');
 const viewer=await context.newPage();observe(viewer);await viewer.goto(info.visitor);
 await viewer.locator('#hosted-access-code').fill('synthetic-clarity-invitation-no-real-secret');await viewer.locator('#hosted-open').click();
 await viewer.locator('#sixd-workspace[aria-busy="false"]').waitFor();
 await viewer.waitForFunction(()=>document.documentElement.classList.contains('sixd-hosted'));
 const viewerKey=await api(info.visitor,'/api/ai/status');assert.equal(viewerKey.key_present,false);
 assert.equal(Object.hasOwn(viewerKey,'budget'),false);assert.equal(typeof viewerKey.spend_available,'boolean');
 assert.equal(Object.hasOwn(viewerKey,'max_job_reservation_usd'),false);
 assert.ok((viewerKey.available_models||[]).every(row=>!Object.hasOwn(row,'max_job_reservation_usd')));
 const hostedStatus=await api(info.visitor,'/api/hosted/status');assert.equal(Object.hasOwn(hostedStatus,'inference_budget'),false);
 assert.equal(typeof hostedStatus.inference_available,'boolean');
 assert.equal(await viewer.locator('[data-action="owner-settings"]:visible, [data-action="ai-settings"]:visible').count(),0);
 for(const route of ['/api/ai/connect','/api/shutdown','/api/ai-quality/start','/api/research/search','/api/observability/export']){
  const response=await context.request.post(info.visitor+route,{data:{},headers:{Origin:info.visitor}});assert.equal(response.status(),403,route);
 }
 for(const route of ['/api/ai-quality/status','/api/model-evaluation/status','/api/workflow-evaluation/status','/api/evidence-evaluation/status','/api/ultra-workflow/status']){
  const response=await context.request.get(info.visitor+route);assert.equal(response.status(),403,route);
 }
 pass('Protected visitor session has financial-status redaction and cannot execute or read owner administrative diagnostics');
 assert.deepEqual(await snapshot(),before);
 const afterStatus=await api(info.owner,'/api/ai/status');assert.equal(afterStatus.budget.reserved_usd,beforeStatus.budget.reserved_usd);
 assert.ok(posts.every(p=>p.path==='/api/hosted/login'||['/api/impact','/api/interfaces/preview','/api/test-evidence/impact'].includes(p.path)),JSON.stringify(posts));
 assert.deepEqual(external,[]);assert.deepEqual(errors,[]);assert.deepEqual(badResponses,[]);assert.deepEqual(failures.filter(r=>r.error!=='net::ERR_ABORTED'),[]);
 pass('Navigation/settings made no inference/search/upload/save calls and left the owner fixture unchanged');
 const result={schema:'sixd.clarity-browser-acceptance.v1',synthetic_fixture:true,checks,errors,external_requests:external.length,unexpected_responses:badResponses,post_routes:posts,live_provider_calls:0,canonical_unchanged:true,allowance_unchanged:true};
 await writeFile(join(output,'results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}catch(error){if(page)await page.screenshot({path:join(output,'failure.png'),fullPage:true}).catch(()=>{});console.error(error.stack||error);console.error(JSON.stringify({errors,badResponses,failures,posts,stderr}));process.exitCode=1;}
finally{await browser?.close();if(child.exitCode===null){const done=new Promise(yes=>child.once('exit',yes));child.kill();await done;}}
