"""Separately written six-state adaptive integration with fuel-root events.

No production timeline, impulse root, RHS or mass helpers are used. Reference
mass/fuel are numerical states, while production integrates their impulse exactly.
"""
from copy import deepcopy
import math
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from sixd import staged_ascent
try:
    import scipy
    from scipy.integrate import solve_ivp
except ImportError:
    solve_ivp=None

TOLERANCES=dict(position_m=.02,velocity_m_s=.001,mass_kg=1e-7,event_time_s=1e-8)


def parameters():
    p=dict(payload_mass=100.,reference_area=.8,drag_coefficient=.4,reference_density=1.225,
           scale_height=8500.,gravitational_parameter=3.986004418e14,launch_radius=6371000.,
           coast_duration=20.,steps=16,position_numerical_tolerance=.5,
           velocity_numerical_tolerance=.02,relative_numerical_tolerance=1e-6,
           pitch_start_time=5.,pitch_end_time=25.,initial_pitch_angle=0.,final_pitch_angle=.45)
    for i,(dry,fuel,isp,gap,segments) in enumerate([(150.,500.,250.,2.,[(30.,22000.,18000.),(45.,18000.,16000.)]),
                                                   (80.,200.,280.,0.,[(20.,6000.,4500.),(100.,4500.,5500.)])],1):
        p.update({f'stage.{i}.dry_mass':dry,f'stage.{i}.propellant_mass':fuel,
                  f'stage.{i}.specific_impulse':isp,f'stage.{i}.separation_delay':gap})
        for j,(dt,a,b) in enumerate(segments,1):
            p.update({f'stage.{i}.segment.{j}.duration':dt,f'stage.{i}.segment.{j}.thrust_start':a,
                      f'stage.{i}.segment.{j}.thrust_end':b})
    return p


def cases():
    base=parameters()
    zero=deepcopy(base);zero['stage.1.separation_delay']=0.
    low=deepcopy(base);low['stage.2.specific_impulse']=220.
    left=deepcopy(base);left['final_pitch_angle']=-.35;left['stage.1.separation_delay']=4.
    return [('nominal_two_stage',base),('coincident_separation_ignition',zero),
            ('reduced_upper_isp',low),('negative_steering_delay',left)]


def reference(name,p):
    stage_ids=sorted({int(key.split('.')[1]) for key in p if key.startswith('stage.')})
    initial=p['payload_mass']+sum(p[f'stage.{i}.dry_mass']+p[f'stage.{i}.propellant_mass'] for i in stage_ids)
    state=[p['launch_radius'],0.,0.,0.,initial,p['stage.1.propellant_mass']]
    time=0.;intervals=[];burnouts={};separations={};ignitions={}

    def rhs(engine,isp):
        def equations(t,z):
            x,y,vx,vy,mass,fuel=z
            radius,speed=math.hypot(x,y),math.hypot(vx,vy)
            u=max(0.,min(1.,(t-p['pitch_start_time'])/(p['pitch_end_time']-p['pitch_start_time'])))
            pitch=p['initial_pitch_angle']+u*(p['final_pitch_angle']-p['initial_pitch_angle'])
            angle=math.atan2(y,x)+pitch
            force=engine(t)
            rho=p['reference_density']*math.exp(-(radius-p['launch_radius'])/p['scale_height'])
            drag=.5*rho*p['drag_coefficient']*p['reference_area']*speed
            central=p['gravitational_parameter']/radius**3
            return [vx,vy,(force*math.cos(angle)-drag*vx)/mass-central*x,
                    (force*math.sin(angle)-drag*vy)/mass-central*y,-force/(isp*9.80665),-force/(isp*9.80665)]
        return equations

    def integrate(start,end,z,engine,isp,stage,phase,events=None):
        # Independently split continuous ODE intervals only for the two supplied
        # pitch derivative knots; mass depletion is located by an adaptive event.
        cuts=sorted({start,end}|{p[k] for k in ('pitch_start_time','pitch_end_time') if start<p[k]<end})
        last=None
        for a,b in zip(cuts,cuts[1:]):
            sol=solve_ivp(rhs(engine,isp),(a,b),z,method='DOP853',rtol=2e-12,atol=1e-10,
                          dense_output=True,max_step=(b-a)/50,events=events)
            assert sol.success,sol.message
            intervals.append(dict(start=a,end=float(sol.t[-1]),stage=stage,phase=phase,solution=sol))
            z=sol.y[:,-1];last=sol
            if sol.status==1:break
        return z,last

    def depleted(t,z):return z[5]
    depleted.terminal=True;depleted.direction=-1

    for i in stage_ids:
        prefix=f'stage.{i}.';isp=p[prefix+'specific_impulse']
        ignitions[i]=(time,list(state));exhausted=False
        for j in range(1,7):
            key=prefix+f'segment.{j}.'
            if key+'duration' not in p:break
            duration=p[key+'duration'];start_force=p[key+'thrust_start'];end_force=p[key+'thrust_end'];start=time
            engine=lambda t,a=start,b=duration,c=start_force,d=end_force:c+(d-c)*(t-a)/b
            state,sol=integrate(time,time+duration,state,engine,isp,i,'powered',depleted)
            time=float(sol.t[-1])
            if sol.status==1:
                exhausted=True;break
        assert exhausted,'Independent fuel event was not reached'
        burnouts[i]=(time,list(state))
        if i!=stage_ids[-1]:
            before=list(state);state=list(state);state[4]-=p[prefix+'dry_mass']
            state[5]=p[f'stage.{i+1}.propellant_mass'];separations[i]=(time,before,list(state))
            gap=p[prefix+'separation_delay']
            if gap:
                state,_=integrate(time,time+gap,state,lambda t:0.,isp,i+1,'interstage')
                time+=gap
    if p['coast_duration']:
        state,_=integrate(time,time+p['coast_duration'],state,lambda t:0.,p[f'stage.{stage_ids[-1]}.specific_impulse'],stage_ids[-1],'coast')

    metrics,artifact=staged_ascent.evaluate(p)
    differences=[];time_diffs=[]
    for row in artifact['samples']:
        event,stage=row['event'],row.get('event_stage') or row['stage']
        if event=='launch':
            expected=[p['launch_radius'],0.,0.,0.,initial,0.]
        elif event in ('stage_burnout_before','stage_burnout_after'):
            et,expected=burnouts[stage];time_diffs.append(abs(et-row['time_s']))
        elif event in ('separation_before','separation_after'):
            et,before,after=separations[stage];expected=before if event.endswith('before') else after;time_diffs.append(abs(et-row['time_s']))
        elif event in ('ignition_before','ignition_after'):
            et,expected=ignitions[stage];time_diffs.append(abs(et-row['time_s']))
        else:
            choices=[s for s in intervals if s['stage']==row['stage'] and s['phase']==row['phase']
                     and s['start']-1e-7<=row['time_s']<=s['end']+1e-7]
            assert choices,(row['time_s'],row['stage'],row['phase'],event)
            expected=choices[0]['solution'].sol(row['time_s'])
        differences.append((math.hypot(expected[0]-row['x_m'],expected[1]-row['y_m']),
                            math.hypot(expected[2]-row['vx_m_s'],expected[3]-row['vy_m_s']),abs(expected[4]-row['mass_kg'])))
    return dict(case=name,parameters=p,max_position_difference_m=float(max(x[0] for x in differences)),
                max_velocity_difference_m_s=float(max(x[1] for x in differences)),max_mass_difference_kg=float(max(x[2] for x in differences)),
                max_event_time_difference_s=float(max(time_diffs)),grid_agreement_met=artifact['diagnostics']['grid_agreement_met'],
                final_mass_kg=metrics['final_mass']['value'],jettisoned_mass_kg=metrics['jettisoned_mass']['value'],
                burnout_altitude_m=metrics['burnout_altitude']['value'],scipy_version=scipy.__version__)


@unittest.skipIf(solve_ivp is None,'SciPy is development-only; use the documented reference environment.')
class StagedAscentReferenceTests(unittest.TestCase):
    def test_separate_ode_mass_fuel_and_event_roots(self):
        for name,p in cases():
            with self.subTest(case=name):
                result=reference(name,p)
                for key,limit in [('max_position_difference_m',TOLERANCES['position_m']),('max_velocity_difference_m_s',TOLERANCES['velocity_m_s']),
                                  ('max_mass_difference_kg',TOLERANCES['mass_kg']),('max_event_time_difference_s',TOLERANCES['event_time_s'])]:
                    self.assertLess(result[key],limit)
                self.assertTrue(result['grid_agreement_met'])


if __name__=='__main__':unittest.main()
