import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const settle=()=>new Promise(resolve=>setImmediate(resolve));
const clone=value=>JSON.parse(JSON.stringify(value));
const exactTarget='finding:payload&thermal:exact';
const source={title:'Thermal reference',url:'https://example.org/thermal',excerpt:'Exact passage: T < 300 K.\nDo not round or rewrite.',details:'Section 3 · preserved quotation'};
const baseProfile=()=>({project_id:'project-exact',revision:3,run_id:'saved-run-exact',context:'saved',digest:'library-before',sources:[],links:[],targets:[{target_id:exactTarget,kind:'finding',id:'payload&thermal:exact',label:'Payload maximum temperature · saved finding'}],limitations:[]});

// Exercise the real event handlers without a browser or any connected provider.
function host(){
  const listeners=new Map(),nodes=new Map();
  const node=selector=>{
    if(!nodes.has(selector))nodes.set(selector,{value:'',disabled:false,hidden:false,textContent:'',focus(){},scrollIntoView(){}});
    return nodes.get(selector);
  };
  return {isConnected:true,innerHTML:'',node,querySelector:node,querySelectorAll:()=>[],contains:()=>true,
    addEventListener:(type,handler)=>listeners.set(type,handler),removeEventListener:type=>listeners.delete(type),
    field(family,key,value){listeners.get('input')?.({target:{dataset:{[family]:key},value,hasAttribute:()=>false}});},
    click(family,action,extra={}){
      const control=Object.assign(node('[data-'+(family==='slAction'?'sl':'sr')+'-action="'+action+'"]'),{dataset:{[family]:action,...extra}});
      listeners.get('click')?.({target:{closest:()=>control}});
    },
  };
}
function runtime(file){
  const context={window:{SixDSourceTargets:{render:()=>'<div class="target-picker"></div>',update(){}}},URL,AbortController};
  vm.runInNewContext(readFileSync(new URL('../src/sixd/web/'+file,import.meta.url),'utf8'),context);
  return context.window;
}
function libraryFixture({profile=baseProfile(),...overrides}={}){
  const view=host(),calls=[],asked=[],window=runtime('source-library.js');
  const ctx={projectId:profile.project_id,revision:profile.revision,runId:profile.run_id,canEdit:true,
    api:async(path,body)=>{
      calls.push({path,body:body&&clone(body)});
      if(path==='/api/sources'){
        const item={...body.source,source_id:body.source.source_id||'new-source-exact',version:(body.source.base_version||0)+1};
        profile.sources=profile.sources.filter(row=>row.source_id!==item.source_id).concat(item);profile.digest='library-after-save';
      }else if(path==='/api/source-links'){
        const saved=profile.sources.find(item=>item.source_id===body.spec.source_id);
        profile.links.push({link_id:'link-exact',version:1,source_id:saved.source_id,source_version:saved.version,source:clone(saved),target:clone(profile.targets[0]),status:'linked',basis_revision:3,note:body.spec.note});profile.digest='library-after-link';
      }
      return clone(profile);
    },onAskLinkedReference:async value=>{asked.push(clone(value));return true;},...overrides};
  window.SixDSources.mount(view,ctx);
  return {view,calls,asked,sources:window.SixDSources,ctx};
}

test('search preview copy, source save, link and Ask remain separate explicit actions with exact identities',async()=>{
  const f=libraryFixture(),identity={projectId:'project-exact',revision:3,runId:'saved-run-exact'};
  assert.equal(f.sources.prefillAvailability(identity).state,'loading');
  await settle();
  assert.equal(f.calls.length,1);
  assert.equal(f.sources.prefill({...source},exactTarget,identity),true);
  assert.equal(f.calls.length,1,'copying must make no mutation or provider request');
  assert.match(f.view.innerHTML,/Copied draft · not saved or linked/);
  assert.match(f.view.innerHTML,/Exact passage: T &lt; 300 K/);
  assert.equal(f.sources.prefillAvailability(identity).state,'unsaved-editor');
  assert.equal(f.sources.prefill({...source,title:'Replacement'},exactTarget,identity),false);
  assert.doesNotMatch(f.view.innerHTML,/Replacement/);

  f.view.click('slAction','save-source');await settle();
  assert.equal(f.calls.length,2);
  assert.equal(f.calls[1].path,'/api/sources');
  assert.deepEqual(f.calls[1].body.source,{source_id:null,base_version:null,...source});
  assert.match(f.view.innerHTML,/<option value="new-source-exact" selected>/,'the saved identity is selected for the manual link');
  assert.equal(f.asked.length,0);
  assert.doesNotMatch(f.view.innerHTML,/data-sl-action="ask-linked-reference"/);

  f.view.click('slAction','link-source');await settle();
  assert.equal(f.calls.length,3);
  assert.deepEqual(f.calls[2],{path:'/api/source-links',body:{project_id:'project-exact',revision:3,expected_digest:'library-after-save',spec:{source_id:'new-source-exact',source_version:1,target_id:exactTarget,note:''}}});
  assert.equal(f.asked.length,0,'linking must never open or start Ask automatically');
  assert.match(f.view.innerHTML,/Ask about this reference/);
  f.view.click('slAction','ask-linked-reference',{slId:'link-exact'});await settle();
  assert.deepEqual(f.asked,[{source_id:'new-source-exact',target_id:exactTarget}]);
  assert.equal(f.calls.length,3,'Ask handoff performs no API mutation or model request');
});

test('prefill and all mutations refuse changed, historical, project-draft and saved-run contexts',async()=>{
  for(const override of [{hasDraft:true},{canEdit:false}]){
    const f=libraryFixture(override);await settle();
    assert.equal(f.sources.prefill({...source},exactTarget),false);
    f.view.click('slAction','save-source');f.view.click('slAction','link-source');f.view.click('slAction','ask-linked-reference',{slId:'invented'});await settle();
    assert.equal(f.calls.length,1);assert.equal(f.asked.length,0);
  }
  const f=libraryFixture();await settle();
  for(const identity of [{projectId:'another-project'},{revision:2},{runId:'new-calculation'}]){
    assert.equal(f.sources.prefillAvailability(identity).state,'context-changed');
    assert.equal(f.sources.prefill({...source},exactTarget,identity),false);
  }
  assert.equal(f.calls.length,1);
  const mismatched=libraryFixture({runId:'different-mounted-run'});await settle();
  assert.equal(mismatched.sources.prefillAvailability().ready,false);
  assert.match(mismatched.view.node('[data-sl-error]').textContent,/saved calculation changed/);
});

test('reference drafts, size limits and stale links are preserved before a handoff',async()=>{
  const f=libraryFixture();await settle();
  f.view.field('slField','title','My unfinished manual source');
  assert.equal(f.sources.prefillAvailability().state,'unsaved-editor');
  assert.equal(f.sources.prefill({...source},exactTarget),false);
  const empty=libraryFixture();await settle();
  assert.equal(empty.sources.prefill({...source,excerpt:'x'.repeat(8001)},exactTarget),false);
  assert.equal(empty.sources.prefill({...source,url:'https://user:secret@example.org/'},exactTarget),false);
  assert.equal(empty.calls.length,1);
  for(const status of ['needs_review','target_unavailable']){
    const profile=baseProfile();profile.sources=[{...source,source_id:'old-source',version:2}];
    profile.links=[{link_id:'old-link',status,source_id:'old-source',source_version:1,source:{...source,version:1},target:profile.targets[0],review_reasons:['New source version exists'],basis_revision:2,version:1}];
    const stale=libraryFixture({profile});await settle();
    assert.doesNotMatch(stale.view.innerHTML,/data-sl-action="ask-linked-reference"/);
    stale.view.click('slAction','ask-linked-reference',{slId:'old-link'});await settle();
    assert.equal(stale.asked.length,0);assert.equal(stale.calls.length,1);
    assert.match(stale.view.innerHTML,/source v1/);
  }
});

test('failed or late source-library responses do not overwrite another mounted context',async()=>{
  let resolve;
  const first=libraryFixture({api:()=>new Promise(done=>{resolve=done;})});
  const second=host();first.sources.mount(second,{projectId:'other',revision:1,runId:null,api:async()=>({...baseProfile(),project_id:'other',revision:1,run_id:null})});
  await settle();const original=first.view.innerHTML;
  resolve(baseProfile());await settle();
  assert.equal(first.view.innerHTML,original);
  assert.equal(first.sources.prefill({...source},exactTarget,{projectId:'project-exact',revision:3,runId:'saved-run-exact'}),false);
});

test('a refreshed library from another saved calculation invalidates the prior profile',async()=>{
  let remote=baseProfile();const calls=[];
  const f=libraryFixture({api:async(path,body)=>{calls.push({path,body});return clone(remote);}});await settle();
  assert.equal(f.sources.prefillAvailability().ready,true);
  remote.run_id='replacement-calculation';f.view.click('slAction','refresh');await settle();
  assert.equal(f.sources.prefillAvailability().ready,false);
  assert.equal(f.sources.prefill({...source},exactTarget),false);
  f.view.click('slAction','save-source');f.view.click('slAction','link-source');await settle();
  assert.equal(calls.length,2);assert.ok(calls.every(call=>call.body===undefined));
});

test('copy refusal preserves an unfinished reference-link source, target and exact rationale',async()=>{
  const profile=baseProfile(),saved={...source,source_id:'pending-link-source',version:4};profile.sources=[saved];
  const f=libraryFixture({profile});await settle();
  const rationale='Pending rationale: T < 300 K.\nKeep the exact source version and punctuation.';
  f.view.field('slLink','source_id',saved.source_id);f.view.field('slLink','target_id',exactTarget);f.view.field('slLink','note',rationale);
  assert.equal(f.sources.prefillAvailability().state,'unsaved-link');
  assert.match(f.sources.prefillAvailability().reason,/unfinished reference link/);
  assert.equal(f.sources.prefill({...source,title:'Must not replace pending link'},exactTarget),false);
  assert.equal(f.calls.length,1,'a refused preview must not save or link anything');
  f.view.click('slAction','link-source');await settle();
  assert.deepEqual(f.calls[1],{path:'/api/source-links',body:{project_id:profile.project_id,revision:profile.revision,expected_digest:'library-before',spec:{source_id:saved.source_id,source_version:saved.version,target_id:exactTarget,note:rationale}}});
  assert.equal(f.asked.length,0);

  const noteOnly=libraryFixture();await settle();noteOnly.view.field('slLink','note','Unfinished note without a source yet');
  assert.equal(noteOnly.sources.prefillAvailability().state,'unsaved-link');
  assert.equal(noteOnly.sources.prefill({...source},exactTarget),false);
  noteOnly.view.click('slAction','refresh');await settle();
  assert.match(noteOnly.view.innerHTML,/Unfinished note without a source yet/);
  assert.ok(noteOnly.calls.every(call=>call.body===undefined));
});

test('only a validated live library load publishes its exact profile through onChange',async()=>{
  const updates=[],profile=baseProfile();profile.sources=[{...source,source_id:'loaded-source',version:2}];
  const f=libraryFixture({profile,onChange:value=>updates.push(value)});await settle();
  assert.deepEqual(updates.map(clone),[profile]);
  updates[0].sources[0].title='Changed callback copy';
  assert.match(f.view.innerHTML,/Thermal reference/,'onChange receives a copy, not the live library profile');
  f.view.click('slAction','refresh');await settle();assert.equal(updates.length,2);assert.deepEqual(clone(updates[1]),profile);
  const rejected=[];const wrong=libraryFixture({api:async()=>({...baseProfile(),run_id:'different-run'}),onChange:value=>rejected.push(value)});await settle();
  assert.equal(wrong.sources.prefillAvailability().ready,false);assert.equal(rejected.length,0);
  let finish;
  const late=[];const stale=libraryFixture({api:()=>new Promise(resolve=>{finish=resolve;}),onChange:value=>late.push(value)});
  stale.sources.unmount();finish(baseProfile());await settle();assert.equal(late.length,0,'unmounted load must not publish into the current host cache');
});

test('saved search and preview stay read-only until explicit copy, including failed boolean and reasoned handoffs',async()=>{
  const window=runtime('source-research.js'),view=host(),calls=[],copied=[];
  let handoffResult=false;
  const receipt={project_id:'project-exact',revision:3,search_id:'search-exact',digest:'receipt-exact',state:'completed',query:'thermal assumptions',target:{target_id:exactTarget,label:'Payload heat'},results:[{title:source.title,url:source.url,content:source.excerpt}]};
  const profile={project_id:'project-exact',revision:3,targets:[receipt.target],searches:[{...receipt,result_count:1}],can_search:true,library_digest:'library-exact'};
  window.SixDResearch.mount(view,{projectId:'project-exact',revision:3,inAssistant:true,canEdit:true,initialTarget:exactTarget,initialQuery:'thermal assumptions',
    api:async(path,body)=>{calls.push({path,body});if(path==='/api/research/status')return {key_present:true,remaining_credits:1,can_search:true};if(path.includes('/preview?'))return {project_id:'project-exact',revision:3,search_id:receipt.search_id,result_index:0,receipt_digest:receipt.digest,source:clone(source)};if(path.startsWith('/api/research/search-exact?'))return clone(receipt);return clone(profile);},
    onUseReference:async(draft,context)=>{copied.push({draft:clone(draft),context:clone(context)});return handoffResult;}});
  await settle();
  assert.equal(calls.length,2);assert.ok(calls.every(call=>call.body===undefined));
  view.click('srAction','load-record',{srId:'search-exact'});await settle();
  view.click('srAction','preview',{srIndex:'0'});await settle();
  assert.match(view.innerHTML,/Preview · not saved or linked/);
  assert.equal(copied.length,0);
  view.click('srAction','use');await settle();
  assert.deepEqual(copied,[{draft:source,context:{target_id:exactTarget,search_id:'search-exact'}}]);
  assert.match(view.innerHTML,/Preview · not saved or linked/,'failed handoff retains preview');
  handoffResult={copied:false,reason:'Finish the existing reference-link draft before copying this preview.'};
  view.click('srAction','use');await settle();
  assert.equal(copied.length,2);assert.match(view.innerHTML,/Preview · not saved or linked/);
  assert.equal(view.node('[data-sr-error]').textContent,handoffResult.reason,'the precise refusal is visible inside the preview modal');
  assert.ok(calls.every(call=>call.body===undefined),'reading, previewing and failed copy never start search, save or link');
});
