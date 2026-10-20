/* Explicit project topology and scalar interface contracts. No inferred physics. */
(() => {
  'use strict';
  let mounted=null;
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const copy=value=>JSON.parse(JSON.stringify(value));
  const arr=value=>Array.isArray(value)?value:[];
  const own=(object,key)=>Object.prototype.hasOwnProperty.call(object||{},key);
  const safe=id=>typeof id==='string'&&/^[A-Za-z][A-Za-z0-9_-]{0,79}$/.test(id)&&!['__proto__','prototype','constructor'].includes(id);
  const human=value=>String(value||'').replace(/_/g,' ');
  const option=(value,title,selected)=>'<option value="'+esc(value)+'" '+(value===selected?'selected':'')+'>'+esc(title)+'</option>';
  const button=(action,text,disabled=false,extra='')=>'<button type="button" class="sd-button" data-sys="'+esc(action)+'" '+(disabled?'disabled ':'')+extra+'>'+esc(text)+'</button>';
  const badge=status=>'<span class="sy-badge sy-'+(['met','not_met','not_assessed'].includes(status)?status:'not_assessed')+'">'+esc({met:'Meets interface criterion',not_met:'Does not meet interface criterion',not_assessed:'Not assessed'}[status]||'Not assessed')+'</span>';
  function measure(record){
    if(!record||typeof record.value!=='number'||!Number.isFinite(record.value))return 'No numeric evidence';
    if(Number.isInteger(record.value)&&!Number.isSafeInteger(record.value))return 'Exact value withheld in browser; inspect source JSON precision';
    return esc(String(record.value)+' '+record.unit);
  }
  const list=items=>'<ul>'+arr(items).map(item=>'<li>'+esc(typeof item==='string'?item:item.message||item.code||'Unspecified issue')+'</li>').join('')+'</ul>';
  function identities(profile){
    return '<details class="sy-provenance"><summary>Interface evidence identity and limits</summary><dl>'+[
      ['Project / revision',profile.project_id+' / R'+profile.revision],['Context',profile.context],['Project digest',profile.project_digest],
      ['Saved run',profile.run_id||'No current saved run'],['Saved review',profile.review_digest||'No current saved review'],['Interface projection digest',profile.digest]
    ].map(([name,value])=>'<dt>'+esc(name)+'</dt><dd>'+esc(value)+'</dd>').join('')+'</dl>'+
      (Object.keys(profile.sources||{}).length?'<h4>Source versions</h4><dl>'+Object.entries(profile.sources).map(([name,value])=>'<dt>'+esc(name)+'</dt><dd>'+esc(value)+'</dd>').join('')+'</dl>':'')+list(profile.checks?.limitations)+
      '<p>These unsigned local digests identify recorded evidence. Interface results do not establish whole-system validity or launch readiness.</p></details>';
  }
  function report(profile,options={}){
    if(!profile||profile.schema!=='sixd.system-interfaces.v1')return '<section class="sy-evidence"><h3>Interface checks</h3><p>Interface evidence is not available for this configuration.</p></section>';
    const allRows=arr(profile.checks?.rows),rows=allRows.filter(row=>(!options.systemId||row.from_system===options.systemId||row.to_system===options.systemId)&&(!Array.isArray(options.modelIds)||options.modelIds.includes(row.source?.model_id))),draft=profile.context==='draft';
    const scoped=!!options.scopeLabel||!!options.systemId||Array.isArray(options.modelIds),total=Number.isInteger(options.scopeTotal)?options.scopeTotal:allRows.length;
    return '<section class="sy-evidence" aria-label="System interface checks"><div class="sy-heading"><div><span class="sy-eyebrow">Explicit system connections</span><h3>Interface checks</h3></div><span class="sd-chip">'+(draft?'Draft · no numeric verdict':rows.length+' declared interface'+(rows.length===1?'':'s'))+'</span></div>'+
      '<p class="sy-scope">Each contract compares its source scalar with an explicitly declared destination input in the same exact unit. Values are never converted, copied into another model, summed or physically coupled automatically. These findings remain separate from requirement findings.</p>'+
      (scoped?'<p class="sy-small">'+esc(options.scopeLabel||'Selected scope')+': '+rows.length+' of '+total+' project interface contracts. Other interfaces are outside this view. The projection identity below identifies the full source projection.</p>':'')+(draft?'<div class="sd-notice">This is a topology and dependency preview. Save the revision and run checks to assess its interface criteria. Recorded numbers are not draft predictions.</div>':'')+
      (rows.length?'<div class="sy-checks">'+rows.map(row=>'<article class="sy-check" data-interface-check="'+esc(row.id)+'"><header><div><h4>'+esc(row.title||row.id)+'</h4><span class="sy-small">'+esc(row.id)+' · '+(row.critical?'Critical':'Noncritical')+'</span></div>'+badge(draft?'not_assessed':row.status)+'</header><p>'+esc(row.from_system)+' <span aria-label="to">→</span> '+esc(row.to_system)+' · '+esc(row.quantity)+'</p>'+
        '<div class="sy-values"><section><span>'+(row.source_kind==='model_metric'||row.source?.kind==='model_metric'?'Saved calculation':'Declared source input')+'</span><strong>'+(draft?'Not assessed in draft':measure(row.source_value))+'</strong><small>'+esc(row.source?.kind==='model_metric'?row.source.model_id+' / '+row.source.metric:row.source?.input_id)+'</small></section><section><span>Destination criterion '+esc(row.operator)+'</span><strong>'+(draft?'Not assessed in draft':measure(row.target_value))+'</strong><small>'+esc(row.target_input)+' · declared unit '+esc(row.unit)+'</small></section></div>'+
        '<p>'+esc(draft?'No draft numerical verdict has been calculated.':row.reason||'No assessment reason recorded.')+'</p>'+list(row.issues)+(row.description?'<p class="sy-small">Context: '+esc(row.description)+'</p>':'')+
        '<details><summary>Declared dependencies and source</summary><p>Input records: '+esc(arr(row.dependency_input_ids).join(', ')||'None recorded')+'</p><p>'+esc(row.source_origin?.kind==='reviewed_model_metric'?'Saved calculation · '+row.source_origin.model_id+' / '+row.source_origin.metric:row.source_origin?.kind==='declared_input'?'Declared input · '+row.source_origin.input_id+' · '+row.source_origin.source:'No assessed source provenance')+'</p>'+(row.source_origin?.review_digest?'<p class="sy-identity">Source review '+esc(row.source_origin.review_digest)+'<br>Evidence fingerprint '+esc(row.source_origin.evidence_fingerprint)+'</p>':'')+'</details></article>').join('')+'</div>':'<div class="sy-empty"><h4>'+(scoped?'No interfaces in this selected scope':'No interfaces declared')+'</h4><p>'+(scoped?'No contracts match this selection; '+total+' interface contracts exist in the full project.':'This project has no explicit system interface contracts.')+' Absence of coverage is not a passing result.</p></div>')+identities(profile)+'</section>';
  }
  function impact(profile){
    if(!profile?.impact)return '<section class="sy-impact"><h3>System interface impact</h3><p>No interface change comparison is available.</p></section>';
    const value=profile.impact,groups=[['Systems added','added_systems'],['Systems removed','removed_systems'],['Systems changed','changed_systems'],['Interfaces added','added_interfaces'],['Interfaces removed','removed_interfaces'],['Interfaces changed','changed_interfaces'],['Interfaces to review','affected_interface_ids'],['Connected systems to review','interface_review_system_ids'],['Connected models to review','interface_review_model_ids'],['Connected requirements to review','interface_review_requirement_ids']];
    return '<section class="sy-impact"><h3>System interface impact</h3><p>Declared dependency reachability identifies records to review. It does not predict a physical effect, recalculate an observation, or change canonical requirement findings.</p><dl>'+groups.map(([label,key])=>'<dt>'+esc(label)+'</dt><dd>'+esc(arr(value[key]).map(item=>typeof item==='string'?item:item.id||item.interface_id||item.system_id||'Unspecified').join(', ')||'None')+'</dd>').join('')+'</dl>'+list(value.reasons)+'</section>';
  }
  function unmount(){if(mounted){mounted.closed=true;mounted.controller?.abort();mounted.host.replaceChildren();mounted=null;}}
  function mount(host,ctx){
    unmount();
    const state={host,ctx,closed:false,editor:null,error:'',profile:null,loading:true,catalog:null,catalogError:'',request:0,selected:null,controller:null};mounted=state;
    const live=()=>mounted===state&&!state.closed&&host.isConnected;
    const project=()=>ctx.project;
    const systems=()=>arr(project().systems);
    const interfaces=()=>arr(project().interfaces);
    const models=()=>arr(project().models);
    const system=id=>systems().find(item=>item.id===id);
    const model=id=>models().find(item=>item.id===id);
    const catalogModel=id=>state.catalog?.models?.find(item=>item.type===model(id)?.type);
    const ownedIds=id=>arr(system(id)?.model_ids);
    const systemInputs=id=>new Set(ownedIds(id).flatMap(modelId=>[
      ...Object.values(model(modelId)?.inputs||{}),...arr(project().requirements).filter(r=>r.model_id===modelId).map(r=>r.limit_input)
    ]));
    const exposedModels=id=>[...descendants(id)].flatMap(systemId=>ownedIds(systemId));
    const inputChoices=id=>{const suggested=new Set([...descendants(id)].flatMap(systemId=>[...systemInputs(systemId)]));return Object.entries(project().inputs||{}).map(([key,value])=>[key,key+' / '+value.unit+(suggested.has(key)?' · bound in this system tree':' · explicitly supplied record')]);};
    const editable=()=>!!ctx.hasDraft&&ctx.isLatest!==false;
    const field=(title,name,value='',attributes='')=>'<label class="sd-field">'+esc(title)+'<input class="sd-input" name="'+name+'" value="'+esc(value)+'" '+attributes+'></label>';
    const select=(title,name,options,selected,placeholder='Choose explicitly')=>'<label class="sd-field">'+esc(title)+'<select class="sd-input" name="'+name+'" required>'+option('',placeholder,selected)+options.map(([value,label])=>option(value,label,selected)).join('')+'</select></label>';
    const text=(title,name,value='',maxlength=4096)=>'<label class="sd-field">'+esc(title)+'<textarea class="sd-input" name="'+name+'" rows="3" maxlength="'+maxlength+'">'+esc(value)+'</textarea></label>';
    function descendants(id){const result=new Set([id]);for(let changed=true;changed;){changed=false;for(const item of systems())if(result.has(item.parent_id)&&!result.has(item.id)){result.add(item.id);changed=true;}}return result;}
    function tree(){
      const rendered=new Set();
      function node(item,depth){if(rendered.has(item.id))return '';rendered.add(item.id);const assigned=arr(item.model_ids),out=interfaces().filter(i=>i.from_system===item.id),incoming=interfaces().filter(i=>i.to_system===item.id);
        return '<li><article class="sy-system '+(state.selected===item.id?'sy-selected':'')+'" data-system-card="'+esc(item.id)+'"><div class="sy-heading"><div><span class="sy-small">'+esc(item.id)+'</span><h3>'+esc(item.title)+'</h3></div><span class="sd-chip">'+assigned.length+' model'+(assigned.length===1?'':'s')+'</span></div>'+(item.description?'<p>'+esc(item.description)+'</p>':'')+'<div class="sy-models">'+(assigned.map(id=>'<span>'+esc(id)+'</span>').join('')||'<span>No models assigned</span>')+'</div><p class="sy-small">'+incoming.length+' incoming · '+out.length+' outgoing declared interface'+(incoming.length+out.length===1?'':'s')+'</p><div class="sy-actions sy-no-print">'+button('inspect:'+item.id,'Inspect system')+button('edit-system:'+item.id,'Edit',!editable())+button('remove-system:'+item.id,'Remove',!editable())+'</div></article>'+(depth<64?children(item.id,depth+1):'')+'</li>';
      }
      function children(parent,depth){const rows=systems().filter(item=>item.parent_id===parent);return rows.length?'<ul class="sy-tree">'+rows.map(item=>node(item,depth)).join('')+'</ul>':'';}
      let html=children(null,0);const orphan=systems().filter(item=>!rendered.has(item.id));if(orphan.length)html+='<p class="sd-notice">Some imported hierarchy records have missing parents or cycles. Repair their definitions before relying on topology.</p><ul class="sy-tree">'+orphan.map(item=>node(item,0)).join('')+'</ul>';
      return html||'<div class="sy-empty"><h3>Build the project’s actual system structure</h3><p>No explicit systems have been declared. Add a system and assign its maintained models. Existing discipline groups remain available elsewhere in the workspace.</p></div>';
    }
    function editor(){
      const e=state.editor;if(!e)return '';const values=e.values,old=e.id;
      let body=field('Stable ID','id',values.id||'','required maxlength="'+(old?'4096':'80')+'" '+(old?'readonly':''))+field('Title','title',values.title||'','required maxlength="4096"')+text('Engineering context and assumptions','description',values.description||'');
      if(e.kind==='system'){
        const forbidden=old?descendants(old):new Set();
        body+='<label class="sd-field">Parent system<select class="sd-input" name="parent_id">'+option('','Top level',values.parent_id||'')+systems().filter(item=>!forbidden.has(item.id)).map(item=>option(item.id,item.title+' / '+item.id,values.parent_id)).join('')+'</select></label><fieldset class="sy-assignment"><legend>Direct model ownership</legend><p class="sy-small">A model belongs directly to at most one system. A parent may expose a child’s model output through an explicit interface.</p>'+(models().map(item=>{const owner=systems().find(s=>s.id!==old&&arr(s.model_ids).includes(item.id)),checked=arr(values.model_ids).includes(item.id);return '<label><input type="checkbox" name="model_ids" value="'+esc(item.id)+'" '+(checked?'checked ':'')+(owner?'disabled':'')+'>'+esc(item.id)+(owner?' <small>Owned by '+esc(owner.title)+'</small>':'')+'</label>';}).join('')||'<p>No model definitions are available. Add them through Project setup.</p>')+'</fieldset>';
      }else{
        const endpoints=systems().map(item=>[item.id,item.title+' / '+item.id]),source=values.source||{},from=values.from_system,to=values.to_system;
        body+='<div class="sy-form-grid">'+select('Source system','from_system',endpoints.filter(([id])=>id!==to),from)+select('Destination system','to_system',endpoints.filter(([id])=>id!==from),to)+select('Source value kind','source_kind',[['input','Declared input'],['model_metric','Saved model metric']],source.kind)+'</div>';
        if(source.kind==='model_metric'){
          const metrics=arr(catalogModel(source.model_id)?.metrics).map(item=>[item.name,item.label+' / '+item.unit]);
          if(source.metric&&!metrics.some(([id])=>id===source.metric))metrics.push([source.metric,source.metric+' / recorded metric not in maintained catalog']);
          body+='<div class="sy-form-grid">'+select('Source model in system tree','model_id',exposedModels(from).map(id=>[id,id]),source.model_id)+select('Source metric','metric',metrics,source.metric)+'</div>'+(state.catalogError?'<p class="sd-notice">'+esc(state.catalogError)+'</p>':'');
        }
        else if(source.kind==='input')body+=select('Source input','input_id',inputChoices(from),source.input_id);
        body+='<div class="sy-form-grid">'+select('Destination input criterion','target_input',inputChoices(to),values.target_input)+field('Quantity name','quantity',values.quantity||'','required maxlength="4096"')+field('Exact declared unit','unit',values.unit||'','required maxlength="4096"')+select('Source compared with destination','operator',[['<=','≤ (less than or equal)'],['>=','≥ (greater than or equal)'],['==','= (exact scalar equality)']],values.operator)+select('Critical interface','critical',[['true','Yes'],['false','No']],values.critical===undefined?'':String(values.critical))+'</div><p class="sy-small">Both scalar records must use this exact unit. Equality has no hidden tolerance. Input association with each system is your explicit declaration; review its source before use. A declared input is supplied data, not a calculated output. No automatic source-to-target solver feeding occurs.</p>';
      }
      return '<section class="sy-editor sy-no-print"><h3>'+(old?'Edit':'Add')+' '+e.kind+'</h3><form data-sys-form>'+body+'<div class="sy-actions"><button class="sd-button sd-primary" type="submit">Apply to shared draft</button>'+button('cancel','Cancel')+'</div></form></section>';
    }
    function inspector(){
      const item=system(state.selected);if(!item)return '';
      const rows=interfaces().filter(i=>i.from_system===item.id||i.to_system===item.id);
      return '<aside class="sy-inspector"><div class="sy-heading"><h3>'+esc(item.title)+'</h3>'+button('close-inspector','Close')+'</div><p>Parent: '+esc(system(item.parent_id)?.title||'Top level')+'</p><h4>Declared connections</h4>'+(rows.length?rows.map(i=>'<div class="sy-connection"><strong>'+esc(i.title)+'</strong><span>'+esc(system(i.from_system)?.title||i.from_system)+' → '+esc(system(i.to_system)?.title||i.to_system)+'</span><small>'+esc(i.quantity)+' / '+esc(i.unit)+' · '+esc(i.operator)+'</small></div>').join(''):'<p>No declared connections for this system.</p>')+(ctx.onSelectSystem?'<div class="sy-no-print">'+button('open-system:'+item.id,'Open system in workspace')+'</div>':'')+'</aside>';
    }
    function render(){
      if(!live())return;
      const assigned=new Set(systems().flatMap(item=>arr(item.model_ids))),unassigned=models().filter(item=>!assigned.has(item.id));
      host.innerHTML='<article class="sy-workspace"><header class="sy-page-heading"><div><span class="sy-eyebrow">Project architecture · R'+esc(ctx.revision)+'</span><h2>Systems & interfaces</h2><p>Organize the actual project and declare the scalar contracts between its systems.</p></div><span class="sd-chip">'+(ctx.hasDraft?'Shared draft':'Saved configuration')+'</span></header><div class="sy-actions sy-no-print">'+(ctx.hasDraft?button('save','Save shared revision',ctx.isLatest===false):button('draft','Edit in shared draft',ctx.isLatest===false))+button('add-system','Add system',!editable()||systems().length>=64)+button('add-interface','Add interface',!editable()||systems().length<2||interfaces().length>=128)+button('refresh','Refresh evidence',state.loading)+(ctx.onRun?button('run','Run saved checks',!!ctx.hasDraft):'')+'</div>'+(ctx.isLatest===false?'<p class="sd-notice">Historical revisions are read-only. Select the latest revision to author systems and interfaces.</p>':'')+(state.error?'<div class="sy-error" role="alert">'+esc(state.error)+'</div>':'')+editor()+'<div class="sy-architecture"><section><h3>System hierarchy</h3><p class="sy-small">Containment describes organization. Connections below declare engineering interfaces; neither implies physical simulation coupling.</p>'+tree()+'</section>'+inspector()+'</div><section class="sy-unassigned"><h3>Unassigned models</h3><p class="sy-small">Unassigned models remain in the project and keep their existing requirement evidence.</p>'+(unassigned.length?'<div class="sy-models">'+unassigned.map(item=>'<span>'+esc(item.id)+'</span>').join('')+'</div>':'<p>Every model has an explicit system owner.</p>')+'</section><section class="sy-interface-list"><h3>Declared interfaces</h3>'+(interfaces().length?interfaces().map(i=>'<article class="sy-interface" data-interface-definition="'+esc(i.id)+'"><div><h4>'+esc(i.title)+'</h4><p>'+esc(system(i.from_system)?.title||i.from_system)+' → '+esc(system(i.to_system)?.title||i.to_system)+'</p><p class="sy-small">'+esc(i.quantity)+' · '+esc(i.unit)+' · '+esc(i.operator)+' · '+(i.critical?'Critical':'Noncritical')+'</p></div><div class="sy-actions sy-no-print">'+button('edit-interface:'+i.id,'Edit',!editable())+button('remove-interface:'+i.id,'Remove',!editable())+'</div></article>').join(''):'<p>No interfaces have been declared. Add source and destination systems first.</p>')+'</section><div aria-live="polite">'+(state.loading?'<p class="sy-loading">Loading interface evidence for this exact configuration…</p>':state.profile?report(state.profile)+impact(state.profile):'<p class="sd-notice">Interface evidence is unavailable. Refresh to retry.</p>')+'</div></article>';
    }
    function readEditor(){
      if(!state.editor)return;const form=host.querySelector('[data-sys-form]');if(!form)return;
      const data=new FormData(form),e=state.editor,old=e.values;
      e.values={id:data.get('id')||'',title:data.get('title')||'',description:data.get('description')||''};
      if(e.kind==='system'){e.values.parent_id=data.get('parent_id')||null;e.values.model_ids=data.getAll('model_ids');}
      else e.values={...e.values,from_system:data.get('from_system')||'',to_system:data.get('to_system')||'',source:{kind:data.get('source_kind')||'',...(data.get('source_kind')==='model_metric'?{model_id:data.get('model_id')||'',metric:data.get('metric')||''}:{input_id:data.get('input_id')||''})},target_input:data.get('target_input')||'',quantity:data.get('quantity')||'',unit:data.get('unit')||'',operator:data.get('operator')||'',critical:data.get('critical')===''||data.get('critical')===null?undefined:data.get('critical')==='true'};
      return old;
    }
    function validate(candidate){
      const items=arr(candidate.systems),contracts=arr(candidate.interfaces),byId=new Map(items.map(item=>[item.id,item]));
      if(items.length>64||contracts.length>128)throw Error('A project supports at most 64 systems and 128 interfaces.');
      if(byId.size!==items.length||new Set(contracts.map(i=>i.id)).size!==contracts.length)throw Error('System and interface IDs must be unique within their collection.');
      const owners=new Map();
      for(const item of items){
        if(typeof item.id!=='string'||!item.id.trim()||item.id.length>4096||['__proto__','prototype','constructor'].includes(item.id)||!item.title.trim())throw Error('Enter a nonempty identifier and title; reserved prototype names cannot be used as identifiers.');
        if(item.parent_id!==null&&!byId.has(item.parent_id))throw Error('Choose an existing parent system.');
        const seen=new Set([item.id]);let cursor=item.parent_id;while(cursor!==null){if(seen.has(cursor))throw Error('System containment cannot contain a cycle.');seen.add(cursor);cursor=byId.get(cursor)?.parent_id??null;}
        for(const modelId of item.model_ids){if(!models().some(m=>m.id===modelId))throw Error('A system references a missing model.');if(owners.has(modelId))throw Error('A model can belong to only one system.');owners.set(modelId,item.id);}
      }
      const subtreeModels=id=>{const nodes=new Set([id]);for(let changed=true;changed;){changed=false;for(const s of items)if(nodes.has(s.parent_id)&&!nodes.has(s.id)){nodes.add(s.id);changed=true;}}return new Set([...nodes].flatMap(key=>arr(byId.get(key)?.model_ids)));};
      for(const item of contracts){
        if(typeof item.id!=='string'||!item.id.trim()||item.id.length>4096||['__proto__','prototype','constructor'].includes(item.id)||!item.title.trim()||!item.quantity.trim()||!item.unit.trim()||!['<=','>=','=='].includes(item.operator)||typeof item.critical!=='boolean')throw Error('Enter the interface ID, title, quantity, exact unit, operator and explicit criticality.');
        if(!byId.has(item.from_system)||!byId.has(item.to_system)||item.from_system===item.to_system)throw Error('Choose two different existing systems.');
        if(!own(candidate.inputs,item.target_input))throw Error('Choose an explicitly supplied destination input.');
        if(item.source?.kind==='input'){if(!own(candidate.inputs,item.source.input_id))throw Error('Choose an explicitly supplied source input.');}
        else if(item.source?.kind==='model_metric'){if(!subtreeModels(item.from_system).has(item.source.model_id))throw Error('The source model must belong to the source system or one of its descendants.');if(typeof item.source.metric!=='string'||!item.source.metric.trim())throw Error('Choose an explicit source metric.');}
        else throw Error('Choose an explicit source kind.');
      }
    }
    async function apply(candidate){if(!editable())throw Error('Start a shared draft on the latest revision before editing.');validate(candidate);await ctx.onChange(candidate);state.editor=null;}
    async function refresh(){
      const serial=++state.request,snapshot=JSON.stringify(ctx.project),projectId=ctx.projectId,revision=ctx.revision;
      state.controller?.abort();state.controller=new AbortController();state.loading=true;state.profile=null;state.error='';render();
      try{const profile=await ctx.api(ctx.hasDraft?'/api/interfaces/preview':'/api/interfaces?project_id='+encodeURIComponent(projectId)+'&revision='+encodeURIComponent(revision),ctx.hasDraft?{project_id:projectId,base_revision:revision,project:copy(ctx.project)}:undefined,{signal:state.controller.signal});
        if(!live()||serial!==state.request||snapshot!==JSON.stringify(ctx.project))return;
        if(profile.schema!=='sixd.system-interfaces.v1'||profile.project_id!==projectId||profile.revision!==revision||profile.context!==(ctx.hasDraft?'draft':'saved'))throw Error('Interface evidence belongs to a different configuration. Reload the project.');state.profile=profile;
      }catch(error){if(live()&&serial===state.request&&error.name!=='AbortError')state.error=error.message;}
      finally{if(live()&&serial===state.request){state.loading=false;readEditor();render();}}
    }
    host.onclick=async event=>{
      const element=event.target.closest('[data-sys]');if(!live()||!element||!host.contains(element)||element.disabled)return;
      const token=element.dataset.sys,separator=token.indexOf(':'),action=separator<0?token:token.slice(0,separator),id=separator<0?'':token.slice(separator+1);state.error='';
      try{
        if(action==='draft')await ctx.onEdit?.();
        else if(action==='save')await ctx.onSave?.();
        else if(action==='run')await ctx.onRun?.();
        else if(action==='refresh'){readEditor();await refresh();return;}
        else if(action==='cancel')state.editor=null;
        else if(action==='inspect')state.selected=id;
        else if(action==='close-inspector')state.selected=null;
        else if(action==='open-system')await ctx.onSelectSystem?.(id);
        else if(action==='add-system'||action==='add-interface'){if(!editable())throw Error('Start a shared draft before editing.');state.editor={kind:action==='add-system'?'system':'interface',id:null,values:action==='add-system'?{parent_id:null,model_ids:[]}:{source:{kind:''}}};}
        else if(action==='edit-system'||action==='edit-interface'){if(!editable())throw Error('Start a shared draft before editing.');const record=(action==='edit-system'?systems():interfaces()).find(item=>item.id===id);if(!record)throw Error('This definition is no longer present.');state.editor={kind:action==='edit-system'?'system':'interface',id,values:copy(record)};}
        else if(action==='remove-system'){const child=systems().filter(item=>item.parent_id===id),links=interfaces().filter(item=>item.from_system===id||item.to_system===id);if(child.length||links.length)throw Error('Move or remove child systems and connected interface contracts before removing this system. Assigned models will remain in the project.');const next=copy(project());next.systems=arr(next.systems).filter(item=>item.id!==id);await apply(next);}
        else if(action==='remove-interface'){const next=copy(project());next.interfaces=arr(next.interfaces).filter(item=>item.id!==id);await apply(next);}
      }catch(error){state.error=error.message;}if(live())render();
    };
    host.onchange=event=>{
      if(!event.target.closest('[data-sys-form]'))return;const old=readEditor(),name=event.target.name,v=state.editor?.values;if(!v||state.editor.kind!=='interface')return;
      if(name==='from_system'){v.source=v.source.kind==='model_metric'?{kind:'model_metric',model_id:'',metric:''}:{kind:v.source.kind,input_id:''};}
      if(name==='to_system')v.target_input='';
      if(name==='source_kind')v.source=v.source.kind==='model_metric'?{kind:'model_metric',model_id:'',metric:''}:{kind:v.source.kind,input_id:''};
      if(name==='model_id'&&old?.source?.model_id!==v.source.model_id)v.source.metric='';
      if(['from_system','to_system','source_kind','model_id'].includes(name))render();
    };
    host.onsubmit=async event=>{if(!event.target.matches('[data-sys-form]'))return;event.preventDefault();try{readEditor();const e=state.editor,record=copy(e.values);record.id=e.id||record.id.trim();if(!e.id&&!safe(record.id))throw Error('New IDs must start with a letter, followed by at most 79 letters, numbers, underscores or hyphens; reserved prototype names are unavailable.');record.title=record.title.trim();const next=copy(project()),key=e.kind==='system'?'systems':'interfaces';next[key]=arr(next[key]);if(e.id){const index=next[key].findIndex(item=>item.id===e.id);if(index<0)throw Error('This definition is no longer present.');next[key][index]=record;}else next[key].push(record);await apply(next);}catch(error){state.error=error.message;}if(live())render();};
    render();void refresh();
    void ctx.api('/api/model-catalog').then(value=>{if(!live())return;state.catalog=value;readEditor();render();}).catch(error=>{if(!live())return;state.catalogError='The metric catalog could not be loaded: '+error.message;readEditor();render();});
  }
  window.SixDSystems=Object.freeze({mount,unmount,report,impact});
})();
