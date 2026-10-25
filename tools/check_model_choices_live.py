"""Explicit bounded live check through the owner API; never handles a key.

The initial pass creates one labelled constructed project and R2, then at most
nine jobs. Explicit correction modes retain earlier accounting; admission checks
bound all attempts together to USD1.95 and the approved 54/60-request family cap.
No automatic retry, fallback, allowance reset or model-default change occurs.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd.project_examples import example_projects

CEILING = Decimal('1.95')
CASES = (
    ('limit-only-change', 'thermal_limit',
     'Explain the saved thermal finding and the limit-only revision. Distinguish the changed threshold from unchanged physical output. Give concrete next engineering checks using only captured evidence.'),
    ('unsupported-control', 'control_tracking',
     'Explain why this requirement is not assessed and which specific evidence or specialist analysis is needed. Do not treat missing analysis as evidence that the vehicle fails.'),
    ('whole-project', None,
     'Review all saved findings and the limit-only change. Separate unmet criteria from unassessed scope and explain concrete next checks using only captured evidence. Do not claim launch readiness.'),
)


def progress(value):
    """A closed console must not interrupt accounting or lose a saved receipt."""
    try:
        print(json.dumps(value), flush=True)
    except (BrokenPipeError, OSError):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-spend', action='store_true')
    parser.add_argument('--max-reservation-usd', default='0')
    parser.add_argument('--base-url', default='http://127.0.0.1:8768')
    parser.add_argument('--prior-summary', type=Path,
        help='Carry forward an earlier preserved attempt within the SAME USD1.95 ceiling.')
    parser.add_argument('--correction-pass', action='store_true',
        help='Explicit targeted current-source pass: Nano/Super whole project and all three Ultra cases.')
    parser.add_argument('--single-super-check', action='store_true',
        help='One explicitly approved Super whole-project verification; prior receipts required.')
    parser.add_argument('--request-ceiling', type=int, choices=(54, 60), default=54)
    args = parser.parse_args()
    if not args.allow_spend or Decimal(args.max_reservation_usd) != CEILING:
        parser.error('Explicit --allow-spend --max-reservation-usd 1.95 is required.')
    if args.single_super_check and (not args.prior_summary or args.correction_pass or args.request_ceiling != 60):
        parser.error('The single Super check requires prior accounting and explicit --request-ceiling 60.')
    if args.request_ceiling != 54 and not args.single_super_check:
        parser.error('Only the separately approved single Super check may use the 60-request family ceiling.')
    parsed = urlparse(args.base_url)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.username
            or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        parser.error('Only an explicit loopback owner server is supported.')
    base = args.base_url.rstrip('/')

    def api(route, payload=None):
        request = Request(base + route, data=None if payload is None else json.dumps(payload).encode(),
            headers={'Origin': base, 'Content-Type': 'application/json'})
        with urlopen(request, timeout=60) as response:
            return json.load(response)

    status = api('/api/ai/status')
    choices = {row['id']: row for row in status.get('available_models', [])}
    if (set(choices) != {'nano', 'super', 'ultra'} or not status.get('configured')
            or not status.get('key_present') or status.get('provider_mode') != 'live_token_factory'):
        raise RuntimeError('All three choices and a private live connection must be ready.')
    forecast = sum(Decimal(str(row['max_job_reservation_usd'])) * len(CASES) for row in choices.values())
    if forecast != CEILING or any(row['max_job_requests'] != 6 for row in choices.values()):
        raise RuntimeError('The captured job ceilings do not match the fixed batch.')
    if Decimal(str(status['budget']['remaining_usd'])) < CEILING:
        raise RuntimeError('The unchanged cumulative allowance cannot cover the fixed batch.')
    health = api('/health')
    if health.get('restart_required'):
        raise RuntimeError('Restart the current server before the live check.')
    family_initial = Decimal(str(status['budget']['reserved_usd']))
    prior_requests = 0
    if args.correction_pass and not args.prior_summary:
        raise RuntimeError('A targeted correction must carry forward the original receipts and limits.')
    if args.prior_summary:
        previous_path = args.prior_summary.resolve()
        if not previous_path.is_relative_to((ROOT/'work'/'model-choice-live').resolve()):
            raise RuntimeError('Prior summaries must come from the private model-choice receipt directory.')
        previous = json.loads(previous_path.read_text(encoding='utf-8'))
        if previous.get('schema') != 'sixd.model-choice-live-check.v1' or previous.get('batch_max_reservation_usd') != float(CEILING):
            raise RuntimeError('The earlier attempt does not use this fixed ceiling.')
        family_initial = Decimal(str(previous.get('family_initial_reserved_usd', previous['budget_before']['reserved_usd'])))
        if not family_initial.is_finite() or not 0 <= family_initial <= Decimal(str(status['budget']['reserved_usd'])):
            raise RuntimeError('Earlier accounting cannot be reconciled with the current shared ledger.')
        prior_requests = previous.get('family_request_reservations',
            sum(row.get('request_reservations') or 0 for row in previous['rows']))
        if type(prior_requests) is not int or not 0 <= prior_requests <= args.request_ceiling:
            raise RuntimeError('The earlier request reservations are invalid.')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder = ROOT / 'work' / 'model-choice-live' / stamp
    folder.mkdir(parents=True)
    examples = example_projects()
    project = deepcopy(examples['baseline'])
    project.update(project_id='model-choice-check-' + stamp.lower(),
        name='Model choice checks (constructed)', revision='1')
    missing = examples['missing_evidence']
    project['inputs']['maximum_tracking_error'] = deepcopy(missing['inputs']['maximum_tracking_error'])
    project['models'].append(deepcopy(next(m for m in missing['models'] if m['id'] == 'control')))
    project['requirements'].append(deepcopy(next(r for r in missing['requirements'] if r['id'] == 'control_tracking')))
    if args.single_super_check:
        project['project_id'] = previous['project_id']
        reviewed = api('/api/workspace?project_id=' + project['project_id'] + '&revision=2')
        if not reviewed.get('run'):
            raise RuntimeError('The earlier constructed saved calculation must remain current.')
    else:
        created = api('/api/projects', {'project': project})
        api('/api/run', {'project_id': project['project_id'], 'revision': 1})
        draft = deepcopy(created['project'])
        draft['inputs']['maximum_temperature']['value'] = 250
        api('/api/revisions', {'project_id': project['project_id'], 'base_revision': 1, 'project': draft})
        reviewed = api('/api/run', {'project_id': project['project_id'], 'revision': 2})
    findings = reviewed['run']['review']['findings']
    if findings['thermal_limit']['status'] != 'not_met' or findings['control_tracking']['status'] != 'not_assessed':
        raise RuntimeError('Constructed findings do not match the fixed expected outcomes.')
    result = {'schema': 'sixd.model-choice-live-check.v1', 'created_at': stamp,
        'build_id': health['build_id'], 'project_id': project['project_id'], 'revision': 2,
        'batch_max_reservation_usd': float(CEILING), 'batch_max_requests': args.request_ceiling,
        'family_initial_reserved_usd': float(family_initial),
        'prior_summary': str(args.prior_summary) if args.prior_summary else None,
        'prior_request_reservations': prior_requests,
        'planned': 1 if args.single_super_check else 5 if args.correction_pass else 9,
        'default_model_before': status['model'], 'budget_before': status['budget'], 'rows': [],
        'limitations': 'Constructed development cases; automated guards and separate AI review are not independent human engineering validation.'}
    path = folder / 'summary.json'

    def save():
        path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')

    save()
    for model in ('nano', 'super', 'ultra'):
        stopped = False
        for case_id, requirement_id, question in CASES:
            if args.single_super_check and (model != 'super' or case_id != 'whole-project'):
                continue
            if args.correction_pass and model != 'ultra' and case_id != 'whole-project':
                result['rows'].append({'model_choice': model, 'case_id': case_id,
                    'state': 'not_selected', 'reason': 'Earlier requirement completion retained; this targeted pass checks the current whole-project path.'})
                save()
                continue
            if stopped:
                result['rows'].append({'model_choice': model, 'case_id': case_id, 'state': 'not_run'})
                save()
                continue
            payload = {'project_id': project['project_id'], 'revision': 2, 'question': question, 'model_choice': model}
            payload.update({'scope': 'project'} if requirement_id is None else {'requirement_id': requirement_id})
            current = api('/api/ai/status')
            used = Decimal(str(current['budget']['reserved_usd'])) - family_initial
            used_requests = prior_requests + sum(row.get('request_reservations') or 0 for row in result['rows'])
            if used < 0 or used + Decimal(str(choices[model]['max_job_reservation_usd'])) > CEILING or used_requests + 6 > args.request_ceiling:
                result['rows'].append({'model_choice': model, 'case_id': case_id,
                    'state': 'not_run', 'reason': 'Remaining original batch capacity cannot cover this job ceiling.'})
                stopped = True
                save()
                continue
            progress({'model': model, 'case': case_id, 'state': 'starting'})
            record = api('/api/investigations', payload)
            identity = record['investigation_id']
            deadline = time.monotonic() + 360
            while record['state'] in {'queued', 'running'}:
                if time.monotonic() > deadline:
                    result['rows'].append({'model_choice': model, 'case_id': case_id,
                        'investigation_id': identity, 'state': 'pending_at_timeout'})
                    save()
                    raise RuntimeError('A live job is still active; no retry or next job was started.')
                time.sleep(.5)
                record = api('/api/investigations/' + identity)
            (folder / (model + '-' + case_id + '.json')).write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
            row = {key: record.get(key) for key in ('investigation_id', 'model', 'model_choice', 'state',
                'scope', 'live_model_calls', 'request_attempts', 'request_reservations', 'reserved_usd', 'error_code')}
            row['case_id'] = case_id
            result['rows'].append(row)
            stopped = record['state'] != 'completed'
            save()
            progress({'model': model, 'case': case_id, 'state': record['state'],
                'requests': record.get('request_reservations'), 'error_code': record.get('error_code')})
    final = api('/api/ai/status')
    result.update(default_model_after=final['model'], budget_after=final['budget'],
        reserved_usd=sum(Decimal(str(row.get('reserved_usd') or 0)) for row in result['rows']))
    result['reserved_usd'] = float(result['reserved_usd'])
    result['family_reserved_usd'] = float(Decimal(str(final['budget']['reserved_usd'])) - family_initial)
    result['family_request_reservations'] = prior_requests + sum(row.get('request_reservations') or 0 for row in result['rows'])
    result['completed'] = sum(row['state'] == 'completed' for row in result['rows'])
    if result['family_reserved_usd'] > float(CEILING) or result['family_request_reservations'] > args.request_ceiling or final['model'] != status['model']:
        raise RuntimeError('Batch accounting or default preservation needs review.')
    save()
    progress({'completed': result['completed'], 'planned': result['planned'],
        'reserved_usd': result['reserved_usd'], 'family_reserved_usd': result['family_reserved_usd'], 'summary_path': str(path)})
    return 0 if result['completed'] == result['planned'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
