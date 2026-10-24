"""Actual HTTP intake, revision, numerical evidence and combined export."""
from copy import deepcopy
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from sixd import lifecycle
from sixd.workspace_server import create_server


class GuidedAscentAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=ROOT/'work')
        def forbidden(*args,**kwargs): raise AssertionError('No external provider for local ascent review')
        cls.server = create_server(port=0,db_path=Path(cls.temp.name)/'workspace.sqlite3',
                                   provider_factory=forbidden,research_transport=forbidden)
        cls.worker = threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.worker.join();cls.temp.cleanup()

    def request(self,path,body=None):
        c = HTTPConnection('127.0.0.1',self.server.server_port,timeout=60)
        c.request('GET' if body is None else 'POST',path,None if body is None else json.dumps(body),{'Content-Type':'application/json'})
        r = c.getresponse();data = json.loads(r.read());c.close()
        self.assertEqual(r.status,200,data)
        return data

    def test_saved_guided_reference_revision_and_export(self):
        catalog = self.request('/api/model-catalog')
        self.assertEqual(len(catalog['models']),10)
        templates = self.request('/api/templates')['templates']
        project = next(t['project'] for t in templates if t['id']=='guided_ascent_review')
        project['project_id'] = 'api-guided-reference'
        preflight = self.request('/api/authoring/preflight',dict(project=project))
        self.assertTrue(preflight['can_run'],preflight)
        created = self.request('/api/projects',dict(project=project))
        self.assertIsNone(created['run'])
        identity = created['project_id']
        baseline = self.request('/api/run',dict(project_id=identity,revision=1))
        summary = self.request(f'/api/review-workspace?project_id={identity}&revision=1')
        self.assertEqual(summary['counts'],dict(met=10,not_met=0,not_assessed=1,not_run=0))
        self.assertTrue(next(m for m in summary['models'] if m['model_id']=='guided_flight')['has_guided'])
        self.assertEqual(summary['simulations']['canonical_flights'],1)
        self.assertFalse(summary['rocket_reference']['recognized'])
        revised = deepcopy(baseline['project']);revised['inputs']['final_pitch_angle']['value']=1.
        body = dict(project_id=identity,base_revision=1,project=revised)
        impact = self.request('/api/impact',body)['impact']
        self.assertEqual(set(impact['affected_model_ids']),{'guided_flight','atmospheric_load','mount'})
        self.request('/api/revisions',body)
        failed = self.request('/api/run',dict(project_id=identity,revision=2))
        self.assertEqual(failed['run']['review']['findings']['burnout_height']['status'],'not_met')
        self.assertEqual(set(failed['run']['reused_model_ids']),{'propulsion','thermal','launch_gnc'})
        exported = self.request(f'/api/engineering-review-export?project_id={identity}&revision=2')
        review = exported['workspace']['run']['review']
        self.assertEqual(review,failed['run']['review']);self.assertTrue(lifecycle.verify_review(review))
        self.assertEqual(review['findings']['launch_guidance']['status'],'not_assessed')
        self.assertFalse(review['launch_authorization'])
        original = self.request(f'/api/workspace?project_id={identity}&revision=1')
        self.assertEqual(original['run']['review'],baseline['run']['review'])
        self.assertEqual(baseline['run']['live_model_calls'],0)
        self.assertEqual(failed['run']['live_model_calls'],0)


if __name__=='__main__':unittest.main()
