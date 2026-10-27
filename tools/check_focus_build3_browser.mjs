/* Focus Build 3 conversational acceptance on isolated synthetic owner + visitor servers.
 * Run from the repository root: node tools/check_focus_build3_browser.mjs
 * Never opens founder data, credentials or provider networks. */
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdir,mkdtemp,readFile,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';

const root=process.cwd(),output=resolve(root,'work/focus-build3-browser');await mkdir(output,{recursive:true});
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
 response=offline_transport(request)
 message=next((json.loads(row['content']) for row in payload['messages'] if row.get('role')=='user' and isinstance(row.get('content'),str) and 'question_data' in row['content']),{})
 args=json.loads(response['choices'][0]['message']['tool_calls'][0]['function']['arguments'])
 if args['action']=='finish':
  question=message.get('question_data','').casefold()
  args['summary']=("That refers to the burnout-altitude check, not the full mission. The criterion is met within the saved vertical-flight model; review whether its atmosphere and thrust assumptions describe your case." if 'why does that' in question else "Burnout altitude is the modelled height when the usable fuel is exhausted. The saved criterion is met within the bounded vertical-flight assumptions; inspect the supplied thrust, mass and declared altitude limit.")
  response['choices'][0]['message']['tool_calls'][0]['function']['arguments']=json.dumps(args)
 log({'service':'wire_context','question':message.get('question_data'),'history_turns':len(message.get('conversation_context',{}).get('turns',[])),'has_image_payload':any('image_url' in str(row.get('content','')) or 'data:image/' in str(row.get('content','')) for row in payload['messages'])})
 return response
def factory(config,ledger,key):return TokenFactoryProvider(config,ledger,api_key=key,transport=transport,action_adapter=ProjectActionAdapter())
def research(key,body):
 log({'service':'tavily','query':body['query']})
 return {'request_id':'synthetic-rocket-search','usage':{'credits':1},'results':[{'title':'Constructed spacecraft reference','url':'https://www.nasa.gov/example/rocket-browser-reference','content':'A synthetic test excerpt, not a verified NASA statement. Review model assumptions independently.','score':.8}]}
def forbidden(*args,**kwargs):raise AssertionError('Rocket acceptance must not upload external metrics')
owner=create_server(port=0,db_path=folder/'owner.sqlite3',ai_local_directory=folder,provider_factory=factory,research_transport=research,observability_transport=forbidden)
p=example_projects()['rocket_review'];p.update(project_id='rocket-review',name='Rocket usability walkthrough (constructed)',revision='1')
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
 const route=async()=>{await page.goto(info.owner+'/#/projects/'+info.project_id+'/r/1/review-home');await idle();};
 const open=async()=>{await page.locator('#sd-rocket-launcher').click();if(await page.locator('[data-rocket-tab="nemotron"]').getAttribute('aria-selected')!=='true')await page.locator('[data-rocket-tab="nemotron"]').click();await page.locator('#sd-ai-model:enabled').waitFor();};
 const closed=async()=>{await page.locator('[data-rocket-close]').click();await page.locator('#sd-rocket-dialog').waitFor({state:'hidden'});};
 const complete=async count=>{await page.waitForFunction(expected=>document.querySelectorAll('#sd-ai-transcript [data-conversation-state="completed"]').length===expected,count,{timeout:45000});await page.locator('#sd-ai-start:disabled').waitFor();};
 await route();await open();await page.locator('#sd-ai-scope').selectOption('requirement');await page.locator('#sd-rocket-requirement').selectOption('burnout_height');await page.locator('#sd-ai-model:enabled').waitFor();
 assert.equal(await page.locator('#sd-ai-question').getAttribute('spellcheck'),'true');assert.equal(await page.locator('#sd-ai-question').getAttribute('lang'),'en');assert.equal(await page.locator('#sd-ai-question').getAttribute('autocorrect'),'off');
 assert.equal(await page.locator('#sd-ai-transcript').isVisible(),true);assert.match(await page.locator('#sd-ai-transcript').innerText(),/Ask in your own words/);
 assert.equal(await page.locator('#sd-ai-model').inputValue(),'');
 assert.deepEqual(await page.locator('#sd-ai-model option').evaluateAll(nodes=>nodes.map(node=>node.value)),['','nano','super','ultra']);
 assert.match(await page.locator('#sd-ai-model option[value="nano"]').innerText(),/Quick explanations/);
 assert.match(await page.locator('#sd-ai-model option[value="super"]').innerText(),/Everyday review/);
 assert.match(await page.locator('#sd-ai-model option[value="ultra"]').innerText(),/Deeper reasoning/);
 await page.locator('#sd-ai-question').fill('A question before choosing a model');assert.equal(await page.locator('#sd-ai-start').isEnabled(),false);
 await page.locator('#sd-ai-model').selectOption('ultra');assert.match(await page.locator('#sd-ai-model-help').textContent(),/Ultra suits a deeper/);await closed();await open();assert.equal(await page.locator('#sd-ai-model').inputValue(),'ultra');
 await page.evaluate(()=>localStorage.setItem('sixd.assistant.model.v1','super'));await closed();await page.reload();await idle();await open();assert.equal(await page.locator('#sd-ai-model').inputValue(),'');assert.equal(posts.filter(r=>r.path==='/api/investigations').length,0);assert.equal((await api(info.owner,'/api/ai/status')).default_model_choice,beforeStatus.default_model_choice);
 pass('New chats require explicit choice even with an old Super preference; labels guide all three tasks, and an in-progress choice survives close without changing the server default');
 await page.locator('#sd-ai-scope').selectOption('requirement');await page.locator('#sd-rocket-requirement').selectOption('burnout_height');await page.locator('#sd-ai-model:enabled').waitFor();await page.locator('#sd-ai-model').selectOption('super');
 await page.locator('#sd-ai-question').fill('What does burnout altitude mean?');await page.locator('#sd-ai-start:enabled').waitFor();await page.locator('#sd-ai-question').press('Enter');await complete(1);
 assert.equal(await page.locator('#sd-ai-question').inputValue(),'');const first=page.locator('#sd-ai-transcript [data-conversation-state="completed"]').first();assert.match(await first.innerText(),/Burnout altitude is the modelled height/);assert.equal(await first.locator('details[data-conversation-details]').evaluate(node=>node.open),false);
 const firstId=await first.getAttribute('data-conversation-turn');assert.ok(firstId);assert.equal(posts.filter(r=>r.path==='/api/investigations')[0].data.model_choice,'super');assert.equal(Object.hasOwn(posts.filter(r=>r.path==='/api/investigations')[0].data,'parent_investigation_id'),false);
 const sendBox=await page.locator('#sd-ai-start').boundingBox(),dialogBox=await page.locator('#sd-rocket-dialog').boundingBox();assert.ok(sendBox.y+sendBox.height<=dialogBox.y+dialogBox.height,'Send stays inside the open chat');
 const primaryText=await first.locator('.sd-conversation-answer-body').innerText();assert.ok(primaryText.length>50);assert.equal(await first.locator('.sd-conversation-recorded').isVisible(),true);
 const defaultBox=await page.locator('#sd-rocket-dialog').boundingBox(),normalTranscript=await page.locator('#sd-ai-transcript').boundingBox();
 assert.ok(normalTranscript.height>=260,'normal chat has real reading space: '+normalTranscript.height);
 const preservedQuestion='Which input should I verify next?';await page.locator('#sd-ai-question').fill(preservedQuestion);
 const transcriptNode=await page.locator('#sd-ai-transcript').evaluateHandle(node=>node);
 await page.locator('[data-rocket-expand]').click();assert.equal(await page.locator('[data-rocket-expand]').getAttribute('aria-pressed'),'true');
 const expandedBox=await page.locator('#sd-rocket-dialog').boundingBox();assert.ok(expandedBox.width>defaultBox.width+100);assert.ok(expandedBox.height>=1000);
 assert.equal(await page.locator('#sd-ai-question').inputValue(),preservedQuestion);assert.equal(await page.locator('#sd-ai-model').inputValue(),'super');
 assert.equal(await transcriptNode.evaluate(node=>node===document.querySelector('#sd-ai-transcript')),true,'expansion retains the mounted chat');
 assert.equal(posts.filter(r=>r.path==='/api/investigations').length,1);
 await page.locator('#sd-rocket-dialog').screenshot({path:join(output,'expanded-conversation.png')});
 await page.locator('[data-rocket-expand]').click();assert.equal(await page.locator('[data-rocket-expand]').getAttribute('aria-pressed'),'false');
 assert.ok(Math.abs((await page.locator('#sd-rocket-dialog').boundingBox()).width-defaultBox.width)<1);
 await page.locator('#sd-ai-question').fill('');
 pass('Expand and Restore size preserve mounted transcript, question, selected model, saved context and request count while providing a near-full-window reading area');
 pass('A direct question is followed by its accepted plain-language answer before collapsed evidence, with the canonical result visible and composer cleared');
 await page.locator('#sd-ai-question').fill('Why does that matter for this check?');await page.locator('#sd-ai-question').press('Shift+Enter');assert.equal(posts.filter(r=>r.path==='/api/investigations').length,1);await page.locator('#sd-ai-question').press('Enter');await complete(2);
 const requests=posts.filter(r=>r.path==='/api/investigations');assert.equal(requests[1].data.parent_investigation_id,firstId);assert.match(await page.locator('#sd-ai-transcript').innerText(),/That refers to the burnout-altitude check/);assert.equal(await page.locator('#sd-ai-transcript .sd-conversation-user').count(),2);
 const wire=await callLog();assert.ok(wire.some(row=>row.service==='wire_context'&&row.history_turns===1));assert.ok(wire.every(row=>row.has_image_payload!==true));
 await page.locator('#sd-rocket-dialog').screenshot({path:join(output,'conversation.png')});const evidenceSummary=page.locator('#sd-ai-transcript details[data-conversation-details]').last().locator(':scope > summary');await evidenceSummary.scrollIntoViewIfNeeded();const evidenceTop=(await evidenceSummary.boundingBox()).y;await evidenceSummary.click();await page.waitForTimeout(150);assert.ok(Math.abs((await evidenceSummary.boundingBox()).y-evidenceTop)<=2,'opening evidence retains its heading');assert.equal(await page.locator('#sd-ai-transcript .sd-ai-record').last().isVisible(),true);
 pass('Follow-up is a second explicit turn with a server-validated parent and captured conversation; Shift+Enter adds a line and full historical evidence remains accessible');
 await page.locator('[data-action="ai-new-conversation"]').click();assert.equal(await page.locator('#sd-ai-model').inputValue(),'');assert.equal(await page.locator('#sd-ai-transcript .sd-conversation-turn').count(),0);assert.equal(posts.filter(r=>r.path==='/api/investigations').length,2);
 await page.locator('#sd-ai-history-disclosure > summary').click();await page.locator('[data-ai-resume="'+firstId+'"]').click();assert.equal(await page.locator('#sd-ai-transcript .sd-conversation-turn').count(),1);assert.equal(posts.filter(r=>r.path==='/api/investigations').length,2);
 await page.locator('[data-action="ai-new-conversation"]').click();await page.locator('#sd-ai-model').selectOption('nano');
 const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aCKkAAAAASUVORK5CYII=','base64');
 await page.locator('[data-aa-file]').setInputFiles({name:'local-chart.png',mimeType:'image/png',buffer:png});await page.locator('[data-aa-content]').waitFor();assert.match(await page.locator('#sd-ai-attachments').innerText(),/receives your description, not the image/);
 await page.locator('#sd-ai-question').fill('Explain these chart notes simply.');assert.equal(await page.locator('#sd-ai-start').isEnabled(),false);await page.locator('[data-aa-description]').fill('A user-supplied chart labelled burnout altitude, with a declared threshold.');assert.equal(await page.locator('#sd-ai-start').isEnabled(),true);
 await closed();await open();assert.equal(await page.locator('[data-aa-description]').inputValue(),'A user-supplied chart labelled burnout altitude, with a declared threshold.');
 await page.locator('#sd-ai-start').click();await complete(1);const imageRequest=posts.filter(r=>r.path==='/api/investigations').at(-1).data;assert.match(imageRequest.question,/User-supplied image notes/);assert.equal(Object.hasOwn(imageRequest,'parent_investigation_id'),false);assert.equal(Object.keys(imageRequest).some(key=>/image|attachment|file|base64/.test(key)),false);assert.equal(JSON.stringify(imageRequest).includes('data:image/'),false);assert.equal(JSON.stringify(imageRequest).includes('local-chart.png'),false);assert.equal(await page.locator('[data-aa-content]').isVisible(),false);
 pass('New/resumed conversations send nothing; image preview and notes survive close, and only explicitly supplied text is sent—no pixels, filename or hidden vision claim');
 await page.locator('[data-rocket-tab="research"]').click();await page.locator('[data-sr-field="query"]').waitFor();assert.equal(await page.locator('[data-sr-field="query"]').getAttribute('spellcheck'),'true');assert.equal(await page.locator('[data-sr-field="query"]').getAttribute('autocorrect'),'off');await page.locator('[data-sr-field="query"]').fill('areospace NASA');assert.equal(posts.filter(r=>r.path==='/api/research/search').length,0);
 await closed();await page.setViewportSize({width:390,height:844});await open();assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 await closed();await page.setViewportSize({width:1512,height:1060});const pageDetail=page.locator('[data-rw-disclosure="meaning"]');await pageDetail.locator(':scope > summary').scrollIntoViewIfNeeded();const pageSummary=pageDetail.locator(':scope > summary'),pageTop=(await pageSummary.boundingBox()).y;await pageSummary.click();await page.waitForTimeout(150);assert.ok(Math.abs((await pageSummary.boundingBox()).y-pageTop)<=2,'page disclosure retains its heading');
 pass('Installed disclosure guard keeps actual workspace and chat evidence headings stable while content opens below them');
 const after=await api(info.owner,savedPath);assert.deepEqual(after,before);assert.deepEqual(await api(info.owner,sourcePath),beforeSources);assert.equal((await api(info.owner,'/api/ai/status')).budget.cap_usd,beforeStatus.budget.cap_usd);
 assert.deepEqual(errors,[]);assert.deepEqual(badResponses,[]);assert.deepEqual(external,[]);
 pass('Tavily spelling changes only user text, mobile chat stays contained, and original project/sources/allowance remain unchanged without external traffic');
 const result={schema:'sixd.focus-build3-browser.v1',synthetic_fixture:true,checks,errors,unexpected_responses:badResponses,external_requests:external.length,synthetic_chat_turns:3,post_routes:posts.map(item=>item.path),paid_calls:0};await writeFile(join(output,'results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}catch(error){if(page)await page.screenshot({path:join(output,'failure.png'),fullPage:true}).catch(()=>{});console.error(error.stack||error);console.error(JSON.stringify({errors,badResponses,post_routes:posts.map(item=>item.path),stderr}));process.exitCode=1;}
finally{await browser?.close();if(child.exitCode===null){const done=new Promise(resolve=>child.once('exit',resolve));child.kill();await done;}}
