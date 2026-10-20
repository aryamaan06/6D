from copy import deepcopy
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from sixd import attitude
from sixd.engineering import evaluate_models
from sixd.project_examples import example_projects


def parameters(**changes):
    p = dict(inertia=10,initial_angle=0,initial_rate=0,target_angle=.2,
             proportional_gain=1,derivative_gain=2*math.sqrt(10),max_torque=1,
             disturbance_torque=0,duration=40,steps=512,assessment_start=30,
             angle_numerical_tolerance=1e-6,rate_numerical_tolerance=1e-6)
    p.update(changes)
    return p


class AttitudeTests(unittest.TestCase):
    def test_critical_damping_matches_closed_form_every_sample(self):
        metrics,a = attitude.evaluate(parameters())
        n = math.sqrt(.1)
        for row in a['samples']:
            t=row['time_s']
            self.assertAlmostEqual(row['error_rad'], .2*(1+n*t)*math.exp(-n*t), delta=2e-9)
            self.assertAlmostEqual(row['rate_rad_s'], .2*n*n*t*math.exp(-n*t), delta=1e-9)
        self.assertLess(metrics['max_assessed_error']['value'],.001)
        self.assertEqual(metrics['sampled_saturation_fraction']['value'],0)

    def test_free_rotation_and_constant_external_torque(self):
        for disturbance in (0,.1,-.1):
            p=parameters(inertia=2,initial_angle=.3,initial_rate=.2,target_angle=0,
                         proportional_gain=0,derivative_gain=0,max_torque=0,
                         disturbance_torque=disturbance,duration=4,assessment_start=2,steps=64)
            _,a=attitude.evaluate(p)
            for r in a['samples']:
                t=r['time_s']; acc=disturbance/2
                self.assertAlmostEqual(r['angle_rad'],.3+.2*t+acc*t*t/2,delta=2e-14)
                self.assertAlmostEqual(r['rate_rad_s'],.2+acc*t,delta=2e-14)

    def test_undamped_oscillator_reference_and_refinement(self):
        errors=[]
        for steps in (32,64,128):
            _,a=attitude.evaluate(parameters(inertia=1,proportional_gain=1,derivative_gain=0,
                target_angle=0,initial_angle=.4,duration=2,assessment_start=0,steps=steps,
                angle_numerical_tolerance=.001,rate_numerical_tolerance=.001))
            errors.append(abs(a['samples'][-1]['angle_rad']-.4*math.cos(2)))
        self.assertTrue(all(15 < errors[i]/errors[i+1] < 17 for i in range(2)),errors)

    def test_overdamped_independent_exponential_reference(self):
        _,a=attitude.evaluate(parameters(inertia=1,proportional_gain=2,derivative_gain=3,
            initial_angle=0,target_angle=.2,duration=4,assessment_start=0,steps=256))
        for r in a['samples']:
            t=r['time_s']
            self.assertAlmostEqual(r['error_rad'],.4*math.exp(-t)-.2*math.exp(-2*t),delta=1e-9)

    def test_constant_clipped_torque_has_quadratic_response(self):
        m,a=attitude.evaluate(parameters(inertia=2,initial_angle=0,target_angle=10,
            proportional_gain=1,derivative_gain=0,max_torque=.1,duration=1,assessment_start=0,steps=64))
        for r in a['samples']:
            self.assertTrue(r['saturated'])
            self.assertEqual(r['applied_torque_nm'],.1)
            self.assertAlmostEqual(r['angle_rad'],.025*r['time_s']**2,delta=3e-14)
        self.assertEqual(m['sampled_saturation_fraction']['value'],1)

    def test_saturation_releases_and_reverses(self):
        p=parameters(max_torque=.02,angle_numerical_tolerance=1e-5,rate_numerical_tolerance=1e-5)
        m,a=attitude.evaluate(p)
        self.assertGreater(m['sampled_saturation_fraction']['value'],0)
        self.assertLess(m['sampled_saturation_fraction']['value'],1)
        self.assertLess(min(r['applied_torque_nm'] for r in a['samples']),0)
        self.assertLessEqual(m['max_sampled_applied_torque']['value'],.02)
        self.assertGreater(m['max_sampled_command_torque']['value'],.02)

    def test_disturbance_added_after_actuator_limit(self):
        _,a=attitude.evaluate(parameters(inertia=1,initial_angle=0,target_angle=-10,
            derivative_gain=0,proportional_gain=1,max_torque=.1,disturbance_torque=.3,
            duration=1,steps=64,assessment_start=0))
        self.assertAlmostEqual(a['samples'][-1]['angle_rad'],.1,delta=1e-13)
        self.assertEqual(a['samples'][-1]['applied_torque_nm'],-.1)

    def test_sign_symmetry_and_absolute_metrics(self):
        m,a=attitude.evaluate(parameters())
        n,b=attitude.evaluate(parameters(target_angle=-.2))
        self.assertEqual(m,n)
        for x,y in zip(a['samples'],b['samples']):
            for k in ('error_rad','rate_rad_s','command_torque_nm','applied_torque_nm'):
                self.assertEqual(x[k],-y[k])

    def test_fixed_target_zero_error_is_stationary(self):
        m,a=attitude.evaluate(parameters(initial_angle=.2,target_angle=.2))
        self.assertTrue(all(metric['value']==0 for metric in m.values()))
        self.assertTrue(all(r['angle_rad']==.2 for r in a['samples']))

    def test_window_is_explicit_and_final_endpoint_permitted(self):
        m,a=attitude.evaluate(parameters(assessment_start=40))
        self.assertEqual(m['max_assessed_error'],m['final_error'])
        self.assertEqual(a['diagnostics']['assessment_sample_count'],1)
        _,b=attitude.evaluate(parameters(assessment_start=30.01))
        self.assertGreaterEqual(b['diagnostics']['assessment_first_sample_s'],30.01)

    def test_angles_are_not_wrapped(self):
        _,a=attitude.evaluate(parameters(initial_angle=3,target_angle=-3,duration=1,assessment_start=0))
        self.assertEqual(a['samples'][0]['error_rad'],-6)

    def test_invalid_domains_abstain(self):
        cases=[{'inertia':0},{'inertia':-1},{'proportional_gain':-1},{'derivative_gain':-1},
               {'max_torque':-1},{'duration':0},{'steps':31},{'steps':2049},{'steps':32.5},
               {'steps':True},{'assessment_start':-1},{'assessment_start':41},
               {'angle_numerical_tolerance':0},{'rate_numerical_tolerance':-1},
               {'initial_angle':float('nan')},{'initial_rate':float('inf')},{'duration':1e-323},
               {'proportional_gain':1e308,'inertia':1e-300},{'initial_angle':1e7}]
        for change in cases:
            with self.subTest(change=change),self.assertRaises(ValueError):
                attitude.evaluate(parameters(**change))

    def test_coarse_controller_rejected_even_with_loose_tolerances(self):
        with self.assertRaisesRegex(ValueError,'under-resolved'):
            attitude.evaluate(parameters(steps=32,angle_numerical_tolerance=1e3,rate_numerical_tolerance=1e3))

    def test_grid_disagreement_produces_no_completed_result(self):
        p=example_projects()['attitude_review']
        p['inputs']['angle_numerical_tolerance']['value']=1e-30
        r=evaluate_models(p)['pointing']
        self.assertEqual(r['status'],'invalid_inputs')
        self.assertEqual(r['metrics'],{})
        self.assertNotIn('attitude_response',r)
        self.assertIn('refinement',r['issues'][0])

    def test_wrong_unit_and_missing_binding_abstain(self):
        for change in ('unit','binding'):
            p=example_projects()['attitude_review']
            if change=='unit':p['inputs']['initial_angle']['unit']='deg'
            else:del p['models'][0]['inputs']['inertia']
            self.assertEqual(evaluate_models(p)['pointing']['status'],'invalid_inputs')

    def test_evidence_mutations_rejected(self):
        p=parameters();m,a=attitude.evaluate(p)
        self.assertTrue(attitude.validate_artifact(a,m,p,a['source_fingerprint']))
        for field in ('sample','metric','diagnostic','source','boolean','extra'):
            x,y=deepcopy(a),deepcopy(m)
            if field=='sample':x['samples'][2]['rate_rad_s']+=.001
            if field=='metric':y['final_error']['value']+=.001
            if field=='diagnostic':x['diagnostics']['max_grid_error_difference_rad']=-1
            if field=='source':x['source_fingerprint']='0'*64
            if field=='boolean':x['samples'][0]['time_s']=False
            if field=='extra':x['extra']='untrusted'
            with self.subTest(field=field),self.assertRaises(ValueError):
                attitude.validate_artifact(x,y,p,a['source_fingerprint'])

    def test_input_not_mutated_and_deterministic(self):
        p=parameters();before=deepcopy(p)
        self.assertEqual(attitude.evaluate(p),attitude.evaluate(p))
        self.assertEqual(p,before)

    def test_model_family_remains_separate_from_unsupported_gnc(self):
        p=example_projects()['missing_evidence']
        self.assertEqual(evaluate_models(p)['control']['status'],'not_assessed')

    def test_initial_error_bound_abstains_before_a_completed_artifact(self):
        p=example_projects()['attitude_review']
        changes=dict(inertia=1,initial_angle=-1e-6,target_angle=1e6,initial_rate=.001,
                     proportional_gain=0,derivative_gain=0,max_torque=0,duration=1,steps=32,assessment_start=0)
        for key,value in changes.items():p['inputs'][key]['value']=value
        r=evaluate_models(p)['pointing']
        self.assertEqual(r['status'],'invalid_inputs')
        self.assertNotIn('attitude_response',r)

    def test_nonzero_physics_cannot_silently_underflow_to_stationary(self):
        cases=[dict(inertia=1e-320,proportional_gain=1e-320,initial_angle=1e-10,target_angle=0,
                    initial_rate=0,derivative_gain=0,max_torque=1e-300,disturbance_torque=0,
                    duration=1,steps=128,assessment_start=1,angle_numerical_tolerance=1e-15,rate_numerical_tolerance=1e-15),
               dict(inertia=1e300,disturbance_torque=1e-300,proportional_gain=0,derivative_gain=0,
                    max_torque=0,initial_angle=0,target_angle=0,initial_rate=0,duration=1e300,steps=32,assessment_start=1e300)]
        for change in cases:
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'underflow'):
                attitude.evaluate(parameters(**change))


if __name__=='__main__':unittest.main()
