"""Offline hosted spend boundaries; no provider account, key or transport."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd.hosted_limits import HostedProviderBudget, HostedSpendLedger
from sixd.providers import LiveConfig, ProviderError


SESSION = 'a' * 32
OTHER = 'b' * 32
CONFIG = LiveConfig('https://api.tokenfactory.nebius.com/v1/',
    'nvidia/offline-nemotron-hosted-test', 'synthetic-hosted-approval', 1, .06, .24)


class HostedSpendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'hosted-budget.sqlite3'
        self.now = '2026-10-25'

    def ledger(self, **kwargs):
        arguments = dict(approval_id=CONFIG.approval_id, total_cap_usd=1,
            daily_cap_usd=.5, session_cap_usd=.3, initial_reserved_usd=0, clock=lambda: self.now)
        arguments.update(kwargs)
        return HostedSpendLedger(self.path, **arguments)

    def test_exact_decimal_boundary_and_conservative_subnanodollar_rounding(self):
        ledger = self.ledger()
        ledger.reserve(SESSION, CONFIG, .1)
        ledger.reserve(SESSION, CONFIG, .2)
        status = ledger.status(SESSION)
        self.assertEqual(status['session_reserved_usd'], .3)
        self.assertEqual(status['session_remaining_usd'], 0)
        with self.assertRaises(ProviderError):
            ledger.reserve(SESSION, CONFIG, .0000000001)
        self.assertEqual(ledger.status(SESSION)['total_reserved_usd'], .3)
        self.path.unlink()
        tiny = self.ledger(total_cap_usd=.000000001, daily_cap_usd=.000000001,
            session_cap_usd=.000000001)
        config = replace(CONFIG, spend_cap_usd=.000000001)
        tiny.reserve(SESSION, config, .0000000001)
        self.assertEqual(tiny.status(SESSION)['total_reserved_usd'], .000000001)
        with self.assertRaises(ProviderError):
            tiny.reserve(SESSION, config, .0000000001)

    def test_session_allowance_survives_restart_and_later_days(self):
        ledger = self.ledger()
        ledger.reserve(SESSION, CONFIG, .3)
        self.now = '2026-10-26'
        restarted = self.ledger()
        with self.assertRaises(ProviderError) as error:
            restarted.reserve(SESSION, CONFIG, .01)
        self.assertEqual(error.exception.code, 'case_budget_exhausted')
        self.assertEqual(restarted.status(SESSION)['session_reserved_usd'], .3)
        self.assertEqual(restarted.status(SESSION)['daily_reserved_usd'], 0)

    def test_new_session_cannot_bypass_daily_or_total_allowance(self):
        ledger = self.ledger()
        ledger.reserve(SESSION, CONFIG, .3)
        ledger.reserve(OTHER, CONFIG, .2)
        with self.assertRaises(ProviderError) as error:
            ledger.reserve('c' * 32, CONFIG, .01)
        self.assertEqual(error.exception.code, 'batch_budget_exhausted')
        self.now = '2026-10-26'
        ledger.reserve('c' * 32, CONFIG, .3)
        ledger.reserve('d' * 32, CONFIG, .2)
        self.now = '2026-10-27'
        with self.assertRaises(ProviderError) as error:
            ledger.reserve('e' * 32, CONFIG, .01)
        self.assertEqual(error.exception.code, 'cumulative_budget_exhausted')
        self.assertEqual(ledger.status()['total_reserved_usd'], 1)

    def test_policy_changes_fail_closed_and_do_not_rewrite_approval(self):
        ledger = self.ledger()
        ledger.reserve(SESSION, CONFIG, .1)
        for change in [dict(approval_id='another-approval'), dict(total_cap_usd=2),
                       dict(daily_cap_usd=.6), dict(session_cap_usd=.2)]:
            with self.subTest(change=change), self.assertRaises(ProviderError) as error:
                self.ledger(**change)
            self.assertEqual(error.exception.code, 'budget_approval_mismatch')
        self.assertEqual(self.ledger().status(SESSION)['total_reserved_usd'], .1)

    def test_provider_approval_or_cap_mismatch_cannot_reserve(self):
        ledger = self.ledger()
        for config in [replace(CONFIG, approval_id='unapproved'), replace(CONFIG, spend_cap_usd=.5),
                       replace(CONFIG, spend_cap_usd=2)]:
            with self.subTest(config=config), self.assertRaises(ProviderError):
                ledger.reserve(SESSION, config, .1)
        self.assertEqual(ledger.status()['total_reserved_usd'], 0)

    def test_invalid_amounts_and_sessions_leave_all_counters_unchanged(self):
        ledger = self.ledger()
        for amount in [0, -1, True, None, '0.01', float('nan'), float('inf'), 1e300]:
            with self.subTest(amount=amount), self.assertRaises(ProviderError):
                ledger.reserve(SESSION, CONFIG, amount)
        for identity in ['', 'short', '../' + SESSION, SESSION + '\n', None, 9]:
            with self.subTest(identity=identity), self.assertRaises(ProviderError):
                ledger.reserve(identity, CONFIG, .1)
        self.assertEqual(ledger.status()['total_reserved_usd'], 0)

    def test_invalid_policy_is_rejected_without_creating_approval(self):
        for change in [dict(total_cap_usd=30), dict(daily_cap_usd=2), dict(session_cap_usd=.6),
                       dict(total_cap_usd=True), dict(total_cap_usd=.0000000001),
                       dict(approval_id=''), dict(approval_id='has spaces')]:
            with self.subTest(change=change), self.assertRaises(ProviderError):
                self.ledger(**change)
        self.assertFalse(self.path.exists())

    def test_concurrent_sessions_cannot_overreserve_the_day(self):
        ledger = self.ledger(session_cap_usd=.5)
        def attempt(index):
            try:
                ledger.reserve(format(index, '032x'), CONFIG, .1)
                return True
            except ProviderError:
                return False
        with ThreadPoolExecutor(max_workers=12) as executor:
            results = list(executor.map(attempt, range(20)))
        self.assertEqual(sum(results), 5)
        self.assertEqual(ledger.status()['daily_reserved_usd'], .5)
        self.assertEqual(ledger.status()['total_reserved_usd'], .5)

    def test_backward_utc_clock_does_not_reopen_previous_day(self):
        ledger = self.ledger()
        ledger.reserve(SESSION, CONFIG, .1)
        self.now = '2026-10-26'
        ledger.reserve(OTHER, CONFIG, .1)
        self.now = '2026-10-25'
        with self.assertRaises(ProviderError):
            ledger.reserve('c' * 32, CONFIG, .1)
        with self.assertRaises(ProviderError):
            ledger.status()
        self.now = '2026-10-26'
        self.assertEqual(ledger.status()['total_reserved_usd'], .2)

    def test_clock_must_be_aware_or_an_exact_iso_day(self):
        for value in [datetime(2026, 10, 25), '2026-1-2', '2026-02-30', None, 123]:
            with self.subTest(value=value), self.assertRaises(ProviderError):
                self.ledger(clock=lambda: value)
        # Local offset is converted to UTC instead of opening a local-time day.
        ledger = self.ledger(clock=lambda: datetime(2026, 10, 26, 1, tzinfo=timezone(timedelta(hours=5, minutes=30))))
        self.assertEqual(ledger.status()['day_utc'], '2026-10-25')

    def test_status_is_read_only_and_does_not_disclose_session_identities(self):
        ledger = self.ledger()
        ledger.reserve(OTHER, CONFIG, .1)
        before = self.path.read_bytes()
        status = ledger.status(SESSION)
        self.assertEqual(status['session_reserved_usd'], 0)
        self.assertEqual(status['total_reserved_usd'], .1)
        self.assertNotIn(OTHER, str(status))
        self.assertNotIn(SESSION, str(status))
        self.assertEqual(self.path.read_bytes(), before)

    def test_counter_corruption_or_missing_policy_fails_closed(self):
        ledger = self.ledger()
        ledger.reserve(SESSION, CONFIG, .1)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE sessions SET reserved=0')
        with self.assertRaises(ProviderError):
            ledger.reserve(OTHER, CONFIG, .1)
        with self.assertRaises(ProviderError):
            ledger.status()
        with self.assertRaises(ProviderError):
            self.ledger()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('DELETE FROM policy')
        with self.assertRaises(ProviderError):
            self.ledger()

    def test_unavailable_storage_has_controlled_error_without_path_echo(self):
        self.path.mkdir()
        with self.assertRaises(ProviderError) as error:
            self.ledger()
        self.assertNotIn(str(self.path), str(error.exception))

    def test_prior_development_reservations_consume_total_but_not_new_day_or_session(self):
        ledger = self.ledger(initial_reserved_usd=.8)
        status = ledger.status(SESSION)
        self.assertEqual(status['total_reserved_usd'], .8)
        self.assertEqual(status['prior_reserved_usd'], .8)
        self.assertEqual(status['daily_reserved_usd'], 0)
        self.assertEqual(status['session_reserved_usd'], 0)
        ledger.reserve(SESSION, CONFIG, .2)
        with self.assertRaises(ProviderError) as error:
            ledger.reserve(OTHER, CONFIG, .01)
        self.assertEqual(error.exception.code, 'cumulative_budget_exhausted')
        self.assertEqual(ledger.status(SESSION)['hosted_reserved_usd'], .2)
        self.assertEqual(self.ledger(initial_reserved_usd=.8).status()['total_reserved_usd'], 1)
        with self.assertRaises(ProviderError):
            self.ledger(initial_reserved_usd=0)

    def test_prior_reservations_cannot_be_invalid_or_fractionally_underreserved(self):
        for value in [-1, True, '0.5', float('nan'), float('inf'), 2]:
            with self.subTest(value=value), self.assertRaises(ProviderError):
                self.ledger(initial_reserved_usd=value)
        ledger = self.ledger(initial_reserved_usd=.30000000000000004)
        self.assertEqual(ledger.status()['prior_reserved_usd'], .300000001)

    def test_wrapper_requires_both_reservations_and_retains_host_on_local_failure(self):
        ledger = self.ledger()
        class ExistingBudget:
            count = 0
            reserved = 0
            def reserve(self, config, amount):
                self.count += 1
                raise ProviderError('Synthetic local session changed.', code='session_changed')
        shared = ExistingBudget()
        wrapper = HostedProviderBudget(shared, ledger, SESSION)
        with self.assertRaises(ProviderError):
            wrapper.reserve(CONFIG, .1)
        self.assertEqual(wrapper.count, 1)
        self.assertEqual(ledger.status(SESSION)['total_reserved_usd'], .1)

    def test_host_exhaustion_prevents_original_job_reservation(self):
        ledger = self.ledger()
        ledger.reserve(SESSION, CONFIG, .3)
        class ExistingBudget:
            def reserve(self, config, amount):
                self.fail = True
        shared = ExistingBudget()
        with self.assertRaises(ProviderError):
            HostedProviderBudget(shared, ledger, SESSION).reserve(CONFIG, .1)
        self.assertFalse(hasattr(shared, 'fail'))
        self.assertEqual(ledger.status()['total_reserved_usd'], .3)

    def test_successful_wrapper_preserves_existing_job_bookkeeping(self):
        ledger = self.ledger()
        class ExistingBudget:
            count = 0
            reserved = 0
            def reserve(self, config, amount):
                self.count += 1
                self.reserved += amount
        shared = ExistingBudget()
        wrapper = HostedProviderBudget(shared, ledger, SESSION)
        wrapper.reserve(CONFIG, .1)
        self.assertEqual(wrapper.count, 1)
        self.assertEqual(wrapper.reserved, .1)
        self.assertEqual(ledger.status(SESSION)['session_reserved_usd'], .1)


if __name__ == '__main__':
    unittest.main()
