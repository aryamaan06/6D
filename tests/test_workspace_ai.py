"""Project-assistant job lifecycle with an offline provider and isolated ledgers.

No test uses the founder's configuration, credential, ledger, or a network.
"""
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd.providers import BudgetLedger, LiveConfig, ProviderError, Turn
from sixd.workspace import ConflictError, WorkspaceError, WorkspaceStore
from sixd.workspace_ai import JobBudget, WorkspaceAI


TEST_KEY = "synthetic-private-project-key-for-offline-tests"


class ScriptedProvider:
    """Select real bounded engine actions; use only a temporary shared budget."""
    mode = "offline_transport_fixture"
    model = "nvidia/offline-nemotron-project-tests"

    def __init__(self, config, ledger, key, *, fail_on=None, block_on=None,
                 entered=None, release=None, reservation=.003, summary=None):
        self.config, self.ledger, self._key = config, ledger, key
        self.fail_on, self.block_on = fail_on, block_on
        self.entered, self.release = entered, release
        self.reservation = reservation
        self.summary = summary or "The recorded bounded finding and its assumptions require engineering review."
        self.request_attempts = 0
        self.histories = []

    def complete(self, messages, tools):
        ordinal = self.request_attempts + 1
        if ordinal == self.block_on:
            self.entered.set()
            if not self.release.wait(5):
                raise AssertionError("Offline test synchronization timed out.")
        # Match production ordering: session/budget guard precedes transport.
        self.ledger.reserve(self.config, self.reservation)
        self.request_attempts += 1
        self.histories.append(deepcopy(messages))
        if ordinal == self.fail_on:
            raise ProviderError("Controlled offline provider failure; no automatic retry.")
        available = {item["function"]["name"]: item for item in tools}
        action = next(name for name in ("read_requirement", "read_model", "recheck_model", "finish")
                      if name in available)
        arguments = {}
        if action == "finish":
            arguments = {"evidence_ids": available[action]["function"]["parameters"]["properties"]
                         ["evidence_ids"]["items"]["enum"], "summary": self.summary}
        return Turn({"role": "assistant", "content": None, "tool_calls": [{
            "id": "offline-project-" + str(ordinal), "type": "function", "function": {
                "name": action, "arguments": json.dumps(arguments),
            },
        }]}, {"prompt_tokens": 10, "completion_tokens": 10}, response_meta={
            "finish_reason": "stop", "response_format": "native_tool_call", "call_id_origin": "provider"})


class WorkspaceAIJobsTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / "work"
        scratch.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temporary.cleanup)
        self.local = Path(temporary.name)
        self.config = LiveConfig("https://api.tokenfactory.nebius.com/v1/",
            ScriptedProvider.model, "offline-project-tests-only", 5.0, .06, .24,
            2048, 45, "native_no_thinking", "forced_action_v1")
        self.write_config()
        self.path = self.local / "workspace.sqlite3"
        self.store = WorkspaceStore(self.path)
        self.project_id = self.store.ensure_default()
        self.providers = []
        self.options = {}
        environment = patch.dict("os.environ", {"NEBIUS_API_KEY": ""})
        environment.start()
        self.addCleanup(environment.stop)
        self.manager = WorkspaceAI(self.store, self.local, provider_factory=self.factory)
        # Parent integration edits cannot masquerade as a runtime source change
        # halfway through a bounded asynchronous test. A separate test below
        # deliberately exercises the real guard's rejection branch.
        sources = patch.object(self.manager, "_sources", return_value=self.manager._runtime)
        sources.start()
        self.addCleanup(sources.stop)

    def write_config(self, **changes):
        data = {**self.config.__dict__, "account_verified": True,
                "model_license_reviewed": True, "spend_approved": True, **changes}
        (self.local / "token-factory.json").write_text(json.dumps(data), encoding="utf-8")

    def factory(self, config, ledger, key):
        provider = ScriptedProvider(config, ledger, key, **self.options)
        self.providers.append(provider)
        return provider

    def connect(self):
        return self.manager.connect(TEST_KEY)

    def start(self, requirement="thermal_limit", question="Explain the selected saved finding.", revision=1):
        return self.manager.start(self.project_id, revision, requirement, question)

    def wait(self, identity):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            record = self.manager.get(identity)
            if record["state"] not in {"queued", "running"} and self.manager._active is None:
                return record
            threading.Event().wait(.01)
        self.fail("Offline project job did not settle.")

    def reserved(self):
        path = self.local / "budget.sqlite3"
        if not path.exists():
            return 0
        with closing(sqlite3.connect(path)) as db:
            row = db.execute("SELECT id,cap,reserved FROM budget").fetchone()
        self.assertEqual(row[:2], (self.config.approval_id, 5.0))
        return row[2]

    def assert_private(self, *public):
        self.assertNotIn(TEST_KEY, json.dumps(public))
        # SQLite records and config must not contain a credential after close.
        for path in self.local.iterdir():
            if path.is_file():
                self.assertNotIn(TEST_KEY.encode(), path.read_bytes(), str(path))

    def test_connect_status_disconnect_are_private_and_make_no_reservations(self):
        self.assertFalse(self.manager.status()["configured"])
        connected = self.connect()
        self.assertTrue(connected["configured"])
        self.assertTrue(connected["key_present"])
        self.assertFalse(connected["live_validated"])
        self.assertEqual(connected["max_job_requests"], 6)
        self.assertEqual(connected["max_job_reservation_usd"], .10)
        disconnected = self.manager.disconnect()
        self.assertFalse(disconnected["key_present"])
        self.assertEqual(self.providers, [])
        self.assertFalse((self.local / "budget.sqlite3").exists())
        self.assert_private(connected, disconnected)
        reopened = WorkspaceAI(self.store, self.local, provider_factory=self.factory)
        self.assertFalse(reopened.status()["key_present"])

    def test_existing_cumulative_reservations_survive_connect_status_and_reopen(self):
        BudgetLedger(self.local / "budget.sqlite3").reserve(self.config, 1.25)
        before = (self.local / "budget.sqlite3").read_bytes()
        status = self.connect()
        self.assertEqual(status["budget"]["reserved_usd"], 1.25)
        self.assertEqual(status["budget"]["remaining_usd"], 3.75)
        self.manager.disconnect()
        reopened = WorkspaceAI(self.store, self.local, provider_factory=self.factory)
        self.assertEqual(reopened.status()["budget"]["reserved_usd"], 1.25)
        self.assertEqual((self.local / "budget.sqlite3").read_bytes(), before)
        self.assertEqual(self.providers, [])

    def test_invalid_key_and_configuration_do_not_connect_or_change_allowance(self):
        for key in (None, "short", TEST_KEY + "\n", TEST_KEY + " ", "a" * 8193):
            with self.subTest(key_type=type(key).__name__), self.assertRaises(WorkspaceError):
                self.manager.connect(key)
        self.write_config(spend_cap_usd=30.0)
        with self.assertRaisesRegex(ProviderError, "approved cumulative"):
            self.connect()
        self.assertFalse(self.manager.status()["key_present"])
        self.assertEqual(self.providers, [])
        self.assertFalse((self.local / "budget.sqlite3").exists())

    def test_mismatched_approval_status_does_not_reset_existing_ledger(self):
        BudgetLedger(self.local / "budget.sqlite3").reserve(self.config, .5)
        self.write_config(approval_id="silently-replaced-approval")
        before = (self.local / "budget.sqlite3").read_bytes()
        status = self.connect()
        self.assertFalse(status["configured"])
        self.assertIsNone(status["budget"])
        with self.assertRaisesRegex(ProviderError, "operator review"):
            self.start()
        self.assertEqual((self.local / "budget.sqlite3").read_bytes(), before)
        self.assertEqual(self.providers, [])

    def test_missing_key_unreviewed_revision_and_invalid_scope_make_no_jobs(self):
        with self.assertRaisesRegex(ConflictError, "Connect Nebius"):
            self.start()
        self.connect()
        for requirement in ("missing", "", None):
            with self.subTest(requirement=requirement), self.assertRaises(WorkspaceError):
                self.start(requirement=requirement)
        for question in ("", " ", "a" * 2001, None):
            with self.subTest(question_type=type(question).__name__), self.assertRaises(WorkspaceError):
                self.start(question=question)
        project = self.store.get(self.project_id)["project"]
        project["inputs"]["heat_input"]["value"] = 700
        self.store.save_revision(self.project_id, 1, project)
        with self.assertRaisesRegex(ConflictError, "Run checks"):
            self.start(revision=2)
        self.assertEqual(self.manager.list(self.project_id, 1), [])
        self.assertEqual(self.providers, [])

    def test_credential_in_question_is_rejected_before_any_record_or_request(self):
        self.connect()
        with self.assertRaises(WorkspaceError):
            self.start(question="Investigate " + TEST_KEY)
        self.assertEqual(self.manager.list(self.project_id, 1), [])
        self.assertEqual(self.providers, [])
        self.assert_private(self.manager.status())

    def test_completed_job_preserves_actual_findings_and_reopens_as_offline_history(self):
        self.connect()
        before = self.store.get(self.project_id)
        queued = self.start()
        self.assertEqual(queued["state"], "queued")
        record = self.wait(queued["investigation_id"])
        self.assertEqual(record["state"], "completed", record.get("error"))
        self.assertEqual(record["request_attempts"], 4)
        self.assertEqual(record["live_model_calls"], 0)
        self.assertEqual(record["provider_mode"], "offline_transport_fixture")
        self.assertEqual([event["action"] for event in record["events"]],
                         ["read_requirement", "read_model", "recheck_model", "finish"])
        self.assertEqual(record["canonical_finding"], before["run"]["review"]["findings"]["thermal_limit"])
        self.assertEqual(record["citations"], sorted(record["evidence"]))
        self.assertTrue(record["evidence"]["recheck:thermal"]["matches_saved_result"])
        self.assertAlmostEqual(self.reserved(), .012)
        self.assertEqual(self.store.get(self.project_id), before)
        reopened = WorkspaceAI(WorkspaceStore(self.path), self.local, provider_factory=self.factory)
        self.assertEqual(reopened.get(record["investigation_id"]), record)
        self.assertEqual(reopened.list(self.project_id, 1, "thermal_limit"), [record])
        self.assertEqual(reopened.list(self.project_id, 1, "control_tracking"), [])
        self.assertFalse(reopened.status()["live_validated"])
        self.assert_private(queued, record, reopened.status())

    def test_unsupported_coverage_cannot_become_an_engineering_pass(self):
        self.connect()
        record = self.wait(self.start(requirement="control_tracking")["investigation_id"])
        self.assertEqual(record["state"], "completed")
        self.assertEqual(record["finding_status"], "not_assessed")
        self.assertNotIn("recheck_model", [event["action"] for event in record["events"]])
        self.assertEqual(record["request_attempts"], 3)
        self.assertFalse(record["launch_authorization"])
        self.assertEqual(self.store.get(self.project_id)["run"]["review"]["findings"]
                         ["control_tracking"]["status"], "not_assessed")

    def test_live_validation_badge_requires_matching_model_and_provider_settings(self):
        self.connect()
        offline = self.wait(self.start()["investigation_id"])
        self.assertFalse(self.manager.status()["live_validated"])
        # This is a fabricated STATUS fixture in an isolated test DB, never a
        # provider result or a claim that any live request happened in this test.
        crafted_status_receipt = deepcopy(offline)
        crafted_status_receipt.update(provider_mode="live_token_factory", live_model_calls=4,
            model=self.config.model, agent_sources=self.manager._runtime,
            provider_settings={name: getattr(self.config, name) for name in (
                "base_url", "model", "inference_profile", "selection_protocol", "max_output_tokens",
                "request_timeout_seconds", "input_usd_per_million_ceiling", "output_usd_per_million_ceiling")})
        with self.manager._db() as db:
            self.manager._write(db, crafted_status_receipt)
        self.assertTrue(self.manager.status()["live_validated"])
        for changes in ({"model": "nvidia/offline-other-nemotron-test"},
                        {"max_output_tokens": 4096},
                        {"request_timeout_seconds": 90},
                        {"input_usd_per_million_ceiling": .07},
                        {"base_url": "https://api.tokenfactory.us-central1.nebius.com/v1/"},
                        {"inference_profile": "tool_sampling"}):
            with self.subTest(changes=changes):
                self.write_config(**changes)
                self.assertFalse(self.manager.status()["live_validated"])
        self.write_config()
        self.assertTrue(self.manager.status()["live_validated"])
        # A legacy receipt without the bound settings cannot validate a new path.
        del crafted_status_receipt["provider_settings"]
        with self.manager._db() as db:
            self.manager._write(db, crafted_status_receipt)
        self.assertFalse(self.manager.status()["live_validated"])
        self.assertEqual(len(self.providers), 1)
        self.assertEqual(self.providers[0].mode, "offline_transport_fixture")

    def test_failed_provider_retains_partial_evidence_and_reservation_without_retry(self):
        self.options["fail_on"] = 2
        self.connect()
        record = self.wait(self.start()["investigation_id"])
        self.assertEqual(record["state"], "failed")
        self.assertEqual(record["request_attempts"], 2)
        self.assertEqual([event["action"] for event in record["events"]], ["read_requirement"])
        self.assertEqual(list(record["evidence"]), ["requirement:thermal_limit"])
        self.assertEqual(record["summary"], "")
        self.assertEqual(record["citations"], [])
        self.assertAlmostEqual(self.reserved(), .006)
        self.assertEqual(len(self.providers), 1)
        reopened = WorkspaceAI(self.store, self.local, provider_factory=self.factory)
        self.assertEqual(reopened.get(record["investigation_id"]), record)
        self.assertEqual(len(self.providers), 1)

    def test_factory_exception_never_persists_arbitrary_private_text(self):
        marker = "synthetic-private-remote-body-not-the-api-key"
        for code in ("provider_transport_error", None):
            with self.subTest(code=code):
                def fail_factory(config, ledger, key):
                    raise ProviderError(marker, code=code)
                self.manager._factory = fail_factory
                self.connect()
                record = self.wait(self.start()["investigation_id"])
                self.assertEqual(record["state"], "failed")
                self.assertNotIn(marker, json.dumps(record))
                self.assertEqual(record["error_code"], code or "provider_or_action_error")
                self.assertTrue(record["error_next_step"])
                self.assertEqual(record["request_reservations"], 0)

    def test_model_echo_of_private_key_is_rejected_without_persisting_it(self):
        self.options["summary"] = "Private material must be rejected: " + TEST_KEY
        self.connect()
        record = self.wait(self.start()["investigation_id"])
        self.assertEqual(record["state"], "failed")
        self.assertEqual(record["request_attempts"], 4)
        self.assertEqual(record["summary"], "")
        self.assertEqual(record["citations"], [])
        self.assertEqual([event["action"] for event in record["events"]],
                         ["read_requirement", "read_model", "recheck_model"])
        self.assert_private(record, self.manager.status())

    def test_separate_jobs_add_to_the_same_approved_reservation_total(self):
        BudgetLedger(self.local / "budget.sqlite3").reserve(self.config, 1.25)
        self.connect()
        first = self.wait(self.start()["investigation_id"])
        second = self.wait(self.start(requirement="control_tracking")["investigation_id"])
        self.assertEqual((first["state"], second["state"]), ("completed", "completed"))
        self.assertEqual((first["request_reservations"], second["request_reservations"]), (4, 3))
        self.assertAlmostEqual(self.reserved(), 1.271)
        self.assertAlmostEqual(self.manager.status()["budget"]["remaining_usd"], 3.729)
        reopened = WorkspaceAI(self.store, self.local, provider_factory=self.factory)
        self.assertEqual(reopened.get(first["investigation_id"]), first)
        self.assertEqual(reopened.get(second["investigation_id"]), second)
        self.assertEqual(len(self.providers), 2)

    def test_job_reservation_ceiling_blocks_before_another_attempt(self):
        self.options["reservation"] = .03
        self.connect()
        record = self.wait(self.start()["investigation_id"])
        self.assertEqual(record["state"], "failed")
        self.assertEqual(record["request_attempts"], 3)
        self.assertEqual(record["request_reservations"], 3)
        self.assertAlmostEqual(record["reserved_usd"], .09)
        self.assertAlmostEqual(self.reserved(), .09)

    def test_near_exhausted_shared_allowance_blocks_before_transport_without_refund(self):
        BudgetLedger(self.local / "budget.sqlite3").reserve(self.config, 4.9995)
        self.connect()
        record = self.wait(self.start()["investigation_id"])
        self.assertEqual(record["state"], "failed")
        self.assertEqual(record["request_attempts"], 0)
        self.assertEqual(record["request_reservations"], 0)
        self.assertAlmostEqual(self.reserved(), 4.9995)
        BudgetLedger(self.local / "budget.sqlite3").reserve(self.config, .0005)
        with self.assertRaisesRegex(ConflictError, "exhausted"):
            self.start()
        self.assertEqual(len(self.providers), 1)

    def blocking_provider(self, ordinal):
        entered, release = threading.Event(), threading.Event()
        self.options.update(block_on=ordinal, entered=entered, release=release)
        self.addCleanup(release.set)
        self.connect()
        queued = self.start()
        self.assertTrue(entered.wait(3), "Offline provider did not enter controlled block.")
        return queued, release

    def test_active_job_rejects_duplicate_and_connection_change(self):
        queued, release = self.blocking_provider(1)
        try:
            running = self.manager.get(queued["investigation_id"])
            self.assertEqual(running["state"], "running")
            with self.assertRaisesRegex(ConflictError, "already running"):
                self.start()
            with self.assertRaisesRegex(ConflictError, "active investigation"):
                self.manager.connect("another-synthetic-private-project-key")
            self.assertEqual(len(self.manager.list(self.project_id, 1)), 1)
        finally:
            release.set()
        self.assertEqual(self.wait(queued["investigation_id"])["state"], "completed")

    def test_disconnect_stops_next_reservation_and_keeps_completed_action(self):
        queued, release = self.blocking_provider(2)
        before = self.reserved()
        self.manager.disconnect()
        release.set()
        record = self.wait(queued["investigation_id"])
        self.assertEqual(record["state"], "failed")
        self.assertEqual(record["request_attempts"], 1)
        self.assertEqual([event["action"] for event in record["events"]], ["read_requirement"])
        self.assertIn("requirement:thermal_limit", record["evidence"])
        self.assertEqual(self.reserved(), before)

    def test_restart_marks_unfinished_failed_and_old_owner_cannot_overwrite_it(self):
        queued, release = self.blocking_provider(2)
        identity = queued["investigation_id"]
        restarted = WorkspaceAI(self.store, self.local, provider_factory=self.factory)
        interrupted = restarted.get(identity)
        self.assertEqual(interrupted["state"], "failed")
        self.assertIn("server restarted", interrupted["error"])
        self.assertEqual([event["action"] for event in interrupted["events"]], ["read_requirement"])
        self.assertIn("requirement:thermal_limit", interrupted["evidence"])
        self.assertEqual(interrupted["evidence"]["requirement:thermal_limit"]["finding"],
                         self.store.get(self.project_id)["run"]["review"]["findings"]["thermal_limit"])
        self.assertEqual(interrupted["request_attempts"], 1)
        prior_reservations = self.reserved()
        release.set()
        self.wait(identity)
        self.assertEqual(restarted.get(identity), interrupted)
        self.assertEqual(self.reserved(), prior_reservations)
        self.assertEqual(len(self.providers), 1)

    def test_source_change_blocks_before_factory_or_job_creation(self):
        self.connect()
        changed = {**self.manager._runtime, "project_investigation.py": "a" * 64}
        with patch.object(self.manager, "_sources", return_value=changed):
            with self.assertRaisesRegex(ConflictError, "sources changed"):
                self.start()
        self.assertEqual(self.providers, [])
        self.assertEqual(self.manager.list(self.project_id, 1), [])

    def test_source_change_during_job_stops_next_reservation(self):
        queued, release = self.blocking_provider(2)
        changed = {**self.manager._runtime, "project_investigation.py": "b" * 64}
        before = self.reserved()
        with patch.object(self.manager, "_sources", return_value=changed):
            release.set()
            record = self.wait(queued["investigation_id"])
        self.assertEqual(record["state"], "failed")
        self.assertEqual(record["request_attempts"], 1)
        self.assertEqual(self.reserved(), before)
        self.assertIn("requirement:thermal_limit", record["evidence"])

    def test_tampered_investigation_record_is_not_returned(self):
        self.connect()
        record = self.wait(self.start()["investigation_id"])
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE project_investigations SET state='running' WHERE investigation_id=?",
                       (record["investigation_id"],))
        with self.assertRaisesRegex(WorkspaceError, "inconsistent"):
            self.manager.get(record["investigation_id"])

    def test_invalid_ids_are_controlled_and_do_not_touch_provider(self):
        for identity in (None, "../../.local", "a" * 31, "g" * 32, "a" * 33):
            with self.subTest(identity=identity), self.assertRaises(WorkspaceError):
                self.manager.get(identity)
        with self.assertRaisesRegex(WorkspaceError, "not found"):
            self.manager.get("a" * 32)
        self.assertEqual(self.providers, [])


class JobBudgetTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / "work"
        scratch.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "budget.sqlite3"
        self.config = LiveConfig("https://api.tokenfactory.nebius.com/v1/",
            ScriptedProvider.model, "offline-reservation-ceiling-tests-only", 5.0, .06, .24)
        self.checks = []
        self.budget = JobBudget(BudgetLedger(self.path), check_session=lambda: self.checks.append(True))

    def test_six_request_ceiling_remains_below_shared_cap(self):
        for _ in range(6):
            self.budget.reserve(self.config, .001)
        with self.assertRaisesRegex(ProviderError, "ceiling"):
            self.budget.reserve(self.config, .001)
        self.assertEqual(self.budget.count, 6)
        self.assertAlmostEqual(self.budget.reserved, .006)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertAlmostEqual(db.execute("SELECT reserved FROM budget").fetchone()[0], .006)

    def test_invalid_reservations_never_create_a_ledger(self):
        for amount in (0, -1, True, None, "0.001", float("nan"), float("inf")):
            with self.subTest(amount_type=type(amount).__name__), self.assertRaises(ProviderError):
                self.budget.reserve(self.config, amount)
        self.assertEqual(self.budget.count, 0)
        self.assertFalse(self.path.exists())

    def test_session_check_precedes_shared_reservation(self):
        def stopped():
            raise ProviderError("Private connection changed.")
        budget = JobBudget(BudgetLedger(self.path), check_session=stopped)
        with self.assertRaisesRegex(ProviderError, "connection changed"):
            budget.reserve(self.config, .001)
        self.assertFalse(self.path.exists())
        self.assertEqual(budget.count, 0)


if __name__ == "__main__":
    unittest.main()
