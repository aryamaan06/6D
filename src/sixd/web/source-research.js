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
  function searchBlockedReason(s){
    if(s.busy)return 'Wait for the current reference operation to finish.';
    if(s.ctx.hasDraft)return 'Save or discard the draft before searching.';
    if(s.ctx.canEdit===false)return 'Choose the latest saved revision to search.';
    if(!s.status||!s.profile)return 'Reading the saved search context…';
    if(s.status.usage_review_required||s.profile.usage_review_required)return 'Search is paused for an owner usage review.';
    if(!s.status.key_present)return 'Connect Tavily privately in Owner settings before searching.';
    if(!(s.status.remaining_credits>=1))return 'Search is paused: the app’s approved Tavily allowance is used up. Update it in Owner settings; this is separate from your Tavily account balance.';
    if(s.status.can_search===false||s.profile.can_search!==true)return 'Search is unavailable in this saved context. Refresh saved searches or review Owner settings.';
    if(!s.profile.targets.some(target=>target.target_id===s.target))return 'Choose an engineering context before searching.';
    if(!s.query.trim())return 'Type a query, then click Search references. Enter adds a new line.';
    return '';
  }
  function controls(s){
    if(!active(s))return;
    if(s.reportedBusy!==!!s.busy){s.reportedBusy=!!s.busy;s.ctx.onBusyChange?.(s.reportedBusy);}
    s.host.querySelectorAll('[data-sr-field="query"],[data-sr-field="target"],[data-sr-field="advanced-target"]').forEach(node=>node.disabled=!!s.busy||readOnly(s)||s.profile?.can_search!==true||s.status?.usage_review_required===true);
    s.host.querySelectorAll('[data-sr-action="search"]').forEach(node=>node.disabled=!canSearch(s));
    if(s.profile)window.SixDSourceTargets.update(s.host,s.profile.targets,s.target);
    const blocked=find(s,'[data-sr-blocked]');if(blocked){const reason=searchBlockedReason(s);blocked.textContent=reason;blocked.hidden=!reason;}
    s.host.querySelectorAll('[data-sr-action="refresh"],[data-sr-action="load-record"],[data-sr-action="preview"]').forEach(node=>node.disabled=!!s.busy);
    s.host.querySelectorAll('[data-sr-field="key"],[data-sr-field="credit_limit"]').forEach(node=>node.disabled=!!s.busy);
    const connect=find(s,'[data-sr-action="connect"]');if(connect)connect.disabled=!!s.busy||!find(s,'[data-sr-field="key"]')?.value.trim();
    const remember=find(s,'[data-sr-field="remember"]');if(remember){remember.disabled=!!s.busy||s.status?.remember_supported!==true;if(s.status?.remember_supported!==true)remember.checked=false;}
    const forget=find(s,'[data-sr-action="forget"]');if(forget)forget.disabled=!!s.busy||(!s.status?.key_remembered&&!s.status?.credential_error);
    const disconnect=find(s,'[data-sr-action="disconnect"]');if(disconnect)disconnect.disabled=!!s.busy||(!s.status?.key_present&&!s.status?.key_remembered&&!s.status?.credential_error);
    const use=find(s,'[data-sr-action="use"]');if(use)use.disabled=!!s.busy||readOnly(s)||!s.preview||!s.ctx.onUseReference;
    const status=find(s,'[data-sr-status]');if(status)status.textContent=s.busy==='search'?'One Tavily request is in progress. If the connection is interrupted, refresh saved searches before starting another.':s.busy==='connect'?'Updating the private local connection…':s.busy==='preview'?'Reading the saved reference preview…':s.busy==='record'?'Reading the saved search…':s.busy==='load'?'Reading research settings and saved searches…':s.busy==='use'?'Opening the reference form…':s.notice;
    const error=find(s,'[data-sr-error]');if(error){error.hidden=!s.error;error.textContent=s.error;}
  }
  function connection(s){
    const status=s.status||{},limit=Number(status.credit_limit)||1;
    const options=[1,5,10,20];if(!options.includes(limit))options.push(limit);options.sort((a,b)=>a-b);
    const state=status.credential_error?(status.key_present?'Connected for this server session. Saved-key storage state is unavailable.':'No Tavily key is connected. Saved-key storage state is unavailable.'):status.key_present?(status.key_remembered?(status.key_source==='remembered'?'Remembered key connected locally.':'Session connected; an encrypted key copy is saved on this device.'):'Connected for this server session only. No key is saved on this device.'):(status.key_remembered?'A saved key is present, but no key is connected.':'No Tavily key is connected or saved.');
    const rememberHint=status.remember_supported===true?'Optional: save an encrypted copy for this Windows account and restore it when 6D starts. Leaving this unchecked removes any previous saved key when you connect.':'Remembering is unavailable on this device. A connection stays in server memory only.';
    return '<details class="sr-connection"><summary>Optional Tavily connection · '+(status.key_present?(status.key_remembered?'remembered key connected':'session connected'):'not connected')+'</summary><p class="sr-small" role="status">'+esc(state)+'</p>'+(status.key_remembered?'<p class="sr-small">The saved key and search allowance restore on server startup. Restoring or connecting makes no Tavily request and does not validate the key.</p>':'<p class="sr-small">Manual references and local engineering checks work without this connection. Connecting makes no Tavily request and does not validate the key.</p>')+(status.credential_error?'<p class="sr-error" role="alert">The saved key could not be restored or updated. Re-enter it privately, or forget the saved copy. No Tavily request was made.</p>':'')+'<div class="sr-connect-grid"><label class="sr-field">Tavily API key<input type="password" data-sr-field="key" autocomplete="off" autocapitalize="off" spellcheck="false" maxlength="2048" placeholder="Enter privately on this computer"></label><label class="sr-field">Cumulative app search allowance<select data-sr-field="credit_limit">'+options.map(value=>'<option value="'+value+'"'+(value===limit?' selected':'')+'>'+value+' basic search credit'+(value===1?'':'s')+'</option>').join('')+'</select></label></div><label class="sr-remember"><input type="checkbox" data-sr-field="remember" aria-describedby="sr-remember-note"'+(status.remember_supported===true?'':' disabled')+'>Remember on this device</label><p id="sr-remember-note" class="sr-small">'+esc(rememberHint)+'</p><div class="sr-actions">'+button('connect','Connect privately and set allowance')+button('forget','Forget saved key')+button('disconnect','Disconnect and forget')+'</div><p class="sr-small">Forget removes the saved key and keeps the current session connected. Disconnect and forget removes both. The key is cleared from this field on submission and never saved in browser storage.</p><p class="sr-small">This is an absolute cumulative ceiling for this app, not an additional allowance on each connection. Prior reservations survive reconnects. Failed requests retain their reservation; nothing retries automatically.</p><dl class="sr-budget"><dt>App credit ceiling</dt><dd>'+esc(status.credit_limit??'Not set')+'</dd><dt>Conservative credits reserved</dt><dd>'+esc(status.reserved_credits??'—')+'</dd><dt>Remaining request capacity</dt><dd>'+esc(status.remaining_credits??'—')+'</dd></dl><p class="sr-small">These are application reservations, not your Tavily account balance or billed usage. No currency conversion is inferred.</p></details>';
  }
  function searchForm(s){
    const targets=list(s.profile?.targets);
    return '<div class="sr-search-form"><p class="sr-stage">1 · Search in saved R'+esc(s.ctx.revision)+'</p>'+window.SixDSourceTargets.render(targets,s.target,{primaryAttr:'data-sr-field="target"',advancedAttr:'data-sr-field="advanced-target"',label:'What do you want to research?'})+'<label class="sr-field">Your search<textarea rows="2" maxlength="1000" data-sr-field="query" placeholder="For example: NASA rocket heating assumptions">'+esc(s.query)+'</textarea></label><div class="sr-actions">'+button('search','Search references')+'</div><p class="sr-notice" data-sr-blocked role="status" hidden></p><p class="sr-small">Only your typed query is sent to Tavily. Results are references to review, not verified engineering conclusions.</p><details class="sr-identity"><summary>What this search sends and costs</summary><p>One explicit basic search uses the configured Tavily allowance and returns at most five results. Your project data is not attached automatically. Generated answers, page extraction and automatic retries are off.</p></details></div>';
  }
  function history(s){
    const records=list(s.profile?.searches);
    return '<details class="sr-history"><summary>Earlier searches ('+records.length+')</summary><div class="sr-heading"><h4>Saved searches</h4><span class="sr-small">'+records.length+' retained</span></div>'+(records.length?'<div class="sr-history-list">'+records.map(record=>'<button type="button" class="sr-history-item" data-sr-action="load-record" data-sr-id="'+esc(record.search_id)+'"><span>'+esc(record.query)+'</span><small>R'+esc(record.revision)+' · '+esc(record.state)+' · '+esc(record.result_count??0)+' results · '+esc(record.created_at)+'</small></button>').join('')+'</div>':'<p class="sr-small">No searches have been made for this project. Opening this panel does not start one.</p>')+'</details>';
  }
  function result(s){
    const record=s.receipt;if(!record)return '';
    const results=list(record.results),error=record.error;
    return '<section class="sr-record" aria-label="Captured reference search"><div class="sr-heading"><div><span class="sr-eyebrow">'+(record.state==='completed'?'Unverified search results':'Saved search outcome')+'</span><h4>'+esc(record.query)+'</h4></div><span class="sr-badge">'+esc(record.state)+'</span></div><p class="sr-small">Original context: '+esc(record.target?.label||record.target?.target_id||'Not supplied')+' · saved R'+esc(record.revision)+'. Search ranking does not establish source accuracy, relevance or engineering validity.</p>'+(record.revision!==s.ctx.revision?'<p class="sr-notice">This search belongs to an earlier saved revision. Check the source and current engineering context before creating a new link.</p>':'')+(error?'<div class="sr-error"><strong>'+esc(error.message||'The search did not complete.')+'</strong><p>'+esc(error.next_step||'The request reservation is retained. No automatic retry was made.')+'</p></div>':'')+(record.usage_warning?'<p class="sr-error" role="alert">'+esc(record.usage_warning)+'</p>':'')+(record.state==='pending'?'<p class="sr-notice">No terminal response is recorded. Refresh saved searches before deliberately starting another request; a lost browser response does not prove the provider was never contacted.</p>':'')+(results.length?'<div class="sr-results">'+results.map((item,index)=>'<article class="sr-result"><span class="sr-eyebrow">Result '+esc(index+1)+' · unverified reference</span><h5>'+esc(item.title||'Untitled result')+'</h5>'+(safeURL(item.url)?'<a class="sr-url" href="'+esc(safeURL(item.url))+'" target="_blank" rel="noopener noreferrer">'+esc(item.url)+'</a>':'<p class="sr-small">'+esc(item.url||'URL unavailable')+'</p>')+'<blockquote>'+esc(item.content||'No excerpt returned.')+'</blockquote>'+(item.content_truncated?'<p class="sr-small">The captured excerpt was truncated to the application limit.</p>':'')+button('preview','Review reference before using','data-sr-index="'+index+'"')+'</article>').join('')+'</div>':record.state==='completed'?'<p class="sr-small">No usable results were returned. No reference was added to the library.</p>':'')+'<details class="sr-identity"><summary>Captured request and provenance</summary><p>Search '+esc(record.search_id)+'<br>Receipt '+esc(record.digest)+'<br>Original library '+esc(record.library_digest)+'<br>Provider request '+esc(record.request_id||'Not reported')+'<br>Created '+esc(record.created_at)+'<br>Completed '+esc(record.completed_at||'Not recorded')+'</p>'+(s.ctx.inAssistant?'':'<p>Reserved credits: '+esc(record.reserved_credits)+' · Provider-reported credits: '+esc(record.reported_usage?.credits??'Not reported')+'</p>')+'<pre>'+esc(JSON.stringify(record.request||{},null,2))+'</pre><ul>'+list(record.limitations).map(item=>'<li>'+esc(item)+'</li>').join('')+'</ul></details></section>';
  }
  function preview(s){
    if(!s.preview)return '';
    const value=s.preview.source;
    return '<section class="sr-preview" aria-label="Reference preview"><span class="sr-eyebrow">2 · Preview · not saved or linked</span><h4>'+esc(value.title)+'</h4>'+(safeURL(value.url)?'<a class="sr-url" href="'+esc(safeURL(value.url))+'" target="_blank" rel="noopener noreferrer">'+esc(value.url)+'</a>':'<p>'+esc(value.url)+'</p>')+'<blockquote>'+esc(value.excerpt)+'</blockquote><p class="sr-preserve sr-small">'+esc(value.details)+'</p><p class="sr-notice">Review the source and exact passage. Copying opens an unsaved draft in the Source library. Save it there, then link it to the project check before asking Nemotron about it.</p><div class="sr-actions">'+button('use','Copy draft to Source library')+button('close-preview','Close preview')+'</div><p class="sr-small">Nemotron receives only saved references linked to the chosen investigation scope, within its context limits. Search results and previews are excluded.</p></section>';
  }
  function draw(s){
    if(!active(s))return;
    if(s.ctx.connectionOnly){s.host.innerHTML='<section class="sr-page"><h3>Owner Tavily connection</h3>'+connection(s)+'<p data-sr-status role="status"></p><p data-sr-error class="sr-error" role="alert" hidden></p></section>';const disclosure=s.host.querySelector('details');if(disclosure)disclosure.open=true;controls(s);return;}
    if(s.ctx.inAssistant){
      s.host.innerHTML='<section class="sr-page sr-assistant" aria-label="Tavily reference search"><p class="sr-small">Find public references with Tavily, review the passage, then explicitly choose whether to add it to your source library.</p>'+(s.ctx.hasDraft?'<p class="sr-notice">Save or discard the draft before searching or using a preview.</p>':s.ctx.canEdit===false?'<p class="sr-notice">This historical revision is read-only. Select the latest revision to search or use a preview.</p>':'')+((s.status?.usage_review_required||s.profile?.usage_review_required)?'<p class="sr-error" role="alert">Reference search is paused for an owner usage review. Earlier records remain available.</p>':'')+'<p class="sr-live" data-sr-status role="status" aria-live="polite"></p><p class="sr-error" data-sr-error role="alert" hidden></p>'+(s.profile?searchForm(s)+history(s):'<p class="sr-small">Loading saved research…</p>')+button('refresh','Refresh saved searches')+result(s)+preview(s)+'</section>';
      controls(s);return;
    }
    s.host.innerHTML='<section class="sr-page" aria-label="Optional reference research"><header class="sr-page-header"><div><span class="sr-eyebrow">Optional research · saved project R'+esc(s.ctx.revision)+'</span><h3>Find additional references.</h3><p>Search deliberately, inspect the passage, then choose whether it belongs in your source library.</p></div>'+button('refresh','Refresh saved searches')+'</header><p class="sr-notice">'+(s.ctx.hasDraft?'This is the saved project context. Save or discard the draft before searching or using a preview.':s.ctx.canEdit===false?'Historical revisions are read-only. You can inspect saved research; select the latest revision to search or use a preview.':'Web references supplement engineering review. They never change calculation results, requirement verdicts or the scope that remains unassessed.')+'</p>'+'<p class="sr-small">Connection and usage are managed in Owner settings.</p>'+button('owner-settings','Open owner settings','data-owner-only')+((s.status?.usage_review_required||s.profile?.usage_review_required)?'<p class="sr-error" role="alert">Research is paused because recorded provider usage exceeded the expected basic-request reservation. Review the captured receipt and provider/account settings. Reconnecting does not clear this flag.</p>':'')+'<p class="sr-live" data-sr-status role="status" aria-live="polite"></p><p class="sr-error" data-sr-error role="alert" hidden></p>'+(s.profile?searchForm(s)+history(s):'<p class="sr-small">Loading research settings…</p>')+result(s)+preview(s)+'</section>';
    controls(s);
  }
  async function load(s,{preserve=false}={}){
    if(s.busy||!active(s))return;
    const serial=++s.serial;s.controller?.abort();s.controller=new AbortController();s.busy='load';s.error='';s.notice='';controls(s);
    try{
      if(s.ctx.connectionOnly){s.status=await s.ctx.api('/api/research/status',undefined,{signal:s.controller.signal});return;}
      const [status,profile]=await Promise.all([s.ctx.api('/api/research/status',undefined,{signal:s.controller.signal}),s.ctx.api('/api/research'+query(s),undefined,{signal:s.controller.signal})]);
      if(!active(s)||serial!==s.serial)return;
      s.status=status;s.profile=checkProfile(s,profile);
      if(!s.profile.targets.some(target=>target.target_id===s.target))s.target='';
      s.ctx.onDraftChange?.({query:s.query,target:s.target});
      if(!preserve){s.receipt=null;s.preview=null;}
      s.notice='Saved research context loaded. No search request was made.';
    }catch(error){if(active(s)&&serial===s.serial&&error.name!=='AbortError')s.error=error.message||'Research settings could not be read.';}
    finally{if(active(s)&&serial===s.serial){s.busy='';draw(s);}}
  }
  async function connect(s,action='connect'){
    if(s.busy||!active(s))return;
    const input=find(s,'[data-sr-field="key"]'),key=input?.value.trim();
    if(action==='connect'&&!key)return;
    const credit_limit=Number(find(s,'[data-sr-field="credit_limit"]')?.value),serial=++s.serial;
    const remember=s.status?.remember_supported===true&&find(s,'[data-sr-field="remember"]')?.checked===true;
    s.busy='connect';s.error='';s.notice='';const body=action==='connect'?{api_key:key,credit_limit,remember}:{};
    const pending=s.ctx.api('/api/research/'+action,body);if(input)input.value='';controls(s);
    try{
      const status=await pending;if(!active(s)||serial!==s.serial)return;s.status=status;
      s.notice=action==='forget'?(status.key_present?'Saved Tavily key forgotten. The current server session remains connected.':'Saved Tavily key forgotten. No key is connected.'):action==='disconnect'?'Tavily disconnected and the saved key removed. Saved research and prior credit reservations remain.':status.key_remembered?'Tavily connected and remembered on this device. No Tavily request was made; the key has not been validated.':'Tavily connected for this server session. No Tavily request was made; the key has not been validated.';
    }catch{if(active(s)&&serial===s.serial)s.error=action==='forget'?'Removing the saved Tavily key could not be confirmed. Refresh research settings.':action==='disconnect'?'The disconnect and saved-key removal could not be confirmed. Refresh research settings.':'The private connection or credit ceiling could not be updated. Check the key and select a ceiling that preserves prior reservations. No key value is displayed.';}
    finally{if(active(s)&&serial===s.serial){s.busy='';draw(s);}}
  }
  async function search(s){
    if(!canSearch(s))return;
    const serial=++s.serial;s.controller?.abort();s.controller=new AbortController();s.busy='search';s.error='';s.notice='';s.preview=null;controls(s);
    try{
      const value=await s.ctx.api('/api/research/search',{project_id:s.ctx.projectId,revision:s.ctx.revision,target_id:s.target,query:s.query.trim(),expected_digest:s.profile.library_digest},{signal:s.controller.signal});
      if(!active(s)||serial!==s.serial)return;s.receipt=checkReceipt(s,value);
      s.notice=value.state==='completed'?'Search captured. Next: review a result’s preview, then choose whether to copy a draft to the Source library. No reference is saved or linked yet.':'Search outcome saved. Its request reservation remains; no automatic retry was made.';
      if(s.ctx.connectionOnly){s.status=await s.ctx.api('/api/research/status',undefined,{signal:s.controller.signal});return;}
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
      s.preview={source:clone(value.source),search_id:id,index};s.notice='Preview ready. Review the exact passage, then click Copy draft to Source library. No reference is saved or linked yet.';
    }catch(error){if(active(s)&&serial===s.serial&&error.name!=='AbortError')s.error=error.message||'The captured preview could not be read.';}
    finally{if(active(s)&&serial===s.serial){s.busy='';draw(s);if(s.preview)find(s,'.sr-preview')?.scrollIntoView({block:'nearest'});}}
  }
  async function useReference(s){
    if(!active(s)||!s.preview||readOnly(s)||s.busy||!s.ctx.onUseReference)return;
    const draft=clone(s.preview.source),serial=++s.serial;
    const context={target_id:s.receipt?.target?.target_id,search_id:s.preview.search_id};
    s.busy='use';s.error='';controls(s);
    try{
      const copied=await s.ctx.onUseReference(draft,context);
      if(!active(s)||serial!==s.serial)return;
      if(copied===false||copied?.copied===false){s.error=typeof copied?.reason==='string'?copied.reason:'The source form is busy or no longer available. This preview is retained; open the source library and try again.';return;}
      s.preview=null;s.notice='Copied draft · not saved or linked. In the Source library, review it, click Save reference, then Link reference. Ask about this reference becomes available after linking.';
    }catch{if(active(s)&&serial===s.serial)s.error='The reference could not be copied. The preview is retained; reopen the saved source form before trying again.';}
    finally{if(active(s)&&serial===s.serial){s.busy='';draw(s);}}
  }
  function mount(host,ctx){
    unmount();const s={host,ctx,status:null,profile:null,receipt:null,preview:null,target:typeof ctx.initialTarget==='string'?ctx.initialTarget:'',query:typeof ctx.initialQuery==='string'?ctx.initialQuery.slice(0,1000):'',busy:'',error:'',notice:'',serial:0,controller:null,disposed:false};mounted=s;
    const input=event=>{const field=event.target.dataset.srField;if(field==='query')s.query=event.target.value;if(field==='target'||field==='advanced-target')s.target=event.target.value;if(field==='query'||field==='target'||field==='advanced-target')ctx.onDraftChange?.({query:s.query,target:s.target});controls(s);};
    const click=event=>{const control=event.target.closest('[data-sr-action]');if(!control||!host.contains(control)||control.disabled)return;const action=control.dataset.srAction;
      if(action==='owner-settings'){s.ctx.onOwnerSettings?.();return;}
      if(action==='refresh'){void load(s);return;}if(['connect','forget','disconnect'].includes(action)){void connect(s,action);return;}if(action==='search'){void search(s);return;}if(action==='load-record'){void openRecord(s,control.dataset.srId);return;}if(action==='preview'){void openPreview(s,Number(control.dataset.srIndex));return;}if(action==='close-preview'){s.preview=null;draw(s);return;}
      if(action==='use')void useReference(s);
    };
    host.addEventListener('input',input);host.addEventListener('change',input);host.addEventListener('click',click);
    s.dispose=()=>{if(s.disposed)return;const key=find(s,'[data-sr-field="key"]');if(key)key.value='';s.disposed=true;s.serial++;s.controller?.abort();host.removeEventListener('input',input);host.removeEventListener('change',input);host.removeEventListener('click',click);if(mounted===s)mounted=null;if(s.reportedBusy){s.reportedBusy=false;ctx.onBusyChange?.(false);}};
    draw(s);void load(s);return s.dispose;
  }
  function unmount(){mounted?.dispose();}
  window.SixDResearch=Object.freeze({mount,unmount});
})();
