"""Explicit engineering scope declarations alongside unchanged numerical evidence.

Coverage records are supplemental, versioned user declarations. A supplied
phase or fit declaration never expands the capabilities of a calculator.
"""
from copy import deepcopy
import json
import re
from uuid import uuid4

from . import engineering, workspace_sources
from .workspace import ConflictError, WorkspaceError, _digest, _encode, _now, _revision

SCHEMA = 'sixd.engineering-coverage.v1'
MAX_CHECKS = 100
MAX_VERSIONS = 30
MAX_CONTEXT_BYTES = 128 * 1024
PHASES = ['Design', 'Ground test', 'Launch and ascent', 'Orbit operations',
          'Transfer and rendezvous', 'Entry, descent and landing', 'Disposal', 'Unassigned']
STATUSES = ('excluded', 'undecided', 'needs_review', 'missing_analysis',
            'outside_assumptions', 'applicability_unknown', 'unassessed',
            'criterion_unmet', 'criterion_met')
DISCIPLINES = {'ideal_propulsion': 'Propulsion', 'static_cantilever': 'Structures',
              'powered_flight': 'Flight dynamics', 'guided_ascent': 'Flight dynamics', 'staged_ascent': 'Flight dynamics',
              'radiative_equilibrium': 'Thermal', 'drag_load': 'Atmospheric loads',
              'orbital_trajectory': 'Flight dynamics', 'power_energy_budget': 'Power and energy',
              'attitude_control': 'Guidance and control'}
SPEC_FIELDS = {'check_id', 'base_version', 'title', 'phase', 'discipline', 'requirement_id',
               'applicability', 'applicability_note', 'model_fit', 'fit_note', 'next_step'}
LIMITATIONS = [
    'This map covers declared checks and existing requirements, not an exhaustive mission or rocket checklist.',
    'Phase, discipline, inclusion and model-fit entries are user declarations. A declaration does not establish physical applicability or extend a calculator to that mission phase.',
    'A met criterion concerns its stated model, inputs and limit only. Missing analysis, unknown applicability and unmet criteria remain separate.',
    'Excluding a check records a supplied rationale and never removes, changes or resolves a canonical requirement finding.',
    'Coverage annotations supplement saved revisions. Later annotations on the same revision are not part of its original numerical receipt.',
    'Dependency changes require review of prior declarations. Review flags cannot detect unrecorded real-world or external-source changes.',
    'Local histories and unsigned digests provide consistency checks, not authenticated engineering approval or launch authorization.',
]


def _text(value, label, maximum, *, empty=False):
    if (not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip())
            or any(ord(char) < 32 and char not in '\r\n\t' for char in value)):
        raise WorkspaceError(f'{label} must be {"" if empty else "nonempty "}text of at most {maximum} characters.')
    return value


def _validate_spec(spec):
    if not isinstance(spec, dict) or set(spec) != SPEC_FIELDS:
        raise WorkspaceError('A coverage check has missing or unsupported fields.')
    for key, maximum in [('title', 240), ('phase', 80), ('discipline', 80),
                         ('applicability_note', 2000), ('fit_note', 2000), ('next_step', 2000)]:
        _text(spec[key], 'Coverage ' + key, maximum, empty=key.endswith('_note') or key == 'next_step')
    if spec['check_id'] is None:
        if spec['base_version'] is not None:
            raise WorkspaceError('A new coverage check cannot declare a base version.')
    else:
        if not isinstance(spec['check_id'], str) or re.fullmatch(r'[a-f0-9]{32}', spec['check_id']) is None:
            raise WorkspaceError('Select an existing coverage check ID.')
        if type(spec['base_version']) is not int or spec['base_version'] < 1:
            raise WorkspaceError('The coverage base version must be a positive integer.')
    if spec['requirement_id'] is not None:
        _text(spec['requirement_id'], 'Requirement ID', 4096)
    if spec['applicability'] not in ('required', 'excluded', 'undecided'):
        raise WorkspaceError('Choose required, excluded or undecided applicability.')
    if spec['model_fit'] not in ('declared_fit', 'outside_assumptions', 'unknown'):
        raise WorkspaceError('Choose a supplied model-fit declaration or unknown.')
    if spec['applicability'] == 'excluded' and not spec['applicability_note'].strip():
        raise WorkspaceError('Excluding a check requires a written rationale.')
    if spec['model_fit'] != 'unknown':
        if spec['requirement_id'] is None:
            raise WorkspaceError('Link a requirement before declaring its model fit.')
        if not spec['fit_note'].strip():
            raise WorkspaceError('A model-fit declaration requires a written rationale.')


def _context(view, requirement_id):
    if requirement_id is None:
        return {'unmapped_project_configuration': deepcopy(view['project'])}
    target = workspace_sources._targets(view).get('requirement:' + requirement_id)
    return deepcopy(target[1]) if target else None


def _model_summary(view, requirement):
    if requirement is None:
        return None
    definition = next(item for item in view['project']['models'] if item['id'] == requirement['model_id'])
    kind = definition['type']
    current = view['run']
    evidence = current['review']['evidence'].get(definition['id']) if current else None
    applicability = (evidence or {}).get('applicability') or engineering.model_applicability(kind)
    return {'id': definition['id'], 'type': kind, 'supported': kind in engineering.MODEL_VERSIONS,
            'scope': applicability['scope'] if applicability else 'No maintained calculator supports this model type.',
            'assumptions': deepcopy(evidence['assumptions'] if evidence else engineering._ASSUMPTIONS.get(kind, [])),
            'not_assessed': deepcopy(evidence['not_assessed'] if evidence else engineering._NOT_ASSESSED.get(kind, [
                'No maintained deterministic adapter supports this model type.'])),
            'physical_applicability': 'not_assessed',
            'context_source': 'current_saved_review' if evidence else 'current_model_catalog'}


def _calculation(view, requirement, model):
    if requirement is None:
        return 'not_run', None, 'No current requirement is linked to this check.'
    if not model['supported']:
        finding = (view['run'] or {}).get('review', {}).get('findings', {}).get(requirement['id'])
        return 'unsupported', finding['status'] if finding else None, 'No maintained calculator supports the linked model type.'
    if view['run'] is None:
        if view['prior_run'] is not None:
            return 'stale', None, 'Available numerical evidence belongs to another revision or implementation. Run current checks.'
        return 'not_run', None, 'Run checks for this saved revision to obtain numerical evidence.'
    finding = view['run']['review']['findings'].get(requirement['id'])
    if finding is None:
        return 'not_assessed', None, 'The current review does not contain a finding for this requirement.'
    return ('not_assessed' if finding['status'] == 'not_assessed' else 'assessed',
            finding['status'], finding['reason'])


def _coverage_status(row):
    if row['needs_review']:
        return 'needs_review', 'Recorded dependencies changed. Review this declaration against the current configuration.'
    if row['applicability'] == 'excluded':
        return 'excluded', 'Excluded by the supplied rationale; any linked numerical finding remains unchanged.'
    if row['applicability'] == 'undecided':
        return 'undecided', 'Decide whether this check is required for the declared mission and phase.'
    if row['requirement_id'] is None or row['model'] is None or row['calculation_status'] == 'unsupported':
        return 'missing_analysis', 'Define an applicable analysis and criterion for this check; the current mapping supplies no supported calculation.'
    if row['model_fit'] == 'outside_assumptions':
        return 'outside_assumptions', 'The supplied model-fit review identifies conditions outside the model assumptions.'
    if row['model_fit'] == 'unknown':
        return 'applicability_unknown', 'Model applicability has not been declared. A numerical result cannot resolve this gap.'
    if row['calculation_status'] != 'assessed':
        return 'unassessed', row['calculation_reason']
    if row['criterion_status'] == 'not_met':
        return 'criterion_unmet', 'The linked calculation violates its declared criterion; the supplied model-fit declaration is not independently verified.'
    return 'criterion_met', 'The linked criterion is met within the calculated scope; physical applicability remains a supplied, unverified declaration.'


class WorkspaceCoverage:
    def __init__(self, store):
        self.store = store
        with self.store._connect(write=True) as connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS project_coverage_versions (
                project_id TEXT NOT NULL REFERENCES projects(project_id),
                check_id TEXT NOT NULL, version INTEGER NOT NULL,
                basis_revision INTEGER NOT NULL, created_at TEXT NOT NULL,
                snapshot TEXT NOT NULL, digest TEXT NOT NULL,
                PRIMARY KEY(project_id,check_id,version),
                FOREIGN KEY(project_id,basis_revision) REFERENCES revisions(project_id,revision)
            )''')

    def _view(self, connection, project_id, revision, *, write=False):
        _text(project_id, 'Project ID', 4096)
        view = self.store._view(connection, project_id, _revision(revision))
        if write and view['revision'] != view['latest_revision']:
            raise ConflictError('Coverage changes require the latest saved project revision.')
        return view

    @staticmethod
    def _load(row):
        try:
            value = json.loads(row['snapshot'])
            if (not isinstance(value, dict) or _digest(value) != row['digest']
                    or any(value[key] != row[key] for key in ('project_id', 'check_id', 'version', 'basis_revision', 'created_at'))
                    or _digest(value['context']) != value['context_digest']):
                raise ValueError
            _validate_spec({key: (value['version'] if key == 'base_version' else value[key]) for key in SPEC_FIELDS})
            return {**value, 'digest': row['digest']}
        except (KeyError, ValueError, TypeError) as exc:
            raise WorkspaceError('A saved coverage record is inconsistent. No record was replaced.') from exc

    def _records(self, connection, project_id, revision):
        grouped = {}
        for row in connection.execute('''SELECT * FROM project_coverage_versions
                WHERE project_id=? AND basis_revision<=? ORDER BY check_id,version''', (project_id, revision)):
            value = self._load(row)
            prior = grouped.setdefault(value['check_id'], [])
            if value['version'] != len(prior) + 1 or (prior and value['basis_revision'] < prior[-1]['basis_revision']):
                raise WorkspaceError('A saved coverage history is inconsistent. No record was replaced.')
            prior.append(value)
        return grouped

    def summary_in_snapshot(self, connection, view):
        grouped = self._records(connection, view['project_id'], view['revision'])
        requirements = {item['id']: item for item in view['project']['requirements']}
        models = {item['id']: item for item in view['project']['models']}
        checks, mapped = [], set()
        for identity, history in grouped.items():
            record = deepcopy(history[-1])
            requirement = requirements.get(record['requirement_id'])
            context = _context(view, record['requirement_id'])
            reasons = []
            if record['requirement_id'] is not None:
                mapped.add(record['requirement_id'])
                if requirement is None:
                    reasons.append('The linked requirement is no longer present in this revision.')
                elif _digest(context) != record['context_digest']:
                    reasons.append('The linked requirement, criterion, model, bound inputs or verification implementation changed.')
            elif _digest(context) != record['context_digest']:
                reasons.append('The declared project configuration changed. This unmapped check has no narrower dependency binding.')
            record.update(row_id='check:' + identity, base_version=record['version'], origin='declared',
                          history=[{key: deepcopy(item[key]) for key in (*sorted(SPEC_FIELDS - {'base_version'}),
                                   'version', 'basis_revision', 'created_at', 'digest')} for item in history],
                          needs_review=bool(reasons), review_reasons=reasons)
            record.pop('context')
            checks.append(record)
        for identity, requirement in requirements.items():
            if identity in mapped:
                continue
            kind = models[requirement['model_id']]['type']
            checks.append({'row_id': 'requirement:' + identity, 'check_id': None, 'base_version': None,
                           'version': None, 'basis_revision': view['revision'], 'title': requirement['title'],
                           'phase': 'Unassigned', 'discipline': DISCIPLINES.get(kind, 'Other engineering'),
                           'requirement_id': identity, 'applicability': 'required', 'applicability_note': '',
                           'model_fit': 'unknown', 'fit_note': '', 'next_step': '', 'origin': 'requirement',
                           'needs_review': False, 'review_reasons': [], 'history': [], 'digest': None})
        for row in checks:
            requirement = requirements.get(row['requirement_id'])
            row['model'] = _model_summary(view, requirement)
            row['calculation_status'], row['criterion_status'], row['calculation_reason'] = _calculation(view, requirement, row['model'])
            row['coverage_status'], row['reason'] = _coverage_status(row)
        counts = {status: sum(row['coverage_status'] == status for row in checks) for status in STATUSES}
        findings = view['run']['review']['findings'].values() if view['run'] else []
        criterion_counts = {status: sum(item['status'] == status for item in findings)
                            for status in ('met', 'not_met', 'not_assessed')}
        criterion_counts['not_run'] = len(requirements) if view['run'] is None else 0
        result = {'schema': SCHEMA, 'project_id': view['project_id'], 'revision': view['revision'],
                  'project_digest': _digest(view['project']), 'run_id': view['run']['run_id'] if view['run'] else None,
                  'can_edit': view['revision'] == view['latest_revision'], 'checks': checks,
                  'requirements': [{'id': item['id'], 'title': item['title'], 'model_id': item['model_id'],
                                    'model_type': models[item['model_id']]['type']} for item in requirements.values()],
                  'phases': list(PHASES), 'counts': counts, 'criterion_counts': criterion_counts,
                  'count_definitions': {'checks': 'Declared checks plus unmapped project requirements; not a completeness score.',
                                        'criteria': 'All current canonical requirement findings, including excluded check mappings.'},
                  'limits': {'max_checks': MAX_CHECKS, 'max_versions_per_check': MAX_VERSIONS},
                  'limitations': list(LIMITATIONS)}
        result['digest'] = _digest(result)
        return result

    def summary(self, project_id, revision):
        with self.store._connect() as connection:
            connection.execute('BEGIN')
            return self.summary_in_snapshot(connection, self._view(connection, project_id, revision))

    def save(self, project_id, revision, spec, expected_digest):
        _validate_spec(spec)
        if not isinstance(expected_digest, str) or re.fullmatch(r'[a-f0-9]{64}', expected_digest) is None:
            raise WorkspaceError('Supply the exact displayed coverage context digest before saving.')
        with self.store._connect(write=True) as connection:
            view = self._view(connection, project_id, revision, write=True)
            current = self.summary_in_snapshot(connection, view)
            if current['digest'] != expected_digest:
                raise ConflictError('Coverage or saved engineering evidence changed. Refresh and review the current context before saving.')
            if spec['requirement_id'] is not None and spec['requirement_id'] not in {item['id'] for item in view['project']['requirements']}:
                raise WorkspaceError('Select a requirement from this saved project revision, or leave the check unmapped.')
            grouped = self._records(connection, project_id, revision)
            identity = spec['check_id']
            if identity is None:
                if len(grouped) >= MAX_CHECKS:
                    raise WorkspaceError('The project coverage check limit has been reached.')
                identity, version = uuid4().hex, 1
            else:
                history = grouped.get(identity)
                if not history or history[-1]['version'] != spec['base_version']:
                    raise ConflictError('This coverage check changed or is unavailable. Refresh before editing.')
                if len(history) >= MAX_VERSIONS:
                    raise WorkspaceError('This coverage check reached its saved-version limit.')
                version = spec['base_version'] + 1
            context = _context(view, spec['requirement_id'])
            if len(_encode(context).encode('utf-8')) > MAX_CONTEXT_BYTES:
                raise WorkspaceError('This coverage check exceeds the supported dependency-context size.')
            record = {key: deepcopy(value) for key, value in spec.items() if key not in ('check_id', 'base_version')}
            record.update(project_id=project_id, check_id=identity, version=version, basis_revision=revision,
                          created_at=_now(), context=context, context_digest=_digest(context))
            connection.execute('''INSERT INTO project_coverage_versions
                (project_id,check_id,version,basis_revision,created_at,snapshot,digest) VALUES(?,?,?,?,?,?,?)''',
                (project_id, identity, version, revision, record['created_at'], _encode(record), _digest(record)))
            return self.summary_in_snapshot(connection, view)
