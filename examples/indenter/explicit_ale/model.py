"""Explicit ALE. Same model as the explicit Lagrangian run, plus a domain.

    abaqus cae noGUI=examples/indenter/explicit_ale/model.py

A defined adaptive mesh domain that never sweeps produces no error, no
warning, and an ODB that looks normal. This script injects
`*Diagnostics, adaptive mesh=summary` and then reads the `.msg`.

Cases
-----
A  no ALE. The reference. Diff the deck against B: the only extra block
   should be `*Adaptive Mesh`.
B  ALE over a restricted element set around the indenter. Production
   configuration. See docs/02-ale-adaptive-meshing.md.
"""

from __future__ import print_function

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
sys.path.insert(0, os.path.join(_ROOT, 'lib'))
sys.path.insert(0, os.path.join(_ROOT, 'examples'))

from abaqusConstants import UNIFORM
from fldlib import config, report, jobs, ale, inpedit, steps
from common import indenter_model, runner


STUDY = 'indenter_explicit_ale'
CASES = ['A', 'B']
CASE_DOC = {
    'A': 'no ALE (reference)',
    'B': 'ALE restricted box around the indenter',
}


def make_params():
    P = config.Params(STUDY)
    indenter_model.declare(P)
    P.add('ale_box_x_mult', 3.0, '-', 'box half-width / indenter half-width')
    P.add('ale_box_z_mult', 1.3, '-', 'box depth / target penetration depth')
    P.add('ale_frequency', 10, '-', 'sweep every N increments')
    P.add('ale_sweeps', 1, '-', 'mesh sweeps per adaptive increment')
    P.add('ale_initial_sweeps', 5, '-', 'sweeps before the step starts')
    return P.resolve()


def run_case(case, workdir, P):
    print('  %s: %s' % (case, CASE_DOC[case]))
    job_name = 'expale_%s' % case
    handles = indenter_model.build(P, model_name='ExpAle_' + case,
                                   solver='explicit')
    model = handles['model']
    asm = handles['assembly']
    n_soil = handles['n_soil_elements']
    steps.report_time_budget(P.seed, P.soil_e, P.soil_nu, P.soil_rho,
                             P.ind_depth, P.ind_vel)

    n_adaptive = 0
    domain_elset = None
    if case != 'A':
        ale.make_controls(model, 'ALE_BC', smoothing=UNIFORM)
        box = indenter_model.ale_box(P)
        n_adaptive, bbox = ale.box_element_set(
            asm, handles['soil_inst'], 'ALE_Box', box)
        ale.describe_box_set('ALE_Box', n_adaptive, bbox, total=n_soil)
        domain_elset = 'ALE_Box'
        ale.add_domain(model, handles['step_name'], asm.sets['ALE_Box'],
                       'ALE_BC', frequency=P.ale_frequency,
                       mesh_sweeps=P.ale_sweeps,
                       initial_mesh_sweeps=P.ale_initial_sweeps)

    n_cpus = int(os.environ.get('FLD_NCPU', P.n_cpus))
    job = jobs.make_explicit_job('ExpAle_' + case, job_name, n_cpus=n_cpus,
                                 description=CASE_DOC[case])
    inp = jobs.write_input(job, workdir)
    inpedit.inject_diagnostics(inp, mode='summary')

    chk = report.InpCheck(inp)
    chk.requires(r'^\*Diagnostics, adaptive mesh=summary',
                 'per-increment ALE diagnostics requested')
    if case == 'A':
        chk.forbids(r'^\*Adaptive Mesh,', 'case A defines no adaptive domain')
    else:
        chk.requires(r'^\*Adaptive Mesh Controls, name=ALE_BC',
                     'adaptive mesh controls defined')
        chk.requires(r'^\*Adaptive Mesh,.*elset=%s' % domain_elset,
                     'domain restricted to %s' % domain_elset)
    chk.report()

    if not runner.flag('SUBMIT', True):
        return {'adaptive_el': n_adaptive, 'submitted': False}

    jobs.submit(job)
    st = jobs.status(job_name, workdir)
    msg = os.path.join(workdir, job_name + '.msg')
    activity = ale.read_msg_activity(msg) if os.path.isfile(msg) else \
        {'blocks': 0, 'avg_pct_moved': 0.0, 'active': False}
    if case == 'A':
        if activity['active']:
            raise AssertionError(
                'case A has no adaptive mesh domain, yet the .msg reports ALE '
                'activity.')
    else:
        ale.assert_active(msg)

    depth = st['step_time'] * P.ind_vel if st['step_time'] else None
    return {
        'adaptive_el': n_adaptive,
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
                           'INDENTER -- EXPLICIT ALE')
    try:
        print(__doc__)
        P = make_params()
        P.show()
        P.write_json(os.path.join(workdir, STUDY + '_params.json'))
        rows = runner.run_study(STUDY, CASES, lambda c, w: run_case(c, w, P),
                                workdir)
        runner.write_summary_csv(os.path.join(workdir, STUDY + '_summary.csv'),
                                 rows)
    finally:
        report.stop_log(tee)


main()
