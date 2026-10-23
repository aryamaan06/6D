"""Recorded time histories: explicit CSV mappings, replay and frozen comparisons.

No solver, interpolation, unit conversion or canonical finding is run or changed.
"""
from copy import deepcopy
import csv
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import io
import json
import math
from pathlib import Path
import re
import sys
import threading
from uuid import uuid4

from . import workspace
from .project_io import _reject_constant, _unique_object
from .workspace import ConflictError, WorkspaceError, _digest, _encode, _now, _revision

SPEC_SCHEMA = 'sixd.series-spec.v1'
SCHEMA = 'sixd.simulation-import.v1'
MAX_CSV_BYTES, MAX_ROWS, MAX_COLUMNS, MAX_CHANNELS = 4 * 1024 * 1024, 16385, 32, 12
MAX_RECEIPT_BYTES = 96 * 1024 * 1024
LIMITS = dict(max_csv_bytes=MAX_CSV_BYTES, max_rows=MAX_ROWS, max_columns=MAX_COLUMNS,
              max_channels=MAX_CHANNELS, max_field_characters=4096, history_limit=20)
LIMITATIONS = [
    'Imported records are supplied data; authenticity, calibration and physical applicability are not verified.',
    'Configuration and matching conditions are unverified user declarations, not independent model validation.',
    'Only exact timestamps, explicit matching units, reference frame and model-start time origin can be compared; no interpolation, fitting or conversion is performed.',
    'Comparison requires supported retained canonical numerical evidence and an explicit absolute tolerance per channel. Agreement is not proof of physical correctness.',
    'Imported histories and discrepancies never change canonical project requirement findings or establish launch readiness.',
    'CSV is retained as untrusted text, never evaluated as expressions. Numbers use finite binary floating point; unsigned digests check consistency, not authenticity.',
]
_NUMBER = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z')
_ID = re.compile(r'[a-f0-9]{32}\Z')
ORBIT_FIELDS = {**{f'position_{a}': 'm' for a in 'xyz'}, **{f'velocity_{a}': 'm/s' for a in 'xyz'}, 'radius_m': 'm', 'speed_m_s': 'm/s'}
FLIGHT_FIELDS = dict(altitude_m='m', velocity_m_s='m/s', mass_kg='kg', dynamic_pressure_pa='Pa', acceleration_m_s2='m/s^2', thrust_n='N', drag_n='N')


def _sources():
    return {**workspace._sources(), 'workspace_series.py': sha256(Path(__file__).read_bytes()).hexdigest()}


_LOADED_SOURCES = _sources()


def _text(value, label, maximum=1200, empty=False):
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()):
        raise WorkspaceError(f'{label} requires {"text" if empty else "nonempty text"} up to {maximum} characters.')
    return value.strip()


def _number(text):
    if not isinstance(text, str) or not _NUMBER.fullmatch(text):
        raise WorkspaceError('Mapped numeric cells require finite decimal/scientific numbers, without expressions or units.')
    try:
        decimal = Decimal(text)
        value = float(text)
        if (not math.isfinite(value) or (decimal != 0 and abs(value) < sys.float_info.min)
                or (decimal == decimal.to_integral_value() and abs(decimal) > 2**53 - 1)):
            raise ValueError('range')
        return value
    except (ValueError, OverflowError, InvalidOperation) as exc:
        raise WorkspaceError('Mapped numbers cannot overflow, underflow, be subnormal or exceed exact safe-integer range.') from exc


def validate_spec(spec):
    fields = {'schema', 'name', 'source', 'data_kind', 'configuration', 'frame', 'time_origin', 'conditions_match',
              'filename', 'csv_text', 'time_column', 'time_unit', 'model_id', 'channels'}
    if not isinstance(spec, dict) or set(spec) != fields or spec.get('schema') != SPEC_SCHEMA:
        raise WorkspaceError('Supply exactly the fields in a sixd.series-spec.v1 specification.')
    result = deepcopy(spec)
    for key, maximum in [('name',120), ('source',1200), ('configuration',2400), ('frame',120), ('time_origin',120), ('filename',240), ('time_column',128)]:
        result[key] = _text(spec[key], key, maximum)
    result['model_id'] = _text(spec['model_id'], 'Model ID', 120, empty=True)
    if spec['data_kind'] not in ('simulation', 'synthetic', 'measured') or spec['conditions_match'] not in ('declared_match','different','unknown'):
        raise WorkspaceError('Choose an explicit data kind and matching-conditions declaration.')
    if spec['time_unit'] != 's':
        raise WorkspaceError('Time unit must be s; no time conversion is inferred.')
    channels = spec['channels']
    if not isinstance(channels, list) or not 1 <= len(channels) <= MAX_CHANNELS:
        raise WorkspaceError('Map between one and twelve channels.')
    result['channels'] = []
    for channel in channels:
        if not isinstance(channel, dict) or set(channel) != {'name','column','unit','baseline_field','tolerance'}:
            raise WorkspaceError('Each channel requires name, column, unit, baseline_field and tolerance.')
        c = {key: _text(channel[key], key, 128, empty=key == 'baseline_field') for key in ('name','column','unit','baseline_field')}
        tolerance = channel['tolerance']
        if tolerance is not None:
            if type(tolerance) not in (int,float) or tolerance < 0:
                raise WorkspaceError('Channel tolerance must be a nonnegative finite number or null.')
            _number(str(tolerance))
        c['tolerance'] = tolerance
        result['channels'].append(c)
    if len({c['name'] for c in result['channels']}) != len(channels):
        raise WorkspaceError('Channel names must be distinct.')
    selected = [result['time_column']] + [c['column'] for c in result['channels']]
    if len(set(selected)) != len(selected):
        raise WorkspaceError('Map each CSV column at most once, including time.')
    text = spec['csv_text']
    try:
        encoded = text.encode('utf-8', errors='strict') if isinstance(text, str) else b''
    except UnicodeError as exc:
        raise WorkspaceError('CSV must be valid UTF-8 text.') from exc
    if not encoded or len(encoded) > MAX_CSV_BYTES or '\0' in text:
        raise WorkspaceError('Supply nonempty CSV text no larger than 4 MiB without NUL characters.')
    rows = []
    try:
        for row in csv.reader(io.StringIO(text.removeprefix('\ufeff'), newline=''), strict=True):
            if len(row) > MAX_COLUMNS or any(len(v) > 4096 for v in row):
                raise WorkspaceError('CSV supports at most 32 columns and 4096 characters per field.')
            rows.append(row)
            if len(rows) > MAX_ROWS + 1:
                raise WorkspaceError('CSV supports at most 16385 data rows.')
    except csv.Error as exc:
        raise WorkspaceError('Malformed CSV: ' + str(exc)) from exc
    if len(rows) < 3:
        raise WorkspaceError('CSV requires a header and at least two data rows.')
    columns = rows[0]
    if (not columns or any(not c.strip() or len(c) > 128 or c != c.strip() for c in columns)
            or len(set(columns)) != len(columns) or any(c not in columns for c in selected)
            or any(len(r) != len(columns) for r in rows[1:])):
        raise WorkspaceError('CSV needs distinct nonempty headers, existing mapped columns and consistent row widths.')
    indices = [columns.index(c) for c in selected]
    values = [[_number(row[i].strip()) for i in indices] for row in rows[1:]]
    times = [r[0] for r in values]
    if times[0] < 0 or any(a >= b for a,b in zip(times, times[1:])):
        raise WorkspaceError('Time samples must be nonnegative and strictly increasing.')
    if not result['model_id'] and any(c['baseline_field'] for c in result['channels']):
        raise WorkspaceError('Unbound replay channels must leave baseline_field empty.')
    parsed = dict(times=times, channels=[dict(name=c['name'], unit=c['unit'], values=[r[i+1] for r in values]) for i,c in enumerate(result['channels'])],
                  csv_sha256=sha256(encoded).hexdigest(), row_count=len(values), columns=columns)
    return result, parsed


def preview(spec):
    normalized, parsed = validate_spec(spec)
    return dict(schema='sixd.series-preview.v1', spec=normalized, parsed=parsed, limits=deepcopy(LIMITS), limitations=deepcopy(LIMITATIONS))


def _comparisons(spec, parsed, baseline):
    result = baseline['run']['model_results'].get(spec['model_id']) if baseline else None
    kind = result.get('model_type') if result else None
    artifact = result.get('simulation' if kind == 'orbital_trajectory' else 'flight_response', {}) if result else {}
    fields = ORBIT_FIELDS if kind == 'orbital_trajectory' else FLIGHT_FIELDS if kind == 'powered_flight' else {}
    frame = 'body_centered_inertial_3d' if kind == 'orbital_trajectory' else 'radial_vertical_above_launch_surface'
    numerical = bool(result and ((result.get('numerical_accuracy', {}).get('status') == 'supported') if kind == 'orbital_trajectory' else artifact.get('diagnostics', {}).get('grid_agreement_met') is True))
    rows = artifact.get('samples', [])
    outputs = []
    for channel, imported in zip(spec['channels'], parsed['channels']):
        field = channel['baseline_field']
        out = dict(name=channel['name'], status='not_assessed', reason='', aligned_samples=0, unmatched_samples=len(parsed['times']),
                   max_absolute_difference=None, within_count=0, outside_count=0)
        gap = ('No canonical baseline is bound; this is a recorded replay.' if not baseline else
               'The selected model has no completed supported time-history result.' if not result or result.get('status') != 'completed' or not rows or not fields else
               'This channel has no supported canonical field mapping.' if field not in fields else
               'Units must match the canonical field exactly; no conversion is performed.' if channel['unit'] != fields[field] else
               'Reference frame must exactly match the canonical history.' if spec['frame'] != frame else
               'Comparison requires the explicit model_start time origin.' if spec['time_origin'] != 'model_start' else
               'Matching configuration and conditions have not been declared.' if spec['conditions_match'] != 'declared_match' else
               'The canonical result lacks supported numerical accuracy evidence.' if not numerical else
               'An explicit absolute tolerance is required for this channel.' if channel['tolerance'] is None else '')
        if gap:
            out['reason'] = gap
            outputs.append(out)
            continue
        def value(row):
            if kind == 'orbital_trajectory' and field.startswith(('position_', 'velocity_')):
                return row['position_m' if field.startswith('position_') else 'velocity_m_s']['xyz'.index(field[-1])]
            return row[field]
        by_time = {}
        for row in rows:
            by_time.setdefault(row['time_s'], []).append(value(row))
        differences, ambiguous, overflow = [], False, False
        for t,v in zip(parsed['times'], imported['values']):
            matches = by_time.get(t, [])
            if not matches:
                continue
            if any(candidate != matches[0] for candidate in matches):
                ambiguous = True
                continue
            difference = abs(v - matches[0])
            if not math.isfinite(difference):
                overflow = True
            differences.append(difference)
        out['aligned_samples'] = len(differences)
        out['unmatched_samples'] = len(parsed['times']) - len(differences)
        out['within_count'] = sum(d <= channel['tolerance'] for d in differences)
        out['outside_count'] = len(differences) - out['within_count']
        out['max_absolute_difference'] = None if overflow or not differences else max(differences)
        if ambiguous or overflow:
            out['reason'] = 'A canonical event timestamp has different before/after values; event-side mapping is required.' if ambiguous else 'A difference exceeds finite numeric range; no aggregate agreement is asserted.'
        elif not differences:
            out['reason'] = 'No exact timestamps overlap; no interpolation is performed.'
        elif out['unmatched_samples']:
            out['status'] = 'partial'
            out['reason'] = 'Only a subset of imported timestamps aligns exactly; counts describe that subset, not the whole history.'
        else:
            out['status'] = 'outside_tolerance' if out['outside_count'] else 'within_tolerance'
            out['reason'] = 'All imported samples align exactly; differences use the declared absolute tolerance and unverified matching-conditions declaration.'
        outputs.append(out)
    return outputs


class WorkspaceSeries:
    def __init__(self, store):
        self.store, self._lock = store, threading.Lock()
        with store._connect(write=True) as connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS simulation_imports (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, import_id TEXT NOT NULL UNIQUE,
                project_id TEXT NOT NULL, revision INTEGER NOT NULL, created_at TEXT NOT NULL,
                receipt TEXT NOT NULL, digest TEXT NOT NULL,
                FOREIGN KEY(project_id,revision) REFERENCES revisions(project_id,revision))''')
            connection.execute('CREATE INDEX IF NOT EXISTS series_project_revision ON simulation_imports(project_id,revision,sequence)')

    preview = staticmethod(preview)

    def _baseline(self, connection, run_id):
        row = connection.execute('SELECT * FROM runs WHERE run_id=?', (run_id,)).fetchone()
        if row is None:
            raise WorkspaceError('The frozen simulation baseline run is missing.')
        run = self.store._receipt(row)
        revision = connection.execute('SELECT * FROM revisions WHERE project_id=? AND revision=?', (run['project_id'],run['revision'])).fetchone()
        if revision is None or self.store._project(revision) != run['review']['project']:
            raise WorkspaceError('The canonical run does not match its saved revision.')
        return dict(run_id=run_id, run_digest=_digest(run), run=run)

    def save(self, project_id, revision, baseline_run_id, spec):
        _revision(revision)
        if baseline_run_id is not None and (not isinstance(baseline_run_id,str) or not _ID.fullmatch(baseline_run_id)):
            raise WorkspaceError('Choose a saved baseline run or null for replay only.')
        normalized, parsed = validate_spec(spec)
        if bool(baseline_run_id) != bool(normalized['model_id']):
            raise WorkspaceError('Bind both a baseline run and model ID, or leave both unbound for replay.')
        if not self._lock.acquire(blocking=False):
            raise ConflictError('A time-history import is already being saved.')
        try:
            workspace._require_current_runtime()
            if _sources() != _LOADED_SOURCES:
                raise ConflictError('Import code changed; restart 6D before saving.')
            with self.store._connect(write=True) as connection:
                view = self.store._view(connection, project_id, revision)
                if revision != view['latest_revision']:
                    raise ConflictError('Historical project revisions are read-only; choose the latest saved revision.')
                if baseline_run_id and (not view['run'] or view['run']['run_id'] != baseline_run_id):
                    raise ConflictError('Select the exact current canonical run for this saved revision.')
                baseline = self._baseline(connection, baseline_run_id) if baseline_run_id else None
                if baseline and normalized['model_id'] not in baseline['run']['model_results']:
                    raise WorkspaceError('The selected model is absent from the canonical run.')
                receipt = dict(schema=SCHEMA, import_id=uuid4().hex, project_id=project_id, revision=revision, created_at=_now(),
                               spec=normalized, parsed=parsed, baseline=baseline, comparisons=_comparisons(normalized,parsed,baseline),
                               sources=deepcopy(_LOADED_SOURCES), limitations=deepcopy(LIMITATIONS), live_model_calls=0)
                encoded = _encode(receipt)
                if len(encoded.encode('utf-8')) > MAX_RECEIPT_BYTES:
                    raise WorkspaceError('The frozen import exceeds its 96 MiB receipt limit; use a smaller history.')
                if _sources() != _LOADED_SOURCES:
                    raise ConflictError('Import sources changed; no history was saved.')
                row = {key:receipt[key] for key in ('import_id','project_id','revision','created_at')} | dict(receipt=encoded,digest=_digest(receipt))
                self._read(connection,row)
                connection.execute('INSERT INTO simulation_imports(import_id,project_id,revision,created_at,receipt,digest) VALUES (?,?,?,?,?,?)',
                                   tuple(row[k] for k in ('import_id','project_id','revision','created_at','receipt','digest')))
            return self.get(receipt['import_id'],revision)
        finally:
            self._lock.release()

    def _read(self, connection, row):
        try:
            receipt = json.loads(row['receipt'], object_pairs_hook=_unique_object, parse_constant=_reject_constant)
            fields = {'schema','import_id','project_id','revision','created_at','spec','parsed','baseline','comparisons','sources','limitations','live_model_calls'}
            if (not isinstance(receipt,dict) or set(receipt) != fields or receipt['schema'] != SCHEMA or _digest(receipt) != row['digest']
                    or any(receipt[k] != row[k] for k in ('import_id','project_id','revision','created_at'))
                    or type(receipt['revision']) is not int or receipt['revision'] < 1
                    or type(receipt['live_model_calls']) is not int or receipt['live_model_calls'] != 0 or receipt['limitations'] != LIMITATIONS):
                raise ValueError('Identity, digest or scope disclosure mismatch.')
            normalized, parsed = validate_spec(receipt['spec'])
            baseline = receipt['baseline']
            if bool(baseline) != bool(normalized['model_id']):
                raise ValueError('Baseline binding is inconsistent.')
            if baseline:
                actual = self._baseline(connection, baseline['run_id'])
                if (_encode(baseline) != _encode(actual) or actual['run']['project_id'] != receipt['project_id']
                        or actual['run']['revision'] != receipt['revision'] or normalized['model_id'] not in actual['run']['model_results']):
                    raise ValueError('Frozen run differs from the canonical saved baseline.')
            sources = receipt['sources']
            if (not isinstance(sources,dict) or 'workspace_series.py' not in sources
                    or any(not isinstance(v,str) or not re.fullmatch('[a-f0-9]{64}',v) for v in sources.values())
                    or (baseline and {k:v for k,v in sources.items() if k != 'workspace_series.py'} != baseline['run']['review']['verification_sources'])):
                raise ValueError('Source binding is inconsistent.')
            if (_encode(normalized) != _encode(receipt['spec']) or _encode(parsed) != _encode(receipt['parsed'])
                    or _encode(_comparisons(normalized,parsed,baseline)) != _encode(receipt['comparisons'])):
                raise ValueError('CSV, mapping or comparison findings disagree.')
            return receipt
        except (KeyError,TypeError,ValueError,IndexError,OverflowError) as exc:
            raise WorkspaceError('Stored simulation import is inconsistent: ' + str(exc)) from exc

    @staticmethod
    def _freshness(receipt,view):
        source_current = receipt['sources'] == _sources()
        selected = receipt['revision'] == view['revision']
        baseline = receipt['baseline']
        matches = baseline is None or bool(view['run'] and view['run']['run_id'] == baseline['run_id'])
        return dict(source_current=source_current,selected_revision_matches=selected,baseline_run_matches=matches,
                    historical=not(source_current and selected and matches),context_revision=view['revision'],
                    note='Recorded imports retain their original baseline and never replace canonical findings.')

    def _detail(self,connection,row,view):
        receipt = self._read(connection,row)
        return dict(receipt=receipt,receipt_digest=row['digest'],freshness=self._freshness(receipt,view),
                    integrity=dict(digest_valid=True,baseline_binding_valid=True,unsigned=True))

    def get(self,identity,revision=None):
        if not isinstance(identity,str) or not _ID.fullmatch(identity):
            raise WorkspaceError('Invalid simulation import ID.')
        with self.store._connect() as connection:
            connection.execute('BEGIN')
            row = connection.execute('SELECT * FROM simulation_imports WHERE import_id=?',(identity,)).fetchone()
            if row is None:
                raise WorkspaceError('Simulation import not found.')
            view = self.store._view(connection,row['project_id'],revision)
            if row['revision'] > view['revision']:
                raise WorkspaceError('This import belongs to a later revision than the selected context.')
            return self._detail(connection,row,view)

    def snapshot(self,connection,view):
        rows = connection.execute('SELECT * FROM simulation_imports WHERE project_id=? AND revision<=? ORDER BY sequence DESC LIMIT 20',
                                  (view['project_id'],view['revision'])).fetchall()
        total = connection.execute('SELECT COUNT(*) FROM simulation_imports WHERE project_id=? AND revision<=?',
                                   (view['project_id'],view['revision'])).fetchone()[0]
        details, size = [], 0
        for row in rows:
            # Preserve whole records; never silently shorten CSV or a frozen run.
            if size + len(row['receipt'].encode('utf-8')) > 64 * 1024 * 1024:
                break
            details.append(self._detail(connection,row,view))
            size += len(row['receipt'].encode('utf-8'))
        result = dict(imports=details,history_limit=20,history_truncated=total > len(details),
                      omitted_count=total-len(details),limitations=deepcopy(LIMITATIONS))
        return result | dict(digest=_digest(result))

    def summary(self,project_id,revision):
        with self.store._connect() as connection:
            connection.execute('BEGIN')
            view = self.store._view(connection,project_id,_revision(revision))
            return self.snapshot(connection,view)

    def list(self,project_id,revision):
        with self.store._connect() as connection:
            connection.execute('BEGIN')
            view = self.store._view(connection,project_id,_revision(revision))
            rows = connection.execute('SELECT * FROM simulation_imports WHERE project_id=? AND revision<=? ORDER BY sequence DESC LIMIT 20', (project_id,revision)).fetchall()
            imports = []
            for row in rows:
                receipt = self._read(connection,row)
                imports.append({k:receipt[k] for k in ('import_id','project_id','revision','created_at')} |
                               dict(name=receipt['spec']['name'],data_kind=receipt['spec']['data_kind'],row_count=receipt['parsed']['row_count'],
                                    model_id=receipt['spec']['model_id'],baseline_run_id=receipt['baseline']['run_id'] if receipt['baseline'] else None,
                                    comparisons=receipt['comparisons'],freshness=self._freshness(receipt,view)))
            return dict(project_id=project_id,revision=revision,imports=imports,baseline_run_id=view['run']['run_id'] if view['run'] else None,
                        limits=deepcopy(LIMITS),limitations=deepcopy(LIMITATIONS))
