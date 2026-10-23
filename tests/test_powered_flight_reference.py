"""Separate adaptive solver, no production RHS/solver helpers used.

Run with SciPy in the development interpreter. Production Python needs no SciPy.
Case inputs are constructed; this is a different numerical method, not human review.
"""
import math
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from sixd import powered_flight
try:
    import scipy
    from scipy.integrate import solve_ivp
except ImportError:
    solve_ivp=None

CASES=[
    dict(name='atmospheric_ascent',initial_mass=1000.,dry_mass=700.,thrust=20000.,specific_impulse=250.,reference_density=1.225,scale_height=8500.,reference_area=.8,drag_coefficient=.4,coast_duration=20.),
    dict(name='descending_coast',initial_mass=987.3,dry_mass=641.7,thrust=19237.,specific_impulse=240.,reference_density=1.1,scale_height=7300.,reference_area=.7,drag_coefficient=.5,coast_duration=45.),
    dict(name='low_thrust_margin',initial_mass=280.,dry_mass=210.,thrust=3000.,specific_impulse=180.,reference_density=1.225,scale_height=9000.,reference_area=.2,drag_coefficient=.6,coast_duration=8.),
    dict(name='thin_atmosphere',initial_mass=1200.,dry_mass=800.,thrust=30000.,specific_impulse=290.,reference_density=.05,scale_height=6200.,reference_area=1.2,drag_coefficient=.3,coast_duration=70.),
]


def reference(case):
    # Mass is integrated as a third state here, unlike the production analytical mass.
    p={k:v for k,v in case.items() if k!='name'}
    p.update(gravitational_parameter=3.986004418e14,launch_radius=6371000.,steps=256,
             altitude_numerical_tolerance=.1,velocity_numerical_tolerance=.005,relative_numerical_tolerance=1e-7)
    exhaust=p['specific_impulse']*9.80665
    cutoff=(p['initial_mass']-p['dry_mass'])*exhaust/p['thrust']
    def equations(powered):
        def rhs(t,state):
            height,velocity,mass=state
            rho=p['reference_density']*math.exp(-height/p['scale_height'])
            air_force=-.5*rho*p['reference_area']*p['drag_coefficient']*velocity*abs(velocity)
            engine=p['thrust'] if powered else 0.
            return velocity,(engine+air_force)/mass-p['gravitational_parameter']/(p['launch_radius']+height)**2,-engine/exhaust
        return rhs
    burn=solve_ivp(equations(True),(0.,cutoff),[0.,0.,p['initial_mass']],method='DOP853',rtol=2e-12,atol=1e-10,dense_output=True,max_step=cutoff/80)
    assert burn.success
    coast=solve_ivp(equations(False),(cutoff,cutoff+p['coast_duration']),burn.y[:,-1],method='DOP853',rtol=2e-12,atol=1e-10,dense_output=True,max_step=p['coast_duration']/80)
    assert coast.success
    metrics,a=powered_flight.evaluate(p)
    differences=[]
    for row in a['samples']:
        value=(burn if row['phase']=='powered' else coast).sol(row['time_s'])
        differences.append([abs(value[0]-row['altitude_m']),abs(value[1]-row['velocity_m_s']),abs(value[2]-row['mass_kg'])])
    maxima=[max(d[i] for d in differences) for i in range(3)]
    return {'case':case['name'],'max_altitude_difference_m':float(maxima[0]),'max_velocity_difference_m_s':float(maxima[1]),'max_mass_difference_kg':float(maxima[2]),
            'reference_final_altitude_m':float(coast.y[0,-1]),'reference_final_velocity_m_s':float(coast.y[1,-1]),
            'grid_agreement_met':a['diagnostics']['grid_agreement_met'],'scipy_version':scipy.__version__}


@unittest.skipIf(solve_ivp is None,'SciPy reference dependency is development-only; run documented reference command.')
class PoweredFlightReferenceTests(unittest.TestCase):
    def test_separately_integrated_dop853_trajectories(self):
        for case in CASES:
            with self.subTest(case=case['name']):
                r=reference(case)
                self.assertLess(r['max_altitude_difference_m'],2e-4)
                self.assertLess(r['max_velocity_difference_m_s'],2e-6)
                self.assertLess(r['max_mass_difference_kg'],1e-8)
                self.assertTrue(r['grid_agreement_met'])


if __name__=='__main__':unittest.main()
