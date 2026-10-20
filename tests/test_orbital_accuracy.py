"""Explicit orbital tolerances, signed-state refinement and retained evidence."""
from copy import deepcopy
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import orbital_adapter as orbit, simulation


def parameters(**overrides):
    # Constructed Earth-like circle. The exact circular solution is an external
    # analytic reference, not another execution of the numerical integrator.
    values = {
        "mu_m3_s2": 398600441800000.0, "exclusion_radius_m": 6371000.0,
        "position_x": 7000000.0, "position_y": 0.0, "position_z": 0.0,
        "velocity_x": 0.0, "velocity_y": math.sqrt(398600441800000.0 / 7000000.0),
        "velocity_z": 0.0, "duration_s": 500.0, "steps": 1024,
    }
    values.update(overrides)
    return values


CRITERIA = {"position_tolerance_m": 1.0, "velocity_tolerance_m_s": 0.001,
            "source": "Constructed accuracy requirement for this review case"}


class OrbitalAccuracyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parameters = parameters()
        cls.metrics, cls.artifact, cls.receipt = orbit.evaluate_with_accuracy(cls.parameters, CRITERIA)

    def test_missing_criteria_never_invents_accuracy_or_references(self):
        with patch.object(orbit, "evaluate", wraps=orbit.evaluate) as evaluate:
            metrics, artifact, accuracy = orbit.evaluate_with_accuracy(self.parameters)
        self.assertEqual(evaluate.call_count, 1)
        self.assertEqual(metrics, self.metrics)
        self.assertEqual(artifact, self.artifact)
        self.assertEqual(accuracy["status"], "not_assessed")
        self.assertIsNone(accuracy["criteria"])
        self.assertEqual(accuracy["reference_levels"], [])
        self.assertTrue(orbit.validate_accuracy(accuracy, artifact, self.parameters, None, simulation.source_fingerprint()))

    def test_explicit_loose_tolerances_require_both_vector_orders(self):
        accuracy = self.receipt
        self.assertEqual(accuracy["status"], "supported")
        self.assertEqual([r["steps"] for r in accuracy["reference_levels"]], [256, 512])
        self.assertEqual([r["aligned_sample_count"] for r in accuracy["comparisons"]], [257, 513])
        for order in accuracy["observed_orders"].values():
            self.assertAlmostEqual(order, 2.0, places=4)
        last = accuracy["comparisons"][-1]
        self.assertLess(last["max_position_difference_m"], CRITERIA["position_tolerance_m"])
        self.assertLess(last["max_velocity_difference_m_s"], CRITERIA["velocity_tolerance_m_s"])
        self.assertFalse(accuracy["method"]["error_bound_claimed"])

    def test_tight_position_tolerance_blocks_without_changing_finest_result(self):
        criteria = dict(CRITERIA, position_tolerance_m=0.01)
        metrics, artifact, accuracy = orbit.evaluate_with_accuracy(self.parameters, criteria)
        self.assertEqual(metrics, self.metrics)
        self.assertEqual(artifact, self.artifact)
        self.assertEqual(accuracy["status"], "insufficient_accuracy")
        self.assertIn("exceeds", accuracy["reason"])

    def test_velocity_tolerance_is_independent_of_position_tolerance(self):
        _, _, accuracy = orbit.evaluate_with_accuracy(self.parameters, dict(CRITERIA, velocity_tolerance_m_s=1e-8))
        self.assertEqual(accuracy["status"], "insufficient_accuracy")

    def test_circle_analytic_phase_error_is_nonzero_despite_conserved_scalars(self):
        duration = self.parameters["duration_s"]
        radius = self.parameters["position_x"]
        rate = math.sqrt(self.parameters["mu_m3_s2"] / radius ** 3)
        expected = [radius * math.cos(rate * duration), radius * math.sin(rate * duration), 0.0]
        actual = self.artifact["samples"][-1]["position_m"]
        error = math.hypot(*(a - b for a, b in zip(actual, expected)))
        self.assertGreater(error, 0.1)
        self.assertLess(self.artifact["summary"]["max_relative_energy_error"], 1e-12)
        self.assertNotIn("max_relative_energy_error", str(self.receipt["comparisons"]))

    def test_comparison_uses_signed_vectors_at_every_aligned_time(self):
        coarse = deepcopy(self.receipt["reference_levels"][0]["artifact"])
        middle = self.receipt["reference_levels"][1]["artifact"]
        # A reversed intermediate state retains exactly the same scalar radius
        # and speed. A scalar-only or endpoint-only comparison misses the fault.
        row = coarse["samples"][100]
        row["position_m"] = [-value for value in row["position_m"]]
        row["velocity_m_s"] = [-value for value in row["velocity_m_s"]]
        comparison = orbit._compare_aligned(coarse, middle)
        self.assertGreater(comparison["max_position_difference_m"], 13_000_000)
        self.assertGreater(comparison["max_velocity_difference_m_s"], 14_000)
        self.assertEqual(coarse["samples"][-1], self.receipt["reference_levels"][0]["artifact"]["samples"][-1])

    def test_nonsecond_order_phase_defect_blocks_even_with_loose_tolerances(self):
        levels = deepcopy(self.receipt["reference_levels"])
        # Inject a deliberately first-order grid-dependent phase defect. The
        # finest remains unchanged and initial states remain exactly supplied.
        for level in levels:
            artifact = level["artifact"]
            for row in artifact["samples"][1:]:
                angle = row["time_s"] / self.parameters["duration_s"] / level["steps"]
                c, s = math.cos(angle), math.sin(angle)
                for key in ("position_m", "velocity_m_s"):
                    x, y, z = row[key]
                    row[key] = [c * x - s * y, s * x + c * y, z]
                row["radius_m"] = math.hypot(*row["position_m"])
                row["speed_m_s"] = math.hypot(*row["velocity_m_s"])
            metrics = orbit.sampled_metrics(artifact)
            for key in ("min_radius_m", "max_radius_m", "max_speed_m_s"):
                artifact["summary"][key] = metrics[key]["value"]
        criteria = dict(CRITERIA, position_tolerance_m=1e9, velocity_tolerance_m_s=1e9)
        receipt = orbit._accuracy_receipt(self.artifact, criteria, levels, None)
        self.assertEqual(receipt["status"], "insufficient_accuracy")
        self.assertLess(abs(receipt["observed_orders"]["position"]), 0.01)
        self.assertTrue(orbit.validate_accuracy(receipt, self.artifact, self.parameters, criteria, simulation.source_fingerprint()))

    def test_coarse_grid_rejection_retains_valid_finest(self):
        p = parameters(steps=64)
        metrics, artifact, accuracy = orbit.evaluate_with_accuracy(p, CRITERIA)
        self.assertEqual(accuracy["status"], "not_assessed")
        self.assertEqual(accuracy["reference_failure"]["steps"], 16)
        self.assertIn("too coarse", accuracy["reference_failure"]["message"])
        self.assertEqual(len(artifact["samples"]), 65)
        self.assertEqual(metrics, orbit.sampled_metrics(artifact))
        self.assertTrue(orbit.validate_accuracy(accuracy, artifact, p, CRITERIA, simulation.source_fingerprint()))

    def test_ineligible_refinement_grids_abstain_without_changing_solver_limits(self):
        for steps in (32, 66):
            with self.subTest(steps=steps):
                p = parameters(steps=steps, duration_s=100.0)
                _, artifact, accuracy = orbit.evaluate_with_accuracy(p, CRITERIA)
                self.assertEqual(accuracy["status"], "not_assessed")
                self.assertEqual(accuracy["reference_levels"], [])
                self.assertTrue(orbit.validate_accuracy(accuracy, artifact, p, CRITERIA, simulation.source_fingerprint()))
        with self.assertRaisesRegex(ValueError, "too coarse"):
            orbit.evaluate_with_accuracy(parameters(steps=16), CRITERIA)

    def test_invalid_criteria_reject_before_any_propagation(self):
        invalid = [False, {}, dict(CRITERIA, unknown=1), dict(CRITERIA, source=" "),
                   dict(CRITERIA, position_tolerance_m=True), dict(CRITERIA, position_tolerance_m=0),
                   dict(CRITERIA, velocity_tolerance_m_s=-1), dict(CRITERIA, velocity_tolerance_m_s=float("nan")),
                   dict(CRITERIA, position_tolerance_m=float("inf")), dict(CRITERIA, position_tolerance_m=10 ** 1000)]
        with patch.object(simulation, "simulate", side_effect=AssertionError("Unexpected propagation")):
            for criteria in invalid:
                with self.subTest(criteria=str(criteria)[:150]), self.assertRaises(ValueError):
                    orbit.evaluate_with_accuracy(self.parameters, criteria)

    def test_saved_validation_does_not_rerun_solver_or_current_domain_policy(self):
        with patch.object(simulation, "simulate", side_effect=AssertionError("Unexpected solver rerun")), \
             patch.object(simulation, "validate_spec", side_effect=AssertionError("Unexpected current policy")):
            self.assertTrue(orbit.validate_accuracy(self.receipt, self.artifact, self.parameters, CRITERIA, simulation.source_fingerprint()))

    def test_tampered_arithmetic_verdict_criteria_and_metadata_are_rejected(self):
        mutations = [
            lambda r: r.update(status="not_assessed"),
            lambda r: r.update(reason="Everything looks good"),
            lambda r: r["criteria"].update(position_tolerance_m=2.0),
            lambda r: r["comparisons"][-1].update(max_position_difference_m=0.0),
            lambda r: r["comparisons"][-1].update(aligned_sample_count=True),
            lambda r: r["observed_orders"].update(position=2.0),
            lambda r: r["method"].update(error_bound_claimed=True),
            lambda r: r["limitations"].clear(),
            lambda r: r["reference_levels"][0]["artifact"].update(source_fingerprint="0" * 64),
            lambda r: r["reference_levels"][0]["artifact"]["samples"][100]["position_m"].__setitem__(0, 1.0),
        ]
        for index, mutate in enumerate(mutations):
            receipt = deepcopy(self.receipt)
            mutate(receipt)
            with self.subTest(mutation=index), self.assertRaises(ValueError):
                orbit.validate_accuracy(receipt, self.artifact, self.parameters, CRITERIA, simulation.source_fingerprint())
        with self.assertRaises(ValueError):
            orbit.validate_accuracy(self.receipt, self.artifact, self.parameters, dict(CRITERIA, velocity_tolerance_m_s=2), simulation.source_fingerprint())

    def test_legacy_artifact_contract_remains_unchanged(self):
        metrics, artifact = orbit.evaluate(self.parameters)
        self.assertEqual(artifact, self.artifact)
        self.assertNotIn("numerical_accuracy", artifact)
        self.assertTrue(orbit.validate_artifact(artifact, metrics, self.parameters, simulation.source_fingerprint()))


if __name__ == "__main__":
    unittest.main()
