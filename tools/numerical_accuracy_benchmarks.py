"""Independent numerical evidence; development-only NASA CSPICE dependency."""
from dataclasses import replace
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests'),str(ROOT/'tools')]
from published_orbit_benchmarks import _spice
from test_orbital_independent_reference import CASES,reference_errors
from sixd import simulation,orbital_adapter as orbit


def measure():
    spice=_spice()
    rows=[]
    for case in (*CASES,replace(CASES[1],name='circle_eight_periods_refined',steps=16384)):
        artifact=simulation.simulate(case.spec())
        errors=reference_errors(case,artifact)
        elements=[case.semi_major_axis_m*(1-case.eccentricity)/1000,case.eccentricity,
                  *map(math.radians,(case.inclination_deg,case.ascending_node_deg,case.periapsis_argument_deg)),
                  case.mean_anomaly_rad,0.,case.mu_m3_s2/1e9]
        state_errors=[0.,0.];oracle_errors=[0.,0.]
        for sample in artifact['samples']:
            external=[float(x)*1000 for x in spice.conics(elements,sample['time_s'])]
            analytic=case.state(sample['time_s'])
            for i,key in enumerate(('position_m','velocity_m_s')):
                state_errors[i]=max(state_errors[i],math.dist(sample[key],external[3*i:3*i+3]))
                oracle_errors[i]=max(oracle_errors[i],math.dist(analytic[i],external[3*i:3*i+3]))
        # Predeclared synthetic benchmark thresholds; not engineering criteria.
        assert state_errors[0]<.5 and state_errors[1]<.001,(case.name,state_errors)
        assert oracle_errors[0]<1e-5 and oracle_errors[1]<1e-8,(case.name,oracle_errors)
        spec=case.spec();p={k:spec[k] for k in ('mu_m3_s2','exclusion_radius_m','duration_s','steps')}
        for i,axis in enumerate('xyz'):
            p['position_'+axis]=spec['position_m'][i];p['velocity_'+axis]=spec['velocity_m_s'][i]
        criteria=dict(position_tolerance_m=1.,velocity_tolerance_m_s=.01,source='Constructed benchmark criterion')
        _,_,q=orbit.evaluate_with_accuracy(p,criteria)
        rows.append(dict(case=case.name,steps=case.steps,analytic=errors,
            cspice_max_position_difference_m=state_errors[0],cspice_max_velocity_difference_m_s=state_errors[1],
            analytic_cspice_position_difference_m=oracle_errors[0],analytic_cspice_velocity_difference_m_s=oracle_errors[1],
            accuracy_status=q['status'],observed_orders=q['observed_orders'],reason=q['reason']))
    return dict(schema='sixd.numerical-benchmark.v1',source_sha256=simulation.source_fingerprint(),
        method='classical RK4 v2',reference='NASA NAIF CSPICE conics via SpiceyPy',
        spiceypy=spice.__version__,toolkit=spice.tkvrsn('TOOLKIT'),
        source_url='https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/cspice/conics_c.html',
        conditions='Constructed ideal two-body cases; not flight validation or a universal error bound',cases=rows)


if __name__=='__main__':
    result=measure()
    if len(sys.argv)>1:Path(sys.argv[1]).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'cases':len(result['cases']),'passed':True,'source':result['source_sha256']}))
