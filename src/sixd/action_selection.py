"""Bounded model action selection; all physics inputs stay in the locked runner."""
from copy import deepcopy
import json


WIRE_TOOL = 'select_next_action'
PROTOCOL = 'forced_action_v1'
CHECK_ACTIONS = ('check_force', 'check_refinement', 'check_reversibility')
ACTION_DESCRIPTIONS = {
    'check_force': 'Independent central-force reference.',
    'check_refinement': 'Circular-reference refinement and rotated initial conditions.',
    'check_reversibility': 'Applicable Verlet time-reversal experiment.',
    'finish': 'Finish by citing exactly the recorded evidence identifiers.',
}
SYSTEM = (
    'Select the next action for a space-only circular-orbit investigation. '
    'Call select_next_action exactly once per response with exactly action and evidence_ids. '
    'Choose only an action in the current menu. For a check, evidence_ids must be []. '
    'For finish, cite exactly all recorded evidence identifiers in the current menu. '
    'The runner supplies physics inputs from the locked contract and independently computes evidence. '
    'Do not provide physics parameters, change assumptions or issue a verdict. '
    'Return only the selected tool call. This is a constructed numerical investigation, not hardware certification.'
)
PROBLEM = {
    'code': 'invalid_action_selection',
    'message': 'Call select_next_action once with exactly action and evidence_ids. '
               'Choose an available action; use [] for a check or exactly the recorded IDs for finish.',
}


def _fail(message):
    # The provider imports this module; defer the exception import to avoid a cycle.
    from .providers import ProviderError
    raise ProviderError(message)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key.')
        result[key] = value
    return result


def _parse(arguments):
    def reject_constant(_):
        raise ValueError('Non-finite JSON constant.')
    return json.loads(arguments, object_pairs_hook=_unique_object,
                      parse_constant=reject_constant)


def _menu(tools):
    """Read only the runner's applicable actions and actual finish evidence schema."""
    try:
        if not isinstance(tools, list) or not 1 <= len(tools) <= 3:
            raise ValueError
        actions = [item['function']['name'] for item in tools]
        if (not all(isinstance(action, str) for action in actions) or
                len(set(actions)) != len(actions) or
                any(action not in (*CHECK_ACTIONS, 'finish') for action in actions)):
            raise ValueError
        ids = []
        if 'finish' in actions:
            if actions != ['finish']:
                raise ValueError
            schema = tools[0]['function']['parameters']['properties']['evidence_ids']
            ids = schema['items']['enum']
            if (not isinstance(ids, list) or not 1 <= len(ids) <= 3 or
                    not all(isinstance(value, str) and 1 <= len(value) <= 100 for value in ids) or
                    len(set(ids)) != len(ids) or
                    schema.get('minItems') != len(ids) or schema.get('maxItems') != len(ids)):
                raise ValueError
        return actions, sorted(ids)
    except (KeyError, TypeError, ValueError):
        _fail('The runner action menu is invalid. No request was sent.')


def _history_call(call):
    if not isinstance(call, dict) or not isinstance(call.get('function'), dict):
        _fail('The recorded action history is invalid. No request was sent.')
    function = call['function']
    name = function.get('name')
    if name == WIRE_TOOL:
        # A rejected wire call must stay matched to its existing tool-response ID.
        return deepcopy(call)
    try:
        arguments = _parse(function['arguments'])
        if name in CHECK_ACTIONS and arguments == {}:
            ids = []
        elif name == 'finish' and isinstance(arguments, dict) and set(arguments) == {'evidence_ids'}:
            ids = arguments['evidence_ids']
            if (not isinstance(ids, list) or not all(isinstance(value, str) for value in ids) or
                    len(set(ids)) != len(ids)):
                raise ValueError
        else:
            raise ValueError
        revised = deepcopy(call)
        revised['function'] = {'name': WIRE_TOOL, 'arguments': json.dumps(
            {'action': name, 'evidence_ids': ids}, allow_nan=False)}
        return revised
    except (KeyError, TypeError, ValueError, RecursionError):
        _fail('The recorded action history is invalid. No request was sent.')


def build_action_request(messages, tools):
    """Return wire messages, one selection tool and its explicit named choice."""
    actions, ids = _menu(tools)
    # Named tool choice may compile this schema through a constrained decoder.
    # Keep the wire schema portable; _parse/decode still enforce empty, unique
    # and exact recorded IDs locally before any kernel invocation.
    evidence_schema = {'type': 'array', 'items': {'type': 'string'}}
    wire_tool = {'type': 'function', 'function': {
        'name': WIRE_TOOL,
        'description': 'Select one currently available action; the runner owns all physics inputs.',
        'parameters': {'type': 'object', 'properties': {
            'action': {'type': 'string', 'enum': actions},
            'evidence_ids': evidence_schema,
        }, 'required': ['action', 'evidence_ids'], 'additionalProperties': False},
    }}
    if not isinstance(messages, list):
        _fail('The investigation message history is invalid. No request was sent.')
    wire_messages = [{'role': 'system', 'content': SYSTEM}]
    for message in deepcopy(messages):
        if not isinstance(message, dict):
            _fail('The investigation message history is invalid. No request was sent.')
        if message.get('role') == 'system':
            continue
        if message.get('role') == 'assistant' and message.get('tool_calls'):
            if not isinstance(message['tool_calls'], list):
                _fail('The recorded action history is invalid. No request was sent.')
            message['tool_calls'] = [_history_call(call) for call in message['tool_calls']]
            message['content'] = None
        wire_messages.append(message)
    wire_messages.append({'role': 'user', 'content': json.dumps({
        'available_actions': [{'action': action, 'purpose': ACTION_DESCRIPTIONS[action]}
                              for action in actions],
        'recorded_evidence_ids': ids,
        'valid_selections': [{'action': action, 'evidence_ids': ids if action == 'finish' else []}
                             for action in actions],
        'instruction': 'Call select_next_action once using one valid selection.',
    }, allow_nan=False)})
    choice = {'type': 'function', 'function': {'name': WIRE_TOOL}}
    return wire_messages, [wire_tool], choice


def decode_action_message(message, tools):
    """Validate a wire selection before adapting it to a canonical runner call."""
    actions, ids = _menu(tools)
    if (not isinstance(message, dict) or message.get('role') != 'assistant' or
            not isinstance(message.get('tool_calls'), list) or len(message['tool_calls']) != 1):
        _fail('Expected exactly one structured select_next_action call.')
    call = message['tool_calls'][0]
    if not isinstance(call, dict):
        _fail('Invalid bounded action-selection envelope.')
    identity, function = call.get('id'), call.get('function')
    if (call.get('type') != 'function' or not isinstance(identity, str) or
            not 1 <= len(identity) <= 100 or
            any(not (character.isalnum() or character in '_-') for character in identity) or
            not isinstance(function, dict) or function.get('name') != WIRE_TOOL or
            not isinstance(function.get('arguments'), str) or len(function['arguments']) > 2048):
        _fail('Invalid bounded action-selection envelope.')
    arguments = function['arguments']
    sanitized = {'role': 'assistant', 'content': None, 'tool_calls': [{
        'id': identity, 'type': 'function',
        'function': {'name': WIRE_TOOL, 'arguments': arguments},
    }]}
    try:
        selection = _parse(arguments)
        if not isinstance(selection, dict) or set(selection) != {'action', 'evidence_ids'}:
            raise ValueError
        action, selected_ids = selection['action'], selection['evidence_ids']
        if (not isinstance(action, str) or action not in actions or
                not isinstance(selected_ids, list) or
                not all(isinstance(value, str) for value in selected_ids) or
                len(set(selected_ids)) != len(selected_ids)):
            raise ValueError
        if (action == 'finish' and sorted(selected_ids) != ids) or (action != 'finish' and selected_ids):
            raise ValueError
    except (TypeError, ValueError, RecursionError):
        return sanitized, dict(PROBLEM)
    canonical_args = {'evidence_ids': selected_ids} if action == 'finish' else {}
    sanitized['tool_calls'][0]['function'] = {
        'name': action, 'arguments': json.dumps(canonical_args, allow_nan=False),
    }
    return sanitized, None


def decode_action_response(message, tools, *, internal_call_id):
    """Accept a native envelope or exact selection JSON, never extract prose.

    Content selections use an explicitly runner-origin internal ID. They are
    never represented in receipts as native provider tool calls.
    """
    if not isinstance(message, dict) or message.get('role') != 'assistant':
        _fail('Expected a bounded assistant action response.')
    calls = message.get('tool_calls')
    if calls is not None and calls != []:
        decoded, problem = decode_action_message(message, tools)
        return decoded, problem, 'native_tool_call', 'provider'
    content = message.get('content')
    if not isinstance(content, str) or not 1 <= len(content) <= 2048:
        _fail('Expected a native selector or an exact bounded selection JSON object.')
    try:
        selection = _parse(content)
        if (not isinstance(selection, dict) or set(selection) != {'action', 'evidence_ids'} or
                not isinstance(selection['action'], str) or
                not isinstance(selection['evidence_ids'], list) or
                not all(isinstance(value, str) for value in selection['evidence_ids'])):
            raise ValueError
    except (TypeError, ValueError, RecursionError):
        _fail('Content did not contain an exact bounded action selection. No action was executed.')
    envelope = {'role': 'assistant', 'content': None, 'tool_calls': [{
        'id': internal_call_id, 'type': 'function', 'function': {
            'name': WIRE_TOOL, 'arguments': content,
        },
    }]}
    decoded, problem = decode_action_message(envelope, tools)
    return decoded, problem, 'content_selection_json', 'runner'
