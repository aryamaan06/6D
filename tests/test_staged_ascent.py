"""Analytic impulse/mass, staging continuity and retained-evidence checks."""
from copy import deepcopy
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from sixd import staged_ascent as ascent


def parameters(**changes):
    p=dict(payload_mass=100,reference_area=.8,drag_coefficient=.4,reference_density=1.225,
           scale_height=8500,gravitational_parameter=3.986004418e14,launch_radius=6371000,
           coast_duration=20,steps=16,position_numerical_tolerance=.5,velocity_numerical_tolerance=.02,
           relative_numerical_tolerance=1e-6,pitch_start_time=5,pitch_end_time=25,initial_pitch_angle=0,final_pitch_angle=.45)
    for s,dry,fuel,isp,delay,segments in [
        (1,150,500,250,2,[(30,22000,18000),(45,18000,16000)]),
        (2,80,200,280,0,[(20,6000,4500),(100,4500,5500)]),
    ]:
        for key,value in dict(dry_mass=dry,propellant_mass=fuel,specific_impulse=isp,separation_delay=delay).items():p[f'stage.{s}.{key}']=value
        for j,row in enumerate(segments,1):
            for key,value in zip(('duration','thrust_start','thrust_end'),row):p[f'stage.{s}.segment.{j}.{key}']=value
    p.update(changes)
    return p


def single(**changes):
    p={k:v for k,v in parameters().items() if not k.startswith('stage.')}
    p.update(reference_density=0,gravitational_parameter=0,initial_pitch_angle=0,final_pitch_angle=0,steps=32)
    for key,value in dict(dry_mass=50,propellant_mass=200,specific_impulse=250,separation_delay=0).items():p['stage.1.'+key]=value
    for key,value in dict(duration=100,thrust_start=8000,thrust_end=8000).items():p['stage.1.segment.1.'+key]=value
    p.update(changes)
    return p


class StagedAscentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=parameters();cls.metrics,cls.artifact=ascent.evaluate(cls.p)

    def test_layout_requires_complete_contiguous_stages_and_segments(self):
        units=ascent.parameter_units(self.p)
        self.assertEqual(units['stage.2.segment.2.thrust_end'],'N')
        self.assertEqual(units['stage.1.propellant_mass'],'kg')
        variants=[]
        p=deepcopy(self.p);del p['stage.1.dry_mass'];variants.append(p)
        p=deepcopy(self.p);p['stage.5.dry_mass']=1;variants.append(p)
        p=deepcopy(self.p);p['stage.1.segment.4.duration']=1;variants.append(p)
        p=deepcopy(self.p);p['unexpected']=1;variants.append(p)
        for p in variants:
            with self.assertRaises(ValueError):ascent.parameter_units(p)

    def test_linear_thrust_fuel_root_matches_independent_quadratic(self):
        p=single(**{'stage.1.segment.1.thrust_start':10000,'stage.1.segment.1.thrust_end':20000,'stage.1.propellant_mass':300})
        plan=ascent.stage_plan(ascent.validate_parameters(p))[0]
        target=300*250*9.80665
        expected=(-10000+math.sqrt(10000**2+200*target))/100
        self.assertAlmostEqual(plan['used_profile_duration_s'],expected,delta=2e-14)
        self.assertAlmostEqual(plan['consumed_impulse_n_s'],target,delta=1e-8)
        self.assertAlmostEqual(plan['unused_profile_duration_s'],100-expected,delta=2e-14)
        _,a=ascent.evaluate(p)
        cutoff=next(r for r in a['samples'] if r['event']=='stage_burnout_before')
        self.assertEqual(cutoff['stage_propellant_kg'],0)
        self.assertEqual(cutoff['mass_kg'],150)

    def test_single_stage_constant_thrust_matches_closed_form_vacuum(self):
        p=single();m,a=ascent.evaluate(p);ve=250*9.80665;flow=8000/ve;burn=200/flow
        for row in a['samples']:
            t=min(row['time_s'],burn);mass=350-flow*t
            v=ve*math.log(350/mass)
            h=ve*(t-mass/flow*math.log(350/mass))+v*max(0,row['time_s']-burn)
            self.assertAlmostEqual(row['speed_m_s'],v,delta=5e-6)
            self.assertAlmostEqual(row['altitude_m'],h,delta=.001)
            self.assertEqual(row['y_m'],0)
        self.assertEqual(m['initial_mass']['value'],350)
        self.assertEqual(m['final_mass']['value'],150)
        self.assertEqual(m['jettisoned_mass']['value'],0)

    def test_two_stage_vacuum_velocity_is_sum_of_ideal_rocket_equations(self):
        p=parameters(reference_density=0,gravitational_parameter=0,initial_pitch_angle=0,final_pitch_angle=0,steps=64)
        m,a=ascent.evaluate(p)
        expected=250*9.80665*math.log(1030/530)+280*9.80665*math.log(380/180)
        self.assertAlmostEqual(m['burnout_speed']['value'],expected,delta=2e-6)
        self.assertAlmostEqual(m['final_speed']['value'],expected,delta=2e-6)
        self.assertEqual(m['propellant_consumed']['value']+m['jettisoned_mass']['value']+m['final_mass']['value'],m['initial_mass']['value'])
        before=next(r for r in a['samples'] if r['event']=='separation_before')
        after=next(r for r in a['samples'] if r['event']=='separation_after')
        for key in ('time_s','x_m','y_m','vx_m_s','vy_m_s'):self.assertEqual(before[key],after[key])
        self.assertEqual(before['mass_kg']-after['mass_kg'],150)
        self.assertEqual(after['stage'],2)
        self.assertEqual(after['event_stage'],1)
        self.assertEqual(after['stage_propellant_kg'],200)

    def test_discontinuous_throttle_preserves_mass_and_kinematic_state(self):
        p=parameters(**{'stage.1.segment.2.thrust_start':24000})
        _,a=ascent.evaluate(p)
        before=next(r for r in a['samples'] if r['event']=='thrust_knot_before' and r['stage']==1)
        after=next(r for r in a['samples'] if r['event']=='thrust_knot_after' and r['stage']==1)
        for key in ('time_s','x_m','y_m','vx_m_s','vy_m_s','mass_kg','stage_propellant_kg'):self.assertEqual(before[key],after[key])
        self.assertEqual(before['thrust_n'],18000)
        self.assertEqual(after['thrust_n'],24000)

    def test_zero_and_nonzero_delays_have_explicit_ordered_event_sides(self):
        for delay in (0,3):
            p=parameters(**{'stage.1.separation_delay':delay});m,a=ascent.evaluate(p)
            plan=a['solver']['stage_plan'];self.assertEqual(plan[1]['ignition_time_s']-plan[0]['burnout_time_s'],delay)
            self.assertAlmostEqual(m['total_duration']['value'],m['burn_duration']['value']+delay+20,delta=3e-14)
            for stage in (1,2):
                before=next(r for r in a['samples'] if r['event']=='stage_burnout_before' and r['stage']==stage)
                after=next(r for r in a['samples'] if r['event']=='stage_burnout_after' and r['stage']==stage)
                for key in ('time_s','x_m','y_m','vx_m_s','vy_m_s','mass_kg'):self.assertEqual(before[key],after[key])
                self.assertEqual(after['thrust_n'],0)
            for rows in (a['refinement']['coarse_samples'],a['refinement']['middle_samples'],a['samples']):
                self.assertTrue(all(x['time_s']<=y['time_s'] for x,y in zip(rows,rows[1:])))
                self.assertEqual(next(r['time_s'] for r in rows if r['event']=='stage_burnout_before'),plan[0]['burnout_time_s'])

    def test_steering_boundary_inside_interstage_coast_is_retained_exactly(self):
        base=parameters();end=ascent.stage_plan(base)[0]['burnout_time_s']
        p=parameters(pitch_start_time=end+.5,pitch_end_time=end+1.5)
        _,a=ascent.evaluate(p)
        for key,event in (('pitch_start_time','pitch_start'),('pitch_end_time','pitch_end')):
            row=next(r for r in a['samples'] if r['event']==event)
            self.assertEqual(row['time_s'],p[key]);self.assertEqual(row['phase'],'interstage');self.assertEqual(row['thrust_n'],0)

    def test_mirrored_steering_reflects_complete_multistage_trajectory(self):
        _,other=ascent.evaluate(parameters(final_pitch_angle=-.45))
        for a,b in zip(self.artifact['samples'],other['samples']):
            for field in ('x_m','vx_m_s','altitude_m','speed_m_s','mass_kg','thrust_n'):self.assertEqual(a[field],b[field])
            for field in ('y_m','vy_m_s','downrange_m'):self.assertEqual(a[field],-b[field])

    def test_zero_air_final_coast_conserves_energy_and_angular_momentum(self):
        p=parameters(reference_density=0,steps=32);_,a=ascent.evaluate(p)
        rows=[r for r in a['samples'] if r['phase']=='coast']
        def energy(r):return .5*r['speed_m_s']**2-p['gravitational_parameter']/math.hypot(r['x_m'],r['y_m'])
        def momentum(r):return r['x_m']*r['vy_m_s']-r['y_m']*r['vx_m_s']
        for row in rows:
            self.assertAlmostEqual(energy(row)/energy(rows[0]),1,delta=1e-11)
            self.assertAlmostEqual(momentum(row)/momentum(rows[0]),1,delta=1e-11)

    def test_numerical_gap_is_explicit_and_blocks_supported_accuracy(self):
        _,a=ascent.evaluate(parameters(steps=8,position_numerical_tolerance=1e-12,velocity_numerical_tolerance=1e-12,relative_numerical_tolerance=0))
        self.assertFalse(a['diagnostics']['grid_agreement_met'])
        self.assertGreater(ascent.metric_allowance(a,'burnout_altitude'),0)

    def test_three_and_four_serial_stages_preserve_complete_mass_budget(self):
        for count in (3,4):
            p={k:v for k,v in single().items() if not k.startswith('stage.')}
            p['payload_mass']=5;p['coast_duration']=5;p['steps']=64
            expected=0.0;mass=5+count*30
            for stage in range(1,count+1):
                for key,value in dict(dry_mass=10,propellant_mass=20,specific_impulse=250,separation_delay=0).items():p[f'stage.{stage}.{key}']=value
                for key,value in dict(duration=100,thrust_start=2000,thrust_end=2000).items():p[f'stage.{stage}.segment.1.{key}']=value
                expected+=250*9.80665*math.log(mass/(mass-20));mass-=30 if stage<count else 20
            m,a=ascent.evaluate(p)
            self.assertEqual(m['final_mass']['value'],15)
            self.assertEqual(m['initial_mass']['value'],5+count*30)
            self.assertEqual(m['jettisoned_mass']['value'],(count-1)*10)
            self.assertAlmostEqual(m['burnout_speed']['value'],expected,delta=2e-5)
            self.assertEqual(sum(e['event']=='separation_after' for e in a['events']),count-1)

    def test_fuel_exhaustion_at_a_declared_thrust_knot_pins_its_time(self):
        for initial,final,duration,isp in ((1000,2000,20,275.3),(22000,18000,30,250),(1700,1100,23.7,213.4)):
            fuel=.5*(initial+final)*duration/(isp*9.80665)
            p=single(**{'stage.1.propellant_mass':fuel,'stage.1.specific_impulse':isp,
                        'stage.1.segment.1.duration':duration,'stage.1.segment.1.thrust_start':initial,
                        'stage.1.segment.1.thrust_end':final,'pitch_start_time':1,'pitch_end_time':2})
            plan=ascent.stage_plan(ascent.validate_parameters(p))[0]
            self.assertEqual(plan['burnout_time_s'],duration)
            self.assertEqual(plan['unused_profile_duration_s'],0)

    def test_invalid_profiles_and_outside_domain_inputs_are_rejected(self):
        variants=[{'stage.1.propellant_mass':100000},{'stage.1.segment.1.thrust_start':0},
                  {'stage.1.segment.1.thrust_end':-1},{'stage.2.separation_delay':2},
                  {'payload_mass':-1},{'stage.1.dry_mass':0},{'steps':129},
                  {'steps':8.5},{'final_pitch_angle':2},{'initial_pitch_angle':math.pi/2},
                  {'pitch_end_time':10000},{'pitch_start_time':25}, {'payload_mass':True}, {'reference_density':float('nan')}]
        for change in variants:
            with self.subTest(change=change),self.assertRaises(ValueError):ascent.validate_parameters(parameters(**change))

    def test_retained_validator_does_not_integrate_and_rejects_tampering(self):
        with patch.object(ascent,'_integrate',side_effect=AssertionError('Reading must not integrate')):
            self.assertTrue(ascent.validate_artifact(self.artifact,self.metrics,self.p,self.artifact['source_fingerprint']))
        for kind in ('sample','mass','stage','event','frame','plan','diagnostic','source','scope','refinement'):
            with self.subTest(kind=kind):
                a=deepcopy(self.artifact)
                if kind=='sample':a['samples'][5]['x_m']+=1
                elif kind=='mass':next(r for r in a['samples'] if r['event']=='separation_after')['mass_kg']+=1
                elif kind=='stage':a['samples'][5]['stage']=4
                elif kind=='event':a['events'][1]['event']='made_up'
                elif kind=='frame':a['frame']['launch_position'][0]+=1
                elif kind=='plan':a['solver']['stage_plan'][0]['dry_mass_kg']+=1
                elif kind=='diagnostic':a['diagnostics']['grid_agreement_met']=False
                elif kind=='source':a['source_fingerprint']='0'*64
                elif kind=='scope':a['not_assessed']=[]
                elif kind=='refinement':a['refinement']['coarse_samples'][3]['mass_kg']+=1
                with self.assertRaises(ValueError):ascent.validate_artifact(a,self.metrics,self.p,self.artifact['source_fingerprint'])


if __name__=='__main__':unittest.main()
