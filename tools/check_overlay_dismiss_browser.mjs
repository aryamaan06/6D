/* Isolated pointer/keyboard integration checks: no owner server or API calls. */
import assert from 'node:assert/strict';
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
const root=process.cwd(),output=resolve(root,'work/overlay-dismiss-browser');
await mkdir(output,{recursive:true});
let library;
try {library=await import(process.env.PLAYWRIGHT_MODULE||'playwright');}
catch {library=await import('file:///C:/Users/Arya/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs');}
const browser=await library.chromium.launch({channel:process.env.SIXD_BROWSER_CHANNEL||'chrome',headless:true});
const context=await browser.newContext({viewport:{width:1100,height:800}}),page=await context.newPage();
const errors=[],network=[],checks=[];
page.on('pageerror',error=>errors.push(error.message));
await context.route('**/*',route=>{network.push(route.request().url());return route.abort();});
const source=await readFile(resolve(root,'src/sixd/web/overlay-dismiss.js'),'utf8');
const pass=label=>{checks.push(label);console.log('PASS '+label);};
try {
 await page.setContent(`<!doctype html><html><head><style>body{padding:30px;font:16px system-ui}details{width:260px;margin-bottom:16px}summary,button,input{padding:10px}dialog{width:360px;padding:24px;border:1px solid #ddd;border-radius:12px}dialog::backdrop{background:#0002}#outside{position:absolute;left:8px;top:8px}</style></head><body>
 <button id="outside">Outside action</button>
 <details class="sd-project-actions" id="menu"><summary>Project actions</summary><nav><input id="menu-input"><button id="menu-action">Open report</button></nav></details>
 <details class="sd-source" id="explanation"><summary>Scope and limits</summary><p>Ordinary inline explanatory content.</p></details>
 <dialog id="connection"><h2>AI connection</h2><input id="key" type="password"><button id="inside">Inside action</button></dialog>
 <dialog id="editor"><h2>Record editor</h2><input id="draft" value="unchanged"></dialog>
 <script>window.outsideClicks=0;window.dismissals=[];document.querySelector('#outside').onclick=()=>outsideClicks++;document.querySelector('#connection').addEventListener('close',()=>document.querySelector('#key').value='');document.addEventListener('sixd:before-dismiss',e=>{dismissals.push(e.detail.reason);if(e.target.id==='editor'&&document.querySelector('#draft').value!=='unchanged')e.preventDefault();});</script>
 </body></html>`);
 await page.addScriptTag({content:source});
 await page.locator('#menu > summary').click();assert.equal(await page.locator('#menu').getAttribute('open'),'');
 await page.locator('#menu-input').click();assert.equal(await page.locator('#menu').getAttribute('open'),'');
 const menuBounds=await page.locator('#menu-input').boundingBox();
 await page.mouse.move(menuBounds.x+10,menuBounds.y+10);await page.mouse.down();await page.mouse.move(15,15);await page.mouse.up();
 assert.equal(await page.locator('#menu').getAttribute('open'),'');
 await page.locator('#outside').click();assert.equal(await page.locator('#menu').getAttribute('open'),null);
 pass('Project actions stays open for an inside field or inside-to-outside drag and closes on an outside click');
 await page.locator('#menu > summary').click();await page.locator('#menu-action').click();assert.equal(await page.locator('#menu').getAttribute('open'),null);
 await page.locator('#menu > summary').click();assert.equal(await page.locator('#menu').getAttribute('open'),'');
 await page.locator('#menu > summary').click();assert.equal(await page.locator('#menu').getAttribute('open'),null);
 await page.locator('#explanation > summary').click();await page.locator('#outside').click();assert.equal(await page.locator('#explanation').getAttribute('open'),'');
 pass('Menu action/trigger toggles work; ordinary explanatory disclosures are not dismissed');
 await page.evaluate(()=>document.querySelector('#connection').showModal());await page.locator('#key').fill('synthetic-private-test');
 await page.locator('#inside').click();assert.equal(await page.locator('#connection').getAttribute('open'),'');
 const before=await page.evaluate(()=>outsideClicks);await page.mouse.click(15,15);
 await page.waitForFunction(()=>!document.querySelector('#connection').open&&document.querySelector('#key').value==='');assert.equal(await page.locator('#key').inputValue(),'');assert.equal(await page.evaluate(()=>outsideClicks),before);
 pass('Outside pointer closes a native modal through its close hook, clears its key and cannot click through');
 await page.evaluate(()=>document.querySelector('#connection').showModal());
 const bounds=await page.locator('#connection').boundingBox();await page.mouse.move(bounds.x+30,bounds.y+30);await page.mouse.down();await page.mouse.move(15,15);await page.mouse.up();assert.equal(await page.locator('#connection').getAttribute('open'),'');
 await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.querySelector('#connection').open);
 pass('Dragging from inside to outside does not close a dialog; Escape retains native cancellation');
 await page.evaluate(()=>document.querySelector('#editor').showModal());await page.locator('#draft').fill('unsaved record');await page.mouse.click(15,15);assert.equal(await page.locator('#editor').getAttribute('open'),'');assert.equal(await page.locator('#draft').inputValue(),'unsaved record');
 await page.keyboard.press('Escape');assert.equal(await page.locator('#editor').getAttribute('open'),'');
 await page.locator('#draft').fill('unchanged');await page.mouse.click(15,15);await page.waitForFunction(()=>!document.querySelector('#editor').open);
 pass('A cancelable dismissal guard preserves unapplied record edits for both outside click and Escape');
 await page.evaluate(()=>{const d=document.createElement('dialog');d.id='dynamic';d.innerHTML='<h2>Dynamic intake</h2>';d.addEventListener('cancel',e=>{e.preventDefault();d.close();d.remove();window.dynamicCleaned=true;});document.body.append(d);d.showModal();});await page.mouse.click(15,15);await page.waitForFunction(()=>window.dynamicCleaned===true);assert.equal(await page.locator('#dynamic').count(),0);
 pass('Dynamically created dialogs retain module-specific cancel cleanup');
 await page.evaluate(()=>{const d=document.createElement('dialog');d.id='fallback';d.innerHTML='<h2>Fallback close</h2>';Object.defineProperty(d,'requestClose',{value:undefined});document.body.append(d);d.showModal();});await page.mouse.click(15,15);await page.waitForFunction(()=>!document.querySelector('#fallback').open);
 await page.locator('#menu > summary').click();await page.keyboard.press('Escape');assert.equal(await page.locator('#menu').getAttribute('open'),null);
 pass('Older requestClose fallback and menu Escape dismissal work');
 assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
 const result={schema:'sixd.overlay-dismiss-browser.v1',synthetic_fixture:true,checks,errors,network_requests:network.length,paid_calls:0};
 await writeFile(resolve(output,'results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}catch(error){await page.screenshot({path:resolve(output,'failure.png'),fullPage:true}).catch(()=>{});throw error;}
finally {await browser.close();}
