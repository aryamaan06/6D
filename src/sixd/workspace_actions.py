"""Versioned engineering work records, separate from numerical findings.

An action's workflow state records user-declared progress. It never changes a
requirement verdict, authenticates evidence or verifies completion criteria.
"""
from copy import deepcopy
import json
import re
from uuid import uuid4

from . import workspace_sources
from .explanation_quality import build_guidance
from .workspace import ConflictError, WorkspaceError, _digest, _encode, _now, _revision

SCHEMA = 'sixd.engineering-actions.v1'
STATES = ('todo', 'in_progress', 'ready_for_review', 'closed')
MAX_ACTIONS = 100
MAX_VERSIONS = 30
MAX_SUPPORTS = 20
MAX_CONTEXT_BYTES = 128 * 1024
LIMITATIONS = [
    'Action states, notes and completion criteria are user-declared workflow records, not calculated engineering findings.',
    'Closing an action never changes a requirement verdict, resolves unsupported coverage or establishes physical validity.',
    'Supporting results and manual references are pinned records. Their relevance and sufficiency for completion criteria are not automatically verified.',
    'Review flags compare declared project dependencies and recorded evidence only; external changes and actual work execution are not detected.',
    'An explicit context review preserves history and clears prior closure/support selections; it is not engineering approval.',
    'History and digests are unsigned local consistency records, not authenticated review, certification or launch authorization.',
]
TEXT_FIELDS = {'title': (240, False), 'next_check': (8000, False),
               'missing_evidence': (8000, True), 'completion_criteria': (4000, False),
               'note': (4000, True)}


def _fields(value, names, label):
    if not isinstance(value, dict) or set(value) != set(names):
        raise WorkspaceError(label + ' has missing or unsupported fields.')


def _text(value, label, maximum=4096, *, empty=False):
    if (not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip())
            or any(ord(char) < 32 and char not in '\r\n\t' for char in value)):
        raise WorkspaceError(f'{label} must be {"" if empty else "nonempty "}text of at most {maximum} characters.')
    return value


def _version(value):
    if type(value) is not int or value < 1:
        raise WorkspaceError('The action base version must be a positive integer.')
    return value


def _bounded_context(value):
    if len(_encode(value).encode('utf-8')) > MAX_CONTEXT_BYTES:
        raise WorkspaceError('The selected action/evidence context exceeds its supported size bound.')
    return value


def _finding_suggestion(view, requirement_id):
    requirement = next(item for item in view['project']['requirements'] if item['id'] == requirement_id)
    guidance = build_guidance(view['project'], view['run']['review'], requirement_id)
    actions = guidance['review_actions']
    missing = guidance['missing_information']
    return {'title': ('Review ' + requirement['title'])[:240],
            'next_check': '\n\n'.join(item['action'] for item in actions[:3])[:8000] or 'Inspect the saved finding, its declared inputs and its model applicability before choosing a supported next check.',
            'missing_evidence': '\n'.join(item['item'] + ' ' + item['why'] for item in missing[:4])[:8000],
            'completion_criteria': 'Record the work performed and the evidence checked against this requirement. Explain remaining limitations and unresolved findings; closing this action does not make the requirement pass.'}


class WorkspaceActions:
    def __init__(self, store, source_library):
        if source_library.store is not store:
            raise WorkspaceError('Actions and source references must use the same workspace store.')
        self.store, self.source_library = store, source_library
        with self.store._connect(write=True) as connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS project_action_versions (
                project_id TEXT NOT NULL REFERENCES projects(project_id),
                action_id TEXT NOT NULL, version INTEGER NOT NULL,
                basis_revision INTEGER NOT NULL, created_at TEXT NOT NULL,
                snapshot TEXT NOT NULL, digest TEXT NOT NULL,
                PRIMARY KEY(project_id,action_id,version),
                FOREIGN KEY(project_id,basis_revision) REFERENCES revisions(project_id,revision)
            )''')

    def _view(self, connection, project_id, revision, *, write=False):
        _text(project_id, 'Project ID')
        view = self.store._view(connection, project_id, _revision(revision))
        if write and view['revision'] != view['latest_revision']:
            raise ConflictError('Actions can be changed only on the latest saved project revision.')
        return view

    @staticmethod
    def _load(row):
        try:
            value = json.loads(row['snapshot'])
            if (not isinstance(value, dict) or _digest(value) != row['digest']
                    or any(value[key] != row[key] for key in ('project_id', 'action_id', 'version', 'basis_revision', 'created_at'))
                    or _digest(value['origin_context']) != value['origin_context_digest']
                    or _revision(value['origin_basis_revision']) > value['basis_revision']
                    or any(_digest(item['snapshot']) != item['context_digest'] for item in value['supports'])):
                raise ValueError
            return {**value, 'digest': row['digest']}
        except (KeyError, ValueError, TypeError) as exc:
            raise WorkspaceError('A stored engineering action is inconsistent. No record was replaced.') from exc

    def _records(self, connection, project_id, revision):
        grouped = {}
        for row in connection.execute('''SELECT * FROM project_action_versions
                WHERE project_id=? AND basis_revision<=? ORDER BY action_id,version''', (project_id, revision)):
            record = self._load(row)
            grouped.setdefault(record['action_id'], []).append(record)
        return grouped

    @staticmethod
    def _insert(connection, record):
        connection.execute('''INSERT INTO project_action_versions
            (project_id,action_id,version,basis_revision,created_at,snapshot,digest) VALUES(?,?,?,?,?,?,?)''',
            (record['project_id'], record['action_id'], record['version'], record['basis_revision'], record['created_at'],
             _encode(record), _digest(record)))

    def _context(self, connection, view):
        """Build current options and resolvers within one existing read snapshot."""
        targets = workspace_sources._targets(view)
        source_profile = self.source_library.summary_in_snapshot(connection, view)
        source_latest = {item['source_id']: {key: deepcopy(value) for key, value in item.items() if key != 'history'}
                         for item in source_profile['sources']}
        all_origins, eligible, supports = {}, [], {}
        requirements = {item['id']: item for item in view['project']['requirements']}
        for target_id, (target, context) in targets.items():
            if target['kind'] != 'finding':
                continue
            requirement = requirements[target['id']]
            origin = {**deepcopy(target), 'requirement_id': target['id'], 'model_id': requirement['model_id']}
            all_origins[target_id] = (origin, deepcopy(context))
            finding = context['finding']
            snapshot = {'project_id': view['project_id'], 'revision': view['revision'],
                        'run_id': view['run']['run_id'], 'review_digest': view['run']['review']['digest'],
                        'requirement': deepcopy(requirement), 'finding': deepcopy(finding),
                        'criterion_input': deepcopy(view['project']['inputs'][requirement['limit_input']]),
                        'declared_context': deepcopy(context)}
            support = {'support_id': target_id, 'kind': 'finding', 'label': target['label'] + ' · ' + finding['status'],
                       'requirement_id': target['id'], 'model_id': requirement['model_id'],
                       'snapshot': snapshot, 'context_digest': _digest(snapshot)}
            supports[target_id] = support
            if finding['status'] in {'not_met', 'not_assessed'}:
                eligible.append({**origin, 'finding_status': finding['status'],
                                 'suggested': _finding_suggestion(view, target['id'])})
        for source_id, source in source_latest.items():
            identity = 'source:' + source_id
            supports[identity] = {'support_id': identity, 'kind': 'source', 'label': source['title'] + ' · v' + str(source['version']),
                                  'source_id': source_id, 'source_version': source['version'],
                                  'snapshot': deepcopy(source), 'context_digest': _digest(source)}
        for link in source_profile['links']:
            old_target = link['target']
            origin_id = 'source_link:' + link['link_id']
            current_target = targets.get(old_target['target_id'])
            origin = {'target_id': origin_id, 'kind': 'source_link', 'id': link['link_id'],
                      'label': 'Review reference link · ' + old_target['label']}
            if old_target['kind'] in {'requirement', 'finding'}:
                origin['requirement_id'] = old_target['id']
                requirement = requirements.get(old_target['id'])
                if requirement:
                    origin['model_id'] = requirement['model_id']
            elif old_target['kind'] == 'model_assumption':
                origin['model_id'] = old_target['id']
            context = {'link': {key: deepcopy(value) for key, value in link.items() if key != 'history'},
                       'latest_source': deepcopy(source_latest.get(link['source_id'])),
                       'current_target': deepcopy(current_target)}
            all_origins[origin_id] = (origin, context)
            if link['status'] in {'needs_review', 'target_unavailable'}:
                eligible.append({**origin, 'source_review_status': link['status'], 'suggested': {
                    'title': ('Review reference: ' + old_target['label'])[:240],
                    'next_check': 'Compare the pinned source passage and its limitations with the current target and changed dependencies. Review the latest source version in Source library before confirming its link.',
                    'missing_evidence': 'A current applicability and relevance rationale for the reference link. ' + ' '.join(link['review_reasons']),
                    'completion_criteria': 'Record the reference and target context reviewed, supporting evidence and any unresolved relevance or validity limits. An action closure is not a source verification or engineering approval.'}})
        return all_origins, eligible, supports

    @staticmethod
    def _review_state(record, origins, support_options):
        origin = origins.get(record['origin']['target_id'])
        reasons = []
        status = 'current'
        if origin is None:
            status = 'origin_unavailable'
            reasons.append('The action origin is unavailable in this saved revision. Run relevant checks or restore the declared target before reviewing the action context.')
        elif origin[0] != record['origin'] or _digest(origin[1]) != record['origin_context_digest']:
            status = 'needs_review'
            reasons.append('The origin finding, source-review context or declared engineering dependencies changed after this action context was recorded.')
        for support in record['supports']:
            current = support_options.get(support['support_id'])
            if current is None or current['context_digest'] != support['context_digest']:
                if status == 'current':
                    status = 'needs_review'
                reasons.append('Supporting evidence changed or is unavailable: ' + support['label'] + '. The earlier evidence remains pinned.')
        return status, reasons, deepcopy(origin[0]) if origin else None

    def summary_in_snapshot(self, connection, view):
        records = self._records(connection, view['project_id'], view['revision'])
        origins, eligible, support_options = self._context(connection, view)
        actions = []
        for versions in records.values():
            record = deepcopy(versions[-1])
            status, reasons, current = self._review_state(record, origins, support_options)
            history_keys = ('action_id', 'version', 'basis_revision', 'created_at', 'title', 'next_check',
                            'missing_evidence', 'completion_criteria', 'status', 'note', 'closure_note', 'origin',
                            'origin_context_digest', 'origin_basis_revision', 'supports', 'digest')
            record.update(review_status=status, review_reasons=reasons, current_origin=current,
                          support_ids=[item['support_id'] for item in record['supports']],
                          history=[{key: deepcopy(item[key]) for key in history_keys} for item in versions])
            actions.append(record)
        result = {'schema': SCHEMA, 'project_id': view['project_id'], 'revision': view['revision'],
                  'context': 'saved', 'run_id': view['run']['run_id'] if view['run'] else None,
                  'project_digest': _digest(view['project']), 'actions': actions, 'origins': eligible,
                  'support_options': list(support_options.values()), 'limitations': list(LIMITATIONS),
                  'states': list(STATES), 'limits': {'max_actions': MAX_ACTIONS, 'max_versions_per_action': MAX_VERSIONS,
                                                   'max_supports_per_action': MAX_SUPPORTS}}
        result['digest'] = _digest(result)
        return result

    def summary(self, project_id, revision):
        with self.store._connect() as connection:
            connection.execute('BEGIN')
            return self.summary_in_snapshot(connection, self._view(connection, project_id, revision))

    def _require_expected(self, connection, view, expected_digest):
        if not isinstance(expected_digest, str) or re.fullmatch(r'[a-f0-9]{64}', expected_digest) is None:
            raise WorkspaceError('Supply the exact displayed action-queue SHA-256 context digest.')
        profile = self.summary_in_snapshot(connection, view)
        if profile['digest'] != expected_digest:
            raise ConflictError('The action queue or its source/evidence context changed. Refresh and inspect the current records before saving.')
        return profile

    @staticmethod
    def _details(spec):
        return {key: _text(spec[key], 'Action ' + key, maximum, empty=empty)
                for key, (maximum, empty) in TEXT_FIELDS.items()}

    def _version_record(self, connection, view, action_id, base_version):
        _text(action_id, 'Action ID', 64)
        _version(base_version)
        versions = self._records(connection, view['project_id'], view['revision']).get(action_id)
        if not versions or versions[-1]['version'] != base_version:
            raise ConflictError('The action changed or is unavailable. Refresh it before saving.')
        if len(versions) >= MAX_VERSIONS:
            raise WorkspaceError('This action reached its recorded-version limit.')
        return versions[-1]

    def create(self, project_id, revision, spec, *, expected_digest):
        _fields(spec, {'origin_id', *TEXT_FIELDS}, 'New action')
        _text(spec['origin_id'], 'Action origin ID', 8192)
        details = self._details(spec)
        with self.store._connect(write=True) as connection:
            view = self._view(connection, project_id, revision, write=True)
            profile = self._require_expected(connection, view, expected_digest)
            if len(profile['actions']) >= MAX_ACTIONS:
                raise WorkspaceError('The project action limit has been reached.')
            if not any(item['target_id'] == spec['origin_id'] for item in profile['origins']):
                raise ConflictError('Select a current unmet/unassessed finding or a flagged source link. Refresh the queue first.')
            if any(item['origin']['target_id'] == spec['origin_id'] and item['status'] != 'closed' for item in profile['actions']):
                raise ConflictError('An open action already tracks this origin. Update or review that action instead.')
            origins, _, _ = self._context(connection, view)
            origin, context = origins[spec['origin_id']]
            _bounded_context(context)
            record = {'project_id': project_id, 'action_id': uuid4().hex, 'version': 1,
                      'basis_revision': revision, 'created_at': _now(), **details, 'status': 'todo',
                      'origin': deepcopy(origin), 'origin_context': deepcopy(context), 'origin_basis_revision': revision,
                      'origin_context_digest': _digest(context), 'supports': [], 'closure_note': ''}
            self._insert(connection, record)
            return self.summary_in_snapshot(connection, view)

    def update(self, project_id, revision, action_id, base_version, spec, *, expected_digest):
        _fields(spec, {*TEXT_FIELDS, 'status', 'closure_note', 'support_ids'}, 'Action update')
        details = self._details(spec)
        if spec['status'] not in STATES:
            raise WorkspaceError('Choose a supported action workflow state.')
        closure_note = _text(spec['closure_note'], 'Closure note', 4000, empty=True)
        ids = spec['support_ids']
        if (not isinstance(ids, list) or len(ids) > MAX_SUPPORTS or any(not isinstance(item, str) for item in ids)
                or len(ids) != len(set(ids))):
            raise WorkspaceError('Select at most twenty distinct supporting evidence records.')
        with self.store._connect(write=True) as connection:
            view = self._view(connection, project_id, revision, write=True)
            self._require_expected(connection, view, expected_digest)
            old = self._version_record(connection, view, action_id, base_version)
            previous, selected = old['status'], spec['status']
            allowed = selected == previous or selected == 'in_progress'
            allowed |= previous in {'in_progress', 'ready_for_review'} and selected == 'todo'
            allowed |= STATES.index(selected) == STATES.index(previous) + 1
            if not allowed:
                raise ConflictError('Move through To do, In progress and Ready for review before closing; reopen a closed action to In progress.')
            origins, _, options = self._context(connection, view)
            old_supports = {item['support_id']: item for item in old['supports']}
            supports = []
            for identity in ids:
                if identity not in options:
                    raise ConflictError('A selected support is unavailable. Refresh and review the action context before selecting evidence.')
                support = deepcopy(old_supports[identity] if identity in old_supports else options[identity])
                _bounded_context(support['snapshot'])
                supports.append(support)
            if selected == 'closed':
                candidate = {**old, 'supports': supports}
                review_status, _, _ = self._review_state(candidate, origins, options)
                if review_status != 'current':
                    raise ConflictError('Review the changed action/evidence context before closing this action.')
                if not closure_note.strip() or not supports:
                    raise WorkspaceError('Closing requires a completion note and at least one linked supporting result or reference.')
            if previous == 'closed' and selected != 'closed':
                closure_note = ''
            record = {key: deepcopy(value) for key, value in old.items() if key != 'digest'}
            record.update(version=base_version + 1, basis_revision=revision, created_at=_now(),
                          **details, status=selected, supports=supports, closure_note=closure_note)
            self._insert(connection, record)
            return self.summary_in_snapshot(connection, view)

    def review(self, project_id, revision, action_id, base_version, *, expected_digest):
        with self.store._connect(write=True) as connection:
            view = self._view(connection, project_id, revision, write=True)
            self._require_expected(connection, view, expected_digest)
            old = self._version_record(connection, view, action_id, base_version)
            origins, _, _ = self._context(connection, view)
            resolved = origins.get(old['origin']['target_id'])
            if resolved is None:
                raise ConflictError('The action origin is unavailable. Run the required checks or restore the declared target before reviewing it.')
            origin, context = resolved
            _bounded_context(context)
            record = {key: deepcopy(value) for key, value in old.items() if key != 'digest'}
            record.update(version=base_version + 1, basis_revision=revision, created_at=_now(),
                          origin=deepcopy(origin), origin_context=deepcopy(context), origin_context_digest=_digest(context), origin_basis_revision=revision,
                          supports=[], closure_note='',
                          status='in_progress' if old['status'] in {'closed', 'ready_for_review'} else old['status'])
            self._insert(connection, record)
            return self.summary_in_snapshot(connection, view)
