"""Separate adaptive integration of five states, including mass.

Uses no production right-hand side, schedule, segment or diagnostic helpers.
This compares numerical implementations on constructed cases, not flight data.
"""
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd import guided_ascent
try:
    import scipy
    from scipy.integrate import solve_ivp
except ImportError:
    solve_ivp = None

CASES = [
    dict(name='positive_turn', steps=32, initial_mass=1000., dry_mass=700., thrust=20000., specific_impulse=250.,
         reference_density=1.225, scale_height=8500., reference_area=.8, drag_coefficient=.4,
         coast_duration=20., pitch_start_time=5., pitch_end_time=25., initial_pitch_angle=0., final_pitch_angle=.45),
    dict(name='negative_turn', initial_mass=1000., dry_mass=700., thrust=20000., specific_impulse=250.,
         reference_density=1.225, scale_height=8500., reference_area=.8, drag_coefficient=.4,
         coast_duration=25., pitch_start_time=3., pitch_end_time=23., initial_pitch_angle=0., final_pitch_angle=-.35),
    dict(name='late_stronger_turn', initial_mass=987.3, dry_mass=641.7, thrust=19237., specific_impulse=240.,
         reference_density=1.1, scale_height=7300., reference_area=.7, drag_coefficient=.5,
         coast_duration=20., pitch_start_time=12., pitch_end_time=30., initial_pitch_angle=0., final_pitch_angle=.7),
    dict(name='thin_atmosphere', initial_mass=1200., dry_mass=800., thrust=30000., specific_impulse=290.,
         reference_density=.05, scale_height=6200., reference_area=1.2, drag_coefficient=.3,
         coast_duration=40., pitch_start_time=4., pitch_end_time=26., initial_pitch_angle=.04, final_pitch_angle=.6),
]
TOLERANCES = dict(position_m=5e-4, velocity_m_s=3e-6, mass_kg=1e-8)


def reference(case):
    p = {key:value for key,value in case.items() if key != 'name'}
    p.update(gravitational_parameter=3.986004418e14, launch_radius=6371000., steps=case.get('steps',128),
             altitude_numerical_tolerance=.5, velocity_numerical_tolerance=.02,
             relative_numerical_tolerance=1e-6)
    exhaust = p['specific_impulse'] * 9.80665
    burnout = (p['initial_mass'] - p['dry_mass']) * exhaust / p['thrust']

    def equations(powered):
        def rhs(t, state):
            x, y, vx, vy, mass = state
            radius, speed = math.hypot(x,y), math.hypot(vx,vy)
            progress = min(1., max(0., (t-p['pitch_start_time'])/(p['pitch_end_time']-p['pitch_start_time'])))
            pitch = p['initial_pitch_angle'] + progress*(p['final_pitch_angle']-p['initial_pitch_angle'])
            direction = math.atan2(y,x) + pitch
            engine = p['thrust'] if powered else 0.
            density = p['reference_density'] * math.exp(-(radius-p['launch_radius'])/p['scale_height'])
            drag_factor = .5*density*p['drag_coefficient']*p['reference_area']*speed
            central_factor = p['gravitational_parameter']/radius**3
            ax = engine*math.cos(direction)/mass - drag_factor*vx/mass - central_factor*x
            ay = engine*math.sin(direction)/mass - drag_factor*vy/mass - central_factor*y
            return [vx, vy, ax, ay, -engine/exhaust]
        return rhs

    cuts = sorted(set([0., p['pitch_start_time'], p['pitch_end_time'], burnout]))
    state = [p['launch_radius'],0.,0.,0.,p['initial_mass']]
    solutions = []
    for start,end in zip(cuts,cuts[1:]):
        if end <= start:
            continue
        sol = solve_ivp(equations(True), (start,end), state, method='DOP853',
                        rtol=2e-12, atol=1e-10, dense_output=True, max_step=(end-start)/80)
        assert sol.success, sol.message
        solutions.append((start,end,'powered',sol))
        state = sol.y[:,-1]
    if p['coast_duration']:
        end = burnout+p['coast_duration']
        sol = solve_ivp(equations(False), (burnout,end), state, method='DOP853',
                        rtol=2e-12, atol=1e-10, dense_output=True, max_step=p['coast_duration']/80)
        assert sol.success, sol.message
        solutions.append((burnout,end,'coast',sol))
    metrics, artifact = guided_ascent.evaluate(p)
    differences = []
    for row in artifact['samples']:
        choices = [s for s in solutions if s[2] == row['phase'] and s[0]-1e-10 <= row['time_s'] <= s[1]+1e-10]
        assert choices, row
        expected = choices[0][3].sol(row['time_s'])
        differences.append((math.hypot(expected[0]-row['x_m'],expected[1]-row['y_m']),
                            math.hypot(expected[2]-row['vx_m_s'],expected[3]-row['vy_m_s']),
                            abs(expected[4]-row['mass_kg'])))
    maxima = [float(max(row[i] for row in differences)) for i in range(3)]
    return dict(case=case['name'],parameters=p,max_position_difference_m=maxima[0],max_velocity_difference_m_s=maxima[1],
                max_mass_difference_kg=maxima[2],grid_agreement_met=artifact['diagnostics']['grid_agreement_met'],
                burnout_altitude_m=metrics['burnout_altitude']['value'],
                burnout_downrange_m=metrics['burnout_downrange']['value'],scipy_version=scipy.__version__)


@unittest.skipIf(solve_ivp is None, 'SciPy is development-only; use the documented reference environment.')
class GuidedAscentReferenceTests(unittest.TestCase):
    def test_separate_five_state_dop853_reference(self):
        for case in CASES:
            with self.subTest(case=case['name']):
                result = reference(case)
                self.assertLess(result['max_position_difference_m'], TOLERANCES['position_m'])
                self.assertLess(result['max_velocity_difference_m_s'], TOLERANCES['velocity_m_s'])
                self.assertLess(result['max_mass_difference_kg'], TOLERANCES['mass_kg'])
                self.assertTrue(result['grid_agreement_met'])


if __name__ == '__main__':
    unittest.main()
