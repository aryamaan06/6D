"""Audit recorded reuse against an independent dependency-closure traversal.

This audit does not use production reuse keys or impact helpers and executes no
physics. It catches unsafe reuse after source/definition edits even when a fresh
calculation happens to return the same numbers.
"""
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
import argparse
import json
import math
from pathlib import Path
from recalculation_cases import build_cases


def canonical_dependencies(project, target):
    models={model['id']:model for model in project['models']}
    visited=set();pending=[target]
    while pending:
        identity=pending.pop()
        if identity in visited:continue
        visited.add(identity)
        pending.extend(link['model_id'] for link in models[identity].get('links',{}).values())
    definitions={identity:deepcopy(models[identity]) for identity in sorted(visited)}
    inputs={key for model in definitions.values() for key in model['inputs'].values()}
    records={key:deepcopy(project['inputs'][key]) for key in sorted(inputs)}
    for record in records.values():
        value=record['value']
        record['value']={'exact_rational':str(Fraction(value)),
                         'negative_zero':value==0 and isinstance(value,float) and math.copysign(1,value)<0}
    return {'models':definitions,'inputs':records}


def unsafe_reuse(case, reused):
    before={model['id'] for model in case['before']['models']}
    return [identity for identity in reused if identity not in before
            or canonical_dependencies(case['before'],identity)!=canonical_dependencies(case['after'],identity)]


def audit(directory):
    directory=Path(directory)
    summary=json.loads((directory/'summary.json').read_text(encoding='utf-8'))
    summary_digest=summary.pop('digest')
    encoded=json.dumps(summary,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
    if sha256(encoded.encode()).hexdigest()!=summary_digest:raise ValueError('Summary digest mismatch')
    raw=(directory/'cases.jsonl').read_bytes()
    if sha256(raw).hexdigest()!=summary['ledger_sha256']:raise ValueError('Case ledger digest mismatch')
    rows=[json.loads(line) for line in raw.decode().splitlines()]
    cases=list(build_cases(summary['seed'],summary['requested_cases']))
    if len(rows)!=len(cases):raise ValueError('Case count mismatch')
    failures=[];checked=0
    for case,row in zip(cases,rows):
        if case['id']!=row['id']:raise ValueError('Case identity mismatch')
        for field in ['before','after']:
            serialized=json.dumps(case[field],sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
            if row.get(field+'_digest')!=sha256(serialized.encode()).hexdigest():raise ValueError('Generated case snapshot differs: '+row['id'])
        if row['outcome']!='equivalent':continue
        bad=unsafe_reuse(case,row['reused_model_ids']);checked+=len(row['reused_model_ids'])
        if bad:failures.append({'id':case['id'],'unsafe_reused_model_ids':bad})
    result={'schema':'sixd.reuse-dependency-audit.v1','summary_digest':summary_digest,'passed':not failures,
            'generated_cases':len(cases),'reused_models_checked':checked,'failures':failures,
            'audit_source_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
            'method':'Independent closure traversal and Fraction-based exact input identity; no production reuse/impact helpers.',
            'paid_model_calls':0}
    (directory/'reuse-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    result=audit(parser.parse_args().directory);print(json.dumps(result));raise SystemExit(0 if result['passed'] else 1)
