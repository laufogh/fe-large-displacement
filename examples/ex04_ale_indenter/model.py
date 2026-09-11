"""Example 04 -- ALE adaptive meshing: defining it, restricting it, controlling it,
and proving it actually ran.

    abaqus cae noGUI=examples/ex04_ale_indenter/model.py

Same benchmark as examples 01-03. The only thing that changes between cases is
the adaptive mesh block.

Cases
-----
A  no ALE. The reference. The *only* difference between this deck and case B is
   the `*Adaptive Mesh` block -- diff them and check.
B  ALE over the whole soil part, default controls.
C  ALE over a **restricted element set**: a box around the indenter. This is the
   configuration to use in production. It concentrates the adaptive work where
   the distortion is, and it is far kinder to the parallel decomposition
   (example 05).
D  as B, but `frequency=2` instead of the default 10 -- sweep five times as
   often.
E  as B, but `smoothing objective=GRADED` with `curvature refinement=0`.

The point that matters most
---------------------------
**A defined adaptive mesh domain that never sweeps produces no error, no
warning, and an ODB that looks completely normal.** If your domain elset is
empty, or contains elements that are not first-order reduced-integration, or the
step is not `*Dynamic, Explicit`, Abaqus does nothing and tells you nothing.

The only evidence is in the `.msg`, and only if you asked for it. So this
example injects `*Diagnostics, adaptive mesh=summary` into every deck and then
asserts, per case, that the `.msg` reports a nonzero percentage of nodes moved.
Case A is asserted to have *no* activity, which proves the check itself works.

Do the same thing in your own models. It costs nothing and it is the difference
between using ALE and believing you are using ALE.

Two documentation landmines
---------------------------
1. The `*ADAPTIVE MESH` keyword reference gives the default `MESH SWEEPS` as 5.
   The ALE guide section, CAE and the solver all use **1**.
2. Abaqus documentation up to 2016 stated 'All nodes in a general contact domain
   are nonadaptive'. That is **not** the behaviour in 2021 -- ALE stays active
   under general contact, and the sentence has been removed from current docs.
   If you read an old thread telling you ALE and general contact are
   incompatible, it is out of date.
"""

from __future__ import print_function

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_ROOT, 'lib'))
sys.path.insert(0, os.path.join(_ROOT, 'examples'))

from abaqusConstants import UNIFORM, GRADED                    # noqa: E402
from fldlib import config, report, jobs, ale, inpedit, steps   # noqa: E402
from common import indenter_model, runner                      # noqa: E402


STUDY = 'ex04_ale_indenter'
CASES = ['A', 'B', 'C', 'D', 'E']

CASE_DOC = {
    'A': 'no ALE (reference)',
    'B': 'ALE whole soil, default controls',
    'C': 'ALE restricted box around the indenter  <- production configuration',
    'D': 'ALE whole soil, frequency=2',
    'E': 'ALE whole soil, GRADED smoothing, curvature refinement 0',
}


def make_params():
    P = config.Params(STUDY)
    indenter_model.declare(P)
    # The box is expressed as multiples of the indenter half-width and of the
    # target depth, so it follows the geometry when you change it. A box written
    # in absolute coordinates is the single most common way to end up with an
    # empty -- and therefore inert -- adaptive domain.
    P.add('ale_box_x_mult', 3.0, '-', 'box half-width / indenter half-width')
    P.add('ale_box_z_mult', 1.3, '-', 'box depth / target penetration depth')
    P.add('ale_frequency', 10, '-', 'sweep every N increments (cases B, C, E)')
    P.add('ale_sweeps', 1, '-', 'mesh sweeps per adaptive increment')
    P.add('ale_initial_sweeps', 5, '-', 'sweeps before the step starts')
    return P.resolve()


def ale_box(P):
    """The adaptive domain around the indenter, in assembly coordinates.

    Soil top is z = 0 and penetration is -z, so the box runs from the surface
    down past the target depth. It deliberately stops short of the model base
    and sides: elements at a boundary have fewer neighbours to smooth against,
    and there is no distortion to fix out there anyway.
    """
    half = P.ind_half * P.ale_box_x_mult
    deep = -P.ind_depth * P.ale_box_z_mult
    return dict(xmin=-half, xmax=half,
                ymin=-P.soil_wid, ymax=P.soil_wid,      # full width
                zmin=max(deep, -P.soil_dep + 2.0 * P.seed), zmax=0.0)


def run_case(case, workdir, P):
    print('  %s: %s' % (case, CASE_DOC[case]))

    model_name = 'Ex04_' + case
    job_name = 'ex04_%s' % case
    handles = indenter_model.build(P, model_name=model_name, solver='explicit')
    model = handles['model']
    asm = handles['assembly']
    soil_inst = handles['soil_inst']
    step_name = handles['step_name']
    n_soil = handles['n_soil_elements']

    steps.report_time_budget(P.seed, P.soil_e, P.soil_nu, P.soil_rho,
                             P.ind_depth, P.ind_vel)

    # -- the adaptive mesh block, and nothing else, differs between cases ----
    domain_elset = None
    n_adaptive = 0
    if case != 'A':
        if case == 'E':
            ale.make_controls(model, 'ALE_BC', smoothing=GRADED,
                              curvature_refinement=0.0)
        else:
            ale.make_controls(model, 'ALE_BC', smoothing=UNIFORM)

        if case == 'C':
            box = ale_box(P)
            n_adaptive, bbox = ale.box_element_set(asm, soil_inst, 'ALE_Box',
                                                   box)
            ale.describe_box_set('ALE_Box', n_adaptive, bbox, total=n_soil)
            region = asm.sets['ALE_Box']
            domain_elset = 'ALE_Box'
        else:
            region = asm.Set(name='ALE_WholeSoil', elements=soil_inst.elements)
            n_adaptive = len(region.elements)
            print('  element set ALE_WholeSoil  %6d elements (100 %% of %d)'
                  % (n_adaptive, n_soil))
            domain_elset = 'ALE_WholeSoil'

        ale.add_domain(model, step_name, region, 'ALE_BC',
                       frequency=(2 if case == 'D' else P.ale_frequency),
                       mesh_sweeps=P.ale_sweeps,
                       initial_mesh_sweeps=P.ale_initial_sweeps)

    # -- write, edit, verify, then (and only then) submit --------------------
    n_cpus = int(os.environ.get('FLD_NCPU', P.n_cpus))
    if n_cpus != 1:
        print('  *** NOTE: running on %d CPUs. With domain-level '
              'parallelisation the nodes shared between parallel domains are '
              'NONADAPTIVE, which distorts this study. Use 1 CPU to measure '
              'ALE mechanics; see example 05 for the parallel picture. ***'
              % n_cpus)

    job = jobs.make_explicit_job(model_name, job_name, n_cpus=n_cpus,
                                 description=CASE_DOC[case])
    inp = jobs.write_input(job, workdir)

    n_diag = inpedit.inject_diagnostics(inp, mode='summary')
    print('  injected *Diagnostics into %d explicit step(s)' % n_diag)

    chk = report.InpCheck(inp)
    chk.requires(r'^\*Diagnostics, adaptive mesh=summary',
                 'per-increment ALE diagnostics requested')
    if case == 'A':
        chk.forbids(r'^\*Adaptive Mesh,', 'case A defines no adaptive domain')
        chk.forbids(r'^\*Adaptive Mesh Controls', 'case A defines no controls')
    else:
        chk.requires(r'^\*Adaptive Mesh Controls, name=ALE_BC',
                     'adaptive mesh controls defined')
        chk.requires(r'^\*Adaptive Mesh,.*elset=%s' % domain_elset,
                     'domain restricted to %s' % domain_elset)
        chk.count(r'^\*Adaptive Mesh,', 1,
                  'exactly one adaptive mesh domain (CAE allows only one)')
        if case == 'D':
            chk.requires(r'^\*Adaptive Mesh,.*frequency=2',
                         'frequency=2 written (it differs from the default 10)')
        else:
            # frequency=10 equals the default, so CAE omits it. A missing
            # parameter is not evidence the setting did not take.
            chk.forbids(r'^\*Adaptive Mesh,.*frequency=',
                        'frequency omitted because it equals the default 10')
        if case == 'E':
            chk.requires(r'smoothing objective=GRADED', 'GRADED smoothing')
            chk.requires(r'curvature refinement=0', 'curvature refinement 0')
    chk.report()

    print('  *Adaptive Mesh lines in the deck:')
    for line in (inpedit.keyword_lines(inp, '*Adaptive Mesh') or ['    (none)']):
        print('    %s' % line)

    if not runner.flag('SUBMIT', True):
        return {'adaptive_el': n_adaptive, 'submitted': False}

    jobs.submit(job)
    st = jobs.status(job_name, workdir)

    # -- prove ALE was ACTIVE, not merely defined ---------------------------
    msg = os.path.join(workdir, job_name + '.msg')
    activity = ale.read_msg_activity(msg) if os.path.isfile(msg) else \
        {'blocks': 0, 'avg_pct_moved': 0.0, 'active': False}
    print('  ALE diagnostics: %d block(s), average %.2f %% of nodes moved'
          % (activity['blocks'], activity['avg_pct_moved']))

    if case == 'A':
        if activity['active']:
            raise AssertionError(
                'case A has no adaptive mesh domain, yet the .msg reports ALE '
                'activity. The diagnostic parser is wrong, or the deck is not '
                'the one that ran.')
        print('  case A correctly reports NO adaptive activity '
              '(this is what makes the check trustworthy)')
    else:
        ale.assert_active(msg)

    depth = st['step_time'] * P.ind_vel if st['step_time'] else None
    return {
        'adaptive_el': n_adaptive,
        'adaptive_pct': 100.0 * n_adaptive / float(n_soil),
        'msg_blocks': activity['blocks'],
        'pct_moved': activity['avg_pct_moved'],
        'increments': st['increments'],
        'depth_m': depth,
        'completed': st['completed'],
        'abort': (st['abort_reason'] or '')[:50],
    }


def main():
    workdir = config.workdir(STUDY)
    os.chdir(workdir)

    tee = report.start_log(os.path.join(workdir, STUDY + '.log'),
                           'EXAMPLE 04 -- ALE ADAPTIVE MESHING')
    try:
        print(__doc__)
        P = make_params()
        P.show()
        P.write_json(os.path.join(workdir, STUDY + '_params.json'))
        print('  ALE box for case C: %r' % (ale_box(P),))

        rows = runner.run_study(
            STUDY, CASES, lambda c, w: run_case(c, w, P), workdir)
        runner.write_summary_csv(
            os.path.join(workdir, STUDY + '_summary.csv'), rows)

        report.banner('HOW TO READ THE TABLE', level=1)
        print("""
  adaptive_el / adaptive_pct  size of the adaptive domain.
  msg_blocks                  how many times Abaqus reported a sweep. Zero means
                              the domain was inert -- and would have been silent.
  pct_moved                   average share of nodes the sweeps moved. The
                              restricted box (C) shows a much higher percentage
                              than the whole domain (B) simply because the box
                              contains only the elements that need moving.
  depth_m                     how far the indenter got before the job stopped.

  ALE buys depth. It does not buy unlimited depth: the mesh topology is still
  fixed, so once material has to flow around the indenter rather than merely be
  smoothed, ALE stops helping. That is where example 06 (CEL) begins.
""")
    finally:
        report.stop_log(tee)


main()
