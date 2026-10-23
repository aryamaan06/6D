"""Read-only comparison of pinned engineering runs and hypothetical cases.

Values and verdicts remain those in the recorded receipts. Differences describe
declared quantities; no new physics, unit conversion or overall ranking occurs.
"""
from copy import deepcopy
import math

from . import workspace, workspace_scenarios, engineering
from .workspace import WorkspaceError, _digest, _encode, _revision

SCHEMA = 'sixd.design-comparison.v1'
CATALOG_SCHEMA = 'sixd.design-comparison-catalog.v1'
MAX_RUNS, MAX_STUDIES, MAX_BYTES = 100, 20, 64 * 1024 * 1024
LIMITATIONS = [
    'This read-only comparison uses pinned saved results and performs no calculation or paid model call.',
    'A hypothetical scenario is not a saved project revision, physical test or prediction of whole-vehicle behaviour.',
    'Improved or worsened means a criterion margin changed under matching declared criteria and tracked model context; it is not a causal design or mission-success judgement.',
    'Changed limits, operators, quantities, units, model definitions or verification implementations are shown explicitly rather than ranked as equivalent.',
    'Historical values and unassessed requirements remain visible. A displayed diagnostic output does not resolve an unassessed criterion.',
    'No unit conversion, interpolation, probability, independent physical validation or overall best-design ranking is provided.',
    'Record digests are unsigned consistency checks, not authentication, certification or launch authorization.',
]


def _quantity(record, **extra):
    if record is None:
        return None
    return {**deepcopy(record), 'display_value': str(record['value']), **extra}


def _difference(after, before, unit):
    try:
        value = after - before
        if not math.isfinite(value):
            return None
    except (OverflowError, ValueError, TypeError):
        return None
    return _quantity({'value': value, 'unit': unit})


def _side_requirement(side, requirement):
    review = side['review']
    finding = review['findings'][requirement['id']]
    evidence = review['evidence'][requirement['model_id']]
    assessed = finding['status'] in {'met', 'not_met'} and finding.get('evidence') is not None
    metric = finding['evidence']['metric'] if assessed else evidence['metrics'].get(requirement['metric'])
    limit = finding['evidence']['limit'] if assessed else side['project']['inputs'][requirement['limit_input']]
    margin = workspace_scenarios.margin(finding) if assessed else None
    model = next(m for m in side['project']['models'] if m['id'] == requirement['model_id'])
    ancestors = {}
    for identity, ancestor in evidence.get('calculation_inputs', {}).get('ancestors', {}).items():
        recorded = review['evidence'][identity]
        ancestors[identity] = {'definition': deepcopy(ancestor['model_definition']),
            **{key: deepcopy(recorded[key]) for key in ('model_type', 'model_version', 'assumptions', 'verification_sources')}}
    result = {'requirement': deepcopy(requirement), 'finding': deepcopy(finding),
            'metric': _quantity(metric, **({'note': 'Diagnostic model output; the requirement remains unassessed.'} if metric and not assessed else {})),
            'metric_assessed': assessed, 'limit': _quantity(limit),
            'margin': _quantity(margin) if margin and margin['value'] is not None else None,
            'model_context': {'definition': deepcopy(model), 'model_type': evidence['model_type'],
                'model_version': evidence['model_version'], 'assumptions': deepcopy(evidence['assumptions']),
                'not_assessed': deepcopy(evidence['not_assessed']),
                'input_records': deepcopy(evidence['input_records']),
                'verification_sources': deepcopy(evidence['verification_sources']),
                'ancestor_model_context': ancestors,
                **{key: deepcopy(evidence[key]) for key in ('calculation_inputs', 'applicability', 'numerical_accuracy', 'references') if key in evidence}},
            'source_identity': {'record_digest': side['record_digest'], 'review_digest': side['review_digest'],
                'run_id': side.get('run_id'), 'study_id': side.get('study_id'), 'case_index': side.get('case_index')}}
    result['context_display'] = _encode({key: result[key] for key in ('model_context', 'source_identity')})
    return result


class WorkspaceComparison:
    def __init__(self, store, scenarios):
        if scenarios.store is not store:
            raise WorkspaceError('Comparison and scenarios must use the same workspace.')
        self.store, self.scenarios = store, scenarios

    def _view(self, connection, project_id, revision):
        if not isinstance(project_id, str) or not project_id.strip() or len(project_id) > 4096:
            raise WorkspaceError('Select a saved project for comparison.')
        selected = _revision(revision)
        row = connection.execute('SELECT * FROM revisions WHERE project_id=? AND revision=?',
                                 (project_id, selected)).fetchone()
        if row is None:
            raise WorkspaceError('Project revision not found.')
        self.store._project(row)
        # The general workspace view traverses later revisions and their runs.
        # A historical comparison is bound solely to its explicitly selected revision.
        return {'project_id': project_id, 'revision': selected}

    def _run(self, connection, project_id, revision, run_id):
        if not isinstance(run_id, str) or not run_id or len(run_id) > 128:
            raise WorkspaceError('Select an exact recorded run ID.')
        row = connection.execute('SELECT * FROM runs WHERE project_id=? AND run_id=? AND revision<=?',
                                 (project_id, run_id, revision)).fetchone()
        if row is None:
            raise WorkspaceError('The selected run is unavailable in this project revision.')
        receipt = self.store._receipt(row)
        saved = connection.execute('SELECT * FROM revisions WHERE project_id=? AND revision=?',
                                   (project_id, receipt['revision'])).fetchone()
        if saved is None or self.store._project(saved) != receipt['review']['project']:
            raise WorkspaceError('The recorded run does not match its saved project revision.')
        return row, receipt

    @staticmethod
    def _freshness(review, *, scenario_sources=None):
        current = review['verification_sources'] == workspace._sources() and review['adapter_versions'] == engineering.MODEL_VERSIONS
        if scenario_sources is not None:
            current = current and scenario_sources == workspace_scenarios._sources()
        return {'current_implementation': current,
                'note': ('Recorded verification sources and adapter versions match the maintained implementation.' if current else
                         'Historical verification implementation differs; recorded values remain inspectable, with trends withheld.')}

    def _resolve(self, connection, view, selection):
        if not isinstance(selection, dict):
            raise WorkspaceError('Select a recorded run or a hypothetical scenario case.')
        kind = selection.get('kind')
        pid, revision = view['project_id'], view['revision']
        if kind == 'run' and set(selection) == {'kind', 'run_id'}:
            row, receipt = self._run(connection, pid, revision, selection['run_id'])
            review = receipt['review']
            return {'selection': deepcopy(selection), 'kind': 'run', 'hypothetical': False,
                    'label': f"Saved R{receipt['revision']} · run {receipt['run_id'][:12]}",
                    'project_revision': receipt['revision'], 'created_at': receipt['created_at'],
                    'run_id': receipt['run_id'], 'record_digest': row['digest'],
                    'review_digest': review['digest'], 'project': deepcopy(review['project']),
                    'review': deepcopy(review), 'freshness': self._freshness(review)}
        if kind == 'scenario' and set(selection) == {'kind', 'study_id', 'case_index'}:
            identity, index = selection['study_id'], selection['case_index']
            if not isinstance(identity, str) or not identity or len(identity) > 128 or type(index) is not int or not 0 <= index < 16:
                raise WorkspaceError('Select an exact scenario study and case index.')
            row = connection.execute('SELECT * FROM scenario_studies WHERE project_id=? AND study_id=? AND revision<=?',
                                     (pid, identity, revision)).fetchone()
            if row is None:
                raise WorkspaceError('The scenario case is unavailable in this project revision.')
            receipt = self.scenarios._read(connection, row)
            if index >= len(receipt['cases']) or receipt['cases'][index]['index'] != index:
                raise WorkspaceError('The selected scenario case does not exist.')
            case, review = receipt['cases'][index], receipt['cases'][index]['review']
            return {'selection': deepcopy(selection), 'kind': 'scenario', 'hypothetical': True,
                    'label': f"Hypothetical · {receipt['spec']['name']} · {case['name']}",
                    'project_revision': receipt['revision'], 'created_at': receipt['created_at'],
                    'study_id': identity, 'case_index': index, 'case_name': case['name'],
                    'baseline_run_id': receipt['baseline']['run_id'], 'record_digest': row['digest'],
                    'case_digest': _digest(case), 'review_digest': review['digest'],
                    'project': deepcopy(review['project']), 'review': deepcopy(review),
                    'freshness': self._freshness(review, scenario_sources=receipt['sources'])}
        raise WorkspaceError('The comparison selection has missing or unsupported fields.')

    def catalog(self, project_id, revision):
        with self.store._connect() as connection:
            connection.execute('BEGIN')
            view = self._view(connection, project_id, revision)
            options = []
            run_rows = connection.execute('SELECT * FROM runs WHERE project_id=? AND revision<=? ORDER BY revision DESC, sequence DESC LIMIT ?',
                                           (project_id, revision, MAX_RUNS + 1)).fetchall()
            for row in run_rows[:MAX_RUNS]:
                side = self._resolve(connection, view, {'kind': 'run', 'run_id': row['run_id']})
                options.append({key: deepcopy(side[key]) for key in ('selection', 'label', 'kind', 'hypothetical', 'project_revision', 'created_at', 'record_digest', 'review_digest', 'freshness')})
            study_rows = connection.execute('SELECT * FROM scenario_studies WHERE project_id=? AND revision<=? ORDER BY sequence DESC LIMIT ?',
                                             (project_id, revision, MAX_STUDIES + 1)).fetchall()
            for row in study_rows[:MAX_STUDIES]:
                receipt = self.scenarios._read(connection, row)
                for case in receipt['cases']:
                    review = case['review']
                    options.append({'selection': {'kind': 'scenario', 'study_id': row['study_id'], 'case_index': case['index']},
                        'label': f"Hypothetical · {receipt['spec']['name']} · {case['name']}", 'kind': 'scenario',
                        'hypothetical': True, 'project_revision': row['revision'], 'created_at': row['created_at'],
                        'record_digest': row['digest'], 'review_digest': review['digest'],
                        'baseline_run_id': receipt['baseline']['run_id'],
                        'freshness': self._freshness(review, scenario_sources=receipt['sources'])})
            unreviewed = [{'revision': row[0], 'reason': 'No recorded run for this saved revision. Run checks explicitly before comparing its results.'}
                for row in connection.execute('SELECT r.revision FROM revisions r WHERE r.project_id=? AND r.revision<=? AND NOT EXISTS (SELECT 1 FROM runs x WHERE x.project_id=r.project_id AND x.revision=r.revision) ORDER BY r.revision', (project_id, revision))]
            result = {'schema': CATALOG_SCHEMA, 'project_id': project_id, 'revision': view['revision'], 'options': options,
                      'unreviewed_revisions': unreviewed, 'limits': {'max_runs': MAX_RUNS, 'max_studies': MAX_STUDIES},
                      'history_truncated': len(run_rows) > MAX_RUNS or len(study_rows) > MAX_STUDIES,
                      'limitations': list(LIMITATIONS)}
            result['digest'] = _digest(result)
            return result

    @staticmethod
    def _compatibility(left, right):
        reasons, blocked = [], False
        if left['kind'] == right['kind'] == 'scenario':
            blocked = left['baseline_run_id'] != right['baseline_run_id']
        elif left['kind'] != right['kind']:
            scenario, run = (left, right) if left['kind'] == 'scenario' else (right, left)
            blocked = scenario['baseline_run_id'] != run['run_id']
        if blocked:
            reasons.append('The hypothetical selection does not share the exact selected baseline run. Raw records are shown; numerical trends are withheld.')
        old = not left['freshness']['current_implementation'] or not right['freshness']['current_implementation']
        if old:
            reasons.append('At least one recorded verification implementation is historical. Values are preserved, but no improvement trend is inferred.')
        return {'status': 'incompatible' if blocked else 'limited' if old else 'compatible', 'reasons': reasons}, blocked or old

    @staticmethod
    def _inputs(left, right):
        rows = []
        a, b = left['project']['inputs'], right['project']['inputs']
        for identity in dict.fromkeys([*a, *b]):
            before, after = a.get(identity), b.get(identity)
            change = ('added' if before is None else 'removed' if after is None else
                      'unit_changed' if before['unit'] != after['unit'] else 'unchanged' if before == after else 'changed')
            delta = _difference(after['value'], before['value'], before['unit']) if before and after and before['unit'] == after['unit'] else None
            reason = ('Units differ; no conversion or numeric delta is supplied.' if change == 'unit_changed' else
                      'Input record was added or removed.' if before is None or after is None else
                      'Difference is outside the finite numeric range.' if delta is None else '')
            rows.append({'id': identity, 'left': _quantity(before), 'right': _quantity(after), 'change': change,
                         'value_delta': delta, 'reason': reason})
        return rows

    @staticmethod
    def _requirements(left, right, blocked):
        a = {r['id']: r for r in left['project']['requirements']}
        b = {r['id']: r for r in right['project']['requirements']}
        rows = []
        for identity in dict.fromkeys([*a, *b]):
            before = _side_requirement(left, a[identity]) if identity in a else None
            after = _side_requirement(right, b[identity]) if identity in b else None
            row = {'requirement_id': identity, 'title': (b.get(identity) or a[identity])['title'],
                   'left': before, 'right': after, 'comparability': {'comparable': False, 'criterion_unchanged': False, 'reasons': []},
                   'metric_delta': None, 'margin_delta': None, 'trend': 'not_comparable', 'notes': []}
            reasons = row['comparability']['reasons']
            if before is None or after is None:
                row['trend'] = 'added' if before is None else 'removed'
                reasons.append('This requirement exists on only one selected side; it is not an improvement or regression.')
                rows.append(row)
                continue
            ra, rb, ma, mb = before['requirement'], after['requirement'], before['model_context'], after['model_context']
            if blocked:
                reasons.append('Selection baseline or implementation compatibility prevents a numerical trend.')
            if not before['metric_assessed'] or not after['metric_assessed']:
                reasons.append('At least one canonical finding is unassessed or has no assessed numeric evidence.')
            for label, first, second in [('model identity', ra['model_id'], rb['model_id']),
                ('metric identity', ra['metric'], rb['metric']), ('comparison operator', ra['operator'], rb['operator']),
                ('model definition', ma['definition'], mb['definition']), ('model type', ma['model_type'], mb['model_type']),
                ('adapter version', ma['model_version'], mb['model_version']),
                ('verification sources', ma['verification_sources'], mb['verification_sources']),
                ('model assumptions', ma['assumptions'], mb['assumptions']),
                ('upstream model context', ma['ancestor_model_context'], mb['ancestor_model_context'])]:
                if first != second:
                    reasons.append('The ' + label + ' changed; quantities are not treated as interchangeable.')
            if before['metric'] and after['metric'] and before['metric']['unit'] != after['metric']['unit']:
                reasons.append('Metric units differ; no conversion is performed.')
            if before['limit']['unit'] != after['limit']['unit']:
                reasons.append('Declared limit units differ; no conversion is performed.')
            unchanged_criterion = (ra['operator'] == rb['operator'] and before['limit']['value'] == after['limit']['value']
                                   and before['limit']['unit'] == after['limit']['unit'])
            row['comparability']['criterion_unchanged'] = unchanged_criterion
            if not reasons:
                row['comparability']['comparable'] = True
                row['metric_delta'] = _difference(after['metric']['value'], before['metric']['value'], after['metric']['unit'])
                if before['margin'] and after['margin']:
                    row['margin_delta'] = _difference(after['margin']['value'], before['margin']['value'], after['margin']['unit'])
                if not unchanged_criterion:
                    row['trend'] = 'criterion_changed'
                    row['notes'].append('These margins use different declared limits. Their difference is descriptive, not evidence of like-for-like design improvement.')
                elif before['margin'] is None or after['margin'] is None or row['margin_delta'] is None:
                    row['comparability']['comparable'] = False
                    reasons.append('The margin or its difference exceeds the finite numeric range; use the recorded findings.')
                else:
                    delta = row['margin_delta']['value']
                    better = delta < 0 if ra['operator'] == '==' else delta > 0
                    row['trend'] = 'unchanged' if delta == 0 else 'improved' if better else 'worsened'
                    row['notes'].append('Trend describes the declared criterion margin under the supplied inputs; it does not select a best design or establish causation.')
                if row['metric_delta'] is None:
                    row['notes'].append('Metric difference exceeds the finite numeric range; exact recorded values remain visible.')
            rows.append(row)
        return rows

    def compare(self, project_id, revision, left, right):
        if left == right:
            raise WorkspaceError('Choose two different recorded selections.')
        with self.store._connect() as connection:
            connection.execute('BEGIN')
            view = self._view(connection, project_id, revision)
            a, b = self._resolve(connection, view, left), self._resolve(connection, view, right)
            compatibility, blocked = self._compatibility(a, b)
            inputs = self._inputs(a, b)
            requirements = self._requirements(a, b, blocked)
            if compatibility['status'] == 'compatible' and any(r['trend'] in {'not_comparable', 'criterion_changed', 'added', 'removed'} for r in requirements):
                compatibility['status'] = 'limited'
                compatibility['reasons'].append('Some declared requirements, criteria or quantities differ or remain unassessed. Inspect individual row reasons.')
            if a['project'] == b['project']:
                compatibility['reasons'].append('The selections use the same recorded project configuration; their run/case identities remain distinct.')
            models = []
            ma, mb = ({m['id']: m for m in side['project']['models']} for side in (a, b))
            for identity in dict.fromkeys([*ma, *mb]):
                models.append({'model_id': identity, 'left': deepcopy(a['review']['evidence'].get(identity)),
                    'right': deepcopy(b['review']['evidence'].get(identity)),
                    'definition_changed': ma.get(identity) != mb.get(identity)})
            trends = ('improved', 'worsened', 'unchanged', 'criterion_changed', 'not_comparable', 'added', 'removed')
            result = {'schema': SCHEMA, 'project_id': project_id, 'revision': view['revision'], 'left': a, 'right': b,
                'compatibility': compatibility, 'inputs': inputs, 'requirements': requirements, 'models': models,
                'summary': {'counts': {trend: sum(row['trend'] == trend for row in requirements) for trend in trends},
                    'left_statuses': {status: sum(f['status'] == status for f in a['review']['findings'].values()) for status in ('met', 'not_met', 'not_assessed')},
                    'right_statuses': {status: sum(f['status'] == status for f in b['review']['findings'].values()) for status in ('met', 'not_met', 'not_assessed')},
                    'changed_inputs': sum(row['change'] != 'unchanged' for row in inputs),
                    'total_requirements': len(requirements), 'no_overall_ranking': True},
                'execution': 'read_only_recorded_engineering_evidence', 'live_model_calls': 0,
                'limitations': list(LIMITATIONS)}
            result['models_display'] = _encode(models)
            result['digest'] = _digest(result)
            if len(_encode(result).encode('utf-8')) > MAX_BYTES:
                raise WorkspaceError('This comparison exceeds the 64 MiB export bound. Compare smaller recorded cases.')
            return result
