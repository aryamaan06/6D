"""Independent analytic references and domain checks for 3D propagation."""

from pathlib import Path
import copy
import hashlib
import json
import math
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import simulation


def distance(left, right):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))


def cross(left, right):
    return [left[1] * right[2] - left[2] * right[1],
            left[2] * right[0] - left[0] * right[2],
            left[0] * right[1] - left[1] * right[0]]


def rotate(vector):
    """A nonsymmetric rigid rotation with three independently chosen angles."""
    x, y, z = vector
    x, y, z = x, math.cos(.38) * y - math.sin(.38) * z, math.sin(.38) * y + math.cos(.38) * z
    x, y, z = math.cos(-.71) * x + math.sin(-.71) * z, y, -math.sin(-.71) * x + math.cos(-.71) * z
    return [math.cos(.43) * x - math.sin(.43) * y, math.sin(.43) * x + math.cos(.43) * y, z]


def kepler_reference(a, eccentricity, mu, initial_mean_anomaly, time):
    """Solve Kepler's equation, independently of all numerical stepping code."""
    mean_motion = math.sqrt(mu / a ** 3)
    mean_anomaly = (initial_mean_anomaly + mean_motion * time) % (2 * math.pi)
    anomaly = mean_anomaly
    for _ in range(30):
        correction = (anomaly - eccentricity * math.sin(anomaly) - mean_anomaly) / (1 - eccentricity * math.cos(anomaly))
        anomaly -= correction
        if abs(correction) < 1e-14:
            break
    factor = math.sqrt(1 - eccentricity ** 2)
    denominator = 1 - eccentricity * math.cos(anomaly)
    position = [a * (math.cos(anomaly) - eccentricity), a * factor * math.sin(anomaly), 0]
    velocity = [-a * mean_motion * math.sin(anomaly) / denominator,
                a * mean_motion * factor * math.cos(anomaly) / denominator, 0]
    return rotate(position), rotate(velocity)


def eccentric_spec(eccentricity=.42, periods=1.2, steps=4096, mean_anomaly=.73):
    spec = simulation.default_spec()
    a = 9_000_000.0
    spec.update({"name": "Constructed held-out eccentric Kepler reference",
                 "exclusion_radius_m": 3_000_000.0,
                 "duration_s": periods * 2 * math.pi * math.sqrt(a ** 3 / spec["mu_m3_s2"]),
                 "steps": steps})
    spec["position_m"], spec["velocity_m_s"] = kepler_reference(a, eccentricity, spec["mu_m3_s2"], mean_anomaly, 0)
    return spec, a, eccentricity, mean_anomaly


class SimulationReferenceTests(unittest.TestCase):
    def test_inclined_circular_history_matches_independent_analytic_geometry(self):
        spec = simulation.default_spec()
        result = simulation.simulate(spec)
        radius = 7_000_000.0
        inclination = math.radians(55)
        speed = math.sqrt(spec["mu_m3_s2"] / radius)
        angular_rate = speed / radius
        position_errors = []
        velocity_errors = []
        for sample in result["samples"]:
            angle = angular_rate * sample["time_s"]
            expected_position = [radius * math.cos(angle), radius * math.sin(angle) * math.cos(inclination), radius * math.sin(angle) * math.sin(inclination)]
            expected_velocity = [-speed * math.sin(angle), speed * math.cos(angle) * math.cos(inclination), speed * math.cos(angle) * math.sin(inclination)]
            position_errors.append(distance(sample["position_m"], expected_position) / radius)
            velocity_errors.append(distance(sample["velocity_m_s"], expected_velocity) / speed)
        # This finite-step reference is bounded to 0.01% state error, rather
        # than inferring position accuracy from its much smaller energy drift.
        self.assertLess(max(position_errors), 1e-4)
        self.assertLess(max(velocity_errors), 1e-4)
        self.assertGreater(result["samples"][256]["position_m"][2], .8 * radius)
        self.assertLess(result["samples"][768]["position_m"][2], -.8 * radius)
        self.assertLess(result["summary"]["max_relative_energy_error"], 4e-10)
        self.assertLess(result["summary"]["max_relative_angular_momentum_error"], 2e-14)

    def test_eccentric_oblique_history_matches_independent_kepler_solution(self):
        spec, a, e, anomaly = eccentric_spec()
        result = simulation.simulate(spec)
        position_errors, velocity_errors = [], []
        for sample in result["samples"][::31] + result["samples"][-1:]:
            expected_position, expected_velocity = kepler_reference(a, e, spec["mu_m3_s2"], anomaly, sample["time_s"])
            position_errors.append(distance(sample["position_m"], expected_position) / a)
            velocity_errors.append(distance(sample["velocity_m_s"], expected_velocity) / math.sqrt(spec["mu_m3_s2"] / a))
        self.assertLess(max(position_errors), 4e-5)
        self.assertLess(max(velocity_errors), 7e-5)
        self.assertAlmostEqual(result["summary"]["eccentricity"], e, places=13)
        self.assertAlmostEqual(result["summary"]["semi_major_axis_m"] / a, 1.0, places=13)
        self.assertLess(abs(result["summary"]["min_radius_m"] / (a * (1 - e)) - 1), 2e-5)
        self.assertLess(abs(result["summary"]["max_radius_m"] / (a * (1 + e)) - 1), 2e-5)

    def test_state_error_converges_at_second_order_under_time_step_refinement(self):
        errors = []
        for steps in (512, 1024, 2048):
            spec, a, e, anomaly = eccentric_spec(eccentricity=.3, periods=.7, steps=steps)
            sample = simulation.simulate(spec)["samples"][-1]
            expected_position, expected_velocity = kepler_reference(a, e, spec["mu_m3_s2"], anomaly, spec["duration_s"])
            errors.append(math.hypot(distance(sample["position_m"], expected_position) / a,
                                     distance(sample["velocity_m_s"], expected_velocity) / math.sqrt(spec["mu_m3_s2"] / a)))
        for coarse, fine in zip(errors, errors[1:]):
            self.assertGreater(coarse / fine, 3.9)
            self.assertLess(coarse / fine, 4.1)

    def test_arbitrary_rotation_covariance_of_full_state_history(self):
        spec, *_ = eccentric_spec(periods=.6, steps=2048)
        rotated_spec = copy.deepcopy(spec)
        rotated_spec["position_m"] = rotate(spec["position_m"])
        rotated_spec["velocity_m_s"] = rotate(spec["velocity_m_s"])
        plain = simulation.simulate(spec)
        rotated = simulation.simulate(rotated_spec)
        for sample, transformed in zip(plain["samples"][::29], rotated["samples"][::29]):
            self.assertLess(distance(rotate(sample["position_m"]), transformed["position_m"]) / sample["radius_m"], 2e-13)
            self.assertLess(distance(rotate(sample["velocity_m_s"]), transformed["velocity_m_s"]) / sample["speed_m_s"], 2e-13)

    def test_forward_then_reversed_velocity_returns_to_initial_state(self):
        spec, *_ = eccentric_spec(periods=.37, steps=1024)
        result = simulation.simulate(spec)
        reversed_spec = copy.deepcopy(spec)
        reversed_spec["position_m"] = result["samples"][-1]["position_m"]
        reversed_spec["velocity_m_s"] = [-value for value in result["samples"][-1]["velocity_m_s"]]
        final = simulation.simulate(reversed_spec)["samples"][-1]
        self.assertLess(distance(final["position_m"], spec["position_m"]) / math.hypot(*spec["position_m"]), 2e-12)
        self.assertLess(distance(final["velocity_m_s"], [-value for value in spec["velocity_m_s"]]) / math.hypot(*spec["velocity_m_s"]), 2e-12)

    def test_dimensional_scale_change_preserves_normalized_solution(self):
        spec = simulation.default_spec()
        changed = copy.deepcopy(spec)
        # Newtonian similarity: r' = L*r, t' = T*t, mu' = L^3/T^2*mu.
        length, time = .000001, .0001
        changed["position_m"] = [component * length for component in spec["position_m"]]
        changed["velocity_m_s"] = [component * length / time for component in spec["velocity_m_s"]]
        changed["mu_m3_s2"] *= length ** 3 / time ** 2
        changed["duration_s"] *= time
        changed["exclusion_radius_m"] *= length
        ordinary = simulation.simulate(spec)
        scaled = simulation.simulate(changed)
        for first, second in zip(ordinary["samples"][::47], scaled["samples"][::47]):
            self.assertLess(distance(first["position_m"], [value / length for value in second["position_m"]]) / first["radius_m"], 1e-12)
            self.assertLess(distance(first["velocity_m_s"], [value * time / length for value in second["velocity_m_s"]]) / first["speed_m_s"], 1e-12)


class SimulationContractTests(unittest.TestCase):
    def test_result_is_finite_json_reproducible_and_exactly_sampled(self):
        spec = simulation.default_spec()
        result = simulation.simulate(spec)
        self.assertEqual(result, simulation.simulate(spec))
        json.dumps(result, allow_nan=False)
        self.assertEqual(result["schema"], "sixd.orbit-simulation.v1")
        self.assertEqual(len(result["samples"]), spec["steps"] + 1)
        self.assertEqual(result["samples"][0]["position_m"], spec["position_m"])
        self.assertEqual(result["samples"][0]["velocity_m_s"], spec["velocity_m_s"])
        self.assertEqual(result["samples"][-1]["time_s"], spec["duration_s"])
        self.assertEqual(result["method"]["name"], "velocity_verlet")
        for index, sample in enumerate(result["samples"]):
            self.assertEqual(sample["time_s"], spec["duration_s"] * index / spec["steps"])
            self.assertEqual(sample["radius_m"], math.hypot(*sample["position_m"]))
            self.assertEqual(sample["speed_m_s"], math.hypot(*sample["velocity_m_s"]))
        self.assertIn("no engineering pass/fail", result["diagnostics_label"])
        self.assertNotIn("verdict", result)

    def test_diagnostics_recomputed_independently_from_saved_si_samples(self):
        spec, *_ = eccentric_spec()
        result = simulation.simulate(spec)
        samples = result["samples"]
        energies = [sum(component ** 2 for component in sample["velocity_m_s"]) / 2
                    - spec["mu_m3_s2"] / math.sqrt(sum(component ** 2 for component in sample["position_m"]))
                    for sample in samples]
        momenta = [cross(sample["position_m"], sample["velocity_m_s"]) for sample in samples]
        energy_error = max(abs(value - energies[0]) / abs(energies[0]) for value in energies)
        momentum_error = max(distance(value, momenta[0]) / math.hypot(*momenta[0]) for value in momenta)
        self.assertAlmostEqual(energy_error, result["summary"]["max_relative_energy_error"], delta=4e-15)
        self.assertAlmostEqual(momentum_error, result["summary"]["max_relative_angular_momentum_error"], delta=4e-15)
        for energy, sample in zip(energies, samples):
            self.assertAlmostEqual(energy / energies[0], sample["specific_energy_j_kg"] / energies[0], delta=1e-15)

    def test_canonicalization_does_not_mutate_or_alias_input(self):
        spec = simulation.default_spec()
        original = copy.deepcopy(spec)
        canonical = simulation.validate_spec(spec)
        canonical["position_m"][0] = 9
        self.assertEqual(spec, original)
        result = simulation.simulate(spec)
        result["samples"][0]["position_m"][0] = 4
        self.assertEqual(result["spec"], original)
        self.assertEqual(spec, original)

    def test_source_identity_is_exact_solver_file_sha256(self):
        expected = hashlib.sha256((ROOT / "src/sixd/simulation.py").read_bytes()).hexdigest()
        self.assertEqual(simulation.source_fingerprint(), expected)
        self.assertEqual(simulation.simulate(simulation.default_spec())["source_fingerprint"], expected)

    def test_later_disk_change_cannot_relabel_loaded_solver_identity(self):
        loaded_identity = simulation.source_fingerprint()
        with patch.object(Path, "read_bytes", return_value=b"a later unexecuted source edit"):
            self.assertEqual(simulation.source_fingerprint(), loaded_identity)

    def assert_invalid(self, updates, pattern=None):
        spec = simulation.default_spec()
        spec.update(updates)
        with self.assertRaisesRegex(ValueError, pattern or "."):
            simulation.simulate(spec)

    def test_rejects_nonfinite_boolean_string_and_extreme_scale_inputs(self):
        for field in ("mu_m3_s2", "exclusion_radius_m", "duration_s"):
            for invalid in (math.nan, math.inf, -math.inf, True, "7000", 10 ** 1000, -1):
                with self.subTest(field=field, invalid_type=type(invalid).__name__):
                    self.assert_invalid({field: invalid})
        for field in ("position_m", "velocity_m_s"):
            for invalid in (math.nan, math.inf, True, "1", 10 ** 1000):
                self.assert_invalid({field: [1.0, invalid, 0.0]})
        self.assert_invalid({"position_m": [1e13, 1e13, 0]}, "radius")
        self.assert_invalid({"mu_m3_s2": 1e-13})
        self.assert_invalid({"velocity_m_s": [1e9, 0, 0]})

    def test_rejects_missing_unknown_and_unsupported_semantics(self):
        self.assert_invalid({"units": "km"}, "exactly")
        self.assert_invalid({"thrust_n": 100}, "exactly")
        self.assert_invalid({"schema": "sixd.orbit-scenario.v2"}, "schema")
        self.assert_invalid({"frame": "body_fixed"}, "frame")
        self.assert_invalid({"source": "  "}, "source")
        self.assert_invalid({"name": "x" * 121}, "name")
        self.assert_invalid({"source": "x" * 2001}, "source")
        self.assert_invalid({"name": "bad\x00name"}, "control")
        for field in simulation.default_spec():
            spec = simulation.default_spec()
            del spec[field]
            with self.assertRaisesRegex(ValueError, "exactly"):
                simulation.validate_spec(spec)
        with self.assertRaises(ValueError):
            simulation.validate_spec([])

    def test_rejects_malformed_vectors_and_unbounded_work(self):
        for vector in ([1, 2], [1, 2, 3, 4], "1,2,3", (1, 2, 3), None):
            self.assert_invalid({"position_m": vector}, "JSON array")
        for steps in (True, 15, 4097, 1024.0, "1024", 10 ** 1000):
            self.assert_invalid({"steps": steps}, "steps")
        self.assert_invalid({"position_m": [0, 0, 0]}, "radius")
        self.assert_invalid({"duration_s": 31_557_601}, "duration_s")

    def test_rejects_escape_radial_and_near_parabolic_motion(self):
        spec = simulation.default_spec()
        circular_speed = math.sqrt(spec["mu_m3_s2"] / 7_000_000)
        self.assert_invalid({"velocity_m_s": [0, 1.5 * circular_speed, 0]}, "bounded elliptic")
        self.assert_invalid({"velocity_m_s": [0, 0, 0]}, "Eccentricity")
        self.assert_invalid({"velocity_m_s": [circular_speed, 0, 0]}, "Eccentricity")
        self.assert_invalid({"velocity_m_s": [0, math.sqrt(1.95) * circular_speed, 0]}, "Eccentricity")

    def test_rejects_pericenter_contact_even_when_start_is_above_exclusion(self):
        spec = simulation.default_spec()
        self.assertGreater(math.hypot(*spec["position_m"]), spec["exclusion_radius_m"])
        slower = [component * .8 for component in spec["velocity_m_s"]]
        self.assert_invalid({"velocity_m_s": slower}, "pericenter")
        self.assert_invalid({"exclusion_radius_m": 7_000_000 / 1.005}, "pericenter")

    def test_rejects_coarse_steps_long_runs_and_unresolvable_small_steps(self):
        self.assert_invalid({"steps": 128}, "too coarse")
        spec = simulation.default_spec()
        self.assert_invalid({"duration_s": 8.01 * spec["duration_s"], "steps": 4096}, "at most 8")
        self.assert_invalid({"duration_s": 1e-6, "steps": 4096}, "too short")
        # Eccentric pericenter resolution is stricter than duration / mean period.
        eccentric, *_ = eccentric_spec(eccentricity=.7, periods=1, steps=1024)
        eccentric["exclusion_radius_m"] = 1_000_000
        with self.assertRaisesRegex(ValueError, "too coarse"):
            simulation.simulate(eccentric)


if __name__ == "__main__":
    unittest.main()
