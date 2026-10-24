"""Rerun existing independent numerical references under canonical source bytes.

Development-only SciPy/SpiceyPy are required; the application remains stdlib-only.
Historical reference files and stored receipts are never overwritten.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dependency-directory',type=Path,action='append',default=[])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    sys.path[:0]=[str(p.resolve()) for p in args.dependency_directory]+[str(ROOT/'src'),str(ROOT/'tests'),str(ROOT/'tools')]
    from check_source_consistency import check
    from numerical_accuracy_benchmarks import measure
    import test_powered_flight_reference as vertical
    import test_guided_ascent_reference as planar
    import test_staged_ascent_reference as staged
    import scipy
    if not check(ROOT)['passed']:raise SystemExit('Canonical source check failed; no reference result was published.')
    if any(module.solve_ivp is None for module in (vertical,planar,staged)):
        raise SystemExit('SciPy development dependency unavailable; no substitute reference was used.')
    results={
        'orbital':measure(),
        'vertical':{'method':'Separate SciPy DOP853 three-state ODE with integrated mass',
            'tolerances':{'altitude_m':.0002,'velocity_m_s':.000002,'mass_kg':.00000001},
            'cases':[vertical.reference(c) for c in vertical.CASES]},
        'planar':{'method':'Separate SciPy DOP853 five-state ODE with integrated mass',
            'tolerances':planar.TOLERANCES,'cases':[planar.reference(c) for c in planar.CASES]},
        'staged':{'method':'Separate SciPy DOP853 six-state ODE with terminal fuel events',
            'tolerances':staged.TOLERANCES,'cases':[staged.reference(n,p) for n,p in staged.cases()]}}
    pairs={'vertical':[('max_altitude_difference_m','altitude_m'),('max_velocity_difference_m_s','velocity_m_s'),('max_mass_difference_kg','mass_kg')],
        'planar':[('max_position_difference_m','position_m'),('max_velocity_difference_m_s','velocity_m_s'),('max_mass_difference_kg','mass_kg')],
        'staged':[('max_position_difference_m','position_m'),('max_velocity_difference_m_s','velocity_m_s'),('max_mass_difference_kg','mass_kg'),('max_event_time_difference_s','event_time_s')]}
    for group,fields in pairs.items():
        r=results[group]
        r['passed']=all(all(c[k]<r['tolerances'][t] for k,t in fields) and c.get('grid_agreement_met',True) for c in r['cases'])
    results['orbital']['passed']=True  # measure() asserts its predeclared thresholds.
    from sixd import lifecycle
    source_paths=[ROOT/'src/sixd'/name for name in sorted(lifecycle.VERIFICATION_SOURCE_NAMES)]
    source_paths += [Path(m.__file__) for m in (vertical,planar,staged)]
    source_paths += [ROOT/'tests/test_orbital_independent_reference.py', ROOT/'tools/numerical_accuracy_benchmarks.py', ROOT/'tools/published_orbit_benchmarks.py', Path(__file__).resolve()]
    report={'schema':'sixd.canonical-reference-recheck.v1','passed':all(v['passed'] for v in results.values()),
        'python_version':platform.python_version(),'scipy_version':scipy.__version__,
        'case_count':sum(len(v['cases']) for v in results.values()),'groups':results,
        'source_sha256':{p.relative_to(ROOT).as_posix():sha256(p.read_bytes()).hexdigest() for p in source_paths},
        'conditions':'Constructed numerical cases and separate reference algorithms; no flight, customer or independent human validation.',
        'historical_records_unchanged':True,'paid_model_calls':0}
    args.output.write_bytes((json.dumps(report,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'passed':report['passed'],'case_count':report['case_count'],'python':report['python_version'],'groups':{k:len(v['cases']) for k,v in results.items()}}))
    return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
