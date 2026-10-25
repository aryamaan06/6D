"""Persistent hosted inference reservations, in addition to existing job limits.

No provider is called here. One SQLite transaction reserves against the hosted
total, the UTC day and a stable visitor session. A failed/unknown request never
refunds a reservation. This ledger is separate from the founder's local data.
"""
from contextlib import closing
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path
import math
import re
import sqlite3

from .providers import ProviderError


_SCALE = Decimal(1_000_000_000)  # Integer nanodollars; reservations round upward.
_MAX_CAP = Decimal('29.50')
_SESSION = re.compile(r'[A-Za-z0-9_-]{16,128}\Z')
_MAX_SESSIONS = 4096
_MAX_DAYS = 4096


def _error(message='Hosted reservation storage needs operator review.', code='budget_ledger_error'):
    return ProviderError(message + ' No request was sent.', code=code)


def _units(value, *, cap=False):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise _error('A positive finite hosted allowance or reservation is required.', 'budget_reservation_invalid')
    try:
        amount = Decimal(str(value)) * _SCALE
        # Caps cannot be rounded upward: an operator approves the exact ceiling.
        if cap and (amount != amount.to_integral_value() or Decimal(str(value)) > _MAX_CAP):
            raise ValueError
        result = int(amount.to_integral_value(rounding=ROUND_CEILING))
        if not 0 < result <= int(_MAX_CAP * _SCALE):
            raise ValueError
        return result
    except (InvalidOperation, ValueError, OverflowError):
        raise _error('The hosted amount exceeds the supported approved ceiling.', 'budget_reservation_invalid') from None


def _money(units):
    return float(Decimal(units) / _SCALE)


def _session(value):
    if not isinstance(value, str) or not _SESSION.fullmatch(value):
        raise _error('A stable hosted session identity is required.', 'configuration_error')
    return value


class HostedSpendLedger:
    """Atomically enforce one fixed approval across session, UTC-day and total caps.

    ``clock`` optionally returns an aware datetime or an ISO ``YYYY-MM-DD`` day
    for offline tests. Backward UTC days fail closed instead of reopening a day.
    The constructor validates/initializes policy only; it never makes a provider
    request. Policy changes and deleting/resetting this file are operator acts,
    never HTTP actions. Up to 4,096 lifetime session/day counters are retained.
    ``initial_reserved_usd`` is required: it carries earlier approved development
    reservations into the immutable total. At activation, the prior independently
    writable ledger must stop authorizing requests; a snapshot cannot account for
    later concurrent usage on another machine.
    """
    def __init__(self, path, *, approval_id, total_cap_usd, daily_cap_usd,
                 session_cap_usd, initial_reserved_usd, clock=None):
        if (not isinstance(approval_id, str) or not 1 <= len(approval_id) <= 200
                or approval_id.strip() != approval_id or any(ord(ch) < 33 or ord(ch) > 126 for ch in approval_id)):
            raise _error('An explicit hosted approval identity is required.', 'configuration_error')
        self.path = Path(path)
        self.approval_id = approval_id
        self.total_cap = _units(total_cap_usd, cap=True)
        self.daily_cap = _units(daily_cap_usd, cap=True)
        self.session_cap = _units(session_cap_usd, cap=True)
        if (type(initial_reserved_usd) not in (int, float) or not math.isfinite(initial_reserved_usd)
                or initial_reserved_usd < 0):
            raise _error('Existing approved reservations must be carried forward.', 'configuration_error')
        self.initial_reserved = _units(initial_reserved_usd) if initial_reserved_usd else 0
        if not self.session_cap <= self.daily_cap <= self.total_cap:
            raise _error('Hosted session/day ceilings must fit within the total approval.', 'configuration_error')
        if self.initial_reserved > self.total_cap:
            raise _error('Earlier reservations exceed the hosted total approval.', 'configuration_error')
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('CREATE TABLE IF NOT EXISTS policy (singleton INTEGER PRIMARY KEY CHECK(singleton=1), approval TEXT NOT NULL, total_cap INTEGER NOT NULL, daily_cap INTEGER NOT NULL, session_cap INTEGER NOT NULL, initial_reserved INTEGER NOT NULL, reserved INTEGER NOT NULL, last_day TEXT NOT NULL)')
                db.execute('CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, reserved INTEGER NOT NULL)')
                db.execute('CREATE TABLE IF NOT EXISTS days (day TEXT PRIMARY KEY, reserved INTEGER NOT NULL)')
                if not db.execute('SELECT 1 FROM policy').fetchone():
                    if db.execute('SELECT 1 FROM sessions').fetchone() or db.execute('SELECT 1 FROM days').fetchone():
                        raise _error()
                    db.execute('INSERT INTO policy VALUES (1,?,?,?,?,?,?,?)',
                        (self.approval_id, self.total_cap, self.daily_cap, self.session_cap,
                         self.initial_reserved, self.initial_reserved, self._day()))
                self._read(db)
        except (sqlite3.Error, OSError):
            raise _error() from None

    def _day(self):
        try:
            value = self._clock()
            if isinstance(value, datetime):
                if value.tzinfo is None or value.utcoffset() is None:
                    raise ValueError
                return value.astimezone(timezone.utc).date().isoformat()
            if isinstance(value, str) and date.fromisoformat(value).isoformat() == value:
                return value
            raise ValueError
        except Exception:
            raise _error('The UTC reservation clock is unavailable.') from None

    def _read(self, db):
        rows = db.execute('SELECT singleton,approval,total_cap,daily_cap,session_cap,initial_reserved,reserved,last_day FROM policy').fetchall()
        if (len(rows) != 1 or rows[0][:6] != (1, self.approval_id, self.total_cap, self.daily_cap, self.session_cap, self.initial_reserved)):
            raise _error('The hosted approval or ceilings changed; operator review is required.', 'budget_approval_mismatch')
        _, _, _, _, _, _, reserved, last_day = rows[0]
        sessions = db.execute('SELECT session_id,reserved FROM sessions').fetchall()
        days = db.execute('SELECT day,reserved FROM days').fetchall()
        try:
            if (type(reserved) is not int or not self.initial_reserved <= reserved <= self.total_cap
                    or not isinstance(last_day, str) or date.fromisoformat(last_day).isoformat() != last_day
                    or len(sessions) > _MAX_SESSIONS or len(days) > _MAX_DAYS):
                raise ValueError
            if any(not isinstance(identity, str) or not _SESSION.fullmatch(identity)
                   or type(amount) is not int or not 0 < amount <= self.session_cap for identity, amount in sessions):
                raise ValueError
            if any(not isinstance(day, str) or date.fromisoformat(day).isoformat() != day or day > last_day
                   or type(amount) is not int or not 0 < amount <= self.daily_cap for day, amount in days):
                raise ValueError
            if (reserved - self.initial_reserved != sum(amount for _, amount in sessions)
                    or reserved - self.initial_reserved != sum(amount for _, amount in days)):
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            raise _error() from None
        return reserved, last_day, dict(sessions), dict(days)

    def reserve(self, session_id, config, amount):
        """Reserve before dispatch. The existing job/local ledger must also pass."""
        session_id, amount_units = _session(session_id), _units(amount)
        if (getattr(config, 'approval_id', None) != self.approval_id
                or _units(getattr(config, 'spend_cap_usd', None), cap=True) != self.total_cap):
            raise _error('Provider approval differs from the hosted approval.', 'budget_approval_mismatch')
        day = self._day()
        try:
            with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
                db.execute('BEGIN IMMEDIATE')
                used, last_day, sessions, days = self._read(db)
                if day < last_day:
                    raise _error('The UTC reservation clock moved backward; operator review is required.')
                session_used, day_used = sessions.get(session_id, 0), days.get(day, 0)
                if used + amount_units > self.total_cap:
                    raise _error('The hosted total allowance is exhausted.', 'cumulative_budget_exhausted')
                if day_used + amount_units > self.daily_cap:
                    raise _error('The hosted UTC-day allowance is exhausted.', 'batch_budget_exhausted')
                if session_used + amount_units > self.session_cap:
                    raise _error('This hosted session allowance is exhausted.', 'case_budget_exhausted')
                if ((session_id not in sessions and len(sessions) >= _MAX_SESSIONS)
                        or (day not in days and len(days) >= _MAX_DAYS)):
                    raise _error('Hosted accounting reached its retained-counter limit.')
                db.execute('UPDATE policy SET reserved=?,last_day=? WHERE singleton=1', (used + amount_units, day))
                db.execute('INSERT OR REPLACE INTO sessions VALUES (?,?)', (session_id, session_used + amount_units))
                db.execute('INSERT OR REPLACE INTO days VALUES (?,?)', (day, day_used + amount_units))
        except (sqlite3.Error, OSError):
            raise _error() from None

    def status(self, session_id=None):
        """Return caps/conservative usage, never keys or other session identities."""
        if session_id is not None:
            _session(session_id)
        day = self._day()
        try:
            with closing(sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True, timeout=10)) as db:
                db.execute('BEGIN')
                used, last_day, sessions, days = self._read(db)
                if day < last_day:
                    raise _error('The UTC reservation clock moved backward; operator review is required.')
                day_used, session_used = days.get(day, 0), sessions.get(session_id, 0)
                return {'schema': 'sixd.hosted-spending.v1', 'approval_id': self.approval_id,
                    'total_cap_usd': _money(self.total_cap), 'total_reserved_usd': _money(used),
                    'prior_reserved_usd': _money(self.initial_reserved),
                    'hosted_reserved_usd': _money(used - self.initial_reserved),
                    'total_remaining_usd': _money(self.total_cap - used),
                    'day_utc': day, 'daily_cap_usd': _money(self.daily_cap),
                    'daily_reserved_usd': _money(day_used), 'daily_remaining_usd': _money(self.daily_cap - day_used),
                    'session_cap_usd': _money(self.session_cap),
                    'session_reserved_usd': _money(session_used) if session_id is not None else None,
                    'session_remaining_usd': _money(self.session_cap - session_used) if session_id is not None else None,
                    'accounting': 'Conservative reservations, not provider charges. Failed or unknown requests retain reservations.'}
        except (sqlite3.Error, OSError):
            raise _error() from None


class HostedProviderBudget:
    """Require hosted and existing job/local reservations before provider dispatch.

    Hosted reservation occurs first. If the existing job/session check then fails,
    its hosted reservation is retained conservatively; no provider call can follow
    either failure. This intentionally favors unused allowance over overspending.
    """
    def __init__(self, shared_job_budget, hosted_ledger, session_id):
        self.shared = shared_job_budget
        self.hosted = hosted_ledger
        self.session_id = _session(session_id)

    def reserve(self, config, amount):
        self.hosted.reserve(self.session_id, config, amount)
        self.shared.reserve(config, amount)

    def __getattr__(self, name):
        return getattr(self.shared, name)
