"""Operating studies use real adapters and preserve canonical projects."""
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
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from sixd import workspace_scenarios as studies
from sixd.project_examples import example_projects
from sixd.workspace_server import create_server


def spec():
    return dict(schema='sixd.envelope-spec.v1',name='Constructed atmospheric conditions',source='Independent acceptance arithmetic; not flight measurements.',mode='grid',
        axes=[dict(input_id='density',minimum=.01,maximum=.03,points=2),dict(input_id='relative_speed',minimum=100,maximum=200,points=2)])


class EnvelopeAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(dir=ROOT/'work')
        def forbidden(*a,**kw):raise AssertionError('No paid calls')
        cls.server=create_server(port=0,db_path=Path(cls.tmp.name)/'test.sqlite3',ai_local_directory=Path(cls.tmp.name)/'ai',provider_factory=forbidden,research_transport=forbidden)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()
    def req(self,path,body=None,headers=None):
        c=HTTPConnection('127.0.0.1',self.server.server_port,timeout=30)
        c.request('GET' if body is None else 'POST',path,None if body is None else json.dumps(body),{'Content-Type':'application/json',**(headers or {})})
        r=c.getresponse();content=r.read();status=r.status;typ=r.getheader('Content-Type');c.close()
        return status,json.loads(content) if typ.startswith('application/json') else content
    def baseline(self):
        p=deepcopy(example_projects()['baseline']);p['project_id']='envelope-api-'+uuid4().hex
        status,v=self.req('/api/projects',{'project':p});self.assertEqual(status,200,v)
        status,v=self.req('/api/run',dict(project_id=p['project_id'],revision=1));self.assertEqual(status,200,v);return v
    def payload(self,v,s=None):return dict(project_id=v['project_id'],revision=1,baseline_run_id=v['run']['run_id'],spec=s or spec())
    def query(self,v):return '?project_id='+v['project_id']+'&revision=1'
    def test_preview_is_solver_free_and_shows_full_product(self):
        v=self.baseline()
        with patch.object(studies,'evaluate_models',side_effect=AssertionError('No preview execution')):
            status,p=self.req('/api/envelopes/preview',self.payload(v));self.assertEqual(status,200,p)
        self.assertEqual(p['case_count'],4)
        self.assertEqual(p['axes'][0]['values'],[.01,.03])
        self.assertEqual(self.req('/api/scenarios'+self.query(v))[1]['studies'],[])
    def test_actual_grid_margin_matches_independent_drag_arithmetic_and_snapshot(self):
        v=self.baseline();status,d=self.req('/api/scenarios',self.payload(v));self.assertEqual(status,200,d)
        r=d['receipt'];self.assertEqual(r['schema'],'sixd.envelope-study.v1');self.assertEqual(len(r['cases']),4)
        summary=next(x for x in r['envelope_summary'] if x['requirement_id']=='drag_limit')
        self.assertAlmostEqual(summary['worst_observed']['value'],100-.5*.03*200**2,places=9)
        self.assertEqual(summary['counts'],dict(met=1,not_met=3,not_assessed=0))
        self.assertEqual(summary['worst_observed']['case_indices'],[3])
        self.assertEqual(self.req('/api/workspace'+self.query(v))[1],v)
        with patch.object(studies,'evaluate_models',side_effect=AssertionError('No history execution')):
            self.assertEqual(self.req('/api/scenario-export?id='+r['study_id']+'&revision=1')[1],d)
            status,e=self.req('/api/engineering-review-export'+self.query(v));self.assertEqual(status,200,e)
        self.assertEqual(e['operating_envelopes']['studies'][0],d)
        self.assertEqual(e['workspace']['run']['review'],v['run']['review'])
        self.assertEqual(self.req('/api/envelopes/summary'+self.query(v))[1],e['operating_envelopes'])
    def test_criteria_and_excess_product_are_blocked(self):
        v=self.baseline();s=spec();s['axes'][0]['input_id']='maximum_drag_force'
        self.assertEqual(self.req('/api/envelopes/preview',self.payload(v,s))[0],400)
        s=spec();s['axes'][0]['points']=5;s['axes'][1]['points']=5
        self.assertEqual(self.req('/api/scenarios',self.payload(v,s))[0],400)
        self.assertEqual(self.req('/api/scenarios'+self.query(v))[1]['studies'],[])
    def test_stale_baseline_refused_and_frozen_history_retained(self):
        v=self.baseline();status,d=self.req('/api/scenarios',self.payload(v));self.assertEqual(status,200,d)
        self.req('/api/run',dict(project_id=v['project_id'],revision=1))
        self.assertEqual(self.req('/api/scenarios',self.payload(v))[0],409)
        later=self.req('/api/scenarios/'+d['receipt']['study_id']+'?revision=1')[1]
        self.assertEqual(later['receipt'],d['receipt']);self.assertTrue(later['freshness']['historical'])
    def test_assets_and_cross_origin_boundary(self):
        for file in ['/envelopes.js','/envelopes.css']:self.assertEqual(self.req(file)[0],200)
        v=self.baseline();self.assertEqual(self.req('/api/envelopes/preview',self.payload(v),{'Origin':'https://example.org'})[0],403)


if __name__=='__main__':unittest.main()
