"""Bounded orchestration; only the deterministic kernel issues engineering findings."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json
from .contracts import digest
from .kernel import audit, force_experiment, refinement_experiment, reversal_experiment
from .providers import ProviderError


def tool(name, description, properties=None, required=None):
    return {'type': 'function', 'function': {'name': name, 'description': description,
            'parameters': {'type': 'object', 'properties': properties or {},
                           'required': required or [], 'additionalProperties': False}}}


TOOLS = [tool('check_force', 'Run the independent central-force reference at declared radii/phases.'),
         tool('check_refinement', 'Run exact circular-reference refinement and rotated initial conditions.'),
         tool('check_reversibility', 'Check the declared Verlet time-reversal property against recorded roundoff-aware allowance; this is not algorithm identity proof.'),
         tool('finish', 'Finish only after all applicable checks. Cite every recorded evidence ID; do not issue a verdict.',
              {'evidence_ids': {'type': 'array', 'items': {'type': 'string'}, 'uniqueItems': True}}, ['evidence_ids'])]
CHECKS = {'check_force': force_experiment, 'check_refinement': refinement_experiment,
          'check_reversibility': reversal_experiment}
SYSTEM = ('You coordinate a space-only circular-orbit engineering investigation. The contract is locked. '
          'Call each applicable supported check once, in an order you choose, then finish citing every actual evidence ID. '
          'Use actual tool evidence. Do not change assumptions, units, thresholds, source or verdict. '
          'Do not diagnose real hardware. No code execution, network tools or patching are supported. '
          'Return structured tool calls only; the deterministic kernel produces the final finding.')


def compact_check(check):
    result = deepcopy(check)
    for run in result.get('runs', []):
        run.pop('samples', None)
    return result


def investigate(example, provider, *, contract=None, review=None, max_turns=4):
    c = contract or example.contract
    locked = c.sha256
    trace, evidence, usage = [], {}, []
    attempts = successes = 0
    initial_requests = getattr(provider, 'request_attempts', 0)
    state, error = 'incomplete', None
    checks = {name: function for name, function in CHECKS.items()
              if name != 'check_reversibility' or c.declared_method == 'velocity_verlet'}
    applicable_tools = [item for item in TOOLS if item['function']['name'] in (*checks, 'finish')]
    messages = [{'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': json.dumps({'contract': c.record(), 'contract_sha256': locked,
                    'candidate_source': example.source_record(), 'supported_tools': list(checks)})}]
    if c.ambiguities():
        state = 'blocked_contract'
    else:
        try:
            for _ in range(max_turns):
                attempts += 1
                turn = provider.complete(deepcopy(messages), deepcopy(applicable_tools))
                successes += 1
                usage.append(turn.usage)
                raw = turn.message
                if not isinstance(raw, dict):
                    raise ProviderError('Expected a structured assistant message.')
                calls = raw.get('tool_calls')
                if raw.get('role') != 'assistant' or not isinstance(calls, list) or not 1 <= len(calls) <= 2:
                    raise ProviderError('Expected one or two supported structured tool calls.')
                clean_calls = []
                for call in calls:
                    if (not isinstance(call, dict) or call.get('type') != 'function' or
                        not isinstance(call.get('id'), str) or not 1 <= len(call['id']) <= 100 or
                        any(not (ch.isalnum() or ch in '_-') for ch in call['id']) or
                        any(event['call_id'] == call['id'] for event in trace) or
                        any(previous['id'] == call['id'] for previous in clean_calls)):
                        raise ProviderError('Invalid or repeated tool-call identifier.')
                    function = call.get('function', {})
                    if not isinstance(function, dict) or not isinstance(function.get('arguments'), str) or len(function['arguments']) > 2048:
                        raise ProviderError('Invalid bounded tool arguments.')
                    name = function.get('name')
                    args = json.loads(function.get('arguments', ''))
                    if name not in (*checks, 'finish') or not isinstance(args, dict):
                        raise ProviderError('An unsupported tool or argument shape was rejected.')
                    clean_calls.append({'id': call['id'], 'type': 'function',
                                        'function': {'name': name, 'arguments': json.dumps(args)}})
                # Free-form model content is discarded, never treated as engineering evidence.
                messages.append({'role': 'assistant', 'content': None, 'tool_calls': clean_calls})
                for call in clean_calls:
                    name = call['function']['name']
                    args = json.loads(call['function']['arguments'])
                    if c.sha256 != locked:
                        raise ProviderError('The locked contract changed.')
                    if name == 'finish':
                        ids = args.get('evidence_ids')
                        if (len(clean_calls) != 1 or set(args) != {'evidence_ids'} or
                            not isinstance(ids, list) or not all(isinstance(i, str) for i in ids) or
                            len(ids) != len(checks) or set(ids) != set(evidence) or len(evidence) != len(checks)):
                            raise ProviderError('Finish requires all applicable actual evidence IDs, with no verdict override.')
                        trace.append({'call_id': call['id'], 'tool': name, 'evidence_ids': ids})
                        state = 'completed'
                        break
                    if args or any(event['tool'] == name for event in trace):
                        raise ProviderError('Checks accept no parameters and may run only once.')
                    check = checks[name](example, c)
                    evidence[check['id']] = check
                    trace.append({'call_id': call['id'], 'tool': name, 'evidence_id': check['id'],
                                  'evidence_sha256': digest(check)})
                    messages.append({'role': 'tool', 'tool_call_id': call['id'],
                                     'content': json.dumps(compact_check(check), allow_nan=False)})
                if state == 'completed':
                    break
            if state != 'completed':
                error = 'The bounded tool-turn limit was reached.'
        except ProviderError as exc:
            state, error = 'failed', str(exc)
        except (ValueError, TypeError, KeyError, ArithmeticError):
            state = 'failed'
            error = 'The investigation stopped on a provider, protocol or experiment error. Kernel findings remain independent.'
    # Mandatory coverage is independently rerun, including after an interrupted investigation.
    # No model-produced number or verdict is passed into the kernel.
    report = audit(example, contract=c, review=review)
    actual = {check['id']: check for check in report['checks']}
    if any(actual.get(key) != value for key, value in evidence.items()):
        state, error = 'failed', 'Selected experiments differed from the independent final audit.'
    report['model_mode'] = provider.mode
    report['live_model_calls'] = successes if provider.mode == 'live_token_factory' else 0
    report['investigation'] = {'schema': 'sixd.investigation.v1', 'state': state,
        'provider_mode': provider.mode, 'model': provider.model, 'provider_attempts': attempts,
        'provider_successes': successes, 'live_request_attempts':
            getattr(provider, 'request_attempts', 0) - initial_requests if provider.mode == 'live_token_factory' else 0,
        'usage': usage, 'trace': trace, 'error': error,
        'contract_sha256': locked, 'kernel_audit_id': report['audit_id'],
        'summary': report['summary'], 'summary_origin': 'deterministic_kernel',
        'reproduction_scope': 'Numerical evidence can be reproduced locally; the provider selection transcript is a recorded run, not a claim of repeatable inference.',
        'source_versions': {name: sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                            for name in ('investigation.py', 'providers.py')}}
    report['report_payload_sha256'] = digest({k: v for k, v in report.items() if k != 'report_payload_sha256'})
    return report
