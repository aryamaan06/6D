/* Local image previews and user-written notes. No OCR, upload or model request. */
(() => {
  'use strict';

  const LIMITS=Object.freeze({bytes:5*1024*1024,width:8192,height:8192,pixels:12000000,description:1000,contexts:4});
  const contexts=new Map();
  let mounted=null,instance=0;
  const ascii=(bytes,offset,length)=>String.fromCharCode(...bytes.subarray(offset,offset+length));
  const u16=(bytes,offset)=>bytes[offset]*256+bytes[offset+1];
  const u32=(bytes,offset)=>bytes[offset]*16777216+bytes[offset+1]*65536+bytes[offset+2]*256+bytes[offset+3];
  const le32=(bytes,offset)=>bytes[offset]+bytes[offset+1]*256+bytes[offset+2]*65536+bytes[offset+3]*16777216;
  const le24=(bytes,offset)=>bytes[offset]+bytes[offset+1]*256+bytes[offset+2]*65536;
  const fail=message=>{throw new Error(message);};

  function inspectDimensions(width,height){
    if(!Number.isSafeInteger(width)||!Number.isSafeInteger(height)||width<1||height<1)fail('The image dimensions could not be read.');
    if(width>LIMITS.width||height>LIMITS.height||width*height>LIMITS.pixels)fail('Choose an image no larger than 8,192 pixels on either side and 12 megapixels in total.');
    return {width,height};
  }

  function pngDimensions(bytes){
    if(bytes.length<33||u32(bytes,8)!==13||ascii(bytes,12,4)!=='IHDR')fail('This PNG header is incomplete.');
    const dimensions=inspectDimensions(u32(bytes,16),u32(bytes,20));
    // Animated containers can hide many frames behind a small first-frame size.
    for(let offset=8;offset+12<=bytes.length;){
      const size=u32(bytes,offset),kind=ascii(bytes,offset+4,4);
      if(size>bytes.length-offset-12)fail('This PNG file is incomplete.');
      if(kind==='acTL')fail('Choose a still PNG, JPEG or WebP image; animated images are not supported.');
      if(kind==='IEND')break;
      offset+=size+12;
    }
    return dimensions;
  }

  function jpegDimensions(bytes){
    for(let offset=2;offset<bytes.length;){
      if(bytes[offset++]!==255)fail('This JPEG header is incomplete.');
      while(bytes[offset]===255)offset++;
      const marker=bytes[offset++];
      if(marker===0xD9||marker===0xDA)break;
      if(marker===0xD8||marker===1||marker>=0xD0&&marker<=0xD7)continue;
      if(offset+2>bytes.length)break;
      const size=u16(bytes,offset);
      if(size<2||size>bytes.length-offset)break;
      if([0xC0,0xC1,0xC2,0xC3,0xC5,0xC6,0xC7,0xC9,0xCA,0xCB,0xCD,0xCE,0xCF].includes(marker)){
        if(size<8)break;
        return inspectDimensions(u16(bytes,offset+5),u16(bytes,offset+3));
      }
      offset+=size;
    }
    fail('The JPEG dimensions could not be read.');
  }

  function webpDimensions(bytes){
    if(bytes.length<25||le32(bytes,4)+8!==bytes.length)fail('This WebP file is incomplete.');
    for(let offset=12;offset+8<=bytes.length;){
      const size=le32(bytes,offset+4),kind=ascii(bytes,offset,4);
      if(size>bytes.length-offset-8)fail('This WebP file is incomplete.');
      if(kind==='ANIM'||kind==='ANMF')fail('Choose a still PNG, JPEG or WebP image; animated images are not supported.');
      offset+=8+size+(size&1);
    }
    const kind=ascii(bytes,12,4),size=le32(bytes,16);
    if(size>bytes.length-20)fail('This WebP file is incomplete.');
    if(kind==='VP8X'){
      if(size<10)fail('This WebP header is incomplete.');
      if(bytes[20]&2)fail('Choose a still PNG, JPEG or WebP image; animated images are not supported.');
      return inspectDimensions(1+le24(bytes,24),1+le24(bytes,27));
    }
    if(kind==='VP8L'&&size>=5&&bytes[20]===0x2F)return inspectDimensions(1+(bytes[21]|(bytes[22]&63)<<8),1+((bytes[22]>>6)|bytes[23]<<2|(bytes[24]&15)<<10));
    if(kind==='VP8 '&&size>=10&&bytes[23]===0x9D&&bytes[24]===1&&bytes[25]===0x2A)return inspectDimensions((bytes[26]|bytes[27]<<8)&16383,(bytes[28]|bytes[29]<<8)&16383);
    fail('The WebP dimensions could not be read.');
  }

  function inspectBytes(value,declaredType=''){
    const bytes=value instanceof Uint8Array?value:value instanceof ArrayBuffer?new Uint8Array(value):null;
    if(!bytes||!bytes.length)fail('Choose a nonempty PNG, JPEG or WebP image.');
    if(bytes.length>LIMITS.bytes)fail('Choose an image of 5 MiB or less.');
    let mime,dimensions;
    if(bytes.length>=8&&[137,80,78,71,13,10,26,10].every((value,index)=>bytes[index]===value)){mime='image/png';dimensions=pngDimensions(bytes);}
    else if(bytes.length>=3&&bytes[0]===255&&bytes[1]===216&&bytes[2]===255){mime='image/jpeg';dimensions=jpegDimensions(bytes);}
    else if(bytes.length>=12&&ascii(bytes,0,4)==='RIFF'&&ascii(bytes,8,4)==='WEBP'){mime='image/webp';dimensions=webpDimensions(bytes);}
    else fail('Only genuine PNG, JPEG and WebP image files are supported. SVG and other file types are not accepted.');
    const type=String(declaredType||'').toLowerCase();
    if(type&&type!==mime)fail('The file type does not match its image contents. Choose a PNG, JPEG or WebP file.');
    return Object.freeze({mime,bytes:bytes.length,...dimensions});
  }

  function dataURL(file,mime,signal){
    return new Promise((resolve,reject)=>{
      const reader=new FileReader();
      const abort=()=>reader.abort(),done=(error,result)=>{signal.removeEventListener('abort',abort);reader.onload=null;reader.onerror=null;reader.onabort=null;error?reject(error):resolve(result);};
      if(signal.aborted){reject(Error('Image selection was cancelled.'));return;}
      signal.addEventListener('abort',abort,{once:true});
      reader.onload=()=>{
        const result=String(reader.result||''),separator=result.indexOf(',');
        if(separator<0||!result.slice(0,separator).endsWith(';base64')){done(Error('The image could not be previewed.'));return;}
        done(null,'data:'+mime+';base64,'+result.slice(separator+1));
      };
      reader.onerror=()=>done(Error('The image could not be read.'));
      reader.onabort=()=>done(Error('Image selection was cancelled.'));
      reader.readAsDataURL(file);
    });
  }

  function decodedDimensions(url,signal){
    return new Promise((resolve,reject)=>{
      const image=new Image();let settled=false;
      const abort=()=>done(Error('Image selection was cancelled.'));
      const done=(error,result)=>{if(settled)return;settled=true;signal.removeEventListener('abort',abort);image.onload=null;image.onerror=null;image.src='';error?reject(error):resolve(result);};
      if(signal.aborted){reject(Error('Image selection was cancelled.'));return;}
      signal.addEventListener('abort',abort,{once:true});
      const loaded=()=>done(null,{width:image.naturalWidth,height:image.naturalHeight}),failed=()=>done(Error('This image cannot be decoded. Choose another file.'));
      image.onerror=failed;
      if(typeof image.decode!=='function')image.onload=loaded;
      image.src=url;
      if(typeof image.decode==='function')image.decode().then(loaded,failed);
    });
  }

  function mount(host,options={}){
    if(!host||typeof host.replaceChildren!=='function')throw new TypeError('An attachment host is required.');
    const key=options.contextKey;
    if(typeof key!=='string'||!key||key.length>2000)throw new TypeError('A saved assistant context key is required.');
    mounted?.dispose();
    let state=contexts.get(key)||{asset:null,description:''};
    contexts.delete(key);contexts.set(key,state);
    while(contexts.size>LIMITS.contexts)contexts.delete(contexts.keys().next().value);
    const uid='aa-'+(++instance),controller=new AbortController();
    let disposed=false,serial=0,busy=false,disabled=false;
    const snapshot=()=>({present:!!state.asset,description:state.asset?state.description:''});
    const changed=()=>options.onChange?.(snapshot());
    const live=()=>!disposed&&host.isConnected!==false;
    host.innerHTML='<section class="aa-attachment" aria-label="Local image and description"><div class="aa-top"><button type="button" class="sd-mini-action aa-add" data-aa-add>Add image</button><span class="aa-hint">Local preview · text-only models</span></div><input class="aa-file" id="'+uid+'-file" data-aa-file type="file" accept="image/png,image/jpeg,image/webp" tabindex="-1" hidden><p class="aa-error" data-aa-error role="alert" hidden></p><div class="aa-content" data-aa-content hidden><figure class="aa-preview"><img data-aa-image alt="Your selected image, previewed locally"><figcaption data-aa-name></figcaption></figure><div class="aa-notes"><div class="aa-notes-heading"><label for="'+uid+'-description">Describe the image for Nemotron</label><button type="button" class="sd-mini-action" data-aa-remove>Remove image</button></div><textarea id="'+uid+'-description" class="sd-input" data-aa-description rows="3" maxlength="1000" spellcheck="true" lang="en" autocorrect="off" placeholder="Paste the visible text or describe what you want to discuss."></textarea><div class="aa-description-meta"><span>Unverified image notes</span><span data-aa-count>0/1000</span></div><p class="aa-explanation">Nemotron receives your description, not the image. No image upload or automatic reading occurs. These notes do not become saved calculation evidence.</p></div></div></section>';
    const find=selector=>host.querySelector(selector),input=find('[data-aa-file]'),description=find('[data-aa-description]'),add=find('[data-aa-add]');
    const error=message=>{const node=find('[data-aa-error]');node.textContent=message;node.hidden=!message;};
    function render(){
      if(!live())return;
      find('[data-aa-content]').hidden=!state.asset;
      const preview=find('[data-aa-image]');
      if(state.asset){preview.src=state.asset.url;find('[data-aa-name]').textContent=state.asset.name;}
      else{preview.removeAttribute('src');find('[data-aa-name]').textContent='';}
      description.value=state.description;
      find('[data-aa-count]').textContent=state.description.length+'/'+LIMITS.description;
      add.textContent=busy?'Checking image…':state.asset?'Replace image':'Add image';add.disabled=busy||disabled;find('[data-aa-remove]').disabled=busy||disabled;description.disabled=busy||disabled;input.disabled=busy||disabled;
    }
    async function select(file){
      if(!file||disabled||busy)return;
      const request=++serial;
      if(!Number.isSafeInteger(file.size)||file.size<1||file.size>LIMITS.bytes){error('Choose a nonempty PNG, JPEG or WebP image of 5 MiB or less.');input.value='';return;}
      busy=true;error('');render();changed();
      try{
        const info=inspectBytes(await file.arrayBuffer(),file.type);
        if(!live()||request!==serial)return;
        const url=await dataURL(file,info.mime,controller.signal);
        if(!live()||request!==serial)return;
        const decoded=await decodedDimensions(url,controller.signal);inspectDimensions(decoded.width,decoded.height);
        if(!live()||request!==serial)return;
        state.asset={url,name:String(file.name||'Selected image').slice(0,240)};state.description='';changed();
      }catch(problem){if(live()&&request===serial)error(problem?.message||'The image could not be previewed.');}
      finally{if(live()&&request===serial){busy=false;input.value='';render();changed();}}
    }
    add.addEventListener('click',()=>input.click(),{signal:controller.signal});
    input.addEventListener('change',()=>{void select(input.files?.[0]);},{signal:controller.signal});
    description.addEventListener('input',()=>{
      if(!state.asset||disabled||busy)return;
      state.description=description.value.slice(0,LIMITS.description);if(description.value!==state.description)description.value=state.description;
      find('[data-aa-count]').textContent=state.description.length+'/'+LIMITS.description;changed();
    },{signal:controller.signal});
    function clear(){if(disposed)return;serial++;busy=false;state.asset=null;state.description='';input.value='';error('');render();changed();}
    find('[data-aa-remove]').addEventListener('click',()=>{clear();add.focus();},{signal:controller.signal});
    const api={snapshot,isBusy:()=>!disposed&&busy,clear,setDisabled(value){if(disposed)return;const wasBusy=busy;disabled=!!value;if(disabled){serial++;busy=false;input.value='';}render();if(wasBusy&&!busy)changed();},dispose(){if(disposed)return;disposed=true;serial++;controller.abort();find('[data-aa-image]')?.removeAttribute('src');host.replaceChildren();if(mounted===api)mounted=null;}};
    mounted=api;render();changed();return Object.freeze(api);
  }

  window.SixDAssistantAttachments=Object.freeze({mount,inspectBytes,inspectDimensions,limits:LIMITS});
})();
