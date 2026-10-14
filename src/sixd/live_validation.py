"""Explicit, budget-limited forced action validation; never a fixture fallback."""
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import Lock
from uuid import uuid4
import json
import math
import os

from .examples import EXAMPLES
from .investigation import investigate
from .kernel import audit
from .providers import BudgetLedger, LiveConfig, ProviderError, TokenFactoryProvider
from .reporting import save_report, verify_payload


SESSION_CAP_USD = 0.10
MAX_RESERVATIONS = 10
CASES = ('euler_method_limit', 'force_sign_error')
PROFILES = (('native_no_thinking', 2048),)
SELECTION_PROTOCOL = 'forced_action_v1'
WIRE_TOOL = 'select_next_action'
OPERATOR_ERROR_CODES = frozenset((
    'check_arguments_not_empty', 'duplicate_check_batch', 'check_already_executed',
    'finish_must_be_alone', 'finish_before_checks', 'finish_evidence_mismatch',
    'invalid_action_selection',
))
SESSION_STOP_PREFIXES = (
    'Usage exceeded the configured reservation bound;',
    'The approved inference allowance is exhausted.',
    'The live validation session allowance is exhausted.',
    'The ledger approval/cap differs;',
    'The budget ledger could not be locked or written.',
    'Nebius request failed: HTTP 401.',
    'Nebius request failed: HTTP 402.',
    'Nebius request failed: HTTP 403.',
    'Nebius request failed: HTTP 429.',
    'Nebius request timed out.',
    'Nebius network connection failed.',
    'Nebius TLS connection failed.',
    'Inference transport failed;',
)


class SessionBudget:
    """Add a small session ceiling without replacing the durable approved ledger."""
    def __init__(self, ledger, cap=SESSION_CAP_USD):
        self.ledger, self.cap, self.reserved = ledger, cap, 0.0
        self.reservations = 0
        self._lock = Lock()

    def reserve(self, config, amount):
        if (type(amount) not in (int, float) or not math.isfinite(amount) or amount < 0):
            raise ProviderError('Invalid validation reservation. No request was sent.')
        with self._lock:
            if self.reservations >= MAX_RESERVATIONS or self.reserved + amount > self.cap:
                raise ProviderError('The live validation session allowance is exhausted. No request was sent.')
            self.ledger.reserve(config, amount)
            self.reserved += amount
            self.reservations += 1


def safe_diagnostic(record):
    """Copy only bounded response facts, never remote text or exception details."""
    if not isinstance(record, dict):
        return {}
    result = {}
    if record.get('finish_reason') in ('length', 'stop', 'tool_calls', 'content_filter',
                                       'function_call', 'unknown'):
        result['finish_reason'] = record['finish_reason']
    for key in ('http_status', 'max_output_tokens', 'prompt_tokens',
                'completion_tokens', 'total_tokens'):
        value = record.get(key)
        if type(value) is int and 0 <= value <= 10_000_000:
            result[key] = value
    usage = record.get('usage')
    if isinstance(usage, dict):
        result['usage'] = {key: usage[key] for key in
                           ('prompt_tokens', 'completion_tokens', 'total_tokens')
                           if type(usage.get(key)) is int and 0 <= usage[key] <= 10_000_000}
        details = usage.get('completion_tokens_details')
        if (isinstance(details, dict) and type(details.get('reasoning_tokens')) is int and
                0 <= details['reasoning_tokens'] <= result['usage'].get('completion_tokens', -1)):
            result['usage']['completion_tokens_details'] = {'reasoning_tokens': details['reasoning_tokens']}
    if (isinstance(record.get('inference_profile'), str) and
            record['inference_profile'] in {profile for profile, _ in PROFILES}):
        result['inference_profile'] = record['inference_profile']
    if record.get('selection_protocol') in ('native_tools_v1', SELECTION_PROTOCOL):
        result['selection_protocol'] = record['selection_protocol']
    return result


def update_profile(path, original, profile, limit):
    """Commit a validated profile atomically, preserving every unrelated setting."""
    if json.loads(path.read_text(encoding='utf-8')) != original:
        raise ValueError('Configuration changed while validation ran.')
    revised = dict(original, inference_profile=profile, max_output_tokens=limit,
                   selection_protocol=SELECTION_PROTOCOL)
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as target:
            json.dump(revised, target, indent=2, allow_nan=False)
            target.write('\n')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def validate_live(root, *, accept_contract=False):
    """Validate one forced action protocol across two cases with one private key entry."""
    if accept_contract is not True:
        for name in CASES:
            print('Constructed case:', name)
            print(json.dumps(EXAMPLES[name].contract.record(), indent=2))
        print('Review both constructed example contracts, then use --accept-contract. No request was sent.')
        return 2
    if not os.environ.get('NEBIUS_API_KEY'):
        print('The private local key is missing. No request was sent.')
        return 2
    root = Path(root)
    config_path = root / '.local' / 'token-factory.json'
    try:
        config = LiveConfig.load(config_path)
        original = json.loads(config_path.read_text(encoding='utf-8'))
    except (ProviderError, OSError, ValueError):
        print('Local account, model and approved-budget configuration is unavailable or invalid. No request was sent.')
        return 2
    budget = SessionBudget(BudgetLedger(root / '.local' / 'budget.sqlite3'))
    output = root / 'artifacts' / 'provider-validation'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    summary = {'schema': 'sixd.provider_validation.v1', 'created_at':
               datetime.now(timezone.utc).isoformat(), 'cases': list(CASES),
               'model': config.model, 'base_url': config.base_url,
               'contract_sha256': {name: EXAMPLES[name].contract.sha256 for name in CASES},
               'session_cap_usd': SESSION_CAP_USD, 'max_request_reservations': MAX_RESERVATIONS,
               'global_spend_cap_usd': config.spend_cap_usd,
               'selection_protocol': SELECTION_PROTOCOL, 'wire_tool': WIRE_TOOL,
               'profiles': [{'inference_profile': profile, 'max_output_tokens': limit}
                            for profile, limit in PROFILES],
               'source_versions': {name: sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                   for name in ('live_validation.py', 'providers.py', 'investigation.py',
                                                'action_selection.py', 'reporting.py')},
               'attempts': [], 'state': 'failed', 'configuration_updated': False,
               'claim_boundary': 'Forced action protocol validation on two constructed numerical examples; not model quality or whole-mission validation. The native_no_thinking profile previously produced short accepted responses; its name describes requested settings, not proof of reasoning being disabled.'}
    print('Live validation: one forced action-selection protocol; no profile matrix, transport retries or fixture fallback.')
    print('Session ceiling: $0.10 and 10 request reservations within the existing approved cumulative allowance.')
    try:
        stop_session = False
        for profile, limit in PROFILES:
            selected = replace(config, inference_profile=profile, max_output_tokens=limit,
                               selection_protocol=SELECTION_PROTOCOL)
            print(f'Profile: {profile}; selection protocol: {SELECTION_PROTOCOL}; output ceiling: {limit} tokens.')
            completed_cases = []
            for name in CASES:
                if budget.reservations >= MAX_RESERVATIONS:
                    break
                example = EXAMPLES[name]
                print('Constructed case:', name)
                provider = TokenFactoryProvider(selected, budget)
                report = investigate(example, provider, max_turns=5,
                    review={'mode': 'operator_acknowledged_cli', 'human_acceptance_claimed': True,
                            'authenticated_identity': False})
                verify_payload(report)
                baseline = audit(example)
                if any(report.get(field) != baseline[field] for field in
                       ('checks', 'verdict', 'summary', 'audit_id', 'not_tested', 'contract_sha256')):
                    raise ValueError('The live result differs from its independent audit.')
                paths = save_report(report, output)
                run = report['investigation']
                state = run.get('state') if run.get('state') in (
                    'completed', 'failed', 'incomplete', 'blocked_contract') else 'invalid'
                attempt = {'inference_profile': profile, 'max_output_tokens': limit, 'case': name,
                           'selection_protocol': SELECTION_PROTOCOL, 'wire_tool': WIRE_TOOL,
                           'state': state, 'record_id': paths['record_id'],
                           'evidence_json': paths['json_path'], 'kernel_verdict': report['verdict'],
                           'live_request_attempts': run.get('live_request_attempts', 0),
                           'accepted_live_responses': report.get('live_model_calls', 0),
                           'failed_provider_response': safe_diagnostic(run.get('failed_provider_response')),
                           'operator_error_codes': sorted({event.get('error_code') for event in run.get('trace', [])
                                                           if isinstance(event, dict) and isinstance(event.get('error_code'), str) and
                                                           event.get('error_code') in OPERATOR_ERROR_CODES})}
                summary['attempts'].append(attempt)
                print(f'Investigation: {state}; accepted live responses: {attempt["accepted_live_responses"]}; '
                      f'request attempts: {attempt["live_request_attempts"]}.')
                if attempt['failed_provider_response']:
                    print('Controlled provider diagnostic:', json.dumps(attempt['failed_provider_response']))
                if attempt['operator_error_codes']:
                    print('Controlled operator error codes:', ', '.join(attempt['operator_error_codes']))
                print('Evidence JSON:', paths['json_path'])
                error = run.get('error')
                if isinstance(error, str) and error.startswith(SESSION_STOP_PREFIXES):
                    stop_session = True
                    print('Session stopped: a budget, account or transport boundary requires review. No further request will run.')
                    break
                completed = (state == 'completed' and provider.mode == 'live_token_factory' and
                             report.get('model_mode') == 'live_token_factory' and
                             type(report.get('live_model_calls')) is int and report['live_model_calls'] > 0 and
                             type(run.get('live_request_attempts')) is int and run['live_request_attempts'] > 0 and
                             run.get('model') == selected.model and run.get('inference_profile') == profile and
                             run.get('selection_protocol') == SELECTION_PROTOCOL)
                if not completed:
                    break
                completed_cases.append(name)
            if completed_cases == list(CASES):
                summary['state'] = 'completed'
                summary['successful_profile'] = profile
                update_profile(config_path, original, profile, limit)
                summary['configuration_updated'] = True
                print('Both live end-to-end investigations completed. The validated action protocol is now saved locally.')
                break
            if stop_session or budget.reservations >= MAX_RESERVATIONS:
                break
        if summary['state'] != 'completed':
            print('The action protocol did not complete both live cases. The active configuration remains unchanged.')
    except (ProviderError, OSError, ValueError, TypeError, KeyError, ArithmeticError):
        summary['state'] = 'failed'
        print('Validation stopped on a configuration, evidence, budget or local storage error. Private details were suppressed.')
    finally:
        summary['session_reserved_usd'] = budget.reserved
        summary['request_reservations'] = budget.reservations
        try:
            output.mkdir(parents=True, exist_ok=True)
            path = output / ('validation-' + stamp + '.json')
            with path.open('x', encoding='utf-8') as target:
                json.dump(summary, target, indent=2, allow_nan=False)
                target.write('\n')
            print('Validation summary JSON:', path)
        except (OSError, ValueError, TypeError):
            print('The validation summary could not be saved. Private details were suppressed.')
            summary['state'] = 'failed'
    return 0 if summary['state'] == 'completed' and summary['configuration_updated'] else 2
