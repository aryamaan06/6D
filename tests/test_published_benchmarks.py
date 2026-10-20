"""Reference suite gates, deliberate fault sensitivity and boundary regression."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tools'))
import benchmark_engineering as benchmark
import published_static_benchmarks as static
import published_power_benchmarks as power
import published_control_benchmarks as control
from sixd import engineering,orbital_adapter,simulation


class PublishedReferenceTests(unittest.TestCase):
    def test_static_published_and_decimal_references_pass(self):
        checks=static.run_checks()
        self.assertTrue(all(row['passed'] for row in checks),[r['id'] for r in checks if not r['passed']])
        self.assertEqual({r['model'] for r in checks},{'ideal_propulsion','static_cantilever','radiative_equilibrium','drag_load'})
        self.assertTrue(any(r['reference_kind']=='published_rounded_worked_example' for r in checks))

    def test_independent_beam_reference_detects_deliberate_calculator_fault(self):
        def wrong(_parameters):
            return {'bending_stress':(1.,'Pa'),'tip_deflection':(1.,'m')}
        with patch.dict(engineering._CALCULATORS,{'static_cantilever':wrong}):
            checks=static.run_checks()
        beam=next(r for r in checks if r['id']=='cantilever_tip_load')
        self.assertFalse(beam['passed'])

    def test_published_power_totals_and_rate_shortfall_are_separate(self):
        checks=power.run_checks();self.assertTrue(all(r['passed'] for r in checks))
        self.assertEqual(checks[0]['expected']['total_load_energy']['value'],394200000)
        self.assertEqual(checks[1]['expected']['total_load_energy']['value'],78840000)
        schedule=checks[-1]['actual']
        self.assertGreater(schedule['battery_energy_margin']['value'],0)
        self.assertLess(schedule['minimum_battery_power_margin']['value'],0)

    def test_published_control_solutions_check_all_saved_states(self):
        checks=control.run_checks()
        self.assertEqual(len(checks),5)
        self.assertTrue(all(r['passed'] for r in checks),[r['id'] for r in checks if not r['passed']])
        self.assertEqual(sum(r['reference_kind']=='published_worked_solution' for r in checks),2)
        for row in checks:
            self.assertLessEqual(row['actual']['maximum_angle_difference_rad'],row['tolerance']['angle_absolute_rad'])
            self.assertLessEqual(row['actual']['maximum_rate_difference_rad_s'],row['tolerance']['rate_absolute_rad_s'])

    def test_missing_external_reference_is_failure_without_substitute(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as directory:
            with patch('published_orbit_benchmarks._spice',side_effect=RuntimeError('Reference unavailable')),redirect_stdout(io.StringIO()):
                report=benchmark.run(Path(directory)/'missing.json')
        self.assertFalse(report['passed'])
        self.assertIn('orbital_trajectory',report['missing_reference_models'])
        self.assertEqual(report['errors'][0]['module'],'published_orbit_benchmarks')


def boundary_parameters():
    # Constructed elements converted by external CSPICE_N0067 conics through
    # SpiceyPy8.3.0, not a state produced by the solver under test.
    return {'mu_m3_s2':398600441800000.,'exclusion_radius_m':1000000.,
            'position_x':3801294.423081409,'position_y':4916126.426372032,'position_z':3222089.643224831,
            'velocity_x':-5478.61324578323,'velocity_y':884.9914662466416,'velocity_z':5113.169982011355,
            'duration_s':46628.13310148812,'steps':4096}


class PeriodBoundaryRegressionTests(unittest.TestCase):
    def test_external_exact_eight_period_boundary_accepts_roundoff(self):
        metrics,artifact=orbital_adapter.evaluate(boundary_parameters())
        self.assertEqual(len(artifact['samples']),4097)
        self.assertTrue(all(math.isfinite(m['value']) for m in metrics.values()))

    def test_material_excess_remains_rejected(self):
        for excess in (1e-5,1000):
            parameters=boundary_parameters();parameters['duration_s']+=excess
            with self.assertRaisesRegex(ValueError,'at most 8'):
                orbital_adapter.evaluate(parameters)

    def test_roundoff_policy_is_bounded_to_sixteen_ulps(self):
        parameters=boundary_parameters()
        spec=orbital_adapter.scenario_from_parameters(parameters)
        shorter=deepcopy(spec);shorter['duration_s']*=.99
        period=simulation._orbit(shorter)['orbital_period_s']
        limit=8*period
        spec['duration_s']=limit+32*math.ulp(limit)
        with self.assertRaisesRegex(ValueError,'at most 8'):
            simulation.validate_spec(spec)


if __name__=='__main__':unittest.main()
