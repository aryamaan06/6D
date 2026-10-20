"""Multi-step workspace histories must retain the fresh-calculation verdicts."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from recalculation_histories import check_history


class RecalculationHistoryTests(unittest.TestCase):
    def run_history(self, name, count):
        with tempfile.TemporaryDirectory(prefix="history-unit-", dir=ROOT / "work") as directory:
            result = check_history(name, Path(directory))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["compared_runs"], count)
        self.assertTrue(result["history_preserved"])
        return result

    def test_repeated_same_revision_preserves_calculation_origins(self):
        result = self.run_history("repeated_same_revision", 2)
        self.assertEqual(result["run_checks"][-1]["executed_model_ids"], [])

    def test_a_b_a_revert_recomputes_changed_branch(self):
        result = self.run_history("revert_after_reviewed_edit", 3)
        self.assertEqual(result["run_checks"][-1]["executed_model_ids"], ["thermal"])

    def test_unrun_revision_uses_last_reviewed_ancestor(self):
        result = self.run_history("unrun_intervening_revision", 2)
        self.assertEqual([row["revision"] for row in result["run_checks"]], [1, 3])

    def test_chain_rewire_detaches_old_source_and_propagates_gap(self):
        result = self.run_history("chain_rewiring_multistep", 5)
        self.assertEqual(set(result["run_checks"][-1]["executed_model_ids"]), {"aero", "beam"})


if __name__ == "__main__":
    unittest.main()
