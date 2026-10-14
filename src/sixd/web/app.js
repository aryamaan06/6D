"use strict";
const $ = id => document.getElementById(id);
const labels = {no_defect_found_in_scope:"No defect found in supported checks",defect_likely:"Defect likely",method_limitation:"Method limitation",inconclusive:"Inconclusive"};
const checkNames = {central_force_reference:"Independent central-force reference",analytic_reference_refinement:"Exact circular-orbit reference and refinement"};
let examples = [];
let selected = null;
let displayed = null;
let busy = false;
let comparing = false;
let comparisonGeneration = 0;

async function api(path, options) {
  const response = await fetch(path, options);
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || "The local request did not complete.");
  return value;
}
function error(message) {
  $("error").hidden = !message;
  $("error").textContent = message || "";
}
function number(value) {
  if (value === null || value === undefined) return "Unresolved";
  return Math.abs(value) < 0.001 && value !== 0 ? value.toExponential(3) : Number(value).toLocaleString(undefined,{maximumSignificantDigits:6});
}
function definition(list, name, value) {
  const dt = document.createElement("dt");dt.textContent=name;
  const dd = document.createElement("dd");dd.textContent=value;
  list.append(dt,dd);
}
function selectExample() {
  selected = examples.find(e=>e.id === $("example").value);
  if (!selected) return;
  const c = selected.contract;
  $("example-summary").textContent=selected.summary;
  const list=$("contract-fields");list.replaceChildren();
  definition(list,"Supported model","Synthetic, point-mass circular orbit");
  definition(list,"Declared method",`${c.declared_method.replaceAll("_"," ")} / order ${c.declared_order}`);
  definition(list,"Reference frame",c.frame.replaceAll("_"," "));
  definition(list,"Position / velocity / gravity units",`${c.position_unit} / ${c.velocity_unit} / ${c.mu_unit}`);
  definition(list,"Example radius",`${number(c.radius)} m`);
  definition(list,"Central-body parameter",`${number(c.mu)} m³/s²`);
  definition(list,"Experiment coverage","One circular-orbit period, four refinement levels, three initial phases");
  $("contract-json").textContent=JSON.stringify(c,null,2);
  $("candidate-source").textContent=selected.source.step_source+"\n"+selected.source.acceleration_source;
  $("contract-hash").textContent=selected.contract_sha256;
  $("accept").checked=false;$("run").disabled=true;
  displayed=null;$("result").hidden=true;$("empty").hidden=false;
  $("evidence-title").textContent="Evidence for this version";
  error(null);
}
function renderResult(value) {
  displayed=value;
  const report=value.report;
  $("evidence-title").textContent="Recorded evidence: "+report.example_title;
  $("empty").hidden=true;$("result").hidden=false;
  $("verdict").textContent=labels[report.verdict];
  $("verdict-block").dataset.kind=report.verdict;
  $("summary").textContent=report.summary;
  $("claim-boundary").textContent=report.claim_boundary;
  $("investigation").hidden=!report.investigation;
  const trace=$("investigation-trace");trace.replaceChildren();
  if (report.investigation) {
    const run=report.investigation;
    $("investigation-status").textContent=`${run.provider_mode} / ${run.state} / ${report.live_model_calls} live completed calls. ${run.error||""}`;
    run.trace.forEach(event=>{const li=document.createElement("li");li.textContent=event.tool+(event.evidence_id ? ` → ${event.evidence_id}` : "");trace.append(li)});
  }
  const checks=$("checks");checks.replaceChildren();
  report.checks.forEach(check=>{
    const row=document.createElement("div");row.className="check";
    const name=document.createElement("span");name.textContent=checkNames[check.id]||check.id;
    const status=document.createElement("strong");status.textContent=check.status;
    row.append(name,status);checks.append(row);
    if (check.id === "central_force_reference") {
      const detail=document.createElement("p");detail.className="small-note";
      detail.textContent=`Largest relative residual: ${number(check.max_relative_residual)}. Predeclared threshold: ${number(check.acceptance_threshold)}.`;
      checks.append(detail);
    }
  });
  if (!report.checks.length) {
    const p=document.createElement("p");p.className="secondary";
    p.textContent="No numerical experiment was run because the contract could not be resolved.";checks.append(p);
  }
  if (report.findings.some(f=>f.kind==="contract_ambiguity")) {
    report.findings.forEach(f=>{
      const p=document.createElement("p");p.className="secondary";p.textContent=f.message;checks.append(p);
    });
  }
  const refinement=report.checks.find(c=>c.id === "analytic_reference_refinement");
  $("refinement-section").hidden=!refinement;
  const tbody=$("refinement");tbody.replaceChildren();
  if (refinement) {
    refinement.runs.forEach(run=>{
      const row=document.createElement("tr");
      [run.steps,run.dt_seconds,run.max_state_error,run.max_abs_energy_change_fraction].forEach(v=>{
        const td=document.createElement("td");td.textContent=number(v);row.append(td);
      });tbody.append(row);
    });
    $("orders").textContent=`Declared order: ${refinement.declared_order}. Measured refinement orders: ${refinement.observed_orders.map(number).join(", ")}. Finest-level estimates are repeated in two rotated initial conditions.`;
  }
  const gaps=$("not-tested");gaps.replaceChildren();
  report.not_tested.forEach(gap=>{const li=document.createElement("li");li.textContent=gap;gaps.append(li)});
  const versions=$("versions");versions.replaceChildren();
  definition(versions,"Recorded example",report.example_title);
  definition(versions,"Recorded at",report.created_at);
  definition(versions,"Contract hash",report.contract_sha256);
  definition(versions,"Candidate source hash",report.candidate_source.source_sha256);
  definition(versions,"Kernel version",report.kernel_version);
  definition(versions,"Audit identity",report.audit_id);
  definition(versions,"Review mode",report.review.mode);
  definition(versions,"Live model calls",String(report.live_model_calls));
  $("reproduce").textContent=`python run.py reproduce "artifacts/${value.record_id}.json"`;
}
async function history() {
  const value=await api("/api/reports");
  comparisonChoices(value.reports);
  const list=$("history-list");list.replaceChildren();
  if (!value.reports.length) {
    const p=document.createElement("p");p.className="secondary";p.textContent="No evidence snapshots yet.";list.append(p);return;
  }
  value.reports.slice(0,12).forEach(record=>{
    const row=document.createElement("div");row.className="history-row";
    const copy=document.createElement("div");
    const title=document.createElement("p");title.textContent=`${record.example_title} / ${labels[record.verdict]}`;
    const info=document.createElement("small");info.textContent=new Date(record.created_at).toLocaleString();
    const button=document.createElement("button");button.type="button";button.className="secondary-button";button.textContent="Inspect evidence";
    button.addEventListener("click",async()=>{
      try {renderResult(await api("/api/reports/"+record.record_id));error(null);$("evidence-title").scrollIntoView({behavior:"smooth",block:"start"});}
      catch(err){error(err.message)}
    });copy.append(title,info);row.append(copy,button);list.append(row);
  });
}
function comparisonReady() {
  $("compare").disabled=comparing||!$("previous-report").value||!$("new-report").value||$("previous-report").value===$("new-report").value;
}
function clearComparison() {
  comparisonGeneration++;
  $("comparison-result").hidden=true;
  $("comparison-error").hidden=true;
  comparisonReady();
}
function comparisonChoices(records) {
  const previous=$("previous-report").value;
  const current=$("new-report").value;
  for (const id of ["previous-report","new-report"]) {
    $(id).replaceChildren(...records.map(record=>{
      const option=document.createElement("option");option.value=record.record_id;
      option.textContent=`${record.example_title} / ${new Date(record.created_at).toLocaleString()}`;return option;
    }));
    $(id).disabled=comparing||records.length<2;
  }
  if(records.length) {
    $("new-report").value=records.some(record=>record.record_id===current)?current:records[0].record_id;
    $("previous-report").value=records.some(record=>record.record_id===previous)?previous:records[Math.min(1,records.length-1)].record_id;
  }
  $("comparison-empty").hidden=records.length>=2;
  clearComparison();
}
function comparisonValue(value) {
  if(value===null||value===undefined)return "Not measured";
  if(Array.isArray(value))return value.map(comparisonValue).join(", ");
  if(typeof value==="number")return number(value);
  return String(value);
}
function comparisonRow(container, values) {
  const row=document.createElement("tr");
  values.forEach(value=>{const cell=document.createElement("td");cell.textContent=value;row.append(cell)});
  container.append(row);
}
function renderComparison(value) {
  const comparison=value.comparison;
  $("comparison-summary").textContent=`${value.previous_title}: ${labels[comparison.previous_verdict]}. ${value.new_title}: ${labels[comparison.new_verdict]}.`;
  $("comparison-scope").textContent=comparison.coverage_note;
  const versions=$("comparison-versions");versions.replaceChildren();
  definition(versions,"Candidate source",comparison.candidate_source_changed?"Changed":"Unchanged");
  definition(versions,"Verification sources",comparison.verification_sources_changed?"Changed":"Unchanged");
  definition(versions,"Provider mode",`${comparison.previous_provider} / ${comparison.new_provider}`);
  const contracts=$("comparison-contracts");contracts.replaceChildren();
  comparison.contract_changes.forEach(change=>comparisonRow(contracts,[change.field.replaceAll("_"," "),comparisonValue(change.before),comparisonValue(change.after)]));
  $("comparison-no-assumptions").hidden=Boolean(comparison.contract_changes.length);
  $("comparison-contract-table").hidden=!comparison.contract_changes.length;
  const checks=$("comparison-checks");checks.replaceChildren();
  const metrics={max_relative_residual:"Maximum relative force residual",observed_orders:"Observed refinement orders",finest_dt_seconds:"Finest step (seconds)",finest_max_state_error:"Finest normalized state error",finest_max_abs_energy_change_fraction:"Finest fractional energy change"};
  comparison.check_changes.forEach(change=>{
    comparisonRow(checks,[checkNames[change.evidence_id]||change.evidence_id,change.previous_status||"Not run",change.new_status||"Not run"]);
    change.measurement_changes.forEach(metric=>comparisonRow(checks,[metrics[metric.metric]||metric.metric,comparisonValue(metric.before),comparisonValue(metric.after)]));
  });
  $("comparison-no-checks").hidden=Boolean(comparison.check_changes.length);
  const gaps=$("comparison-gaps");gaps.replaceChildren();
  const before=new Set(comparison.not_tested_before),after=new Set(comparison.not_tested_after);
  for(const gap of new Set([...before,...after])) {
    const li=document.createElement("li");
    li.textContent=(before.has(gap)&&after.has(gap)?"Unassessed in both: ":before.has(gap)?"Listed only in earlier audit: ":"Listed only in later audit: ")+gap;
    gaps.append(li);
  }
  const records=$("comparison-records");records.replaceChildren();
  definition(records,"Earlier record",value.previous_record_id);definition(records,"Later record",value.new_record_id);
  $("comparison-result").hidden=false;
}
for(const id of ["previous-report","new-report"])$(id).addEventListener("change",clearComparison);
$("compare").addEventListener("click",async()=>{
  if(comparing||$("compare").disabled)return;
  comparing=true;const generation=++comparisonGeneration;comparisonReady();
  $("previous-report").disabled=true;$("new-report").disabled=true;$("compare").textContent="Reading saved evidence…";
  $("comparison-error").hidden=true;$("comparison-result").hidden=true;
  try {
    const value=await api("/api/compare",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({previous_record_id:$("previous-report").value,new_record_id:$("new-report").value})});
    if(generation===comparisonGeneration)renderComparison(value);
  } catch(err) {
    if(generation===comparisonGeneration){$("comparison-error").textContent=err.message;$("comparison-error").hidden=false;}
  } finally {
    comparing=false;$("previous-report").disabled=$("new-report").options.length<2;$("new-report").disabled=$("previous-report").disabled;
    $("compare").textContent="Compare saved audits";comparisonReady();
  }
});
$("example").addEventListener("change",selectExample);
$("accept").addEventListener("change",()=>{$("run").disabled=busy||!$("accept").checked});
$("run").addEventListener("click",async()=>{
  if (busy||!selected||!$("accept").checked) return;
  busy=true;$("run").disabled=true;$("example").disabled=true;$("accept").disabled=true;$("workflow").disabled=true;
  $("run").textContent="Running numerical experiments…";error(null);
  try {
    const value=await api("/api/"+$("workflow").value,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({example_id:selected.id,contract_sha256:selected.contract_sha256,review_accepted:true})});
    renderResult(value);await history();
  } catch(err) {error(err.message)}
  finally {busy=false;$("example").disabled=false;$("accept").disabled=false;$("workflow").disabled=false;$("run").textContent="Run supported checks";$("run").disabled=!$("accept").checked}
});
$("download-json").addEventListener("click",()=>{
  if (!displayed) return;
  const url=URL.createObjectURL(new Blob([JSON.stringify(displayed.report,null,2)+"\n"],{type:"application/json"}));
  const a=document.createElement("a");a.href=url;a.download=displayed.record_id+".json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
$("refresh").addEventListener("click",()=>history().catch(err=>error(err.message)));
async function initialize() {
  try {
    const value=await api("/api/examples");examples=value.examples;
    $("example").replaceChildren(...examples.map(e=>{const o=document.createElement("option");o.value=e.id;o.textContent=e.title;return o}));
    selectExample();await history();
  } catch(err) {error("The local interface could not load: "+err.message)}
}
initialize();
