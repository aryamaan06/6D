from copy import deepcopy
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from sixd import powered_flight as flight
from sixd import engineering, lifecycle
from sixd.project_examples import powered_flight_review


def parameters(**changes):
    p={key:value['value'] for key,value in powered_flight_review()['inputs'].items() if key in flight.PARAMETERS}
    p.update(changes)
    return p


class PoweredFlightTests(unittest.TestCase):
    def test_vacuum_rocket_closed_form_at_every_sample(self):
        p=parameters(gravitational_parameter=0,reference_density=0)
        metrics,a=flight.evaluate(p);ve=9.80665*p['specific_impulse'];flow=p['thrust']/ve
        burn=(p['initial_mass']-p['dry_mass'])/flow
        for row in a['samples']:
            t=min(row['time_s'],burn);m=p['initial_mass']-flow*t
            velocity=ve*math.log(p['initial_mass']/m)
            height=ve*(t-m/flow*math.log(p['initial_mass']/m))+velocity*max(0,row['time_s']-burn)
            self.assertAlmostEqual(row['velocity_m_s'],velocity,delta=2e-8)
            self.assertAlmostEqual(row['altitude_m'],height,delta=2e-6)
        self.assertEqual(metrics['propellant_consumed']['value'],300)
        self.assertTrue(a['diagnostics']['grid_agreement_met'])

    def test_cutoff_exact_and_mass_never_below_dry(self):
        p=parameters(initial_mass=987.3,dry_mass=641.7,thrust=19237)
        _,a=flight.evaluate(p)
        before,after=[a['samples'][e['sample_index']] for e in a['events'] if 'cutoff' in e['event']]
        for key in ('time_s','mass_kg','altitude_m','velocity_m_s'):self.assertEqual(before[key],after[key])
        self.assertEqual(before['mass_kg'],p['dry_mass']);self.assertEqual(after['thrust_n'],0)
        self.assertAlmostEqual(before['acceleration_m_s2']-after['acceleration_m_s2'],p['thrust']/p['dry_mass'])
        self.assertTrue(all(row['mass_kg']>=p['dry_mass'] for row in a['samples']))

    def test_zero_coast_ends_before_cutoff_without_extra_segment(self):
        _,a=flight.evaluate(parameters(coast_duration=0))
        self.assertEqual(len(a['samples']),513)
        self.assertEqual(a['samples'][-1]['event'],'before_cutoff')
        self.assertEqual(a['samples'][-1]['mass_kg'],700)

    def test_signed_drag_opposes_descent_above_surface(self):
        _,a=flight.evaluate(parameters(coast_duration=40))
        descending=[r for r in a['samples'] if r['velocity_m_s']<0]
        self.assertTrue(descending)
        self.assertTrue(all(r['drag_n']<0 and r['altitude_m']>0 for r in descending))
        self.assertTrue(all(r['drag_n']*r['velocity_m_s']>=0 for r in a['samples']))

    def test_unforced_vacuum_coast_conserves_specific_energy(self):
        p=parameters(reference_density=0,coast_duration=50)
        _,a=flight.evaluate(p);rows=[r for r in a['samples'] if r['phase']=='coast']
        energy=lambda r:r['velocity_m_s']**2/2-p['gravitational_parameter']/(p['launch_radius']+r['altitude_m'])
        self.assertLess(max(abs(energy(r)-energy(rows[0])) for r in rows),2e-6)

    def test_tight_grid_criteria_retain_diagnostics_and_block_requirements(self):
        p=powered_flight_review()
        for key,value in dict(steps=8,altitude_numerical_tolerance=1e-12,velocity_numerical_tolerance=1e-12,relative_numerical_tolerance=0).items():p['inputs'][key]['value']=value
        results=engineering.evaluate_models(p);r=results['vertical_flight'];self.assertEqual(r['status'],'completed')
        self.assertFalse(r['flight_response']['diagnostics']['grid_agreement_met'])
        v=lifecycle.review_project(p,results)
        for finding in v['findings'].values():self.assertEqual(finding['status'],'not_assessed');self.assertIsNone(finding['evidence'])
        self.assertTrue(lifecycle.verify_review(v))

    def test_criterion_within_numerical_allowance_is_unassessed(self):
        p=powered_flight_review();r=engineering.evaluate_models(p)
        p['inputs']['minimum_burnout_altitude']['value']=r['vertical_flight']['metrics']['burnout_altitude']['value']-.1
        v=lifecycle.review_project(p,r)
        self.assertEqual(v['findings']['burnout_height']['status'],'not_assessed')
        self.assertIn('allowance',v['findings']['burnout_height']['reason'])

    def test_outside_domain_is_input_gap_not_vehicle_failure(self):
        for change in ({'thrust':1000},{'coast_duration':500},{'dry_mass':1000},{'steps':7},{'steps':8.5},
                       {'reference_density':-1},{'relative_numerical_tolerance':.1},{'thrust':float('nan')},{'steps':True}):
            with self.subTest(change=change),self.assertRaises((ValueError,ArithmeticError)):flight.evaluate(parameters(**change))
        p=powered_flight_review();p['inputs']['thrust']['value']=1000
        r=engineering.evaluate_models(p);v=lifecycle.review_project(p,r)
        self.assertEqual(r['vertical_flight']['status'],'invalid_inputs')
        self.assertTrue(all(x['status']=='not_assessed' for x in v['findings'].values()))

    def test_retained_validation_never_integrates(self):
        p=parameters();m,a=flight.evaluate(p)
        with patch.object(flight,'_integrate',side_effect=AssertionError('No history reintegration')):
            self.assertTrue(flight.validate_artifact(a,m,p,a['source_fingerprint']))

    def test_artifact_tampering_detected(self):
        p=parameters();m,a=flight.evaluate(p)
        for kind in ('sample','mass','time','diagnostic','metric','input','source','cutoff','missing_grid','extra_field'):
            b,c=deepcopy(a),deepcopy(m)
            if kind=='sample':b['samples'][22]['altitude_m']+=10
            elif kind=='mass':b['samples'][22]['mass_kg']+=1
            elif kind=='time':b['samples'][22]['time_s']+=.1
            elif kind=='diagnostic':b['diagnostics']['metric_allowances']['burnout_altitude']=0
            elif kind=='metric':c['final_velocity']['value']+=1
            elif kind=='input':b['parameters']['thrust']+=1
            elif kind=='source':b['source_fingerprint']='0'*64
            elif kind=='cutoff':b['samples'][513]['velocity_m_s']+=1
            elif kind=='missing_grid':b['refinement'].pop('coarse_samples')
            else:b['trust_me']=True
            with self.subTest(kind=kind),self.assertRaises(ValueError):flight.validate_artifact(b,c,p,a['source_fingerprint'])


if __name__=='__main__':unittest.main()
