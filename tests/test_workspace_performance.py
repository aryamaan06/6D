"""Bounded receipt work without trusting mutable storage or caller objects."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import lifecycle, workspace
from sixd.project_examples import example_projects
from sixd.workspace import WorkspaceError, WorkspaceStore


class WorkspacePerformanceTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "work").mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / "work")
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "workspace.sqlite3"
        self.store = WorkspaceStore(self.path)
        project = example_projects()["orbital_review"]
        project["inputs"]["steps"]["value"] = 64
        project["inputs"]["duration_s"]["value"] = 240
        self.pid = project["project_id"]
        self.store.create_project(project)
        self.first = self.store.run(self.pid, 1)

    def history(self, count):
        view = self.store.get(self.pid)
        while view["revision"] < count:
            project = view["project"]
            # Requirement changes preserve the actual numerical trajectory and
            # its originating execution; these are separate retained receipts.
            project["inputs"]["maximum_final_radius"]["value"] += 10
            self.store.save_revision(self.pid, view["revision"], project)
            view = self.store.run(self.pid, view["revision"] + 1)
        return view

    def rewrite(self, run_id, change, *, rehash=True):
        with self.store._connect(write=True) as connection:
            row = connection.execute("SELECT receipt,digest FROM runs WHERE run_id=?", (run_id,)).fetchone()
            receipt = json.loads(row["receipt"])
            change(receipt)
            connection.execute("UPDATE runs SET receipt=?,digest=? WHERE run_id=?",
                (workspace._encode(receipt), workspace._digest(receipt) if rehash else row["digest"], run_id))

    def test_cold_selected_verification_is_bounded_as_trajectory_history_grows(self):
        counts = []
        for size in (2, 9):
            self.history(size)
            cold = WorkspaceStore(self.path)
            with patch.object(lifecycle, "verify_review", wraps=lifecycle.verify_review) as verify:
                view = cold.get(self.pid)
            counts.append(verify.call_count)
            self.assertEqual(view["run"]["revision"], size)
            self.assertEqual(view["prior_run"]["revision"], size - 1)
            self.assertEqual(len(view["revisions"]), size)
            self.assertTrue(all(row["has_current_run"] for row in view["revisions"]))
            with patch.object(lifecycle, "verify_review", wraps=lifecycle.verify_review) as warm:
                self.assertEqual(cold.get(self.pid), view)
            self.assertEqual(warm.call_count, 0)
        self.assertEqual(counts, [4, 4])  # two selected receipts + one comparison

    def test_save_and_repeated_run_do_not_verify_all_older_trajectories(self):
        latest = self.history(8)
        cold = WorkspaceStore(self.path)
        draft = deepcopy(latest["project"])
        draft["inputs"]["maximum_final_radius"]["value"] += 10
        with patch.object(lifecycle, "verify_review", wraps=lifecycle.verify_review) as verify:
            pending = cold.save_revision(self.pid, 8, draft)
        self.assertEqual(verify.call_count, 1)
        self.assertIsNone(pending["run"])
        self.assertEqual(pending["prior_run"]["revision"], 8)
        with patch.object(lifecycle, "verify_review", wraps=lifecycle.verify_review) as verify:
            result = cold.run(self.pid, 9)
        self.assertLessEqual(verify.call_count, 3)
        with patch.object(lifecycle, "verify_review", wraps=lifecycle.verify_review) as verify:
            repeated = cold.run(self.pid, 9)
        self.assertLessEqual(verify.call_count, 3)
        self.assertEqual(repeated["run"]["executed_model_ids"], [])
        self.assertEqual(repeated["prior_run"]["revision"], 8)
        self.assertEqual(repeated["comparison"]["from_revision"], "8")
        self.assertEqual(repeated["run"]["model_origins"]["orbit"]["run_id"], self.first["run"]["run_id"])
        self.assertEqual(result["run"]["model_results"]["orbit"], self.first["run"]["model_results"]["orbit"])
        with self.store._connect() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM runs").fetchone()[0], 10)
        # Earlier selection keeps its own nearest reviewed ancestor even when
        # later repeated runs exist; all revision freshness flags remain present.
        earlier = cold.get(self.pid, 3)
        self.assertEqual(earlier["run"]["revision"], 3)
        self.assertEqual(earlier["prior_run"]["revision"], 2)
        self.assertEqual(len(earlier["revisions"]), 9)

    def test_changed_payload_with_unchanged_database_digest_cannot_hit_cache(self):
        run_id = self.first["run"]["run_id"]
        self.store.get(self.pid)
        self.rewrite(run_id, lambda receipt: receipt.update(live_model_calls=99), rehash=False)
        with self.assertRaisesRegex(WorkspaceError, "digest"):
            self.store.get(self.pid)

    def test_rehashed_invalid_selected_numerical_payload_is_verified_again(self):
        run_id = self.first["run"]["run_id"]
        self.store.get(self.pid)
        def change(receipt):
            receipt["review"]["evidence"]["orbit"]["simulation"]["samples"][0]["radius_m"] += 100
            receipt["review"]["digest"] = workspace._digest({key: value for key, value in receipt["review"].items() if key != "digest"})
        self.rewrite(run_id, change)
        with self.assertRaisesRegex(WorkspaceError, "receipt is inconsistent"):
            self.store.get(self.pid)

    def test_unselected_historical_bytes_origins_sources_and_snapshots_are_checked(self):
        self.history(4)
        run_id = self.first["run"]["run_id"]
        with self.store._connect() as connection:
            original = json.loads(connection.execute("SELECT receipt FROM runs WHERE run_id=?", (run_id,)).fetchone()[0])
        changes = [
            (lambda receipt: receipt.update(run_id="invented-run"), True),
            (lambda receipt: receipt["review"].update(schema="invented-review"), True),
            (lambda receipt: receipt["review"]["findings"]["orbit_final_radius"].update(status="invented-status"), True),
            (lambda receipt: receipt["model_origins"]["orbit"].update(revision=99), True),
            (lambda receipt: receipt["review"]["verification_sources"].update({"simulation.py": "invalid"}), True),
            (lambda receipt: receipt["review"]["project"]["inputs"]["duration_s"].update(value=1), True),
            (lambda receipt: receipt.update(live_model_calls=99), False),
        ]
        for change, rehash in changes:
            with self.subTest(change=change):
                self.rewrite(run_id, lambda receipt: (receipt.clear(), receipt.update(deepcopy(original))))
                self.store.get(self.pid)  # refill metadata for the restored bytes
                self.rewrite(run_id, change, rehash=rehash)
                with self.assertRaises(WorkspaceError):
                    self.store.get(self.pid)

    def test_source_and_adapter_freshness_invalidate_cached_verification(self):
        self.history(3)
        original = self.store.get(self.pid)
        sources = deepcopy(original["run"]["review"]["verification_sources"])
        sources["engineering.py"] = "a" * 64
        with patch.object(lifecycle, "_verification_sources", return_value=sources), \
                patch.object(lifecycle, "verify_review", wraps=lifecycle.verify_review) as verify:
            stale = self.store.get(self.pid)
            self.assertIsNone(stale["run"])
            self.assertTrue(stale["prior_run"]["stale"])
            self.assertEqual(verify.call_count, 1)
            self.assertFalse(any(row["has_current_run"] for row in stale["revisions"]))
        with patch.dict(workspace.MODEL_VERSIONS, {"orbital_trajectory": "changed-test-version"}), \
                patch.object(lifecycle, "verify_review", wraps=lifecycle.verify_review) as verify:
            stale = self.store.get(self.pid)
            self.assertIsNone(stale["run"])
            self.assertTrue(stale["prior_run"]["stale"])
            self.assertEqual(verify.call_count, 1)
        self.assertEqual(self.store.get(self.pid), original)

    def test_callers_cannot_mutate_cached_nested_samples_projects_origins_or_comparison(self):
        original = self.history(2)
        exposed = self.store.get(self.pid)
        exposed["run"]["review"]["evidence"]["orbit"]["simulation"]["samples"][0]["position_m"][0] = 0
        exposed["run"]["model_results"]["orbit"]["simulation"]["samples"].clear()
        exposed["prior_run"]["review"]["project"]["inputs"]["duration_s"]["source"] = "caller mutation"
        exposed["run"]["model_origins"]["orbit"]["run_id"] = "caller mutation"
        exposed["comparison"]["changed_inputs"].clear()
        exposed["project"]["inputs"].clear()
        self.assertEqual(self.store.get(self.pid), original)

    def test_cache_limits_bytes_and_entries_and_oversized_receipts_still_verify(self):
        self.history(10)
        for cache in (self.store._verified_receipts, self.store._run_summaries, self.store._comparisons):
            self.assertLessEqual(len(cache.values), cache.entries)
            self.assertLessEqual(cache.size, cache.byte_limit)
            self.assertTrue(all(isinstance(value[0], str) for value in cache.values.values()))
        self.store._verified_receipts = workspace._SerializedCache(2, 1)
        with patch.object(lifecycle, "verify_review", wraps=lifecycle.verify_review) as verify:
            self.store.get(self.pid)
            self.store.get(self.pid)
        self.assertEqual(verify.call_count, 4)
        self.assertEqual(self.store._verified_receipts.size, 0)

    def test_metadata_and_selected_fetch_share_snapshot_during_external_update(self):
        original = self.history(2)
        # WAL lets the independent writer commit while the pinned reader keeps
        # its original snapshot, making this race deterministic rather than
        # depending on rollback-journal writer timing.
        with self.store._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
        selected = self.store._selected_receipt
        edited = False
        def update_between_metadata_and_selected(connection, metadata, snapshots, fingerprint):
            nonlocal edited
            self.assertTrue(connection.in_transaction)
            if not edited:
                edited = True
                self.rewrite(original["run"]["run_id"],
                             lambda receipt: receipt.update(live_model_calls=99), rehash=False)
            return selected(connection, metadata, snapshots, fingerprint)
        with patch.object(self.store, "_selected_receipt", side_effect=update_between_metadata_and_selected):
            self.assertEqual(self.store.get(self.pid), original)
        self.assertTrue(edited)
        with self.assertRaisesRegex(WorkspaceError, "digest"):
            self.store.get(self.pid)

    def test_noncanonical_json_retains_canonical_digest_validation(self):
        self.history(3)
        original = self.store.get(self.pid)
        with self.store._connect(write=True) as connection:
            for row in connection.execute("SELECT sequence,receipt FROM runs").fetchall():
                receipt = json.loads(row["receipt"])
                # Reorder the outer map and add whitespace, preserving content
                # and the existing canonical application digest.
                receipt = dict(reversed(list(receipt.items())))
                connection.execute("UPDATE runs SET receipt=? WHERE sequence=?",
                                   (json.dumps(receipt, indent=2), row["sequence"]))
        self.assertEqual(self.store.get(self.pid), original)
        self.assertEqual(WorkspaceStore(self.path).get(self.pid), original)

    def test_old_numerical_consistency_is_lazy_but_checked_when_selected(self):
        self.history(4)
        def change(receipt):
            receipt["review"]["evidence"]["orbit"]["simulation"]["samples"][0]["radius_m"] += 100
            receipt["review"]["digest"] = workspace._digest({key: value for key, value in receipt["review"].items() if key != "digest"})
        self.rewrite(self.first["run"]["run_id"], change)
        # The ordinary current view checks all history bytes and metadata, then
        # verifies the two displayed trajectories. It does not certify every
        # old trajectory's internal numerical relationships on every read.
        self.assertEqual(self.store.get(self.pid)["run"]["revision"], 4)
        with self.assertRaisesRegex(WorkspaceError, "receipt is inconsistent"):
            self.store.get(self.pid, 1)

    def test_sqlite_without_json_projection_uses_safe_full_validation(self):
        self.history(3)
        cold = WorkspaceStore(self.path)
        cold._has_json_projection = False
        with patch.object(lifecycle, "verify_review", wraps=lifecycle.verify_review) as verify:
            view = cold.get(self.pid)
        self.assertEqual(view["revision"], 3)
        self.assertGreaterEqual(verify.call_count, 3)
        self.assertEqual(view, self.store.get(self.pid))


if __name__ == "__main__":
    unittest.main()
