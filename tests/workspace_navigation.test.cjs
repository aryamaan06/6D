/* Isolated browser-history contract checks. No HTTP server or provider is used. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../src/sixd/web/workspace-navigation.js'),'utf8');
function browser(hash='') {
  const listeners=new Map(),entries=[{hash,state:null}];let position=0;
  const window={location:{hash},addEventListener(name,fn){if(!listeners.has(name))listeners.set(name,new Set());listeners.get(name).add(fn);},
    removeEventListener(name,fn){listeners.get(name)?.delete(fn);}};
  function emit(name){for(const listener of [...listeners.get(name)||[]])listener({type:name});}
  window.history={get state(){return entries[position].state;},
    pushState(state,_title,hash){entries.splice(position+1);entries.push({hash,state});position++;window.location.hash=hash;},
    replaceState(state,_title,hash){entries[position]={hash,state};window.location.hash=hash;},
    go(delta){const next=position+delta;if(next<0||next>=entries.length)return;queueMicrotask(()=>{position=next;window.location.hash=entries[position].hash;emit('popstate');emit('hashchange');});},
    back(){this.go(-1);},forward(){this.go(1);}};
  vm.runInNewContext(source,{window,URLSearchParams,queueMicrotask,Set,Number,Error,encodeURIComponent,decodeURIComponent});
  return {window,api:window.SixDNavigation,entries,get position(){return position;},manual(hash){window.history.pushState(null,'',hash);emit('hashchange');}};
}
const route=(page='review-home',id='rocket',revision=1)=>({projectId:id,revision,page,system:'overview',view:'canvas',panel:'details'});
const plain=x=>JSON.parse(JSON.stringify(x));
async function tick(){await new Promise(resolve=>setImmediate(resolve));}
test('locations round-trip item IDs, saved revision, scope and trajectory without engineering values',()=>{
  const b=browser(),r={...route('simulation','rocket / Δ',3),selected:{kind:'requirement',id:'altitude & margin'},view:'reader',panel:'assistant',aiScope:'project',trajectory:{modelId:'flight',runId:'receipt-123'}};
  assert.deepEqual(plain(b.api.parse(b.api.format(r))),r);
  assert.equal(b.api.format({page:'projects'}),'#/projects');
  assert.equal(b.api.parse(''),null);
  assert.equal(b.api.format({...r,question:'private prompt',draft:{thrust:20000}}).includes('private'),false);
});
test('malformed locations and unsupported or repeated options are rejected',()=>{
  const b=browser();
  for(const bad of ['#external','#/projects/a/r/0/system','#/projects/a/r/1/unknown','#/projects/a/r/1/system?view=table&view=reader','#/projects/a/r/1/system?key=secret','#/projects/a/r/1/system?kind=input','#/projects/%ZZ/r/1/system','#/projects/a/r/1/system?panel=credentials'])assert.throws(()=>b.api.parse(bad),undefined,bad);
});
test('the routed workspace owns page scroll while mounted and restores the browser policy on disposal',()=>{
  const b=browser();let current=route();b.window.history.scrollRestoration='auto';
  const c=b.api.create({read:()=>current,apply:async r=>{current=r;return true;}});
  c.start();assert.equal(b.window.history.scrollRestoration,'manual');
  c.dispose();assert.equal(b.window.history.scrollRestoration,'auto');
});
test('render syncing deduplicates entries and browser Back/Forward restores item context once',async()=>{
  const b=browser();let current=route(),applies=0;
  const c=b.api.create({read:()=>current,apply:async r=>{applies++;current=r;return true;}});c.start();c.sync();c.sync();
  current={...route('system'),system:'propulsion',view:'table',selected:{kind:'input',id:'thrust'}};c.sync();
  current=route('report');c.sync();assert.equal(b.entries.length,3);
  c.back();await tick();await c.settled;assert.equal(current.page,'system');assert.equal(current.selected.id,'thrust');assert.equal(applies,1);assert.equal(c.canForward,true);
  c.forward();await tick();await c.settled;assert.equal(current.page,'report');assert.equal(applies,2);c.dispose();
});
test('declining a route change restores the previous history entry without discarding draft state',async()=>{
  const b=browser();let current=route(),prompts=0;const draft={thrust:11000};
  const c=b.api.create({read:()=>current,apply:async()=>{prompts++;return false;}});c.start();current=route('changes','rocket',2);c.sync();
  c.back();await tick();await c.settled;assert.equal(b.position,1);assert.equal(b.window.location.hash,b.api.format(current));assert.equal(prompts,1);assert.equal(draft.thrust,11000);c.dispose();
});
test('an invalid manually edited hash recovers the last valid location and reports an error',async()=>{
  const b=browser();let current=route(),errors=0,applies=0;
  const c=b.api.create({read:()=>current,apply:async r=>{applies++;current=r;},onError:()=>errors++});c.start();
  b.manual('#/projects/rocket/r/1/system?key=private');await tick();await c.settled;
  assert.equal(errors,1);assert.equal(applies,0);assert.equal(b.window.location.hash,b.api.format(current));c.dispose();
});
test('rapid traversals converge on the latest requested location while render sync is suppressed',async()=>{
  const b=browser();let current=route(),release;
  const c=b.api.create({read:()=>current,apply:async r=>{await new Promise(resolve=>{release=resolve;});current=r;c.sync();return true;}});c.start();
  current=route('coverage');c.sync();current=route('report');c.sync();
  c.back();await tick();assert.equal(c.applying,true);c.back();await tick();release();await tick();release();await tick();await c.settled;
  assert.equal(current.page,'review-home');assert.equal(b.window.location.hash,b.api.format(current));assert.equal(b.entries.length,3);c.dispose();
});
