"""Recorded history acceptance: strict intake, bounded diagnostics and retention."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd import workspace_series as series
from sixd.project_examples import example_projects
from sixd.workspace import WorkspaceStore, WorkspaceError, ConflictError, _digest, _encode


def spec(**changes):
    result = dict(schema=series.SPEC_SCHEMA, name='Constructed history', source='Synthetic independent intake fixture',
                  data_kind='synthetic', configuration='Same declared reference configuration', frame='body_centered_inertial_3d',
                  time_origin='model_start', conditions_match='declared_match', filename='history.csv',
                  csv_text='t,height\n0,7000000\n1,7000001\n', time_column='t', time_unit='s', model_id='',
                  channels=[dict(name='Radius',column='height',unit='m',baseline_field='',tolerance=1)])
    return result | changes


class SeriesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.store = WorkspaceStore(Path(self.temp.name) / 'workspace.sqlite3')
        self.service = series.WorkspaceSeries(self.store)
        self.project = example_projects()['orbital_review']
        self.store.create_project(self.project)
        self.view = self.store.run(self.project['project_id'],1)
        self.pid, self.rid = self.project['project_id'], self.view['run']['run_id']
        self.samples = self.view['run']['model_results']['orbit']['simulation']['samples']

    def tearDown(self):
        self.temp.cleanup()

    def bound(self, **changes):
        rows = [self.samples[i] for i in (0,16,32)]
        csv = 't,height\n' + ''.join(f"{r['time_s']},{r['radius_m']+2}\n" for r in rows)
        return spec(model_id='orbit',csv_text=csv,
                    channels=[dict(name='Radius',column='height',unit='m',baseline_field='radius_m',tolerance=3)]) | changes

    def save(self, value=None):
        return self.service.save(self.pid,1,self.rid,self.bound() if value is None else value)

    def rewrite(self, receipt, digest=True):
        with self.store._connect(write=True) as connection:
            connection.execute('UPDATE simulation_imports SET receipt=?,digest=? WHERE import_id=?',
                               (_encode(receipt), _digest(receipt) if digest else '0'*64,receipt['import_id']))

    def test_exact_aligned_diagnostic_does_not_change_canonical_review(self):
        before = deepcopy(self.store.get(self.pid,1)['run'])
        item = self.save()
        result = item['receipt']['comparisons'][0]
        self.assertEqual(result['status'],'within_tolerance')
        self.assertEqual(result['max_absolute_difference'],2)
        self.assertEqual((result['aligned_samples'],result['unmatched_samples'],result['within_count']),(3,0,3))
        self.assertEqual(item['receipt']['baseline']['run'],{k:v for k,v in before.items() if k not in ('stale','stale_reasons')})
        self.assertEqual(self.store.get(self.pid,1)['run'],before)
        self.assertTrue(item['integrity']['unsigned'])
        outside = self.bound()
        outside['channels'][0]['tolerance'] = 1
        result = self.save(outside)['receipt']['comparisons'][0]
        self.assertEqual((result['status'],result['outside_count']),('outside_tolerance',3))

    def test_replay_only_without_run_or_model_and_no_automatic_binding(self):
        item = self.service.save(self.pid,1,None,spec())
        self.assertIsNone(item['receipt']['baseline'])
        self.assertEqual(item['receipt']['parsed']['times'],[0,1])
        self.assertEqual(item['receipt']['comparisons'][0]['status'],'not_assessed')
        with self.assertRaises(WorkspaceError):
            self.service.save(self.pid,1,None,self.bound())
        with self.assertRaises(WorkspaceError):
            self.service.save(self.pid,1,self.rid,spec())

    def test_preview_is_pure_and_preserves_csv_and_explicit_units(self):
        value = spec(csv_text='\ufefft,height,ignored\n0,1,"=DO_NOT_RUN()"\n1,2,text\n')
        p = self.service.preview(value)
        self.assertEqual(p['spec']['csv_text'],value['csv_text'])
        self.assertEqual(p['parsed']['channels'][0],dict(name='Radius',unit='m',values=[1,2]))
        self.assertEqual(self.service.list(self.pid,1)['imports'],[])
        self.assertEqual(p['parsed']['row_count'],2)

    def test_numeric_rejections_include_scientific_unsafe_integers(self):
        for bad in ('NaN','Infinity','=2+2','1e400','1e-400','5e-324','1e-309','9007199254740992','9.007199254740992e15','1,2'):
            with self.subTest(bad=bad), self.assertRaises(WorkspaceError):
                self.service.preview(spec(csv_text=f't,height\n0,{bad}\n1,2\n'))

    def test_strict_time_mapping_and_csv_shape(self):
        cases = [spec(time_unit='ms'),spec(csv_text='t,height\n1,2\n1,3\n'),
                 spec(csv_text='t,height\n2,2\n1,3\n'),spec(csv_text='t,height\n-1,2\n1,3\n'),
                 spec(csv_text='t,height\n0,1\n'),spec(csv_text='t,t\n0,1\n1,2\n'),
                 spec(csv_text='t,height\n0,1,2\n1,2\n'),spec(csv_text='t,height\n0,1\n1,"unterminated'),
                 spec(time_column='missing'),spec(channels=[]),spec(extra='ignored'),
                 spec(channels=[dict(name='Radius',column='t',unit='m',baseline_field='',tolerance=1)])]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(WorkspaceError):
                self.service.preview(value)

    def test_conditions_frame_unit_origin_and_tolerance_gates(self):
        for key,value in [('frame','some_other_frame'),('time_origin','launch_epoch'),('conditions_match','unknown'),('conditions_match','different')]:
            with self.subTest(key=key,value=value):
                self.assertEqual(self.save(self.bound(**{key:value}))['receipt']['comparisons'][0]['status'],'not_assessed')
        for key,value in [('tolerance',None),('unit','km'),('baseline_field','unavailable')]:
            candidate = self.bound()
            candidate['channels'][0][key] = value
            self.assertEqual(self.save(candidate)['receipt']['comparisons'][0]['status'],'not_assessed')
        for tolerance in (-1,True,float('nan'),float('inf'),1e-310):
            candidate = self.bound()
            candidate['channels'][0]['tolerance'] = tolerance
            with self.assertRaises(WorkspaceError):
                self.save(candidate)

    def test_partial_and_missing_alignment_never_become_whole_history_agreement(self):
        candidate = self.bound(csv_text=f"t,height\n0,7000000\n0.1,7000000\n{self.samples[16]['time_s']},7000000\n")
        result = self.save(candidate)['receipt']['comparisons'][0]
        self.assertEqual((result['status'],result['aligned_samples'],result['unmatched_samples']),('partial',2,1))
        result = self.save(self.bound(csv_text='t,height\n0.1,7e6\n0.2,7e6\n'))['receipt']['comparisons'][0]
        self.assertEqual((result['status'],result['aligned_samples']),('not_assessed',0))

    def test_retained_numerical_gap_blocks_comparison(self):
        p = deepcopy(self.project)
        del p['models'][0]['accuracy']
        self.store.save_revision(self.pid,1,p)
        view = self.store.run(self.pid,2)
        receipt = self.service.save(self.pid,2,view['run']['run_id'],self.bound())['receipt']
        self.assertEqual(receipt['comparisons'][0]['status'],'not_assessed')
        self.assertIn('numerical',receipt['comparisons'][0]['reason'])

    def test_current_run_and_revision_guards_and_historical_freshness(self):
        item = self.save()
        second = self.store.run(self.pid,1)
        with self.assertRaises(ConflictError):
            self.save()
        saved = self.service.get(item['receipt']['import_id'],1)
        self.assertEqual(saved['receipt'],item['receipt'])
        self.assertFalse(saved['freshness']['baseline_run_matches'])
        p = deepcopy(self.project)
        p['name'] += ' changed'
        self.store.save_revision(self.pid,1,p)
        with self.assertRaises(ConflictError):
            self.service.save(self.pid,1,second['run']['run_id'],self.bound())
        self.assertTrue(self.service.get(item['receipt']['import_id'],2)['freshness']['historical'])

    def test_tamper_reparse_and_comparison_recompute_even_with_new_digest(self):
        item = self.save()
        original = item['receipt']
        for change in ('raw','parsed','verdict','baseline','digest'):
            tampered = deepcopy(original)
            if change == 'raw': tampered['spec']['csv_text'] = tampered['spec']['csv_text'].replace('7000002','7000099')
            if change == 'parsed': tampered['parsed']['times'][1] += .1
            if change == 'verdict': tampered['comparisons'][0]['within_count'] = 999
            if change == 'baseline': tampered['baseline']['run']['created_at'] = 'changed'
            self.rewrite(tampered,digest=change!='digest')
            with self.subTest(change=change),self.assertRaises(WorkspaceError):
                self.service.get(original['import_id'],1)
        self.rewrite(original)
        self.assertEqual(self.service.get(original['import_id'],1)['receipt'],original)

    def test_history_reopens_without_current_solver_and_sources_are_not_rewritten(self):
        item = self.save()
        with patch('sixd.simulation.simulate',side_effect=AssertionError('no integration')), patch('sixd.powered_flight._integrate',side_effect=AssertionError('no integration')):
            result = self.service.get(item['receipt']['import_id'],1)
            self.assertEqual(result['receipt'],item['receipt'])
        with patch.object(series,'_sources',return_value={**series._sources(),'workspace_series.py':'0'*64}):
            result = self.service.get(item['receipt']['import_id'],1)
            self.assertFalse(result['freshness']['source_current'])
            self.assertEqual(result['receipt'],item['receipt'])
            with self.assertRaises(ConflictError): self.save()

    def test_same_snapshot_export_digest_and_bounded_history(self):
        self.service.save(self.pid,1,None,spec())
        with self.store._connect() as connection:
            view = self.store._view(connection,self.pid,1)
            snapshot = self.service.snapshot(connection,view)
        self.assertEqual(self.service.summary(self.pid,1),snapshot)
        self.assertEqual(snapshot['digest'],_digest({k:v for k,v in snapshot.items() if k!='digest'}))
        self.assertEqual(len(snapshot['imports']),1)
        self.assertFalse(snapshot['history_truncated'])
        self.assertEqual(self.service.list(self.pid,1)['baseline_run_id'],self.rid)

    def test_component_channels_and_powered_cutoff_ambiguity(self):
        candidate = self.bound()
        candidate['channels'][0]['baseline_field']='position_x'
        candidate['csv_text']='t,height\n'+''.join(f"{r['time_s']},{r['position_m'][0]}\n" for r in self.samples[:2])
        self.assertEqual(self.save(candidate)['receipt']['comparisons'][0]['status'],'within_tolerance')
        p = example_projects()['powered_flight_review']
        self.store.create_project(p)
        view = self.store.run(p['project_id'],1)
        rows = view['run']['model_results']['vertical_flight']['flight_response']['samples']
        cutoff = next(r for r in rows if r['event'] == 'before_cutoff')
        candidate = spec(model_id='vertical_flight',frame='radial_vertical_above_launch_surface',
                         csv_text=f"t,height\n0,20000\n{cutoff['time_s']},0\n",
                         channels=[dict(name='Thrust',column='height',unit='N',baseline_field='thrust_n',tolerance=1)])
        result = self.service.save(p['project_id'],1,view['run']['run_id'],candidate)['receipt']['comparisons'][0]
        self.assertEqual(result['status'],'not_assessed')
        self.assertIn('before/after',result['reason'])


class SeriesPreviewBoundsTests(unittest.TestCase):
    def test_declared_limits_reject_oversized_csv_rows_columns_and_channels(self):
        oversized_rows = 't,height\n' + ''.join(f'{i},1\n' for i in range(series.MAX_ROWS+1))
        oversized_columns = ','.join(['t','height']+[f'c{i}' for i in range(31)])+'\n'+','.join(['0']*33)+'\n'+','.join(['1']*33)+'\n'
        for value in (spec(csv_text='x'*(series.MAX_CSV_BYTES+1)), spec(csv_text=oversized_rows),
                      spec(csv_text=oversized_columns), spec(channels=[dict(name=str(i),column=str(i),unit='m',baseline_field='',tolerance=None) for i in range(13)])):
            with self.assertRaises(WorkspaceError):
                series.preview(value)

    def test_maximum_rows_remain_replayable_without_default_units(self):
        text = 't,height\n' + ''.join(f'{i},1\n' for i in range(series.MAX_ROWS))
        result = series.preview(spec(csv_text=text))
        self.assertEqual(result['parsed']['row_count'],series.MAX_ROWS)
        self.assertEqual(result['parsed']['times'][-1],series.MAX_ROWS-1)
        value = spec()
        value['channels'][0]['unit']=''
        with self.assertRaises(WorkspaceError): series.preview(value)


if __name__ == '__main__':
    unittest.main()
