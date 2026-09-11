"""Example 01 -- where a Lagrangian mesh gives up.

    abaqus cae noGUI=examples/ex01_lagrangian_limit/model.py

This is the motivation for everything else in the repository. Before learning
ALE or CEL, you should see, with your own job files, exactly how and where an
ordinary Lagrangian analysis of a penetration problem fails -- and satisfy
yourself that it is a real limitation of the formulation rather than a mistake
you made.

Cases
-----
A  implicit, Abaqus/Standard, geometrically nonlinear, automatic stabilisation.
   This is what most people reach for first. Watch it stop converging. The
   `.sta` shows the increment size collapsing towards `minInc` and the job
   aborting with 'Too many attempts made for this increment'.

B  explicit, Abaqus/Explicit, Lagrangian, same mesh and material. Explicit has
   no convergence to lose, so it gets further -- and then aborts on
   'Excessive distortion of element number N', or on 'The ratio of deformation
   speed to wave speed exceeds 1.0000', which is the same failure a little
   further along.

C  explicit, same as B, but with a mesh twice as coarse. The depth reached
   changes. That is the diagnostic point of this example: **the failure depth
   is a property of the mesh, not of the soil.** A result that depends on the
   discretisation that way is not a result.

What to look at afterwards
--------------------------
* the `_summary.csv` written next to the job files -- depth reached per case;
* the abort message printed for each case;
* in the ODB, the deformed shape of the elements under the indenter corner.

Expect every case here to abort. That is the intended outcome, and the runner
reports it as a successful case: the case ran, the job failed, and the failure
is the data.
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


STUDY = 'ex01_lagrangian_limit'
CASES = ['A', 'B', 'C']

CASE_DOC = {
    'A': 'implicit Standard, nlgeom, automatic stabilisation',
    'B': 'explicit Lagrangian, seed 0.010 m',
    'C': 'explicit Lagrangian, seed 0.020 m (coarser)',
}


def make_params():
    P = config.Params(STUDY)
    indenter_model.declare(P)
    P.add('coarse_seed', 0.020, 'm', 'seed used by case C')
    return P.resolve()


def run_case(case, workdir, P):
    solver = 'implicit' if case == 'A' else 'explicit'
    job_name = 'ex01_%s' % case

    print('  %s: %s' % (case, CASE_DOC[case]))

    # Case C is the same model with a coarser seed. The parameter object is
    # frozen, so the seed is passed through the model builder rather than
    # mutated -- a study that quietly edits its own parameters is a study you
    # cannot reproduce.
    if case == 'C':
        os.environ['FLD_SEED'] = repr(P.coarse_seed)
        Pc = make_params()
        del os.environ['FLD_SEED']
    else:
        Pc = P

    handles = indenter_model.build(Pc, model_name='Ex01_' + case,
                                   solver=solver)
    print('  soil elements: %d' % handles['n_soil_elements'])

    if solver == 'explicit':
        steps.report_time_budget(
            min_element_size=Pc.seed, youngs=Pc.soil_e, poisson=Pc.soil_nu,
            density=Pc.soil_rho, travel=Pc.ind_depth, velocity=Pc.ind_vel)

    n_cpus = int(os.environ.get('FLD_NCPU', Pc.n_cpus))
    if solver == 'explicit':
        job = jobs.make_explicit_job('Ex01_' + case, job_name, n_cpus=n_cpus,
                                     description=CASE_DOC[case])
    else:
        job = jobs.make_implicit_job('Ex01_' + case, job_name, n_cpus=n_cpus,
                                     description=CASE_DOC[case])

    inp = jobs.write_input(job, workdir)

    chk = report.InpCheck(inp)
    chk.requires(r'^\*Step,.*nlgeom=YES', 'the step is geometrically nonlinear')
    if solver == 'explicit':
        chk.requires(r'^\*Dynamic, Explicit', 'explicit dynamics procedure')
        chk.requires(r'^\*Boundary,.*type=VELOCITY', 'velocity-driven indenter')
    else:
        chk.requires(r'^\*Static', 'static procedure')
    chk.forbids(r'^\*Adaptive Mesh,', 'no ALE in this example -- purely Lagrangian')
    chk.forbids(r'^\*Section Controls', 'no distortion control yet (example 03)')
    chk.report()

    if not runner.flag('SUBMIT', True):
        return {'seed': Pc.seed, 'elements': handles['n_soil_elements'],
                'submitted': False}

    jobs.submit(job)
    st = jobs.status(job_name, workdir)

    depth = None
    if st['step_time'] is not None:
        if solver == 'explicit':
            depth = st['step_time'] * Pc.ind_vel
        else:
            depth = st['step_time'] * Pc.ind_depth

    return {
        'seed': Pc.seed,
        'elements': handles['n_soil_elements'],
        'completed': st['completed'],
        'increments': st['increments'],
        'depth_m': depth,
        'depth_pct': (100.0 * depth / Pc.ind_depth) if depth else None,
        'distortion_abort': jobs.distortion_aborted(st),
        'abort': (st['abort_reason'] or '')[:60],
    }


def main():
    workdir = config.workdir(STUDY)
    os.chdir(workdir)

    tee = report.start_log(os.path.join(workdir, STUDY + '.log'),
                           'EXAMPLE 01 -- THE LAGRANGIAN LIMIT')
    try:
        print(__doc__)
        P = make_params()
        P.show()
        P.write_json(os.path.join(workdir, STUDY + '_params.json'))

        rows = runner.run_study(
            STUDY, CASES, lambda c, w: run_case(c, w, P), workdir)
        runner.write_summary_csv(
            os.path.join(workdir, STUDY + '_summary.csv'), rows)

        report.banner('WHAT THIS SHOWED', level=1)
        print("""
  Every case stopped before reaching the target depth, and case C stopped at a
  different depth from case B on identical physics. The mesh, not the soil, set
  the answer.

  Three ways forward, in the order the next examples take them:

    02  make the explicit run honestly quasi-static, so that what you measure
        before the abort is at least meaningful;
    03  section controls -- distortion control and hourglass control. Cheap,
        no change to the formulation, buys real depth;
    04  ALE adaptive meshing -- let the nodes move relative to the material;
    06  CEL -- give up on the mesh following the material at all.
""")
    finally:
        report.stop_log(tee)


main()
