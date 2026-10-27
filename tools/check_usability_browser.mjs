/* Six-issue usability acceptance on isolated synthetic owner + visitor servers.
 * Run from the repository root: node tools/check_usability_browser.mjs
 * Never opens founder data, credentials or provider networks. */
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdir,mkdtemp,readFile,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';

const root=process.cwd(),output=resolve(root,'work/usability-browser');await mkdir(output,{recursive:true});
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
p=example_projects()['missing_evidence'];p.update(project_id='rocket-review',name='Rocket usability walkthrough (constructed)',revision='1')
owner.store.create_project(p);owner.store.run(p['project_id'],1);owner.store.ensure_default=lambda:p['project_id']
owner.ai.connect('synthetic-rocket-key-never-network');owner.research.connect('synthetic-usability-research-key-only',1)
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
 browser=await playwright.chromium.launch({channel:process.env.SIXD_BROWSER_CHANNEL||'chrome',headless:true,args:['--enable-unsafe-swiftshader']});
 const context=await browser.newContext({viewport:{width:1512,height:1060}}),allowed=new Set([info.owner,info.visitor]);
 await context.route('**/*',route=>{if(!allowed.has(new URL(route.request().url()).origin)){external.push(route.request().url());return route.abort();}return route.continue();});
 const observe=p=>{p.setDefaultTimeout(25000);p.on('pageerror',error=>errors.push(error.stack||error.message));p.on('requestfailed',r=>failures.push({path:new URL(r.url()).pathname,error:r.failure()?.errorText}));p.on('request',r=>{if(r.method()==='POST')posts.push({origin:new URL(r.url()).origin,path:new URL(r.url()).pathname,data:r.postDataJSON()});});p.on('response',r=>{if(allowed.has(new URL(r.url()).origin)&&r.status()>=400)badResponses.push({path:new URL(r.url()).pathname,status:r.status()});});};
 page=await context.newPage();observe(page);
 const api=async(origin,path)=>{const response=await context.request.get(origin+path);assert.equal(response.status(),200,await response.text());return response.json();};
 const savedPath='/api/workspace?project_id='+info.project_id+'&revision=1';
 const sourcePath='/api/sources?project_id='+info.project_id+'&revision=1';
 const before=await api(info.owner,savedPath),beforeSources=await api(info.owner,sourcePath),beforeStatus=await api(info.owner,'/api/ai/status');
 const idle=()=>page.locator('#sixd-workspace[aria-busy="false"]').waitFor();
 const click=async action=>{await page.locator('[data-action="'+action+'"]:visible').first().click();await idle();};
 const route=async name=>{await page.goto(info.owner+'/'+(name==='projects'?'#/projects':'#/projects/'+info.project_id+'/r/1/'+name));await idle();};
 const waitChoices=()=>page.waitForFunction(()=>document.querySelectorAll('#sd-ai-model option').length===3&&!document.querySelector('#sd-ai-model').disabled);
 const openRocket=async(tab='nemotron')=>{if(!await page.locator('#sd-rocket-dialog').evaluate(d=>d.open))await page.locator('#sd-rocket-launcher').click();if(await page.locator('[data-rocket-tab="'+tab+'"]').getAttribute('aria-selected')!=='true')await page.locator('[data-rocket-tab="'+tab+'"]').click();};
 const closeRocket=async()=>{await page.locator('#sd-rocket-dialog [data-rocket-close]').click();await page.waitForFunction(()=>!document.querySelector('#sd-rocket-dialog').open);};
 const placement=()=>page.evaluate(()=>JSON.parse(localStorage.getItem('sixd.rocket.placement.v2')));
 const safeRocket=async()=>{
  await page.waitForTimeout(180);
  const report=await page.locator('.sd-rocket-companion').evaluate(companion=>{
   const box=companion.getBoundingClientRect(),overlaps=[];
   for(const node of document.querySelectorAll('#sixd-workspace button,#sixd-workspace a[href],#sixd-workspace input,#sixd-workspace select,#sixd-workspace textarea,#sixd-workspace summary,#sixd-workspace [role="button"],#sixd-workspace [role="tab"],#sixd-workspace [data-kind][data-id]')){
    if(companion.contains(node)||node.closest('dialog')||!node.getClientRects().length)continue;
    const rect=node.getBoundingClientRect(),left=Math.max(box.left,rect.left,0),right=Math.min(box.right,rect.right,innerWidth),top=Math.max(box.top,rect.top,0),bottom=Math.min(box.bottom,rect.bottom,innerHeight);
    if(right-left<1||bottom-top<1)continue;
    const underneath=document.elementsFromPoint((left+right)/2,(top+bottom)/2).filter(element=>!companion.contains(element));
    if(underneath.some(element=>element===node||node.contains(element)))overlaps.push(node.getAttribute('aria-label')||node.textContent.trim().slice(0,90)||node.tagName);
   }
   return{left:box.left,top:box.top,right:box.right,bottom:box.bottom,mode:companion.dataset.mode,inline:companion.classList.contains('sd-rocket-inline'),overlaps,width:innerWidth,height:innerHeight};
  });
  assert.deepEqual(report.overlaps,[],JSON.stringify(report));assert.ok(report.left>=7&&report.top>=0&&report.right<=report.width-7&&report.bottom<=report.height-7,JSON.stringify(report));
  return report;
 };
 for(const name of ['projects','engineering','analysis','review-home','system']){
  await route(name);
  if(await page.locator('#sd-review-guide').isVisible()){await click('guided-close');await page.locator('#sd-review-guide').waitFor({state:'hidden'});}
  const location=page.url();await click('guided-toggle');await page.locator('#sd-review-guide').waitFor({state:'visible'});
  assert.equal(await page.locator('[data-action="guided-toggle"]').getAttribute('aria-expanded'),'true');assert.equal(page.url(),location);
  assert.match(await page.locator('#sd-review-guide').innerText(),/project|review|design|baseline/i);
  await click('guided-close');await page.locator('#sd-review-guide').waitFor({state:'hidden'});
 }
 assert.equal(posts.filter(r=>r.path==='/api/run').length,0);assert.equal((await callLog()).length,0);
 pass('Guided review opens and closes in place from Projects, work-area hubs, Overview and Systems without hidden navigation or provider calls');
 await route('review-home');await page.locator('.rw-workspace[aria-busy="false"]').waitFor();
 const oldRun=before.run.run_id;
 let firstRun;
 for(const [index,label] of [[0,'Calculate'],[1,'Recalculate']]){
  await page.locator('[data-rw-disclosure="workflow"] > summary').click();
  let release,entered;const gate=new Promise(resolve=>release=resolve),pending=new Promise(resolve=>entered=resolve);
  const hold=async request=>{entered();await gate;await request.continue();};
  await page.route(info.owner+'/api/run',hold);
  const completed=page.waitForResponse(r=>r.url()===info.owner+'/api/run'&&r.request().method()==='POST');
  const control=page.locator('#sd-project-journey [data-rw="run"]').nth(index);await control.click();await pending;
  assert.equal(await page.locator('#sixd-workspace').getAttribute('aria-busy'),'true');
  assert.equal(await page.locator('#sd-calculation-feedback').getAttribute('data-phase'),'working');
  assert.ok((await page.locator('#sd-calculation-feedback').innerText()).trim().length>0,label+' progress must be visible');
  await control.evaluate(node=>node.click());assert.equal(posts.filter(r=>r.path==='/api/run').length,index+1,'Only one run may start while a run is pending');
  release();const response=await completed;assert.equal(response.status(),200);const saved=await response.json();await idle();await page.locator('.rw-workspace[aria-busy="false"]').waitFor();
  assert.equal(saved.revision,1);assert.deepEqual(saved.project,before.project);assert.deepEqual(saved.run.model_results,before.run.model_results);
  assert.notEqual(saved.run.run_id,index===0?oldRun:firstRun);if(index===0)firstRun=saved.run.run_id;
  assert.equal(await page.locator('#sd-calculation-feedback').getAttribute('data-phase'),'done');
  assert.match(await page.locator('#sd-calculation-feedback').innerText(),/Calculation complete for R1/i);
  await page.unroute(info.owner+'/api/run',hold);
 }
 pass('Calculate and Recalculate each save a new review on an already calculated revision, show progress/completion and prevent duplicate in-flight starts');
 await page.locator('#sd-rocket-canvas').waitFor();
 await page.waitForFunction(()=>document.querySelector('#sd-rocket-canvas')?.dataset.renderer==='webgl'&&Number(document.querySelector('#sd-rocket-canvas').dataset.frameCount)>0);
 const renderer=await page.locator('#sd-rocket-canvas').evaluate(canvas=>({renderer:canvas.dataset.renderer,frames:Number(canvas.dataset.frameCount),width:canvas.width,height:canvas.height}));
 assert.equal(renderer.renderer,'webgl');assert.ok(renderer.frames>0&&renderer.width>=64&&renderer.height>=64);
 await page.locator('#sd-rocket-launcher').screenshot({path:join(output,'rocket-metal-detail.png')});
 pass('The companion draws actual local WebGL geometry rather than the previous SVG, with frames rendered before interaction');
 const launcher=page.locator('#sd-rocket-launcher'),origin=await launcher.boundingBox();
 const end={x:Math.min(1000,1512-origin.width-20),y:420};
 await page.mouse.move(origin.x+origin.width/2,origin.y+origin.height/2);await page.mouse.down();await page.mouse.move(end.x,end.y,{steps:14});await page.mouse.up();
 assert.equal(await page.locator('#sd-rocket-dialog').evaluate(dialog=>dialog.open),false);
 const dragged=await launcher.boundingBox();assert.ok(Math.abs(dragged.x-origin.x)>100||Math.abs(dragged.y-origin.y)>100);
 const savedPlacement=await placement(),position=savedPlacement.position;assert.equal(savedPlacement.version,2);assert.ok(position.x>=0&&position.x<=1&&position.y>=0&&position.y<=1);await safeRocket();
 await page.reload();await idle();await safeRocket();assert.deepEqual(await placement(),savedPlacement,'Reload retains the exact preferred position; current controls can require a different safe resting point.');
 await launcher.focus();const keyStart=await page.locator('.sd-rocket-companion').boundingBox();const beforeKey=(await placement()).position;await page.keyboard.press(beforeKey.x>.75?'Alt+ArrowLeft':'Alt+ArrowRight');const keyEnd=(await placement()).position;assert.notDeepEqual(keyEnd,beforeKey);await safeRocket();
 await launcher.click();await page.locator('#sd-rocket-dialog[open]').waitFor();await closeRocket();
 pass('Pointer dragging repositions without opening AI, restores its saved preference after reload, and retains click/keyboard movement while resting clear of page controls');
 await page.emulateMedia({reducedMotion:'reduce'});await page.waitForFunction(()=>document.querySelector('#sd-rocket-canvas')?.dataset.motion==='reduced');
 const stopped=await page.locator('#sd-rocket-canvas').getAttribute('data-frame-count');await page.waitForTimeout(150);assert.equal(await page.locator('#sd-rocket-canvas').getAttribute('data-frame-count'),stopped);
 await page.emulateMedia({reducedMotion:'no-preference'});
 pass('Reduced motion pauses the rocket animation without removing its functional launcher');
 await click('engineering');await click('system');await page.locator('#sd-tab-table').click();await page.locator('#sd-view-content [data-kind="requirement"][data-id="thermal_limit"]').first().click();
 await openRocket();await waitChoices();
 assert.deepEqual(await page.locator('#sd-ai-model option').evaluateAll(nodes=>nodes.map(node=>node.value)),['nano','super','ultra']);
 assert.ok(await page.locator('#sd-ai-question').isVisible());assert.ok(await page.locator('#sd-ai-start').isVisible());
 const body=await page.locator('#sd-rocket-ai-body').innerText();assert.doesNotMatch(body,/Cumulative reservations|Approved development allowance|Reservation capacity remaining|\$\d/);
 const beforeCalls=(await callLog()).length;
 const question='Explain the saved result in simple terms and name the next evidence check.';
 await page.locator('#sd-ai-question').fill(question);for(const model of ['nano','super','ultra']){await page.locator('#sd-ai-model').selectOption(model);assert.equal(await page.locator('#sd-ai-question').inputValue(),question);}
 assert.equal((await callLog()).length,beforeCalls);
 await page.screenshot({path:join(output,'nemotron-desktop.png')});
 const responsePromise=page.waitForResponse(r=>r.url()===info.owner+'/api/investigations'&&r.request().method()==='POST');await page.locator('#sd-ai-start').click();const jobResponse=await responsePromise;assert.equal(jobResponse.status(),200);const job=await jobResponse.json();await waitChoices();
 assert.equal((await api(info.owner,'/api/investigations/'+job.investigation_id)).state,'completed');assert.equal(posts.filter(p=>p.path==='/api/investigations').length,1);
 assert.ok(await page.locator('#sd-ai-history').count());assert.ok(await page.locator('#sd-rocket-dialog details').count()>0);
 pass('Nemotron keeps the primary question/model/start controls and all three models, makes no selection-triggered call, and preserves a completed evidence-backed answer');
 await page.locator('[data-rocket-tab="research"]').click();const targets=page.locator('#sd-rocket-research-host [data-sr-field="target"]');await targets.waitFor();
 const options=await targets.locator('option').evaluateAll(nodes=>nodes.map(node=>({value:node.value,label:node.textContent})));
 const normal=options.filter(option=>option.value);assert.ok(normal.length<=12);assert.ok(normal.every(option=>option.value.startsWith('requirement:')));assert.equal(new Set(normal.map(option=>option.value)).size,normal.length);assert.ok(normal.every(option=>!option.label.includes(' Â· saved finding')));
 const advanced=page.locator('#sd-rocket-research-host details.st-advanced');assert.equal(await advanced.evaluate(node=>node.open),false);await advanced.locator('summary').click();
 const exact=page.locator('#sd-rocket-research-host [data-sr-field="advanced-target"]');const exactValues=await exact.locator('option').evaluateAll(nodes=>nodes.map(node=>node.value));assert.ok(exactValues.some(value=>value.startsWith('finding:')));assert.ok(exactValues.some(value=>value.startsWith('assumption:')||value.startsWith('model:')));
 await exact.selectOption(exactValues.find(value=>value.startsWith('finding:')));assert.equal(await exact.inputValue(),exactValues.find(value=>value.startsWith('finding:')));
 await targets.selectOption('requirement:thermal_limit');await page.locator('#sd-rocket-research-host [data-sr-field="query"]').fill('spacecraft steady radiative equilibrium assumptions');
 assert.equal(posts.filter(p=>p.path==='/api/research/search').length,0);assert.equal((await callLog()).filter(call=>call.service==='tavily').length,0);
 pass('Tavily starts with a small duplicate-free human-readable list, while Advanced preserves exact finding/assumption targets without starting a search');
 const searchResponse=page.waitForResponse(r=>r.url()===info.owner+'/api/research/search'&&r.request().method()==='POST');await page.locator('#sd-rocket-research-host [data-sr-action="search"]').click();assert.equal((await searchResponse).status(),200);
 await page.locator('#sd-rocket-research-host [data-sr-action="preview"]').click();
 assert.match(await page.locator('#sd-rocket-research-host .sr-preview').innerText(),/Preview · not saved or linked/i);
 assert.match(await page.locator('#sd-rocket-research-host [data-sr-action="use"]').innerText(),/Copy draft to Source library/);
 assert.match(await page.locator('#sd-rocket-research-host .sr-preview').innerText(),/only saved references linked to the chosen investigation scope/);
 await page.locator('#sd-rocket-research-host [data-sr-action="use"]').click();
 await page.waitForFunction(()=>document.querySelector('[data-sl-field="title"]')?.value==='Constructed spacecraft reference');
 assert.equal(await page.locator('[data-sl-editor]').evaluate(node=>node.open),true);assert.equal(posts.filter(p=>p.path==='/api/sources').length,0);assert.equal(posts.filter(p=>p.path==='/api/source-links').length,0);
 assert.match(await page.locator('[data-sl-source-form] .sl-stage').innerText(),/Copied draft · not saved or linked/i);
 assert.match(await page.locator('[data-sl-busy]').innerText(),/click Save reference.*explicit link/);
 assert.match(await page.locator('.sl-context').innerText(),/Copied drafts and unlinked saved references are excluded/);
 const sourceURL=page.url(),unfinished='Unfinished manual reference draft — preserve exact text';
 await page.locator('#sd-source-library').evaluate(node=>node.dataset.part3HandoffGuard='same-mounted-library');await page.locator('[data-sl-field="title"]').fill(unfinished);
 await openRocket('research');await page.locator('#sd-rocket-research-host [data-sr-action="preview"]').click();await page.locator('#sd-rocket-research-host .sr-preview').waitFor();
 const callsBeforeRefusal=(await callLog()).length,postsBeforeRefusal=posts.length;
 await page.locator('#sd-rocket-research-host [data-sr-action="use"]').click();await page.waitForFunction(()=>document.querySelector('#sd-rocket-research-host [data-sr-error]')?.textContent.includes('retained'));
 assert.equal(page.url(),sourceURL);assert.equal(await page.locator('#sd-rocket-dialog').evaluate(node=>node.open),true);
 assert.equal(await page.locator('#sd-source-library').getAttribute('data-part3-handoff-guard'),'same-mounted-library','same-page refusal must not remount the source editor');
 assert.equal(await page.locator('[data-sl-field="title"]').inputValue(),unfinished);assert.equal(await page.locator('#sd-rocket-research-host .sr-preview').isVisible(),true);
 assert.equal(posts.length,postsBeforeRefusal);assert.equal((await callLog()).length,callsBeforeRefusal);await closeRocket();await page.locator('[data-sl-field="title"]').fill('Constructed spacecraft reference');
 pass('Copying a preview to the same Source library refuses a nonempty editor, preserves its exact draft and mounted DOM, retains the preview and makes no extra search/save/link/model call');
 const pageGeometry=await page.locator('.sl-page').evaluate(node=>{const box=node.getBoundingClientRect(),main=document.querySelector('.sd-main').getBoundingClientRect();return{left:box.left-main.left,right:main.right-box.right,width:box.width};});assert.ok(pageGeometry.left>=15&&pageGeometry.right>=15&&pageGeometry.width<=1200);
 assert.ok(await page.locator('[data-sl-save-help]').count());assert.ok(await page.locator('[data-sl-link-help]').count());
 const title=page.locator('[data-sl-field="title"]');await title.fill('');assert.equal(await page.locator('[data-sl-action="save-source"]').isDisabled(),true);assert.match(await page.locator('[data-sl-save-help]').innerText(),/title|name/i);await title.fill('Constructed spacecraft reference');
 await page.screenshot({path:join(output,'source-library-desktop.png'),fullPage:true});
 const savedResponse=page.waitForResponse(r=>r.url()===info.owner+'/api/sources'&&r.request().method()==='POST');await page.locator('[data-sl-action="save-source"]').click();assert.equal((await savedResponse).status(),200);
 const savedSources=await api(info.owner,sourcePath);assert.equal(savedSources.sources.length,beforeSources.sources.length+1);assert.equal(savedSources.links.length,beforeSources.links.length);
 const savedSource=savedSources.sources.find(source=>!beforeSources.sources.some(old=>old.source_id===source.source_id));assert.ok(savedSource);
 await page.waitForFunction(id=>document.querySelector('[data-sl-link="source_id"]')?.value===id,savedSource.source_id);
 assert.match(await page.locator('.sl-library-source .sl-eyebrow').innerText(),/Saved · source v1/i);assert.match(await page.locator('[data-sl-busy]').innerText(),/Saved to the library.*not linked yet/);
 assert.equal(await page.locator('[data-sl-links]').evaluate(node=>node.open),true);assert.equal(await page.locator('[data-sl-action="ask-linked-reference"]').count(),0);
 assert.equal(posts.filter(p=>p.path==='/api/source-links').length,0);await page.locator('[data-sl-link="target_id"]').selectOption('requirement:thermal_limit');await page.locator('[data-sl-link="note"]').fill('Synthetic reference retained for manual review of the thermal-model assumptions.');
 const linkedResponse=page.waitForResponse(r=>r.url()===info.owner+'/api/source-links'&&r.request().method()==='POST');await page.locator('[data-sl-action="link-source"]').click();assert.equal((await linkedResponse).status(),200);
 const linked=await api(info.owner,sourcePath);assert.equal(linked.links.length,beforeSources.links.length+1);const newLink=linked.links.find(link=>link.source_id===savedSource.source_id&&link.target.target_id==='requirement:thermal_limit');assert.ok(newLink);assert.equal(newLink.source_version,savedSource.version);
 await page.locator('[data-sl-action="ask-linked-reference"]').waitFor();assert.match(await page.locator('[data-sl-busy]').innerText(),/Linked to the selected project check/);
 pass('The Source library shows Copied draft, Saved source version and Linked progress, and saves/links only through two separate explicit actions with the exact source version');
 const startsBeforeReference=posts.filter(post=>post.path==='/api/investigations').length,callsBeforeReference=(await callLog()).length;
 const exactScopeResponse=page.waitForResponse(response=>{const url=new URL(response.url());return response.request().method()==='GET'&&url.pathname==='/api/investigations'&&url.searchParams.get('project_id')===info.project_id&&url.searchParams.get('revision')==='1'&&url.searchParams.get('scope')==='requirement'&&url.searchParams.get('requirement_id')==='thermal_limit';});
 await page.locator('[data-sl-action="ask-linked-reference"]').click();assert.equal((await exactScopeResponse).status(),200);await waitChoices();
 const handoffSummary=await page.locator('#sd-ai-context-summary').innerText(),currentSaved=await api(info.owner,savedPath);
 assert.match(handoffSummary,new RegExp(savedSource.source_id));assert.ok(handoffSummary.includes(before.project.name+' · R1'));assert.ok(handoffSummary.includes(currentSaved.run.run_id));assert.ok(handoffSummary.includes(before.project.requirements.find(row=>row.id==='thermal_limit').title));assert.match(handoffSummary,/1 linked reference available in this scope/);
 assert.equal(await page.locator('[data-rocket-tab="nemotron"]').getAttribute('aria-selected'),'true');assert.ok((await page.locator('#sd-ai-question').inputValue()).trim());assert.equal(posts.filter(post=>post.path==='/api/investigations').length,startsBeforeReference);assert.equal((await callLog()).length,callsBeforeReference);
 await page.screenshot({path:join(output,'linked-reference-handoff.png')});await closeRocket();
 pass('Ask about this reference opens the same rocket with its exact saved project/revision/calculation/check and source identity, without starting inference or repeating search/save/link');
 const fonts=await page.evaluate(()=>{
  const family=selector=>{const node=document.querySelector(selector);return node?{selector,font:getComputedStyle(node).fontFamily,size:parseFloat(getComputedStyle(node).fontSize)}:null;};
  return{base:getComputedStyle(document.querySelector('#sixd-workspace')).fontFamily,samples:['#sd-project-picker','#sd-project-picker option','#sd-page-title','#sd-location-trail button','.sl-page p','[data-sl-link="source_id"]','[data-sl-link="note"]'].map(family)};
 });for(const sample of fonts.samples){assert.ok(sample,sample?.selector);assert.equal(sample.font,fonts.base,JSON.stringify(sample));assert.ok(sample.size>=13,JSON.stringify(sample));}
 await openRocket();await waitChoices();const assistantFonts=await page.locator('#sd-rocket-dialog').evaluate(dialog=>[dialog.querySelector('h2'),dialog.querySelector('#sd-ai-question'),dialog.querySelector('#sd-ai-model'),dialog.querySelector('#sd-ai-start')].map(node=>getComputedStyle(node).fontFamily));assert.ok(assistantFonts.every(font=>font===fonts.base));
 await closeRocket();
 pass('Project names, source text, native controls and Nemotron dialog copy share the global UI font rather than local module-specific stacks');
 await page.setViewportSize({width:390,height:844});let mobile=await launcher.boundingBox();assert.ok(mobile.x>=7&&mobile.y>=7&&mobile.x+mobile.width<=383&&mobile.y+mobile.height<=837);
 await openRocket();const popup=await page.locator('#sd-rocket-dialog').boundingBox();assert.ok(popup.x>=0&&popup.x+popup.width<=391);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
 await page.screenshot({path:join(output,'nemotron-mobile.png'),fullPage:true});await closeRocket();
 pass('Dragged companion and simplified conversation remain inside a narrow mobile viewport with no page-wide horizontal overflow');
 const viewer=await context.newPage();observe(viewer);await viewer.goto(info.visitor);await viewer.locator('#hosted-access-code').fill('synthetic-rocket-invitation-no-real-secret');await viewer.locator('#hosted-open').click();await viewer.locator('#sixd-workspace[aria-busy="false"]').waitFor();await viewer.locator('[data-open-project]').first().click();await viewer.locator('#sixd-workspace[aria-busy="false"]').waitFor();await viewer.locator('#sd-rocket-launcher').click();
 assert.equal(await viewer.locator('[data-action="owner-settings"]:visible,[data-action="ai-settings"]:visible').count(),0);const visitorAI=await api(info.visitor,'/api/ai/status');assert.equal(Object.hasOwn(visitorAI,'budget'),false);
 for(const path of ['/api/ai-quality/status','/api/ultra-workflow/status'])assert.equal((await context.request.get(info.visitor+path)).status(),403);
 pass('Simplified hosted conversation preserves the existing owner-only controls and financial-status boundary');
 const after=await api(info.owner,savedPath);assert.deepEqual(after.project,before.project);assert.deepEqual(after.run.model_results,before.run.model_results);assert.equal(after.revisions.length,before.revisions.length);
 assert.equal(posts.filter(p=>p.path==='/api/run').length,2);assert.equal(posts.filter(p=>p.path==='/api/investigations').length,1);assert.equal(posts.filter(p=>p.path==='/api/research/search').length,1);assert.equal(posts.filter(p=>p.path==='/api/sources').length,1);assert.equal(posts.filter(p=>p.path==='/api/source-links').length,1);
 assert.equal((await api(info.owner,'/api/ai/status')).budget.cap_usd,beforeStatus.budget.cap_usd);
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);assert.deepEqual(badResponses,[]);assert.deepEqual(failures.filter(r=>r.error!=='net::ERR_ABORTED'),[]);
 pass('Only explicit isolated actions posted; original design, numerical results and allowance remain unchanged, with no external provider traffic');
 if(await page.locator('#sd-rocket-dialog').evaluate(d=>d.open))await closeRocket();
 await page.setViewportSize({width:1512,height:1060});await page.waitForTimeout(450);await safeRocket();
 assert.equal(await page.locator('.sd-rocket-companion').getAttribute('data-mode'),'full','Desktop restores full geometry after automatic mobile compaction.');
 await page.locator('#sd-rocket-canvas').evaluate(canvas=>canvas.dispatchEvent(new Event('webglcontextlost',{cancelable:true})));
 assert.equal(await page.locator('#sd-rocket-canvas').getAttribute('data-renderer'),'fallback');
 assert.equal(await page.locator('.sd-rocket-fallback').isVisible(),true);
 await openRocket();assert.equal(await page.locator('#sd-rocket-dialog').evaluate(d=>d.open),true);await closeRocket();
 pass('Graphics-context loss exposes the honest local fallback while the draggable assistant remains functional');
 const result={schema:'sixd.usability-browser-acceptance.v1',synthetic_fixture:true,checks,errors,external_requests:external.length,unexpected_responses:badResponses,post_routes:posts.map(p=>p.path),explicit_local_runs:2,synthetic_nemotron_starts:1,synthetic_tavily_searches:1,explicit_reference_saves:1,explicit_reference_links:1,renderer,fonts,live_provider_calls:0,canonical_project_and_metrics_unchanged:true,allowance_unchanged:true};
 await writeFile(join(output,'results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}catch(error){if(page)await page.screenshot({path:join(output,'failure.png'),fullPage:true}).catch(()=>{});console.error(error.stack||error);console.error(JSON.stringify({errors,badResponses,failures,post_routes:posts.map(p=>p.path),stderr}));process.exitCode=1;}
finally{releaseResearchProfile?.();await browser?.close();if(child.exitCode===null){const done=new Promise(yes=>child.once('exit',yes));child.kill();await done;}}
