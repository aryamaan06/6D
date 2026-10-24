"""Bounded planar flight with analytical throttle impulse and serial staging.

The attached vehicle is a point mass. Separation discards only declared lower
stage dry mass with no impulse. Steering is prescribed, not closed-loop GNC.
"""
from hashlib import sha256
import json
import math
from pathlib import Path
import re

_LOADED_SOURCE_FINGERPRINT = sha256(Path(__file__).read_bytes()).hexdigest()
PARAMETERS = dict(payload_mass='kg', reference_area='m^2', drag_coefficient='1',
                  reference_density='kg/m^3', scale_height='m', gravitational_parameter='m^3/s^2',
                  launch_radius='m', coast_duration='s', steps='1', position_numerical_tolerance='m',
                  velocity_numerical_tolerance='m/s', relative_numerical_tolerance='1',
                  pitch_start_time='s', pitch_end_time='s', initial_pitch_angle='rad', final_pitch_angle='rad')
_STAGE_UNITS = dict(dry_mass='kg',propellant_mass='kg',specific_impulse='s',separation_delay='s')
_SEGMENT_UNITS = dict(duration='s',thrust_start='N',thrust_end='N')
METRICS = [
    ('burnout_altitude','m','Altitude at final-stage burnout'),
    ('burnout_speed','m/s','Speed at final-stage burnout'),
    ('burnout_downrange','m','Signed surface arc at final-stage burnout'),
    ('final_altitude','m','Altitude at the final retained state'),
    ('final_speed','m/s','Speed at the final retained state'),
    ('final_downrange','m','Signed surface arc at the final retained state'),
    ('max_sampled_altitude','m','Maximum sampled altitude'),
    ('max_sampled_speed','m/s','Maximum sampled speed'),
    ('max_sampled_dynamic_pressure','Pa','Maximum sampled dynamic pressure'),
    ('max_sampled_drag','N','Maximum sampled drag magnitude'),
    ('max_sampled_acceleration','m/s^2','Maximum sampled net acceleration magnitude'),
    ('burn_duration','s','Sum of powered stage durations, including zero-thrust intervals'),
    ('propellant_consumed','kg','Total propellant consumed by all stages'),
    ('initial_mass','kg','Payload and all initial wet stages'),
    ('final_mass','kg','Payload and retained final-stage dry mass'),
    ('total_duration','s','Flight duration including interstage delays and final coast'),
    ('jettisoned_mass','kg','Discarded nonfinal-stage dry mass'),
]
METRIC_UNITS = {name:unit for name,unit,_ in METRICS}
ASSUMPTIONS = [
    'Serial one-to-four-stage planar point mass, initially at rest at (launch_radius,0); all stage wet masses and payload are carried initially.',
    'Each stage has supplied positive dry/propellant mass and constant specific impulse. Supplied nonnegative thrust is piecewise linear in stage-local time; propellant use is the exact thrust integral divided by Isp times standard gravity.',
    'Burnout is the earliest resolved time at which the stage propellant is exhausted. Remaining supplied thrust schedule is truncated and reported; insufficient total impulse is rejected.',
    'Every nonfinal dry stage is discarded at burnout with no separation impulse. Position and velocity remain continuous; only declared dry mass is removed. A supplied zero-thrust delay precedes the next stage ignition. Final-stage dry mass remains attached.',
    'Central inverse-square gravity, stationary exponential atmosphere and fixed supplied drag coefficient/reference area for the entire attached vehicle; vector drag opposes velocity.',
    'Pitch is prescribed from the local outward radial toward the counterclockwise tangent, with one global linear transition between declared times. No attitude or closed-loop guidance is computed.',
    'RK4 stops exactly at thrust, steering, burnout, separation and ignition boundaries. Three aligned grids assess sampled vector position and velocity; mass is analytical and is never stepped.',
]
NOT_ASSESSED = [
    'Physical validity of supplied engine profiles, specific impulse, masses, atmosphere, fixed aerodynamic coefficient/area and steering programme.',
    'Closed-loop guidance, navigation, attitude, stability, actuator authority, programme feasibility or optimality; three-dimensional flight, rotation, wind, lift and aeroheating.',
    'Separation dynamics, impulse, debris trajectory, collisions, engine startup/shutdown transients, ullage, restart constraints, residual fuel, parallel boosters or crossfeed.',
    'Stage-dependent aerodynamics or geometry, engine pressure/altitude dependence, variable Isp, reserves, surface crossing, reentry, landing and complete launch-to-orbit targeting.',
    'Continuous-time extrema, rigorous numerical error bounds, uncertainty, flight qualification or launch authorization. Retained evidence is consistency-checked, not authenticated.',
]
_G0 = 9.80665
_SCHEMA = 'sixd.staged-ascent.v1'
_SCOPE = 'Sampled three-grid agreement only; not a rigorous numerical error bound or physical validation.'


def parameter_units(bindings):
    """Validate the role layout without inspecting or calculating bound values."""
    if not isinstance(bindings,dict):
        raise ValueError('Staged-ascent bindings must be an object.')
    expected = dict(PARAMETERS)
    stages, segments = set(), {}
    for key in bindings:
        if key in PARAMETERS:
            continue
        m = re.fullmatch(r'stage\.([1-4])\.(dry_mass|propellant_mass|specific_impulse|separation_delay)',key)
        if m:
            stage = int(m[1]);stages.add(stage);expected[key] = _STAGE_UNITS[m[2]];continue
        m = re.fullmatch(r'stage\.([1-4])\.segment\.([1-6])\.(duration|thrust_start|thrust_end)',key)
        if m:
            stage,segment = int(m[1]),int(m[2]);stages.add(stage)
            segments.setdefault(stage,set()).add(segment);expected[key] = _SEGMENT_UNITS[m[3]];continue
        raise ValueError('Unsupported staged-ascent parameter role: '+str(key))
    if not stages or stages != set(range(1,max(stages)+1)):
        raise ValueError('Stages must be contiguous from 1, with one through four stages.')
    for stage in stages:
        for role,unit in _STAGE_UNITS.items():expected[f'stage.{stage}.{role}'] = unit
        indexes = segments.get(stage,set())
        if not indexes or indexes != set(range(1,max(indexes)+1)):
            raise ValueError('Each stage needs contiguous thrust segments starting at 1, at most six.')
        for segment in indexes:
            for role,unit in _SEGMENT_UNITS.items():expected[f'stage.{stage}.segment.{segment}.{role}'] = unit
    if set(bindings) != set(expected):
        raise ValueError('Staged ascent needs all global, stage and thrust-segment roles with no missing bindings.')
    return expected


def _finite(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)):
        raise ValueError('Staged-ascent quantities must be finite numbers.')
    try: result = float(value)
    except OverflowError: raise ValueError('Staged-ascent quantity exceeds the finite range.') from None
    if not math.isfinite(result):raise ValueError('Staged-ascent quantities must be finite numbers.')
    return result


def _stage_count(p):
    return max(int(key.split('.')[1]) for key in p if key.startswith('stage.'))


def _impulse(segment,dt):
    duration = segment['end_s']-segment['start_s']
    fraction = dt/duration
    current = segment['thrust_start_n']+(segment['thrust_end_n']-segment['thrust_start_n'])*fraction
    return dt*(.5*segment['thrust_start_n']+.5*current)


def _root_time(start,end,duration,impulse):
    if impulse == 0:return 0.0
    if start == end:return impulse/start
    scale = max(start,end)
    a,b = start/scale,(end-start)/scale
    q = impulse/(duration*scale)
    discriminant = max(0.0,a*a+2*b*q)
    return duration*(2*q/(a+math.sqrt(discriminant)))


def stage_plan(p):
    """Compute analytical impulse, exhaustion and attached-mass bookkeeping."""
    count = _stage_count(p)
    initial = p['payload_mass']+sum(p[f'stage.{s}.{r}'] for s in range(1,count+1) for r in ('dry_mass','propellant_mass'))
    mass,clock,plan = initial,0.0,[]
    for s in range(1,count+1):
        prefix = f'stage.{s}.'
        dry,fuel,isp,delay = (p[prefix+r] for r in _STAGE_UNITS)
        exhaust,target = isp*_G0,fuel*isp*_G0
        profiles=[]
        for j in range(1,7):
            sp = prefix+f'segment.{j}.'
            if sp+'duration' not in p:break
            profiles.append(dict(segment=j,duration_s=p[sp+'duration'],thrust_start_n=p[sp+'thrust_start'],thrust_end_n=p[sp+'thrust_end']))
        capacity = sum(.5*(r['thrust_start_n']+r['thrust_end_n'])*r['duration_s'] for r in profiles)
        if not all(math.isfinite(x) for x in (initial,mass,exhaust,target,capacity)):
            raise ValueError('Staged-ascent mass or impulse exceeds the finite range.')
        if capacity + 8*math.ulp(max(capacity,target)) < target:
            raise ValueError(f'Stage {s} thrust profile has insufficient impulse to exhaust its declared propellant.')
        used,impulse,burn_segments = 0.0,0.0,[]
        for row in profiles:
            available = .5*(row['thrust_start_n']+row['thrust_end_n'])*row['duration_s']
            remaining = max(0.0,target-impulse)
            if remaining == 0:break
            last = available + 8*math.ulp(max(available,remaining)) >= remaining and available > 0
            # An exactly exhausted declared knot must remain that exact time,
            # rather than a quadratic root a few ulps before the boundary.
            at_knot = last and abs(available-remaining) <= 8*math.ulp(max(available,remaining))
            dt = row['duration_s'] if not last or at_knot else min(row['duration_s'],_root_time(row['thrust_start_n'],row['thrust_end_n'],row['duration_s'],remaining))
            start,end = clock+used,clock+used+dt
            if dt <= 0 or not end > start:
                raise ValueError('Thrust profile cannot resolve a positive stage segment.')
            thrust_end = row['thrust_start_n']+(row['thrust_end_n']-row['thrust_start_n'])*dt/row['duration_s']
            burn_segments.append(dict(stage=s,start_s=start,end_s=end,thrust_start_n=row['thrust_start_n'],thrust_end_n=thrust_end,impulse_start_n_s=impulse,impulse_end_n_s=target if last else impulse+available))
            used += dt
            impulse = target if last else impulse+available
            if last:break
        if not burn_segments or impulse < target:
            raise ValueError(f'Stage {s} fuel exhaustion could not be resolved from its thrust profile.')
        burnout = clock+used
        after_burn = mass-fuel
        post = after_burn-dry if s < count else after_burn
        if not all(math.isfinite(x) and x>0 for x in (used,burnout,after_burn,post)) or not after_burn < mass or s<count and not post < after_burn:
            raise ValueError('Stage timeline or attached mass is outside the resolved positive range.')
        supplied = sum(r['duration_s'] for r in profiles)
        plan.append(dict(stage=s,ignition_time_s=clock,burnout_time_s=burnout,
                         separation_time_s=burnout if s<count else None,next_ignition_time_s=burnout+delay if s<count else None,
                         initial_mass_kg=mass,burnout_mass_kg=after_burn,post_separation_mass_kg=post,
                         dry_mass_kg=dry,propellant_mass_kg=fuel,specific_impulse_s=isp,separation_delay_s=delay,
                         consumed_impulse_n_s=target,planned_profile_duration_s=supplied,used_profile_duration_s=used,
                         unused_profile_duration_s=max(0.0,supplied-used),profile_segments=profiles,burn_segments=burn_segments))
        mass,clock = post,burnout+delay
    return plan


def validate_parameters(parameters):
    parameter_units(parameters)
    p = {key:_finite(value) for key,value in parameters.items()}
    zero = {'payload_mass','drag_coefficient','reference_density','gravitational_parameter','coast_duration','relative_numerical_tolerance','pitch_start_time'}
    angles = {'initial_pitch_angle','final_pitch_angle'}
    for key in PARAMETERS:
        if key in angles:continue
        if p[key] < 0 or p[key] == 0 and key not in zero:
            raise ValueError(key+' must be '+('nonnegative.' if key in zero else 'positive.'))
    if p['steps'] != int(p['steps']) or not 8 <= p['steps'] <= 128:
        raise ValueError('Steps must be an integer from 8 to 128 per nonzero integration segment.')
    if p['relative_numerical_tolerance'] > .01:raise ValueError('Relative numerical tolerance must not exceed 0.01.')
    count = _stage_count(p)
    for key,value in p.items():
        if not key.startswith('stage.'):continue
        allow_zero = key.endswith(('separation_delay','thrust_start','thrust_end'))
        if value < 0 or value == 0 and not allow_zero:
            raise ValueError(key+' must be '+('nonnegative.' if allow_zero else 'positive.'))
    if p[f'stage.{count}.separation_delay'] != 0:
        raise ValueError('Final-stage separation delay must be zero; use final coast duration instead.')
    if any(abs(p[k]) > math.pi/2 for k in angles):raise ValueError('Pitch angles must be within -pi/2..pi/2 radians.')
    try:
        plan = stage_plan(p)
        end = plan[-1]['burnout_time_s']+p['coast_duration']
        if not math.isfinite(end) or end > 10000:raise ValueError('Total staged flight must be resolved and at most 10000 seconds.')
        if not 0 <= p['pitch_start_time'] < p['pitch_end_time'] <= plan[-1]['burnout_time_s']:
            raise ValueError('Steering must satisfy 0 <= pitch start < pitch end <= final burnout.')
        initial_thrust = p['stage.1.segment.1.thrust_start']
        if (abs(p['initial_pitch_angle']) == math.pi/2 or initial_thrust*math.cos(p['initial_pitch_angle'])/plan[0]['initial_mass_kg'] <= p['gravitational_parameter']/p['launch_radius']**2):
            raise ValueError('Initial radial thrust must exceed weight for the immediate-liftoff assumption.')
        operations = _operations(p,plan)
        intervals = sum(op['kind']=='integrate' for op in operations)
        events = sum(op['kind']=='event' for op in operations)
        if intervals*int(p['steps'])*4+events > 8192:
            raise ValueError('The supplied stage/steering profile exceeds 8192 fine-grid retained samples; use fewer intervals or a smaller grid.')
        for op in operations:
            if op['kind']=='integrate':
                a,b = op['start_s'],op['end_s']
                dt = (b-a)/(int(p['steps'])*4)
                if b<=a or a+dt/2 in (a,b) or b-dt/2 in (a,b):
                    raise ValueError('Stage, steering or thrust intervals cannot resolve distinct RK4 times.')
        return p
    except (OverflowError,ZeroDivisionError):raise ValueError('Staged-ascent inputs exceed the resolved finite numerical range.') from None


def _pitch(p,t):
    u = max(0.0,min(1.0,(t-p['pitch_start_time'])/(p['pitch_end_time']-p['pitch_start_time'])))
    return p['initial_pitch_angle']+u*(p['final_pitch_angle']-p['initial_pitch_angle'])


def _context(stage,phase,*,segment=None,mass=None,propellant=None):
    return dict(stage=stage,phase=phase,segment=segment,mass=mass,propellant=propellant)


def _operations(p,plan):
    """One canonical event/state layout, independent of the integration grid."""
    ops=[]
    def event(t,name,ctx,event_stage=None):
        ops.append(dict(kind='event',time_s=t,event=name,event_stage=event_stage or ctx['stage'],ctx=ctx))
    def integrate(start,end,ctx,end_event=None,event_stage=None):
        cuts=sorted({start,end}|{p[k] for k in ('pitch_start_time','pitch_end_time') if start<p[k]<end})
        for a,b in zip(cuts,cuts[1:]):
            label=end_event if b==end else 'pitch_start' if b==p['pitch_start_time'] else 'pitch_end'
            if b>a:ops.append(dict(kind='integrate',start_s=a,end_s=b,ctx=ctx,end_event=label,event_stage=event_stage or ctx['stage']))
            if b in (p['pitch_start_time'],p['pitch_end_time']) and label not in ('pitch_start','pitch_end'):
                event(b,'pitch_start' if b==p['pitch_start_time'] else 'pitch_end',ctx,event_stage)

    first=plan[0]
    event(0.0,'launch',_context(1,'interstage',mass=first['initial_mass_kg'],propellant=first['propellant_mass_kg']))
    for index,stage in enumerate(plan):
        s=stage['stage'];burns=stage['burn_segments'];start=stage['ignition_time_s']
        off=_context(s,'interstage',mass=stage['initial_mass_kg'],propellant=stage['propellant_mass_kg'])
        event(start,'ignition_before',off)
        event(start,'ignition_after',_context(s,'powered',segment=burns[0]))
        if start==0 and p['pitch_start_time']==0:event(start,'pitch_start',_context(s,'powered',segment=burns[0]))
        for j,segment in enumerate(burns):
            ctx=_context(s,'powered',segment=segment)
            cuts=sorted({segment['start_s'],segment['end_s']}|{p[k] for k in ('pitch_start_time','pitch_end_time') if segment['start_s']<p[k]<segment['end_s']})
            for a,b in zip(cuts,cuts[1:]):
                label=('stage_burnout_before' if b==stage['burnout_time_s'] else
                       'thrust_knot_before' if b==segment['end_s'] else
                       'pitch_start' if b==p['pitch_start_time'] else 'pitch_end')
                integrate(a,b,ctx,label)
            if j+1<len(burns):event(segment['end_s'],'thrust_knot_after',_context(s,'powered',segment=burns[j+1]))
        end=stage['burnout_time_s'];last=index==len(plan)-1
        stopped=_context(s,'coast' if last else 'interstage',mass=stage['burnout_mass_kg'],propellant=0.0)
        event(end,'stage_burnout_after',stopped)
        if not last:
            event(end,'separation_before',stopped)
            following=plan[index+1]
            coast=_context(s+1,'interstage',mass=stage['post_separation_mass_kg'],propellant=following['propellant_mass_kg'])
            event(end,'separation_after',coast,s)
            integrate(end,following['ignition_time_s'],coast,'coast_end')
        else:
            if p['coast_duration']:integrate(end,end+p['coast_duration'],stopped,'end')
            else:event(end,'end',stopped)
    return ops


def _physical(p,plan,ctx,t,x,y,vx,vy):
    if not all(math.isfinite(v) for v in (t,x,y,vx,vy)):raise ValueError('Staged-ascent state must remain finite.')
    r,speed=math.hypot(x,y),math.hypot(vx,vy)
    h=r-p['launch_radius'];angle=math.atan2(y,x)
    if r<=0 or h < -1e-8 or h>1e7 or speed>1e5 or abs(angle)>=math.pi/2:
        raise ValueError('Staged ascent left its above-surface domain: altitude 0..1e7 m, speed <=1e5 m/s, within a quarter turn. Surface crossing and landing are not modeled.')
    stage=plan[ctx['stage']-1]
    if ctx['phase']=='powered':
        segment=ctx['segment'];dt=max(0.0,min(t-segment['start_s'],segment['end_s']-segment['start_s']))
        consumed=(segment['impulse_start_n_s'] if t==segment['start_s'] else segment['impulse_end_n_s'] if t==segment['end_s'] else segment['impulse_start_n_s']+_impulse(segment,dt))
        prop=max(0.0,stage['propellant_mass_kg']-consumed/(stage['specific_impulse_s']*_G0))
        if t==stage['burnout_time_s']:prop=0.0
        mass=stage['burnout_mass_kg']+prop
        thrust=(segment['thrust_start_n'] if t==segment['start_s'] else segment['thrust_end_n'] if t==segment['end_s'] else segment['thrust_start_n']+(segment['thrust_end_n']-segment['thrust_start_n'])*(dt/(segment['end_s']-segment['start_s'])))
    else:mass,prop,thrust=ctx['mass'],ctx['propellant'],0.0
    rx,ry=x/r,y/r;pitch=_pitch(p,t)
    cosine=0.0 if abs(pitch)==math.pi/2 else math.cos(pitch)
    tx,ty=cosine*rx-math.sin(pitch)*ry,cosine*ry+math.sin(pitch)*rx
    gravity=p['gravitational_parameter']/r**2
    density=p['reference_density']*math.exp(-h/p['scale_height'])
    pressure=.5*density*speed*speed;drag=pressure*p['drag_coefficient']*p['reference_area']
    dx,dy=(drag*vx/speed,drag*vy/speed) if speed else (0.0,0.0)
    ax,ay=(thrust*tx-dx)/mass-gravity*rx,(thrust*ty-dy)/mass-gravity*ry
    values=dict(altitude_m=h,downrange_m=p['launch_radius']*angle,speed_m_s=speed,
                radial_velocity_m_s=vx*rx+vy*ry,tangential_velocity_m_s=-vx*ry+vy*rx,
                mass_kg=mass,stage_propellant_kg=prop,thrust_n=thrust,pitch_angle_rad=pitch,
                gravity_m_s2=gravity,density_kg_m3=density,dynamic_pressure_pa=pressure,drag_n=drag,
                acceleration_m_s2=math.hypot(ax,ay),ax_m_s2=ax,ay_m_s2=ay)
    if not all(math.isfinite(v) for v in values.values()):raise ValueError('Staged-ascent arithmetic exceeds the finite numerical range.')
    return values


def _sample(p,plan,ctx,t,state,event=None,event_stage=None):
    x,y,vx,vy=state
    return dict(time_s=t,stage=ctx['stage'],phase=ctx['phase'],event=event,
                event_stage=event_stage if event else None,x_m=x,y_m=y,vx_m_s=vx,vy_m_s=vy,
                **_physical(p,plan,ctx,t,x,y,vx,vy))


def _time(op,j,n):
    return op['start_s'] if j==0 else op['end_s'] if j==n else op['start_s']+(op['end_s']-op['start_s'])*j/n


def _integrate(p,n,plan=None):
    plan=plan or stage_plan(p);state=[p['launch_radius'],0.0,0.0,0.0];rows=[]
    for op in _operations(p,plan):
        ctx=op['ctx']
        if op['kind']=='event':
            rows.append(_sample(p,plan,ctx,op['time_s'],state,op['event'],op['event_stage']));continue
        def rhs(t,values):
            f=_physical(p,plan,ctx,t,*values)
            return [values[2],values[3],f['ax_m_s2'],f['ay_m_s2']]
        for j in range(n):
            a,b=_time(op,j,n),_time(op,j+1,n);dt=b-a
            if dt<=0 or a+dt/2 in (a,b):raise ValueError('Time grid cannot resolve distinct RK4 times.')
            k1=rhs(a,state);k2=rhs(a+dt/2,[v+dt*k/2 for v,k in zip(state,k1)])
            k3=rhs(a+dt/2,[v+dt*k/2 for v,k in zip(state,k2)])
            k4=rhs(b,[v+dt*k for v,k in zip(state,k3)])
            state=[v+dt*(a1+2*a2+2*a3+a4)/6 for v,a1,a2,a3,a4 in zip(state,k1,k2,k3,k4)]
            rows.append(_sample(p,plan,ctx,b,state,op['end_event'] if j==n-1 else None,op['event_stage']))
    return rows


def _metrics(p,rows,plan=None):
    plan=plan or stage_plan(p)
    cutoff=next(row for row in reversed(rows) if row['event']=='stage_burnout_before')
    values=dict(burnout_altitude=cutoff['altitude_m'],burnout_speed=cutoff['speed_m_s'],burnout_downrange=cutoff['downrange_m'],
                final_altitude=rows[-1]['altitude_m'],final_speed=rows[-1]['speed_m_s'],final_downrange=rows[-1]['downrange_m'],
                max_sampled_altitude=max(r['altitude_m'] for r in rows),max_sampled_speed=max(r['speed_m_s'] for r in rows),
                max_sampled_dynamic_pressure=max(r['dynamic_pressure_pa'] for r in rows),max_sampled_drag=max(r['drag_n'] for r in rows),
                max_sampled_acceleration=max(r['acceleration_m_s2'] for r in rows),burn_duration=sum(s['used_profile_duration_s'] for s in plan),
                propellant_consumed=sum(s['propellant_mass_kg'] for s in plan),initial_mass=plan[0]['initial_mass_kg'],final_mass=plan[-1]['burnout_mass_kg'],
                total_duration=rows[-1]['time_s'],jettisoned_mass=sum(s['dry_mass_kg'] for s in plan[:-1]))
    return {key:dict(value=value,unit=METRIC_UNITS[key]) for key,value in values.items()}


def _aligned(p,plan,high,n):
    result=[];cursor=0
    for op in _operations(p,plan):
        if op['kind']=='event':result.append(high[cursor]);cursor+=1
        else:result.extend(high[cursor+2*j-1] for j in range(1,n+1));cursor+=2*n
    return result


def _diagnostics(p,grids,plan=None):
    plan=plan or stage_plan(p);levels=[];agreed=True;differences={key:0.0 for key in METRIC_UNITS}
    for i in range(2):
        n=int(p['steps'])*2**i;low,high=grids[i:i+2];aligned=_aligned(p,plan,high,n)
        if len(aligned)!=len(low):raise ValueError('Staged-ascent refinement grids do not align.')
        pdiffs,vdiffs=[],[]
        for a,b in zip(low,aligned):
            if (a['time_s'],a['event'],a['stage']) != (b['time_s'],b['event'],b['stage']):raise ValueError('Staged-ascent refinement event/time alignment is inconsistent.')
            pd=math.hypot(a['x_m']-b['x_m'],a['y_m']-b['y_m']);vd=math.hypot(a['vx_m_s']-b['vx_m_s'],a['vy_m_s']-b['vy_m_s'])
            scale=max(math.hypot(r['x_m']-p['launch_radius'],r['y_m']) for r in (a,b))
            agreed=agreed and pd<=p['position_numerical_tolerance']+p['relative_numerical_tolerance']*scale
            agreed=agreed and vd<=p['velocity_numerical_tolerance']+p['relative_numerical_tolerance']*max(a['speed_m_s'],b['speed_m_s'])
            pdiffs.append(pd);vdiffs.append(vd)
        lm,hm=_metrics(p,low,plan),_metrics(p,high,plan);md={k:abs(lm[k]['value']-hm[k]['value']) for k in METRIC_UNITS}
        for k,d in md.items():differences[k]=max(differences[k],d)
        levels.append(dict(coarse_steps=n,fine_steps=n*2,max_position_difference_m=max(pdiffs),max_velocity_difference_m_s=max(vdiffs),metric_differences=md))
    algebraic={'burn_duration','propellant_consumed','initial_mass','final_mass','total_duration','jettisoned_mass'}
    allowances={}
    for key,metric in _metrics(p,grids[-1],plan).items():
        absolute=p['position_numerical_tolerance'] if metric['unit']=='m' else p['velocity_numerical_tolerance'] if metric['unit']=='m/s' else 0.0
        allowances[key]=0.0 if key in algebraic else max(differences[key],absolute+p['relative_numerical_tolerance']*abs(metric['value']))
    return dict(grid_agreement_met=bool(agreed),reason='Both aligned grid comparisons meet declared vector-state tolerances.' if agreed else 'At least one vector-state grid comparison exceeds declared tolerances; quantitative criteria and downstream use are blocked.',
                max_position_difference_m=max(r['max_position_difference_m'] for r in levels),max_velocity_difference_m_s=max(r['max_velocity_difference_m_s'] for r in levels),
                metric_differences=differences,metric_allowances=allowances,level_differences=levels,scope=_SCOPE)


def _frame(p):
    return dict(id='body_centered_inertial_plane',position_unit='m',velocity_unit='m/s',launch_position=[p['launch_radius'],0.0],launch_velocity=[0.0,0.0],
                pitch_convention='From local outward radial toward counterclockwise tangent.',downrange_convention='launch_radius * atan2(y,x); signed surface arc, not Cartesian displacement.')


def _solver(p,plan):
    return dict(method='classical_rk4',order=4,version='1',mass='analytical_piecewise_linear_thrust_impulse',
                segment_steps=[int(p['steps'])*f for f in (1,2,4)],stage_plan=plan,
                time_grid='pinned_segment_endpoints',staging='dry_mass_drop_without_separation_impulse',standard_gravity_m_s2=_G0)


def _events(rows):
    return [dict(sample_index=i,time_s=r['time_s'],event=r['event'],stage=r['event_stage']) for i,r in enumerate(rows) if r['event']]


def evaluate(parameters):
    p=validate_parameters(parameters);plan=stage_plan(p)
    grids=[_integrate(p,int(p['steps'])*f,plan) for f in (1,2,4)]
    metrics=_metrics(p,grids[-1],plan)
    artifact=dict(schema=_SCHEMA,parameters=p,solver=_solver(p,plan),frame=_frame(p),samples=grids[-1],events=_events(grids[-1]),
                  refinement=dict(coarse_samples=grids[0],middle_samples=grids[1]),diagnostics=_diagnostics(p,grids,plan),
                  assumptions=list(ASSUMPTIONS),not_assessed=list(NOT_ASSESSED),source_fingerprint=_LOADED_SOURCE_FINGERPRINT)
    return metrics,artifact


def metric_allowance(artifact,metric):return artifact['diagnostics']['metric_allowances'][metric]


def _equal(a,b):
    try:return json.dumps(a,sort_keys=True,allow_nan=False,separators=(',',':'))==json.dumps(b,sort_keys=True,allow_nan=False,separators=(',',':'))
    except (TypeError,ValueError):return False


def validate_artifact(artifact,metrics,parameters,source_fingerprint):
    """Consistency check only: retained states are not reintegrated or authenticated."""
    p=validate_parameters(parameters);plan=stage_plan(p)
    fields={'schema','parameters','solver','frame','samples','events','refinement','diagnostics','assumptions','not_assessed','source_fingerprint'}
    if not isinstance(artifact,dict) or set(artifact)!=fields or artifact['schema']!=_SCHEMA:raise ValueError('Invalid staged-ascent artifact schema.')
    if not _equal(artifact['parameters'],p) or not _equal(artifact['solver'],_solver(p,plan)) or not _equal(artifact['frame'],_frame(p)) or artifact['source_fingerprint']!=source_fingerprint:
        raise ValueError('Staged-ascent inputs, source, frame or analytical stage plan disagree.')
    if artifact['assumptions']!=ASSUMPTIONS or artifact['not_assessed']!=NOT_ASSESSED:raise ValueError('Staged-ascent scope is inconsistent.')
    refinement=artifact['refinement']
    if not isinstance(refinement,dict) or set(refinement)!={'coarse_samples','middle_samples'}:raise ValueError('Staged-ascent refinement grids are missing.')
    grids=[refinement['coarse_samples'],refinement['middle_samples'],artifact['samples']];ops=_operations(p,plan)
    for factor,rows in zip((1,2,4),grids):
        n=int(p['steps'])*factor
        size=sum(1 if op['kind']=='event' else n for op in ops)
        if not isinstance(rows,list) or len(rows)!=size:raise ValueError('Staged-ascent retained grid size is inconsistent.')
        cursor=0;state=[p['launch_radius'],0.0,0.0,0.0]
        for op in ops:
            if op['kind']=='event':
                expected=_sample(p,plan,op['ctx'],op['time_s'],state,op['event'],op['event_stage'])
                if not _equal(rows[cursor],expected):raise ValueError('Staged-ascent event, mass drop, cutoff or continuity is inconsistent.')
                cursor+=1
            else:
                for j in range(1,n+1):
                    row=rows[cursor];cursor+=1
                    if not isinstance(row,dict):raise ValueError('Staged-ascent retained sample must be an object.')
                    state=[_finite(row.get(k)) for k in ('x_m','y_m','vx_m_s','vy_m_s')]
                    expected=_sample(p,plan,op['ctx'],_time(op,j,n),state,op['end_event'] if j==n else None,op['event_stage'])
                    if not _equal(row,expected):raise ValueError('Staged-ascent retained time, force, fuel or state fields are inconsistent.')
    if not _equal(artifact['events'],_events(grids[-1])) or not _equal(metrics,_metrics(p,grids[-1],plan)) or not _equal(artifact['diagnostics'],_diagnostics(p,grids,plan)):
        raise ValueError('Staged-ascent metrics, events or diagnostics disagree with retained samples.')
    return True
