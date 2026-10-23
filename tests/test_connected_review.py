"""Connected overview retains exact canonical context and supplemental scope."""
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
from sixd import simulation,workspace_review
from sixd.workspace import _digest
from sixd.project_examples import example_projects
from sixd.workspace_server import create_server


class ConnectedReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(dir=ROOT/'work')
        def forbidden(*args,**kw):raise AssertionError('Overview cannot call AI')
        cls.server=create_server(port=0,db_path=Path(cls.tmp.name)/'test.sqlite3',ai_local_directory=Path(cls.tmp.name)/'ai',provider_factory=forbidden,research_transport=forbidden)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()
    def req(self,path,body=None):
        c=HTTPConnection('127.0.0.1',self.server.server_port,timeout=30);c.request('GET' if body is None else 'POST',path,None if body is None else json.dumps(body),{'Content-Type':'application/json'})
        r=c.getresponse();b=r.read();status=r.status;typ=r.getheader('Content-Type');c.close();return status,json.loads(b) if typ.startswith('application/json') else b
    def project(self,run=True):
        p=deepcopy(example_projects()['baseline']);p['project_id']='review-'+uuid4().hex
        self.server.store.create_project(p)
        return self.server.store.run(p['project_id'],1) if run else self.server.store.get(p['project_id'],1)
    def get(self,v,revision=None):
        status,d=self.req('/api/review-workspace?project_id='+v['project_id']+'&revision='+str(revision or v['revision']));self.assertEqual(status,200,d);return d
    def test_current_findings_are_exact_without_solver_or_ai_execution(self):
        v=self.project();before=deepcopy(v)
        with patch.object(simulation,'simulate',side_effect=AssertionError('No solver')):
            d=self.get(v)
        self.assertEqual(d['run_id'],v['run']['run_id']);self.assertEqual(d['review_digest'],v['run']['review']['digest'])
        for row in d['findings']:
            original=v['run']['review']['findings'][row['requirement_id']]
            self.assertEqual(row['status'],original['status']);self.assertEqual(row['reason'],original['reason']);self.assertEqual(row['metric'],original['evidence']['metric'])
        self.assertEqual(sum(d['counts'].values()),len(v['project']['requirements']))
        self.assertEqual(self.server.store.get(v['project_id'],1),before)
        digest=d.pop('digest');self.assertEqual(digest,_digest(d))
    def test_uncalculated_requirements_are_not_numerical_unknowns_or_passes(self):
        v=self.project(False);d=self.get(v)
        self.assertIsNone(d['run_id']);self.assertEqual(d['counts']['not_run'],6);self.assertEqual(d['counts']['not_assessed'],0)
        self.assertTrue(all(x['status']=='not_run' and x['metric'] is None for x in d['findings']))
    def test_new_revision_does_not_borrow_earlier_findings(self):
        v=self.project();p=deepcopy(v['project']);p['inputs']['heat_input']['value']=700
        self.server.store.save_revision(v['project_id'],1,p);d=self.get(v,2)
        self.assertIsNone(d['run_id']);self.assertEqual(d['prior_review']['run_id'],v['run']['run_id']);self.assertEqual(d['counts']['not_run'],6)
        old=self.get(v,1);self.assertEqual(old['revision'],1);self.assertEqual(old['latest_revision'],2);self.assertEqual(old['run_id'],v['run']['run_id'])
    def test_supplemental_coverage_never_becomes_a_canonical_pass(self):
        v=self.project();d=self.get(v)
        self.assertEqual(len(d['coverage']['checks']),6)
        self.assertTrue(all(x['coverage_status']=='applicability_unknown' for x in d['coverage']['checks']))
        self.assertEqual(d['counts']['met'],6)
        self.assertEqual(d['actions']['actions'],[]);self.assertEqual(d['sources']['links'],[])
    def test_hypothetical_study_metadata_is_historical_after_rerun(self):
        v=self.project();spec=dict(schema='sixd.envelope-spec.v1',name='Bounded range',source='Constructed context',mode='grid',axes=[dict(input_id='heat_input',minimum=100,maximum=700,points=2)])
        saved=self.server.scenarios.run(v['project_id'],1,v['run']['run_id'],spec)
        d=self.get(v);self.assertEqual(d['simulations']['envelopes'][0]['study_id'],saved['receipt']['study_id']);self.assertNotIn('cases',d['simulations']['envelopes'][0]);self.assertEqual(d['counts']['met'],6)
        self.server.store.run(v['project_id'],1);d=self.get(v);self.assertTrue(d['simulations']['envelopes'][0]['historical'])
    def test_large_history_preview_discloses_omissions_without_loading_receipt(self):
        v=self.project();spec=dict(schema='sixd.envelope-spec.v1',name='Range',source='Constructed',mode='grid',axes=[dict(input_id='heat_input',minimum=100,maximum=700,points=2)])
        self.server.scenarios.run(v['project_id'],1,v['run']['run_id'],spec)
        with patch.object(workspace_review,'HISTORY_BYTES',1):d=self.get(v)
        self.assertEqual(d['simulations']['envelopes'],[]);self.assertEqual(d['simulations']['scenarios_history']['omitted_count'],1)
    def test_static_assets_and_read_only_route_contract(self):
        for path in ['/review-workspace.js','/review-workspace.css','/units.js','/connected-review.css']:self.assertEqual(self.req(path)[0],200)
        self.assertEqual(self.req('/api/review-workspace',{})[0],404)


if __name__=='__main__':unittest.main()
