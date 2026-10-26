/* Plain-language labels are navigation only; exact engineering IDs stay intact. */
(() => {
  'use strict';
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const list=value=>Array.isArray(value)?value:[];
  function topic(target){
    const text=String(target.label||target.target_id||'').toLowerCase();
    if(/propellant|fuel|burn.duration|specific impulse|delta.?v|thrust|engine/.test(text))return 'Engine & fuel';
    if(/stress|deflection|bending|drag|dynamic pressure|density|structur/.test(text))return 'Forces & structure';
    if(/thermal|radiat|temperature|heat|emissiv/.test(text))return 'Heating';
    if(/pointing|tracking|guidance|control|angular|torque/.test(text))return 'Guidance';
    if(/power|energy|battery|electric/.test(text))return 'Power';
    if(/altitude|height|acceleration|flight|orbit|position|velocity|speed/.test(text))return 'Flight path';
    return 'Other project checks';
  }
  function shortLabel(target){
    const original=String(target.label||target.target_id||'Project check');
    const text=original.toLowerCase();
    let label;
    if(/burnout.*(height|altitude)|(height|altitude).*burnout/.test(text))label='Altitude at engine cutoff';
    else if(/propellant.*margin|fuel.*margin/.test(text))label='Fuel margin';
    else if(/burn.duration/.test(text))label='Engine burn time';
    else if(/dynamic pressure/.test(text))label='Pressure from airflow';
    else if(/upward acceleration/.test(text))label='Upward acceleration';
    else if(/drag.force/.test(text))label='Drag force';
    else if(/stress/.test(text))label='Structural stress';
    else if(/deflection|bending/.test(text))label='Structural bending';
    else if(/temperature/.test(text))label='Temperature';
    else if(/tracking/.test(text))label='Guidance tracking';
    else if(/pointing/.test(text))label='Pointing accuracy';
    else label=original.replace(/\s*· saved finding$/i,'').replace(/^declared\s+/i,'').replace(/\breference-density\s+|\bindependent\s+|\btheoretical\s+|\btransverse\s+|\bscreening\s+/gi,'').trim();
    if(label!==original && /minimum|required minimum/.test(text)&&!/^minimum/i.test(label))label='Minimum '+label.charAt(0).toLowerCase()+label.slice(1);
    if(label!==original && /maximum/.test(text)&&!/^maximum/i.test(label))label='Maximum '+label.charAt(0).toLowerCase()+label.slice(1);
    return label.charAt(0).toUpperCase()+label.slice(1);
  }
  function requirements(targets,selected){
    const seen=new Set(),rows=list(targets).filter(target=>{
      if(target.kind!=='requirement'&&!String(target.target_id||'').startsWith('requirement:'))return false;
      if(seen.has(target.target_id))return false;seen.add(target.target_id);return true;
    });
    const result=rows.slice(0,12),chosen=rows.find(row=>row.target_id===selected);
    if(chosen&&!result.some(row=>row.target_id===selected))result[result.length-1]=chosen;
    return {rows:result,total:rows.length};
  }
  function primaryOptions(targets,selected){
    const choices=requirements(targets,selected),groups=new Map();
    for(const target of choices.rows){const group=topic(target);if(!groups.has(group))groups.set(group,[]);groups.get(group).push(target);}
    return [...groups].map(([group,rows])=>'<optgroup label="'+esc(group)+'">'+rows.map(target=>'<option value="'+esc(target.target_id)+'" title="'+esc(target.label)+'"'+(selected===target.target_id?' selected':'')+'>'+esc(shortLabel(target))+'</option>').join('')+'</optgroup>').join('');
  }
  function render(targets,selected,{primaryAttr,advancedAttr,label='What is this about?'}={}){
    const current=list(targets).find(row=>row.target_id===selected),choices=requirements(targets,selected);
    return '<div class="st-target-picker"><label class="st-field">'+esc(label)+'<select '+primaryAttr+' aria-label="'+esc(label)+'"><option value="">'+(current&&current.kind!=='requirement'?'Specific record selected below':'Choose a topic')+'</option>'+primaryOptions(targets,selected)+'</select></label><p class="st-hint">'+(choices.total>12?'Showing a short list of project checks. More choices are in Advanced.':'Choose a project check. Detailed assumptions and saved results are in Advanced.')+'</p><details class="st-advanced"'+(current&&current.kind!=='requirement'?' open':'')+'><summary>Advanced: exact engineering record</summary><label class="st-field">Specific requirement, result or assumption<select '+advancedAttr+'><option value="">Choose an exact record</option>'+list(targets).map(target=>'<option value="'+esc(target.target_id)+'"'+(selected===target.target_id?' selected':'')+'>'+esc(target.label)+'</option>').join('')+'</select></label><p class="st-exact" data-st-current>'+esc(current?.label||'No record selected.')+'</p><code data-st-identity>'+esc(current?.target_id||'')+'</code><p class="st-hint">These choices keep distinct links to a requirement, its saved result or a model assumption.</p></details></div>';
  }
  function update(host,targets,selected){
    const current=list(targets).find(row=>row.target_id===selected);
    host.querySelectorAll('.st-target-picker').forEach(picker=>{
      const selects=picker.querySelectorAll('select'),primary=selects[0],advanced=selects[1];
      if(primary){const html='<option value="">'+(current&&current.kind!=='requirement'?'Specific record selected below':'Choose a topic')+'</option>'+primaryOptions(targets,selected);if(primary.dataset.options!==html){primary.innerHTML=html;primary.dataset.options=html;}primary.value=[...primary.options].some(row=>row.value===selected)?selected:'';}
      if(advanced)advanced.value=selected||'';
      const description=picker.querySelector('[data-st-current]'),identity=picker.querySelector('[data-st-identity]');
      if(description)description.textContent=current?.label||'No record selected.';
      if(identity)identity.textContent=current?.target_id||'';
    });
  }
  window.SixDSourceTargets=Object.freeze({render,update,shortLabel,topic});
})();
