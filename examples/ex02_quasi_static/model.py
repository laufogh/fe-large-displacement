"""Example 02 -- making an explicit run honestly quasi-static.

    abaqus cae noGUI=examples/ex02_quasi_static/model.py

Example 01 used Abaqus/Explicit to solve a static problem without asking whether
that was legitimate. This example asks.

The trade
---------
The stable time increment is set by the mesh and the wave speed, not by you.
A realistic installation rate would need millions of increments, so you run the
event faster than reality (or make the material heavier, which amounts to the
same thing). Both introduce inertia. The question is always *how much*, and the
answer is always in the energy history.

Cases
-----
A  v = 0.25 m/s, no mass scaling    -- slow, expensive, the reference
B  v = 1.0 m/s,  no mass scaling    -- 4x faster
C  v = 4.0 m/s,  no mass scaling    -- 16x faster; expect this to fail the test
D  v = 1.0 m/s,  mass scaling to a target stable increment
E  v = 4.0 m/s,  mass scaling       -- both levers at once, the usual production
                                       compromise and the one to be careful with

Each case reports peak ALLKE/ALLIE, peak ALLAE/ALLIE and the energy-balance
drift, then grades itself:

    good              ALLKE/ALLIE below 1 %   -- quote this
    acceptable        below 5 %               -- use it, say so
    not quasi-static  above 5 %               -- the inertia is carrying load

Read the *peak*, not the final value
------------------------------------
A run whose kinetic energy is 0.5 % at the end but spiked to 30 % during the
ramp has already corrupted the initial stiffness of the penetration curve, which
is often exactly the part you care about. The peak time is reported for that
reason.

A caution about mass scaling
----------------------------
Semi-automatic mass scaling to a target increment scales only the elements that
need it. That is usually a handful of small or badly-shaped elements -- which,
in a large-displacement run, are precisely the elements next to the structure
where the physics happens. Scaling their mass by a factor of 100 there is not
the same as scaling the whole domain by 100. Always check the `.sta` for the
total mass added: Abaqus reports it, and more than a few percent of the total
model mass should make you uncomfortable.
"""

from __future__ import print_function

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_ROOT, 'lib'))
sys.path.insert(0, os.path.join(_ROOT, 'examples'))

from fldlib import config, report, jobs, steps                 # noqa: E402
from common import indenter_model, runner                      # noqa: E402
from postproc import energy                                    # noqa: E402


STUDY = 'ex02_quasi_static'
CASES = ['A', 'B', 'C', 'D', 'E']

CASE_SETUP = {
    #      velocity  mass-scale target dt (None = off)
    'A': (0.25, None),
    'B': (1.00, None),
    'C': (4.00, None),
    'D': (1.00, 'target'),
    'E': (4.00, 'target'),
}
CASE_DOC = {
    'A': 'v=0.25 m/s, no mass scaling (reference)',
    'B': 'v=1.0 m/s,  no mass scaling',
    'C': 'v=4.0 m/s,  no mass scaling',
    'D': 'v=1.0 m/s,  semi-automatic mass scaling',
    'E': 'v=4.0 m/s,  semi-automatic mass scaling',
}


def make_params(velocity=None):
    P = config.Params(STUDY)
    indenter_model.declare(P)
    P.add('ms_target_dt', 5.0e-5, 's', 'mass-scaling target stable increment')
    P.add('ind_depth_short', 0.05, 'm',
          'shortened target depth -- this study is about energy, not depth')
    return P.resolve()


def run_case(case, workdir, P):
    velocity, mass_scale = CASE_SETUP[case]
    print('  %s: %s' % (case, CASE_DOC[case]))

    # Rebuild the parameter set with this case's velocity and the shortened
    # depth, through the environment, so the printed table and the JSON record
    # match what actually ran.
    os.environ['FLD_IND_VEL'] = repr(velocity)
    os.environ['FLD_IND_DEPTH'] = repr(P.ind_depth_short)
    try:
        Pc = make_params()
    finally:
        del os.environ['FLD_IND_VEL']
        del os.environ['FLD_IND_DEPTH']

    model_name = 'Ex02_' + case
    job_name = 'ex02_%s' % case
    handles = indenter_model.build(Pc, model_name=model_name,
                                   solver='explicit')

    budget = steps.report_time_budget(Pc.seed, Pc.soil_e, Pc.soil_nu,
                                      Pc.soil_rho, Pc.ind_depth, velocity)

    if mass_scale:
        steps.mass_scaling(handles['model'].steps[handles['step_name']],
                           target_dt=Pc.ms_target_dt, throughout=True)
        print('  mass scaling: semi-automatic to dt = %.3e s '
              '(natural dt is %.3e s, so up to %.0fx mass on the worst element)'
              % (Pc.ms_target_dt, budget['dt'],
                 (Pc.ms_target_dt / budget['dt']) ** 2))

    n_cpus = int(os.environ.get('FLD_NCPU', Pc.n_cpus))
    job = jobs.make_explicit_job(model_name, job_name, n_cpus=n_cpus,
                                 description=CASE_DOC[case])
    inp = jobs.write_input(job, workdir)

    chk = report.InpCheck(inp)
    chk.requires(r'^\*Output, history', 'history output requested')
    chk.requires(r'ALLKE', 'kinetic energy in the history output')
    chk.requires(r'ALLIE', 'internal energy in the history output')
    if mass_scale:
        chk.requires(r'^\*Variable Mass Scaling|^\*Fixed Mass Scaling',
                     'mass scaling written to the deck')
    else:
        chk.forbids(r'^\*Variable Mass Scaling|^\*Fixed Mass Scaling',
                    'no mass scaling in this case')
    chk.report()

    if not runner.flag('SUBMIT', True):
        return {'v': velocity, 'mass_scaled': bool(mass_scale),
                'submitted': False}

    jobs.submit(job)
    st = jobs.status(job_name, workdir)

    odb = os.path.join(workdir, job_name + '.odb')
    if not os.path.isfile(odb):
        return {'v': velocity, 'mass_scaled': bool(mass_scale),
                'increments': st['increments'], 'grade': 'no ODB'}

    e = energy.read_energies(odb)
    r = energy.ratios(e)
    grade = energy.verdict(r)

    return {
        'v': velocity,
        'mass_scaled': bool(mass_scale),
        'increments': st['increments'],
        'wall_per_inc_ms': None,
        'ke_peak_%': 100.0 * r['ALLKE/ALLIE']['peak'],
        'ke_final_%': 100.0 * r['ALLKE/ALLIE']['final'],
        'ae_peak_%': 100.0 * r['ALLAE/ALLIE']['peak'],
        'etot_%': 100.0 * r['ETOTAL/ALLIE']['peak'],
        'grade': grade,
    }


def main():
    workdir = config.workdir(STUDY)
    os.chdir(workdir)

    tee = report.start_log(os.path.join(workdir, STUDY + '.log'),
                           'EXAMPLE 02 -- QUASI-STATIC OR NOT')
    try:
        print(__doc__)
        P = make_params()
        P.show()
        P.write_json(os.path.join(workdir, STUDY + '_params.json'))

        rows = runner.run_study(
            STUDY, CASES, lambda c, w: run_case(c, w, P), workdir)
        runner.write_summary_csv(
            os.path.join(workdir, STUDY + '_summary.csv'), rows)

        report.banner('WHAT TO TAKE AWAY', level=1)
        print("""
  There is no universally correct rate or mass-scaling factor. There is only the
  check. Run it every time, on every model, including the ones that worked last
  week with a slightly different mesh.

  When a case fails the check, the fix is to slow down or scale less -- not to
  add damping until the kinetic energy goes away. Damping removes the symptom
  and leaves the error.
""")
    finally:
        report.stop_log(tee)


main()
