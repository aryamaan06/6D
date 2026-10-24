"""Run the documented development-only planar-ascent numerical cross-check."""
from hashlib import sha256
import platform
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from test_guided_ascent_reference import CASES, TOLERANCES, reference, solve_ivp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if solve_ivp is None:
        parser.error('Install SciPy in a separate development environment; the application does not require it.')
    results = [reference(case) for case in CASES]
    passed = all(r['max_position_difference_m'] < TOLERANCES['position_m']
                 and r['max_velocity_difference_m_s'] < TOLERANCES['velocity_m_s']
                 and r['max_mass_difference_kg'] < TOLERANCES['mass_kg']
                 and r['grid_agreement_met'] for r in results)
    report = dict(method='Separate SciPy DOP853 five-state equations, including integrated mass',
                  scope='Constructed planar ascent cases; numerical cross-check only, not flight or human validation.',
                  tolerances=TOLERANCES,passed=passed,cases=results,python_version=platform.python_version(),
                  source_sha256={name:sha256((ROOT/path).read_bytes()).hexdigest() for name,path in {'guided_ascent.py':'src/sixd/guided_ascent.py','reference_equations.py':'tests/test_guided_ascent_reference.py'}.items()})
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
