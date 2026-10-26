import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const context={window:{}};
vm.runInNewContext(readFileSync(new URL('../src/sixd/web/source-targets.js',import.meta.url),'utf8'),context);
const {shortLabel,topic,render,update}=context.window.SixDSourceTargets;
const requirement=(id,label)=>({target_id:'requirement:'+id,kind:'requirement',label});
const decode=value=>value.replace(/&(amp|lt|gt|quot|#39);/g,(_,entity)=>({amp:'&',lt:'<',gt:'>',quot:'"','#39':"'"}[entity]));
const options=html=>[...html.matchAll(/<option value="([^"]*)"([^>]*)>([\s\S]*?)<\/option>/g)].map(match=>({
  value:decode(match[1]),label:decode(match[3]),selected:/\sselected(?:\s|$)/.test(match[2]),
}));
const pickerOptions=(targets,selected)=>[...render(targets,selected,{primaryAttr:'data-primary',advancedAttr:'data-advanced'})
  .matchAll(/<select\b[^>]*>([\s\S]*?)<\/select>/g)].map(match=>options(match[1]));

test('thermal requirements retain their component names in labels and Heating group',()=>{
  const battery=requirement('battery_thermal','Battery maximum temperature');
  const engine=requirement('engine_thermal','Engine maximum temperature');
  assert.equal(shortLabel(battery),'Battery maximum temperature');
  assert.equal(shortLabel(engine),'Engine maximum temperature');
  assert.equal(topic(battery),'Heating');
  assert.equal(topic(engine),'Heating');
  const [primary]=pickerOptions([battery,engine],engine.target_id);
  assert.deepEqual(primary.filter(row=>row.value),[
    {value:battery.target_id,label:battery.label,selected:false},
    {value:engine.target_id,label:engine.label,selected:true},
  ]);
});

test('fuel, stress and thermal labels preserve arbitrary component and load-case context',()=>{
  const cases=[
    ['Upper stage minimum propellant margin','Upper stage minimum fuel margin'],
    ['Booster minimum propellant margin','Booster minimum fuel margin'],
    ['Nonnegative ideal delta-v propellant margin','Nonnegative ideal delta-v fuel margin'],
    ['Declared engine mount maximum bending stress','Engine mount maximum bending stress'],
    ['Declared antenna mount maximum bending stress','Antenna mount maximum bending stress'],
    ['Declared transverse static screening stress limit','Transverse static screening stress limit'],
    ['Declared independent steady radiator temperature limit','Independent steady radiator temperature limit'],
    ['Payload temperature after engine cutoff','Payload temperature after engine cutoff'],
    ['Maximum pointing error','Maximum pointing error'],
    ['Minimum pointing accuracy','Minimum pointing accuracy'],
  ];
  for(const [label,expected] of cases)assert.equal(shortLabel({label}),expected,label);
  assert.equal(topic({label:'Engine mount maximum bending stress'}),'Forces & structure');
});

test('generic reference checks remain readable without erasing sampling or bounds',()=>{
  const cases=[
    ['Declared minimum burnout altitude','Minimum altitude at engine cutoff'],
    ['Declared maximum sampled dynamic pressure','Maximum sampled pressure from airflow'],
    ['Declared maximum sampled upward acceleration','Maximum sampled upward acceleration'],
    ['Declared burn-duration limit','Burn time limit'],
    ['Declared required ideal delta-v burn-duration limit','Required ideal delta-v burn time limit'],
    ['Declared reference-density screening drag-force limit','Reference-density screening drag force limit'],
    ['Propellant margin','Fuel margin'],
    ['Burn duration','Engine burn time'],
    ['Stress','Structural stress'],
    ['Temperature','Temperature'],
  ];
  for(const [label,expected] of cases)assert.equal(shortLabel({label}),expected,label);
});

test('Advanced keeps exact labels and separate requirement, finding and assumption identities',()=>{
  const targets=[
    requirement('battery_thermal','Declared battery maximum temperature'),
    {target_id:'finding:battery_thermal',kind:'finding',label:'Declared battery maximum temperature · saved finding'},
    {target_id:'assumption:battery:0',kind:'model_assumption',label:'battery · Independent fixed heat input'},
  ];
  for(const target of targets){
    const [primary,advanced]=pickerOptions(targets,target.target_id);
    assert.deepEqual(primary.filter(row=>row.value).map(row=>row.value),[targets[0].target_id]);
    assert.deepEqual(advanced.filter(row=>row.value).map(row=>({value:row.value,label:row.label})),
      targets.map(row=>({value:row.target_id,label:row.label})));
    assert.deepEqual(advanced.filter(row=>row.selected).map(row=>row.value),[target.target_id]);
    assert.deepEqual(primary.filter(row=>row.selected).map(row=>row.value),target.kind==='requirement'?[target.target_id]:[]);
  }
});

test('render escapes labels and IDs while preserving their exact selectable values',()=>{
  const target=requirement('thermal&"\'<panel>','Battery & "engine" <hot> \'panel\' maximum temperature');
  const html=render([target],target.target_id,{primaryAttr:'data-primary',advancedAttr:'data-advanced',label:'Check <topic> & "record"'});
  assert.ok(!html.includes('<hot>'));
  assert.ok(!html.includes('<panel>'));
  assert.ok(!html.includes('<topic>'));
  assert.ok(html.includes('&amp;'));
  assert.ok(html.includes('&quot;'));
  assert.ok(html.includes('&#39;'));
  for(const rows of pickerOptions([target],target.target_id)){
    assert.deepEqual(rows.filter(row=>row.value),[{value:target.target_id,label:target.label,selected:true}]);
  }
});

test('short list deduplicates IDs and retains the exact selected requirement beyond twelve',()=>{
  const targets=Array.from({length:15},(_,index)=>requirement('thermal_'+index,'Component '+index+' maximum temperature'));
  targets.splice(1,0,{...targets[0]});
  targets.push({target_id:'finding:thermal_14',kind:'finding',label:'Component 14 maximum temperature · saved finding'});
  const selected='requirement:thermal_14';
  const [primary]=pickerOptions(targets,selected);
  const choices=primary.filter(row=>row.value);
  assert.equal(choices.length,12);
  assert.equal(new Set(choices.map(row=>row.value)).size,12);
  assert.ok(choices.every(row=>row.value.startsWith('requirement:')));
  assert.deepEqual(choices.filter(row=>row.selected),[{value:selected,label:'Component 14 maximum temperature',selected:true}]);
});

test('update keeps exact selected IDs and original record descriptions',()=>{
  const targets=[requirement('battery_thermal','Declared battery maximum temperature'),
    {target_id:'finding:battery_thermal',kind:'finding',label:'Declared battery maximum temperature · saved finding'}];
  const primary={dataset:{},innerHTML:'',value:'',get options(){return options(this.innerHTML);}};
  const advanced={value:''},description={textContent:''},identity={textContent:''};
  const picker={querySelectorAll:()=>[primary,advanced],querySelector:selector=>selector==='[data-st-current]'?description:identity};
  const host={querySelectorAll:()=>[picker]};
  for(const target of targets){
    update(host,targets,target.target_id);
    assert.equal(primary.value,target.kind==='requirement'?target.target_id:'');
    assert.equal(advanced.value,target.target_id);
    assert.equal(description.textContent,target.label);
    assert.equal(identity.textContent,target.target_id);
  }
});
