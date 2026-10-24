"""Analytic, conservation, event and retained-evidence checks for planar ascent."""
from copy import deepcopy
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from sixd import guided_ascent as ascent, powered_flight


def parameters(**changes):
    result = dict(initial_mass=1000,dry_mass=700,thrust=20000,specific_impulse=250,
                  reference_area=.8,drag_coefficient=.4,reference_density=1.225,
                  scale_height=8500,gravitational_parameter=3.986004418e14,launch_radius=6371000,
                  coast_duration=20,steps=32,altitude_numerical_tolerance=.5,
                  velocity_numerical_tolerance=.02,relative_numerical_tolerance=1e-6,
                  pitch_start_time=5,pitch_end_time=25,initial_pitch_angle=0,final_pitch_angle=.6)
    result.update(changes)
    return result


class GuidedAscentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = parameters()
        cls.metrics,cls.artifact = ascent.evaluate(cls.p)

    def test_vacuum_vertical_closed_form_at_each_retained_sample(self):
        p = parameters(reference_density=0,gravitational_parameter=0,final_pitch_angle=0)
        metrics,artifact = ascent.evaluate(p)
        exhaust = 9.80665*p['specific_impulse']
        flow = p['thrust']/exhaust
        burn = (p['initial_mass']-p['dry_mass'])/flow
        for row in artifact['samples']:
            t = min(row['time_s'],burn)
            mass = p['initial_mass']-flow*t
            velocity = exhaust*math.log(p['initial_mass']/mass)
            altitude = exhaust*(t-mass/flow*math.log(p['initial_mass']/mass))+velocity*max(0,row['time_s']-burn)
            self.assertAlmostEqual(row['speed_m_s'],velocity,delta=3e-8)
            self.assertAlmostEqual(row['altitude_m'],altitude,delta=3e-6)
            self.assertEqual(row['y_m'],0)
            self.assertEqual(row['downrange_m'],0)
        self.assertEqual(metrics['propellant_consumed']['value'],300)
        self.assertTrue(artifact['diagnostics']['grid_agreement_met'])

    def test_zero_pitch_reduces_to_existing_vertical_equations(self):
        p = parameters(initial_pitch_angle=0,final_pitch_angle=0)
        metrics,artifact = ascent.evaluate(p)
        vertical,_ = powered_flight.evaluate({key:p[key] for key in powered_flight.PARAMETERS})
        for name in ('burnout_altitude','final_altitude','max_sampled_dynamic_pressure'):
            self.assertAlmostEqual(metrics[name]['value'],vertical[name]['value'],delta=2e-4)
        self.assertAlmostEqual(metrics['burnout_speed']['value'],vertical['burnout_velocity']['value'],delta=2e-6)
        self.assertTrue(all(row['y_m'] == row['vy_m_s'] == 0 for row in artifact['samples']))

    def test_mirrored_steering_reflects_the_entire_trajectory(self):
        _,other = ascent.evaluate(parameters(final_pitch_angle=-.6))
        for left,right in zip(self.artifact['samples'],other['samples']):
            for field in ('x_m','vx_m_s','altitude_m','speed_m_s','dynamic_pressure_pa','mass_kg'):
                self.assertEqual(left[field],right[field])
            for field in ('y_m','vy_m_s','downrange_m','tangential_velocity_m_s'):
                self.assertEqual(left[field],-right[field])
        self.assertGreater(self.metrics['burnout_downrange']['value'],1000)

    def test_drag_opposes_the_full_velocity_vector(self):
        p = ascent.validate_parameters(parameters())
        r = p['launch_radius']+2000
        x,y = r*math.cos(.1),r*math.sin(.1)
        vx,vy = -80.0,120.0
        t = 10.0
        force = ascent._physical(p,t,x,y,vx,vy,True)
        pitch = ascent._pitch(p,t)
        theta = math.atan2(y,x)
        tx,ty = math.cos(theta+pitch),math.sin(theta+pitch)
        gravity_x,gravity_y = -force['gravity_m_s2']*x/r,-force['gravity_m_s2']*y/r
        drag_x = force['mass_kg']*(force['ax_m_s2']-gravity_x)-p['thrust']*tx
        drag_y = force['mass_kg']*(force['ay_m_s2']-gravity_y)-p['thrust']*ty
        self.assertLess(drag_x*vx+drag_y*vy,0)
        self.assertAlmostEqual(math.hypot(drag_x,drag_y),.5*p['reference_density']*math.exp(-2000/p['scale_height'])*(vx*vx+vy*vy)*p['drag_coefficient']*p['reference_area'],delta=1e-8)
        self.assertAlmostEqual(drag_x*vy-drag_y*vx,0,delta=1e-8)

    def test_vacuum_coast_conserves_energy_and_angular_momentum(self):
        p = parameters(reference_density=0,coast_duration=35)
        _,artifact = ascent.evaluate(p)
        coast = [row for row in artifact['samples'] if row['phase'] == 'coast']
        energy = lambda row:(row['vx_m_s']**2+row['vy_m_s']**2)/2-p['gravitational_parameter']/math.hypot(row['x_m'],row['y_m'])
        momentum = lambda row:row['x_m']*row['vy_m_s']-row['y_m']*row['vx_m_s']
        self.assertLess(max(abs(energy(row)-energy(coast[0])) for row in coast),3e-6)
        self.assertLess(max(abs(momentum(row)-momentum(coast[0])) for row in coast),3e-5)

    def test_cutoff_is_exact_and_both_sides_retain_identical_state(self):
        rows = self.artifact['samples']
        before = next(row for row in rows if row['event'] == 'before_cutoff')
        after = next(row for row in rows if row['event'] == 'after_cutoff')
        for field in ('time_s','x_m','y_m','vx_m_s','vy_m_s','mass_kg','altitude_m','downrange_m'):
            self.assertEqual(before[field],after[field])
        self.assertEqual(before['time_s'],self.metrics['burn_duration']['value'])
        self.assertEqual(before['mass_kg'],700)
        self.assertEqual(after['thrust_n'],0)
        self.assertAlmostEqual(math.hypot(before['ax_m_s2']-after['ax_m_s2'],before['ay_m_s2']-after['ay_m_s2']),20000/700)
        self.assertTrue(all(row['mass_kg']>=700 for row in rows))

    def test_steering_knots_are_exact_on_every_grid(self):
        grids = [self.artifact['refinement']['coarse_samples'],self.artifact['refinement']['middle_samples'],self.artifact['samples']]
        for rows in grids:
            start = next(row for row in rows if row['event'] == 'pitch_start')
            end = next(row for row in rows if row['event'] == 'pitch_end')
            self.assertEqual(start['time_s'],5)
            self.assertEqual(start['pitch_angle_rad'],0)
            self.assertEqual(end['time_s'],25)
            self.assertEqual(end['pitch_angle_rad'],.6)
            for row in rows:
                expected = 0 if row['time_s']<=5 else .6 if row['time_s']>=25 else .6*(row['time_s']-5)/20
                self.assertAlmostEqual(row['pitch_angle_rad'],expected,delta=1e-15)

    def test_coincident_knots_and_zero_coast_have_no_zero_width_segment(self):
        p = parameters(pitch_start_time=0,coast_duration=0)
        p['pitch_end_time'] = (p['initial_mass']-p['dry_mass'])*p['specific_impulse']*9.80665/p['thrust']
        _,artifact = ascent.evaluate(p)
        self.assertEqual(len(artifact['solver']['segments']),1)
        self.assertEqual(len(artifact['samples']),4*int(p['steps'])+1)
        self.assertEqual(artifact['samples'][-1]['event'],'before_cutoff')
        self.assertFalse(any(row['event']=='after_cutoff' for row in artifact['samples']))

    def test_domain_errors_are_rejected_instead_of_relabelled_failures(self):
        changes = [dict(pitch_start_time=-1),dict(pitch_end_time=5),dict(pitch_end_time=100),
                   dict(initial_pitch_angle=math.pi),dict(final_pitch_angle=-math.pi),
                   dict(initial_pitch_angle=1.2),dict(initial_pitch_angle=math.pi/2,gravitational_parameter=0),
                   dict(thrust=1000),dict(coast_duration=500),
                   dict(final_pitch_angle=float('nan')),dict(steps=True),dict(thrust=10**999)]
        for change in changes:
            with self.subTest(change=change),self.assertRaises((ValueError,ArithmeticError)):
                ascent.evaluate(parameters(**change))
        for state in ((0,0,0,0),(6371000,0,100001,0),(-6371000,0,0,0)):
            with self.assertRaises(ValueError):
                ascent._physical(ascent.validate_parameters(parameters()),0,*state,True)

    def test_numerical_gap_is_visible_and_position_scale_is_not_body_radius(self):
        p = parameters(steps=8,altitude_numerical_tolerance=1e-12,velocity_numerical_tolerance=1e-12,relative_numerical_tolerance=0)
        _,artifact = ascent.evaluate(p)
        self.assertFalse(artifact['diagnostics']['grid_agreement_met'])
        self.assertGreater(artifact['diagnostics']['max_position_difference_m'],1e-10)
        self.assertGreater(ascent.metric_allowance(artifact,'burnout_altitude'),0)

    def test_retained_artifact_validation_does_not_integrate(self):
        with patch.object(ascent,'_integrate',side_effect=AssertionError('History must not integrate')):
            self.assertTrue(ascent.validate_artifact(self.artifact,self.metrics,self.p,self.artifact['source_fingerprint']))

    def test_frame_samples_scope_events_and_diagnostics_tampering_are_rejected(self):
        for kind in ('frame','position','velocity','mass','time','event','metric','diagnostic','scope','source','segments','extra','cutoff'):
            artifact,metrics = deepcopy(self.artifact),deepcopy(self.metrics)
            if kind=='frame':artifact['frame']['downrange_convention']='Cartesian x'
            elif kind=='position':artifact['samples'][22]['x_m']+=10
            elif kind=='velocity':artifact['samples'][22]['vx_m_s']+=1
            elif kind=='mass':artifact['samples'][22]['mass_kg']+=1
            elif kind=='time':artifact['samples'][22]['time_s']+=.01
            elif kind=='event':artifact['events'].pop()
            elif kind=='metric':metrics['burnout_downrange']['value']+=1
            elif kind=='diagnostic':artifact['diagnostics']['grid_agreement_met']=False
            elif kind=='scope':artifact['not_assessed']=[]
            elif kind=='source':artifact['source_fingerprint']='0'*64
            elif kind=='segments':artifact['solver']['segments'][0]['end_s']+=.1
            elif kind=='cutoff':next(row for row in artifact['samples'] if row['event']=='after_cutoff')['vy_m_s']+=1
            else:artifact['trust_me']=True
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                ascent.validate_artifact(artifact,metrics,self.p,self.artifact['source_fingerprint'])


if __name__ == '__main__':
    unittest.main()
