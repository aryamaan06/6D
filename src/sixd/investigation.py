"""Bounded orchestration; only the deterministic kernel issues engineering findings."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json
from .contracts import digest
from .kernel import audit, force_experiment, refinement_experiment, reversal_experiment
from .providers import ProviderError, safe_response_diagnostic
from .action_selection import PROTOCOL as ACTION_PROTOCOL, PROBLEM as ACTION_PROBLEM, WIRE_TOOL


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
          'Call each offered check once, in an order you choose. Every check takes exactly the empty JSON object {}: '
          'the runner supplies all values from the locked contract. Do not pass parameters, a contract, or a schema. '
          'You may call up to three different offered checks together. Only after their evidence exists, '
          'call finish alone with exactly the evidence_ids listed in its description. '
          'Use actual tool evidence. Do not change assumptions, units, thresholds, source or verdict. '
          'Do not diagnose real hardware. No code execution, network tools or patching are supported. '
          'Return structured tool calls only; the deterministic kernel produces the final finding.')


def compact_check(check):
    result = deepcopy(check)
    for run in result.get('runs', []):
        run.pop('samples', None)
    return result


def remaining_tools(checks, executed, evidence):
    """Offer only executable checks, then an evidence-constrained finish."""
    pending = set(checks) - executed
    if pending:
        result = [deepcopy(item) for item in TOOLS if item['function']['name'] in pending]
        for item in result:
            item['function']['description'] += ' Arguments must be exactly {}. The locked contract supplies all values.'
        return result
    result = deepcopy(TOOLS[-1])
    ids = sorted(evidence)
    result['function']['description'] += ' Call alone with exactly ' + json.dumps({'evidence_ids': ids}) + '.'
    result['function']['parameters']['properties']['evidence_ids'].update(
        {'items': {'type': 'string', 'enum': ids}, 'minItems': len(ids), 'maxItems': len(ids)})
    return [result]


def batch_error(calls, checks, executed, evidence):
    """Validate the whole batch before executing any of its experiments."""
    names = [call['function']['name'] for call in calls]
    if 'finish' in names:
        if len(calls) != 1:
            return 'finish_must_be_alone', 'Call finish alone after all applicable checks.'
        args = json.loads(calls[0]['function']['arguments'])
        if set(args) != {'evidence_ids'}:
            raise ProviderError('Finish requires only actual evidence IDs, with no verdict override.')
        if executed != set(checks):
            return 'finish_before_checks', 'Finish is unavailable until every applicable check has recorded evidence.'
        ids = args['evidence_ids']
        if (not isinstance(ids, list) or not all(isinstance(i, str) for i in ids) or
                len(ids) != len(checks) or set(ids) != set(evidence)):
            return 'finish_evidence_mismatch', 'Finish must cite exactly the recorded evidence IDs in its tool description.'
    else:
        if any(json.loads(call['function']['arguments']) for call in calls):
            return 'check_arguments_not_empty', 'Check arguments must be exactly {}. All values come from the locked contract.'
        if len(names) != len(set(names)):
            return 'duplicate_check_batch', 'Request each unfinished check at most once in a batch.'
        if any(name in executed for name in names):
            return 'check_already_executed', 'That check already has evidence. Select an unfinished offered check.'
    return None


def response_metadata(turn, selection_protocol):
    """Persist only controlled adapter facts, never arbitrary provider metadata."""
    meta = getattr(turn, 'response_meta', None)
    if meta is None:
        return {}
    if not isinstance(meta, dict) or selection_protocol != ACTION_PROTOCOL:
        raise ProviderError('Invalid action-response provenance was rejected.')
    triple = (meta.get('finish_reason'), meta.get('response_format'), meta.get('call_id_origin'))
    if triple not in (('stop', 'native_tool_call', 'provider'),
                      ('tool_calls', 'native_tool_call', 'provider'),
                      ('stop', 'content_selection_json', 'runner')):
        raise ProviderError('Invalid action-response provenance was rejected.')
    return {key: meta[key] for key in ('finish_reason', 'response_format', 'call_id_origin')}


def investigate(example, provider, *, contract=None, review=None, max_turns=5, max_protocol_corrections=1):
    if (type(max_turns) is not int or not 1 <= max_turns <= 5 or
            type(max_protocol_corrections) is not int or not 0 <= max_protocol_corrections <= 1):
        raise ValueError('Investigations allow one to five turns and at most one protocol correction.')
    c = contract or example.contract
    locked = c.sha256
    trace, evidence, usage = [], {}, []
    executed = set()
    rejections = corrections = 0
    attempts = successes = 0
    initial_requests = getattr(provider, 'request_attempts', 0)
    state, error = 'incomplete', None
    failed_provider_response = {}
    selection_protocol = getattr(getattr(provider, 'config', None), 'selection_protocol', 'native_tools_v1')
    selection_meta = ({'selection_protocol': ACTION_PROTOCOL, 'wire_tool': WIRE_TOOL}
                      if selection_protocol == ACTION_PROTOCOL else {})
    checks = {name: function for name, function in CHECKS.items()
              if name != 'check_reversibility' or c.declared_method == 'velocity_verlet'}
    messages = [{'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': json.dumps({'contract': c.record(), 'contract_sha256': locked,
                    'candidate_source': example.source_record(), 'supported_tools': list(checks)})}]
    if c.ambiguities():
        state = 'blocked_contract'
    else:
        try:
            for _ in range(max_turns):
                attempts += 1
                turn = provider.complete(deepcopy(messages), remaining_tools(checks, executed, evidence))
                successes += 1
                usage.append(turn.usage)
                event_meta = {**selection_meta, **response_metadata(turn, selection_protocol)}
                raw = turn.message
                if not isinstance(raw, dict):
                    raise ProviderError('Expected a structured assistant message.')
                calls = raw.get('tool_calls')
                if raw.get('role') != 'assistant' or not isinstance(calls, list) or not 1 <= len(calls) <= 3:
                    raise ProviderError('Expected one to three supported check calls, or finish alone.')
                if turn.protocol_error is not None:
                    if (selection_protocol != ACTION_PROTOCOL or turn.protocol_error != ACTION_PROBLEM or
                            len(calls) != 1 or not isinstance(calls[0], dict)):
                        raise ProviderError('Invalid action-selection feedback was rejected.')
                    call = calls[0]
                    identity, function = call.get('id'), call.get('function')
                    if (call.get('type') != 'function' or not isinstance(identity, str) or
                            not 1 <= len(identity) <= 100 or
                            any(not (ch.isalnum() or ch in '_-') for ch in identity) or
                            any(event['call_id'] == identity for event in trace) or
                            not isinstance(function, dict) or function.get('name') != WIRE_TOOL or
                            not isinstance(function.get('arguments'), str) or len(function['arguments']) > 2048):
                        raise ProviderError('Invalid or repeated action-selection identifier or envelope.')
                    if c.sha256 != locked:
                        raise ProviderError('The locked contract changed.')
                    # Invalid arguments remain only in transient model conversation history;
                    # the receipt records the controlled rejection, never their values.
                    messages.append({'role': 'assistant', 'content': None, 'tool_calls': [deepcopy(call)]})
                    rejections += 1
                    can_correct = corrections < max_protocol_corrections and attempts < max_turns
                    trace.append({'call_id': identity, 'tool': WIRE_TOOL, 'status': 'rejected',
                                  'error_code': ACTION_PROBLEM['code'], **event_meta})
                    feedback = {'error': dict(ACTION_PROBLEM), 'retry_allowed': can_correct,
                                'available_actions': [item['function']['name'] for item in remaining_tools(checks, executed, evidence)],
                                'recorded_evidence_ids': sorted(evidence)}
                    messages.append({'role': 'tool', 'tool_call_id': identity, 'content': json.dumps(feedback)})
                    if not can_correct:
                        raise ProviderError('The bounded action-selection correction allowance was exhausted.')
                    corrections += 1
                    continue
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
                if c.sha256 != locked:
                    raise ProviderError('The locked contract changed.')
                problem = batch_error(clean_calls, checks, executed, evidence)
                if problem:
                    code, detail = problem
                    rejections += 1
                    can_correct = corrections < max_protocol_corrections and attempts < max_turns
                    offered = remaining_tools(checks, executed, evidence)
                    feedback = {'error': {'code': code, 'message': detail}, 'retry_allowed': can_correct,
                                'available_tools': [item['function']['name'] for item in offered],
                                'recorded_evidence_ids': sorted(evidence)}
                    for call in clean_calls:
                        trace.append({'call_id': call['id'], 'tool': call['function']['name'],
                                      'status': 'rejected', 'error_code': code,
                                      'argument_count': len(json.loads(call['function']['arguments'])),
                                      **event_meta})
                        messages.append({'role': 'tool', 'tool_call_id': call['id'],
                                         'content': json.dumps(feedback)})
                    if not can_correct:
                        raise ProviderError(detail + ' The bounded protocol-correction allowance was exhausted.')
                    corrections += 1
                    continue
                for call in clean_calls:
                    name = call['function']['name']
                    args = json.loads(call['function']['arguments'])
                    if c.sha256 != locked:
                        raise ProviderError('The locked contract changed.')
                    if name == 'finish':
                        ids = args.get('evidence_ids')
                        trace.append({'call_id': call['id'], 'tool': name, 'status': 'completed', 'evidence_ids': ids,
                                      **event_meta})
                        state = 'completed'
                        break
                    check = checks[name](example, c)
                    executed.add(name)
                    evidence[check['id']] = check
                    trace.append({'call_id': call['id'], 'tool': name, 'status': 'executed', 'evidence_id': check['id'],
                                  'evidence_sha256': digest(check), **event_meta})
                    messages.append({'role': 'tool', 'tool_call_id': call['id'],
                                     'content': json.dumps(compact_check(check), allow_nan=False)})
                if state == 'completed':
                    break
            if state != 'completed':
                error = 'The bounded tool-turn limit was reached.'
        except ProviderError as exc:
            state, error = 'failed', str(exc)
            failed_provider_response = safe_response_diagnostic(exc.diagnostic)
        except (ValueError, TypeError, KeyError, ArithmeticError, StopIteration):
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
        'inference_profile': getattr(getattr(provider, 'config', None), 'inference_profile', 'not_applicable'),
        'selection_protocol': selection_protocol,
        'failed_provider_response': failed_provider_response,
        'protocol_rejections': rejections, 'protocol_corrections': corrections,
        'contract_sha256': locked, 'kernel_audit_id': report['audit_id'],
        'summary': report['summary'], 'summary_origin': 'deterministic_kernel',
        'reproduction_scope': 'Numerical evidence can be reproduced locally; the provider selection transcript is a recorded run, not a claim of repeatable inference.',
        'source_versions': {name: sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                            for name in ('investigation.py', 'providers.py', 'action_selection.py')}}
    report['report_payload_sha256'] = digest({k: v for k, v in report.items() if k != 'report_payload_sha256'})
    return report
