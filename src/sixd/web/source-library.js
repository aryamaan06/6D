/* Manual source records and explicit links. No URL fetching, AI or calculations. */
(() => {
  'use strict';
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const array=value=>Array.isArray(value)?value:[];
  const copy=value=>JSON.parse(JSON.stringify(value));
  const statusLabel=value=>({linked:'Linked to recorded context',needs_review:'Link needs review',target_unavailable:'Target unavailable'}[value]||'Link state unavailable');
  const status=value=>'<span class="sl-badge sl-'+(['linked','needs_review','target_unavailable'].includes(value)?value:'unknown')+'">'+esc(statusLabel(value))+'</span>';
  const option=(value,label,current)=>'<option value="'+esc(value)+'"'+(String(value)===String(current)?' selected':'')+'>'+esc(label)+'</option>';
  const safeURL=value=>{try{const url=new URL(value);return ['https:','http:'].includes(url.protocol)&&!url.username&&!url.password?url.href:null;}catch{return null;}};
  const sourceURL=value=>safeURL(value)?'<a href="'+esc(safeURL(value))+'" target="_blank" rel="noopener noreferrer">'+esc(value)+'</a>':'<span class="sl-small">'+esc(value||'No URL supplied')+'</span>';
  const sourceFields=source=>'<div class="sl-source-meta"><span class="sl-eyebrow">User-supplied reference · v'+esc(source?.version??'?')+'</span><h4>'+esc(source?.title||'Source not available')+'</h4><div class="sl-url">'+sourceURL(source?.url)+'</div>'+(source?.excerpt?'<blockquote>'+esc(source.excerpt)+'</blockquote>':'')+(source?.details?'<p class="sl-preserve sl-small">'+esc(source.details)+'</p>':'')+'</div>';
  const limitation='References support a stated rationale. A link or manual review does not validate a source, change a calculated finding or close an unassessed requirement.';
  let mounted=null;

  function scoped(link,options){
    const target=link.target||{};
    if(!Array.isArray(options.requirementIds)&&!Array.isArray(options.modelIds))return true;
    if(target.kind==='model_assumption')return Array.isArray(options.modelIds)&&options.modelIds.includes(target.model_id??target.id);
    if(['requirement','finding'].includes(target.kind))return Array.isArray(options.requirementIds)&&options.requirementIds.includes(target.requirement_id??target.id);
    return false;
  }
  function render(profile,options={}){
    if(!profile||!Array.isArray(profile.links))return '<section class="sl-evidence"><h3>Linked references</h3><p class="sl-small">Reference information is not available for this saved configuration.</p></section>';
    const links=profile.links.filter(link=>scoped(link,options)), draft=options.hasDraft||profile.context==='draft';
    return '<section class="sl-evidence" aria-label="Linked project references"><div class="sl-heading"><div><span class="sl-eyebrow">Supplemental project records</span><h3>Linked references</h3></div><span class="sl-count">'+links.length+' link'+(links.length===1?'':'s')+'</span></div><p class="sl-small">'+limitation+'</p>'+(draft?'<p class="sl-notice">These links describe saved R'+esc(profile.revision)+'. Draft changes have not been reviewed against these sources.</p>':'')+(links.length?'<div class="sl-reference-list">'+links.map(link=>'<article class="sl-reference"><header><strong>'+esc(link.target?.label||link.target?.id||'Recorded target')+'</strong>'+status(link.status)+'</header>'+sourceFields(link.source)+'<p class="sl-small">Linked at R'+esc(link.basis_revision)+' · source v'+esc(link.source_version)+(link.target?.run_id?' · finding run '+esc(link.target.run_id):'')+'</p>'+(link.note?'<p class="sl-preserve sl-small">Link rationale: '+esc(link.note)+'</p>':'')+(array(link.review_reasons).length?'<ul class="sl-reasons">'+link.review_reasons.map(reason=>'<li>'+esc(reason)+'</li>').join('')+'</ul>':'')+'</article>').join('')+'</div>':'<p class="sl-empty">No references are linked in this selected scope. This is a documentation gap, not a calculated pass or failure.</p>')+'<details class="sl-identity"><summary>Reference snapshot identity</summary><p>Project '+esc(profile.project_id)+' · saved R'+esc(profile.revision)+'<br>Library '+esc(profile.digest||'No digest supplied')+'</p><p>'+array(profile.limitations).map(esc).join('<br>')+'</p></details></section>';
  }
  function el(s,selector){return s.host.querySelector(selector);}
  function live(s){return !s.disposed&&mounted===s&&s.host.isConnected;}
  function checkProfile(s,value){
    if(!value||value.project_id!==s.ctx.projectId||Number(value.revision)!==Number(s.ctx.revision)||value.context!=='saved'||!Array.isArray(value.sources)||!Array.isArray(value.links)||!Array.isArray(value.targets))throw Error('Reference context changed. Reload this saved project before continuing.');
    return value;
  }
  function button(action,label,extra=''){return '<button type="button" class="sl-button" data-sl-action="'+action+'" '+extra+'>'+esc(label)+'</button>';}
  function clearEditor(s){s.editor={source_id:null,base_version:null,title:'',url:'',excerpt:'',details:''};s.editorOpen=false;}
  function controls(s){
    if(!live(s))return;
    const locked=!!s.busy||!!s.ctx.hasDraft||s.ctx.canEdit===false;
    s.host.querySelectorAll('button,input,textarea,select').forEach(node=>node.disabled=locked);
    const refresh=el(s,'[data-sl-action="refresh"]');if(refresh)refresh.disabled=!!s.busy;
    let saveReason=s.busy?'Wait for the current library operation.':s.ctx.hasDraft?'Save or discard your project draft before adding references.':s.ctx.canEdit===false?'Choose the latest saved project revision to add references.':!s.editor.title.trim()?'Add a title to continue.':!s.editor.url.trim()?'Add the source web address to continue.':!safeURL(s.editor.url)?'Use an http:// or https:// address without embedded credentials.':!s.editor.excerpt.trim()?'Paste the passage you are relying on to continue.':'';
    const save=el(s,'[data-sl-action="save-source"]');if(save){save.disabled=locked||!!saveReason;save.title=saveReason;}
    const saveHelp=el(s,'[data-sl-save-help]');if(saveHelp)saveHelp.textContent=saveReason||'Ready to save. Linking it to a project check is a separate step.';
    const linkReason=s.busy?'Wait for the current library operation.':s.ctx.hasDraft?'Save or discard the project draft before linking references.':s.ctx.canEdit===false?'Choose the latest saved revision to create a link.':!s.profile?.sources.length?'Save a reference first, then choose what it supports.':!s.link.source_id?'Choose a saved reference.':!s.link.target_id?'Choose the project check this reference supports.':'';
    const link=el(s,'[data-sl-action="link-source"]');if(link){link.disabled=locked||!!linkReason;link.title=linkReason;}
    const linkHelp=el(s,'[data-sl-link-help]');if(linkHelp)linkHelp.textContent=linkReason||'Ready to record this link. It does not change a calculated result.';
    if(s.profile)window.SixDSourceTargets.update(s.host,s.profile.targets,s.link.target_id);
    const error=el(s,'[data-sl-error]');if(error){error.textContent=s.error;error.hidden=!s.error;}
    const busy=el(s,'[data-sl-busy]');if(busy)busy.textContent=s.busy==='load'?'Loading references…':s.busy?'Saving your explicit change…':s.notice;
  }
  function sourceEditor(s){
    const item=s.editor;
    return '<details class="sl-editor" data-sl-editor'+(s.editorOpen?' open':'')+'><summary>'+ (item.source_id?'Edit saved reference':'Add a reference manually')+'</summary><section class="sl-card sl-editor-card" data-sl-source-form><div class="sl-heading"><h3>Reference details</h3>'+(item.source_id?button('new-source','Start another reference'):'')+'</div><p class="sl-small">Save a web address and the passage you actually relied on. A web address alone is not fetched or checked.</p><div class="sl-editor-meta"><label class="sl-field">Title<input maxlength="240" data-sl-field="title" value="'+esc(item.title)+'" placeholder="e.g. NASA spacecraft thermal control"></label><label class="sl-field">Web address<input type="url" maxlength="2048" data-sl-field="url" value="'+esc(item.url)+'" placeholder="https://…" spellcheck="false"></label></div><label class="sl-field">Supporting passage<textarea rows="3" maxlength="8000" data-sl-field="excerpt" placeholder="Paste the useful passage here.">'+esc(item.excerpt)+'</textarea></label><details class="sl-extra"><summary>Optional source details and limitations</summary><label class="sl-field">Author, date, section or limitations<textarea rows="2" maxlength="4000" data-sl-field="details" placeholder="Add details that help someone review this source.">'+esc(item.details)+'</textarea></label></details><div class="sl-actions">'+button('save-source',item.source_id?'Save new version':'Save reference')+'</div><p class="sl-help" data-sl-save-help role="status"></p>'+(item.source_id?'<p class="sl-small">Earlier versions stay preserved. Existing links may need review after an edit.</p>':'')+'</section></details>';
  }
  function history(source){
    const versions=array(source.history);
    if(!versions.length)return '';
    return '<details class="sl-history"><summary>Recorded source versions ('+versions.length+')</summary>'+versions.map(v=>'<article><strong>Version '+esc(v.version)+'</strong>'+sourceFields(v)+'<p class="sl-identity-text">'+esc(v.digest||'')+'</p></article>').join('')+'</details>';
  }
  function library(s){
    return '<section class="sl-card sl-saved"><div class="sl-heading"><div><span class="sl-eyebrow">Step 2</span><h3>Your saved references</h3></div><span class="sl-count">'+s.profile.sources.length+' saved</span></div>'+(s.profile.sources.length?'<div class="sl-source-list">'+s.profile.sources.map(source=>'<article class="sl-library-source"><div class="sl-heading"><div><h4>'+esc(source.title)+'</h4><div class="sl-url">'+sourceURL(source.url)+'</div></div>'+button('edit-source','Edit','data-sl-id="'+esc(source.source_id)+'"')+'</div><details class="sl-saved-passage"><summary>Read saved passage</summary><blockquote>'+esc(source.excerpt)+'</blockquote>'+(source.details?'<p class="sl-preserve sl-small">'+esc(source.details)+'</p>':'')+'</details>'+(array(source.history).length>1?history(source):'')+'</article>').join('')+'</div>':'<div class="sl-empty"><h4>No references saved yet</h4><p>Add one manually above, or use the rocket’s Find references tab and review a search result.</p></div>')+'</section>';
  }
  function links(s){
    const profile=s.profile,open=s.linksOpen===null?profile.sources.length>0:s.linksOpen;
    const linked=profile.links.length?'<div class="sl-reference-list">'+profile.links.map(link=>'<article class="sl-reference"><header><strong>'+esc(link.target?.label||link.target?.id||'Recorded target')+'</strong>'+status(link.status)+'</header>'+sourceFields(link.source)+'<p class="sl-small">Linked at R'+esc(link.basis_revision)+' · source v'+esc(link.source_version)+' · link v'+esc(link.version)+'</p>'+(link.note?'<p class="sl-preserve sl-small">Why it supports this check: '+esc(link.note)+'</p>':'')+(array(link.review_reasons).length?'<ul class="sl-reasons">'+link.review_reasons.map(r=>'<li>'+esc(r)+'</li>').join('')+'</ul>':'')+(link.status==='needs_review'&&profile.targets.some(target=>target.target_id===link.target?.target_id)?'<div class="sl-actions">'+button('confirm-link','Confirm link review','data-sl-id="'+esc(link.link_id)+'" data-sl-version="'+esc(link.version)+'"')+'</div><p class="sl-small">Confirm after reviewing the latest reference and current check. This records a link review, not engineering approval.</p>':'')+'<details class="sl-identity"><summary>Preserved link identity</summary><p>Link '+esc(link.link_id)+' · v'+esc(link.version)+'<br>'+esc(link.digest||'')+'</p>'+(link.target?.run_id?'<p>Original finding run '+esc(link.target.run_id)+'</p>':'')+'</details></article>').join('')+'</div>':'<p class="sl-empty">No project checks are linked yet. Saving a reference and linking it are separate steps.</p>';
    return '<details class="sl-link-section" data-sl-links'+(open?' open':'')+'><summary><span>Step 3 · Link a reference to your project</span><small>'+profile.links.length+' linked</small></summary><section class="sl-card"><p class="sl-small">Choose a saved reference, choose what it supports, then record the connection.</p><div class="sl-link-form"><label class="sl-field">Saved reference<select data-sl-link="source_id">'+option('','Choose a saved reference',s.link.source_id)+profile.sources.map(source=>option(source.source_id,source.title,s.link.source_id)).join('')+'</select></label>'+window.SixDSourceTargets.render(profile.targets,s.link.target_id,{primaryAttr:'data-sl-link="target_id"',advancedAttr:'data-sl-advanced-target',label:'What does it support?'})+'<label class="sl-field sl-wide">Why is this source useful?<textarea rows="2" maxlength="4000" data-sl-link="note" placeholder="Describe what the passage supports and any limits.">'+esc(s.link.note)+'</textarea></label><div class="sl-actions sl-wide">'+button('link-source','Link reference')+'</div><p class="sl-help sl-wide" data-sl-link-help role="status"></p></div><details class="sl-extra"><summary>What a link means</summary><p class="sl-small">A link captures the selected source version and exact engineering context. Later changes flag it for review. It does not validate the source or change any calculation result.</p></details></section></details><details class="sl-linked-records"'+(profile.links.length?' open':'')+'><summary>Linked references and review <small>'+profile.links.length+'</small></summary>'+linked+'</details>';
  }
  function draw(s){
    if(!live(s))return;
    s.host.innerHTML='<article class="sl-page" aria-label="Project reference library"><div class="sl-intro"><p>Keep the passages behind your project decisions, then connect them to the checks they support.</p>'+button('refresh','Refresh library')+'</div><ol class="sl-flow" aria-label="Reference workflow"><li><span>1</span>Add a reference</li><li><span>2</span>Review saved references</li><li><span>3</span>Link to a project check</li></ol>'+(s.ctx.hasDraft||s.ctx.canEdit===false?'<p class="sl-notice">'+(s.ctx.hasDraft?'Save or discard your project draft before changing references.':'This saved revision is read-only. Select the latest revision to edit references.')+'</p>':'')+'<p data-sl-busy class="sl-live" role="status" aria-live="polite"></p><p data-sl-error class="sl-error" role="alert" hidden></p>'+(s.profile?'<div class="sl-layout"><section class="sl-add"><div class="sl-heading"><div><span class="sl-eyebrow">Step 1</span><h3>Add supporting material</h3></div>'+button('open-editor','Add reference')+'</div><p class="sl-small">Use the rocket to find web references, or add a passage you already have.</p>'+sourceEditor(s)+'</section>'+library(s)+links(s)+'</div><details class="sl-identity"><summary>Scope, library identity and limitations</summary><p>'+limitation+'</p><p>Library '+esc(s.profile.digest||'No digest supplied')+'<br>Project '+esc(s.profile.project_id)+' · R'+esc(s.profile.revision)+'</p><ul>'+array(s.profile.limitations).map(value=>'<li>'+esc(value)+'</li>').join('')+'</ul></details>':'<div class="sl-empty">Loading references for this saved project…</div>')+'</article>';
    controls(s);
  }
  async function load(s){
    if(s.busy||!live(s))return;
    s.busy='load';s.error='';s.notice='';const serial=++s.serial;controls(s);
    try{
      const value=await s.ctx.api('/api/sources?project_id='+encodeURIComponent(s.ctx.projectId)+'&revision='+encodeURIComponent(s.ctx.revision));
      if(!live(s)||serial!==s.serial)return;
      s.profile=checkProfile(s,value);s.notice='Saved library loaded. References remain separate from calculation evidence.';
    }catch(error){if(live(s)&&serial===s.serial)s.error=error.message||String(error);}
    finally{if(live(s)&&serial===s.serial){s.busy='';draw(s);}}
  }
  async function mutate(s,path,payload,success){
    if(!live(s)||s.busy||s.ctx.hasDraft||s.ctx.canEdit===false)return;
    s.busy='save';s.error='';s.notice='';const serial=++s.serial;controls(s);
    try{
      const value=await s.ctx.api(path,{project_id:s.ctx.projectId,revision:s.ctx.revision,...payload});
      if(!live(s)||serial!==s.serial)return;
      s.profile=checkProfile(s,value);success?.();s.notice='Saved locally. Calculation findings are unchanged.';
      s.busy='';draw(s);s.ctx.onChange?.(copy(s.profile));
    }catch(error){if(live(s)&&serial===s.serial){s.error=error.message||String(error);s.busy='';controls(s);}}
  }
  function mount(host,ctx){
    unmount();
    const s={host,ctx,disposed:false,profile:null,busy:'',notice:'',error:'',serial:0,link:{source_id:'',target_id:'',note:''},editorOpen:false,linksOpen:null};clearEditor(s);mounted=s;
    const input=event=>{
      const target=event.target;
      if(target.dataset.slField){s.editor[target.dataset.slField]=target.value;s.error='';controls(s);}
      if(target.dataset.slLink){s.link[target.dataset.slLink]=target.value;s.error='';controls(s);}if(target.hasAttribute('data-sl-advanced-target')){s.link.target_id=target.value;s.error='';controls(s);}
    };
    const click=event=>{
      const control=event.target.closest('[data-sl-action]');if(!control||!host.contains(control))return;
      const action=control.dataset.slAction;
      if(action==='refresh'){void load(s);return;}
      if(s.busy||s.ctx.hasDraft||s.ctx.canEdit===false)return;
      if(action==='open-editor'){s.editorOpen=true;draw(s);el(s,'[data-sl-field="title"]')?.focus();return;}
      if(action==='new-source'){clearEditor(s);s.editorOpen=true;s.error='';draw(s);el(s,'[data-sl-field="title"]')?.focus();return;}
      if(action==='edit-source'){
        const source=s.profile.sources.find(item=>item.source_id===control.dataset.slId);if(!source)return;
        s.editor={source_id:source.source_id,base_version:source.version,title:source.title,url:source.url,excerpt:source.excerpt,details:source.details};s.editorOpen=true;s.error='';draw(s);el(s,'[data-sl-field="title"]')?.focus();return;
      }
      if(action==='save-source'){
        if(!s.editor.title.trim()||!s.editor.url.trim()||!s.editor.excerpt.trim())return;
        if(!safeURL(s.editor.url)){s.error='Use an http:// or https:// source URL without embedded credentials.';controls(s);return;}
        void mutate(s,'/api/sources',{source:copy(s.editor)},()=>clearEditor(s));return;
      }
      if(action==='link-source'){
        const source=s.profile.sources.find(item=>item.source_id===s.link.source_id);if(!source||!s.link.target_id)return;
        void mutate(s,'/api/source-links',{expected_digest:s.profile.digest,spec:{source_id:source.source_id,source_version:source.version,target_id:s.link.target_id,note:s.link.note}},()=>{s.link={source_id:'',target_id:'',note:''};});return;
      }
      if(action==='confirm-link')void mutate(s,'/api/source-links/confirm',{link_id:control.dataset.slId,base_version:Number(control.dataset.slVersion),expected_digest:s.profile.digest});
    };
    const toggle=event=>{if(event.target.hasAttribute('data-sl-editor'))s.editorOpen=event.target.open;if(event.target.hasAttribute('data-sl-links'))s.linksOpen=event.target.open;};
    host.addEventListener('input',input);host.addEventListener('change',input);host.addEventListener('click',click);host.addEventListener('toggle',toggle,true);
    s.dispose=()=>{if(s.disposed)return;s.disposed=true;s.serial++;host.removeEventListener('input',input);host.removeEventListener('change',input);host.removeEventListener('click',click);host.removeEventListener('toggle',toggle,true);if(mounted===s)mounted=null;};
    draw(s);void load(s);return s.dispose;
  }
  function unmount(){mounted?.dispose();}
  function prefill(source,targetId){
    const s=mounted;if(!s||!live(s)||s.busy||!s.profile||s.ctx.hasDraft||s.ctx.canEdit===false)return false;
    const limits={title:240,url:2048,excerpt:8000,details:4000};
    if(!source||Object.entries(limits).some(([key,max])=>typeof source[key]!=='string'||source[key].length>max)||!safeURL(source.url))return false;
    clearEditor(s);s.editorOpen=true;for(const key of Object.keys(limits))s.editor[key]=source[key];
    if(targetId&&s.profile.targets.some(target=>target.target_id===targetId))s.link.target_id=targetId;
    s.notice='Research preview copied into this unsaved form. Review the excerpt, save the reference, then add its explicit link.';s.error='';draw(s);
    el(s,'[data-sl-field="title"]')?.focus();return true;
  }
  window.SixDSources=Object.freeze({mount,unmount,render,prefill});
})();

