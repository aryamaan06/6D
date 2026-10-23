/* Explicit, bounded reference searches. Results never change engineering findings. */
(() => {
  'use strict';
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const list=value=>Array.isArray(value)?value:[];
  const clone=value=>JSON.parse(JSON.stringify(value));
  const button=(action,label,extra='')=>'<button type="button" class="sr-button" data-sr-action="'+action+'" '+extra+'>'+esc(label)+'</button>';
  const safeURL=value=>{try{const url=new URL(value);return ['http:','https:'].includes(url.protocol)&&!url.username&&!url.password?url.href:null;}catch{return null;}};
  const query=(s)=>'?project_id='+encodeURIComponent(s.ctx.projectId)+'&revision='+encodeURIComponent(s.ctx.revision);
  const readOnly=s=>!!s.ctx.hasDraft||s.ctx.canEdit===false;
  let mounted=null;
  const active=s=>mounted===s&&!s.disposed&&s.host.isConnected;
  const find=(s,selector)=>s.host.querySelector(selector);
  function checkProfile(s,value){
    if(!value||value.project_id!==s.ctx.projectId||Number(value.revision)!==Number(s.ctx.revision)||!Array.isArray(value.targets)||!Array.isArray(value.searches))throw Error('The research context changed. Refresh this saved project.');
    return value;
  }
  function checkReceipt(s,value){
    if(!value||value.project_id!==s.ctx.projectId||!Number.isInteger(value.revision)||value.revision>s.ctx.revision||!['completed','failed','pending'].includes(value.state)||!Array.isArray(value.results))throw Error('The search record does not match this saved project. Refresh its history.');
    return value;
  }
  function canSearch(s){return !s.busy&&!readOnly(s)&&s.profile?.can_search===true&&!!s.status?.key_present&&!s.status?.usage_review_required&&s.status?.can_search!==false&&s.status?.remaining_credits>=1&&s.profile.targets.some(target=>target.target_id===s.target)&&!!s.query.trim();}
  function controls(s){
    if(!active(s))return;
    s.host.querySelectorAll('[data-sr-field="query"],[data-sr-field="target"]').forEach(node=>node.disabled=!!s.busy||readOnly(s)||s.profile?.can_search!==true||s.status?.usage_review_required===true);
    s.host.querySelectorAll('[data-sr-action="search"]').forEach(node=>node.disabled=!canSearch(s));
    s.host.querySelectorAll('[data-sr-action="refresh"],[data-sr-action="load-record"],[data-sr-action="preview"]').forEach(node=>node.disabled=!!s.busy);
    s.host.querySelectorAll('[data-sr-field="key"],[data-sr-field="credit_limit"]').forEach(node=>node.disabled=!!s.busy);
    const connect=find(s,'[data-sr-action="connect"]');if(connect)connect.disabled=!!s.busy||!find(s,'[data-sr-field="key"]')?.value.trim();
    const disconnect=find(s,'[data-sr-action="disconnect"]');if(disconnect)disconnect.disabled=!!s.busy||!s.status?.key_present;
    const use=find(s,'[data-sr-action="use"]');if(use)use.disabled=!!s.busy||readOnly(s)||!s.preview||!s.ctx.onUseReference;
    const status=find(s,'[data-sr-status]');if(status)status.textContent=s.busy==='search'?'One Tavily request is in progress. If the connection is interrupted, refresh saved searches before starting another.':s.busy==='connect'?'Updating the private local connection…':s.busy==='preview'?'Reading the saved reference preview…':s.busy==='record'?'Reading the saved search…':s.busy==='load'?'Reading research settings and saved searches…':s.notice;
    const error=find(s,'[data-sr-error]');if(error){error.hidden=!s.error;error.textContent=s.error;}
  }
  function connection(s){
    const status=s.status||{},limit=Number(status.credit_limit)||1;
    const options=[1,5,10,20];if(!options.includes(limit))options.push(limit);options.sort((a,b)=>a-b);
    return '<details class="sr-connection"><summary>Optional Tavily connection · '+(status.key_present?'connected locally':'not connected')+'</summary><p class="sr-small">Manual references and local engineering checks work without this connection. Enter the Tavily key privately here. It stays in server memory until disconnect or restart; connecting makes no search request.</p><div class="sr-connect-grid"><label class="sr-field">Tavily API key<input type="password" data-sr-field="key" autocomplete="off" autocapitalize="off" spellcheck="false" maxlength="2048" placeholder="Enter privately on this computer"></label><label class="sr-field">Cumulative app search allowance<select data-sr-field="credit_limit">'+options.map(value=>'<option value="'+value+'"'+(value===limit?' selected':'')+'>'+value+' basic search credit'+(value===1?'':'s')+'</option>').join('')+'</select></label></div><div class="sr-actions">'+button('connect','Connect privately and set allowance')+button('disconnect','Disconnect Tavily')+'</div><p class="sr-small">This is an absolute cumulative ceiling for this app, not an additional allowance on each connection. Prior reservations survive reconnects. Failed requests retain their reservation; nothing retries automatically.</p><dl class="sr-budget"><dt>App credit ceiling</dt><dd>'+esc(status.credit_limit??'Not set')+'</dd><dt>Conservative credits reserved</dt><dd>'+esc(status.reserved_credits??'—')+'</dd><dt>Remaining request capacity</dt><dd>'+esc(status.remaining_credits??'—')+'</dd></dl><p class="sr-small">These are application reservations, not your Tavily account balance or billed usage. No currency conversion is inferred.</p></details>';
  }
  function searchForm(s){
    const targets=list(s.profile?.targets);
    return '<div class="sr-search-form"><label class="sr-field">Engineering context<select data-sr-field="target"><option value="">Choose a requirement, assumption or finding</option>'+targets.map(target=>'<option value="'+esc(target.target_id)+'"'+(target.target_id===s.target?' selected':'')+'>'+esc(target.label)+'</option>').join('')+'</select></label><label class="sr-field">Search query<textarea rows="2" maxlength="1000" data-sr-field="query" placeholder="Type the public reference you want to find.">'+esc(s.query)+'</textarea></label><div class="sr-actions">'+button('search','Search references · 1 credit expected')+'</div><p class="sr-small">Only the query you type is sent to Tavily. Your project data is not attached automatically. Each explicit search uses one basic request with at most five results; generated answers, page extraction and automatic retries are off.</p></div>';
  }
  function history(s){
    const records=list(s.profile?.searches);
    return '<section class="sr-history"><div class="sr-heading"><h4>Saved searches</h4><span class="sr-small">'+records.length+' retained</span></div>'+(records.length?'<div class="sr-history-list">'+records.map(record=>'<button type="button" class="sr-history-item" data-sr-action="load-record" data-sr-id="'+esc(record.search_id)+'"><span>'+esc(record.query)+'</span><small>R'+esc(record.revision)+' · '+esc(record.state)+' · '+esc(record.result_count??0)+' results · '+esc(record.created_at)+'</small></button>').join('')+'</div>':'<p class="sr-small">No searches have been made for this project. Opening this panel does not start one.</p>')+'</section>';
  }
  function result(s){
    const record=s.receipt;if(!record)return '';
    const results=list(record.results),error=record.error;
    return '<section class="sr-record" aria-label="Captured reference search"><div class="sr-heading"><div><span class="sr-eyebrow">'+(record.state==='completed'?'Unverified search results':'Saved search outcome')+'</span><h4>'+esc(record.query)+'</h4></div><span class="sr-badge">'+esc(record.state)+'</span></div><p class="sr-small">Original context: '+esc(record.target?.label||record.target?.target_id||'Not supplied')+' · saved R'+esc(record.revision)+'. Search ranking does not establish source accuracy, relevance or engineering validity.</p>'+(record.revision!==s.ctx.revision?'<p class="sr-notice">This search belongs to an earlier saved revision. Check the source and current engineering context before creating a new link.</p>':'')+(error?'<div class="sr-error"><strong>'+esc(error.message||'The search did not complete.')+'</strong><p>'+esc(error.next_step||'The request reservation is retained. No automatic retry was made.')+'</p></div>':'')+(record.usage_warning?'<p class="sr-error" role="alert">'+esc(record.usage_warning)+'</p>':'')+(record.state==='pending'?'<p class="sr-notice">No terminal response is recorded. Refresh saved searches before deliberately starting another request; a lost browser response does not prove the provider was never contacted.</p>':'')+(results.length?'<div class="sr-results">'+results.map((item,index)=>'<article class="sr-result"><span class="sr-eyebrow">Result '+esc(index+1)+' · unverified reference</span><h5>'+esc(item.title||'Untitled result')+'</h5>'+(safeURL(item.url)?'<a class="sr-url" href="'+esc(safeURL(item.url))+'" target="_blank" rel="noopener noreferrer">'+esc(item.url)+'</a>':'<p class="sr-small">'+esc(item.url||'URL unavailable')+'</p>')+'<blockquote>'+esc(item.content||'No excerpt returned.')+'</blockquote>'+(item.content_truncated?'<p class="sr-small">The captured excerpt was truncated to the application limit.</p>':'')+button('preview','Review reference before using','data-sr-index="'+index+'"')+'</article>').join('')+'</div>':record.state==='completed'?'<p class="sr-small">No usable results were returned. No reference was added to the library.</p>':'')+'<details class="sr-identity"><summary>Captured request and provenance</summary><p>Search '+esc(record.search_id)+'<br>Receipt '+esc(record.digest)+'<br>Original library '+esc(record.library_digest)+'<br>Provider request '+esc(record.request_id||'Not reported')+'<br>Created '+esc(record.created_at)+'<br>Completed '+esc(record.completed_at||'Not recorded')+'</p><p>Reserved credits: '+esc(record.reserved_credits)+' · Provider-reported credits: '+esc(record.reported_usage?.credits??'Not reported')+'</p><pre>'+esc(JSON.stringify(record.request||{},null,2))+'</pre><ul>'+list(record.limitations).map(item=>'<li>'+esc(item)+'</li>').join('')+'</ul></details></section>';
  }
  function preview(s){
    if(!s.preview)return '';
    const value=s.preview.source;
    return '<section class="sr-preview" aria-label="Reference preview"><span class="sr-eyebrow">Preview · not saved or linked</span><h4>'+esc(value.title)+'</h4>'+(safeURL(value.url)?'<a class="sr-url" href="'+esc(safeURL(value.url))+'" target="_blank" rel="noopener noreferrer">'+esc(value.url)+'</a>':'<p>'+esc(value.url)+'</p>')+'<blockquote>'+esc(value.excerpt)+'</blockquote><p class="sr-preserve sr-small">'+esc(value.details)+'</p><p class="sr-notice">Review the source and passage. Using this preview only fills the existing reference form; you must explicitly save it and then create its engineering link.</p><div class="sr-actions">'+button('use','Use in source form')+button('close-preview','Close preview')+'</div></section>';
  }
  function draw(s){
    if(!active(s))return;
    s.host.innerHTML='<section class="sr-page" aria-label="Optional reference research"><header class="sr-page-header"><div><span class="sr-eyebrow">Optional research · saved project R'+esc(s.ctx.revision)+'</span><h3>Find additional references.</h3><p>Search deliberately, inspect the passage, then choose whether it belongs in your source library.</p></div>'+button('refresh','Refresh saved searches')+'</header><p class="sr-notice">'+(s.ctx.hasDraft?'This is the saved project context. Save or discard the draft before searching or using a preview.':s.ctx.canEdit===false?'Historical revisions are read-only. You can inspect saved research; select the latest revision to search or use a preview.':'Web references supplement engineering review. They never change calculation results, requirement verdicts or the scope that remains unassessed.')+'</p>'+connection(s)+((s.status?.usage_review_required||s.profile?.usage_review_required)?'<p class="sr-error" role="alert">Research is paused because recorded provider usage exceeded the expected basic-request reservation. Review the captured receipt and provider/account settings. Reconnecting does not clear this flag.</p>':'')+'<p class="sr-live" data-sr-status role="status" aria-live="polite"></p><p class="sr-error" data-sr-error role="alert" hidden></p>'+(s.profile?searchForm(s)+history(s):'<p class="sr-small">Loading research settings…</p>')+result(s)+preview(s)+'</section>';
    controls(s);
  }
  async function load(s,{preserve=false}={}){
    if(s.busy||!active(s))return;
    const serial=++s.serial;s.controller?.abort();s.controller=new AbortController();s.busy='load';s.error='';s.notice='';controls(s);
    try{
      const [status,profile]=await Promise.all([s.ctx.api('/api/research/status',undefined,{signal:s.controller.signal}),s.ctx.api('/api/research'+query(s),undefined,{signal:s.controller.signal})]);
      if(!active(s)||serial!==s.serial)return;
      s.status=status;s.profile=checkProfile(s,profile);
      if(!s.profile.targets.some(target=>target.target_id===s.target))s.target='';
      if(!preserve){s.receipt=null;s.preview=null;}
      s.notice='Saved research context loaded. No search request was made.';
    }catch(error){if(active(s)&&serial===s.serial&&error.name!=='AbortError')s.error=error.message||'Research settings could not be read.';}
    finally{if(active(s)&&serial===s.serial){s.busy='';draw(s);}}
  }
  async function connect(s,disconnect=false){
    if(s.busy||!active(s))return;
    const input=find(s,'[data-sr-field="key"]'),key=input?.value.trim();
    if(!disconnect&&!key)return;
    const credit_limit=Number(find(s,'[data-sr-field="credit_limit"]')?.value),serial=++s.serial;
    s.busy='connect';s.error='';s.notice='';const body=disconnect?{}:{api_key:key,credit_limit};
    const pending=s.ctx.api(disconnect?'/api/research/disconnect':'/api/research/connect',body);if(input)input.value='';controls(s);
    try{
      const status=await pending;if(!active(s)||serial!==s.serial)return;s.status=status;
      s.notice=disconnect?'Tavily disconnected. Saved research and prior credit reservations remain.':'Tavily connected for this server session. No search request was made.';
    }catch{if(active(s)&&serial===s.serial)s.error=disconnect?'The disconnect could not be confirmed. Refresh research settings.':'The private connection or credit ceiling could not be updated. Check the key and select a ceiling that preserves prior reservations. No key value is displayed.';}
    finally{if(active(s)&&serial===s.serial){s.busy='';draw(s);}}
  }
  async function search(s){
    if(!canSearch(s))return;
    const serial=++s.serial;s.controller?.abort();s.controller=new AbortController();s.busy='search';s.error='';s.notice='';s.preview=null;controls(s);
    try{
      const value=await s.ctx.api('/api/research/search',{project_id:s.ctx.projectId,revision:s.ctx.revision,target_id:s.target,query:s.query.trim(),expected_digest:s.profile.library_digest},{signal:s.controller.signal});
      if(!active(s)||serial!==s.serial)return;s.receipt=checkReceipt(s,value);
      s.notice=value.state==='completed'?'Search captured. Review a result before choosing to use it. Nothing was added to the source library.':'Search outcome saved. Its request reservation remains; no automatic retry was made.';
      const [status,profile]=await Promise.all([s.ctx.api('/api/research/status'),s.ctx.api('/api/research'+query(s))]);
      if(!active(s)||serial!==s.serial)return;s.status=status;s.profile=checkProfile(s,profile);
    }catch(error){if(active(s)&&serial===s.serial&&error.name!=='AbortError')s.error='The search outcome could not be confirmed. Refresh saved searches before starting another. '+(error.message||'');}
    finally{if(active(s)&&serial===s.serial){s.busy='';draw(s);}}
  }
  async function openRecord(s,id){
    if(s.busy||!s.profile?.searches.some(record=>record.search_id===id))return;
    const serial=++s.serial;s.controller?.abort();s.controller=new AbortController();s.busy='record';s.error='';s.preview=null;controls(s);
    try{
      const value=await s.ctx.api('/api/research/'+encodeURIComponent(id)+query(s),undefined,{signal:s.controller.signal});
      if(!active(s)||serial!==s.serial)return;s.receipt=checkReceipt(s,value);s.notice='The original saved search is displayed. No request was repeated.';
    }catch(error){if(active(s)&&serial===s.serial&&error.name!=='AbortError')s.error=error.message||'The saved search could not be read.';}
    finally{if(active(s)&&serial===s.serial){s.busy='';draw(s);}}
  }
  async function openPreview(s,index){
    if(s.busy||!s.receipt||s.receipt.state!=='completed'||!Number.isInteger(index)||index<0||index>=s.receipt.results.length)return;
    const serial=++s.serial,id=s.receipt.search_id;s.controller?.abort();s.controller=new AbortController();s.busy='preview';s.error='';s.preview=null;controls(s);
    try{
      const value=await s.ctx.api('/api/research/'+encodeURIComponent(id)+'/preview'+query(s)+'&result_index='+index,undefined,{signal:s.controller.signal});
      if(!active(s)||serial!==s.serial||s.receipt?.search_id!==id)return;
      if(value?.project_id!==s.ctx.projectId||Number(value.revision)!==Number(s.ctx.revision)||value.search_id!==id||value.result_index!==index||value.receipt_digest!==s.receipt.digest||!value.source||!['title','url','excerpt','details'].every(key=>typeof value.source[key]==='string')||!safeURL(value.source.url))throw Error('The captured reference preview does not match this search result. Refresh its saved record.');
      s.preview={source:clone(value.source),search_id:id,index};s.notice='Preview loaded from the saved search. No source was saved or linked.';
    }catch(error){if(active(s)&&serial===s.serial&&error.name!=='AbortError')s.error=error.message||'The captured preview could not be read.';}
    finally{if(active(s)&&serial===s.serial){s.busy='';draw(s);if(s.preview)find(s,'.sr-preview')?.scrollIntoView({block:'nearest'});}}
  }
  function mount(host,ctx){
    unmount();const s={host,ctx,status:null,profile:null,receipt:null,preview:null,target:'',query:'',busy:'',error:'',notice:'',serial:0,controller:null,disposed:false};mounted=s;
    const input=event=>{const field=event.target.dataset.srField;if(field==='query')s.query=event.target.value;if(field==='target')s.target=event.target.value;controls(s);};
    const click=event=>{const control=event.target.closest('[data-sr-action]');if(!control||!host.contains(control)||control.disabled)return;const action=control.dataset.srAction;
      if(action==='refresh'){void load(s);return;}if(action==='connect'){void connect(s);return;}if(action==='disconnect'){void connect(s,true);return;}if(action==='search'){void search(s);return;}if(action==='load-record'){void openRecord(s,control.dataset.srId);return;}if(action==='preview'){void openPreview(s,Number(control.dataset.srIndex));return;}if(action==='close-preview'){s.preview=null;draw(s);return;}
      if(action==='use'&&s.preview&&!readOnly(s)&&!s.busy){
        const draft=clone(s.preview.source);
        try{
          const copied=ctx.onUseReference?.(draft,{target_id:s.receipt?.target?.target_id,search_id:s.preview.search_id});
          if(copied===false){s.error='The source form is busy or no longer available. Keep this preview and refresh the saved source library before copying.';controls(s);return;}
          s.preview=null;s.notice='Reference copied to the source form. Review it and save explicitly, then add its engineering link.';draw(s);
        }catch{s.error='The reference could not be copied. The preview is retained; reopen the saved source form before trying again.';controls(s);}
      }
    };
    host.addEventListener('input',input);host.addEventListener('change',input);host.addEventListener('click',click);
    s.dispose=()=>{if(s.disposed)return;const key=find(s,'[data-sr-field="key"]');if(key)key.value='';s.disposed=true;s.serial++;s.controller?.abort();host.removeEventListener('input',input);host.removeEventListener('change',input);host.removeEventListener('click',click);if(mounted===s)mounted=null;};
    draw(s);void load(s);return s.dispose;
  }
  function unmount(){mounted?.dispose();}
  window.SixDResearch=Object.freeze({mount,unmount});
})();
