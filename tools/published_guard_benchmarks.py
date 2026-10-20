"""Documented adapter gates; these are not external physical validation."""
import math
from copy import deepcopy
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from sixd.engineering import evaluate_models
from sixd.project_examples import example_projects


def _check(identity,template,model_id,role,value,description):
    project=deepcopy(example_projects()[template])
    model=next(m for m in project['models'] if m['id']==model_id)
    input_id=model['inputs'][role];project['inputs'][input_id]['value']=value
    project['models']=[model]
    result=evaluate_models(project)[model_id]
    expected={'status':'invalid_inputs','metrics_empty':True}
    actual={'status':result['status'],'metrics_empty':not result['metrics']}
    return {'id':identity,'model':model['type'],'source_urls':[],
            'reference_kind':'domain_guard_not_physical_validation','inputs':{role:{'value':value,'unit':project['inputs'][input_id]['unit']}},
            'expected':expected,'actual':actual,'issues':result['issues'],'tolerance':{'kind':'exact_status'},
            'passed':actual==expected,'limitations':[description,'This checks a documented sign/range/numerical gate; it does not prove physical applicability.']}


def run_checks():
    power=next(m for m in example_projects()['power_budget']['models'] if m['type']=='power_energy_budget')
    count=next(role for role in power['inputs'] if role.endswith('.count'))
    orbit=example_projects()['orbital_review']
    period=2*math.pi*math.sqrt(orbit['inputs']['position_x']['value']**3/orbit['inputs']['mu_m3_s2']['value'])
    return [
        _check('guard_beam_zero_length','baseline','mount','length',0,'Positive beam length is required.'),
        _check('guard_power_fractional_equipment_count','power_budget',power['id'],count,.5,'Equipment counts are integral; fractional equipment is not silently rounded.'),
        _check('guard_control_underresolved_grid','attitude_review','pointing','duration',1000,'The fixed control grid must resolve the declared dynamics.'),
        _check('guard_orbit_negative_gravitational_parameter','orbital_review','orbit','mu_m3_s2',-1,'Positive gravitational parameter is required for the supported model.'),
        _check('guard_orbit_nine_periods','orbital_review','orbit','duration_s',9*period,'A material excess beyond the eight-period limit remains rejected after the narrow roundoff fix.'),
    ]
