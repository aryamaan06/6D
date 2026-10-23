"""HTTP acceptance for real CSV imports and canonical evidence preservation."""
from copy import deepcopy
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from sixd import simulation
from sixd.workspace_server import create_server
from sixd.project_examples import example_projects


def spec():
    return dict(schema='sixd.series-spec.v1',name='Constructed external history',source='Synthetic API acceptance values',
        data_kind='synthetic',configuration='Recorded demonstration only',frame='test_frame',time_origin='test_start',
        conditions_match='unknown',filename='history.csv',csv_text='t,value\n0,5\n1,6\n2,7\n',time_column='t',time_unit='s',model_id='',
        channels=[dict(name='Value',column='value',unit='m',baseline_field='',tolerance=None)])


class SimulationImportsAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(dir=ROOT/'work')
        def forbidden(*a,**k):raise AssertionError('No AI requests')
        cls.server=create_server(port=0,db_path=Path(cls.tmp.name)/'data.sqlite3',ai_local_directory=Path(cls.tmp.name)/'ai',provider_factory=forbidden,research_transport=forbidden)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()
    def req(self,path,data=None,headers=None):
        c=HTTPConnection('127.0.0.1',self.server.server_port,timeout=30)
        c.request('GET' if data is None else 'POST',path,None if data is None else json.dumps(data),{'Content-Type':'application/json',**(headers or {})})
        r=c.getresponse();body=r.read();status=r.status;typ=r.getheader('Content-Type');c.close()
        return status,json.loads(body) if typ.startswith('application/json') else body
    def project(self,run=False):
        p=deepcopy(example_projects()['orbital_review']);p['project_id']='import-api-'+uuid4().hex
        status,v=self.req('/api/projects',{'project':p});self.assertEqual(status,200,v)
        if run:
            status,v=self.req('/api/run',dict(project_id=v['project_id'],revision=1));self.assertEqual(status,200,v)
        return v
    def save(self,v,s=None,baseline=None):
        return self.req('/api/simulation-imports',dict(project_id=v['project_id'],revision=1,baseline_run_id=baseline,spec=s or spec()))
    def query(self,v):return '?project_id='+v['project_id']+'&revision=1'
    def test_preview_save_reopen_export_and_combined_snapshot_preserve_exact_data(self):
        v=self.project();s=spec();s['csv_text']=s['csv_text'].replace('\n','\r\n')
        status,p=self.req('/api/simulation-imports/preview',{'spec':s});self.assertEqual(status,200,p)
        self.assertEqual(p['parsed']['times'],[0,1,2])
        status,d=self.save(v,s);self.assertEqual(status,200,d);identity=d['receipt']['import_id']
        self.assertEqual(d['receipt']['spec']['csv_text'],s['csv_text'])
        with patch.object(simulation,'simulate',side_effect=AssertionError('No recalculation')):
            self.assertEqual(self.req('/api/simulation-imports/'+identity+'?revision=1')[1],d)
            self.assertEqual(self.req('/api/simulation-import-export?id='+identity+'&revision=1')[1],d)
            status,export=self.req('/api/engineering-review-export'+self.query(v));self.assertEqual(status,200,export)
            self.assertEqual(export['simulation_imports']['imports'][0],d)
            self.assertEqual(self.req('/api/simulation-import-summary'+self.query(v))[1],export['simulation_imports'])
        self.assertEqual(self.req('/api/workspace'+self.query(v))[1],v)
    def bound(self,v):
        s=spec();r=v['run']['model_results']['orbit']['simulation'];rows=[r['samples'][0],r['samples'][-1]]
        s.update(frame='body_centered_inertial_3d',time_origin='model_start',model_id='orbit',conditions_match='declared_match',
            csv_text='t,radius\n'+''.join(f"{x['time_s']!r},{x['radius_m']!r}\n" for x in rows),
            channels=[dict(name='Radius',column='radius',unit='m',baseline_field='radius_m',tolerance=0)])
        return s
    def test_exact_baseline_comparison_and_original_findings_unchanged(self):
        v=self.project(True);s=self.bound(v)
        status,d=self.save(v,s,v['run']['run_id']);self.assertEqual(status,200,d)
        self.assertEqual(d['receipt']['comparisons'][0]['status'],'within_tolerance')
        self.assertEqual(d['receipt']['comparisons'][0]['aligned_samples'],2)
        self.assertEqual(self.req('/api/workspace'+self.query(v))[1],v)
    def test_frame_mismatch_cannot_be_reported_as_agreement(self):
        v=self.project(True);s=self.bound(v);s['frame']='rotating_frame'
        status,d=self.save(v,s,v['run']['run_id']);self.assertEqual(status,200,d)
        self.assertEqual(d['receipt']['comparisons'][0]['status'],'not_assessed')
    def test_stale_baseline_rejected_and_prior_import_becomes_historical(self):
        v=self.project(True);s=self.bound(v);status,d=self.save(v,s,v['run']['run_id']);self.assertEqual(status,200,d)
        self.req('/api/run',dict(project_id=v['project_id'],revision=1))
        self.assertEqual(self.save(v,s,v['run']['run_id'])[0],409)
        reread=self.req('/api/simulation-imports/'+d['receipt']['import_id']+'?revision=1')[1]
        self.assertEqual(reread['receipt'],d['receipt']);self.assertTrue(reread['freshness']['historical'])
    def test_bad_csv_and_cross_origin_do_not_save(self):
        v=self.project();s=spec();s['csv_text']='t,value\n0,5\n0,7\n'
        self.assertEqual(self.save(v,s)[0],400)
        self.assertEqual(self.req('/api/simulation-imports',dict(project_id=v['project_id'],revision=1,baseline_run_id=None,spec=spec()),{'Origin':'https://example.org'})[0],403)
        self.assertEqual(self.req('/api/simulation-imports'+self.query(v))[1]['imports'],[])
    def test_static_assets_and_upload_bound_are_available(self):
        for path in ['/simulation-imports.js','/simulation-imports.css']:
            self.assertEqual(self.req(path)[0],200)
        s=spec();s['csv_text']='t,value,comment\n'+''.join(str(i)+',1,'+'x'*180+'\n' for i in range(16385))
        status,p=self.req('/api/simulation-imports/preview',{'spec':s});self.assertEqual(status,200,p)
        self.assertEqual(p['parsed']['row_count'],16385)


if __name__=='__main__':unittest.main()
