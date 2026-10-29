"""Run the separate protected judge server. No cloud resources are provisioned."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from sixd.hosted_runtime import HostedRuntimeFactory, read_private_file
from sixd.hosted_server import HostedConfig, create_hosted_server
from sixd.providers import LiveConfig, ProviderError


def configured_server(environment, *, loopback_preview=False):
    try:
        live = environment.get('SIXD_LIVE_AI_ENABLED', '0')
        if live not in ('0', '1'):
            raise ValueError('SIXD_LIVE_AI_ENABLED must be 0 or 1.')
        root = Path(environment['SIXD_STATE_ROOT']).absolute()
        origin = environment['SIXD_PUBLIC_ORIGIN']
        code = read_private_file(environment['SIXD_JUDGE_ACCESS_CODE_FILE'], 4096).decode('utf-8').strip()
        host = environment.get('SIXD_HOST', '127.0.0.1')
        port = int(environment.get('SIXD_PORT', '8080'))
        if not 1 <= port <= 65535 or (loopback_preview and host != '127.0.0.1'):
            raise ValueError('Choose a valid port and loopback bind for local preview.')
        config = HostedConfig(root, origin, code, allow_loopback_http=loopback_preview)
        tavily_key_file = environment.get('SIXD_TAVILY_API_KEY_FILE')
        tavily_key = read_private_file(tavily_key_file, 4096).decode('utf-8').strip() if tavily_key_file else None
        tavily_cap = int(environment.get('SIXD_TAVILY_CREDIT_LIMIT', '4125'))
        if live == '1':
            if environment.get('SIXD_CUMULATIVE_LEDGER_HANDOFF_CONFIRMED') != '1':
                raise ValueError('Freeze and retire the previous ledger writer before confirming cumulative ledger handoff.')
            provider = LiveConfig.load(environment['SIXD_PROVIDER_CONFIG_FILE'])
            key = read_private_file(environment['SIXD_NEBIUS_API_KEY_FILE'], 16384).decode('utf-8').strip()
            factory = HostedRuntimeFactory(root, config=provider, api_key=key,
                prior_budget_path=environment['SIXD_PRIOR_BUDGET_FILE'],
                daily_cap_usd=float(environment['SIXD_INFERENCE_DAILY_CAP_USD']),
                session_cap_usd=float(environment['SIXD_INFERENCE_SESSION_CAP_USD']),
                tavily_api_key=tavily_key, tavily_credit_limit=tavily_cap)
        else:
            factory = HostedRuntimeFactory(root, tavily_api_key=tavily_key, tavily_credit_limit=tavily_cap)
        return config, factory, host, port
    except (KeyError, OSError, UnicodeError, TypeError, ValueError, ProviderError) as error:
        # Deliberately never echo submitted env values, paths, provider errors or keys.
        raise ValueError('Hosted configuration is incomplete or invalid. Review docs/HOSTED_DEPLOYMENT.md; no server started.') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-preview', action='store_true', help='Explicitly allow HTTP on loopback only; never a public deployment.')
    parser.add_argument('--check', action='store_true', help='Validate operator settings without listening or contacting providers.')
    args = parser.parse_args()
    try:
        config, factory, host, port = configured_server(os.environ, loopback_preview=args.local_preview)
        if args.check:
            print('Hosted configuration accepted. No listener, cloud resource or provider request created.')
            return 0
        with create_hosted_server(config, host=host, port=port, runtime_factory=factory) as server:
            print('Protected 6D judge server ready; use its configured public origin. Live AI: ' + ('off' if factory.config is None else 'explicit visitor action only'), flush=True)
            server.serve_forever()
        return 0
    except (ValueError, OSError):
        print('Hosted server did not start. Review the private operator configuration and deployment guide.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
