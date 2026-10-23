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
  function clearEditor(s){s.editor={source_id:null,base_version:null,title:'',url:'',excerpt:'',details:''};}
  function controls(s){
    if(!live(s))return;
    s.host.querySelectorAll('button,input,textarea,select').forEach(node=>node.disabled=!!s.busy||!!s.ctx.hasDraft||s.ctx.canEdit===false);
    const refresh=el(s,'[data-sl-action="refresh"]');if(refresh)refresh.disabled=!!s.busy;
    const edit=el(s,'[data-sl-source-form]');if(edit)edit.querySelector('[data-sl-action="save-source"]').disabled=!!s.busy||!!s.ctx.hasDraft||s.ctx.canEdit===false||!s.editor.title.trim()||!s.editor.url.trim()||!s.editor.excerpt.trim();
    const link=el(s,'[data-sl-action="link-source"]');if(link)link.disabled=!!s.busy||!!s.ctx.hasDraft||s.ctx.canEdit===false||!s.link.source_id||!s.link.target_id;
    const error=el(s,'[data-sl-error]');if(error){error.textContent=s.error;error.hidden=!s.error;}
    const busy=el(s,'[data-sl-busy]');if(busy)busy.textContent=s.busy==='load'?'Loading source records…':s.busy?'Saving an explicit library change…':s.notice;
  }
  function sourceEditor(s){
    const item=s.editor;
    return '<section class="sl-card" data-sl-source-form><div class="sl-heading"><h3>'+(item.source_id?'Edit source · v'+esc(item.base_version):'Add a reference')+'</h3>'+(item.source_id?button('new-source','New reference'):'')+'</div><p class="sl-small">Record the reference and the passage you are relying on. URLs are stored; 6D does not fetch them.</p><label class="sl-field">Title<input maxlength="240" data-sl-field="title" value="'+esc(item.title)+'" placeholder="e.g. NASA spacecraft thermal control"></label><label class="sl-field">Source URL<input type="url" maxlength="2048" data-sl-field="url" value="'+esc(item.url)+'" placeholder="https://…" spellcheck="false"></label><label class="sl-field">Relevant excerpt<textarea rows="4" maxlength="8000" data-sl-field="excerpt" placeholder="Paste the passage supporting this rationale.">'+esc(item.excerpt)+'</textarea></label><label class="sl-field">Source details and limitations<textarea rows="3" maxlength="4000" data-sl-field="details" placeholder="Author, publication date, section, access date or limitations.">'+esc(item.details)+'</textarea></label><div class="sl-actions">'+button('save-source',item.source_id?'Save new source version':'Save reference')+'</div><p class="sl-small">'+(item.source_id?'Earlier versions and their links stay preserved. Editing creates a new version; existing links may need review.':'Reference content is supplied by you; source authenticity and applicability are not established.')+'</p></section>';
  }
  function history(source){
    const versions=array(source.history);
    if(!versions.length)return '';
    return '<details class="sl-history"><summary>Recorded source versions ('+versions.length+')</summary>'+versions.map(v=>'<article><strong>Version '+esc(v.version)+'</strong>'+sourceFields(v)+'<p class="sl-identity-text">'+esc(v.digest||'')+'</p></article>').join('')+'</details>';
  }
  function library(s){
    return '<section class="sl-card"><div class="sl-heading"><h3>Project references</h3><span class="sl-count">'+s.profile.sources.length+'</span></div>'+(s.profile.sources.length?'<div class="sl-source-list">'+s.profile.sources.map(source=>'<article class="sl-library-source">'+sourceFields(source)+'<div class="sl-actions">'+button('edit-source','Edit reference','data-sl-id="'+esc(source.source_id)+'"')+'</div>'+history(source)+'</article>').join('')+'</div>':'<div class="sl-empty"><h4>No references yet</h4><p>Add a reference, then link it to a requirement, a model assumption or a saved finding.</p></div>')+'</section>';
  }
  function links(s){
    const profile=s.profile;
    return '<section class="sl-card sl-wide"><div class="sl-heading"><h3>Connect a reference to the engineering record</h3><span class="sl-count">Explicit links</span></div><div class="sl-link-form"><label class="sl-field">Reference<select data-sl-link="source_id">'+option('','Choose a source',s.link.source_id)+profile.sources.map(source=>option(source.source_id,source.title+' · v'+source.version,s.link.source_id)).join('')+'</select></label><label class="sl-field">Engineering target<select data-sl-link="target_id">'+option('','Choose a requirement, assumption or finding',s.link.target_id)+profile.targets.map(target=>option(target.target_id,target.label,s.link.target_id)).join('')+'</select></label><label class="sl-field sl-wide">Why this reference belongs here<textarea rows="2" maxlength="4000" data-sl-link="note" placeholder="Describe what this passage supports and its limits.">'+esc(s.link.note)+'</textarea></label><div class="sl-actions sl-wide">'+button('link-source','Add explicit link')+'</div></div><p class="sl-small">A link captures the selected source version and engineering context. Later changes flag the link for review.</p></section><section class="sl-card sl-wide"><div class="sl-heading"><h3>Linked context and review</h3><span class="sl-count">'+profile.links.length+' links</span></div>'+(profile.links.length?'<div class="sl-reference-list">'+profile.links.map(link=>'<article class="sl-reference"><header><strong>'+esc(link.target?.label||link.target?.id||'Recorded target')+'</strong>'+status(link.status)+'</header>'+sourceFields(link.source)+'<p class="sl-small">Linked at R'+esc(link.basis_revision)+' · source v'+esc(link.source_version)+' · link v'+esc(link.version)+'</p>'+(link.note?'<p class="sl-preserve sl-small">Link rationale: '+esc(link.note)+'</p>':'')+(array(link.review_reasons).length?'<ul class="sl-reasons">'+link.review_reasons.map(r=>'<li>'+esc(r)+'</li>').join('')+'</ul>':'')+(link.status==='needs_review'&&profile.targets.some(target=>target.target_id===link.target?.target_id)?'<div class="sl-actions">'+button('confirm-link','Confirm link review','data-sl-id="'+esc(link.link_id)+'" data-sl-version="'+esc(link.version)+'"')+'</div><p class="sl-small">Confirm only after checking the latest reference and current target. This records your link review, not engineering approval.</p>':'')+'<details class="sl-identity"><summary>Preserved link identity</summary><p>Link '+esc(link.link_id)+' · v'+esc(link.version)+'<br>'+esc(link.digest||'')+'</p>'+(link.target?.run_id?'<p>Original finding run '+esc(link.target.run_id)+'</p>':'')+'</details></article>').join('')+'</div>':'<p class="sl-empty">No links have been supplied. Adding a reference alone does not assign it to an engineering claim.</p>')+'</section>';
  }
  function draw(s){
    if(!live(s))return;
    s.host.innerHTML='<article class="sl-page"><header class="sl-page-header"><div><span class="sl-eyebrow">Project source library · saved R'+esc(s.ctx.revision)+'</span><h2>Keep the reasoning connected.</h2><p>Store the references behind requirements, model assumptions and saved findings.</p></div>'+button('refresh','Refresh library')+'</header><p class="sl-notice">'+(s.ctx.hasDraft?'Save or discard the draft before changing library records. Displayed links still belong to the saved configuration.':s.ctx.canEdit===false?'This historical revision is read-only. Select the latest saved revision to add or review source links.':limitation)+'</p><p data-sl-busy class="sl-live" role="status" aria-live="polite"></p><p data-sl-error class="sl-error" role="alert" hidden></p>'+(s.profile?'<div class="sl-layout">'+sourceEditor(s)+library(s)+links(s)+'</div><details class="sl-identity"><summary>Library snapshot and limitations</summary><p>Library '+esc(s.profile.digest||'No digest supplied')+'<br>Project '+esc(s.profile.project_id)+' · R'+esc(s.profile.revision)+'</p><ul>'+array(s.profile.limitations).map(value=>'<li>'+esc(value)+'</li>').join('')+'</ul></details>':'<div class="sl-empty">Loading references for this saved project…</div>')+'</article>';
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
    const s={host,ctx,disposed:false,profile:null,busy:'',notice:'',error:'',serial:0,link:{source_id:'',target_id:'',note:''}};clearEditor(s);mounted=s;
    const input=event=>{
      const target=event.target;
      if(target.dataset.slField){s.editor[target.dataset.slField]=target.value;s.error='';controls(s);}
      if(target.dataset.slLink){s.link[target.dataset.slLink]=target.value;s.error='';controls(s);}
    };
    const click=event=>{
      const control=event.target.closest('[data-sl-action]');if(!control||!host.contains(control))return;
      const action=control.dataset.slAction;
      if(action==='refresh'){void load(s);return;}
      if(s.busy||s.ctx.hasDraft||s.ctx.canEdit===false)return;
      if(action==='new-source'){clearEditor(s);s.error='';draw(s);el(s,'[data-sl-field="title"]')?.focus();return;}
      if(action==='edit-source'){
        const source=s.profile.sources.find(item=>item.source_id===control.dataset.slId);if(!source)return;
        s.editor={source_id:source.source_id,base_version:source.version,title:source.title,url:source.url,excerpt:source.excerpt,details:source.details};s.error='';draw(s);el(s,'[data-sl-field="title"]')?.focus();return;
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
    host.addEventListener('input',input);host.addEventListener('change',input);host.addEventListener('click',click);
    s.dispose=()=>{if(s.disposed)return;s.disposed=true;s.serial++;host.removeEventListener('input',input);host.removeEventListener('change',input);host.removeEventListener('click',click);if(mounted===s)mounted=null;};
    draw(s);void load(s);return s.dispose;
  }
  function unmount(){mounted?.dispose();}
  function prefill(source,targetId){
    const s=mounted;if(!s||!live(s)||s.busy||!s.profile||s.ctx.hasDraft||s.ctx.canEdit===false)return false;
    const limits={title:240,url:2048,excerpt:8000,details:4000};
    if(!source||Object.entries(limits).some(([key,max])=>typeof source[key]!=='string'||source[key].length>max)||!safeURL(source.url))return false;
    clearEditor(s);for(const key of Object.keys(limits))s.editor[key]=source[key];
    if(targetId&&s.profile.targets.some(target=>target.target_id===targetId))s.link.target_id=targetId;
    s.notice='Research preview copied into this unsaved form. Review the excerpt, save the reference, then add its explicit link.';s.error='';draw(s);
    el(s,'[data-sl-field="title"]')?.focus();return true;
  }
  window.SixDSources=Object.freeze({mount,unmount,render,prefill});
})();

