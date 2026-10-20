"""Service authorization, interruption and record isolation, without inference."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from sixd import workflow_evaluation as plans
from sixd.workspace_workflow_evaluation import WorkflowEvaluation
from sixd.workspace_ai import WorkspaceAI, _digest, _encode
from sixd.workspace import WorkspaceStore, WorkspaceError, ConflictError
from test_workspace_ai_api import KEY, offline_factory, write_offline_config


class WorkspaceWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'work');self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name);write_offline_config(self.path)
        self.store=WorkspaceStore(self.path/'workspace.sqlite3')
        self.ai=WorkspaceAI(self.store,self.path,provider_factory=offline_factory)
        self.service=WorkflowEvaluation(self.ai)

    def test_status_connect_and_invalid_ids_never_call_provider_or_create_budget(self):
        self.assertIsNone(self.service.status()['latest'])
        self.ai.connect(KEY)
        status=self.service.status()
        self.assertEqual(status['batch_cap_usd'],3)
        self.assertEqual(status['planned_tasks'],30)
        self.assertNotIn(KEY,json.dumps(status))
        self.assertFalse((self.path/'budget.sqlite3').exists())
        for identity in ['bad','a'*32]:
            with self.assertRaises(WorkspaceError):self.service.get(identity)

    def test_wrong_authorization_rejected_before_plan_or_session(self):
        with patch('sixd.workspace_workflow_evaluation.build_plan',side_effect=AssertionError('No preparation')):
            for amount,allow in [(1.5,True),(3,False),(True,True),(float('nan'),True)]:
                with self.assertRaises(WorkspaceError):self.service.start(allowance_usd=amount,allow_spend=allow)

    def test_missing_connection_rejected_before_record_and_no_fallback(self):
        with patch('sixd.workspace_workflow_evaluation.build_plan',return_value={'cases':[]}), \
             patch('sixd.workspace_workflow_evaluation.workflow_preflight',return_value={'fits':True}):
            with self.assertRaises(ConflictError):self.service.start(allowance_usd=3,allow_spend=True)
        self.assertIsNone(self.service.status()['latest'])
        self.assertFalse((self.path/'budget.sqlite3').exists())

    def test_bad_preflight_prevents_private_session_and_spending(self):
        self.ai.connect(KEY)
        with patch('sixd.workspace_workflow_evaluation.build_plan',return_value={'cases':[]}), \
             patch('sixd.workspace_workflow_evaluation.workflow_preflight',return_value={'fits':False}):
            with self.assertRaises(ConflictError):self.service.start(allowance_usd=3,allow_spend=True)
        self.assertIsNone(self.ai._active)
        self.assertIsNone(self.service.status()['latest'])

    def test_offline_service_uses_separate_records_and_never_changes_selection(self):
        self.ai.connect(KEY)
        report={'schema':plans.REPORT_SCHEMA,'mode':'offline_harness_validation','rows':[],
                'candidates':[],'active_model_changed':False}
        report['report_digest']=_digest(report)
        with patch('sixd.workspace_workflow_evaluation.build_plan',return_value={'cases':[]}), \
             patch('sixd.workspace_workflow_evaluation.workflow_preflight',return_value={'fits':True}), \
             patch('sixd.workspace_workflow_evaluation.run_comparison',return_value=report):
            started=self.service.start(allowance_usd=3,allow_spend=True)
            until=time.monotonic()+5
            while time.monotonic()<until:
                value=self.service.get(started['comparison_id'])
                if value['state'] not in {'queued','running'}:break
                time.sleep(.01)
        self.assertEqual(value['state'],'completed',value.get('error'))
        self.assertEqual(value['reserved_usd'],0)
        self.assertIsNone(self.ai._active)
        self.assertFalse((self.path/'project-assistant-model.json').exists())
        self.assertEqual(self.service.status()['scorecard']['mode'],'offline_harness_validation')

    def test_restart_preserves_partial_record_without_resume(self):
        record={'schema':'sixd.workspace-workflow-evaluation.v1','comparison_id':'f'*32,
                'state':'running','created_at':'2026-10-20','completed_at':None,'rows':[],
                'reserved_usd':.01,'request_reservations':1,'plan':{},'report':None,'error':None}
        with self.ai._db() as db:
            db.execute('INSERT INTO workflow_evaluations VALUES (?,?,?,?,?,?)',
                       ('f'*32,'2026-10-20','running','old-owner',_encode(record),_digest(record)))
        restarted=WorkflowEvaluation(self.ai)
        saved=restarted.get('f'*32)
        self.assertEqual(saved['state'],'interrupted')
        self.assertEqual(saved['reserved_usd'],.01)
        self.assertEqual(saved['rows'],[])
        self.assertIsNone(self.ai._active)


if __name__=='__main__':unittest.main()
