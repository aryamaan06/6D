"""Bounded evaluation orchestration; fixtures are never live quality evidence."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from sixd import workflow_evaluation as evaluation, model_evaluation as old
from sixd.project_investigation import validate_investigation_view
from sixd.workspace_evaluation import BatchBudget
from sixd.providers import ProviderError
from test_model_evaluation import EvidenceFixture


class WorkflowEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch=tempfile.TemporaryDirectory(dir=ROOT/'work')
        cls.plan=evaluation.build_plan(temporary_root=cls.scratch.name)

    @classmethod
    def tearDownClass(cls):
        cls.scratch.cleanup()

    def test_fixed_pack_covers_accuracy_changes_power_and_unsupported_evidence(self):
        self.assertEqual(tuple(c['id'] for c in self.plan['cases']),evaluation.CASE_IDS)
        self.assertEqual(len(self.plan['cases'])*len(self.plan['candidates']),30)
        self.assertTrue(all(c['held_out_variation'] is False for c in self.plan['cases']))
        self.assertTrue(evaluation.validate_plan(self.plan))
        self.assertEqual({c['expected'].get('assessment_status') for c in self.plan['cases']},
                         {None,'accuracy_not_assessed','insufficient_accuracy'})
        self.assertEqual(self.plan['cases'][6]['expected']['requires_recheck'],True)
        self.assertEqual(self.plan['cases'][-1]['expected']['requires_recheck'],False)

    def test_mutated_snapshot_is_rejected_before_provider_creation(self):
        changed=deepcopy(self.plan)
        changed['cases'][0]['view']['project']['inputs']['steps']['value']=16
        with self.assertRaises(ValueError):
            evaluation.run_comparison(changed,lambda *_:self.fail('No provider may be created'))

    def test_current_source_guard_is_distinct_from_historical_consistency(self):
        case=self.plan['cases'][0]
        with patch('sixd.project_investigation._runtime_matches',return_value=False):
            with self.assertRaises(ValueError):
                validate_investigation_view(case['view'],case['requirement_id'])
            self.assertTrue(validate_investigation_view(case['view'],case['requirement_id'],require_current_sources=False))
            self.assertTrue(evaluation.validate_plan(self.plan,require_current_sources=False))
        corrupt=deepcopy(case['view']);corrupt['run']['review']['launch_authorization']=True
        with self.assertRaises(ValueError):
            validate_investigation_view(corrupt,case['requirement_id'],require_current_sources=False)

    def test_identical_cases_run_offline_without_claiming_semantic_or_live_success(self):
        seen={}
        def factory(candidate,case):
            seen.setdefault(case['id'],[]).append(case['case_digest'])
            return EvidenceFixture(candidate)
        report=evaluation.run_comparison(self.plan,factory)
        card=evaluation.scorecard(report)
        self.assertEqual(len(report['rows']),30)
        self.assertTrue(all(len(set(digests))==1 and len(digests)==3 for digests in seen.values()))
        self.assertEqual(report['mode'],'offline_harness_validation')
        self.assertEqual(report['live_calls'],0)
        self.assertFalse(card['active_model_changed'])
        self.assertTrue(all(c['semantic_review']=='pending_independent_human_review' for c in card['candidates']))
        self.assertTrue(all(c['completed']==10 for c in card['candidates']),[(r['case_id'],r.get('receipt',{}).get('error')) for r in report['rows'] if r['state']!='completed'])
        self.assertNotEqual(report['schema'],old.REPORT_SCHEMA)

    def test_failed_candidate_is_stopped_without_retry_or_fallback(self):
        invoked=[]
        def factory(candidate,case):
            invoked.append((candidate['id'],case['id']))
            return EvidenceFixture(candidate,fail=candidate['id']=='nano')
        report=evaluation.run_comparison(self.plan,factory)
        nano=[r for r in report['rows'] if r['candidate_id']=='nano']
        self.assertEqual([r['state'] for r in nano],['failed']+['not_run']*9)
        self.assertEqual(sum(candidate=='nano' for candidate,_ in invoked),1)
        self.assertEqual(len(report['rows']),30)
        self.assertFalse(report['active_model_changed'])
        candidate=evaluation.scorecard(report)['candidates'][0]
        self.assertEqual(candidate['untested'],9)
        self.assertEqual(len(candidate['stopped_cases']),1)
        self.assertEqual(candidate['stopped_cases'][0]['case_id'],'orbit-met')
        self.assertTrue(candidate['stopped_cases'][0]['error_code'])

    def test_batch_ceiling_is_shared_enforced_before_extra_request(self):
        class Shared:
            def __init__(self):self.calls=[]
            def reserve(self,config,amount):self.calls.append(amount)
        shared=Shared();budget=BatchBudget(shared,lambda:None,threading.RLock(),cap_usd=3,max_requests=180)
        budget.reserve(None,2.99)
        with self.assertRaises(ProviderError):budget.reserve(None,.02)
        self.assertEqual(shared.calls,[2.99]);self.assertEqual(budget.count,1)
        with self.assertRaises(ValueError):BatchBudget(shared,lambda:None,threading.RLock(),cap_usd=3.01,max_requests=180)
        with self.assertRaises(ValueError):BatchBudget(shared,lambda:None,threading.RLock(),cap_usd=3,max_requests=181)

    def test_corrupt_scorecard_is_not_exported(self):
        with self.assertRaises(ValueError):evaluation.scorecard({'schema':evaluation.REPORT_SCHEMA,'report_digest':'bad'})


if __name__=='__main__':unittest.main()
