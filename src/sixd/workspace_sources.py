"""Versioned, manual project references, separate from numerical evidence.

URLs are stored as text and are never fetched. A link records user-supplied
support, not a verified citation, model applicability or engineering approval.
"""
from copy import deepcopy
import json
import re
from urllib.parse import urlsplit
from uuid import uuid4

from . import chains, engineering, lifecycle, workspace
from .workspace import ConflictError, WorkspaceError, _digest, _encode, _now, _revision

SCHEMA = 'sixd.project-sources.v1'
MAX_SOURCES = 100
MAX_LINKS = 300
MAX_VERSIONS = 20
MAX_CONTEXT_BYTES = 128 * 1024
LIMITATIONS = [
    'References, excerpts and support claims are supplied manually; 6D does not fetch, authenticate or independently verify their contents.',
    'Source links supplement a saved configuration. They never change a canonical calculation, requirement finding or immutable engineering receipt.',
    'Linked means the recorded source version and declared engineering dependencies still match. It is not a physical-validity or approval verdict.',
    'Review flags compare explicit dependencies only. Changes in the world or at an external URL are not detected without a new supplied source version.',
    'Confirming a link records a user review of its current context; it does not establish the accuracy, relevance or sufficiency of the cited evidence.',
    'Annotations added later to a saved revision are supplemental library records, not part of that revision’s original numerical review.',
    'Source and link digests are unsigned consistency checks, not authenticated approvals or proof of truth.',
]


def _fields(value, names, label):
    if not isinstance(value, dict) or set(value) != set(names):
        raise WorkspaceError(label + ' has missing or unsupported fields.')


def _text(value, label, limit, *, empty=False):
    if (not isinstance(value, str) or len(value) > limit or (not empty and not value.strip())
            or any(ord(ch) < 32 and ch not in '\r\n\t' for ch in value)):
        raise WorkspaceError(f'{label} must be {"" if empty else "nonempty "}text of at most {limit} characters.')
    return value


def _url(value):
    _text(value, 'Source URL', 2048)
    if value != value.strip() or any(ch.isspace() for ch in value) or '\\' in value:
        raise WorkspaceError('Use an HTTP or HTTPS source URL without whitespace, credentials or backslashes.')
    try:
        parsed = urlsplit(value)
        port = parsed.port
        if (parsed.scheme.lower() not in {'http', 'https'} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or not parsed.hostname.strip('.') or any(ch in parsed.hostname for ch in '<>"\'`')
                or (port is not None and not 1 <= port <= 65535)):
            raise ValueError
    except ValueError as exc:
        raise WorkspaceError('Use a valid HTTP or HTTPS source URL with a hostname and no credentials.') from exc
    return value


def _version(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise WorkspaceError(label + ' must be a positive integer.')
    return value


def _model_context(project, model):
    context = {'definition': deepcopy(model), 'inputs': lifecycle._bound_inputs(project, model),
               'adapter_version': engineering.MODEL_VERSIONS.get(model['type']),
               'verification_sources': workspace._sources()}
    if model.get('links'):
        context['calculation_dependencies'] = chains.dependency_configuration(project, model['id'])
    return context


def _targets(view):
    project, run = view['project'], view['run']
    models = {item['id']: item for item in project['models']}
    output = {}
    for requirement in project['requirements']:
        model = models[requirement['model_id']]
        target = {'target_id': 'requirement:' + requirement['id'], 'kind': 'requirement',
                  'id': requirement['id'], 'label': requirement['title']}
        context = {'requirement': deepcopy(requirement), 'model': _model_context(project, model),
                   'criterion_input': deepcopy(project['inputs'][requirement['limit_input']])}
        output[target['target_id']] = (target, context)
        if run and requirement['id'] in run['review']['findings']:
            target = {'target_id': 'finding:' + requirement['id'], 'kind': 'finding',
                      'id': requirement['id'], 'label': requirement['title'] + ' · saved finding',
                      'run_id': run['run_id']}
            finding = run['review']['findings'][requirement['id']]
            output[target['target_id']] = (target, {**context, 'run_id': run['run_id'],
                'review_digest': run['review']['digest'], 'finding': deepcopy(finding)})
    for model in project['models']:
        for index, assumption in enumerate(engineering._ASSUMPTIONS.get(model['type'], [])):
            target = {'target_id': 'assumption:' + model['id'] + ':' + str(index),
                      'kind': 'model_assumption', 'id': model['id'], 'assumption_index': index,
                      'label': model['id'] + ' · ' + assumption}
            output[target['target_id']] = (target, {'model': _model_context(project, model),
                'assumption': assumption, 'assumption_index': index})
    return output


class WorkspaceSources:
    def __init__(self, store):
        self.store = store
        with self.store._connect(write=True) as connection:
            for table, identity in [('project_source_versions', 'source_id'), ('project_source_link_versions', 'link_id')]:
                connection.execute(f'''CREATE TABLE IF NOT EXISTS {table} (
                    project_id TEXT NOT NULL REFERENCES projects(project_id),
                    {identity} TEXT NOT NULL, version INTEGER NOT NULL,
                    basis_revision INTEGER NOT NULL, created_at TEXT NOT NULL,
                    snapshot TEXT NOT NULL, digest TEXT NOT NULL,
                    PRIMARY KEY(project_id, {identity}, version),
                    FOREIGN KEY(project_id, basis_revision) REFERENCES revisions(project_id, revision)
                )''')

    def _view(self, connection, project_id, revision, *, write=False):
        _text(project_id, 'Project ID', 4096)
        view = self.store._view(connection, project_id, _revision(revision))
        if write and view['revision'] != view['latest_revision']:
            raise ConflictError('Source changes require the latest saved project revision. Switch to it first.')
        return view

    @staticmethod
    def _load(row, identity):
        try:
            snapshot = json.loads(row['snapshot'])
            if (not isinstance(snapshot, dict) or _digest(snapshot) != row['digest']
                    or snapshot['project_id'] != row['project_id']
                    or snapshot[identity] != row[identity] or snapshot['version'] != row['version']
                    or snapshot['basis_revision'] != row['basis_revision']
                    or snapshot['created_at'] != row['created_at']):
                raise ValueError
            return {**snapshot, 'digest': row['digest']}
        except (ValueError, TypeError, KeyError) as exc:
            raise WorkspaceError('A stored source-library record is inconsistent. No record was replaced.') from exc

    def _records(self, connection, table, identity, project_id, revision):
        rows = connection.execute(f'''SELECT * FROM {table} WHERE project_id=? AND basis_revision<=?
            ORDER BY {identity}, version''', (project_id, revision)).fetchall()
        grouped = {}
        for row in rows:
            record = self._load(row, identity)
            grouped.setdefault(record[identity], []).append(record)
        return grouped

    @staticmethod
    def _insert(connection, table, identity, value):
        digest = _digest(value)
        connection.execute(f'''INSERT INTO {table}
            (project_id,{identity},version,basis_revision,created_at,snapshot,digest) VALUES(?,?,?,?,?,?,?)''',
            (value['project_id'], value[identity], value['version'], value['basis_revision'], value['created_at'], _encode(value), digest))

    def summary_in_snapshot(self, connection, view):
        """Project references captured with a caller's existing SQLite snapshot."""
        sources = self._records(connection, 'project_source_versions', 'source_id', view['project_id'], view['revision'])
        links = self._records(connection, 'project_source_link_versions', 'link_id', view['project_id'], view['revision'])
        targets = _targets(view)
        latest_sources = {key: values[-1] for key, values in sources.items()}
        displayed_sources = [{**deepcopy(values[-1]), 'history': deepcopy(values)} for values in sources.values()]
        displayed_links = []
        for values in links.values():
            link = deepcopy(values[-1])
            history = [{key: deepcopy(item[key]) for key in ('version', 'source_version', 'target', 'note',
                       'basis_revision', 'created_at', 'context_digest', 'digest')} for item in values]
            source = next((item for item in sources.get(link['source_id'], []) if item['version'] == link['source_version']), None)
            if source is None:
                raise WorkspaceError('A saved source link has no matching source version.')
            if source['digest'] != link['source_digest'] or _digest(link['context']) != link['context_digest']:
                raise WorkspaceError('A saved source link has inconsistent source or target context binding.')
            reasons = []
            target = targets.get(link['target']['target_id'])
            status = 'linked'
            if target is None:
                status = 'target_unavailable'
                reasons.append('The linked requirement, model assumption or current finding is unavailable in this saved revision.')
            elif _digest(target[1]) != link['context_digest'] or target[0] != link['target']:
                status = 'needs_review'
                reasons.append('The target’s declared dependencies, assumption text or saved finding changed after this link was recorded.')
            if latest_sources[link['source_id']]['version'] != link['source_version']:
                if status == 'linked':
                    status = 'needs_review'
                reasons.append('A newer source version exists. This link still preserves its originally recorded source version.')
            displayed_links.append({**link, 'source': deepcopy(source), 'status': status,
                                    'review_reasons': reasons, 'history': history})
        result = {'schema': SCHEMA, 'project_id': view['project_id'], 'revision': view['revision'],
                  'project_digest': _digest(view['project']),
                  'context': 'saved', 'run_id': view['run']['run_id'] if view['run'] else None,
                  'sources': displayed_sources, 'links': displayed_links,
                  'targets': [deepcopy(target) for target, _ in targets.values()],
                  'limitations': list(LIMITATIONS),
                  'limits': {'max_sources': MAX_SOURCES, 'max_links': MAX_LINKS, 'max_versions_per_record': MAX_VERSIONS}}
        result['digest'] = _digest(result)
        return result

    def summary(self, project_id, revision):
        with self.store._connect() as connection:
            connection.execute('BEGIN')
            return self.summary_in_snapshot(connection, self._view(connection, project_id, revision))

    def save_source(self, project_id, revision, source):
        _fields(source, {'source_id', 'base_version', 'title', 'url', 'excerpt', 'details'}, 'Source')
        fields = {name: _text(source[name], 'Source ' + name, maximum, empty=empty)
                  for name, maximum, empty in [('title', 240, False), ('excerpt', 8000, False), ('details', 4000, True)]}
        fields['url'] = _url(source['url'])
        identity = source['source_id']
        if identity is not None:
            _text(identity, 'Source ID', 64)
            _version(source['base_version'], 'Source base version')
        elif source['base_version'] is not None:
            raise WorkspaceError('A new source must not declare a base version.')
        with self.store._connect(write=True) as connection:
            view = self._view(connection, project_id, revision, write=True)
            sources = self._records(connection, 'project_source_versions', 'source_id', project_id, revision)
            if identity is None:
                if len(sources) >= MAX_SOURCES:
                    raise WorkspaceError('The project source limit has been reached.')
                identity, version = uuid4().hex, 1
            else:
                versions = sources.get(identity)
                if not versions or versions[-1]['version'] != source['base_version']:
                    raise ConflictError('The source changed or is unavailable. Refresh it before editing.')
                if len(versions) >= MAX_VERSIONS:
                    raise WorkspaceError('This source reached its saved-version limit; preserve it and add a separate source.')
                version = source['base_version'] + 1
            self._insert(connection, 'project_source_versions', 'source_id', {'project_id': project_id,
                'source_id': identity, 'version': version, 'basis_revision': revision, 'created_at': _now(), **fields})
            return self.summary_in_snapshot(connection, view)

    @staticmethod
    def _link_record(project_id, revision, source, target, context, note, *, identity=None, version=1):
        if len(_encode(context).encode('utf-8')) > MAX_CONTEXT_BYTES:
            raise WorkspaceError('This target context exceeds the source-link size limit.')
        return {'project_id': project_id, 'link_id': identity or uuid4().hex, 'version': version,
                'basis_revision': revision, 'created_at': _now(), 'source_id': source['source_id'],
                'source_version': source['version'], 'source_digest': source['digest'],
                'target': deepcopy(target), 'context': deepcopy(context), 'context_digest': _digest(context), 'note': note}

    def _require_expected_profile(self, connection, view, expected_digest):
        if expected_digest is None:
            return  # Trusted internal callers may operate on a fresh transaction.
        if not isinstance(expected_digest, str) or re.fullmatch(r'[a-f0-9]{64}', expected_digest) is None:
            raise WorkspaceError('The expected source-library digest must be a lowercase SHA-256 digest.')
        if self.summary_in_snapshot(connection, view)['digest'] != expected_digest:
            raise ConflictError('The source library or saved finding changed after you reviewed it. Refresh and review the current context before linking or confirming.')

    def link_source(self, project_id, revision, spec, *, expected_digest=None):
        _fields(spec, {'source_id', 'source_version', 'target_id', 'note'}, 'Source link')
        _text(spec['source_id'], 'Source ID', 64)
        _version(spec['source_version'], 'Source version')
        _text(spec['target_id'], 'Target ID', 8192)
        _text(spec['note'], 'Link note', 4000, empty=True)
        with self.store._connect(write=True) as connection:
            view = self._view(connection, project_id, revision, write=True)
            self._require_expected_profile(connection, view, expected_digest)
            targets = _targets(view)
            if spec['target_id'] not in targets:
                raise ConflictError('The selected target is unavailable. Refresh the source library.')
            sources = self._records(connection, 'project_source_versions', 'source_id', project_id, revision)
            versions = sources.get(spec['source_id'])
            if not versions or versions[-1]['version'] != spec['source_version']:
                raise ConflictError('Link the current source version. Refresh the library first.')
            links = self._records(connection, 'project_source_link_versions', 'link_id', project_id, revision)
            if len(links) >= MAX_LINKS:
                raise WorkspaceError('The project link limit has been reached.')
            if any(items[-1]['source_id'] == spec['source_id'] and items[-1]['target']['target_id'] == spec['target_id'] for items in links.values()):
                raise ConflictError('This source is already linked to that target. Review its existing link instead.')
            target, context = targets[spec['target_id']]
            self._insert(connection, 'project_source_link_versions', 'link_id', self._link_record(
                project_id, revision, versions[-1], target, context, spec['note']))
            return self.summary_in_snapshot(connection, view)

    def confirm_link(self, project_id, revision, link_id, base_version, *, expected_digest=None):
        _text(link_id, 'Source link ID', 64)
        _version(base_version, 'Link base version')
        with self.store._connect(write=True) as connection:
            view = self._view(connection, project_id, revision, write=True)
            self._require_expected_profile(connection, view, expected_digest)
            links = self._records(connection, 'project_source_link_versions', 'link_id', project_id, revision)
            versions = links.get(link_id)
            if not versions or versions[-1]['version'] != base_version:
                raise ConflictError('The source link changed or is unavailable. Refresh before confirming it.')
            if len(versions) >= MAX_VERSIONS:
                raise WorkspaceError('This source link reached its saved-version limit.')
            old = versions[-1]
            targets = _targets(view)
            if old['target']['target_id'] not in targets:
                raise ConflictError('The target is unavailable; its previous link remains preserved.')
            sources = self._records(connection, 'project_source_versions', 'source_id', project_id, revision)
            source = sources[old['source_id']][-1]
            target, context = targets[old['target']['target_id']]
            self._insert(connection, 'project_source_link_versions', 'link_id', self._link_record(
                project_id, revision, source, target, context, old['note'], identity=link_id, version=base_version + 1))
            return self.summary_in_snapshot(connection, view)
