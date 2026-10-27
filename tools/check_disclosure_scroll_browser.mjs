/* Real Chromium regression for native disclosure anchoring. Synthetic DOM only;
 * no owner workspace, stored data, credentials, provider or search traffic. */
import assert from 'node:assert/strict';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
const root=process.cwd(),out=resolve(root,'work/disclosure-scroll-browser');await mkdir(out,{recursive:true});
let playwright;try{playwright=await import(process.env.PLAYWRIGHT_MODULE||'playwright');}catch(error){if(process.env.PLAYWRIGHT_MODULE)throw error;playwright=await import('file:///C:/Users/Arya/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs');}
const source=await readFile(join(root,'src/sixd/web/disclosure-scroll.js'),'utf8');
const browser=await playwright.chromium.launch({channel:process.env.SIXD_BROWSER_CHANNEL||'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1100,height:800}}),checks=[],errors=[],external=[],measurements={};
page.on('pageerror',error=>errors.push(error.message));await page.route('**/*',route=>{external.push(route.request().url());return route.abort();});
const css=`body{margin:0;font:16px/1.6 Arial;color:#1d1d1f}main{padding:20px}.before{height:1000px;overflow-anchor:none}summary{padding:14px;border:1px solid #ddd;overflow-anchor:none}details{overflow-anchor:none}.content{height:1000px;overflow-anchor:none}.after{height:1500px}.anchor{overflow-anchor:auto}button,input{font:inherit}.dialog{position:fixed;left:50px;top:60px;width:850px;height:600px;border:1px solid #aaa;background:white;padding:20px}.scroll{height:400px;overflow:auto}.dialog .before{height:850px}.dialog .after{height:1500px}`;
const body=`<div class="before">Other project content</div><details id="graph"><summary id="summary">View graph and explanation</summary><div class="content"><p id="first">First line of the explanation</p><input id="draft" value="Unsaved source note"><p>Read the rest by scrolling down.</p></div></details><div class="after"><p class="anchor">Content below the disclosure is the native scroll anchor.</p></div>`;
async function load({guard=true,nested=false}={}){
 await page.setContent('<!doctype html><html><head><style>'+css+'</style></head><body><main id="fixture">'+(nested?'<div class="dialog"><h1>Saved conversation</h1><div class="scroll" id="scroller">'+body+'</div></div>':body)+'</main></body></html>');
 if(guard){await page.addScriptTag({content:source});await page.evaluate(()=>{window.cleanup=SixDDisclosureScroll.install(document.querySelector('#fixture'));});}
 await page.evaluate(isNested=>{if(isNested)document.querySelector('#scroller').scrollTop=730;else scrollTo({top:880,behavior:'instant'});},nested);
 await page.waitForTimeout(80);
}
const pos=()=>page.locator('#summary').evaluate(node=>({top:node.getBoundingClientRect().top,page:scrollY,nested:document.querySelector('#scroller')?.scrollTop??null}));
const settle=()=>page.waitForTimeout(100);
function pass(name){checks.push(name);console.log('PASS '+name);}
try{
 await load({guard:false});const before=await pos();await page.locator('#summary').click();await settle();const broken=await pos();assert.ok(before.top-broken.top>900,'Control fixture must reproduce a native anchor jump without manual scroll scripting.');measurements.native_without_guard={before,after:broken};
 await load();const stableBefore=await pos();await page.locator('#summary').click();await settle();const stableAfter=await pos();assert.ok(Math.abs(stableAfter.top-stableBefore.top)<1);assert.equal(await page.locator('#graph').evaluate(n=>n.open),true);assert.ok((await page.locator('#first').boundingBox()).y>stableAfter.top);measurements.page_with_guard={before:stableBefore,after:stableAfter};
 pass('Native Chromium anchor regression reproduces a jump over 900px without the guard; explicit expansion keeps the summary within 1px and content unfolds below it');

 await page.locator('#draft').fill('Keep this unsaved source note');await page.evaluate(()=>window.draftNode=document.querySelector('#draft'));
 const closing=await pos();await page.locator('#summary').click();await settle();assert.ok(Math.abs((await pos()).top-closing.top)<1);await page.locator('#summary').click();await settle();assert.equal(await page.locator('#draft').inputValue(),'Keep this unsaved source note');assert.equal(await page.evaluate(()=>window.draftNode===document.querySelector('#draft')),true);
 pass('Collapse and reopen preserve the reading position, exact draft value and mounted input identity without DOM replacement');

 await load({nested:true});const nestedBefore=await pos();await page.locator('#summary').click();await settle();const nestedAfter=await pos();assert.ok(Math.abs(nestedAfter.top-nestedBefore.top)<1);assert.equal(nestedAfter.page,nestedBefore.page);assert.equal(nestedAfter.nested,nestedBefore.nested);measurements.nested_with_guard={before:nestedBefore,after:nestedAfter};
 pass('A fixed centered-dialog scroll area expands downward without moving its summary or the background document');

 await load();await page.emulateMedia({reducedMotion:'reduce'});await page.locator('#summary').focus();const keyboardBefore=await pos();await page.locator('#summary').press('Enter');await settle();assert.equal(await page.locator('#graph').evaluate(n=>n.open),true);assert.ok(Math.abs((await pos()).top-keyboardBefore.top)<1);assert.equal(await page.evaluate(()=>document.activeElement?.id),'summary');await page.locator('#summary').press('Space');await settle();assert.equal(await page.locator('#graph').evaluate(n=>n.open),false);assert.ok(Math.abs((await pos()).top-keyboardBefore.top)<1);await page.emulateMedia({reducedMotion:'no-preference'});
 pass('Native Enter and Space disclosure activation retain focus and position, including reduced-motion mode');

 await load();await page.evaluate(()=>{document.documentElement.style.setProperty('overflow-anchor','auto','important');document.documentElement.style.setProperty('scroll-behavior','smooth','important');});await page.locator('#summary').click();await settle();assert.deepEqual(await page.evaluate(()=>['overflow-anchor','scroll-behavior'].map(k=>[document.documentElement.style.getPropertyValue(k),document.documentElement.style.getPropertyPriority(k)])),[['auto','important'],['smooth','important']]);
 await page.evaluate(()=>{document.querySelector('#summary').addEventListener('click',e=>e.preventDefault(),{once:true});});const open=await page.locator('#graph').evaluate(n=>n.open);await page.locator('#summary').click();await page.waitForTimeout(220);assert.equal(await page.locator('#graph').evaluate(n=>n.open),open);assert.equal(await page.evaluate(()=>document.documentElement.style.getPropertyValue('overflow-anchor')),'auto');
 pass('Temporary anchoring/smooth-scroll suppression restores original inline values and priorities, including a prevented native toggle');

 await load();await page.evaluate(()=>{document.querySelector('#summary').click();document.dispatchEvent(new WheelEvent('wheel',{bubbles:true}));scrollTo({top:420,behavior:'instant'});});await settle();assert.equal(await page.evaluate(()=>scrollY),420);assert.equal(await page.evaluate(()=>document.documentElement.style.getPropertyValue('overflow-anchor')),'');
 await page.evaluate(()=>{const first=SixDDisclosureScroll.install(document.querySelector('#fixture'));const second=SixDDisclosureScroll.install(document.querySelector('#fixture'));window.sameController=first===second;first();});assert.equal(await page.evaluate(()=>window.sameController),true);
 await load();await page.evaluate(()=>{window.cleanup();document.querySelector('#summary').insertAdjacentHTML('beforeend',' <a id="jump" href="#destination">Go elsewhere</a>');document.querySelector('#fixture').insertAdjacentHTML('beforeend','<h2 id="destination">Explicit navigation target</h2>');SixDDisclosureScroll.install(document.querySelector('#fixture'));});await page.locator('#jump').click();await settle();assert.equal(await page.locator('#graph').evaluate(n=>n.open),false);assert.ok(await page.evaluate(()=>scrollY>1500));
 pass('User scrolling interrupts preservation immediately; installation is idempotent and explicit navigation inside a summary is not intercepted');

 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
 await writeFile(join(out,'results.json'),JSON.stringify({schema:'sixd.disclosure-scroll-browser.v1',checks,measurements,browser_errors:errors,external_requests:external.length,synthetic_fixture:true,paid_calls:0},null,2)+'\n');
 console.log(JSON.stringify({passed:checks.length,measurements,browser_errors:errors,external_requests:external.length,paid_calls:0},null,2));
}catch(error){await page.screenshot({path:join(out,'failure.png'),fullPage:true}).catch(()=>{});console.error(error.stack||error);process.exitCode=1;}
finally{await browser.close();}
