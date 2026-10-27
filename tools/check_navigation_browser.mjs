/* Build 1 acceptance. Starts an isolated server; never targets the founder workspace.
 * Run from the repository root: node tools/check_navigation_browser.mjs
 * PLAYWRIGHT_MODULE may name an installed Playwright module or file URL.
 */
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp, mkdir, writeFile, readFile} from 'node:fs/promises';
import {resolve, join} from 'node:path';

const root=process.cwd(), output=resolve(root,'work/navigation-browser');
await mkdir(output,{recursive:true});
const isolated=await mkdtemp(join(output,'state-'));
const python=process.env.SIXD_TEST_PYTHON || (process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
let imported;
try { imported=await import(process.env.PLAYWRIGHT_MODULE || 'playwright'); }
catch (error) {
 if(process.env.PLAYWRIGHT_MODULE)throw error;
 imported=await import('file:///C:/Users/Arya/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs');
}
const {chromium}=imported;
const source=`import json,os,sys
from copy import deepcopy
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from sixd.workspace_server import create_server
from sixd.project_examples import integrated_rocket_review, staged_ascent_review
folder=Path(sys.argv[1])
for k in ('NEBIUS_API_KEY','LANGSMITH_API_KEY','TAVILY_API_KEY'):os.environ.pop(k,None)
def forbidden(*args,**kwargs):raise AssertionError('External service forbidden by navigation fixture')
with create_server(port=0,db_path=folder/'workspace.sqlite3',ai_local_directory=folder,provider_factory=forbidden,research_transport=forbidden,observability_transport=forbidden) as server:
 for suffix in ('a','b'):
  p=integrated_rocket_review();p['project_id']='navigation-'+suffix;p['name']='Navigation rocket '+suffix.upper()
  if suffix=='b':
   thermal=next(r for r in p['requirements'] if r['model_id']=='thermal')
   for component in ('battery','engine'):
    r=deepcopy(thermal);r['id']=component+'_temperature';r['title']=component.title()+' maximum temperature';p['requirements'].append(r)
  view=server.store.create_project(p);server.store.run(p['project_id'],1)
  if suffix=='a':
   p=deepcopy(view['project']);p['name']+=' revision 2'
   server.store.save_revision(p['project_id'],1,p);server.store.run(p['project_id'],2)
  if suffix=='b':
   for label in ('alpha','beta'):
    duplicate=integrated_rocket_review();duplicate['project_id']='duplicate-'+label+'-common';duplicate['name']='Repeated reference';server.store.create_project(duplicate)
 p=staged_ascent_review();p['project_id']='navigation-staged';p['name']='Navigation staged profile'\n view=server.store.create_project(p);p=deepcopy(view['project']);p['name']+=' revision 2';server.store.save_revision(p['project_id'],1,p)\n server.store.ensure_default=lambda:'navigation-a'
 print(json.dumps({'url':'http://127.0.0.1:'+str(server.server_port)}),flush=True)
 server.serve_forever()
`;
const child=spawn(python,['-u','-c',source,isolated],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
let stderr='';child.stderr.on('data',chunk=>{stderr+=chunk.toString();});
let browser,page;
const checks=[],errors=[],external=[],unexpectedResponses=[],posts=[],failedRequests=[];
const pass=label=>{checks.push(label);console.log('PASS '+label);};
try {
 const info=await new Promise((resolvePromise,reject)=>{
  let raw='';const timer=setTimeout(()=>reject(Error('Fixture startup timed out: '+stderr)),90000);
  child.stdout.on('data',chunk=>{raw+=chunk;try{const value=JSON.parse(raw.split('\n')[0]);clearTimeout(timer);resolvePromise(value);}catch{}});
  child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code+': '+stderr));});
 });
 const origin=info.url;
 browser=await chromium.launch({channel:process.env.SIXD_BROWSER_CHANNEL||'chrome',headless:true});
 const context=await browser.newContext({viewport:{width:1512,height:1060},acceptDownloads:true});
 page=await context.newPage();page.setDefaultTimeout(20000);
 page.on('pageerror',error=>errors.push(error.stack||error.message));
 page.on('request',request=>{if(request.method()==='POST')posts.push(new URL(request.url()).pathname);});
 page.on('requestfailed',request=>failedRequests.push({url:request.url(),error:request.failure()?.errorText}));
 page.on('response',response=>{if(response.url().startsWith(origin)&&response.status()>=400)unexpectedResponses.push({path:new URL(response.url()).pathname,status:response.status()});});
 await context.route('**/*',route=>{if(new URL(route.request().url()).origin!==origin){external.push(route.request().url());return route.abort();}return route.continue();});
 const api=async path=>{const r=await context.request.get(origin+path);assert.equal(r.status(),200,await r.text());return r.json();};
 const view=async(project='navigation-a',revision=2)=>api('/api/workspace?project_id='+project+'&revision='+revision);
 const idle=async()=>{await page.locator('#sixd-workspace[aria-busy="false"]').waitFor();};
 const click=async action=>{await page.locator('[data-action="'+action+'"]:visible').first().click();await idle();};
 const route=()=>page.evaluate(()=>decodeURIComponent(location.hash));
 const ensureProject=async id=>{await page.locator('#sd-project-picker').selectOption(id);await idle();};
 const initialA=await view(),initialB=await view('navigation-b',1),initialStaged=await view('navigation-staged',2),initialProjects=await api('/api/projects');
 await page.goto(origin);await idle();
 await page.screenshot({path:join(output,'projects-desktop.png'),fullPage:true});
 const duplicateCards=page.locator('[data-open-project^="duplicate-"]');
 const duplicateNames=await duplicateCards.locator('strong').allTextContents();
 assert.equal(duplicateNames.length,2);assert.equal(new Set(duplicateNames).size,2);
 assert.ok(duplicateNames.every(name=>name.includes('Repeated reference')));
 for(const id of ['duplicate-alpha-common','duplicate-beta-common'])assert.match(await page.locator('[data-open-project="'+id+'"]').getAttribute('title'),new RegExp(id));
 pass('Repeated project names are visibly distinct through stable real identities without renaming, deleting or hiding records');
 await page.locator('[data-open-project="navigation-a"]').click();await idle();await click('review-home');
 await page.locator('.rw-workspace[aria-busy="false"]').waitFor();
 assert.match(await route(),/navigation-a/);
 assert.match(await route(),/review-home/);
 pass('Selected project and saved revision have an addressable overview');
 const coverage=page.locator('.rw-coverage-context');
 assert.match(await coverage.innerText(),/Criterion counts above describe calculated requirements/);
 assert.match(await coverage.innerText(),/model.fit declaration/i);
 assert.match(await page.locator('[data-rw-coverage-status="applicability_unknown"]').innerText(),/9/);
 assert.match(await page.locator('[data-rw-coverage-status="missing_analysis"]').innerText(),/1/);
 assert.match(await page.locator('.rw-counts').innerText(),/9/);
 await coverage.locator('[data-rw-nav="coverage"]').click();await idle();assert.match(await route(),/coverage/);
 await click('review-home');await page.locator('.rw-workspace[aria-busy="false"]').waitFor();
 pass('Passing calculation criteria remain separate from nine missing fit declarations and one unsupported analysis, with a working coverage action');
 const reportLink=page.locator('.rw-map [data-rw-nav="report"]');
 await reportLink.scrollIntoViewIfNeeded();assert.ok(await page.evaluate(()=>scrollY)>200);
 await reportLink.click();await idle();await page.waitForFunction(()=>scrollY<2);
 assert.ok(await page.locator('#sd-page-title').evaluate(el=>el.getBoundingClientRect().top)>=0);
 const reportUrl=page.url();await page.evaluate(()=>scrollTo(0,1000));assert.ok(await page.evaluate(()=>scrollY)>200);
 await page.goBack();await page.waitForFunction(()=>location.hash.includes('/review-home'));await page.waitForFunction(()=>scrollY<2);
 await page.goForward();await page.waitForFunction(expected=>location.href===expected,reportUrl);await page.waitForFunction(()=>scrollY<2);
 await click('review-home');await page.locator('.rw-workspace[aria-busy="false"]').waitFor();
 await page.locator('.rw-map [data-rw-nav="report"]').click();await page.waitForFunction(()=>location.hash.endsWith('/report'));await page.waitForFunction(()=>scrollY<2);
 await click('review-home');await page.locator('.rw-workspace[aria-busy="false"]').waitFor();
 pass('Opening a report from lower Overview and accepted Back/Forward start at the page heading instead of inheriting a deep scroll');
 await click('analysis');
 assert.match(await page.locator('.sd-destination[data-action="vertical-mode"] .sd-tool-status').innerText(),/^Recorded calculation$/);
 assert.match(await page.locator('.sd-destination[data-action="simulation"] .sd-tool-status').innerText(),/Not configured/);
 assert.match(await page.locator('.sd-destination[data-action="guided-ascent"] .sd-tool-status').innerText(),/Not configured/);
 await ensureProject('navigation-staged');await click('analysis');
 assert.match(await page.locator('.sd-destination[data-action="staged-ascent"] .sd-tool-status').innerText(),/Configured · not calculated/);
 assert.match(await page.locator('.sd-destination[data-action="vertical-mode"] .sd-tool-status').innerText(),/Not configured/);
 await page.locator('#sd-revision-picker').selectOption('1');await idle();
 assert.match(await page.locator('.sd-tool-context').innerText(),/Saved R1.*Historical/);
 await ensureProject('navigation-a');await click('analysis');
 assert.match(await page.locator('.sd-destination[data-action="vertical-mode"] .sd-tool-status').innerText(),/^Recorded calculation$/);
 assert.match(await page.locator('.sd-tool-context').innerText(),/Saved R2/);
 pass('Tool badges distinguish recorded flight, absent mappings and uncalculated staging, and update across projects and historical revisions');
 await ensureProject('navigation-b');await click('review-home');await page.locator('#sd-rocket-launcher').click();
 await page.locator('#sd-ai-scope').selectOption('requirement');
 const battery=await page.locator('#sd-rocket-requirement option[value="battery_temperature"]').innerText();
 const engine=await page.locator('#sd-rocket-requirement option[value="engine_temperature"]').innerText();
 assert.match(battery,/Battery/i);assert.match(engine,/Engine/i);assert.notEqual(battery,engine);
 await page.locator('#sd-rocket-dialog [data-rocket-close]').click();
 await ensureProject('navigation-a');await click('review-home');await page.locator('.rw-workspace[aria-busy="false"]').waitFor();
 pass('The actual assistant picker distinguishes battery and engine temperature checks while retaining their exact requirement IDs without inference');
 const exactAltitude=initialA.run.review.findings.burnout_height.evidence.metric.value;
 const altitudeRow=page.locator('.rw-findings-table tr').filter({has:page.locator('[data-rw-requirement="burnout_height"]')});
 assert.match(await altitudeRow.locator('td.rw-quantity').first().innerText(),/6,126\.146 m/);
 assert.match(await altitudeRow.locator('.sd-number').first().evaluate(el=>getComputedStyle(el).fontFamily),/mono|Consolas/i);
 await page.locator('[data-rw-requirement="burnout_height"]').click();
 assert.ok((await page.locator('[data-exact-values]').innerText()).includes(String(exactAltitude)));
 assert.equal(await page.locator('h1:visible').count(),1);
 pass('Overview uses compact shared precision while a selected finding exposes exact values and preserves its canonical status');
 await click('setup');await click('author-project');await page.locator('.sd-authoring').waitFor();
 assert.equal(await page.locator('details.sd-author-group').count(),3);
 assert.equal(await page.locator('details.sd-author-group[open]').count(),0);
 const inputsGroup=page.locator('details[data-disclosure-key*="author-group:inputs"]');await inputsGroup.locator(':scope > summary').click();
 const thrustRecord=page.locator('details[data-disclosure-key*="author-record:input:thrust"]');await thrustRecord.locator(':scope > summary').click();
 assert.ok((await thrustRecord.innerText()).includes(initialA.project.inputs.thrust.source));
 const downloadPromise=page.waitForEvent('download');await page.locator('[data-action="export-project"]:visible').first().click();const download=await downloadPromise;
 assert.deepEqual(JSON.parse(await readFile(await download.path(),'utf8')),initialA.project);
 pass('Authoring groups retain every input source and record action, and project export preserves original names, SI unit strings and full numeric values');
 await click('author-edit');
 assert.equal(await inputsGroup.evaluate(el=>el.open),true);assert.equal(await thrustRecord.evaluate(el=>el.open),true);
 await thrustRecord.locator('[data-author-edit="input"]').click();await page.locator('#sd-author-dialog[open]').waitFor();
 await page.locator('#sd-author-dialog [name="value"]').fill('19500');
 const formSidebarState=await page.locator('#sd-sidebar-toggle').getAttribute('aria-expanded');
 await page.locator('#sd-author-dialog [name="value"]').press('Control+Backslash');
 assert.notEqual(await page.locator('#sd-sidebar-toggle').getAttribute('aria-expanded'),formSidebarState);
 assert.equal(await page.locator('#sd-author-dialog [name="value"]').inputValue(),'19500');assert.equal(await page.locator('#sd-author-dialog').evaluate(el=>el.open),true);
 await page.locator('#sd-author-dialog [name="value"]').press('Control+Backslash');
 assert.equal(await page.locator('#sd-sidebar-toggle').getAttribute('aria-expanded'),formSidebarState);
 await page.locator('#sd-author-dialog button[type="submit"]').click();
 await page.locator('#sd-author-dialog').waitFor({state:'hidden'});
 assert.equal(await inputsGroup.evaluate(el=>el.open),true);assert.equal(await thrustRecord.evaluate(el=>el.open),true);assert.match(await thrustRecord.locator(':scope > summary').innerText(),/19,500/);
 await page.locator('#sd-setup-validation').waitFor();assert.equal((await view()).project.inputs.thrust.value,20000);
 page.once('dialog',dialog=>dialog.accept());await ensureProject('navigation-b');await ensureProject('navigation-a');await click('analysis');await click('scenarios');
 const muChoice=page.locator('#sd-view-content option[value="gravitational_parameter"]');await muChoice.waitFor({state:'attached'});
 assert.match(await muChoice.innerText(),/m³\/s²/);assert.equal(await muChoice.getAttribute('value'),'gravitational_parameter');
 pass('Draft edits keep their grouped section open without saving, and readable native unit labels retain canonical selection values');
 await click('analysis');await click('vertical-mode');
 assert.equal(await page.locator('#sd-page-title').innerText(),'Vertical flight');assert.equal(await page.locator('.pf-page > h2:visible').count(),0);
 assert.equal(await page.locator('h1:visible').count(),1);assert.equal(await page.locator('.pf-page details').filter({hasText:'Assumptions and exclusions'}).count(),1);
 const exactFlight=page.locator('.pf-page details').filter({has:page.locator('summary').filter({hasText:'Exact saved metrics and numerical diagnostics'})});await exactFlight.locator(':scope > summary').click();
 assert.ok((await exactFlight.innerText()).includes(String(exactAltitude)));
 await page.getByRole('button',{name:'Open full report',exact:true}).click();await idle();const scopeDetails=page.locator('.sd-reader details[data-disclosure-key*="project-description"]');
 assert.equal(await scopeDetails.evaluate(el=>el.open),false);assert.equal(await page.locator('.sd-reader > h2:visible').count(),0);assert.equal(await page.locator('h1:visible').count(),1);
 assert.equal(await page.locator('.sd-reader > .sd-accuracy-warning').isVisible(),true);
 await page.evaluate(()=>dispatchEvent(new Event('beforeprint')));assert.equal(await scopeDetails.evaluate(el=>el.open),true);
 await page.evaluate(()=>dispatchEvent(new Event('afterprint')));assert.equal(await scopeDetails.evaluate(el=>el.open),false);
 await click('review-home');await page.locator('.rw-workspace[aria-busy="false"]').waitFor();
 pass('Pages keep one visible primary heading, preserve flight exclusions and exact diagnostics, and expand then restore folded project scope for printing');
 const home=page.url();
 for(const area of ['engineering','analysis','evidence','setup']){
  await click(area);assert.match(await route(),new RegExp(area));
  if(area==='engineering')await page.screenshot({path:join(output,'engineering-desktop.png'),fullPage:true});
  assert.ok((await page.locator('#sd-page-title').innerText()).trim());
 }
 pass('Five broad work areas are reachable without a flat list of every tool');
 await page.goBack();await page.waitForFunction(()=>location.hash.includes('/evidence'));assert.match(await route(),/evidence/);
 await page.goForward();await page.waitForFunction(()=>location.hash.includes('/setup'));assert.match(await route(),/setup/);
 pass('Native browser Back and Forward restore internal locations');
 await page.reload();await idle();assert.match(await route(),/setup/);
 assert.equal(await page.locator('#sd-project-picker').inputValue(),'navigation-a');
 assert.equal(await page.locator('#sd-revision-picker').inputValue(),'2');
 pass('Reload preserves the routed project, saved revision and work area');
 await page.locator('#sd-revision-picker').selectOption('1');await idle();
 const historicUrl=page.url();await page.reload();await idle();
 assert.equal(await page.locator('#sd-revision-picker').inputValue(),'1');assert.equal(page.url(),historicUrl);
 await page.locator('#sd-revision-picker').selectOption('2');await idle();
 pass('A deep link to a historical revision survives reload');
 await click('engineering');await click('system');
 await page.locator('#sd-tab-table').click();await page.locator('#sd-view-content [data-kind="requirement"]').first().click();
 await page.locator('[data-panel="evidence"]').click();
 const selectedRoute=page.url();await page.reload();await idle();
 assert.equal(page.url(),selectedRoute);
 assert.equal(await page.locator('#sd-tab-table').getAttribute('aria-selected'),'true');
 assert.equal(await page.locator('[data-panel="evidence"]').getAttribute('aria-selected'),'true');
 assert.match(await page.locator('#sd-location-trail').innerText(),/Engineering/);
 pass('System Table, selected requirement and evidence panel survive deep reload with a parent breadcrumb');
 await click('review-home');
 await page.locator('[data-rw="rocket-stage"]').click();await idle();
 assert.match(await page.locator('#sd-view-content').innerText(),/11,?000/);
 await click('evidence');assert.equal(await page.locator('#sd-draft-strip').isVisible(),true);
 await page.goBack();await page.waitForFunction(()=>location.hash.includes('/changes'));
 assert.equal(await page.locator('#sd-draft-strip').isVisible(),true);
 assert.equal((await view()).project.inputs.thrust.value,20000);
 assert.equal((await view()).latest_revision,2);
 pass('Same-project page navigation and Back retain the unsaved shared draft without a database write');
 // Cancel a project switch through its actual UI; verify the draft survives.
 page.once('dialog',dialog=>dialog.dismiss());await ensureProject('navigation-b');
 assert.equal(await page.locator('#sd-project-picker').inputValue(),'navigation-a');
 assert.equal(await page.locator('#sd-draft-strip').isVisible(),true);
 page.once('dialog',dialog=>dialog.accept());await ensureProject('navigation-b');
 assert.equal(await page.locator('#sd-project-picker').inputValue(),'navigation-b');
 assert.equal(await page.locator('#sd-draft-strip').isVisible(),false);
 pass('Cancelled project switch preserves draft; confirmed switch explicitly discards it');
 // Create a known cross-project history boundary, then exercise browser Back.
 await click('review-home');const bUrl=page.url();
 await ensureProject('navigation-a');await click('review-home');
 await page.locator('[data-rw="rocket-stage"]').click();await idle();
 const aDraftUrl=page.url();
 let dismissed=0;const rejectDialog=async d=>{dismissed++;await d.dismiss();};page.on('dialog',rejectDialog);
 // The staged Changes view is another entry; first Back is same project, second crosses projects.
 for(let n=0;n<8 && dismissed===0;n++){
  const before=page.url();await page.goBack();await page.waitForTimeout(120);
  if(before===page.url()&&dismissed>0)break;
 }
 page.off('dialog',rejectDialog);
 assert.ok(dismissed>0,'Browser Back crossing project must request draft consent');
 assert.equal(await page.locator('#sd-project-picker').inputValue(),'navigation-a');
 assert.equal(await page.locator('#sd-draft-strip').isVisible(),true);
 pass('Cancelling browser Back across project context preserves URL, displayed project and draft');
 let accepted=0;page.once('dialog',async d=>{accepted++;await d.accept();});
 await page.goBack();await idle();
 await page.waitForFunction(()=>document.querySelector('#sd-project-picker')?.value==='navigation-b');
 assert.equal(accepted,1);assert.equal(await page.locator('#sd-draft-strip').isVisible(),false);
 pass('Accepting browser Back loads the previous saved project and discards only the unsaved draft');
 // Simulate a slow saved-project read, then Back while the application is busy.
 const slowPattern=origin+'/api/workspace?project_id=navigation-a*';
 await page.route(slowPattern,async requestRoute=>{await new Promise(resolvePromise=>setTimeout(resolvePromise,400));await requestRoute.continue();});
 await page.locator('#sd-project-picker').selectOption('navigation-a');
 await page.waitForFunction(()=>document.querySelector('#sixd-workspace')?.getAttribute('aria-busy')==='true');
 await page.goBack();await idle();await page.waitForTimeout(500);
 const settledProject=await page.locator('#sd-project-picker').inputValue();
 assert.match(await route(),new RegExp(settledProject));
 await page.unroute(slowPattern);
 pass('Back during a delayed project load leaves URL and displayed project in the same context');
 await ensureProject('navigation-staged');await click('analysis');await click('staged-ascent');
 await page.locator('[data-sa-action="profile"]').click();
 const profileField=page.locator('[data-sa-profile-stage="0"][data-sa-profile-segment="0"][data-sa-profile-key="thrust_start"]');
 await profileField.fill('12345');const profileRoute=page.url();
 await click('engineering');assert.equal(page.url(),profileRoute);assert.equal(await profileField.inputValue(),'12345');
 assert.match(await page.locator('#sd-message').innerText(),/Apply or cancel/);
 await page.locator('#sd-project-picker').selectOption('navigation-a');await idle();
 assert.equal(await page.locator('#sd-project-picker').inputValue(),'navigation-staged');
 assert.equal(await profileField.inputValue(),'12345');
 await page.locator('#sd-revision-picker').selectOption('1');await idle();
 assert.equal(await page.locator('#sd-revision-picker').inputValue(),'2');assert.equal(await profileField.inputValue(),'12345');
 pass('Unapplied stage-profile values survive blocked area, project and revision navigation');
 await page.evaluate(()=>scrollTo(0,600));const profileScroll=await page.evaluate(()=>scrollY);
 await page.goBack();await page.waitForFunction(expected=>location.href===expected,profileRoute);await page.waitForTimeout(150);
 assert.equal(page.url(),profileRoute);assert.equal(await profileField.inputValue(),'12345');
 assert.equal(await page.locator('#sd-project-picker').inputValue(),'navigation-staged');
 assert.ok(Math.abs((await page.evaluate(()=>scrollY))-profileScroll)<2,'Blocked Back must not move the open profile');
 pass('Browser Back cannot remount or discard an unapplied stage-profile form');
 await page.locator('[data-sa-action="cancel-profile"]').click();assert.equal(await page.locator('[data-sa-profile-form]').count(),0);
 await click('engineering');assert.match(await route(),/engineering/);
 assert.deepEqual(await view('navigation-staged',2),initialStaged);
 pass('Explicit profile cancellation restores navigation while saved staged inputs stay unchanged');
 await ensureProject('navigation-a');await click('review-home');await page.locator('.rw-workspace[aria-busy="false"]').waitFor();
 const styles=await page.evaluate(()=>{
  const root=document.querySelector('#sixd-workspace'),heading=document.querySelector('h1'),body=getComputedStyle(root),h=getComputedStyle(heading);
  return {font:body.fontFamily,color:body.color,background:body.backgroundColor,headingTracking:h.letterSpacing,metricFont:getComputedStyle(document.querySelector('.rw-count-value')).fontFamily,bodyPx:parseFloat(body.fontSize),labelPx:parseFloat(getComputedStyle(document.querySelector('.sd-label')).fontSize),metricPx:parseFloat(getComputedStyle(document.querySelector('.rw-count-value')).fontSize)};
 });
 await page.evaluate(()=>document.fonts.ready);
 assert.match(styles.font,/^\"?Geist Sans/);
 assert.equal(await page.evaluate(()=>document.fonts.check('14px \"Geist Sans\"')),true);
 assert.equal(await page.evaluate(()=>document.fonts.check('14px \"Geist Mono\"')),true);
 assert.equal(styles.color,'rgb(29, 29, 31)');
 assert.notEqual(styles.background,'rgb(255, 255, 255)');
 assert.ok(parseFloat(styles.headingTracking)<0);
 assert.match(styles.metricFont,/mono|Consolas/i);
 assert.ok(styles.bodyPx>=14.5);assert.ok(styles.labelPx>=13);assert.ok(styles.metricPx>=13);
 pass('Actual locally loaded Geist Sans/Mono, readable sizes, ink and soft canvas cover the workspace with no external font request');
 const sidebarLocation=await route(),mountedMarker='keep-mounted-focus-layout';
 await page.locator('.rw-workspace').evaluate((node,token)=>node.dataset.focusFixture=token,mountedMarker);
 const mainBefore=await page.locator('.sd-main').boundingBox();await page.locator('#sd-sidebar-toggle').click();
 assert.equal(await page.locator('#sd-sidebar-toggle').getAttribute('aria-expanded'),'false');assert.equal(await page.locator('#sd-sidebar').isVisible(),false);
 assert.ok((await page.locator('.sd-main').boundingBox()).width>mainBefore.width+150);assert.equal(await route(),sidebarLocation);
 assert.equal(await page.locator('.rw-workspace').getAttribute('data-focus-fixture'),mountedMarker);assert.deepEqual(await view(),initialA);
 await page.reload();await idle();await page.locator('.rw-workspace[aria-busy=\"false\"]').waitFor();
 assert.equal(await page.locator('#sd-sidebar-toggle').getAttribute('aria-expanded'),'false');assert.equal(await page.locator('#sd-sidebar').isVisible(),false);assert.equal(await route(),sidebarLocation);
 await page.locator('#sd-sidebar-toggle').click();assert.equal(await page.locator('#sd-sidebar').isVisible(),true);
 assert.equal(await page.locator('#sd-sidebar-toggle').getAttribute('aria-expanded'),'true');
 pass('Sidebar focus mode gives the main content its width, remembers the preference and leaves route, mounted content and saved evidence unchanged');
 await page.screenshot({path:join(output,'desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.locator('#sd-sidebar').isVisible(),false);assert.equal(await page.locator('#sd-sidebar-toggle').getAttribute('aria-expanded'),'false');
 await page.locator('#sd-sidebar-toggle').click();assert.equal(await page.locator('#sd-sidebar').isVisible(),true);
 await page.locator('#sd-sidebar-toggle').click();assert.equal(await page.locator('#sd-sidebar').isVisible(),false);
 assert.equal(await route(),sidebarLocation);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
 await page.screenshot({path:join(output,'mobile.png'),fullPage:true});
 pass('Mobile sidebar has an explicit open/close control and independent preference without route changes or horizontal overflow');
 assert.deepEqual(await view(),initialA);assert.deepEqual(await view('navigation-b',1),initialB);assert.deepEqual(await view('navigation-staged',2),initialStaged);
 assert.deepEqual(await api('/api/projects'),initialProjects);
 assert.deepEqual(external,[]);assert.deepEqual(errors,[]);assert.deepEqual(unexpectedResponses,[]);
 const readOnlyPreviews=new Set(['/api/impact','/api/interfaces/preview','/api/test-evidence/impact','/api/authoring/preflight']);
 assert.ok(posts.every(path=>readOnlyPreviews.has(path)),'Only read-only draft previews may POST: '+posts.join(','));
 assert.deepEqual(failedRequests.filter(request=>request.error!=='net::ERR_ABORTED'),[]);
 pass('Original fixture receipts unchanged; no provider, search, upload, calculation or save POSTs; no browser errors');
 const result={schema:'sixd.navigation-browser-acceptance.v1',checks,errors,unexpected_responses:unexpectedResponses,external_requests:external.length,post_routes:posts,aborted_stale_requests:failedRequests.length,synthetic_fixture:true,paid_calls:0,typography:styles};
 await writeFile(join(output,'results.json'),JSON.stringify(result,null,2));
 console.log(JSON.stringify(result,null,2));
} catch(error){
 if(page)await page.screenshot({path:join(output,'failure.png'),fullPage:true}).catch(()=>{});
 const startup=page?await page.evaluate(()=>({ready:document.readyState,modules:Object.fromEntries(['SixDNavigation','SixDWorkspaceShell','SixDSystems','SixDPoweredFlight'].map(k=>[k,typeof window[k]])),resources:performance.getEntriesByType('resource').filter(e=>/\.js/.test(e.name)).map(e=>({url:e.name,duration:e.duration,bytes:e.transferSize}))})).catch(()=>null):null;console.error(error);console.error(JSON.stringify({url:page?.url(),errors,unexpectedResponses,posts,failedRequests,startup},null,2));if(stderr)console.error(stderr);process.exitCode=1;
} finally {
 if(browser)await browser.close();
 const closed=new Promise(resolvePromise=>child.once('exit',resolvePromise));if(child.exitCode===null){child.kill();await closed;}
}
