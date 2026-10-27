/* Local-only attachment guards and actual browser lifecycle. No provider calls. */
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import {deflateSync} from 'node:zlib';

const source=await readFile(new URL('../src/sixd/web/assistant-attachments.js',import.meta.url),'utf8');
const stylesheet=await readFile(new URL('../src/sixd/web/assistant-attachments.css',import.meta.url),'utf8');
const scope={window:{},Uint8Array,ArrayBuffer};vm.createContext(scope);vm.runInContext(source,scope);
const api=scope.window.SixDAssistantAttachments;
const put32=(bytes,offset,value)=>{bytes[offset]=value>>>24;bytes[offset+1]=value>>>16;bytes[offset+2]=value>>>8;bytes[offset+3]=value;};
function crc32(bytes){let result=0xFFFFFFFF;for(const value of bytes){result^=value;for(let bit=0;bit<8;bit++)result=result&1?(result>>>1)^0xEDB88320:result>>>1;}return (result^0xFFFFFFFF)>>>0;}
function chunk(kind,data){const bytes=Buffer.alloc(data.length+12);bytes.writeUInt32BE(data.length);bytes.write(kind,4,'ascii');data.copy(bytes,8);bytes.writeUInt32BE(crc32(bytes.subarray(4,-4)),bytes.length-4);return bytes;}
function png(width=1,height=1,animated=false,badPixels=false){
  const header=Buffer.alloc(13);header.writeUInt32BE(width);header.writeUInt32BE(height,4);header[8]=8;header[9]=6;
  return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),chunk('IHDR',header),...(animated?[chunk('acTL',Buffer.from([0,0,0,2,0,0,0,0]))]:[]),chunk('IDAT',badPixels?Buffer.from([1,2,3]):deflateSync(Buffer.from([0,50,100,150,255]))),chunk('IEND',Buffer.alloc(0))]);
}
function jpeg(width,height){const bytes=new Uint8Array([255,216,255,192,0,8,8,0,0,0,0,1,255,217]);bytes[7]=height>>8;bytes[8]=height;bytes[9]=width>>8;bytes[10]=width;return bytes;}
function webpX(width,height,flags=0){
  const bytes=new Uint8Array(30);bytes.set(Buffer.from('RIFF'));bytes[4]=22;bytes.set(Buffer.from('WEBPVP8X'),8);bytes[16]=10;bytes[20]=flags;
  for(let index=0;index<3;index++){bytes[24+index]=(width-1)>>(index*8);bytes[27+index]=(height-1)>>(index*8);}return bytes;
}

test('image signatures determine type and dimensions; names and claimed types cannot admit SVG or arbitrary data',()=>{
  for(const [bytes,type,width,height] of [[png(),'image/png',1,1],[jpeg(640,480),'image/jpeg',640,480],[webpX(100,200),'image/webp',100,200]]){
    const found=api.inspectBytes(bytes,type);assert.equal(found.mime,type);assert.equal(found.width,width);assert.equal(found.height,height);assert.equal(found.bytes,bytes.length);
  }
  assert.equal(api.inspectBytes(png(),'').mime,'image/png');
  assert.throws(()=>api.inspectBytes(Buffer.from('<svg onload="alert(1)"></svg>'),'image/png'),/genuine PNG/);
  assert.throws(()=>api.inspectBytes(png(),'image/svg+xml'),/does not match/);
  assert.throws(()=>api.inspectBytes(Buffer.from('GIF89a'),'image/gif'),/genuine PNG/);
  assert.throws(()=>api.inspectBytes(new Uint8Array()),/nonempty/);
  assert.throws(()=>api.inspectBytes(png().subarray(0,20),'image/png'),/incomplete/);
});

test('size, edge, pixel and animation guards reject oversized containers before browser decoding',()=>{
  assert.throws(()=>api.inspectBytes(new Uint8Array(api.limits.bytes+1),'image/png'),/5 MiB/);
  for(const [width,height] of [[8193,1],[1,8193],[4000,4000],[0,2]])assert.throws(()=>api.inspectBytes(png(width,height),'image/png'),/dimensions|megapixels/);
  assert.equal(api.inspectBytes(png(8192,1),'image/png').width,8192);
  assert.equal(api.inspectBytes(png(3000,4000),'image/png').height,4000);
  assert.throws(()=>api.inspectDimensions(Infinity,1),/dimensions/);
  assert.throws(()=>api.inspectDimensions(2.5,1),/dimensions/);
  assert.throws(()=>api.inspectBytes(png(1,1,true),'image/png'),/animated/);
  assert.throws(()=>api.inspectBytes(webpX(100,200,2),'image/webp'),/animated/);
  const truncated=webpX(100,200);truncated[4]=255;assert.throws(()=>api.inspectBytes(truncated,'image/webp'),/incomplete/);
});

test('malformed JPEG marker lengths and WebP variants cannot bypass dimension parsing',()=>{
  for(const bytes of [new Uint8Array([255,216,255,192,0,1]),new Uint8Array([255,216,255,218]),new Uint8Array([255,216,255,255,255])])assert.throws(()=>api.inspectBytes(bytes,'image/jpeg'),/dimensions/);
  const webp=webpX(1,1);webp.set(Buffer.from('JUNK'),12);assert.throws(()=>api.inspectBytes(webp,'image/webp'),/dimensions/);
  webp.set(Buffer.from('ANIM'),12);assert.throws(()=>api.inspectBytes(webp,'image/webp'),/animated/);
  assert.throws(()=>api.inspectBytes('not bytes','image/png'),/nonempty/);
});

let playwright;
try{playwright=await import(process.env.PLAYWRIGHT_MODULE||'playwright');}
catch(error){if(process.env.PLAYWRIGHT_MODULE)throw error;try{playwright=await import('file:///C:/Users/Arya/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs');}catch{}}

test('actual browser preview is local; descriptions are text-only snapshots, bounded and isolated across remounts', {skip:!playwright,timeout:90000},async()=>{
  const browser=await playwright.chromium.launch({channel:process.env.SIXD_BROWSER_CHANNEL||'chrome',headless:true});
  try{
    const context=await browser.newContext(),page=await context.newPage(),requests=[],errors=[];page.setDefaultTimeout(10000);
    await context.route('**/*',route=>{requests.push(route.request().url());return route.abort();});
    page.on('pageerror',error=>errors.push(error.message));
    await page.setContent('<!doctype html><html lang="en"><head></head><body><main id="host"></main></body></html>');
    await page.addStyleTag({content:stylesheet});await page.addScriptTag({content:source});
    await page.evaluate(()=>{
      window.changes=[];window.busyChanges=[];window.storageCalls=[];
      for(const name of ['localStorage','sessionStorage'])Object.defineProperty(window,name,{configurable:true,value:{setItem:(...args)=>window.storageCalls.push(args),getItem(){throw Error('Persistent browser storage must not be used.');}}});
      window.mountAttachment=key=>{window.attachment=window.SixDAssistantAttachments.mount(document.querySelector('#host'),{contextKey:key,onChange:value=>{window.changes.push(value);window.busyChanges.push(window.attachment?.isBusy()??false);}});};
      window.holdImageDecode=()=>{const original=HTMLImageElement.prototype.decode;HTMLImageElement.prototype.decode=function(...args){return original.apply(this,args).then(()=>new Promise(resolve=>{window.releaseImageDecode=()=>{HTMLImageElement.prototype.decode=original;window.releaseImageDecode=null;resolve();};}));};};
      window.mountAttachment('project-a:r1:run1');
    });
    const upload=async(buffer,name='example.png',mimeType='image/png')=>page.locator('[data-aa-file]').setInputFiles({name,mimeType,buffer:Buffer.from(buffer)});
    assert.deepEqual(await page.evaluate(()=>window.attachment.snapshot()),{present:false,description:''});
    await page.evaluate(()=>window.holdImageDecode());await upload(png());await page.waitForFunction(()=>typeof window.releaseImageDecode==='function');
    assert.equal(await page.evaluate(()=>window.attachment.isBusy()),true);assert.equal(await page.evaluate(()=>window.busyChanges.at(-1)),true);assert.equal(await page.locator('[data-aa-add]').isEnabled(),false);assert.deepEqual(await page.evaluate(()=>window.attachment.snapshot()),{present:false,description:''});
    await page.evaluate(()=>window.releaseImageDecode());await page.locator('[data-aa-content]').waitFor({state:'visible'});await page.locator('[data-aa-add]:enabled').waitFor();assert.equal(await page.evaluate(()=>window.attachment.isBusy()),false);assert.equal(await page.evaluate(()=>window.busyChanges.at(-1)),false);
    assert.match(await page.locator('[data-aa-image]').getAttribute('src'),/^data:image\/png;base64,/);
    for(const [mime,extension] of [['image/jpeg','jpg'],['image/webp','webp']]){
      const url=await page.evaluate(type=>{const canvas=document.createElement('canvas');canvas.width=2;canvas.height=3;canvas.getContext('2d').fillRect(0,0,2,3);return canvas.toDataURL(type);},mime);
      await upload(Buffer.from(url.split(',')[1],'base64'),'real.'+extension,mime);await page.waitForFunction(type=>document.querySelector('[data-aa-image]').src.startsWith('data:'+type+';base64,'),mime);
    }
    await upload(png());await page.waitForFunction(()=>document.querySelector('[data-aa-image]').src.startsWith('data:image/png;base64,'));
    assert.match(await page.locator('.aa-explanation').innerText(),/receives your description, not the image/);
    const notes=page.locator('[data-aa-description]');assert.equal(await notes.getAttribute('spellcheck'),'true');assert.equal(await notes.getAttribute('lang'),'en');assert.equal(await notes.getAttribute('autocorrect'),'off');
    await notes.fill('The plotted line approaches the declared limit. This is my reading of the image.');
    const expected={present:true,description:'The plotted line approaches the declared limit. This is my reading of the image.'};
    assert.deepEqual(await page.evaluate(()=>window.attachment.snapshot()),expected);
    await page.evaluate(()=>window.holdImageDecode());await upload(png());await page.waitForFunction(()=>typeof window.releaseImageDecode==='function');assert.equal(await page.evaluate(()=>window.attachment.isBusy()),true);
    await page.evaluate(()=>window.attachment.setDisabled(true));assert.equal(await page.evaluate(()=>window.attachment.isBusy()),false);assert.equal(await page.evaluate(()=>window.busyChanges.at(-1)),false);await page.evaluate(()=>window.releaseImageDecode());await page.evaluate(()=>window.attachment.setDisabled(false));assert.deepEqual(await page.evaluate(()=>window.attachment.snapshot()),expected);
    assert.equal(await page.evaluate(()=>Object.keys(window.attachment.snapshot()).some(key=>/url|image|name|bytes|pixels/i.test(key))),false);
    await upload(Buffer.from('<svg onload="alert(1)"></svg>'),'spoof.png','image/png');await page.locator('[data-aa-error]').waitFor({state:'visible'});assert.deepEqual(await page.evaluate(()=>window.attachment.snapshot()),expected);
    // A parseable header is not enough: the browser must decode the complete image.
    await upload(jpeg(640,480),'incomplete.jpg','image/jpeg');await page.locator('[data-aa-error]').waitFor({state:'visible'});assert.deepEqual(await page.evaluate(()=>window.attachment.snapshot()),expected);
    await page.evaluate(()=>{window.attachment.dispose();window.mountAttachment('project-b:r1:run1');});assert.deepEqual(await page.evaluate(()=>window.attachment.snapshot()),{present:false,description:''});
    await page.evaluate(()=>window.mountAttachment('project-a:r1:run1'));assert.deepEqual(await page.evaluate(()=>window.attachment.snapshot()),expected);assert.equal(await notes.inputValue(),expected.description);
    await notes.evaluate(node=>{node.value='a'.repeat(1004);node.dispatchEvent(new Event('input',{bubbles:true}));});assert.equal((await page.evaluate(()=>window.attachment.snapshot())).description.length,1000);
    await page.evaluate(()=>window.attachment.setDisabled(true));assert.equal(await notes.isEnabled(),false);assert.equal(await page.locator('[data-aa-add]').isEnabled(),false);assert.equal(await page.locator('[data-aa-remove]').isEnabled(),false);assert.deepEqual(await page.evaluate(()=>window.attachment.snapshot()),{present:true,description:'a'.repeat(1000)});
    await page.evaluate(()=>window.attachment.setDisabled(false));await page.locator('[data-aa-remove]').click();assert.deepEqual(await page.evaluate(()=>window.attachment.snapshot()),{present:false,description:''});assert.equal(await page.locator('[data-aa-image]').getAttribute('src'),null);
    // Four newer contexts evict an earlier local image rather than retaining an unbounded image history.
    await upload(png());await page.locator('[data-aa-content]').waitFor({state:'visible'});await notes.fill('Local preview cache');
    await page.evaluate(()=>window.attachment.clear());assert.deepEqual(await page.evaluate(()=>window.attachment.snapshot()),{present:false,description:''});
    await upload(png());await page.locator('[data-aa-content]').waitFor({state:'visible'});await notes.fill('Local preview cache');
    await page.evaluate(()=>{for(let index=0;index<4;index++)window.mountAttachment('other-'+index);window.mountAttachment('project-a:r1:run1');});assert.deepEqual(await page.evaluate(()=>window.attachment.snapshot()),{present:false,description:''});
    assert.deepEqual(await page.evaluate(()=>window.storageCalls),[]);assert.deepEqual(requests,[]);assert.deepEqual(errors,[]);
    const snapshots=await page.evaluate(()=>window.changes);assert.ok(snapshots.length>=5);assert.ok(snapshots.every(value=>Object.keys(value).sort().join(',')==='description,present'));
    await context.close();
  }finally{await browser.close();}
});
