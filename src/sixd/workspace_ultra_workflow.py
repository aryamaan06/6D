"""A fresh six-case Ultra screen, separate from historical selection proof.

Preparation and status are offline. Only an explicitly authorised start obtains
the owner's private session, and every request shares its existing ledger.
"""
from copy import deepcopy
from dataclasses import replace
import json
import threading
from time import perf_counter
from uuid import uuid4

from .explanation_quality import evaluate_explanation
from .model_evaluation import (CANDIDATES, SETTINGS, _ObservedProvider,
    build_evaluation_plan, score_receipt, validate_evaluation_plan)
from .project_investigation import ProjectActionAdapter, investigate_project
from .providers import BudgetLedger, ERROR_CODES, ProviderError, TokenFactoryProvider
from .workspace import ConflictError, WorkspaceError
from .workspace_ai import JobBudget, _digest, _encode, _now
from .workspace_evaluation import BatchBudget
from .workspace_workflow_evaluation import WorkflowEvaluation

CAP_USD = 2.10
MAX_REQUESTS = 36
PLAN_SCHEMA = 'sixd.ultra-six-plan.v1'
REPORT_SCHEMA = 'sixd.ultra-six-report.v1'
ULTRA = next(deepcopy(c) for c in CANDIDATES if c['id'] == 'ultra')
STOP_CODES = {'cumulative_budget_exhausted', 'case_budget_exhausted',
    'batch_budget_exhausted', 'request_limit', 'budget_ledger_error',
    'session_changed', 'budget_approval_mismatch', 'budget_reservation_invalid',
    'configuration_error', 'verification_sources_changed', 'recheck_mismatch'}


def build_plan(*, temporary_root):
    pack = build_evaluation_plan(temporary_root=temporary_root)
    validate_evaluation_plan(pack)
    plan = {'schema': PLAN_SCHEMA, 'state': 'prepared_offline', 'live_calls': 0,
        'case_pack': pack, 'candidate': deepcopy(ULTRA), 'settings': deepcopy(SETTINGS),
        'batch_cap_usd': CAP_USD, 'max_request_reservations': MAX_REQUESTS,
        'automatic_retries': 0, 'active_model_changed': False,
        'coverage_limit': 'Six constructed development cases; not customer, flight or independent human validation.'}
    plan['plan_digest'] = _digest(plan)
    return plan


def validate_plan(plan, *, require_current_sources=True):
    if (not isinstance(plan, dict) or plan.get('schema') != PLAN_SCHEMA
            or plan.get('plan_digest') != _digest({k:v for k,v in plan.items() if k != 'plan_digest'})
            or plan.get('candidate') != ULTRA or plan.get('settings') != SETTINGS
            or plan.get('batch_cap_usd') != CAP_USD
            or plan.get('max_request_reservations') != MAX_REQUESTS
            or plan.get('automatic_retries') != 0 or plan.get('active_model_changed') is not False):
        raise ValueError('Use an intact Ultra six-case plan.')
    validate_evaluation_plan(plan.get('case_pack'), require_current_sources=require_current_sources)
    return True


def _must_stop(row):
    if row.get('error_code') in STOP_CODES:
        return True
    diagnostic = (row.get('receipt') or {}).get('provider_diagnostic') or row.get('provider_diagnostic') or {}
    return diagnostic.get('http_status') in {401, 403}


def run_cases(plan, provider_factory, *, mode='offline', on_case=None):
    """Try each independent case once; a rejected explanation is not a retry.

    Authentication, source/session and budget failures stop further requests.
    Other bounded model failures remain failed while untouched cases are tried.
    """
    validate_plan(plan)
    if mode not in {'offline', 'live'}:
        raise ValueError('Choose an explicit offline or live screen.')
    rows, stopped = [], False
    for case in plan['case_pack']['cases']:
        if stopped:
            row = {'candidate_id': 'ultra', 'case_id': case['id'], 'case_digest': case['case_digest'],
                'state': 'not_run', 'reason': 'session_or_budget_stopped', 'live_model_calls': 0,
                'request_reservations': 0, 'reserved_usd': 0, 'score': None, 'receipt': None}
        else:
            try:
                candidate = {**deepcopy(ULTRA), 'settings': deepcopy(SETTINGS)}
                provider = provider_factory(candidate, deepcopy(case))
                provider_mode = getattr(provider, 'mode', '')
                if mode == 'offline' and not provider_mode.startswith('offline_'):
                    raise ValueError('Offline screening requires an explicitly offline provider.')
                if mode == 'live' and (provider_mode != 'live_token_factory' or provider.model != ULTRA['model']):
                    raise ValueError('Live screening requires the exact Ultra model and Token Factory provider.')
                config = getattr(provider, 'config', None)
                if mode == 'live' and any(getattr(config, key, None) != SETTINGS[key] for key in
                        ('max_output_tokens', 'inference_profile', 'selection_protocol')):
                    raise ValueError('The live settings differ from the declared fixed plan.')
                observed = _ObservedProvider(provider)
                start = perf_counter()
                receipt = investigate_project(deepcopy(case['view']), case['requirement_id'],
                    case['question'], observed, investigation_id='ultra-six-' + case['id'])
                ledger = getattr(provider, 'ledger', None)
                row = {'candidate_id': 'ultra', 'case_id': case['id'], 'case_digest': case['case_digest'],
                    'state': receipt['state'], 'provider_mode': provider_mode,
                    'actual_provider_model': receipt['model'], 'elapsed_seconds': perf_counter() - start,
                    'score': score_receipt(case, receipt, evaluate_explanation), 'receipt': receipt,
                    'request_digests': observed.request_digests, 'usage': observed.usage,
                    'live_model_calls': receipt['live_model_calls'],
                    'request_reservations': getattr(ledger, 'count', 0),
                    'reserved_usd': getattr(ledger, 'reserved', 0),
                    'error_code': receipt.get('error_code'), 'billed_cost_usd': None}
            except ProviderError as error:
                row = {'candidate_id': 'ultra', 'case_id': case['id'], 'case_digest': case['case_digest'],
                    'state': 'failed', 'reason': 'provider_factory_rejected',
                    'error_code': error.code if error.code in ERROR_CODES else None,
                    'provider_diagnostic': error.diagnostic, 'live_model_calls': 0,
                    'request_reservations': 0, 'reserved_usd': 0, 'score': None, 'receipt': None}
            stopped = _must_stop(row)
        rows.append(row)
        if on_case is not None and on_case(deepcopy(row)) is False:
            stopped = True
    report = {'schema': REPORT_SCHEMA, 'plan_digest': plan['plan_digest'],
        'mode': 'live_screen' if mode == 'live' else 'offline_harness_validation',
        'candidate': deepcopy(ULTRA), 'settings': deepcopy(SETTINGS), 'rows': rows,
        'created_at': _now(), 'live_calls': sum(r['live_model_calls'] for r in rows),
        'active_model_changed': False, 'automatic_retries': 0,
        'coverage_limit': plan['coverage_limit'], 'manual_review': 'pending'}
    report['report_digest'] = _digest(report)
    return report


def scorecard(report):
    rows = report.get('rows', [])
    return {'planned': 6, 'attempted': sum(r['state'] != 'not_run' for r in rows),
        'completed': sum(r['state'] == 'completed' for r in rows),
        'failed': sum(r['state'] == 'failed' for r in rows),
        'not_run': max(0, 6 - sum(r['state'] != 'not_run' for r in rows)),
        'workflow_passes': sum(bool((r.get('score') or {}).get('workflow_gate_pass')) for r in rows),
        'semantic_accuracy_established': False, 'human_review': 'pending',
        'cases': [{'case_id': r['case_id'], 'state': r['state'],
            'workflow_pass': (r.get('score') or {}).get('workflow_gate_pass'),
            'error_code': r.get('error_code') or (r.get('receipt') or {}).get('error_code')}
            for r in rows]}


def preflight(plan, config):
    budgets = []

    class Forecast:
        def __init__(self): self.count, self.reserved = 0, 0.0
        def reserve(self, config, amount): self.count += 1; self.reserved += amount

    def factory(candidate, case):
        ledger = Forecast(); budgets.append((case['id'], ledger))
        cfg = replace(config, model=ULTRA['model'],
            input_usd_per_million_ceiling=ULTRA['input_usd_per_million'],
            output_usd_per_million_ceiling=ULTRA['output_usd_per_million'],
            max_output_tokens=SETTINGS['max_output_tokens'],inference_profile=SETTINGS['inference_profile'],
            selection_protocol=SETTINGS['selection_protocol'])

        def transport(request):
            menu = json.loads(json.loads(request.data)['messages'][-1]['content'])
            available = {item['action'] for item in menu['available_actions']}
            action = next(name for name in ('read_requirement','read_model','read_changes','recheck_model','finish') if name in available)
            args = {'action': action, 'evidence_ids': menu['recorded_evidence_ids'] if action == 'finish' else [],
                'summary': 'Review the recorded criterion within the bounded model scope and its stated assumptions. Obtain applicable missing analysis before extending these supplied component findings.' if action == 'finish' else ''}
            return {'choices':[{'finish_reason':'tool_calls','message':{'role':'assistant','content':None,
                'tool_calls':[{'id':'offline-ultra-six-'+action,'type':'function',
                'function':{'name':'select_next_action','arguments':json.dumps(args)}}]}}],
                'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}
        return TokenFactoryProvider(cfg, ledger, api_key='synthetic-ultra-six-capacity-only',
            transport=transport, action_adapter=ProjectActionAdapter())

    report = run_cases(plan, factory, mode='offline')
    cases = [{'case_id': identity, 'requests': ledger.count,
        'forecast_reservation_usd': ledger.reserved, 'with_headroom_usd': ledger.reserved * 1.15,
        'fits_case_cap': ledger.count <= 6 and ledger.reserved * 1.15 <= ULTRA['per_case_cap_usd']}
        for identity, ledger in budgets]
    total = sum(row['with_headroom_usd'] for row in cases)
    return {'schema':'sixd.ultra-six-capacity.v1','live_calls':0,'cases':cases,
        'forecast_with_headroom_usd':total,'batch_cap_usd':CAP_USD,
        'request_reservations':sum(r['requests'] for r in cases),'max_request_reservations':MAX_REQUESTS,
        'fits':len(cases)==6 and all(r['fits_case_cap'] for r in cases) and total <= CAP_USD
            and sum(r['requests'] for r in cases) <= MAX_REQUESTS
            and all(r['state']=='completed' for r in report['rows'])}


class UltraWorkflow(WorkflowEvaluation):
    TABLE = 'ultra_workflow_screens'

    def prepare(self):
        plan = build_plan(temporary_root=self.ai.local / 'evaluation-work')
        forecast = preflight(plan, self.ai._config('ultra'))
        return {'schema':'sixd.ultra-six-preparation.v1','state':'prepared_offline',
            'live_calls':0,'plan':plan,'capacity_preflight':forecast,'active_model_changed':False}

    def status(self):
        with self.ai._db() as db:
            row = db.execute(f'SELECT * FROM {self.TABLE} ORDER BY created_at DESC LIMIT 1').fetchone()
        record = self._read(row) if row else None
        latest = None
        if record:
            latest = {key:record.get(key) for key in ('comparison_id','state','created_at','completed_at',
                'reserved_usd','request_reservations','error','provider_mode')}
            latest['current_sources_match'] = record.get('agent_sources') == self.ai._runtime and self.ai._sources() == self.ai._runtime
        return {'schema':'sixd.ultra-six-status.v1','model':ULTRA['model'],'case_count':6,
            'batch_cap_usd':CAP_USD,'max_request_reservations':MAX_REQUESTS,
            'max_case_requests':6,'case_cap_usd':ULTRA['per_case_cap_usd'],
            'latest':latest,'scorecard':scorecard(record.get('report') or {'rows':record.get('rows',[])}) if record else None,
            'automatic_model_selection':False,'automatic_retries':0,
            'note':'Fresh six-case Ultra workflow screen. Historical comparisons and default selection remain unchanged; semantic and independent human review remain separate.'}

    def start(self, *, allow_spend, allowance_usd):
        if allow_spend is not True or type(allowance_usd) not in (int,float) or allowance_usd != CAP_USD:
            raise WorkspaceError('Explicitly authorise the fixed USD2.10 Ultra six-case ceiling inside the existing allowance.')
        prepared = self.prepare()
        if not prepared['capacity_preflight']['fits']:
            raise ConflictError('The offline Ultra forecast exceeds its fixed ceilings. No request was sent.')
        if self.ai._budget(self.ai._config())['remaining_usd'] < CAP_USD:
            raise ConflictError('The existing cumulative allowance cannot cover this screen ceiling.')
        identity = uuid4().hex
        config, key, epoch = self.ai.begin_comparison(identity)
        try:
            record = {'schema':'sixd.ultra-six-record.v1','comparison_id':identity,
                'created_at':_now(),'completed_at':None,'state':'queued','owner':self.ai.owner,
                'plan':prepared['plan'],'capacity_preflight':prepared['capacity_preflight'],
                'agent_sources':self.ai._runtime,'provider_mode':self.ai._provider_mode,
                'batch_cap_usd':CAP_USD,'max_request_reservations':MAX_REQUESTS,
                'budget_before':self.ai._budget(config),'rows':[],'report':None,'error':None,
                'reserved_usd':0.0,'request_reservations':0,'active_model_changed':False}
            with self.ai._db() as db:
                db.execute(f'INSERT INTO {self.TABLE} VALUES (?,?,?,?,?,?)',
                    (identity,record['created_at'],'queued',self.ai.owner,_encode(record),_digest(record)))
            threading.Thread(target=self._run,args=(deepcopy(record),config,key,epoch),daemon=True).start()
            return {'comparison_id':identity,'state':'queued','batch_cap_usd':CAP_USD}
        except Exception:
            self.ai.finish_comparison(identity)
            raise

    def _run(self, record, config, key, epoch):
        identity = record['comparison_id']

        def check():
            self.ai.check_comparison_session(identity,epoch)
            with self.ai._db() as db:
                row = db.execute(f'SELECT owner,state FROM {self.TABLE} WHERE comparison_id=?',(identity,)).fetchone()
            if not row or row['owner'] != self.ai.owner or row['state'] not in {'queued','running'}:
                raise ProviderError('The Ultra screen was interrupted.',code='session_changed')

        batch = BatchBudget(BudgetLedger(self.ai.local/'budget.sqlite3'),check,self.ai._lock,
            cap_usd=CAP_USD,max_requests=MAX_REQUESTS)
        try:
            record['state']='running';self._save(record)

            def factory(candidate, case):
                check()
                cfg = replace(config,model=ULTRA['model'],
                    input_usd_per_million_ceiling=ULTRA['input_usd_per_million'],
                    output_usd_per_million_ceiling=ULTRA['output_usd_per_million'],
                    max_output_tokens=SETTINGS['max_output_tokens'],inference_profile=SETTINGS['inference_profile'],
                    selection_protocol=SETTINGS['selection_protocol'])
                budget = JobBudget(batch,check_session=check,request_lock=self.ai._lock,
                    max_reservation_usd=ULTRA['per_case_cap_usd'])
                return self.ai._factory(cfg,budget,key)

            def progress(row):
                record['rows'].append(row)
                record.update(reserved_usd=batch.reserved,request_reservations=batch.count)
                self._save(record);check()
                return batch.count < MAX_REQUESTS and batch.reserved < CAP_USD

            report = run_cases(record['plan'],factory,
                mode='live' if self.ai._provider_mode=='live_token_factory' else 'offline',on_case=progress)
            check()
            record.update(report=report,rows=report['rows'],state='completed',completed_at=_now())
        except Exception:
            record.update(state='failed',completed_at=_now(),
                error='The Ultra screen stopped; saved partial evidence remains. No retry, fallback or default-model change occurred.')
        finally:
            record.update(reserved_usd=batch.reserved,request_reservations=batch.count)
            try:self._save(record)
            finally:self.ai.finish_comparison(identity)
