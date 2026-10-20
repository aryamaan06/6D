"""Power accounting against published energy numbers and explicit schedules.

Expected values are externally stated textbook totals converted to SI, or a
literal independently summed schedule. Neither imports production formulas.
These check accounting, not qualification of spacecraft electrical hardware.
"""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from sixd.engineering import evaluate_models

TEXTBOOK='https://openstax.org/books/university-physics-volume-2/pages/9-5-electrical-energy-and-power'
SI='https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-4-two-classes-si-units-and-si-prefixes'
NASA='https://www.nasa.gov/smallsat-institute/sst-soa/power-subsystems/'


def _project(modes,energy,battery,bus):
    records={'usable_battery_energy':(energy,'J'),'max_battery_power':(battery,'W'),'bus_power_limit':(bus,'W')}
    for i,(identity,duration,generation,loads) in enumerate(modes,1):
        prefix=f'mode.{i}.{identity}.'
        records[prefix+'duration']=(duration,'s');records[prefix+'generation']=(generation,'W')
        for name,power,count in loads:
            records[prefix+'load.'+name+'.power']=(power,'W')
            records[prefix+'load.'+name+'.count']=(count,'1')
    return {'inputs':{key:{'value':value,'unit':unit,'source':'Published benchmark mapping or declared constructed schedule; no measured space hardware data.'} for key,(value,unit) in records.items()},
            'models':[{'id':'power','type':'power_energy_budget','inputs':{key:key for key in records}}]}


def _row(identity,kind,project,expected,source,limits):
    actual=evaluate_models(project)['power']
    checks={}
    for name,reference in expected.items():
        measured=actual['metrics'].get(name)
        difference=abs(measured['value']-reference['value']) if measured else None
        allowance=max(1e-6,abs(reference['value'])*1e-12)
        checks[name]={'absolute_error':difference,'allowance':allowance,
                      'passed':measured is not None and measured['unit']==reference['unit'] and difference<=allowance}
    return {'id':identity,'model':'power_energy_budget','source_urls':source,'reference_kind':kind,
            'source_section':'OpenStax University Physics Volume 2, §9.5, Example 9.10 and energy conversion; NIST SI table; NASA power chapter is spacecraft scope context only.',
            'inputs':project['inputs'],'expected':expected,'actual':{name:actual['metrics'].get(name) for name in expected},
            'actual_status':actual['status'],'tolerance':{'absolute':1e-6,'relative':1e-12},'checks':checks,
            'passed':actual['status']=='completed' and all(check['passed'] for check in checks.values()),
            'limitations':limits}


def run_checks():
    rows=[]
    for label,watts,published_kwh in [('incandescent',100,109.5),('led',20,21.90)]:
        # The source states the annual energy totals. Convert those stated
        # totals to joules; do not derive the reference from the product path.
        energy_j=394200000 if label=='incandescent' else 78840000
        p=_project([(label,3*3600*365,0,[('load',watts,1)])],energy=energy_j,battery=watts,bus=watts)
        rows.append(_row('power-openstax-9-10-'+label,'published_worked_example',p,
            {'total_load_energy':{'value':energy_j,'unit':'J'},'peak_load_power':{'value':watts,'unit':'W'}},[TEXTBOOK,SI],
            [f'Textbook states {published_kwh} kWh; 1 kWh = 3600000 J. Aggregated on-time maps to a single supplied constant-load interval.',
             'Household example checks the same energy-accounting arithmetic; it is not a spacecraft power-system design or battery validation.',
             'Zero generation, capacity values and battery policy are benchmark wrappers, not values claimed by the textbook.']))
    schedule=[('dark',60,0,[('payload',4,2),('cpu',2,1)]),('bright',120,20,[('payload',4,1)])]
    p=_project(schedule,energy=1000,battery=8,bus=15)
    expected={'peak_load_power':{'value':10,'unit':'W'},'total_load_energy':{'value':1080,'unit':'J'},
              'total_generated_energy':{'value':2400,'unit':'J'},'battery_energy_required':{'value':600,'unit':'J'},
              'battery_energy_margin':{'value':400,'unit':'J'},'minimum_bus_power_margin':{'value':5,'unit':'W'},
              'minimum_battery_power_margin':{'value':-2,'unit':'W'},'minimum_power_margin':{'value':-2,'unit':'W'},
              'minimum_generation_margin':{'value':-10,'unit':'W'},'max_battery_power_required':{'value':10,'unit':'W'},
              'total_duration':{'value':180,'unit':'s'},'surplus_generation_energy':{'value':1920,'unit':'J'}}
    rows.append(_row('power-piecewise-independent-budget','reference_equation_constructed',p,expected,[TEXTBOOK,SI,NASA],
        ['Constructed 60s×10W +120s×4W schedule evaluated by literal independent arithmetic; not a published spacecraft design.',
         'Only the dark interval draws the declared battery budget. Surplus generation receives no recharge credit under the declared 6D accounting policy.',
         'Positive energy margin coexists with a negative battery-power margin; adequate joules do not imply adequate watts.']))
    return rows


if __name__=='__main__':
    import json
    rows=run_checks();print(json.dumps(rows,indent=2));raise SystemExit(0 if all(r['passed'] for r in rows) else 1)
