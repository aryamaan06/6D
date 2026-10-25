"""Operator-owned hosted inference; disabled unless explicitly configured.

No visitor credential routes are exposed. Deployment must carry forward a frozen
development ledger and retire that ledger's old writer before enabling live AI.
Nothing in this module contacts a provider on construction or restoration.
"""
from dataclasses import asdict
import json
import math
from pathlib import Path
import sqlite3

from .credential_store import valid_key
from .hosted_limits import HostedProviderBudget, HostedSpendLedger
from .project_investigation import ProjectActionAdapter
from .providers import LiveConfig, ProviderError, TokenFactoryProvider
from .workspace_ai import MAX_APPROVED_ALLOWANCE_USD
from .workspace_server import WorkspaceRuntime


def read_private_file(path, maximum=32768):
    """Read an operator-selected regular secret/config file, with bounded input."""
    try:
        path = Path(path)
        if not path.is_file():
            raise ValueError
        with path.open('rb') as stream:
            value = stream.read(maximum + 1)
        if not value or len(value) > maximum:
            raise ValueError
        return value
    except (OSError, ValueError, TypeError):
        raise ValueError('A required operator file is missing, unreadable or outside its size limit.') from None


def carried_reservation(path, config):
    """Read-only import of the frozen cumulative ledger; never invent zero usage."""
    try:
        source = Path(path).resolve(strict=True)
        db = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=10)
        try:
            rows = db.execute('SELECT id,cap,reserved FROM budget').fetchall()
        finally:
            db.close()
        if (len(rows) != 1 or rows[0][0] != config.approval_id
                or rows[0][1] != config.spend_cap_usd
                or type(rows[0][2]) not in (int, float) or not math.isfinite(rows[0][2])
                or not 0 <= rows[0][2] <= config.spend_cap_usd):
            raise ValueError
        return rows[0][2]
    except (OSError, ValueError, TypeError, sqlite3.Error):
        raise ValueError('The frozen cumulative ledger does not match the operator-approved provider configuration.') from None


class HostedRuntimeFactory:
    def __init__(self, state_root, *, config=None, api_key=None, prior_budget_path=None,
                 daily_cap_usd=None, session_cap_usd=None, transport=None):
        self.state_root = Path(state_root).resolve()
        self.config, self._key, self._transport, self.ledger = config, api_key, transport, None
        if config is None:
            if any(x is not None for x in (api_key, prior_budget_path, daily_cap_usd, session_cap_usd, transport)):
                raise ValueError('Live inference requires the complete explicit operator configuration.')
            return
        if (not isinstance(config, LiveConfig) or not valid_key(api_key)
                or not 0 < config.spend_cap_usd <= MAX_APPROVED_ALLOWANCE_USD
                or config.inference_profile != 'native_no_thinking'
                or config.selection_protocol != 'forced_action_v1'):
            raise ValueError('Hosted inference settings must satisfy the established project protocol and approved allowance.')
        if prior_budget_path is None:
            raise ValueError('Live hosting requires the frozen cumulative ledger; existing usage cannot be reset.')
        prior = carried_reservation(prior_budget_path, config)
        self.ledger = HostedSpendLedger(self.state_root / 'hosted-budget.sqlite3',
            approval_id=config.approval_id, total_cap_usd=config.spend_cap_usd,
            daily_cap_usd=daily_cap_usd, session_cap_usd=session_cap_usd,
            initial_reserved_usd=prior)

    def __call__(self, folder, session_id):
        folder = Path(folder).resolve()
        if not folder.is_relative_to(self.state_root):
            raise ValueError('Hosted sessions must stay inside their separate persistent state directory.')
        private = folder / 'private'
        private.mkdir(parents=True, exist_ok=True)
        config_path = private / 'token-factory.json'
        if self.config is None:
            # An operator must not silently downgrade an existing live deployment.
            if config_path.exists():
                raise ValueError('This session has live settings. Review the operator mode before reopening it.')
        else:
            value = {**asdict(self.config), 'account_verified': True,
                     'model_license_reviewed': True, 'spend_approved': True}
            encoded = json.dumps(value, sort_keys=True, allow_nan=False).encode()
            if config_path.exists() and config_path.read_bytes() != encoded:
                raise ValueError('Saved hosted provider settings changed; explicit operator review is required.')
            if not config_path.exists():
                config_path.write_bytes(encoded)
        runtime = WorkspaceRuntime(folder / 'workspace.sqlite3', ai_local_directory=private,
                                   allow_environment_key=False)
        if self.config is not None:
            runtime.ai._key = self._key
            runtime.ai._key_source = 'hosted_operator'
            runtime.ai._provider_mode = 'offline_transport_fixture' if self._transport is not None else 'live_token_factory'
            runtime.hosted_spending = lambda: self.ledger.status(session_id)

            def hosted_budget(config):
                if config != self.config:
                    raise ProviderError('Hosted provider settings changed.', code='configuration_error')
                value = self.ledger.status(session_id)
                return {'cap_usd': value['total_cap_usd'], 'reserved_usd': value['total_reserved_usd'],
                        'remaining_usd': value['total_remaining_usd'],
                        'hosted_limits': value, 'accounting': value['accounting']}

            runtime.ai._budget = hosted_budget

            def provider(config, budget, key):
                if config != self.config or key != self._key:
                    raise ProviderError('Hosted provider configuration changed; no request was sent.', code='configuration_error')
                return TokenFactoryProvider(config, HostedProviderBudget(budget, self.ledger, session_id),
                    api_key=key, transport=self._transport, action_adapter=ProjectActionAdapter())

            runtime.ai._factory = provider
        return runtime
