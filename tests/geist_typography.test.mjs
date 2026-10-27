/* Genuine local font loading, not a computed fallback-stack assertion. */
import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';

const web=fileURLToPath(new URL('../src/sixd/web/',import.meta.url));
const html=`<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
body{margin:24px}.legacy-copy{font:14.5px Georgia,serif}button,input,select{font:14px Times,serif}#sixd-workspace h1{font-size:30px}.sd-finding-value{font-size:24px}.sd-receipt{font-size:13px}
</style><link rel="stylesheet" href="/typography.css"><div id="sixd-workspace"><h1 style="font-weight:620">Rocket design review</h1><h2 style="font-weight:500">Understand the saved result</h2><h3 style="font-weight:400">Evidence and limits</h3><p class="legacy-copy">A readable explanation of the saved requirement.</p><button>Open engineering</button><input aria-label="Project name" value="Arya rocket walkthrough"><select aria-label="Model"><option>Nemotron 3 Super</option></select><textarea aria-label="Question">Explain aerospace in simple words.</textarea><p class="sd-receipt">R3 · original-ID-001</p><strong class="sd-finding-value">6126.145572278846 m</strong><pre><code><span>unit = m/s^2</span></code></pre><em>Model assumptions remain explicit.</em><svg class="sd-chart" width="300" height="30"><text x="0" y="20">5000 m</text></svg></div></html>`;
let server,browser,origin,manifest;
const requests=[];
before(async()=>{
 manifest=JSON.parse(await readFile(web+'fonts/provenance.json','utf8'));
 const files=new Map([['/typography.css',await readFile(web+'typography.css')]]);
 for(const item of manifest.files)files.set('/fonts/'+item.file,await readFile(web+'fonts/'+item.file));
 server=createServer((request,response)=>{requests.push(request.url);const file=files.get(request.url);if(file){response.setHeader('Content-Type',request.url.endsWith('.woff2')?'font/woff2':request.url.endsWith('.css')?'text/css':'text/plain');response.end(file);}else if(request.url==='/'){response.setHeader('Content-Type','text/html');response.end(html);}else{response.statusCode=404;response.end();}});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));origin='http://127.0.0.1:'+server.address().port;
 let pw;try{pw=await import(process.env.PLAYWRIGHT_MODULE||'playwright');}catch(error){if(process.env.PLAYWRIGHT_MODULE)throw error;pw=await import('file:///C:/Users/Arya/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs');}
 browser=await pw.chromium.launch({channel:process.env.SIXD_BROWSER_CHANNEL||'chrome',headless:true});
});
after(async()=>{await browser?.close();await new Promise(resolve=>server?.close(resolve));});

test('bundled font bytes match the pinned official release manifest and retain the OFL notice',async()=>{
 assert.equal(manifest.release,'v1.8.2');assert.equal(manifest.modified,false);assert.equal(manifest.license,'SIL Open Font License 1.1');assert.equal(manifest.files.length,5);
 for(const item of manifest.files){const data=await readFile(web+'fonts/'+item.file);assert.equal(data.length,item.bytes);assert.equal(createHash('sha256').update(data).digest('hex'),item.sha256);if(item.file.endsWith('.woff2'))assert.equal(data.subarray(0,4).toString(),'wOF2');}
 assert.match(await readFile(web+'fonts/OFL-Geist.txt','utf8'),/Copyright 2024 The Geist Project Authors/);
});

test('Chromium decodes all four local Geist faces with no third-party font request',async()=>{
 const page=await browser.newPage();const external=[],errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',route=>{if(new URL(route.request().url()).origin!==origin){external.push(route.request().url());return route.abort();}return route.continue();});
 try{
  await page.goto(origin);
  const loaded=await page.evaluate(async()=>{for(const spec of ['400 16px "Geist Sans"','650 22px "Geist Sans"','italic 400 16px "Geist Sans"','400 16px "Geist Mono"','italic 400 16px "Geist Mono"'])await document.fonts.load(spec);await document.fonts.ready;return [...document.fonts].map(face=>({family:face.family,style:face.style,weight:face.weight,status:face.status}));});
  assert.equal(loaded.length,4);for(const face of loaded){assert.equal(face.status,'loaded');assert.equal(face.weight,'100 900');assert.ok(['Geist Sans','Geist Mono'].some(name=>face.family.replaceAll('"','')===name));}
  for(const file of manifest.files.filter(item=>item.file.endsWith('.woff2')))assert.ok(requests.includes('/fonts/'+file.file),file.file);
  const widths=await page.evaluate(()=>{const context=document.createElement('canvas').getContext('2d'),text='Rocket engineering evidence 6126';context.font='16px "Geist Sans"';const sans=context.measureText(text).width;context.font='16px Arial';const fallback=context.measureText(text).width;context.font='16px "Geist Mono"';const monoI=context.measureText('iiii').width,monoW=context.measureText('WWWW').width;return {sans,fallback,monoI,monoW};});
  assert.ok(Math.abs(widths.sans-widths.fallback)>.1,'Genuine Geist metrics differ from the fallback font.');assert.equal(widths.monoI,widths.monoW);
  assert.deepEqual(external,[]);assert.deepEqual(errors,[]);
 }finally{await page.close();}
});

test('legacy prose, native controls and headings use Sans while technical text retains Mono and exact values',async()=>{
 const page=await browser.newPage();try{
  await page.goto(origin);await page.evaluate(()=>document.fonts.ready);
  const styles=await page.evaluate(()=>{const style=selector=>{const n=document.querySelector(selector),c=getComputedStyle(n);return {font:c.fontFamily,size:parseFloat(c.fontSize),weight:c.fontWeight,text:n.value??n.textContent};};return {body:style('#sixd-workspace'),title:style('h1'),heading:style('h2'),smallHeading:style('h3'),ui:['.legacy-copy','button','input','select','option','textarea','em'].map(style),technical:['.sd-receipt','.sd-finding-value','code span','.sd-chart text'].map(style)};});
  assert.ok(styles.body.size>=14.5);assert.equal(styles.title.weight,'700');assert.equal(styles.heading.weight,'650');assert.equal(styles.smallHeading.weight,'600');
  for(const row of styles.ui)assert.match(row.font,/^"?Geist Sans"?,/);for(const row of styles.technical)assert.match(row.font,/^"?Geist Mono"?,/);
  assert.equal(styles.technical[1].text,'6126.145572278846 m');assert.equal(styles.technical[2].text,'unit = m/s^2');assert.equal(styles.ui[2].text,'Arya rocket walkthrough');
 }finally{await page.close();}
});
