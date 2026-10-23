"""Read-only connected review. Counts never replace canonical findings."""
from copy import deepcopy
from .workspace import WorkspaceError, _digest, _encode, _revision

HISTORY_LIMIT = 20
HISTORY_BYTES = 8 * 1024 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
LIMITATIONS = [
    'This overview captures the selected saved revision and supplemental records in one read snapshot; opening it executes no model or AI request.',
    'Canonical criterion findings, declared engineering coverage and action completion are separate records; none establishes whole-mission readiness.',
    'Draft edits have no calculated findings. Historical evidence remains available in its dedicated view and never supplies a current pass.',
    'History previews are bounded to twenty records and eight MiB of retained input per category; omitted records remain available in their dedicated histories.',
    'Source links, imported data and conditions declarations are user-supplied; their authenticity or physical applicability is not established by this overview.',
]


def _pick(record, keys):
    return {key: deepcopy(record[key]) for key in keys if key in record}


class WorkspaceReview:
    def __init__(self, store, coverage, actions, sources, series, scenarios):
        self.store, self.coverage, self.actions, self.sources = store, coverage, actions, sources
        self.series, self.scenarios = series, scenarios

    def _histories(self, connection, view):
        identity, revision = view['project_id'], view['revision']
        result = dict(imports=[], scenarios=[], envelopes=[], limits=dict(history_limit=HISTORY_LIMIT, input_byte_limit=HISTORY_BYTES))
        for table, service, label in [('simulation_imports',self.series,'imports'),('scenario_studies',self.scenarios,'scenarios')]:
            total = connection.execute(f'SELECT count(*) FROM {table} WHERE project_id=? AND revision<=?',(identity,revision)).fetchone()[0]
            rows = connection.execute(f'SELECT * FROM {table} WHERE project_id=? AND revision<=? ORDER BY sequence DESC LIMIT ?', (identity,revision,HISTORY_LIMIT)).fetchall()
            size, included = 0, 0
            for row in rows:
                length = len(row['receipt'].encode('utf-8'))
                if size + length > HISTORY_BYTES:
                    break
                receipt = service._read(connection,row)
                fresh = service._freshness(receipt,view)
                item = dict(name=receipt['spec']['name'], revision=receipt['revision'], historical=fresh['historical'],
                            source_current=fresh['source_current'], receipt_digest=row['digest'])
                if label == 'imports':
                    item['import_id'] = receipt['import_id']
                    result['imports'].append(item)
                else:
                    item.update(study_id=receipt['study_id'],mode=receipt['spec']['mode'])
                    result['envelopes' if item['mode']=='grid' else 'scenarios'].append(item)
                size += length
                included += 1
            result[label+'_history'] = dict(total=total,included=included,omitted_count=total-included,history_truncated=total>included)
        return result

    def summary(self, project_id, revision):
        with self.store._connect() as connection:
            connection.execute('BEGIN')
            view = self.store._view(connection,project_id,_revision(revision))
            project, run = view['project'], view['run']
            results = run['model_results'] if run else {}
            models = {m['id']:m for m in project['models']}
            findings = []
            for requirement in project['requirements']:
                finding = run['review']['findings'][requirement['id']] if run else None
                evidence = finding['evidence'] if finding else None
                findings.append(dict(requirement_id=requirement['id'],title=requirement['title'],
                    model_id=requirement['model_id'],model_type=models[requirement['model_id']]['type'],
                    status=finding['status'] if finding else 'not_run',
                    reason=finding['reason'] if finding else 'No current calculation exists for this saved revision. Retained earlier results do not assess this configuration.',
                    metric=deepcopy(evidence['metric']) if evidence else None,
                    limit=deepcopy(evidence['limit']) if evidence else None,operator=requirement['operator'],
                    assumptions=deepcopy(finding['assumptions']) if finding else [],
                    not_assessed=deepcopy(finding['not_assessed']) if finding else []))
            model_rows = []
            for model in project['models']:
                record = results.get(model['id']) or {}
                model_rows.append(dict(model_id=model['id'],type=model['type'],name=model.get('name') or model['id'],
                    status=record.get('status','not_run'),has_orbit=bool(record.get('simulation')),
                    has_flight=bool(record.get('flight_response')),has_attitude=bool(record.get('attitude_response')),
                    has_power=model['type']=='power_energy_budget' and record.get('status')=='completed'))
            coverage = self.coverage.summary_in_snapshot(connection,view)
            actions = self.actions.summary_in_snapshot(connection,view)
            sources = self.sources.summary_in_snapshot(connection,view)
            # Keep native summary identities, but omit histories and large source
            # excerpts from this navigation projection. Dedicated views retain them.
            coverage = _pick(coverage,('counts','criterion_counts','digest','limitations','count_definitions')) | dict(checks=[
                _pick(x,('row_id','title','requirement_id','phase','discipline','coverage_status','reason','needs_review','criterion_status')) for x in coverage['checks']])
            actions = _pick(actions,('digest','limitations','states')) | dict(actions=[
                _pick(x,('action_id','title','status','review_status','review_reasons','next_check')) for x in actions['actions']])
            sources = _pick(sources,('digest','limitations')) | dict(sources=[
                _pick(x,('source_id','title','version','url')) for x in sources['sources']],links=[
                _pick(x,('link_id','source_id','status','review_reasons','target_kind','target_id','target')) for x in sources['links']])
            histories = self._histories(connection,view)
            histories.update(canonical_orbits=sum(x['has_orbit'] for x in model_rows),canonical_flights=sum(x['has_flight'] for x in model_rows))
            prior = view.get('prior_run')
            result = dict(schema='sixd.review-workspace.v1',project_id=project_id,revision=revision,latest_revision=view['latest_revision'],
                project_name=project['name'],context='saved',project_digest=_digest(project),run_id=run['run_id'] if run else None,
                review_digest=run['review']['digest'] if run else None,has_current_review=run is not None,
                prior_review=_pick(prior,('revision','run_id','stale_reasons')) if prior else None,
                counts={status:sum(x['status']==status for x in findings) for status in ('met','not_met','not_assessed','not_run')},
                findings=findings,models=model_rows,coverage=coverage,actions=actions,sources=sources,simulations=histories,
                limitations=deepcopy(LIMITATIONS))
            result['digest'] = _digest(result)
            if len(_encode(result).encode('utf-8')) > MAX_RESPONSE_BYTES:
                raise WorkspaceError('The overview exceeds its 4 MiB display bound. Use the dedicated evidence and report views.')
            return result
