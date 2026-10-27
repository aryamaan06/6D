/* Real DOM placement checks; isolated local fixtures, no projects or providers. */
import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';

let browser,server,origin;
const assets=new Map();
const html=`<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><style>
:root{--sd-bg:#fff;--sd-ink:#202124;--sd-soft:#555;--sd-side:#f5f5f5;--sd-border:#ddd;--sd-font-sans:Arial,sans-serif}body{margin:0;font-family:Arial}#sixd-workspace{min-height:100vh}.sd-top{height:64px;border-bottom:1px solid #ddd}#fixture-content{min-height:500px}button,input,select{font:16px Arial;padding:10px}#other-dialog{padding:24px}
</style><link rel="stylesheet" href="/rocket-assistant.css"><div id="sixd-workspace"><header class="sd-top"><button id="home">Projects</button><button id="settings">Settings</button></header><main id="fixture-content" class="sd-main"><button id="ordinary" style="position:fixed;left:258px;bottom:40px;width:160px;height:160px">Save project</button></main><dialog id="other-dialog"><h2>Project editor</h2><input aria-label="Draft" value="keep draft"><button onclick="this.closest('dialog').close()">Close editor</button></dialog></div><script src="/overlay-dismiss.js"></script><script src="/rocket-renderer.js"></script><script src="/rocket-assistant.js"></script><script>window.opens=0;window.rocket=SixDRocketAssistant.mount({onOpen(){opens++}});</script>`;

before(async()=>{
  for(const name of ['rocket-assistant.js','rocket-assistant.css','rocket-renderer.js','overlay-dismiss.js'])assets.set('/'+name,await readFile(fileURLToPath(new URL('../src/sixd/web/'+name,import.meta.url))));
  server=createServer((request,response)=>{const asset=assets.get(request.url);response.setHeader('Content-Type',asset?(request.url.endsWith('.css')?'text/css':'text/javascript'):'text/html');response.end(asset||html);});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));origin='http://127.0.0.1:'+server.address().port;
  let playwright;try{playwright=await import(process.env.PLAYWRIGHT_MODULE||'playwright');}catch(error){if(process.env.PLAYWRIGHT_MODULE)throw error;playwright=await import('file:///C:/Users/Arya/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs');}
  browser=await playwright.chromium.launch({channel:process.env.SIXD_BROWSER_CHANNEL||'chrome',headless:true});
});
after(async()=>{await browser?.close();await new Promise(resolve=>server?.close(resolve));});
async function fixture(options={}){
  const page=await browser.newPage({viewport:{width:1200,height:800},...options});
  await page.addInitScript(()=>{
    window.placementWrites=0;
    const setItem=Storage.prototype.setItem;
    Storage.prototype.setItem=function(key,value){if(key==='sixd.rocket.placement.v2')window.placementWrites++;return setItem.call(this,key,value);};
  });
  await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  await page.goto(origin);await settled(page);return page;
}
async function settled(page){await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));}
async function clear(page){
  const result=await page.evaluate(()=>{
    const companion=document.querySelector('.sd-rocket-companion'),box=companion.getBoundingClientRect();
    const overlaps=[...document.querySelectorAll('#fixture-content button,.sd-top button')].filter(node=>{
      if(!node.getClientRects().length||getComputedStyle(node).visibility==='hidden')return false;
      const r=node.getBoundingClientRect();return r.width&&r.height&&r.right>0&&r.bottom>0&&r.left<innerWidth&&r.top<innerHeight&&box.left<r.right&&box.right>r.left&&box.top<r.bottom&&box.bottom>r.top;
    }).map(node=>node.id);
    const visibleParts=[...companion.querySelectorAll('button,canvas,.sd-rocket-fallback')].filter(node=>node.getClientRects().length&&getComputedStyle(node).visibility!=='hidden').map(node=>{
      const rect=node.getBoundingClientRect();return{id:node.id||node.className,left:rect.left,right:rect.right,top:rect.top,bottom:rect.bottom};
    });
    return {overlaps,visibleParts,box:{x:box.x,y:box.y,width:box.width,height:box.height,right:box.right,bottom:box.bottom},mode:companion.dataset.mode,inline:companion.classList.contains('sd-rocket-inline')};
  });
  assert.deepEqual(result.overlaps,[]);assert.ok(result.box.x>=0&&result.box.right<=await page.evaluate(()=>innerWidth));
  if(!result.inline)assert.ok(result.box.y>=0&&result.box.bottom<=await page.evaluate(()=>innerHeight));
  const viewport=await page.evaluate(()=>({width:innerWidth,height:innerHeight}));
  for(const part of result.visibleParts){assert.ok(part.left>=-.25&&part.right<=viewport.width+.25,JSON.stringify(part));if(!result.inline)assert.ok(part.top>=-.25&&part.bottom<=viewport.height+.25,JSON.stringify(part));}
  return result;
}

test('default and old normalized positions park clear of controls while retaining the 3D renderer',async()=>{
  const page=await fixture();
  try{
    assert.equal((await clear(page)).mode,'full');
    assert.ok(['webgl','fallback'].includes(await page.locator('#sd-rocket-canvas').getAttribute('data-renderer')));
    assert.equal(await page.locator('#sd-rocket-canvas').count(),1);
    await page.evaluate(()=>{localStorage.removeItem('sixd.rocket.placement.v2');localStorage.setItem('sixd.rocket.position.v1',JSON.stringify({x:.24,y:.96}));});
    await page.reload();await settled(page);await clear(page);
    const saved=await page.evaluate(()=>({old:JSON.parse(localStorage.getItem('sixd.rocket.position.v1')),next:JSON.parse(localStorage.getItem('sixd.rocket.placement.v2'))}));
    assert.deepEqual(saved.old,{x:.24,y:.96});assert.deepEqual(saved.next.position,saved.old);assert.equal(saved.next.version,2);
    assert.equal(await page.evaluate(()=>opens),0);
  }finally{await page.close();}
});

test('body drag stays free and clamped, parks clear on release and never opens Ask 6D',async()=>{
  const page=await fixture();
  try{
    let box=await page.locator('#sd-rocket-launcher').boundingBox();
    await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(110,110,{steps:8});
    await page.mouse.move(-200,-200,{steps:4});await settled(page);
    let state=await page.locator('.sd-rocket-companion').boundingBox();assert.ok(state.x>=8&&state.y>=8);
    await page.mouse.move(320,640,{steps:8});await page.mouse.up();await settled(page);
    await clear(page);assert.equal(await page.evaluate(()=>opens),0);assert.equal(await page.locator('#sd-rocket-dialog').evaluate(node=>node.open),false);
    assert.equal(await page.locator('#sd-rocket-launcher').getAttribute('data-suppress-click'),'true');
    box=await page.locator('#sd-rocket-launcher').boundingBox();await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(2000,2000,{steps:8});await page.mouse.up();await settled(page);await clear(page);
    assert.equal(await page.evaluate(()=>opens),0);
    await page.locator('#sd-rocket-launcher').focus();await page.keyboard.press('Enter');assert.equal(await page.evaluate(()=>opens),1);
  }finally{await page.close();}
});

test('new controls, viewport changes and explicit render refresh park clear of controls',async()=>{
  const page=await fixture();
  try{
    await page.evaluate(()=>{const box=document.querySelector('.sd-rocket-companion').getBoundingClientRect(),button=document.createElement('button');button.id='late-control';button.textContent='Calculate';button.style.cssText=`position:fixed;left:${box.x}px;top:${box.y}px;width:${box.width}px;height:${box.height}px`;document.querySelector('#fixture-content').append(button);});
    await settled(page);await clear(page);
    await page.evaluate(()=>{const button=document.querySelector('#late-control');button.style.position='absolute';document.querySelector('#fixture-content').style.minHeight='2000px';SixDRocketAssistant.refreshPlacement();});
    await settled(page);await clear(page);
    await page.setViewportSize({width:390,height:640});await settled(page);await clear(page);
    await page.evaluate(()=>{document.querySelector('#late-control').remove();SixDRocketAssistant.refreshPlacement();});await settled(page);await clear(page);
    assert.equal(await page.evaluate(()=>opens),0);
  }finally{await page.close();}
});

test('sustained nested scrolling keeps the rocket stable, retains its renderer and makes no preference writes',async()=>{
  const page=await fixture();
  try{
    await page.evaluate(()=>{
      document.querySelector('#ordinary').remove();
      const scroller=document.createElement('div');scroller.id='scrolling-editor';scroller.style.cssText='position:fixed;left:8px;right:8px;top:80px;bottom:8px;overflow:auto';
      scroller.innerHTML='<div style="height:5000px;position:relative"><button id="scrolling-control" style="position:absolute;left:0;top:1500px;width:100%;height:100px">Moving page control</button></div>';
      document.querySelector('#fixture-content').append(scroller);
      const indicator=document.createElement('span');indicator.id='scroll-indicator';document.querySelector('#fixture-content').append(indicator);
      scroller.addEventListener('scroll',()=>{indicator.classList.toggle('sticky-active',Math.floor(scroller.scrollTop/100)%2===0);});
      SixDRocketAssistant.refreshPlacement();
    });
    await settled(page);await clear(page);
    const before=await page.evaluate(()=>{
      window.originalRocketCanvas=document.querySelector('#sd-rocket-canvas');
      const rect=document.querySelector('.sd-rocket-companion').getBoundingClientRect(),scroller=document.querySelector('#scrolling-editor');
      return{x:rect.x,y:rect.y,width:rect.width,height:rect.height,mode:document.querySelector('.sd-rocket-companion').dataset.mode,writes:placementWrites,preference:localStorage.getItem('sixd.rocket.placement.v2'),stop:1500+scroller.getBoundingClientRect().top-rect.y+10};
    });
    for(let step=1;step<=24;step++){
      await page.evaluate(top=>document.querySelector('#scrolling-editor').scrollTop=top,before.stop*step/24);await settled(page);
      const during=await page.evaluate(()=>{const rect=document.querySelector('.sd-rocket-companion').getBoundingClientRect();return{x:rect.x,y:rect.y,width:rect.width,height:rect.height,mode:document.querySelector('.sd-rocket-companion').dataset.mode,sameCanvas:originalRocketCanvas===document.querySelector('#sd-rocket-canvas'),writes:placementWrites,preference:localStorage.getItem('sixd.rocket.placement.v2')};});
      assert.deepEqual(during,{x:before.x,y:before.y,width:before.width,height:before.height,mode:before.mode,sameCanvas:true,writes:before.writes,preference:before.preference});
    }
    await page.waitForTimeout(300);await settled(page);
    const after=await page.locator('.sd-rocket-companion').boundingBox();assert.deepEqual({x:after.x,y:after.y,width:after.width,height:after.height},{x:before.x,y:before.y,width:before.width,height:before.height});
    assert.equal(await page.evaluate(()=>placementWrites),before.writes);assert.equal(await page.evaluate(()=>opens),0);
    // Scrolling content may pass beneath the fixed companion. An explicit dock/
    // render refresh still finds a safe position without changing the preference.
    await page.evaluate(()=>SixDRocketAssistant.refreshPlacement());await settled(page);await clear(page);
  }finally{await page.close();}
});

test('compact/full, help, docking, reset and keyboard motion are explicit accessible controls',async()=>{
  const page=await fixture();
  try{
    await page.getByRole('button',{name:'Minimize rocket',exact:true}).click();await settled(page);assert.equal((await clear(page)).mode,'compact');
    await page.reload();await settled(page);assert.equal((await clear(page)).mode,'compact');
    await page.getByRole('button',{name:'Show full rocket',exact:true}).click();await settled(page);assert.equal((await clear(page)).mode,'full');
    await page.getByRole('button',{name:'Rocket options and movement help'}).click();
    assert.equal(await page.locator('#sd-rocket-controls').evaluate(node=>node.open),true);assert.match(await page.locator('#sd-rocket-controls').innerText(),/Alt.*arrow key/s);
    assert.equal(await page.locator('.sd-rocket-companion').evaluate(node=>getComputedStyle(node).visibility),'hidden');
    await page.keyboard.press('Escape');await settled(page);await clear(page);
    await page.getByRole('button',{name:'Rocket options and movement help'}).click();let box=await page.locator('#sd-rocket-controls').boundingBox();await page.mouse.click(box.x-10,box.y);await settled(page);assert.equal(await page.locator('#sd-rocket-controls').evaluate(node=>node.open),false);
    await page.getByRole('button',{name:'Rocket options and movement help'}).click();await page.getByRole('button',{name:'Dock safely',exact:true}).click();await settled(page);const docked=await clear(page);
    assert.ok(Math.min(docked.box.x-8,docked.box.y-8,1200-docked.box.right-8,800-docked.box.bottom-8)<1);
    await page.locator('#sd-rocket-launcher').focus();await page.keyboard.press('Alt+ArrowRight');await settled(page);await clear(page);
    await page.keyboard.press('Alt+Shift+ArrowUp');await settled(page);await clear(page);
    await page.keyboard.press('Alt+Home');await settled(page);await clear(page);assert.equal(await page.evaluate(()=>opens),0);
  }finally{await page.close();}
});

test('a narrow clear strip compacts automatically and restores the full rocket when space returns',async()=>{
  const page=await fixture({viewport:{width:390,height:640}});
  try{
    await page.evaluate(()=>{document.querySelector('#ordinary').remove();const button=document.createElement('button');button.id='dense-control';button.textContent='Dense editor';button.style.cssText='position:fixed;left:0;top:65px;width:100vw;height:505px';document.querySelector('#fixture-content').append(button);});
    await settled(page);const state=await clear(page);assert.equal(state.mode,'compact');assert.equal(state.inline,false);
    assert.equal(await page.getByRole('button',{name:'Show full rocket',exact:true}).isVisible(),true);
    await page.evaluate(()=>document.querySelector('#dense-control').remove());await settled(page);assert.equal((await clear(page)).mode,'full');
  }finally{await page.close();}
});

test('screens with no clear compact slot use normal-flow access near the header',async()=>{
  const page=await fixture({viewport:{width:390,height:640}});
  try{
    await page.evaluate(()=>{document.querySelector('#ordinary').remove();document.querySelector('#settings').style.width='250px';for(let index=0;index<6;index++){const button=document.createElement('button');button.className='dense-control';button.textContent='Editor action '+index;button.style.cssText='display:block;width:100%;height:96px';document.querySelector('#fixture-content').append(button);}});
    await settled(page);
    const state=await page.locator('.sd-rocket-companion').evaluate(node=>({inline:node.classList.contains('sd-rocket-inline'),mode:node.dataset.mode,previous:node.previousElementSibling.className,position:getComputedStyle(node).position}));
    assert.deepEqual(state,{inline:true,mode:'compact',previous:'sd-top',position:'relative'});
    await clear(page);
    await page.evaluate(()=>document.querySelectorAll('.dense-control').forEach(node=>node.remove()));await settled(page);assert.equal((await clear(page)).mode,'full');
  }finally{await page.close();}
});

test('dialogs hide the whole companion, preserve drafts and restore placement; reduced motion remains native',async()=>{
  const page=await fixture();
  try{
    await page.evaluate(()=>document.querySelector('#other-dialog').showModal());await settled(page);
    assert.equal(await page.locator('.sd-rocket-companion').evaluate(node=>getComputedStyle(node).visibility),'hidden');
    assert.equal(await page.locator('#other-dialog input').inputValue(),'keep draft');
    await page.keyboard.press('Escape');await settled(page);assert.equal(await page.locator('.sd-rocket-companion').evaluate(node=>getComputedStyle(node).visibility),'visible');await clear(page);
    await page.emulateMedia({reducedMotion:'reduce'});await settled(page);
    assert.ok(['reduced','paused'].includes(await page.locator('#sd-rocket-canvas').getAttribute('data-motion')));
    assert.equal(await page.locator('.sd-rocket-art').evaluate(node=>getComputedStyle(node).animationName),'none');
    await page.locator('#sd-rocket-launcher').click();assert.equal(await page.locator('#sd-rocket-dialog').evaluate(node=>node.open),true);assert.equal(await page.locator('#other-dialog input').inputValue(),'keep draft');
  }finally{await page.close();}
});
