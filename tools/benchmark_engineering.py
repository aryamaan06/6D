"""Run sourced numerical references against 6D's seven bounded models.

No network, provider calls or production database access occurs in this runner.
The pinned SPICE reference is a development-only dependency; missing references
are explicit failures, never replaced with the implementation under test.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
from hashlib import sha256
import importlib
import json
import os
from pathlib import Path
import platform
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tools'))
MODELS={'ideal_propulsion','static_cantilever','radiative_equilibrium','drag_load','orbital_trajectory','power_energy_budget','attitude_control'}
MODULES=['published_static_benchmarks','published_power_benchmarks','published_control_benchmarks','published_orbit_benchmarks','published_guard_benchmarks']


def digest(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()).hexdigest()


def source_hashes():
    files=list((ROOT/'src/sixd').glob('*.py'))+[Path(__file__)]+[ROOT/'tools'/(name+'.py') for name in MODULES]
    files+=list((ROOT/'examples').glob('*.json'))+[ROOT/'requirements-benchmarks.txt']
    return {str(p.relative_to(ROOT)).replace('\\','/'):sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def run(output=None):
    started=time.perf_counter();before=source_hashes();rows=[];errors=[]
    for name in MODULES:
        try:
            module=importlib.import_module(name)
            checks=module.run_checks()
            for row in checks:
                required={'id','model','source_urls','reference_kind','inputs','expected','actual','tolerance','passed','limitations'}
                if not required<=set(row) or row['model'] not in MODELS or not isinstance(row['passed'],bool):
                    raise ValueError('Invalid benchmark receipt schema in '+name)
                json.dumps(row,allow_nan=False)
            rows.extend(checks)
        except Exception as error:
            errors.append({'module':name,'error_type':type(error).__name__,'message':str(error)})
        print(name+': '+str(sum(r['passed'] for r in rows if r.get('model') in MODELS))+' cumulative passed checks',flush=True)
    if len({row['id'] for row in rows})!=len(rows):raise ValueError('Duplicate benchmark case IDs')
    positive={row['model'] for row in rows if row['passed'] and row['source_urls'] and not row['reference_kind'].startswith('domain_guard')}
    after=source_hashes()
    passed=not errors and all(row['passed'] for row in rows) and positive==MODELS and before==after
    orbit=[row for row in rows if row['model']=='orbital_trajectory' and 'max_position_error_m' in row['actual']]
    warnings=[{'id':row['id'],'max_position_error_m':row['actual']['max_position_error_m'],
               'meaning':'Measured error in this constructed run; passing a broad regression gate does not establish suitability for an engineering criterion.'} for row in orbit]
    report={'schema':'sixd.published-engineering-benchmarks.v1','created_at':datetime.now(timezone.utc).isoformat(),
            'passed':passed,'checks':rows,'errors':errors,'check_count':len(rows),
            'passed_count':sum(row['passed'] for row in rows),'positive_reference_models':sorted(positive),
            'missing_reference_models':sorted(MODELS-positive),'reference_kinds':dict(Counter(row['reference_kind'] for row in rows)),
            'sources':before,'sources_unchanged':before==after,'python':platform.python_version(),
            'elapsed_seconds':round(time.perf_counter()-started,3),'orbital_accuracy_characterization':warnings,
            'paid_model_calls':0,'database_writes':0,
            'limitations':['Finite implementation comparisons within explicit source/model mappings; no real-spacecraft physical validation.',
                           'Source mapping/reference code/tolerance selection assembled by AI and still require independent human review.',
                           'Constructed published-equation cases and rounded worked examples are distinguished in each receipt.',
                           'General control saturation transitions and orbital mission-accuracy guarantees remain unverified.']}
    report['digest']=digest(report)
    destination=Path(output or ROOT/'artifacts/published-benchmarks/summary.json').resolve()
    private=(ROOT/'.local').resolve()
    if destination==private or private in destination.parents:raise ValueError('Benchmark report cannot be written to production storage')
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path)
    args=parser.parse_args();os.environ.pop('NEBIUS_API_KEY',None)
    report=run(args.output)
    print(json.dumps({k:report[k] for k in ['passed','check_count','passed_count','missing_reference_models','errors','elapsed_seconds','digest','paid_model_calls']}))
    raise SystemExit(0 if report['passed'] else 1)
