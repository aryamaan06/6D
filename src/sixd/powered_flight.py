"""Bounded one-dimensional powered ascent and above-surface coast.

RK4 is segmented exactly at fuel exhaustion. Mass is analytical, never stepped.
Grid agreement compares aligned samples on three grids, not a true error bound.
See docs/POWERED_FLIGHT_REFERENCES.md for independently evaluated references.
"""
from hashlib import sha256
import json
import math
from pathlib import Path

_LOADED_SOURCE_FINGERPRINT = sha256(Path(__file__).read_bytes()).hexdigest()

PARAMETERS = {
    'initial_mass': 'kg', 'dry_mass': 'kg', 'thrust': 'N', 'specific_impulse': 's',
    'reference_area': 'm^2', 'drag_coefficient': '1', 'reference_density': 'kg/m^3',
    'scale_height': 'm', 'gravitational_parameter': 'm^3/s^2', 'launch_radius': 'm',
    'coast_duration': 's', 'steps': '1', 'altitude_numerical_tolerance': 'm',
    'velocity_numerical_tolerance': 'm/s', 'relative_numerical_tolerance': '1',
}
METRICS = [
    ('final_altitude', 'm', 'Final altitude above launch surface'),
    ('final_velocity', 'm/s', 'Final signed vertical velocity'),
    ('max_sampled_altitude', 'm', 'Maximum sampled altitude'),
    ('max_sampled_speed', 'm/s', 'Maximum sampled speed'),
    ('max_sampled_dynamic_pressure', 'Pa', 'Maximum sampled dynamic pressure'),
    ('max_sampled_drag', 'N', 'Maximum sampled drag magnitude'),
    ('max_sampled_upward_acceleration', 'm/s^2', 'Maximum sampled upward acceleration'),
    ('burnout_altitude', 'm', 'Altitude at burnout'),
    ('burnout_velocity', 'm/s', 'Vertical velocity at burnout'),
    ('burn_duration', 's', 'Duration until fuel exhaustion'),
    ('propellant_consumed', 'kg', 'Propellant consumed at burnout'),
]
METRIC_UNITS = {name: unit for name, unit, _ in METRICS}
ASSUMPTIONS = [
    'One radial vertical degree of freedom, starting from rest at the supplied launch radius; immediate liftoff.',
    'Constant upward thrust and specific impulse; analytical constant mass flow consumes initial mass minus dry mass exactly at burnout.',
    'Inverse-square central gravity; stationary exponential atmosphere with constant supplied drag coefficient and reference area.',
    'Signed drag opposes vertical velocity. Coast begins with an instantaneous thrust cutoff and fixed dry mass.',
    'Segmented fixed-step RK4; three-grid agreement checks sampled states and metrics. Extrema cover retained samples only.',
]
NOT_ASSESSED = [
    'Physical validity of supplied thrust, Isp, density, scale height, coefficient, area and mass; source labels are unverified.',
    'Mach/Reynolds dependence, winds, lift, rotation, horizontal motion, guidance, attitude, structural response and aeroheating.',
    'Staging, throttle schedules, variable engine performance, propellant reserves, pad hold-down and delayed liftoff.',
    'Surface crossing, impact, landing, reentry, recovery and a complete launch-to-orbit mission.',
    'Continuous-time extrema, rigorous numerical error bounds, uncertainty and hardware or flight qualification.',
]
_G0 = 9.80665
_SCHEMA = 'sixd.powered-flight.v1'
_SCOPE = 'Sampled three-grid agreement only; not a rigorous error bound or physical validation.'


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Powered-flight quantities must be finite numbers.')
    try:
        if not math.isfinite(value):
            raise ValueError('Powered-flight quantities must be finite numbers.')
    except OverflowError:
        raise ValueError('Powered-flight quantity exceeds the finite numerical range.') from None
    return float(value)


def validate_parameters(parameters):
    if not isinstance(parameters, dict) or set(parameters) != set(PARAMETERS):
        raise ValueError('Powered flight requires all declared parameter bindings, with no extras.')
    p = {key: _finite(value) for key, value in parameters.items()}
    zero_allowed = {'drag_coefficient', 'reference_density', 'gravitational_parameter', 'coast_duration', 'relative_numerical_tolerance'}
    for key, value in p.items():
        if value < 0 or (value == 0 and key not in zero_allowed):
            raise ValueError(key + ' must be ' + ('nonnegative.' if key in zero_allowed else 'positive.'))
    if p['initial_mass'] <= p['dry_mass']:
        raise ValueError('Initial mass must exceed dry mass; this model requires a positive powered segment.')
    if p['steps'] != int(p['steps']) or not 8 <= p['steps'] <= 512:
        raise ValueError('Steps must be an integer from 8 to 512 per segment on the coarse grid; middle/fine use twice/four times this count.')
    if p['relative_numerical_tolerance'] > .01:
        raise ValueError('Relative numerical tolerance must be at most 0.01; this is a numerical input bound, not physical validation.')
    flow = p['thrust'] / (p['specific_impulse'] * _G0)
    duration = (p['initial_mass'] - p['dry_mass']) / flow
    total = duration + p['coast_duration']
    if not all(math.isfinite(x) and x > 0 for x in (flow, duration, total)) or total > 10000:
        raise ValueError('Burn and coast must have finite resolved durations totaling at most 10000 seconds (computational bound).')
    if p['coast_duration'] and total <= duration:
        raise ValueError('Coast duration is too small to resolve at burnout time.')
    if p['thrust'] / p['initial_mass'] <= p['gravitational_parameter'] / p['launch_radius']**2:
        raise ValueError('Outside immediate-liftoff assumptions: initial thrust must exceed initial weight. No pad or delayed-liftoff model is implemented.')
    return p


def _duration(p):
    return (p['initial_mass'] - p['dry_mass']) * (p['specific_impulse'] * _G0) / p['thrust']


def _physical(p, t, h, v, powered):
    if not all(math.isfinite(x) for x in (t, h, v)) or h < -1e-8 or h > 1e7 or abs(v) > 1e5:
        raise ValueError('Trajectory left the above-surface computational domain (altitude 0..1e7 m, speed <=1e5 m/s). Surface crossing/landing is not modeled.')
    mass = max(p['dry_mass'], p['initial_mass'] - p['thrust'] / (p['specific_impulse'] * _G0) * t) if powered else p['dry_mass']
    if t >= _duration(p):
        mass = p['dry_mass']
    thrust = p['thrust'] if powered else 0.0
    gravity = p['gravitational_parameter'] / (p['launch_radius'] + h)**2
    density = p['reference_density'] * math.exp(-h / p['scale_height'])
    q = .5 * density * v * v
    drag = math.copysign(q * p['drag_coefficient'] * p['reference_area'], v)
    acceleration = (thrust - drag) / mass - gravity
    values = (mass, thrust, gravity, density, q, drag, acceleration)
    if not all(math.isfinite(x) for x in values):
        raise ValueError('Powered-flight arithmetic exceeds its finite numerical range.')
    return values


def _sample(p, t, h, v, powered, event=None):
    mass, thrust, gravity, density, q, drag, acceleration = _physical(p, t, h, v, powered)
    return dict(time_s=t, phase='powered' if powered else 'coast', event=event,
                altitude_m=h, velocity_m_s=v, mass_kg=mass, thrust_n=thrust,
                gravity_m_s2=gravity, density_kg_m3=density,
                dynamic_pressure_pa=q, drag_n=drag, acceleration_m_s2=acceleration)


def _integrate(p, n):
    burn = _duration(p)
    h = v = 0.0
    rows = [_sample(p, 0.0, h, v, True, 'launch')]
    segments = [(0., burn, True)] + ([(burn, p['coast_duration'], False)] if p['coast_duration'] else [])
    for start, length, powered in segments:
        if not powered:
            rows.append(_sample(p, start, h, v, False, 'after_cutoff'))
        for i in range(n):
            t = start if i == 0 else start + length*i/n
            end = start + length if i == n-1 else start + length*(i+1)/n
            dt = end-t
            if dt <= 0:
                raise ValueError('Time grid cannot resolve distinct sample times.')
            def rhs(tt, hh, vv):
                return vv, _physical(p, tt, hh, vv, powered)[-1]
            a, b = rhs(t, h, v)
            c, d = rhs(t+dt/2, h+dt*a/2, v+dt*b/2)
            e, f = rhs(t+dt/2, h+dt*c/2, v+dt*d/2)
            g, k = rhs(end, h+dt*e, v+dt*f)
            h += dt*(a+2*c+2*e+g)/6
            v += dt*(b+2*d+2*f+k)/6
            event = ('before_cutoff' if powered else 'end') if i == n-1 else None
            rows.append(_sample(p, end, h, v, powered, event))
    return rows


def _metrics(p, rows):
    cutoff = next(row for row in rows if row['event'] == 'before_cutoff')
    values = dict(final_altitude=rows[-1]['altitude_m'], final_velocity=rows[-1]['velocity_m_s'],
                  max_sampled_altitude=max(row['altitude_m'] for row in rows),
                  max_sampled_speed=max(abs(row['velocity_m_s']) for row in rows),
                  max_sampled_dynamic_pressure=max(row['dynamic_pressure_pa'] for row in rows),
                  max_sampled_drag=max(abs(row['drag_n']) for row in rows),
                  max_sampled_upward_acceleration=max(row['acceleration_m_s2'] for row in rows),
                  burnout_altitude=cutoff['altitude_m'], burnout_velocity=cutoff['velocity_m_s'],
                  burn_duration=_duration(p), propellant_consumed=p['initial_mass']-p['dry_mass'])
    return {key: {'value': value, 'unit': METRIC_UNITS[key]} for key, value in values.items()}


def _aligned(rows, factor, n, coast):
    result = [rows[i*factor] for i in range(n+1)]
    if coast:
        offset = n*factor+1
        result += [rows[offset+i*factor] for i in range(n+1)]
    return result


def _diagnostics(p, grids):
    levels = []
    metric_differences = {name: 0.0 for name in METRIC_UNITS}
    agreed = True
    for i in range(2):
        low, high = grids[i:i+2]
        n = int(p['steps']) * 2**i
        aligned = _aligned(high, 2, n, bool(p['coast_duration']))
        diffs = {}
        for field, tolerance in [('altitude_m', 'altitude_numerical_tolerance'), ('velocity_m_s', 'velocity_numerical_tolerance')]:
            differences = [abs(a[field]-b[field]) for a,b in zip(low, aligned)]
            fits = [diff <= p[tolerance]+p['relative_numerical_tolerance']*max(abs(a[field]),abs(b[field]))
                    for a,b,diff in zip(low,aligned,differences)]
            diffs[field] = max(differences)
            agreed = agreed and all(fits)
        lm, hm = _metrics(p, low), _metrics(p, high)
        md = {name: abs(lm[name]['value']-hm[name]['value']) for name in METRIC_UNITS}
        for name, difference in md.items():
            metric_differences[name] = max(metric_differences[name], difference)
        levels.append({'coarse_steps': n, 'fine_steps': 2*n, 'max_altitude_difference_m': diffs['altitude_m'],
                       'max_velocity_difference_m_s': diffs['velocity_m_s'], 'metric_differences': md})
    metrics = _metrics(p, grids[-1])
    allowances = {}
    for name, metric in metrics.items():
        unit = metric['unit']
        absolute = p['altitude_numerical_tolerance'] if unit == 'm' else p['velocity_numerical_tolerance'] if unit == 'm/s' else 0.
        # Algebraic mass and burn-time outputs are not integrated quantities.
        allowances[name] = 0.0 if name in {'burn_duration', 'propellant_consumed'} else max(metric_differences[name], absolute + p['relative_numerical_tolerance']*abs(metric['value']))
    return {'grid_agreement_met': bool(agreed),
            'reason': 'Both aligned grid comparisons meet declared state tolerances.' if agreed else 'At least one aligned grid comparison exceeds declared state tolerances; quantitative criteria and downstream use are blocked.',
            'max_altitude_difference_m': max(x['max_altitude_difference_m'] for x in levels),
            'max_velocity_difference_m_s': max(x['max_velocity_difference_m_s'] for x in levels),
            'metric_differences': metric_differences, 'metric_allowances': allowances,
            'level_differences': levels, 'scope': _SCOPE}


def metric_allowance(artifact, metric):
    return artifact['diagnostics']['metric_allowances'][metric]


def _solver(p, modern=True):
    result = {'method': 'classical_rk4', 'order': 4, 'mass': 'analytical_constant_flow',
            'segment_steps': [int(p['steps'])*x for x in (1,2,4)], 'burnout': 'exact_segment_boundary',
            'standard_gravity_m_s2': _G0}
    if modern:
        result['version'] = '2'
        result['time_grid'] = 'pinned_segment_endpoints'
    return result


def _events(rows):
    return [{'sample_index': i, 'time_s': row['time_s'], 'event': row['event']}
            for i,row in enumerate(rows) if row['event'] is not None]


def evaluate(parameters):
    p = validate_parameters(parameters)
    grids = [_integrate(p, int(p['steps'])*x) for x in (1,2,4)]
    metrics = _metrics(p, grids[-1])
    artifact = dict(schema=_SCHEMA, parameters=p, solver=_solver(p), samples=grids[-1],
                    events=_events(grids[-1]), refinement={'coarse_samples': grids[0], 'middle_samples': grids[1]},
                    diagnostics=_diagnostics(p, grids), assumptions=list(ASSUMPTIONS), not_assessed=list(NOT_ASSESSED),
                    source_fingerprint=_LOADED_SOURCE_FINGERPRINT)
    return metrics, artifact


def _equal(a, b):
    try:
        return json.dumps(a, sort_keys=True, allow_nan=False, separators=(',',':')) == json.dumps(b, sort_keys=True, allow_nan=False, separators=(',',':'))
    except (TypeError, ValueError):
        return False


def validate_artifact(artifact, metrics, parameters, source_fingerprint):
    """Check retained evidence consistency, never rerun the ODE or authenticate it."""
    p = validate_parameters(parameters)
    keys = {'schema','parameters','solver','samples','events','refinement','diagnostics','assumptions','not_assessed','source_fingerprint'}
    if not isinstance(artifact, dict) or set(artifact) != keys or artifact['schema'] != _SCHEMA:
        raise ValueError('Invalid powered-flight artifact schema or fields.')
    modern = artifact.get('solver', {}).get('version') == '2'
    if not _equal(artifact['parameters'], p) or artifact['source_fingerprint'] != source_fingerprint or not _equal(artifact['solver'], _solver(p, modern)):
        raise ValueError('Powered-flight inputs or solver source identity do not match retained evidence.')
    if artifact['assumptions'] != ASSUMPTIONS or artifact['not_assessed'] != NOT_ASSESSED:
        raise ValueError('Powered-flight scope is inconsistent.')
    refinement = artifact['refinement']
    if not isinstance(refinement, dict) or set(refinement) != {'coarse_samples','middle_samples'}:
        raise ValueError('Powered-flight refinement grids are missing.')
    grids = [refinement['coarse_samples'], refinement['middle_samples'], artifact['samples']]
    burn = _duration(p)
    for factor, rows in zip((1,2,4), grids):
        n = int(p['steps'])*factor
        size = (n+1)*(2 if p['coast_duration'] else 1)
        if not isinstance(rows, list) or len(rows) != size:
            raise ValueError('Powered-flight grid size is inconsistent.')
        for i,row in enumerate(rows):
            powered = i <= n
            j = i if powered else i-n-1
            t = burn*j/n if powered else burn+p['coast_duration']*j/n
            if modern and j == n:
                t = burn if powered else burn+p['coast_duration']
            event = 'launch' if i == 0 else 'before_cutoff' if i == n else 'after_cutoff' if j == 0 else 'end' if j == n else None
            if not isinstance(row, dict):
                raise ValueError('Powered-flight sample must be an object.')
            h, v = _finite(row.get('altitude_m')), _finite(row.get('velocity_m_s'))
            expected = _sample(p, t, h, v, powered, event)
            if not _equal(row, expected):
                raise ValueError('Powered-flight sample fields, time, mass or forces are inconsistent.')
        if rows[0]['altitude_m'] != 0.0 or rows[0]['velocity_m_s'] != 0.0:
            raise ValueError('Powered-flight launch state is inconsistent.')
        if p['coast_duration'] and any(rows[n][key] != rows[n+1][key] for key in ('altitude_m','velocity_m_s','mass_kg')):
            raise ValueError('Powered-flight cutoff state is discontinuous.')
    if not _equal(artifact['events'], _events(grids[-1])) or not _equal(metrics, _metrics(p, grids[-1])) or not _equal(artifact['diagnostics'], _diagnostics(p, grids)):
        raise ValueError('Powered-flight metrics, events or accuracy diagnostics disagree with retained samples.')
    return True
