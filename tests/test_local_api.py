from functools import partial
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
import json
import sys
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from sixd.examples import EXAMPLES
from sixd.kernel import audit
from sixd.reporting import save_report
from sixd.server import Handler


class LocalApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT/"work").mkdir(exist_ok=True)
        cls.directory=tempfile.TemporaryDirectory(dir=ROOT/"work")
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),partial(Handler,artifact_directory=cls.directory.name))
        cls.worker=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.worker.start();cls.port=cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.worker.join()
        cls.directory.cleanup()

    def request(self,path,body=None,headers=None):
        connection=HTTPConnection("127.0.0.1",self.port,timeout=5)
        request_headers={"Content-Type":"application/json",**(headers or {})}
        connection.request("GET" if body is None else "POST",path,None if body is None else json.dumps(body),request_headers)
        response=connection.getresponse();raw=response.read();status=response.status
        connection.close()
        return status,json.loads(raw)

    def payload(self):
        example=EXAMPLES["verlet_correct"]
        return {"example_id":example.id,"contract_sha256":example.contract.sha256,"review_accepted":True}

    def test_review_is_required(self):
        request=self.payload();request["review_accepted"]=False
        self.assertEqual(self.request("/api/audit",request)[0],400)

    def test_contract_change_is_rejected(self):
        request=self.payload();request["contract_sha256"]="0"*64
        self.assertEqual(self.request("/api/audit",request)[0],400)

    def test_unregistered_code_input_is_rejected(self):
        request=self.payload();request["code"]="arbitrary uploaded code"
        self.assertEqual(self.request("/api/audit",request)[0],400)

    def test_cross_origin_audit_request_is_rejected(self):
        self.assertEqual(self.request("/api/audit",self.payload(),{"Origin":"https://example.com"})[0],403)

    def test_an_audit_can_be_read_back_with_evidence(self):
        status,value=self.request("/api/audit",self.payload())
        self.assertEqual(status,200)
        report=value["report"]
        self.assertEqual(report["live_model_calls"],0)
        self.assertEqual(report["review"]["mode"],"operator_acknowledged_local_ui")
        status,read=self.request("/api/reports/"+value["record_id"])
        self.assertEqual(status,200)
        self.assertEqual(read["report"],report)
        self.assertTrue(report["not_tested"])

    def test_fixture_investigation_reports_truthful_mode(self):
        status, value = self.request('/api/investigate', self.payload())
        self.assertEqual(status, 200)
        report = value['report']
        self.assertEqual(report['model_mode'], 'fixture')
        self.assertEqual(report['live_model_calls'], 0)
        self.assertEqual(report['investigation']['state'], 'completed')
        self.assertEqual([event['tool'] for event in report['investigation']['trace']],
                         ['check_force', 'check_refinement', 'check_reversibility', 'finish'])

    def test_ui_cannot_request_paid_provider(self):
        request = self.payload(); request['provider'] = 'token-factory'
        self.assertEqual(self.request('/api/investigate', request)[0], 400)

    def test_fixture_requires_reviewed_contract(self):
        request = self.payload(); request['contract_sha256'] = '0' * 64
        self.assertEqual(self.request('/api/investigate', request)[0], 400)

    def comparison_records(self):
        example=EXAMPLES['verlet_correct']
        previous=save_report(audit(example),self.directory.name)['record_id']
        current=save_report(audit(example,contract=example.contract.updated(radius=example.contract.radius*1.1)),
                            self.directory.name)['record_id']
        return {'previous_record_id':previous,'new_record_id':current}

    def test_comparison_preserves_changed_assumption_and_measured_time_step(self):
        request=self.comparison_records()
        status,value=self.request('/api/compare',request)
        self.assertEqual(status,200)
        comparison=value['comparison']
        self.assertEqual(comparison['contract_changes'][0]['field'],'radius')
        self.assertFalse(comparison['candidate_source_changed'])
        self.assertFalse(comparison['verification_sources_changed'])
        refinement=next(c for c in comparison['check_changes'] if c['evidence_id']=='analytic_reference_refinement')
        step=next(c for c in refinement['measurement_changes'] if c['metric']=='finest_dt_seconds')
        self.assertGreater(step['after'],step['before'])
        self.assertEqual(comparison['not_tested_before'],comparison['not_tested_after'])
        self.assertEqual(value['previous_record_id'],request['previous_record_id'])
        self.assertEqual(value['new_record_id'],request['new_record_id'])

    def test_comparison_rejects_path_input_and_unrelated_parameters(self):
        self.assertEqual(self.request('/api/compare',{'previous_record_id':'../source','new_record_id':'../source'})[0],400)
        request=self.comparison_records();request['provider']='token-factory'
        self.assertEqual(self.request('/api/compare',request)[0],400)

    def test_comparison_missing_record_is_reported_without_running_an_audit(self):
        identity='0'*20+'-20261011T000000000000Z'
        self.assertEqual(self.request('/api/compare',{'previous_record_id':identity,'new_record_id':identity})[0],404)

    def test_comparison_rejects_altered_saved_evidence(self):
        request=self.comparison_records()
        path=Path(self.directory.name)/f"{request['new_record_id']}.json"
        report=json.loads(path.read_text(encoding='utf-8'));report['verdict']='defect_likely'
        path.write_text(json.dumps(report),encoding='utf-8')
        status,value=self.request('/api/compare',request)
        self.assertEqual(status,409)
        self.assertNotIn('comparison',value)

    def test_cross_origin_comparison_is_rejected(self):
        self.assertEqual(self.request('/api/compare',self.comparison_records(),{'Origin':'https://example.com'})[0],403)


if __name__=="__main__":unittest.main()
