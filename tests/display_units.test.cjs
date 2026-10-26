/* Display precision is separate from exact recorded inputs and findings. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
function units(){const window={};vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../src/sixd/web/units.js'),'utf8'),{window});return window.SixDUnits;}

test('ordinary quantities share seven significant digits while zero and signs stay clear',()=>{
  const u=units();assert.equal(u.number(6126.145572278846),'6,126.146');
  assert.equal(u.number(257.68080585928254),'257.6808');assert.equal(u.number(-12.3456789),'-12.34568');
  assert.equal(u.number(0),'0');assert.equal(u.number(-0),'0');assert.equal(u.number(0.00010000004),'0.0001');
});
test('tiny nonzero and extreme finite quantities never become zero, NaN or infinity',()=>{
  const u=units();
  for(const n of [Number.MIN_VALUE,-Number.MIN_VALUE,1e-300,-1e-300,1e-5,-1e-5,Number.MAX_VALUE,-Number.MAX_VALUE,1e7]){
    const label=u.number(n),parsed=Number(label.replaceAll(',',''));
    assert.notEqual(parsed,0,label);assert.ok(Number.isFinite(parsed),label);assert.equal(Math.sign(parsed),Math.sign(n));
  }
  assert.equal(u.number(0.000099999999),'1.00000e-4');
});
test('missing, textual and nonfinite inputs are not coerced into numeric findings',()=>{
  const u=units();for(const x of [null,undefined,'12','',NaN,Infinity,-Infinity,{},false])assert.equal(u.number(x),'—');
});
test('SI exponent labels format safely without rewriting technical source text or canonical values',()=>{
  const u=units();assert.equal(u.format('m^3/s^2'),'m³/s²');assert.equal(u.format('kg/m^3'),'kg/m³');
  assert.equal(u.format('m^4'),'m⁴');assert.equal(u.format('s^-2'),'s⁻²');
  for(const s of ['https://example.org/m^2','{"unit":"m^2"}','`m^2`','C:\\data\\m^2'])assert.equal(u.format(s),s);
  const row=Object.freeze({value:6126.145572278846,unit:'m/s^2'}),before=JSON.stringify(row);
  const html=u.value(row.value,row.unit);assert.match(html,/6,126\.146 m\/s²/);assert.match(html,/6126\.145572278846 m\/s\^2/);
  assert.equal(JSON.stringify(row),before);
});
test('quantity markup escapes unit text and keeps the original numeric string accessible',()=>{
  const u=units(),html=u.value(1.00000004,'m^2 <img src=x>');
  assert.match(html,/title="Exact: 1\.00000004/);assert.match(html,/&lt;img src=x&gt;/);assert.doesNotMatch(html,/<img/);
});
