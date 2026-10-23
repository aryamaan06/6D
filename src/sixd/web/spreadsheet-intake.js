/* Local spreadsheet intake. Files remain in memory; preview never saves or runs a project. */
(() => {
  'use strict';
  const ROLES = {
    inputs: {title:'Inputs', hint:'One row per supplied quantity, including requirement limits.', fields:['id','value','unit','source']},
    bindings: {title:'Model bindings', hint:'One row per model parameter. Repeated model IDs group its explicitly supplied parameter bindings.', fields:['model_id','model_type','parameter','input_id']},
    requirements: {title:'Requirements', hint:'One row per criterion. Critical must explicitly say true or false.', fields:['id','title','model_id','metric','operator','limit_input','critical']}
  };
  const MAX_FILE = 1024 * 1024, MAX_TOTAL = 1.5 * 1024 * 1024;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let session = null;
  const el = (s, selector) => s.dialog.querySelector(selector);
  const button = (action, text, primary=false) => '<button type="button" class="si-button'+(primary?' si-primary':'')+'" data-si-action="'+action+'">'+esc(text)+'</button>';
  const fieldLabel = name => ({id:'Record ID',value:'Value',unit:'Unit',source:'Source',model_id:'Model ID',model_type:'Model type',parameter:'Parameter',input_id:'Input ID',title:'Requirement title',metric:'Metric',operator:'Operator',limit_input:'Limit input ID',critical:'Critical (true / false)'}[name] || name);
  const option = (value, label, selected) => '<option value="'+esc(value)+'"'+(selected?' selected':'')+'>'+esc(label)+'</option>';
  const issueText = issue => typeof issue === 'string' ? issue : issue?.message || issue?.code || 'Review this record.';

  function invalidate(s) {
    s.version++; s.preview=null; s.error='';
    el(s,'[data-si-result]').innerHTML='<p class="si-muted">Preview the current files and mappings before creating a project.</p>';
    controls(s);
  }
  function controls(s) {
    s.dialog.querySelectorAll('[data-si-action="preview"],[data-si-action="create"]').forEach(b => {
      b.disabled=!!s.busy || (b.dataset.siAction==='create' ? !s.preview?.valid : !ready(s));
    });
    s.dialog.querySelectorAll('[data-si-file],[data-si-source],[data-si-map],[data-si-action="clear"]').forEach(b => b.disabled=!!s.busy);
    s.dialog.querySelectorAll('[data-si-meta],[data-si-action="close"]').forEach(b => b.disabled=s.busy==='create');
    el(s,'[data-si-busy]').textContent=s.busy==='inspect'?'Reading the selected files locally…':s.busy==='preview'?'Validating the mapped project…':s.busy==='create'?'Saving this project…':'';
    el(s,'[data-si-error]').textContent=s.error;
    el(s,'[data-si-error]').hidden=!s.error;
  }
  function ready(s) {
    return s.files.length>0 && ['project_id','name','description','lifecycle_stage'].every(k=>s.project[k].trim()) && Object.entries(ROLES).every(([role,spec])=>{
      const table=s.tables[role]; return table && spec.fields.every(f=>table.mapping[f]);
    });
  }
  function table(s,role) {
    const selection=s.tables[role];
    return selection ? s.files[selection.file_index]?.inspection.sheets.find(sheet=>sheet.name===selection.sheet) : null;
  }
  function records(headers,rows,label) {
    if(!rows.length)return '<p class="si-muted">No data rows.</p>';
    const body = list => '<div class="si-table-wrap"><table class="si-table"><caption>'+esc(label)+'</caption><thead><tr>'+headers.map(h=>'<th scope="col">'+esc(h)+'</th>').join('')+'</tr></thead><tbody>'+list.map(row=>'<tr>'+headers.map((_,i)=>'<td>'+esc(row[i])+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';
    return body(rows.slice(0,8))+(rows.length>8?'<details class="si-records"><summary>View all '+rows.length+' rows</summary>'+body(rows)+'</details>':'');
  }
  function renderTables(s) {
    el(s,'[data-si-tables]').innerHTML=Object.entries(ROLES).map(([role,spec])=>{
      const selection=s.tables[role], sheet=table(s,role);
      const choices=s.files.flatMap((f,i)=>(f.inspection.sheets||[]).map(sh=>option(i+'|'+sh.name, f.filename+' · '+sh.name, selection?.file_index===i && selection.sheet===sh.name))).join('');
      return '<section class="si-role" aria-labelledby="si-heading-'+role+'"><div class="si-section-head"><h3 id="si-heading-'+role+'">'+spec.title+'</h3><span class="si-tag">'+(sheet ? sheet.rows.length+' rows' : 'Select a table')+'</span></div><p class="si-muted">'+spec.hint+'</p><label class="si-field">Source table<select data-si-source="'+role+'">'+option('','Choose a file and worksheet',!selection)+choices+'</select></label>'+(sheet?'<div class="si-map-grid">'+spec.fields.map(f=>'<label class="si-field">'+fieldLabel(f)+'<select data-si-map="'+role+'" data-si-field="'+f+'">'+option('','Choose column',!selection.mapping[f])+sheet.headers.map(h=>option(h,h,selection.mapping[f]===h)).join('')+'</select></label>').join('')+'</div>'+((sheet.issues||[]).length?'<ul class="si-issues">'+sheet.issues.map(i=>'<li>'+esc(issueText(i))+'</li>').join('')+'</ul>':'')+'<details class="si-records"><summary>Inspect source rows ('+sheet.rows.length+')</summary>'+records(sheet.headers,sheet.rows,spec.title+' source data')+'</details>':'')+'</section>';
    }).join('');
    el(s,'[data-si-files]').innerHTML=s.files.length?'<ul class="si-files">'+s.files.map(f=>'<li><strong>'+esc(f.filename)+'</strong><span>'+f.inspection.sheets.length+' worksheet'+(f.inspection.sheets.length===1?'':'s')+' · '+Math.ceil(f.size/1024)+' KiB</span></li>').join('')+'</ul>':'<p class="si-muted">No files selected.</p>';
    controls(s);
  }
  function choose(s,role,fileIndex,sheetName) {
    const sheet=s.files[fileIndex]?.inspection.sheets.find(sh=>sh.name===sheetName);
    if(!sheet){delete s.tables[role];return;}
    s.tables[role]={file_index:fileIndex,sheet:sheetName,mapping:Object.fromEntries(ROLES[role].fields.map(f=>[f,sheet.headers.includes(f)?f:'']))};
  }
  function suggest(s) {
    s.tables={};
    Object.keys(ROLES).forEach(role=>{
      const matches=[];
      s.files.forEach((file,i)=>file.inspection.sheets.forEach(sheet=>{
        const stem=file.filename.replace(/\.[^.]+$/,'').toLowerCase();
        if(sheet.name.toLowerCase()===role || (file.inspection.sheets.length===1 && stem===role))matches.push([i,sheet.name]);
      }));
      if(matches.length===1)choose(s,role,...matches[0]);
    });
  }
  function readBase64(file) {
    return new Promise((resolve,reject)=>{
      const reader=new FileReader();
      reader.onerror=()=>reject(Error('Could not read '+file.name+'. Choose the file again.'));
      reader.onload=()=>resolve(String(reader.result).split(',')[1]);
      reader.readAsDataURL(file);
    });
  }
  async function inspect(s,files) {
    if(s.busy)return;
    invalidate(s); s.files=[];s.tables={};s.busy='inspect'; const version=s.version; renderTables(s);
    try {
      if(!files.length)return;
      if(files.length>3)throw Error('Choose up to three files: one workbook or the CSV tables.');
      if(files.some(f=>!/^.+\.(csv|xlsx)$/i.test(f.name)))throw Error('Choose UTF-8 .csv or .xlsx files. Legacy .xls and macro-enabled workbooks are not supported.');
      if(files.some(f=>f.size>MAX_FILE)||files.reduce((n,f)=>n+f.size,0)>MAX_TOTAL)throw Error('Each file must be at most 1 MiB, with at most 1.5 MiB of files in total.');
      const parsed=[];
      for(const file of files){
        const content_base64=await readBase64(file);
        const inspection=await s.api('/api/project-intake/inspect',{filename:file.name,content_base64});
        if(session!==s || !s.dialog.open || s.version!==version)return;
        if(!Array.isArray(inspection.sheets)||!inspection.sheets.length)throw Error('No usable tables were found in '+file.name+'.');
        parsed.push({filename:file.name,content_base64,size:file.size,inspection});
      }
      if(session!==s||s.version!==version)return;
      s.files=parsed; suggest(s); renderTables(s);
    } catch(error){ if(session===s && s.version===version)s.error=error.message || String(error); }
    finally {if(session===s){s.busy='';controls(s);}}
  }
  function renderPreview(s,response) {
    const issues=[...(response.issues||[])], p=response.project;
    for(const issue of response.preflight?.issues||[]){
      if(!issues.some(existing=>issueText(existing)===issueText(issue)))issues.push(issue);
    }
    const metadata=p?'<dl class="si-summary"><div><dt>Project</dt><dd>'+esc(p.name)+'<small>'+esc(p.project_id)+' · '+esc(p.lifecycle_stage)+'</small></dd></div><div><dt>Inputs</dt><dd>'+Object.keys(p.inputs||{}).length+'</dd></div><div><dt>Models</dt><dd>'+(p.models||[]).length+'</dd></div><div><dt>Requirements</dt><dd>'+(p.requirements||[]).length+'</dd></div></dl>':'';
    const evidence=p?'<details class="si-records"><summary>Review mapped project records</summary><h4>Inputs and exact units</h4>'+records(['ID','Value','Unit','Source'],Object.entries(p.inputs||{}).map(([id,v])=>[id,v.value,v.unit,v.source]),'Mapped project inputs')+'<h4>Model parameter bindings</h4>'+records(['Model ID','Model type','Parameter','Input ID'],(p.models||[]).flatMap(m=>Object.entries(m.inputs||{}).map(([parameter,id])=>[m.id,m.type,parameter,id])),'Mapped model bindings')+'<h4>Requirement criteria</h4>'+records(['ID','Title','Model ID','Metric','Operator','Limit input','Critical'],(p.requirements||[]).map(r=>[r.id,r.title,r.model_id,r.metric,r.operator,r.limit_input,String(r.critical)]),'Mapped requirements')+'</details><details class="si-records"><summary>Project description and import provenance</summary><pre class="si-provenance">'+esc(p.description)+'</pre></details>':'';
    const problems=issues.length?'<ul class="si-issues">'+issues.map(i=>'<li class="'+(i.severity==='error'?'si-invalid':'')+'"><strong>'+esc([i.table,i.row?'row '+i.row:'',i.field].filter(Boolean).join(' · '))+'</strong> '+esc(issueText(i))+'</li>').join('')+'</ul>':'';
    const source='<details class="si-records"><summary>File provenance</summary><ul class="si-files">'+s.files.map(file=>'<li><strong>'+esc(file.filename)+'</strong><code>SHA-256 '+esc(file.inspection.sha256)+'</code></li>').join('')+'</ul><p class="si-muted">The preview retains source identifiers, exact supplied units and explicit parameter bindings. A source label does not validate the underlying data.</p></details>';
    el(s,'[data-si-result]').innerHTML='<div tabindex="-1" class="si-result-heading '+(response.valid?'si-valid':'si-invalid')+'"><strong>'+(response.valid?'Project structure is ready for your review':'Resolve the import issues before saving')+'</strong></div>'+metadata+problems+evidence+source+'<p class="si-muted">'+(response.valid?'Creating saves a new local R1. Then choose Run checks in the workspace to calculate engineering findings.':'Correct the spreadsheet or change its column mappings, then preview again.')+' No project has been saved by this preview.</p>';
    const heading=el(s,'.si-result-heading');heading.focus({preventScroll:true});heading.scrollIntoView({block:'start'});
  }
  async function preview(s) {
    if(s.busy||!ready(s))return;
    invalidate(s); s.busy='preview'; const version=s.version; controls(s);
    try {
      const payload={project:{...s.project},files:s.files.map(({filename,content_base64})=>({filename,content_base64})),tables:JSON.parse(JSON.stringify(s.tables))};
      const response=await s.api('/api/project-intake/preview',payload);
      if(session!==s||s.version!==version||!s.dialog.open)return;
      s.preview=response; renderPreview(s,response);
    } catch(error){if(session===s&&s.version===version)s.error=error.message||String(error);}
    finally {if(session===s){s.busy='';controls(s);}}
  }
  async function create(s) {
    if(s.busy||!s.preview?.valid||!s.preview.project)return;
    s.busy='create';s.error='';controls(s);
    try {
      const view=await s.api('/api/projects',{project:JSON.parse(JSON.stringify(s.preview.project))});
      // Saving is explicit and irreversible within this dialog; notify the workspace once.
      s.busy='';s.created=true; close(s); await s.onCreated(view);
    } catch(error){if(session===s){s.error=error.message||String(error);s.busy='';controls(s);}}
  }
  function download(role) {
    const csv={
      inputs:'id,value,unit,source\r\nrho,1,kg/m^3,Constructed example density\r\nspeed,10,m/s,Constructed example relative speed\r\ncd,1,1,Constructed coefficient; applicability not validated\r\narea,2,m^2,Constructed reference area\r\nallowable,150,N,Constructed declared drag limit\r\n',
      bindings:'model_id,model_type,parameter,input_id\r\nload,drag_load,density,rho\r\nload,drag_load,relative_speed,speed\r\nload,drag_load,drag_coefficient,cd\r\nload,drag_load,reference_area,area\r\n',
      requirements:'id,title,model_id,metric,operator,limit_input,critical\r\nload_limit,Declared drag magnitude limit,load,drag_force,<=,allowable,true\r\n'
    }[role];
    if(!csv)return;
    const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
    const link=document.createElement('a');link.href=url;link.download=role+'.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function close(s) {
    if(s.busy==='create')return;
    s.version++; s.files=[];s.tables={};s.preview=null;s.dialog.close();s.dialog.remove();if(session===s)session=null;
  }
  function open({api,onCreated}) {
    if(typeof api!=='function'||typeof onCreated!=='function')throw Error('Spreadsheet intake requires workspace callbacks.');
    if(session){session.dialog.focus();return;}
    const dialog=document.createElement('dialog'); dialog.id='sd-spreadsheet-dialog';dialog.className='si-dialog';dialog.setAttribute('aria-labelledby','si-title');
    const s={api,onCreated,dialog,files:[],tables:{},preview:null,error:'',busy:'',version:0,created:false,project:{project_id:'',name:'',description:'',lifecycle_stage:'design'}}; session=s;
    dialog.innerHTML='<header class="si-header"><div><span class="si-eyebrow">Local project intake</span><h2 id="si-title">Bring your engineering spreadsheet</h2><p>Map supplied inputs, model bindings and requirements. Review the project before saving.</p></div><button type="button" class="si-close" data-si-action="close" aria-label="Close spreadsheet intake">×</button></header><div class="si-body"><section class="si-section"><h3>1. Choose your tables</h3><p class="si-muted">Use an .xlsx workbook with Inputs, Bindings and Requirements worksheets, or three UTF-8 CSV files. No API connection is needed.</p><label class="si-field si-upload">Spreadsheet files<input type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" multiple data-si-file><span>Up to 3 files · 1 MiB each · 1.5 MiB total · 500 rows per sheet</span></label><div data-si-files></div><div class="si-template"><span>Try the constructed drag example:</span><a class="si-button" href="/api/project-intake/example-workbook" download="6d-constructed-drag.xlsx">Excel workbook</a>'+button('template-inputs','Inputs CSV')+button('template-bindings','Bindings CSV')+button('template-requirements','Requirements CSV')+'</div><p class="si-note">Use supplied cell values, not formulas or cached formula results. Units must exactly match the maintained model contract. Import does not convert units, infer models or establish hardware validity. Power-budget mode layouts, CAD and arbitrary spreadsheets are outside this intake format.</p></section><section class="si-section"><h3>2. Name the new project</h3><div class="si-meta-grid"><label class="si-field">Project ID<input data-si-meta="project_id" autocomplete="off" maxlength="120" placeholder="e.g. drag-review"></label><label class="si-field">Project name<input data-si-meta="name" maxlength="240" placeholder="e.g. One-condition drag review"></label><label class="si-field si-wide">Purpose and assumptions<textarea data-si-meta="description" rows="2" maxlength="4000" placeholder="Describe the supplied model and where its assumptions apply."></textarea></label><label class="si-field">Lifecycle stage<select data-si-meta="lifecycle_stage"><option value="design">Design</option><option value="simulation">Simulation</option><option value="physical_test">Physical test</option><option value="operation">Operation</option></select></label></div><p class="si-muted">The stage records your project context; it does not add model coverage or supply test evidence.</p></section><section class="si-section"><h3>3. Map each table</h3><p class="si-muted">Exact matching table and column names are preselected. Inspect every mapping and preview to confirm; other names require an explicit selection. Each role needs its own table.</p><div data-si-tables></div></section><section class="si-section" aria-labelledby="si-preview-heading"><div class="si-section-head"><h3 id="si-preview-heading">4. Preview the project</h3>'+button('preview','Validate and preview')+'</div><div data-si-result aria-live="polite"><p class="si-muted">Choose files and map all required columns to preview the project.</p></div></section><p class="si-error" data-si-error role="alert" hidden></p></div><footer class="si-footer"><div><p data-si-busy role="status" aria-live="polite"></p><p class="si-muted">Preview makes no saved changes and runs no calculations.</p></div><div class="si-actions">'+button('close','Cancel')+button('create','Create project',true)+'</div></footer>';
    document.body.append(dialog);
    dialog.addEventListener('cancel',event=>{event.preventDefault();close(s);});
    dialog.addEventListener('input',event=>{
      if(event.target.dataset.siMeta){s.project[event.target.dataset.siMeta]=event.target.value;invalidate(s);}
    });
    dialog.addEventListener('change',event=>{
      const target=event.target;
      if(target.hasAttribute('data-si-file')){void inspect(s,[...target.files]);return;}
      if(target.dataset.siSource){const value=target.value, split=value.indexOf('|');if(!value)delete s.tables[target.dataset.siSource];else choose(s,target.dataset.siSource,Number(value.slice(0,split)),value.slice(split+1));invalidate(s);renderTables(s);return;}
      if(target.dataset.siMap){s.tables[target.dataset.siMap].mapping[target.dataset.siField]=target.value;invalidate(s);return;}
      if(target.dataset.siMeta){s.project[target.dataset.siMeta]=target.value;invalidate(s);}
    });
    dialog.addEventListener('click',event=>{
      const action=event.target.closest('[data-si-action]')?.dataset.siAction;
      if(!action)return;
      if(action==='close'){close(s);return;}
      if(action==='preview'){void preview(s);return;}
      if(action==='create'){void create(s);return;}
      if(action.startsWith('template-'))download(action.slice(9));
    });
    renderTables(s); dialog.showModal(); el(s,'[data-si-file]').focus();
  }
  window.SixDSpreadsheetIntake=Object.freeze({open});
})();
