"""Replaceable tool-call providers. Network inference is opt-in and budget gated."""
from dataclasses import dataclass
from contextlib import closing
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from uuid import uuid4
import json
import math
import os
import re
import sqlite3
import ssl
from datetime import datetime, timezone
from .action_selection import build_action_request, decode_action_response


RESPONSE_TOO_LARGE = 'Provider response exceeded the bounded size.'
FAILURE_SUFFIX = ' Reservation retained; no automatic retry.'
INFERENCE_PROFILES = ('tool_sampling', 'nebius_no_reasoning', 'native_no_thinking')
SELECTION_PROTOCOLS = ('native_tools_v1', 'forced_action_v1')
FINISH_REASONS = ('length', 'stop', 'content_filter', 'function_call', 'tool_calls')
API_ERROR_TYPES = ('invalid_request_error', 'BadRequestError', 'validation_error')
API_ERROR_CODES = ('invalid_schema', 'unsupported_value', 'invalid_parameter',
                   'unsupported_parameter', 'bad_request', 'validation_error')
API_PARAMETERS = ('tools', 'tool_choice', 'messages', 'max_tokens', 'response_format',
                  'chat_template_kwargs', 'reasoning_effort', 'model', 'temperature', 'top_p')
SCHEMA_KEYWORDS = ('uniqueItems', 'minItems', 'maxItems', 'contains', 'minContains',
                   'maxContains', 'additionalProperties', 'oneOf', 'anyOf')
RESPONSE_SHAPES = ('native_tool_call', 'content_without_tool_calls',
                   'invalid_tool_envelope', 'empty_response')
SELECTION_REJECTIONS = frozenset({
    'selection_shape', 'unavailable_action', 'citations_shape', 'citation_mismatch',
    'summary_type', 'summary_length', 'read_payload_not_empty',
    'assistant_envelope', 'selector_count', 'selector_envelope',
    'arguments_type_or_length', 'invalid_json',
})
ERROR_CODES = frozenset({
    'cumulative_budget_exhausted', 'case_budget_exhausted', 'batch_budget_exhausted',
    'request_limit', 'budget_ledger_error', 'configuration_error', 'provider_transport_error',
    'provider_response_invalid', 'provider_output_limit', 'invalid_action_response',
    'verification_sources_changed', 'recheck_mismatch', 'explanation_rejected',
    'session_changed', 'budget_approval_mismatch', 'budget_reservation_invalid',
})


def safe_response_diagnostic(value):
    """Keep controlled response facts, never response text or arbitrary metadata."""
    if not isinstance(value, dict):
        return {}
    result = {}
    if isinstance(value.get('selection_rejection'), str) and value['selection_rejection'] in SELECTION_REJECTIONS:
        result['selection_rejection'] = value['selection_rejection']
    for key in ('summary_characters', 'arguments_characters', 'evidence_ids_count', 'expected_evidence_ids_count'):
        count = value.get(key)
        if type(count) is int and 0 <= count <= 100000:
            result[key] = count
    status = value.get('http_status')
    if type(status) is int and 100 <= status <= 599:
        result['http_status'] = status
    for key, allowed in (('api_error_type', API_ERROR_TYPES),
                         ('api_error_code', API_ERROR_CODES),
                         ('rejected_parameter', API_PARAMETERS)):
        item = value.get(key)
        if isinstance(item, str) and item in allowed:
            result[key] = item
    if type(value.get('api_error_code')) is int and 100 <= value['api_error_code'] <= 599:
        result['api_error_code'] = value['api_error_code']
    mentions = value.get('schema_keyword_mentions')
    if isinstance(mentions, list):
        selected = [key for key in SCHEMA_KEYWORDS if key in mentions]
        if selected:
            result['schema_keyword_mentions'] = selected
    if 'finish_reason' in value:
        reason = value['finish_reason']
        result['finish_reason'] = reason if isinstance(reason, str) and reason in FINISH_REASONS else 'unknown'
    if value.get('response_shape') in RESPONSE_SHAPES:
        result['response_shape'] = value['response_shape']
    count = value.get('tool_call_count')
    if type(count) is int and 0 <= count <= 16:
        result['tool_call_count'] = count
    if type(value.get('content_present')) is bool:
        result['content_present'] = value['content_present']
    if value.get('inference_profile') in INFERENCE_PROFILES:
        result['inference_profile'] = value['inference_profile']
    limit = value.get('max_output_tokens')
    if type(limit) is int and 128 <= limit <= 8192:
        result['max_output_tokens'] = limit
    usage = value.get('usage')
    if isinstance(usage, dict):
        counts = {key: usage[key] for key in ('prompt_tokens', 'completion_tokens', 'total_tokens')
                  if type(usage.get(key)) is int and usage[key] >= 0}
        details = usage.get('completion_tokens_details')
        if isinstance(details, dict):
            count = details.get('reasoning_tokens')
            if type(count) is int and 0 <= count <= counts.get('completion_tokens', 8192):
                counts['completion_tokens_details'] = {'reasoning_tokens': count}
        result['usage'] = counts
    return result


def response_envelope_diagnostic(message):
    """Describe only the outer response shape; never retain remote values."""
    if not isinstance(message, dict):
        return {'response_shape': 'invalid_tool_envelope'}
    calls = message.get('tool_calls')
    content = message.get('content')
    present = isinstance(content, str) and bool(content)
    if calls is None or calls == []:
        shape = 'content_without_tool_calls' if present else 'empty_response'
    elif isinstance(calls, list) and len(calls) == 1 and isinstance(calls[0], dict):
        shape = 'native_tool_call'
    else:
        shape = 'invalid_tool_envelope'
    diagnostic = {'response_shape': shape, 'content_present': present}
    if isinstance(calls, list) and len(calls) <= 16:
        diagnostic['tool_call_count'] = len(calls)
    elif calls is None:
        diagnostic['tool_call_count'] = 0
    return diagnostic


def http_error_diagnostic(error):
    """Inspect a bounded structured error internally; retain only allowlisted facts."""
    diagnostic = {'http_status': error.code}
    try:
        body = error.read(8193)
        if not isinstance(body, bytes) or len(body) > 8192:
            return safe_response_diagnostic(diagnostic)
        parsed = json.loads(body)
        remote = parsed.get('error') if isinstance(parsed, dict) else None
        if not isinstance(remote, dict):
            return safe_response_diagnostic(diagnostic)
        diagnostic.update(api_error_type=remote.get('type'), api_error_code=remote.get('code'),
                          rejected_parameter=remote.get('param'))
        message = remote.get('message')
        if isinstance(message, str):
            # A mention is recorded as a mention, not asserted as the cause.
            diagnostic['schema_keyword_mentions'] = [keyword for keyword in SCHEMA_KEYWORDS
                if re.search(r'(?<![A-Za-z0-9_])' + keyword + r'(?![A-Za-z0-9_])', message)]
    except Exception:
        pass  # Unreadable/unstructured remote details must never escape.
    return safe_response_diagnostic(diagnostic)


def transport_failure(error):
    """Translate transport errors without copying remote text or credentials."""
    if isinstance(error, HTTPError):
        code = error.code if type(error.code) is int and 100 <= error.code <= 599 else 'unknown'
        return ProviderError(f'Nebius request failed: HTTP {code}.' + FAILURE_SUFFIX,
                             diagnostic=http_error_diagnostic(error), code='provider_transport_error')
    if isinstance(error, (TimeoutError,)):
        return ProviderError('Nebius request timed out.' + FAILURE_SUFFIX, code='provider_transport_error')
    if isinstance(error, ssl.SSLError):
        return ProviderError('Nebius TLS connection failed.' + FAILURE_SUFFIX, code='provider_transport_error')
    if isinstance(error, URLError):
        reason = error.reason
        if isinstance(reason, TimeoutError):
            return ProviderError('Nebius request timed out.' + FAILURE_SUFFIX, code='provider_transport_error')
        if isinstance(reason, ssl.SSLError):
            return ProviderError('Nebius TLS connection failed.' + FAILURE_SUFFIX, code='provider_transport_error')
        return ProviderError('Nebius network connection failed.' + FAILURE_SUFFIX, code='provider_transport_error')
    if isinstance(error, json.JSONDecodeError):
        return ProviderError('Provider response was not valid JSON.' + FAILURE_SUFFIX, code='provider_response_invalid')
    # _send has one controlled size error. Never echo arbitrary transport messages.
    if isinstance(error, ProviderError) and error.args == (RESPONSE_TOO_LARGE,):
        return ProviderError(RESPONSE_TOO_LARGE + FAILURE_SUFFIX, code='provider_response_invalid')
    return ProviderError('Inference transport failed; private exception details were suppressed.' + FAILURE_SUFFIX, code='provider_transport_error')


class ProviderError(ValueError):
    """Safe operator-facing error; never includes a key or remote response body."""
    def __init__(self, message, *, diagnostic=None, code=None):
        super().__init__(message)
        self.diagnostic = safe_response_diagnostic(diagnostic)
        self.code = code if isinstance(code, str) and code in ERROR_CODES else None


@dataclass
class Turn:
    message: dict
    usage: dict
    request_id: str | None = None
    protocol_error: dict | None = None
    response_meta: dict | None = None


class Provider(Protocol):
    mode: str
    model: str

    def complete(self, messages: list, tools: list) -> Turn: ...


class FixtureProvider:
    """Scripted orchestration fixture, without model inference or stored measurements."""
    mode = "fixture"
    model = "scripted-tool-sequence-v1"

    def complete(self, messages, tools):
        seen = [record['id'] for m in messages if m['role'] == 'tool'
                if 'id' in (record := json.loads(m['content']))]
        available = {item['function']['name'] for item in tools}
        sequence = (('check_force', 'central_force_reference'),
                    ('check_refinement', 'analytic_reference_refinement'),
                    ('check_reversibility', 'method_time_reversal'))
        name = next((name for name, evidence_id in sequence if name in available and evidence_id not in seen), 'finish')
        args = {} if name != 'finish' else {'evidence_ids': seen}
        return Turn({'role': 'assistant', 'content': None, 'tool_calls': [
            {'id': f"fixture-{sum(m['role'] == 'tool' for m in messages)}", 'type': 'function',
             'function': {'name': name, 'arguments': json.dumps(args)}}]}, {})


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Do not forward a bearer credential to a redirected destination.


@dataclass(frozen=True)
class LiveConfig:
    base_url: str
    model: str
    approval_id: str
    spend_cap_usd: float
    input_usd_per_million_ceiling: float
    output_usd_per_million_ceiling: float
    max_output_tokens: int = 1024
    request_timeout_seconds: int = 45
    inference_profile: str = 'tool_sampling'
    selection_protocol: str = 'native_tools_v1'

    @classmethod
    def load(cls, path):
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                raise ProviderError('Local provider configuration is missing or invalid; see docs/PROVIDER_SETUP.md.')
            if any(data.get(k) is not True for k in
                   ('account_verified', 'model_license_reviewed', 'spend_approved')):
                raise ProviderError('Account, model license and user spending approval must be verified locally.')
            config = cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})
            endpoint = urlsplit(config.base_url)
            if (endpoint.scheme != 'https' or endpoint.username or endpoint.password or
                endpoint.port not in (None, 443) or endpoint.query or endpoint.fragment or
                endpoint.hostname not in ('api.tokenfactory.nebius.com',
                    'api.tokenfactory.us-central1.nebius.com') or endpoint.path.rstrip('/') != '/v1'):
                raise ProviderError('Use a supported HTTPS Token Factory /v1 endpoint.')
            if not isinstance(config.model, str) or not config.model.lower().startswith('nvidia/') or 'nemotron' not in config.model.lower():
                raise ProviderError('Select the exact account-available NVIDIA Nemotron model ID.')
            if not isinstance(config.approval_id, str) or not config.approval_id.strip():
                raise ProviderError('Record a reference to the user-approved budget.')
            for number in (config.spend_cap_usd, config.input_usd_per_million_ceiling,
                           config.output_usd_per_million_ceiling):
                if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or number <= 0:
                    raise ProviderError('A positive finite cap and verified price ceilings are required.')
            if type(config.max_output_tokens) is not int or not 128 <= config.max_output_tokens <= 8192:
                raise ProviderError('Choose 128–8192 maximum output tokens.')
            if type(config.request_timeout_seconds) is not int or not 15 <= config.request_timeout_seconds <= 180:
                raise ProviderError('Choose a 15–180 second request timeout.')
            if not isinstance(config.inference_profile, str) or config.inference_profile not in INFERENCE_PROFILES:
                raise ProviderError('Choose a supported inference profile; see docs/PROVIDER_SETUP.md.')
            if not isinstance(config.selection_protocol, str) or config.selection_protocol not in SELECTION_PROTOCOLS:
                raise ProviderError('Choose a supported action-selection protocol; see docs/PROVIDER_SETUP.md.')
            return config
        except (OSError, KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ProviderError):
                raise
            raise ProviderError('Local provider configuration is missing or invalid; see docs/PROVIDER_SETUP.md.') from None


class BudgetLedger:
    """Persistent conservative reservations; errors/timeouts retain their allowance."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def reserve(self, config, amount):
        # Legacy callers use zero to verify the existing approval without
        # increasing usage. Actual request/job reservations remain positive.
        if type(amount) not in (int, float) or not math.isfinite(amount) or amount < 0:
            raise ProviderError('Invalid request reservation. No request was sent.', code='budget_reservation_invalid')
        try:
            with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
                db.execute('CREATE TABLE IF NOT EXISTS budget (id TEXT PRIMARY KEY, cap REAL, reserved REAL)')
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT id, cap, reserved FROM budget').fetchall()
                # One approval per ledger: changing an ID must not silently reset allowance.
                if row and (len(row) != 1 or row[0][0] != config.approval_id or row[0][1] != config.spend_cap_usd
                            or type(row[0][2]) not in (int, float) or not math.isfinite(row[0][2])
                            or not 0 <= row[0][2] <= config.spend_cap_usd):
                    raise ProviderError('The ledger approval/cap differs; budget changes require explicit operator review.', code='budget_approval_mismatch')
                used = row[0][2] if row else 0.0
                if used + amount > config.spend_cap_usd:
                    raise ProviderError('The approved inference allowance is exhausted. No request was sent.', code='cumulative_budget_exhausted')
                db.execute('INSERT OR REPLACE INTO budget VALUES (?, ?, ?)',
                           (config.approval_id, config.spend_cap_usd, used + amount))
        except sqlite3.Error:
            raise ProviderError('The budget ledger could not be locked or written. No request was sent.', code='budget_ledger_error') from None

    def increase_cap(self, config, new_cap, *, approved_maximum, authorization):
        """Explicit operator migration; keep approval identity and all reservations.

        Not called by inference, startup or HTTP routes. The host must update
        its local config separately; any interim mismatch fails closed.
        """
        if (type(new_cap) not in (int, float) or type(approved_maximum) not in (int, float)
                or not math.isfinite(new_cap) or not math.isfinite(approved_maximum)
                or not config.spend_cap_usd < new_cap <= approved_maximum
                or not isinstance(authorization, str) or not 1 <= len(authorization) <= 500):
            raise ProviderError('A bounded, explicitly authorized allowance increase is required.', code='configuration_error')
        try:
            with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT id,cap,reserved FROM budget').fetchall()
                if (len(row) != 1 or row[0][0] != config.approval_id or row[0][1] != config.spend_cap_usd
                        or type(row[0][2]) not in (int, float) or not math.isfinite(row[0][2])
                        or not 0 <= row[0][2] <= config.spend_cap_usd):
                    raise ProviderError('The existing ledger needs operator review; no cap changed.', code='budget_approval_mismatch')
                db.execute('CREATE TABLE IF NOT EXISTS allowance_changes (sequence INTEGER PRIMARY KEY, approval_id TEXT NOT NULL, old_cap REAL NOT NULL, new_cap REAL NOT NULL, reserved REAL NOT NULL, authorization TEXT NOT NULL, changed_at TEXT NOT NULL)')
                db.execute('INSERT INTO allowance_changes (approval_id,old_cap,new_cap,reserved,authorization,changed_at) VALUES (?,?,?,?,?,?)',
                    (config.approval_id, config.spend_cap_usd, new_cap, row[0][2], authorization, datetime.now(timezone.utc).isoformat()))
                db.execute('UPDATE budget SET cap=? WHERE id=?', (new_cap, config.approval_id))
                return {'approval_id': config.approval_id, 'old_cap_usd': config.spend_cap_usd,
                        'cap_usd': new_cap, 'reserved_usd': row[0][2], 'authorization': authorization}
        except sqlite3.Error:
            raise ProviderError('The ledger migration failed; inspect the saved allowance before proceeding.', code='budget_ledger_error') from None


class TokenFactoryProvider:
    mode = 'live_token_factory'

    def __init__(self, config, ledger, *, api_key=None, transport=None, action_adapter=None):
        self.config, self.ledger = config, ledger
        # Default dispatch preserves the validated orbital protocol. A project
        # runner may supply its own bounded menu without changing transport or
        # accounting behavior.
        self._action_adapter = action_adapter
        self.model = config.model
        self.request_attempts = 0
        self._key = api_key or os.environ.get('NEBIUS_API_KEY')
        if not self._key:
            raise ProviderError('Set NEBIUS_API_KEY locally. No live call was made.')
        self._transport = transport or self._send
        if transport is not None:
            self.mode = 'offline_transport_fixture'

    def _send(self, request):
        with build_opener(NoRedirect()).open(request, timeout=self.config.request_timeout_seconds) as response:
            data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ProviderError(RESPONSE_TOO_LARGE)
            return json.loads(data)

    def complete(self, messages, tools):
        if self.config.selection_protocol == 'forced_action_v1':
            build = (self._action_adapter.build_action_request
                     if self._action_adapter is not None else build_action_request)
            wire_messages, wire_tools, selection = build(messages, tools)
        elif self.config.selection_protocol == 'native_tools_v1':
            wire_messages, wire_tools = messages, tools
            selection = ({'type': 'function', 'function': {'name': tools[0]['function']['name']}}
                         if len(tools) == 1 else 'auto')
        else:
            raise ProviderError('Unsupported action-selection protocol. No request was sent.')
        payload = {'model': self.model, 'messages': wire_messages, 'tools': wire_tools,
                   'tool_choice': selection, 'max_tokens': self.config.max_output_tokens,
                   'stream': False}
        # NVIDIA recommends this sampling pair for Nano tool calling. Thinking-off
        # profiles are explicit hosted compatibility experiments, not guaranteed flags.
        if self.config.inference_profile == 'tool_sampling':
            payload.update(temperature=0.6, top_p=0.95)
        elif self.config.inference_profile == 'nebius_no_reasoning':
            payload.update(temperature=0, reasoning_effort='none')
        elif self.config.inference_profile == 'native_no_thinking':
            # Raw HTTP fields go at top level; SDK extra_body is a merge argument.
            payload.update(temperature=0, chat_template_kwargs={'enable_thinking': False})
        else:
            raise ProviderError('Unsupported inference profile. No request was sent.')
        encoded = json.dumps(payload, allow_nan=False).encode('utf-8')
        if len(encoded) > 120_000:
            raise ProviderError('The bounded investigation context is too large. No request was sent.')
        # UTF-8 byte count plus framing/tool allowance intentionally over-reserves.
        input_bound = len(encoded) + 4096
        ceiling = (input_bound * self.config.input_usd_per_million_ceiling +
                   self.config.max_output_tokens * self.config.output_usd_per_million_ceiling) / 1_000_000
        self.ledger.reserve(self.config, ceiling)
        request = Request(self.config.base_url.rstrip('/') + '/chat/completions', data=encoded,
                          headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self._key})
        self.request_attempts += 1
        try:
            result = self._transport(request)
        except Exception as error:
            raise transport_failure(error) from None
        if (not isinstance(result, dict) or not isinstance(result.get('choices'), list) or
                not result['choices'] or not isinstance(result['choices'][0], dict)):
            raise ProviderError('Invalid provider response structure.' + FAILURE_SUFFIX, code='provider_response_invalid')
        choice = result['choices'][0]
        message, usage = choice.get('message'), result.get('usage', {})
        if not isinstance(message, dict) or not isinstance(usage, dict):
            raise ProviderError('Invalid provider response structure.' + FAILURE_SUFFIX, code='provider_response_invalid')
        count_keys = ('prompt_tokens', 'completion_tokens', 'total_tokens')
        if any(key in usage and (type(usage[key]) is not int or usage[key] < 0) for key in count_keys):
            raise ProviderError('Invalid provider response structure.' + FAILURE_SUFFIX, code='provider_response_invalid')
        # Preserve only token counts, never remote metadata or echoed credentials.
        counts = {k: v for k, v in usage.items() if k in
                  count_keys}
        details = usage.get('completion_tokens_details')
        if details is not None:
            if not isinstance(details, dict):
                raise ProviderError('Invalid provider response structure.' + FAILURE_SUFFIX, code='provider_response_invalid')
            if 'reasoning_tokens' in details:
                count = details['reasoning_tokens']
                if type(count) is not int or not 0 <= count <= counts.get('completion_tokens', self.config.max_output_tokens):
                    raise ProviderError('Invalid provider response structure.' + FAILURE_SUFFIX, code='provider_response_invalid')
                counts['completion_tokens_details'] = {'reasoning_tokens': count}
        if counts.get('prompt_tokens', 0) > input_bound or counts.get('completion_tokens', 0) > self.config.max_output_tokens:
            raise ProviderError('Usage exceeded the configured reservation bound; stop and review provider billing.' + FAILURE_SUFFIX, code='provider_response_invalid')
        reason = choice.get('finish_reason')
        forced = self.config.selection_protocol == 'forced_action_v1'
        diagnostic = {'finish_reason': reason, 'usage': counts,
                      'max_output_tokens': self.config.max_output_tokens,
                      'inference_profile': self.config.inference_profile}
        if forced:
            diagnostic.update(response_envelope_diagnostic(message))
        # Named tool calls can finish with stop. The envelope and action are
        # still strictly validated below; stop alone never completes a run.
        if reason != 'tool_calls' and not (forced and reason == 'stop'):
            safe_reason = reason if isinstance(reason, str) and reason in FINISH_REASONS else 'unknown'
            detail = (' The output token limit was reached; no complete tool response was accepted.'
                      if safe_reason == 'length' else ' A complete structured tool response is required.')
            raise ProviderError(f'Provider returned finish_reason={safe_reason}.' + detail + FAILURE_SUFFIX,
                                diagnostic=diagnostic, code='provider_output_limit' if safe_reason == 'length' else 'provider_response_invalid')
        if forced:
            try:
                decode = (self._action_adapter.decode_action_response
                          if self._action_adapter is not None else decode_action_response)
                message, problem, response_format, origin = decode(
                    message, tools, internal_call_id='sixd-selection-' + uuid4().hex)
                if response_format == 'content_selection_json' and reason != 'stop':
                    raise ProviderError('A tool-call finish reason requires a native tool envelope.')
            except ProviderError as error:
                error.diagnostic = safe_response_diagnostic({**error.diagnostic, **diagnostic})
                error.code = 'invalid_action_response'
                raise
            return Turn(message, counts, protocol_error=problem,
                        response_meta={'finish_reason': reason, 'response_format': response_format,
                                       'call_id_origin': origin})
        return Turn(message, counts)


def make_provider(name, root):
    if name == 'fixture':
        return FixtureProvider()
    if name != 'token-factory':
        raise ProviderError('Unknown provider selection.')
    local = Path(root) / '.local'
    return TokenFactoryProvider(LiveConfig.load(local / 'token-factory.json'), BudgetLedger(local / 'budget.sqlite3'))


def provider_status(root):
    try:
        config = LiveConfig.load(Path(root) / '.local' / 'token-factory.json')
        ready = bool(os.environ.get('NEBIUS_API_KEY'))
        return {'configured': ready, 'model': config.model, 'live_calls_made': 0,
                'note': 'Local gates configured; account/model access not remotely tested.' if ready else 'NEBIUS_API_KEY is missing.'}
    except ProviderError as exc:
        return {'configured': False, 'live_calls_made': 0, 'note': str(exc)}
