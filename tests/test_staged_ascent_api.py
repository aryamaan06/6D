"""Actual staged-reference intake, mass events, revision and saved export."""
from copy import deepcopy
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from sixd import lifecycle
from sixd.workspace_server import create_server


class StagedAscentAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(dir=ROOT/'work')
        def forbidden(*args,**kwargs):raise AssertionError('No external provider for staged reference')
        cls.server=create_server(port=0,db_path=Path(cls.temp.name)/'workspace.sqlite3',provider_factory=forbidden,research_transport=forbidden)
        cls.worker=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.worker.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.worker.join();cls.temp.cleanup()
    def request(self,path,body=None):
        c=HTTPConnection('127.0.0.1',self.server.server_port,timeout=60)
        c.request('GET' if body is None else 'POST',path,None if body is None else json.dumps(body),{'Content-Type':'application/json'})
        r=c.getresponse();data=json.loads(r.read());c.close();self.assertEqual(r.status,200,data);return data
    def test_reference_event_accounting_revision_and_export(self):
        catalog=self.request('/api/model-catalog');self.assertEqual(len(catalog['models']),10)
        model=next(m for m in catalog['models'] if m['type']=='staged_ascent')
        self.assertEqual(model['profile']['editor'],'staged_ascent')
        templates=self.request('/api/templates')['templates']
        project=next(t['project'] for t in templates if t['id']=='staged_ascent_review');project['project_id']='api-staged-reference'
        preflight=self.request('/api/authoring/preflight',dict(project=project));self.assertTrue(preflight['can_run'],preflight)
        created=self.request('/api/projects',dict(project=project));self.assertIsNone(created['run'])
        identity=created['project_id'];baseline=self.request('/api/run',dict(project_id=identity,revision=1))
        result=baseline['run']['model_results']['staged_flight'];artifact=result['staged_response'];metrics=result['metrics']
        self.assertEqual([metrics[k]['value'] for k in ('initial_mass','final_mass','propellant_consumed','jettisoned_mass')],[1030,180,700,150])
        before=next(r for r in artifact['samples'] if r['event']=='separation_before')
        after=next(r for r in artifact['samples'] if r['event']=='separation_after')
        self.assertEqual(before['mass_kg']-after['mass_kg'],150)
        self.assertEqual([before[k] for k in ('x_m','y_m','vx_m_s','vy_m_s','time_s')],[after[k] for k in ('x_m','y_m','vx_m_s','vy_m_s','time_s')])
        summary=self.request(f'/api/review-workspace?project_id={identity}&revision=1')
        self.assertEqual(summary['counts'],dict(met=8,not_met=3,not_assessed=1,not_run=0))
        self.assertTrue(next(m for m in summary['models'] if m['model_id']=='staged_flight')['has_staged'])
        revised=deepcopy(baseline['project']);revised['inputs']['s2_specific_impulse']['value']=220
        body=dict(project_id=identity,base_revision=1,project=revised)
        impact=self.request('/api/impact',body)['impact'];self.assertEqual(set(impact['affected_model_ids']),{'staged_flight','atmospheric_load','mount'})
        self.request('/api/revisions',body)
        self.assertIsNone(self.request(f'/api/workspace?project_id={identity}&revision=2')['run'])
        changed=self.request('/api/run',dict(project_id=identity,revision=2))
        self.assertEqual(changed['run']['review']['findings']['burnout_height']['status'],'not_met')
        self.assertEqual(changed['run']['model_results']['thermal'],baseline['run']['model_results']['thermal'])
        exported=self.request(f'/api/engineering-review-export?project_id={identity}&revision=2')
        self.assertEqual(exported['workspace']['run']['review'],changed['run']['review']);self.assertTrue(lifecycle.verify_review(exported['workspace']['run']['review']))
        self.assertFalse(changed['run']['review']['launch_authorization'])
        self.assertEqual(self.request(f'/api/workspace?project_id={identity}&revision=1')['run']['review'],baseline['run']['review'])
        self.assertEqual(changed['run']['live_model_calls'],0)


if __name__=='__main__':unittest.main()
