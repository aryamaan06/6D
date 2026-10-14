"""Replaceable tool-call providers. Network inference is opt-in and budget gated."""
from dataclasses import dataclass
from contextlib import closing
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler
import json
import math
import os
import sqlite3
import ssl


RESPONSE_TOO_LARGE = 'Provider response exceeded the bounded size.'
FAILURE_SUFFIX = ' Reservation retained; no automatic retry.'


def transport_failure(error):
    """Translate transport errors without copying remote text or credentials."""
    if isinstance(error, HTTPError):
        code = error.code if type(error.code) is int and 100 <= error.code <= 599 else 'unknown'
        return ProviderError(f'Nebius request failed: HTTP {code}.' + FAILURE_SUFFIX)
    if isinstance(error, (TimeoutError,)):
        return ProviderError('Nebius request timed out.' + FAILURE_SUFFIX)
    if isinstance(error, ssl.SSLError):
        return ProviderError('Nebius TLS connection failed.' + FAILURE_SUFFIX)
    if isinstance(error, URLError):
        reason = error.reason
        if isinstance(reason, TimeoutError):
            return ProviderError('Nebius request timed out.' + FAILURE_SUFFIX)
        if isinstance(reason, ssl.SSLError):
            return ProviderError('Nebius TLS connection failed.' + FAILURE_SUFFIX)
        return ProviderError('Nebius network connection failed.' + FAILURE_SUFFIX)
    if isinstance(error, json.JSONDecodeError):
        return ProviderError('Provider response was not valid JSON.' + FAILURE_SUFFIX)
    # _send has one controlled size error. Never echo arbitrary transport messages.
    if isinstance(error, ProviderError) and error.args == (RESPONSE_TOO_LARGE,):
        return ProviderError(RESPONSE_TOO_LARGE + FAILURE_SUFFIX)
    return ProviderError('Inference transport failed; private exception details were suppressed.' + FAILURE_SUFFIX)


class ProviderError(ValueError):
    """Safe operator-facing error; never includes a key or remote response body."""


@dataclass
class Turn:
    message: dict
    usage: dict
    request_id: str | None = None


class Provider(Protocol):
    mode: str
    model: str

    def complete(self, messages: list, tools: list) -> Turn: ...


class FixtureProvider:
    """Scripted orchestration fixture, without model inference or stored measurements."""
    mode = "fixture"
    model = "scripted-tool-sequence-v1"

    def complete(self, messages, tools):
        seen = [json.loads(m['content'])['id'] for m in messages if m['role'] == 'tool']
        available = {item['function']['name'] for item in tools}
        sequence = (('check_force', 'central_force_reference'),
                    ('check_refinement', 'analytic_reference_refinement'),
                    ('check_reversibility', 'method_time_reversal'))
        name = next((name for name, evidence_id in sequence if name in available and evidence_id not in seen), 'finish')
        args = {} if name != 'finish' else {'evidence_ids': seen}
        return Turn({'role': 'assistant', 'content': None, 'tool_calls': [
            {'id': f'fixture-{len(seen)}', 'type': 'function',
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

    @classmethod
    def load(cls, path):
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
            if any(data.get(k) is not True for k in
                   ('account_verified', 'model_license_reviewed', 'spend_approved')):
                raise ProviderError('Account, model license and user spending approval must be verified locally.')
            config = cls(**{k: data[k] for k in cls.__dataclass_fields__})
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
            if type(config.max_output_tokens) is not int or not 128 <= config.max_output_tokens <= 4096:
                raise ProviderError('Choose 128–4096 maximum output tokens.')
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
        try:
            with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
                db.execute('CREATE TABLE IF NOT EXISTS budget (id TEXT PRIMARY KEY, cap REAL, reserved REAL)')
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT id, cap, reserved FROM budget').fetchall()
                # One approval per ledger: changing an ID must not silently reset allowance.
                if row and (row[0][0] != config.approval_id or row[0][1] != config.spend_cap_usd):
                    raise ProviderError('The ledger approval/cap differs; budget changes require explicit operator review.')
                used = row[0][2] if row else 0.0
                if used + amount > config.spend_cap_usd:
                    raise ProviderError('The approved inference allowance is exhausted. No request was sent.')
                db.execute('INSERT OR REPLACE INTO budget VALUES (?, ?, ?)',
                           (config.approval_id, config.spend_cap_usd, used + amount))
        except sqlite3.Error:
            raise ProviderError('The budget ledger could not be locked or written. No request was sent.') from None


class TokenFactoryProvider:
    mode = 'live_token_factory'

    def __init__(self, config, ledger, *, api_key=None, transport=None):
        self.config, self.ledger = config, ledger
        self.model = config.model
        self.request_attempts = 0
        self._key = api_key or os.environ.get('NEBIUS_API_KEY')
        if not self._key:
            raise ProviderError('Set NEBIUS_API_KEY locally. No live call was made.')
        self._transport = transport or self._send
        if transport is not None:
            self.mode = 'offline_transport_fixture'

    def _send(self, request):
        with build_opener(NoRedirect()).open(request, timeout=45) as response:
            data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ProviderError(RESPONSE_TOO_LARGE)
            return json.loads(data)

    def complete(self, messages, tools):
        payload = {'model': self.model, 'messages': messages, 'tools': tools,
                   'tool_choice': 'auto', 'max_tokens': self.config.max_output_tokens,
                   'temperature': 0, 'stream': False}
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
            raise ProviderError('Invalid provider response structure.' + FAILURE_SUFFIX)
        choice = result['choices'][0]
        message, usage = choice.get('message'), result.get('usage', {})
        if not isinstance(message, dict) or not isinstance(usage, dict):
            raise ProviderError('Invalid provider response structure.' + FAILURE_SUFFIX)
        count_keys = ('prompt_tokens', 'completion_tokens', 'total_tokens')
        if any(key in usage and (type(usage[key]) is not int or usage[key] < 0) for key in count_keys):
            raise ProviderError('Invalid provider response structure.' + FAILURE_SUFFIX)
        # Preserve only token counts, never remote metadata or echoed credentials.
        counts = {k: v for k, v in usage.items() if k in
                  count_keys}
        if counts.get('prompt_tokens', 0) > input_bound or counts.get('completion_tokens', 0) > self.config.max_output_tokens:
            raise ProviderError('Usage exceeded the configured reservation bound; stop and review provider billing.' + FAILURE_SUFFIX)
        reason = choice.get('finish_reason')
        if reason != 'tool_calls':
            safe_reason = reason if isinstance(reason, str) and reason in (
                'length', 'stop', 'content_filter', 'function_call') else 'unknown'
            detail = (' The output token limit was reached; no complete tool response was accepted.'
                      if safe_reason == 'length' else ' A complete structured tool response is required.')
            raise ProviderError(f'Provider returned finish_reason={safe_reason}.' + detail + FAILURE_SUFFIX)
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
