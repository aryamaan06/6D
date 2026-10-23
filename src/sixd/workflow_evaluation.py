"""Current engineering-workflow case pack, separate from historical selection proof."""
from copy import deepcopy
from pathlib import Path
import tempfile

from . import model_evaluation as baseline
from .project_examples import example_projects
from .project_investigation import validate_investigation_view
from .workspace import WorkspaceStore

PLAN_SCHEMA = 'sixd.workflow-evaluation-plan.v1'
REPORT_SCHEMA = 'sixd.workflow-evaluation-report.v1'
BATCH_CAP_USD = 3.00
BATCH_REQUESTS = 180
CASE_IDS = ('orbit-met', 'orbit-no-accuracy', 'orbit-tight-accuracy', 'orbit-near-limit',
            'limit-only-change', 'linked-source-change', 'blocked-upstream',
            'power-shortfall', 'control-met', 'unsupported-control')


def build_plan(*, temporary_root=None):
    """Calculate disposable examples; never call a provider or alter user projects."""
    examples = example_projects()
    scratch = Path(temporary_root) if temporary_root else Path(__file__).resolve().parents[2] / 'work'
    scratch.mkdir(parents=True, exist_ok=True)
    cases = []
    with tempfile.TemporaryDirectory(prefix='workflow-evaluation-', dir=scratch) as directory:
        store = WorkspaceStore(Path(directory) / 'cases.sqlite3')

        def add(identity, description, project, requirement, status, model_status='completed', *,
                assessment=None, revise=None, changed_inputs=(), limit_only=False):
            project = deepcopy(project)
            project['project_id'] = 'workflow-evaluation-' + identity
            project['name'] = 'Constructed evaluation: ' + description
            store.create_project(project)
            view = store.run(project['project_id'], 1)
            if revise:
                changed = deepcopy(view['project'])
                for name, value in revise.items():
                    changed['inputs'][name]['value'] = value
                store.save_revision(project['project_id'], 1, changed)
                view = store.run(project['project_id'], 2)
            selected_model = next(m for m in view['project']['models'] if m['id'] == view['run']['review']['findings'][requirement]['model_id'])
            expected = {'status': status, 'model_status': model_status,
                        'requires_recheck': selected_model['type'] in view['run']['review']['adapter_versions'],
                        'requires_changes': revise is not None, 'changed_inputs': sorted(changed_inputs)}
            if limit_only:
                expected['limit_only_change'] = True
            if assessment:
                expected['assessment_status'] = assessment
            case = {'id': identity, 'description': description, 'constructed': True,
                    'held_out_variation': False, 'evaluation_policy': baseline.CASE_POLICY,
                    'case_origin': 'AI-authored development scenario based on maintained examples; not an independent held-out or customer test.',
                    'requirement_id': requirement, 'view': view, 'expected': expected,
                    'question': 'Explain the selected saved requirement, its actual status and evidence gaps. '
                        'Give concrete next engineering checks without inventing numbers, tests, coupling or launch permission. '
                        'Distinguish numerical grid agreement from physical applicability and a true-error guarantee. '
                        + ('Read and cite the recorded changes; distinguish changed limits from changed physical inputs. '
                           if revise else 'This is the first reviewed revision; do not invent earlier changes. ')}
            case['case_digest'] = baseline._digest(baseline._case_payload(case))
            cases.append(case)

        orbit = examples['orbital_review']
        add('orbit-met', 'Orbital criterion with declared grid agreement', orbit, 'orbit_max_radius', 'met')
        missing = deepcopy(orbit)
        missing['models'][0].pop('accuracy')
        add('orbit-no-accuracy', 'Completed trajectory without accuracy criteria', missing, 'orbit_max_radius',
            'not_assessed', assessment='accuracy_not_assessed')
        tight = deepcopy(orbit)
        # Freshly prepared cases use an intentionally unresolved numerical
        # criterion for the current RK4 adapter. Its retained fine/middle
        # difference is below the old one-metre criterion, which no longer
        # exercises a gap. Historical plans and receipts are never rewritten.
        tight['models'][0]['accuracy']['position_tolerance_m'] = 1e-6
        add('orbit-tight-accuracy', 'Position grid disagreement exceeds declared tolerance', tight, 'orbit_max_radius',
            'not_assessed', assessment='insufficient_accuracy')
        near = deepcopy(orbit)
        # Circular radius remains near 7,000,000m, with a declared 500m allowance.
        # The threshold's 100m gap is deliberately insufficient, not an exact prediction oracle.
        near['inputs']['maximum_sampled_radius']['value'] = 7_000_100
        add('orbit-near-limit', 'Criterion overlaps the declared numerical allowance', near, 'orbit_max_radius',
            'not_assessed', assessment='insufficient_accuracy')
        add('limit-only-change', 'Thermal criterion changes with unchanged heat input', examples['baseline'],
            'thermal_limit', 'not_met', revise={'maximum_temperature': 250},
            changed_inputs=['maximum_temperature'], limit_only=True)
        add('linked-source-change', 'Density change propagates through a declared drag-to-beam link', examples['chain_review'],
            'mount_stress', 'met', revise={'density': .8}, changed_inputs=['density'])
        blocked = deepcopy(missing)
        for name, value, unit in [('rho', .01, 'kg/m^3'), ('cd', 1, '1'), ('area', 1, 'm^2'), ('drag_cap', 100, 'N')]:
            blocked['inputs'][name] = {'value': value, 'unit': unit, 'source': 'Constructed workflow guard test only.'}
        blocked['models'].append({'id': 'drag', 'type': 'drag_load',
            'inputs': {'density': 'rho', 'drag_coefficient': 'cd', 'reference_area': 'area'},
            'links': {'relative_speed': {'model_id': 'orbit', 'metric': 'final_speed_m_s', 'unit': 'm/s',
                'rationale': 'Constructed scalar link to exercise evidence blocking; no atmospheric flight validity asserted.'}}})
        blocked['requirements'].append({'id': 'linked_drag', 'title': 'Declared linked drag threshold', 'model_id': 'drag',
            'metric': 'drag_force', 'operator': '<=', 'limit_input': 'drag_cap', 'critical': True})
        add('blocked-upstream', 'Missing orbital accuracy blocks a downstream calculation', blocked,
            'linked_drag', 'not_assessed', model_status='not_assessed')
        power = deepcopy(examples['power_budget'])
        power['inputs']['battery_power_limit']['value'] = 1
        add('power-shortfall', 'Battery output power inadequate despite a separate energy budget', power,
            'power_capacity', 'not_met')
        add('control-met', 'Bounded single-axis pointing criterion', examples['attitude_review'], 'pointing_window', 'met')
        add('unsupported-control', 'Unimplemented control requirement is not a design failure', examples['missing_evidence'],
            'control_tracking', 'not_assessed', model_status='not_assessed')
    plan = {'schema': PLAN_SCHEMA, 'state': 'prepared_offline', 'live_calls': 0,
            'cases': cases, 'candidates': deepcopy(list(baseline.CANDIDATES)), 'settings': deepcopy(baseline.SETTINGS),
            'manual_review_criteria': deepcopy(baseline.MANUAL_CRITERIA),
            'coverage_limit': 'Ten constructed workflow scenarios, not independent aerospace/customer validation.',
            'budget_policy': {'batch_cap_usd': BATCH_CAP_USD, 'max_request_reservations': BATCH_REQUESTS,
                              'cumulative_allowance_unchanged': True, 'automatic_retries': 0},
            'active_model_changed': False}
    plan['plan_digest'] = baseline._digest(plan)
    validate_plan(plan)
    return plan


def validate_plan(plan, *, require_current_sources=True):
    if (not isinstance(plan, dict) or plan.get('schema') != PLAN_SCHEMA
            or plan.get('plan_digest') != baseline._digest({k:v for k,v in plan.items() if k != 'plan_digest'})
            or plan.get('settings') != baseline.SETTINGS or plan.get('candidates') != list(baseline.CANDIDATES)
            or tuple(c['id'] for c in plan.get('cases', [])) != CASE_IDS):
        raise ValueError('Use the intact engineering-workflow evaluation plan.')
    for case in plan['cases']:
        if (case.get('case_digest') != baseline._digest(baseline._case_payload(case))
                or case.get('evaluation_policy') != baseline.CASE_POLICY
                or case['expected']['requires_changes'] is not (case['view'].get('prior_run') is not None)):
            raise ValueError('The engineering-workflow case changed.')
        validate_investigation_view(case['view'], case['requirement_id'], require_current_sources=require_current_sources)
        baseline._assert_expected(case['view'], case['requirement_id'], case['expected'])
        if case['view']['run']['review']['findings'][case['requirement_id']].get('assessment_status') != case['expected'].get('assessment_status'):
            raise ValueError('The constructed numerical assessment disagrees with the declared expected state.')
    return True


def run_comparison(plan, factory, *, mode='offline', on_case=None):
    validate_plan(plan)
    from .explanation_quality import evaluate_explanation
    return baseline._run_checked_comparison(plan, factory, quality_evaluator=evaluate_explanation,
        mode=mode, on_case=on_case, report_schema=REPORT_SCHEMA)


def scorecard(report):
    """Small read-only projection; complete responses remain in the original report."""
    if report.get('schema') != REPORT_SCHEMA or report.get('report_digest') != baseline._digest({k:v for k,v in report.items() if k != 'report_digest'}):
        raise ValueError('The workflow report digest is inconsistent.')
    candidates = []
    for candidate in report['candidates']:
        rows = [r for r in report['rows'] if r['candidate_id'] == candidate['id']]
        candidates.append({'candidate_id': candidate['id'], 'model': candidate['model'], 'label': candidate['label'],
            'planned': len(rows), 'attempted': sum(r['state'] != 'not_run' for r in rows),
            'completed': sum(r['state'] == 'completed' for r in rows),
            'untested': sum(r['state'] == 'not_run' for r in rows),
            'stopped_cases': [{'case_id': r['case_id'],
                               'error_code': (r.get('receipt') or {}).get('error_code'),
                               'reason': (r.get('receipt') or {}).get('error')}
                              for r in rows if r['state'] not in {'completed', 'not_run'}],
            'workflow_passes': sum(bool((r.get('score') or {}).get('workflow_gate_pass')) for r in rows),
            'reserved_usd': sum(r.get('reserved_usd') or 0 for r in rows),
            'elapsed_seconds': sum(r.get('elapsed_seconds') or 0 for r in rows),
            'semantic_review': 'pending_independent_human_review'})
    return {'schema': 'sixd.workflow-scorecard.v1', 'mode': report['mode'], 'report_digest': report['report_digest'],
            'candidates': candidates, 'active_model_changed': False, 'billed_cost_usd': None,
            'note': 'Workflow passes and limited wording checks do not establish semantic correctness. Skipped cases are untested; reservations are not billed cost.'}
