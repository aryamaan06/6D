"""Separate development-only staged-ascent numerical/event cross-check."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'))
from test_staged_ascent_reference import cases,reference,TOLERANCES,solve_ivp


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if solve_ivp is None:parser.error('SciPy is required only in the separate development environment.')
    results=[reference(name,p) for name,p in cases()]
    pairs=[('max_position_difference_m','position_m'),('max_velocity_difference_m_s','velocity_m_s'),('max_mass_difference_kg','mass_kg'),('max_event_time_difference_s','event_time_s')]
    passed=all(r['grid_agreement_met'] and all(r[key]<TOLERANCES[tolerance] for key,tolerance in pairs) for r in results)
    report=dict(method='Separate SciPy DOP853 six-state ODE with numerical mass/fuel and terminal fuel-exhaustion events',
                scope='Constructed serial-stage cases; different numerical implementation, not flight or human validation.',
                passed=passed,tolerances=TOLERANCES,cases=results,python_version=platform.python_version(),
                source_sha256={label:sha256((ROOT/path).read_bytes()).hexdigest() for label,path in {'staged_ascent.py':'src/sixd/staged_ascent.py','reference_equations.py':'tests/test_staged_ascent_reference.py'}.items()})
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report));return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
