"""Independent elliptic Kepler references for Cartesian orbital propagation.

The reference starts from declared orbital elements and solves Kepler's scalar
equation by bisection. It does not call the production force, orbital-element,
time-integration, refinement, or diagnostic implementation. Cases are synthetic
numerical checks of the stated ideal two-body equations, not flight validation.
"""
from dataclasses import dataclass
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd import simulation


@dataclass(frozen=True)
class KeplerCase:
    name: str
    semi_major_axis_m: float
    eccentricity: float
    inclination_deg: float
    ascending_node_deg: float
    periapsis_argument_deg: float
    mean_anomaly_rad: float
    periods: float
    steps: int
    mu_m3_s2: float = 3.986004418e14
    exclusion_radius_m: float = 6_371_000.0

    @property
    def period_s(self):
        return math.tau * math.sqrt(self.semi_major_axis_m ** 3 / self.mu_m3_s2)

    def state(self, time_s):
        """Position and its analytic time derivative from elliptic elements."""
        e = self.eccentricity
        rate = math.sqrt(self.mu_m3_s2 / self.semi_major_axis_m ** 3)
        mean = math.remainder(self.mean_anomaly_rad + rate * time_s, math.tau)
        if e == 0.0 or mean == 0.0:
            anomaly = mean
        else:
            lower, upper = -math.pi, math.pi
            # E - e sin(E) is strictly increasing for every declared e < 1.
            for _ in range(64):
                anomaly = (lower + upper) / 2.0
                if anomaly == lower or anomaly == upper:
                    break
                if anomaly - e * math.sin(anomaly) < mean:
                    lower = anomaly
                else:
                    upper = anomaly
        a = self.semi_major_axis_m
        c, s = math.cos(anomaly), math.sin(anomaly)
        b = math.sqrt(1.0 - e * e)
        anomaly_rate = rate / (1.0 - e * c)
        position = (a * (c - e), a * b * s)
        velocity = (-a * s * anomaly_rate, a * b * c * anomaly_rate)
        node, inc, arg = map(math.radians, (self.ascending_node_deg,
                                          self.inclination_deg,
                                          self.periapsis_argument_deg))
        cn, sn, ci, si, cw, sw = (math.cos(node), math.sin(node), math.cos(inc),
                                  math.sin(inc), math.cos(arg), math.sin(arg))
        first = (cn * cw - sn * sw * ci, sn * cw + cn * sw * ci, sw * si)
        second = (-cn * sw - sn * cw * ci, -sn * sw + cn * cw * ci, cw * si)
        return tuple([first[j] * pair[0] + second[j] * pair[1] for j in range(3)]
                     for pair in (position, velocity))

    def spec(self, steps=None):
        position, velocity = self.state(0.0)
        return {
            "schema": "sixd.orbit-scenario.v1", "name": self.name,
            "mu_m3_s2": self.mu_m3_s2,
            "exclusion_radius_m": self.exclusion_radius_m,
            "position_m": position, "velocity_m_s": velocity,
            "duration_s": self.period_s * self.periods,
            "steps": self.steps if steps is None else steps,
            "frame": "body_centered_inertial_3d",
            "source": "Synthetic independent Kepler-element numerical reference; no measured flight data.",
        }


CASES = (
    KeplerCase("circle_one_period", 7e6, 0.0, 55, 27, 13, 0.0, 1.0, 1024),
    KeplerCase("circle_eight_periods", 7e6, 0.0, 55, 27, 13, 0.0, 8.0, 4096),
    KeplerCase("eccentric_four_periods", 12e6, 0.25, 63, 41, 22, 0.0, 4.0, 4096),
    KeplerCase("eccentric_one_period", 20e6, 0.6, 32, 72, 38, 0.0, 1.0, 4096),
    KeplerCase("retrograde_eccentric_partial", 30e6, 0.7, 137, 83, 19, 1.2, 0.75, 4096),
    KeplerCase("high_eccentricity_pericenter_passage", 70e6, 0.89, 82, 193, 121,
               -0.025, 0.035, 2048),
    KeplerCase("eccentric_fractional_endpoint", 15e6, 0.35, 71, 241, 78,
               0.71, 0.73, 2048),
)


def reference_errors(case, artifact):
    """Measure all signed states and all five metrics on identical sample times."""
    position_errors, velocity_errors, radii, speeds = [], [], [], []
    for row in artifact["samples"]:
        position, velocity = case.state(row["time_s"])
        position_errors.append(math.dist(position, row["position_m"]))
        velocity_errors.append(math.dist(velocity, row["velocity_m_s"]))
        radii.append(math.hypot(*position))
        speeds.append(math.hypot(*velocity))
    samples = artifact["samples"]
    reference_metrics = {"min_radius_m": min(radii), "max_radius_m": max(radii),
                         "max_speed_m_s": max(speeds), "final_radius_m": radii[-1],
                         "final_speed_m_s": speeds[-1]}
    actual_metrics = {"min_radius_m": min(r["radius_m"] for r in samples),
                      "max_radius_m": max(r["radius_m"] for r in samples),
                      "max_speed_m_s": max(r["speed_m_s"] for r in samples),
                      "final_radius_m": samples[-1]["radius_m"],
                      "final_speed_m_s": samples[-1]["speed_m_s"]}
    return {
        "sample_count": len(samples),
        "max_position_error_m": max(position_errors),
        "max_velocity_error_m_s": max(velocity_errors),
        "final_position_error_m": position_errors[-1],
        "final_velocity_error_m_s": velocity_errors[-1],
        "max_position_error_time_s": samples[position_errors.index(max(position_errors))]["time_s"],
        "metric_absolute_errors": {key: abs(actual_metrics[key] - value)
                                   for key, value in reference_metrics.items()},
    }


class IndependentReferenceTests(unittest.TestCase):
    def test_all_signed_states_against_independent_kepler_reference(self):
        for case in CASES:
            with self.subTest(case=case.name):
                artifact = simulation.simulate(case.spec())
                errors = reference_errors(case, artifact)
                self.assertLess(errors['max_position_error_m'], .5)
                self.assertLess(errors['max_velocity_error_m_s'], .001)
                self.assertEqual(artifact['method']['name'], 'rk4')

    def test_eight_period_accuracy_and_tight_tolerance_abstention(self):
        from sixd import orbital_adapter as orbit
        case = CASES[1]
        spec = case.spec(16384)
        p = {k: spec[k] for k in ('mu_m3_s2','exclusion_radius_m','duration_s','steps')}
        for i, axis in enumerate('xyz'):
            p['position_'+axis] = spec['position_m'][i]
            p['velocity_'+axis] = spec['velocity_m_s'][i]
        criteria = dict(position_tolerance_m=1., velocity_tolerance_m_s=.01, source='Constructed numerical criterion')
        _, artifact, accuracy = orbit.evaluate_with_accuracy(p, criteria)
        self.assertEqual(accuracy['status'], 'supported')
        self.assertEqual(accuracy['schema'], 'sixd.orbit-accuracy.v2')
        self.assertLess(reference_errors(case, artifact)['max_position_error_m'], .002)
        self.assertTrue(orbit.validate_accuracy(accuracy, artifact, p, criteria, simulation.source_fingerprint()))
        tighter = dict(criteria, position_tolerance_m=1e-8)
        _, _, rejected = orbit.evaluate_with_accuracy(p, tighter)
        self.assertEqual(rejected['status'], 'insufficient_accuracy')

    def test_mixed_method_reference_and_unknown_method_are_rejected(self):
        from sixd import orbital_adapter as orbit
        from test_orbital_accuracy import parameters, CRITERIA
        from copy import deepcopy
        p = parameters(duration_s=2000)
        _, artifact, accuracy = orbit.evaluate_with_accuracy(p, CRITERIA)
        changed = deepcopy(accuracy)
        ref = dict(p, steps=p['steps']//4)
        changed['reference_levels'][0]['artifact'] = orbit.evaluate(ref, method='velocity_verlet')[1]
        with self.assertRaisesRegex(ValueError, 'same retained numerical method'):
            orbit.validate_accuracy(changed, artifact, p, CRITERIA, simulation.source_fingerprint())
        with self.assertRaises(ValueError):
            simulation.simulate(CASES[0].spec(), method='unknown')


if __name__ == "__main__":
    unittest.main()
