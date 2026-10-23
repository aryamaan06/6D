"""Explicit current-model live qualification using the existing private session."""
from copy import deepcopy
import json
import re
import threading
from uuid import uuid4

from . import ai_qualification as pack
from .project_investigation import ProjectActionAdapter
from .providers import BudgetLedger, TokenFactoryProvider
from .workspace import ConflictError, WorkspaceError
from .workspace_ai import JobBudget, _digest, _encode, _now
from .workspace_evaluation import BatchBudget


def preflight(plan, config):
    """Exercise the full wire protocol offline, not a live performance result."""
    import json
    ledgers = []

    class Forecast:
        def __init__(self):
            self.count, self.reserved = 0, 0.0

        def reserve(self, config, amount):
            self.count += 1
            self.reserved += amount

    def factory(candidate, case):
        ledger = Forecast()
        ledgers.append((case['id'], ledger, candidate['per_case_cap_usd']))

        def transport(request):
            payload = json.loads(request.data)
            menu = json.loads(payload['messages'][-1]['content'])
            names = {item['action'] for item in menu['available_actions']}
            action = next(a for a in ('read_requirement', 'read_model', 'read_changes', 'recheck_model', 'finish') if a in names)
            args = {'action': action, 'evidence_ids': menu['recorded_evidence_ids'] if action == 'finish' else [],
                'summary': 'Review the captured finding, numerical support and model assumptions. Missing scope remains unresolved; obtain applicable independent analysis before extending this result.' if action == 'finish' else ''}
            return {'choices': [{'finish_reason': 'tool_calls', 'message': {'role': 'assistant', 'content': None,
                'tool_calls': [{'id': 'offline-capacity-' + action, 'type': 'function', 'function': {
                    'name': 'select_next_action', 'arguments': json.dumps(args)}}]}}],
                'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}

        return TokenFactoryProvider(config, ledger, api_key='synthetic-qualification-capacity-only',
            transport=transport, action_adapter=ProjectActionAdapter())

    report = pack.run_plan(plan, factory)
    rows = [{'case_id': identity, 'requests': ledger.count, 'with_headroom_usd': ledger.reserved * 1.15,
             'fits_case': ledger.count <= 6 and ledger.reserved * 1.15 <= cap}
            for identity, ledger, cap in ledgers]
    total = sum(row['with_headroom_usd'] for row in rows)
    return {'mode': 'offline_capacity_forecast', 'live_calls': 0, 'cases': rows,
        'forecast_with_headroom_usd': total,
        'fits': len(rows) == 4 and all(row['fits_case'] for row in rows) and total <= pack.CAP_USD
            and sum(row['requests'] for row in rows) <= pack.MAX_REQUESTS
            and all(row['state'] == 'completed' and row['score']['workflow_gate_pass'] for row in report['rows']),
        'note': 'Synthetic paths and fifteen percent headroom, not observed quality, latency or billed cost.'}


class WorkspaceQualification:
    TABLE = 'ai_qualifications'

    def __init__(self, ai):
        self.ai = ai
        with ai._db() as db:
            db.execute(f'''CREATE TABLE IF NOT EXISTS {self.TABLE} (
                qualification_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, state TEXT NOT NULL,
                owner TEXT NOT NULL, record TEXT NOT NULL, digest TEXT NOT NULL)''')
            for row in db.execute(f"SELECT * FROM {self.TABLE} WHERE state IN ('queued','running')").fetchall():
                record = self._read(row)
                record.update(state='interrupted', completed_at=_now(),
                    error='The server restarted. Partial evidence remains; no automatic retry was made.')
                self._write(db, record)

    @staticmethod
    def _read(row):
        value = json.loads(row['record'])
        report = value.get('report')
        if (_digest(value) != row['digest'] or value.get('qualification_id') != row['qualification_id']
                or value.get('state') != row['state']
                or report is not None and report.get('report_digest') != _digest({k: v for k, v in report.items() if k != 'report_digest'})):
            raise WorkspaceError('The saved qualification is inconsistent.')
        return value

    @classmethod
    def _write(cls, db, value):
        db.execute(f'UPDATE {cls.TABLE} SET state=?,record=?,digest=? WHERE qualification_id=?',
            (value['state'], _encode(value), _digest(value), value['qualification_id']))

    def get(self, identity):
        if not isinstance(identity, str) or not re.fullmatch(r'[a-f0-9]{32}', identity):
            raise WorkspaceError('Choose a valid saved qualification.')
        with self.ai._db() as db:
            row = db.execute(f'SELECT * FROM {self.TABLE} WHERE qualification_id=?', (identity,)).fetchone()
            if not row:
                raise WorkspaceError('Qualification not found.')
            return self._read(row)

    def _save(self, value):
        with self.ai._db() as db:
            row = db.execute(f'SELECT owner,state FROM {self.TABLE} WHERE qualification_id=?', (value['qualification_id'],)).fetchone()
            if row and row['owner'] == self.ai.owner and row['state'] in ('queued', 'running'):
                self._write(db, value)

    def status(self):
        with self.ai._db() as db:
            row = db.execute(f'SELECT * FROM {self.TABLE} ORDER BY created_at DESC LIMIT 1').fetchone()
        record = self._read(row) if row else None
        same = bool(record and record.get('agent_sources') == self.ai._runtime)
        latest = {k: record.get(k) for k in ('qualification_id', 'state', 'created_at', 'completed_at',
            'model', 'reserved_usd', 'request_reservations', 'error', 'provider_mode')} if record else None
        return {'schema': 'sixd.ai-qualification-status.v1', 'latest': latest,
            'cases': deepcopy(list(pack.CASE_INFO)), 'batch_cap_usd': pack.CAP_USD,
            'max_request_reservations': pack.MAX_REQUESTS,
            'current_sources_match': same and self.ai._sources() == self.ai._runtime,
            'scorecard': pack.scorecard(record) if record else None,
            'automatic_model_selection': False}

    def prepare(self):
        config = self.ai._config()
        plan = pack.build_plan(config, temporary_root=self.ai.local / 'evaluation-work')
        forecast = preflight(plan, config)
        return {'plan': plan, 'capacity_preflight': forecast, 'live_calls': 0}

    def start(self, *, allow_spend, allowance_usd):
        if allow_spend is not True or type(allowance_usd) not in (int, float) or allowance_usd != pack.CAP_USD:
            raise WorkspaceError('Explicitly authorize the fixed USD0.80 qualification ceiling within the existing allowance.')
        prepared = self.prepare()
        if not prepared['capacity_preflight']['fits']:
            raise ConflictError('Qualification does not fit its offline forecast. No request was sent.')
        if self.ai._budget(self.ai._config())['remaining_usd'] < pack.CAP_USD:
            raise ConflictError('Insufficient room in the cumulative allowance. No request was sent.')
        identity = uuid4().hex
        config, key, epoch = self.ai.begin_comparison(identity)
        try:
            if prepared['plan']['candidates'][0]['model'] != config.model:
                raise ConflictError('The selected model changed during preparation. No request was sent.')
            record = {'schema': 'sixd.ai-qualification.v1', 'qualification_id': identity,
                'state': 'queued', 'created_at': _now(), 'completed_at': None,
                'model': config.model, 'provider_settings': self.ai._settings(config),
                'agent_sources': self.ai._runtime, 'provider_mode': self.ai._provider_mode,
                'plan': prepared['plan'], 'capacity_preflight': prepared['capacity_preflight'],
                'batch_cap_usd': pack.CAP_USD, 'max_request_reservations': pack.MAX_REQUESTS,
                'reserved_usd': 0.0, 'request_reservations': 0, 'rows': [], 'report': None,
                'budget_before': self.ai._budget(config), 'error': None, 'active_model_changed': False}
            with self.ai._db() as db:
                db.execute(f'INSERT INTO {self.TABLE} VALUES (?,?,?,?,?,?)',
                    (identity, record['created_at'], 'queued', self.ai.owner, _encode(record), _digest(record)))
            threading.Thread(target=self._run, args=(deepcopy(record), config, key, epoch), daemon=True).start()
            return {'qualification_id': identity, 'state': 'queued', 'batch_cap_usd': pack.CAP_USD}
        except Exception:
            self.ai.finish_comparison(identity)
            raise

    def _run(self, record, config, key, epoch):
        identity = record['qualification_id']

        def check():
            self.ai.check_comparison_session(identity, epoch)

        batch = BatchBudget(BudgetLedger(self.ai.local / 'budget.sqlite3'), check, self.ai._lock,
            cap_usd=pack.CAP_USD, max_requests=pack.MAX_REQUESTS)
        try:
            record['state'] = 'running'
            self._save(record)

            def factory(candidate, case):
                check()
                budget = JobBudget(batch, check_session=check, request_lock=self.ai._lock,
                    max_reservation_usd=candidate['per_case_cap_usd'])
                return self.ai._factory(config, budget, key)

            def progress(row):
                record['rows'].append(row)
                record.update(reserved_usd=batch.reserved, request_reservations=batch.count)
                self._save(record)
                check()
                return True

            report = pack.run_plan(record['plan'], factory, on_case=progress,
                mode='live' if self.ai._provider_mode == 'live_token_factory' else 'offline')
            check()
            complete = all(row['state'] == 'completed' and row['score']['workflow_gate_pass'] for row in report['rows'])
            record.update(report=report, rows=report['rows'], state='completed' if complete else 'stopped', completed_at=_now())
        except Exception:
            record.update(state='failed', completed_at=_now(),
                error='Qualification stopped. Saved partial results remain; no retry or model fallback was made.')
        finally:
            record.update(reserved_usd=batch.reserved, request_reservations=batch.count)
            try:
                self._save(record)
            finally:
                self.ai.finish_comparison(identity)
