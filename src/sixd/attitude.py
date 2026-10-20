"""Bounded continuous single-axis PD attitude response with supplied conditions.

Rigid fixed-axis rotational dynamics: I * omega_dot = actuator + disturbance.
The actuator clips kp*(target-angle) - kd*omega to a supplied symmetric limit.
This is an ideal torque source, not a wheel/magnetorquer/flight controller model.
References and independent analytic witnesses are documented in ATTITUDE_MODEL.md.
"""
from hashlib import sha256
import json
import math
from pathlib import Path

PARAMETERS = {
    'inertia': 'kg*m^2', 'initial_angle': 'rad', 'initial_rate': 'rad/s',
    'target_angle': 'rad', 'proportional_gain': 'N*m/rad',
    'derivative_gain': 'N*m*s/rad', 'max_torque': 'N*m',
    'disturbance_torque': 'N*m', 'duration': 's', 'steps': '1',
    'assessment_start': 's', 'angle_numerical_tolerance': 'rad',
    'rate_numerical_tolerance': 'rad/s',
}
METRICS = [
    ('final_error', 'rad', 'Final absolute pointing error'),
    ('final_rate', 'rad/s', 'Final absolute angular rate'),
    ('max_sampled_error', 'rad', 'Maximum sampled absolute error over full run'),
    ('max_sampled_rate', 'rad/s', 'Maximum sampled absolute rate over full run'),
    ('max_assessed_error', 'rad', 'Maximum sampled absolute error in assessment window'),
    ('max_assessed_rate', 'rad/s', 'Maximum sampled absolute rate in assessment window'),
    ('max_sampled_command_torque', 'N*m', 'Maximum sampled requested torque magnitude'),
    ('max_sampled_applied_torque', 'N*m', 'Maximum sampled applied actuator torque magnitude'),
    ('sampled_saturation_fraction', '1', 'Fraction of saved samples with clipped actuator command'),
]
ASSUMPTIONS = [
    'Rigid body with constant inertia rotating about one fixed principal axis; all angles and rates refer to that same axis and inertial reference.',
    'Fixed target with zero desired rate. Signed error is target minus unwrapped angle; no angle wrapping or shortest-path selection.',
    'Continuous proportional-derivative feedback uses exact instantaneous angle and rate; no sensor noise, estimation, delay or digital controller sampling.',
    'An ideal bidirectional torque source clips the requested torque to the supplied symmetric limit. Constant supplied disturbance torque is added after clipping.',
    'Recorded histories use the finer of two fixed RK4 grids. Grid agreement is a numerical diagnostic, not a certified error bound or physical validation.',
    'Extrema and the assessment window concern saved samples only. Final error is not settling time; saturation fraction counts samples, not time.',
]
NOT_ASSESSED = [
    'Source-data accuracy, inertia validity, applicability of a single rigid principal axis, controller suitability and environmental torque estimates.',
    'Three-axis rotation, quaternions, cross-axis coupling, flexible modes, orbital or translation coupling, and moving targets.',
    'Guidance trajectories, navigation or attitude estimation, sensors, noise, delays, digital implementation and flight software.',
    'Reaction-wheel speed or momentum storage/desaturation, actuator bandwidth, magnetorquer field geometry, thrust pulsing, power or fuel consumption.',
    'Continuous-time bounds between recorded samples, guaranteed stability or settling, uncertainty, hardware qualification, rocket landing and mission readiness.',
]
MAX_STEPS = 2048
MAX_STATE = 1e6
METHOD = 'classical_rk4_step_doubling'


def _finite(value, label):
    if not math.isfinite(value):
        raise ValueError(label + ' is outside the finite numerical range.')
    return value


def _multiply(a, b, label):
    value = _finite(a*b, label)
    if a != 0 and b != 0 and value == 0:
        raise ValueError(label + ' underflows the supported numerical range.')
    return value


def _divide(a, b, label):
    value = _finite(a/b, label)
    if a != 0 and value == 0:
        raise ValueError(label + ' underflows the supported numerical range.')
    return value


def validate_parameters(parameters):
    if not isinstance(parameters, dict) or set(parameters) != set(PARAMETERS):
        raise ValueError('Attitude response requires the exact maintained parameter set.')
    p = {}
    for key, value in parameters.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(key + ' must be a finite number.')
        try:
            p[key] = _finite(float(value), key)
        except OverflowError:
            raise ValueError(key + ' is outside the finite numerical range.') from None
    for key in ('inertia', 'duration', 'angle_numerical_tolerance', 'rate_numerical_tolerance'):
        if p[key] <= 0:
            raise ValueError(key + ' must be greater than zero.')
    for key in ('proportional_gain', 'derivative_gain', 'max_torque'):
        if p[key] < 0:
            raise ValueError(key + ' must be nonnegative; zero permits a declared inactive controller/actuator.')
    if not p['steps'].is_integer() or not 32 <= p['steps'] <= MAX_STEPS:
        raise ValueError('steps must be a whole number from 32 to 2048 (the saved fine grid uses twice this count).')
    if not 0 <= p['assessment_start'] <= p['duration']:
        raise ValueError('assessment_start must be within the supplied duration, including endpoints.')
    if max(abs(p[k]) for k in ('initial_angle', 'initial_rate', 'target_angle')) > MAX_STATE:
        raise ValueError('Initial angles and rate exceed the declared numerical state bound of 1000000.')
    if abs(p['target_angle']-p['initial_angle']) > MAX_STATE:
        raise ValueError('Initial pointing error exceeds the numerical state bound of 1000000 rad.')
    step = p['duration'] / p['steps']
    if step <= 0 or step / 2 <= 0:
        raise ValueError('Time-step underflow; choose a representable duration.')
    stiffness = max(math.sqrt(_divide(p['proportional_gain'],p['inertia'], 'Proportional gain / inertia')),
                    _divide(p['derivative_gain'],p['inertia'], 'Derivative gain / inertia'))
    if _multiply(step,stiffness, 'Step resolution') > 0.1:
        raise ValueError('Controller dynamics are under-resolved: duration/steps * max(sqrt(kp/inertia), kd/inertia) must be <= 0.1. Increase steps or review the declared time window; do not change engineering limits to obtain a pass.')
    return p


def _torque(p, error, rate):
    command = _finite(_multiply(p['proportional_gain'],error,'Proportional torque') - _multiply(p['derivative_gain'],rate,'Derivative torque'), 'Requested torque')
    applied = max(-p['max_torque'], min(p['max_torque'], command))
    return command, applied


def _derivative(p, error, rate):
    _, applied = _torque(p, error, rate)
    acceleration = _divide(_finite(applied + p['disturbance_torque'],'Net torque'),p['inertia'], 'Angular acceleration')
    return -rate, acceleration


def _step(p, error, rate, dt):
    a, b = _derivative(p, error, rate)
    c, d = _derivative(p, error + _multiply(a,dt/2,'Stage angle'), rate + _multiply(b,dt/2,'Stage rate'))
    e, f = _derivative(p, error + _multiply(c,dt/2,'Stage angle'), rate + _multiply(d,dt/2,'Stage rate'))
    g, h = _derivative(p, error + _multiply(e,dt,'Stage angle'), rate + _multiply(f,dt,'Stage rate'))
    next_error = _finite(error + _multiply(dt,(a+2*c+2*e+g)/6,'Angle increment'), 'Pointing error')
    next_rate = _finite(rate + _multiply(dt,(b+2*d+2*f+h)/6,'Rate increment'), 'Angular rate')
    if max(abs(next_error), abs(next_rate), abs(p['target_angle']-next_error)) > MAX_STATE:
        raise ValueError('Response exceeded the numerical angle/rate bound of 1000000; no partial result is accepted.')
    return next_error, next_rate


def _integrate(p, steps):
    error, rate = p['target_angle']-p['initial_angle'], p['initial_rate']
    rows = []
    dt = p['duration']/steps
    for index in range(steps+1):
        time = p['duration']*(index/steps)
        if rows and time <= rows[-1]['time_s']:
            raise ValueError('Time samples collapse at this floating-point scale.')
        command, applied = _torque(p, error, rate)
        rows.append({'time_s':time, 'angle_rad':p['target_angle']-error,
                     'error_rad':error, 'rate_rad_s':rate, 'command_torque_nm':command,
                     'applied_torque_nm':applied, 'saturated':abs(command)>p['max_torque']})
        if index < steps:
            error, rate = _step(p, error, rate, dt)
    return rows


def sampled_metrics(samples, assessment_start):
    assessed = [row for row in samples if row['time_s'] >= assessment_start]
    values = {
        'final_error':abs(samples[-1]['error_rad']), 'final_rate':abs(samples[-1]['rate_rad_s']),
        'max_sampled_error':max(abs(row['error_rad']) for row in samples),
        'max_sampled_rate':max(abs(row['rate_rad_s']) for row in samples),
        'max_assessed_error':max(abs(row['error_rad']) for row in assessed),
        'max_assessed_rate':max(abs(row['rate_rad_s']) for row in assessed),
        'max_sampled_command_torque':max(abs(row['command_torque_nm']) for row in samples),
        'max_sampled_applied_torque':max(abs(row['applied_torque_nm']) for row in samples),
        'sampled_saturation_fraction':sum(row['saturated'] for row in samples)/len(samples),
    }
    return {name:{'value':values[name], 'unit':unit} for name, unit, _ in METRICS}


def _calculate(parameters):
    p = validate_parameters(parameters)
    count = int(p['steps'])
    coarse, fine = _integrate(p, count), _integrate(p, 2*count)
    error_difference = max(abs(row['error_rad']-fine[2*i]['error_rad']) for i,row in enumerate(coarse))
    rate_difference = max(abs(row['rate_rad_s']-fine[2*i]['rate_rad_s']) for i,row in enumerate(coarse))
    if error_difference > p['angle_numerical_tolerance'] or rate_difference > p['rate_numerical_tolerance']:
        raise ValueError('Attitude grid refinement did not meet the supplied angle/rate numerical tolerances. Increase resolution within the supported range and review applicability; no completed metrics were produced.')
    assessed = [row for row in fine if row['time_s'] >= p['assessment_start']]
    artifact = {
        'schema':'sixd.attitude-response.v1', 'parameters':p,
        'solver':{'method':METHOD,'coarse_steps':count,'fine_steps':2*count,'saved_step_s':p['duration']/(2*count),
                  'max_steps':MAX_STEPS, 'max_state_magnitude':MAX_STATE, 'max_coarse_resolution_ratio':0.1},
        'samples':fine,
        'diagnostics':{'max_grid_error_difference_rad':error_difference,
                       'max_grid_rate_difference_rad_s':rate_difference,
                       'grid_agreement_met':True,'assessment_first_sample_s':assessed[0]['time_s'],
                       'assessment_sample_count':len(assessed), 'sample_count':len(fine),
                       'label':'Two-grid numerical agreement only; not a certified error bound, stability proof or physical validation.'},
        'assumptions':list(ASSUMPTIONS), 'not_assessed':list(NOT_ASSESSED),
    }
    return sampled_metrics(fine, p['assessment_start']), artifact


def evaluate(parameters):
    metrics, artifact = _calculate(parameters)
    artifact['source_fingerprint'] = sha256(Path(__file__).read_bytes()).hexdigest()
    return metrics, artifact


def validate_artifact(artifact, metrics, parameters, source_fingerprint):
    """Check retained v1 structure and sample-derived arithmetic without integration.

    Like other local receipts, this checks consistency, not authenticity. Imports
    never accept external response artifacts. A deliberately requested recheck
    performs a fresh simulation; history navigation never integrates dynamics.
    """
    def equal(actual, expected, label):
        try:
            encode=lambda v:json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)
            if encode(actual)!=encode(expected):raise ValueError('Inconsistent attitude '+label+'.')
        except (TypeError,OverflowError):
            raise ValueError('Attitude evidence must be finite v1 JSON.') from None
    def fields(value, keys, label):
        if not isinstance(value,dict) or set(value)!=set(keys):
            raise ValueError('Unexpected fields in attitude '+label+'.')
    def number(value,label):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise ValueError('Invalid attitude '+label+'.')
    p=validate_parameters(parameters)
    fields(artifact,{'schema','parameters','solver','samples','diagnostics','assumptions','not_assessed','source_fingerprint'},'artifact')
    equal(artifact['schema'],'sixd.attitude-response.v1','schema')
    equal(artifact['parameters'],p,'parameters')
    equal(artifact['source_fingerprint'],source_fingerprint,'source fingerprint')
    n=int(p['steps']);count=2*n
    equal(artifact['solver'],{'method':METHOD,'coarse_steps':n,'fine_steps':count,'saved_step_s':p['duration']/count,
          'max_steps':MAX_STEPS,'max_state_magnitude':MAX_STATE,'max_coarse_resolution_ratio':0.1},'solver')
    equal(artifact['assumptions'],ASSUMPTIONS,'assumptions')
    equal(artifact['not_assessed'],NOT_ASSESSED,'exclusions')
    samples=artifact['samples']
    if not isinstance(samples,list) or len(samples)!=count+1:
        raise ValueError('Attitude sample count does not match the saved grid.')
    for i,row in enumerate(samples):
        fields(row,{'time_s','angle_rad','error_rad','rate_rad_s','command_torque_nm','applied_torque_nm','saturated'},'sample')
        for key in row:
            if key!='saturated':number(row[key],'sample '+key)
        if not isinstance(row['saturated'],bool):raise ValueError('Attitude saturation flag must be boolean.')
        equal(row['time_s'],p['duration']*(i/count),'sample time')
        equal(row['angle_rad'],p['target_angle']-row['error_rad'],'angle/error relation')
        command,applied=_torque(p,row['error_rad'],row['rate_rad_s'])
        equal(row['command_torque_nm'],command,'requested torque')
        equal(row['applied_torque_nm'],applied,'applied torque')
        equal(row['saturated'],abs(command)>p['max_torque'],'saturation flag')
        if max(abs(row[k]) for k in ('angle_rad','error_rad','rate_rad_s'))>MAX_STATE:
            raise ValueError('Attitude sample exceeds its numerical state bound.')
    equal(samples[0]['error_rad'],p['target_angle']-p['initial_angle'],'initial error')
    equal(samples[0]['rate_rad_s'],p['initial_rate'],'initial rate')
    equal(metrics,sampled_metrics(samples,p['assessment_start']),'sampled metrics')
    d=artifact['diagnostics']
    fields(d,{'max_grid_error_difference_rad','max_grid_rate_difference_rad_s','grid_agreement_met',
              'assessment_first_sample_s','assessment_sample_count','sample_count','label'},'diagnostics')
    for key,tolerance in [('max_grid_error_difference_rad','angle_numerical_tolerance'),('max_grid_rate_difference_rad_s','rate_numerical_tolerance')]:
        number(d[key],key)
        if not 0<=d[key]<=p[tolerance]:raise ValueError('Attitude grid disagreement exceeds its supplied tolerance.')
    equal(d['grid_agreement_met'],True,'grid agreement flag')
    assessed=[r for r in samples if r['time_s']>=p['assessment_start']]
    equal(d['assessment_first_sample_s'],assessed[0]['time_s'],'first assessment sample')
    equal(d['assessment_sample_count'],len(assessed),'assessment sample count')
    equal(d['sample_count'],len(samples),'diagnostic sample count')
    equal(d['label'],'Two-grid numerical agreement only; not a certified error bound, stability proof or physical validation.','diagnostic scope')
    return True
