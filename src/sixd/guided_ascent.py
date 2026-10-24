"""Bounded planar ascent with a declared open-loop pitch programme.

The thrust direction is prescribed, not solved by a guidance or attitude loop.
RK4 grids stop exactly at every steering knot and at fuel exhaustion. Retained
samples establish consistency and sampled grid agreement, not physical validity
or a rigorous global error bound.
"""
from hashlib import sha256
import json
import math
from pathlib import Path

from . import powered_flight

_LOADED_SOURCE_FINGERPRINT = sha256(Path(__file__).read_bytes()).hexdigest()
PARAMETERS = dict(powered_flight.PARAMETERS) | {
    'pitch_start_time': 's', 'pitch_end_time': 's',
    'initial_pitch_angle': 'rad', 'final_pitch_angle': 'rad',
}
METRICS = [
    ('burnout_altitude', 'm', 'Altitude above the launch surface at burnout'),
    ('burnout_speed', 'm/s', 'Inertial speed at burnout'),
    ('burnout_downrange', 'm', 'Signed launch-surface arc at burnout'),
    ('final_altitude', 'm', 'Final altitude above the launch surface'),
    ('final_speed', 'm/s', 'Final inertial speed'),
    ('final_downrange', 'm', 'Final signed launch-surface arc'),
    ('max_sampled_altitude', 'm', 'Maximum sampled altitude'),
    ('max_sampled_speed', 'm/s', 'Maximum sampled inertial speed'),
    ('max_sampled_dynamic_pressure', 'Pa', 'Maximum sampled dynamic pressure'),
    ('max_sampled_drag', 'N', 'Maximum sampled drag magnitude'),
    ('max_sampled_acceleration', 'm/s^2', 'Maximum sampled net acceleration magnitude'),
    ('burn_duration', 's', 'Duration until full propellant exhaustion'),
    ('propellant_consumed', 'kg', 'Propellant consumed at burnout'),
]
METRIC_UNITS = {name: unit for name, unit, _ in METRICS}
ASSUMPTIONS = [
    'Two translational degrees of freedom in a body-centered inertial plane, starting from rest at (launch_radius, 0). The central body and atmosphere do not rotate.',
    'Constant thrust magnitude and specific impulse; analytical constant mass flow consumes initial mass minus dry mass exactly at burnout.',
    'Thrust angle is prescribed relative to local outward radial toward counterclockwise tangent: constant initial angle, linear interpolation between two declared steering times, then constant final angle. This is open-loop steering, not a closed-loop guidance solution.',
    'Inverse-square central gravity and stationary exponential atmosphere; constant supplied drag coefficient and area. Vector drag opposes the complete inertial velocity.',
    'Signed downrange is launch_radius times atan2(y, x), a launch-surface arc rather than Cartesian horizontal displacement. The trajectory remains within a quarter turn of the launch radial.',
    'Fixed-step RK4 is segmented at steering knots and exact burnout; three aligned grids assess sampled position and velocity agreement. Maxima cover retained samples only.',
]
NOT_ASSESSED = [
    'Physical validity of supplied engine, masses, atmosphere, area, coefficient and prescribed pitch programme; source labels are unverified.',
    'Closed-loop guidance, navigation, attitude dynamics, actuator authority, stability and the feasibility or optimality of following the prescribed thrust direction.',
    'Body rotation, winds, lift, Mach/Reynolds-dependent aerodynamics, aeroheating, structural response and three-dimensional flight.',
    'Throttling, staging, variable engine performance, propellant reserves, pad constraints and delayed liftoff.',
    'Surface crossing, impact, reentry, landing, recovery, insertion targeting and a complete launch-to-orbit mission.',
    'Continuous-time extrema, rigorous numerical error bounds, uncertainty, hardware qualification and launch authorization.',
]
_G0 = 9.80665
_SCHEMA = 'sixd.guided-ascent.v1'
_SCOPE = 'Sampled three-grid agreement only; not a rigorous error bound or physical validation.'


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Guided-ascent quantities must be finite numbers.')
    try:
        result = float(value)
        if not math.isfinite(result):
            raise ValueError('Guided-ascent quantities must be finite numbers.')
    except OverflowError:
        raise ValueError('Guided-ascent quantity exceeds the finite numerical range.') from None
    return result


def _duration(p):
    return (p['initial_mass'] - p['dry_mass']) / (p['thrust'] / (p['specific_impulse'] * _G0))


def validate_parameters(parameters):
    if not isinstance(parameters, dict) or set(parameters) != set(PARAMETERS):
        raise ValueError('Guided ascent requires all declared parameter bindings, with no extras.')
    p = {key: _finite(value) for key, value in parameters.items()}
    # The shared bounds keep the existing constant-engine/immediate-liftoff
    # contract. Guided ascent further checks the radial component at launch.
    try:
        powered_flight.validate_parameters({key: p[key] for key in powered_flight.PARAMETERS})
        burn = _duration(p)
        if not 0 <= p['pitch_start_time'] < p['pitch_end_time'] <= burn:
            raise ValueError('Steering times must satisfy 0 <= pitch start < pitch end <= burnout time.')
        if any(abs(p[key]) > math.pi / 2 for key in ('initial_pitch_angle', 'final_pitch_angle')):
            raise ValueError('Pitch angles must lie between -pi/2 and pi/2 radians relative to local outward radial.')
        if (abs(p['initial_pitch_angle']) == math.pi/2 or
                p['thrust'] * math.cos(p['initial_pitch_angle']) / p['initial_mass'] <= p['gravitational_parameter'] / p['launch_radius']**2):
            raise ValueError('Outside immediate-liftoff assumptions: the initial radial thrust component must exceed weight.')
        for segment in _segments(p):
            if segment['end_s'] <= segment['start_s']:
                raise ValueError('Steering and burnout boundaries must define resolved nonzero time intervals.')
    except (OverflowError, ZeroDivisionError):
        raise ValueError('Guided-ascent inputs exceed the resolved finite numerical range.') from None
    return p


def _pitch(p, t):
    if t <= p['pitch_start_time']:
        return p['initial_pitch_angle']
    if t >= p['pitch_end_time']:
        return p['final_pitch_angle']
    fraction = (t - p['pitch_start_time']) / (p['pitch_end_time'] - p['pitch_start_time'])
    return p['initial_pitch_angle'] + fraction * (p['final_pitch_angle'] - p['initial_pitch_angle'])


def _segments(p):
    burn = _duration(p)
    boundaries = sorted({0.0, p['pitch_start_time'], p['pitch_end_time'], burn})
    result = []
    for start, end in zip(boundaries, boundaries[1:]):
        event = ('before_cutoff' if end == burn else
                 'pitch_end' if end == p['pitch_end_time'] else 'pitch_start')
        result.append(dict(start_s=start, end_s=end, phase='powered', end_event=event))
    if p['coast_duration']:
        result.append(dict(start_s=burn, end_s=burn+p['coast_duration'], phase='coast', end_event='end'))
    return result


def _frame(p):
    return dict(id='body_centered_inertial_plane', position_unit='m', velocity_unit='m/s',
                launch_position=[p['launch_radius'], 0.0], launch_velocity=[0.0, 0.0],
                pitch_convention='From local outward radial toward counterclockwise tangential direction.',
                downrange_convention='launch_radius * atan2(y, x); signed launch-surface arc, not Cartesian displacement.')


def _physical(p, t, x, y, vx, vy, powered):
    if not all(math.isfinite(value) for value in (t, x, y, vx, vy)):
        raise ValueError('Guided-ascent state must remain finite.')
    radius, speed = math.hypot(x, y), math.hypot(vx, vy)
    altitude = radius - p['launch_radius']
    angle = math.atan2(y, x)
    if (radius <= 0 or altitude < -1e-8 or altitude > 1e7 or speed > 1e5 or abs(angle) >= math.pi/2):
        raise ValueError('Trajectory left the above-surface computational domain (altitude 0..1e7 m, speed <=1e5 m/s, signed surface arc within a quarter turn). Surface crossing and landing are not modeled.')
    radial_x, radial_y = x/radius, y/radius
    tangent_x, tangent_y = -radial_y, radial_x
    mass = (max(p['dry_mass'], p['initial_mass'] - p['thrust'] / (p['specific_impulse'] * _G0) * t)
            if powered and t < _duration(p) else p['dry_mass'])
    thrust = p['thrust'] if powered else 0.0
    pitch = _pitch(p, t)
    radial_cosine = 0.0 if abs(pitch) == math.pi/2 else math.cos(pitch)
    tx = radial_cosine*radial_x + math.sin(pitch)*tangent_x
    ty = radial_cosine*radial_y + math.sin(pitch)*tangent_y
    gravity = p['gravitational_parameter']/radius**2
    density = p['reference_density']*math.exp(-altitude/p['scale_height'])
    pressure = .5*density*speed*speed
    drag = pressure*p['drag_coefficient']*p['reference_area']
    drag_x, drag_y = (drag*vx/speed, drag*vy/speed) if speed else (0.0, 0.0)
    ax = (thrust*tx - drag_x)/mass - gravity*radial_x
    ay = (thrust*ty - drag_y)/mass - gravity*radial_y
    result = dict(altitude_m=altitude, downrange_m=p['launch_radius']*angle, speed_m_s=speed,
                  radial_velocity_m_s=vx*radial_x+vy*radial_y,
                  tangential_velocity_m_s=vx*tangent_x+vy*tangent_y,
                  mass_kg=mass, thrust_n=thrust, pitch_angle_rad=pitch,
                  gravity_m_s2=gravity, density_kg_m3=density,
                  dynamic_pressure_pa=pressure, drag_n=drag,
                  acceleration_m_s2=math.hypot(ax, ay), ax_m_s2=ax, ay_m_s2=ay)
    if not all(math.isfinite(value) for value in result.values()):
        raise ValueError('Guided-ascent arithmetic exceeds the finite numerical range.')
    return result


def _sample(p, t, x, y, vx, vy, powered, event=None):
    return dict(time_s=t, phase='powered' if powered else 'coast', event=event,
                x_m=x, y_m=y, vx_m_s=vx, vy_m_s=vy,
                **_physical(p, t, x, y, vx, vy, powered))


def _time(segment, index, n):
    if index == n:
        return segment['end_s']
    if index == 0:
        return segment['start_s']
    return segment['start_s'] + (segment['end_s']-segment['start_s'])*(index/n)


def _integrate(p, n):
    state = [p['launch_radius'], 0.0, 0.0, 0.0]
    rows = [_sample(p, 0.0, *state, True, 'launch')]
    for segment in _segments(p):
        powered = segment['phase'] == 'powered'
        if not powered:
            rows.append(_sample(p, segment['start_s'], *state, False, 'after_cutoff'))
        def rhs(t, values):
            forces = _physical(p, t, *values, powered)
            return [values[2], values[3], forces['ax_m_s2'], forces['ay_m_s2']]
        for j in range(n):
            t, end = _time(segment, j, n), _time(segment, j+1, n)
            dt = end-t
            if dt <= 0 or t+dt/2 in (t, end):
                raise ValueError('Time grid cannot resolve distinct RK4 stage times.')
            a = rhs(t, state)
            b = rhs(t+dt/2, [value+dt*derivative/2 for value,derivative in zip(state,a)])
            c = rhs(t+dt/2, [value+dt*derivative/2 for value,derivative in zip(state,b)])
            d = rhs(end, [value+dt*derivative for value,derivative in zip(state,c)])
            state = [value+dt*(aa+2*bb+2*cc+dd)/6 for value,aa,bb,cc,dd in zip(state,a,b,c,d)]
            event = segment['end_event'] if j == n-1 else None
            rows.append(_sample(p, end, *state, powered, event))
    return rows


def _metrics(p, rows):
    cutoff = next(row for row in rows if row['event'] == 'before_cutoff')
    values = dict(burnout_altitude=cutoff['altitude_m'], burnout_speed=cutoff['speed_m_s'],
                  burnout_downrange=cutoff['downrange_m'], final_altitude=rows[-1]['altitude_m'],
                  final_speed=rows[-1]['speed_m_s'], final_downrange=rows[-1]['downrange_m'],
                  max_sampled_altitude=max(row['altitude_m'] for row in rows),
                  max_sampled_speed=max(row['speed_m_s'] for row in rows),
                  max_sampled_dynamic_pressure=max(row['dynamic_pressure_pa'] for row in rows),
                  max_sampled_drag=max(row['drag_n'] for row in rows),
                  max_sampled_acceleration=max(row['acceleration_m_s2'] for row in rows),
                  burn_duration=_duration(p), propellant_consumed=p['initial_mass']-p['dry_mass'])
    return {key: dict(value=value, unit=METRIC_UNITS[key]) for key,value in values.items()}


def _aligned(p, high, n):
    result, cursor = [high[0]], 0
    for segment in _segments(p):
        if segment['phase'] == 'coast':
            cursor += 1
            result.append(high[cursor])
        result.extend(high[cursor+2*j] for j in range(1, n+1))
        cursor += 2*n
    return result


def _diagnostics(p, grids):
    levels, agreed = [], True
    differences = {name: 0.0 for name in METRIC_UNITS}
    for index in range(2):
        low, high = grids[index:index+2]
        n = int(p['steps'])*2**index
        aligned = _aligned(p, high, n)
        position_diffs, velocity_diffs = [], []
        for a,b in zip(low, aligned):
            pd = math.hypot(a['x_m']-b['x_m'], a['y_m']-b['y_m'])
            vd = math.hypot(a['vx_m_s']-b['vx_m_s'], a['vy_m_s']-b['vy_m_s'])
            # Scale positional agreement to travelled displacement, not the
            # body's radius: an Earth radius must not mask launch-path error.
            position_scale = max(math.hypot(row['x_m']-p['launch_radius'],row['y_m']) for row in (a,b))
            velocity_scale = max(a['speed_m_s'], b['speed_m_s'])
            agreed = agreed and pd <= p['altitude_numerical_tolerance'] + p['relative_numerical_tolerance']*position_scale
            agreed = agreed and vd <= p['velocity_numerical_tolerance'] + p['relative_numerical_tolerance']*velocity_scale
            position_diffs.append(pd)
            velocity_diffs.append(vd)
        lm, hm = _metrics(p, low), _metrics(p, high)
        md = {name: abs(lm[name]['value']-hm[name]['value']) for name in METRIC_UNITS}
        for name,difference in md.items():
            differences[name] = max(differences[name], difference)
        levels.append(dict(coarse_steps=n, fine_steps=2*n,
                           max_position_difference_m=max(position_diffs),
                           max_velocity_difference_m_s=max(velocity_diffs), metric_differences=md))
    allowances = {}
    for name,metric in _metrics(p,grids[-1]).items():
        absolute = (p['altitude_numerical_tolerance'] if metric['unit'] == 'm' else
                    p['velocity_numerical_tolerance'] if metric['unit'] == 'm/s' else 0.0)
        allowances[name] = (0.0 if name in {'burn_duration','propellant_consumed'} else
                            max(differences[name], absolute+p['relative_numerical_tolerance']*abs(metric['value'])))
    return dict(grid_agreement_met=bool(agreed),
                reason=('Both aligned grid comparisons meet declared position and velocity tolerances.' if agreed else
                        'At least one aligned grid comparison exceeds declared state tolerances; quantitative criteria and downstream use are blocked.'),
                max_position_difference_m=max(level['max_position_difference_m'] for level in levels),
                max_velocity_difference_m_s=max(level['max_velocity_difference_m_s'] for level in levels),
                metric_differences=differences, metric_allowances=allowances,
                level_differences=levels, scope=_SCOPE)


def _solver(p):
    return dict(method='classical_rk4', order=4, version='1', mass='analytical_constant_flow',
                segment_steps=[int(p['steps'])*factor for factor in (1,2,4)],
                segments=_segments(p), burnout='exact_segment_boundary',
                steering='declared_piecewise_linear_pitch', time_grid='pinned_segment_endpoints',
                standard_gravity_m_s2=_G0)


def _events(rows):
    return [dict(sample_index=index, time_s=row['time_s'], event=row['event'])
            for index,row in enumerate(rows) if row['event'] is not None]


def evaluate(parameters):
    p = validate_parameters(parameters)
    grids = [_integrate(p, int(p['steps'])*factor) for factor in (1,2,4)]
    metrics = _metrics(p, grids[-1])
    artifact = dict(schema=_SCHEMA, parameters=p, solver=_solver(p), frame=_frame(p),
                    samples=grids[-1], events=_events(grids[-1]),
                    refinement=dict(coarse_samples=grids[0], middle_samples=grids[1]),
                    diagnostics=_diagnostics(p,grids), assumptions=list(ASSUMPTIONS),
                    not_assessed=list(NOT_ASSESSED), source_fingerprint=_LOADED_SOURCE_FINGERPRINT)
    return metrics, artifact


def metric_allowance(artifact, metric):
    return artifact['diagnostics']['metric_allowances'][metric]


def _equal(a,b):
    try:
        return json.dumps(a,sort_keys=True,allow_nan=False,separators=(',',':')) == json.dumps(b,sort_keys=True,allow_nan=False,separators=(',',':'))
    except (ValueError,TypeError):
        return False


def validate_artifact(artifact, metrics, parameters, source_fingerprint):
    """Check retained evidence consistency without solving or authenticating it."""
    p = validate_parameters(parameters)
    keys = {'schema','parameters','solver','frame','samples','events','refinement','diagnostics',
            'assumptions','not_assessed','source_fingerprint'}
    if not isinstance(artifact,dict) or set(artifact) != keys or artifact['schema'] != _SCHEMA:
        raise ValueError('Invalid guided-ascent artifact schema or fields.')
    if (not _equal(artifact['parameters'],p) or not _equal(artifact['solver'],_solver(p))
            or not _equal(artifact['frame'],_frame(p)) or artifact['source_fingerprint'] != source_fingerprint):
        raise ValueError('Guided-ascent inputs, frame or solver source identity disagree with retained evidence.')
    if artifact['assumptions'] != ASSUMPTIONS or artifact['not_assessed'] != NOT_ASSESSED:
        raise ValueError('Guided-ascent scope is inconsistent.')
    refinement = artifact['refinement']
    if not isinstance(refinement,dict) or set(refinement) != {'coarse_samples','middle_samples'}:
        raise ValueError('Guided-ascent refinement grids are missing.')
    grids = [refinement['coarse_samples'],refinement['middle_samples'],artifact['samples']]
    segments = _segments(p)
    for factor,rows in zip((1,2,4),grids):
        n = int(p['steps'])*factor
        size = 1+len(segments)*n+bool(p['coast_duration'])
        if not isinstance(rows,list) or len(rows) != size:
            raise ValueError('Guided-ascent grid size is inconsistent.')
        initial = _sample(p,0.0,p['launch_radius'],0.0,0.0,0.0,True,'launch')
        if not _equal(rows[0],initial):
            raise ValueError('Guided-ascent launch state is inconsistent.')
        cursor = 0
        for segment in segments:
            powered = segment['phase'] == 'powered'
            if not powered:
                prior = rows[cursor]
                cursor += 1
                row = rows[cursor]
                if not isinstance(row,dict) or any(row.get(key) != prior.get(key) for key in ('time_s','x_m','y_m','vx_m_s','vy_m_s','mass_kg')):
                    raise ValueError('Guided-ascent cutoff state is discontinuous.')
                expected = _sample(p,segment['start_s'],prior['x_m'],prior['y_m'],prior['vx_m_s'],prior['vy_m_s'],False,'after_cutoff')
                if not _equal(row,expected):
                    raise ValueError('Guided-ascent after-cutoff sample is inconsistent.')
            for j in range(1,n+1):
                row = rows[cursor+j]
                if not isinstance(row,dict):
                    raise ValueError('Guided-ascent sample must be an object.')
                state = [_finite(row.get(key)) for key in ('x_m','y_m','vx_m_s','vy_m_s')]
                t = _time(segment,j,n)
                if t <= _time(segment,j-1,n):
                    raise ValueError('Guided-ascent retained grid cannot resolve distinct times.')
                expected = _sample(p,t,*state,powered,segment['end_event'] if j == n else None)
                if not _equal(row,expected):
                    raise ValueError('Guided-ascent sample fields, time, mass or forces are inconsistent.')
            cursor += n
    if (not _equal(artifact['events'],_events(grids[-1])) or not _equal(metrics,_metrics(p,grids[-1]))
            or not _equal(artifact['diagnostics'],_diagnostics(p,grids))):
        raise ValueError('Guided-ascent metrics, events or diagnostics disagree with retained samples.')
    return True
