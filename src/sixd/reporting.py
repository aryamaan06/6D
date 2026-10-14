"""Append-only local evidence snapshots and portable reading copies."""
from datetime import datetime
from html import escape
from pathlib import Path
from hashlib import sha256
import json
import re
from .contracts import digest

RECORD_ID = re.compile(r"^[a-f0-9]{20}-[0-9]{8}T[0-9]{12}Z$")
LABELS = {"defect_likely":"Defect likely", "method_limitation":"Method limitation",
          "no_defect_found_in_scope":"No defect found in supported checks", "inconclusive":"Inconclusive"}


def verify_payload(report):
    recorded = report.get("report_payload_sha256")
    payload = {k:v for k,v in report.items() if k != "report_payload_sha256"}
    if not recorded or digest(payload) != recorded:
        raise ValueError("Report content does not match its recorded digest. This check is not a digital signature.")
    if digest(report["contract"]) != report.get("contract_sha256"):
        raise ValueError("The contract does not match its recorded digest.")
    source = report["candidate_source"]
    if sha256((source["step_source"]+"\n"+source["acceleration_source"]).encode()).hexdigest() != source["source_sha256"]:
        raise ValueError("The source excerpt does not match its recorded digest.")
    identity = digest({"contract":report["contract_sha256"],"candidate":source["source_sha256"],
                       "verification_sources":report["verification_sources"],"checks":report["checks"],"verdict":report["verdict"]})[:20]
    if identity != report["audit_id"]:
        raise ValueError("The audit identity is inconsistent with its evidence and versions.")
    if 'investigation' in report:
        run = report['investigation']
        if (run['contract_sha256'] != report['contract_sha256'] or
            run['kernel_audit_id'] != report['audit_id'] or run['summary'] != report['summary'] or
            run['summary_origin'] != 'deterministic_kernel' or run['provider_mode'] != report['model_mode']):
            raise ValueError('The investigation is inconsistent with its locked kernel evidence.')
        evidence = {check['id']: check for check in report['checks']}
        selected = set()
        for event in run['trace']:
            response_fields = ('finish_reason', 'response_format', 'call_id_origin')
            if any(field in event for field in response_fields):
                response = tuple(event.get(field) for field in response_fields)
                if (run.get('selection_protocol') != 'forced_action_v1' or
                        response not in (('stop', 'native_tool_call', 'provider'),
                                         ('tool_calls', 'native_tool_call', 'provider'),
                                         ('stop', 'content_selection_json', 'runner')) or
                        (event.get('call_id_origin') == 'runner' and
                         not re.fullmatch(r'sixd-selection-[a-f0-9]{32}', event.get('call_id', '')))):
                    raise ValueError('The action-response provenance is inconsistent.')
            if event.get('status') == 'rejected' and any(
                    key in event for key in ('evidence_id', 'evidence_ids', 'evidence_sha256')):
                raise ValueError('A rejected tool call cannot claim recorded evidence.')
            if 'evidence_id' in event:
                key = event['evidence_id']
                if key not in evidence or event['evidence_sha256'] != digest(evidence[key]) or key in selected:
                    raise ValueError('The tool trace does not match recorded experiment evidence.')
                selected.add(key)
        if run['state'] == 'completed' and (selected != set(evidence) or not selected or
                not run['trace'] or run['trace'][-1]['tool'] != 'finish' or
                set(run['trace'][-1]['evidence_ids']) != selected):
            raise ValueError('A completed investigation must cite all applicable selected checks.')
        if run['provider_mode'] != 'live_token_factory' and (report['live_model_calls'] or run['live_request_attempts']):
            raise ValueError('Offline fixtures cannot claim live inference calls.')
    return True


def refinement_rows(report):
    experiment = next((c for c in report["checks"] if c["id"] == "analytic_reference_refinement"),None)
    if not experiment:
        return "<p>No refinement experiment was run.</p>"
    rows = "".join(f"<tr><td>{r['steps']}</td><td>{r['dt_seconds']:.6g}</td><td>{r['max_state_error']:.6g}</td><td>{r['max_abs_energy_change_fraction']:.6g}</td></tr>" for r in experiment["runs"])
    return f"<table><thead><tr><th>Steps per orbit</th><th>Step (s)</th><th>Maximum normalized state error</th><th>Maximum fractional energy change</th></tr></thead><tbody>{rows}</tbody></table>"


def report_html(report):
    label = LABELS[report["verdict"]]
    checks = "".join(f"<li>{escape(c['id'])}: <strong>{escape(c['status'])}</strong></li>" for c in report["checks"])
    gaps = "".join(f"<li>{escape(item)}</li>" for item in report["not_tested"])
    findings = "".join(f"<li>{escape(f['message'])}</li>" for f in report["findings"]) or "<li>No finding in supported checks.</li>"
    contract = escape(json.dumps(report["contract"],indent=2))
    source = escape(report["candidate_source"]["step_source"] + "\n" + report["candidate_source"]["acceleration_source"])
    mode = escape(report['model_mode'])
    investigation = ''
    if 'investigation' in report:
        run = report['investigation']
        events = ''.join(f"<li>{escape(event['tool'])}: {escape(event.get('status', 'recorded'))}</li>" for event in run['trace'])
        investigation = f"<h2>Structured investigation</h2><p>State: {escape(run['state'])}. Provider: {mode}. Accepted live provider responses: {report['live_model_calls']}.</p><p>Summary comes from the deterministic kernel. Fixture mode is scripted orchestration with no model inference.</p><ol>{events}</ol><p>{escape(run['error'] or '')}</p><p>{escape(run['reproduction_scope'])}</p>"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>6D evidence: {escape(label)}</title>
<style>body{{font:16px/1.6 system-ui,sans-serif;color:#142d3a;background:#f5f8fa;margin:0;padding:32px}}main{{max-width:1040px;margin:auto}}h1{{font-size:36px;line-height:1.2}}h2{{font-size:23px;margin-top:32px}}table{{border-collapse:collapse;width:100%}}th,td{{padding:12px;text-align:left;border-bottom:1px solid #d0dce3}}th{{background:#e7eef2}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#e8eef1;padding:16px}}.mode{{color:#315565}}@media(max-width:550px){{body{{padding:16px}}table{{font-size:13px}}th,td{{padding:7px}}}}</style></head><body><main>
<p class="mode">6D research prototype / Local curated execution / Provider: {mode}</p><h1>{escape(label)}</h1><p>{escape(report['summary'])}</p><p>{escape(report['claim_boundary'])}</p>{investigation}
<h2>Findings</h2><ul>{findings}</ul><h2>Recorded experiments</h2><ul>{checks}</ul>{refinement_rows(report)}
<h2>Not tested</h2><ul>{gaps}</ul><h2>Versioned contract</h2><pre>{contract}</pre><p>Contract SHA-256: <code>{report['contract_sha256']}</code></p>
<h2>Curated source examined</h2><pre>{source}</pre><h2>Reproduction</h2><p>Use the companion JSON with <code>python run.py reproduce path/to/report.json</code>. It checks source versions before rerunning.</p><p>Audit identity: <code>{report['audit_id']}</code></p><p>Recorded: {escape(report['created_at'])}</p><p>Review mode: {escape(report['review']['mode'])}. No authenticated identity or digital signature is claimed.</p><p>{escape(report['evaluation_status'])}</p>
</main></body></html>"""


def save_report(report, directory):
    verify_payload(report)
    directory = Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    timestamp = datetime.fromisoformat(report["created_at"]).strftime("%Y%m%dT%H%M%S%fZ")
    record_id = f"{report['audit_id']}-{timestamp}"
    json_path, html_path = directory/f"{record_id}.json", directory/f"{record_id}.html"
    # Exclusive writes preserve earlier snapshots. Digest checking detects accidental edits,
    # but a person who can rewrite both the record and digest can forge it.
    with json_path.open("x",encoding="utf-8") as target:
        json.dump(report,target,indent=2,allow_nan=False)
        target.write("\n")
    with html_path.open("x",encoding="utf-8") as target:
        target.write(report_html(report))
    return {"record_id":record_id,"json_path":str(json_path),"html_path":str(html_path)}


def read_report(path):
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    verify_payload(report)
    return report


def list_reports(directory):
    summaries = []
    for path in Path(directory).glob("*.json"):
        if not RECORD_ID.fullmatch(path.stem):
            continue
        try:
            report = read_report(path)
            summaries.append({"record_id":path.stem,"example_title":report["example_title"],
                              "created_at":report["created_at"],"verdict":report["verdict"],
                              "contract_sha256":report["contract_sha256"],"audit_id":report["audit_id"]})
        except (ValueError, KeyError, OSError):
            continue
    return sorted(summaries,key=lambda r:r["created_at"],reverse=True)


def compare_reports(old, new):
    verify_payload(old);verify_payload(new)
    fields = sorted(set(old["contract"])|set(new["contract"]))
    changes = [{"field":key,"before":old["contract"].get(key),"after":new["contract"].get(key)}
               for key in fields if old["contract"].get(key)!=new["contract"].get(key)]
    old_checks = {check["id"]: check for check in old["checks"]}
    new_checks = {check["id"]: check for check in new["checks"]}
    check_changes = []
    for identity in sorted(set(old_checks) | set(new_checks)):
        before, after = old_checks.get(identity), new_checks.get(identity)
        def measurements(check):
            if check is None:
                return {}
            values = {key: check[key] for key in ("max_relative_residual", "observed_orders") if key in check}
            if check.get("runs"):
                finest = min(check["runs"], key=lambda run: run["dt_seconds"])
                for key in ("dt_seconds", "max_state_error", "max_abs_energy_change_fraction"):
                    values["finest_" + key] = finest[key]
            return values
        previous, current = measurements(before), measurements(after)
        measurement_changes = [{"metric": key, "before": previous.get(key), "after": current.get(key)}
                               for key in sorted(set(previous) | set(current))
                               if previous.get(key) != current.get(key)]
        check_changes.append({"evidence_id": identity,
                              "previous_status": before["status"] if before else None,
                              "new_status": after["status"] if after else None,
                              "measurement_changes": measurement_changes})
    return {"contract_changes":changes,
            "candidate_source_changed":old["candidate_source"]["source_sha256"]!=new["candidate_source"]["source_sha256"],
            "verification_sources_changed":old["verification_sources"]!=new["verification_sources"],
            "previous_verdict":old["verdict"],"new_verdict":new["verdict"],
            "previous_provider":old["model_mode"],"new_provider":new["model_mode"],
            "check_changes":check_changes,
            "not_tested_before":old["not_tested"],"not_tested_after":new["not_tested"],
            "coverage_note":"An earlier audit supports only its own contract and source versions. This comparison does not infer physical change impact."}
