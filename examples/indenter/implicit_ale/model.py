"""Implicit ALE. The same Standard model, with an adaptive mesh domain.

    abaqus cae noGUI=examples/indenter/implicit_ale/model.py

Abaqus/Standard ALE is the weaker tool: Lagrangian domains only, one smoothing
algorithm, no initial mesh sweeps. It is here so the code path is visible.
Expect it to fail in much the same place as the implicit Lagrangian run.
Production penetration work uses Explicit ALE, then CEL.
"""

from __future__ import print_function

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
sys.path.insert(0, os.path.join(_ROOT, 'lib'))
sys.path.insert(0, os.path.join(_ROOT, 'examples'))

from abaqusConstants import UNIFORM
from fldlib import config, report, jobs, ale, inpedit
from common import indenter_model, runner


STUDY = 'indenter_implicit_ale'
CASES = ['A']
CASE_DOC = {'A': 'implicit Static + restricted ALE box'}


def make_params():
    P = config.Params(STUDY)
    indenter_model.declare(P)
    P.add('ale_box_x_mult', 3.0, '-', 'box half-width / indenter half-width')
    P.add('ale_box_z_mult', 1.3, '-', 'box depth / target penetration depth')
    P.add('ale_frequency', 10, '-', 'sweep every N increments')
    P.add('ale_sweeps', 1, '-', 'mesh sweeps per adaptive increment')
    return P.resolve()


def run_case(case, workdir, P):
    job_name = 'impale_%s' % case
    print('  %s: %s' % (case, CASE_DOC[case]))

    handles = indenter_model.build(P, model_name='ImpAle_' + case,
                                   solver='implicit')
    model = handles['model']
    asm = handles['assembly']
    n_soil = handles['n_soil_elements']

    ale.make_controls(model, 'ALE_BC', smoothing=UNIFORM)
    box = indenter_model.ale_box(P)
    n_adaptive, bbox = ale.box_element_set(asm, handles['soil_inst'],
                                           'ALE_Box', box)
    ale.describe_box_set('ALE_Box', n_adaptive, bbox, total=n_soil)
    ale.add_domain(model, handles['step_name'], asm.sets['ALE_Box'], 'ALE_BC',
                   frequency=P.ale_frequency, mesh_sweeps=P.ale_sweeps,
                   initial_mesh_sweeps=None)

    n_cpus = int(os.environ.get('FLD_NCPU', P.n_cpus))
    job = jobs.make_implicit_job('ImpAle_' + case, job_name, n_cpus=n_cpus,
                                 description=CASE_DOC[case])
    inp = jobs.write_input(job, workdir)
    inpedit.inject_diagnostics(inp, mode='summary', include_static=True)

    chk = report.InpCheck(inp)
    chk.requires(r'^\*Static', 'static procedure')
    chk.requires(r'^\*Adaptive Mesh Controls, name=ALE_BC',
                 'adaptive mesh controls defined')
    chk.requires(r'^\*Adaptive Mesh,.*elset=ALE_Box',
                 'domain restricted to ALE_Box')
    chk.requires(r'^\*Diagnostics, adaptive mesh=summary',
                 'ALE diagnostics requested')
    chk.report()

    if not runner.flag('SUBMIT', True):
        return {'adaptive_el': n_adaptive, 'submitted': False}

    jobs.submit(job)
    st = jobs.status(job_name, workdir)
    msg = os.path.join(workdir, job_name + '.msg')
    activity = ale.read_msg_activity(msg) if os.path.isfile(msg) else \
        {'blocks': 0, 'avg_pct_moved': 0.0, 'active': False}
    if os.path.isfile(msg):
        ale.assert_active(msg, required=False)
    depth = (st['step_time'] * P.ind_depth) if st['step_time'] is not None else None
    return {
        'adaptive_el': n_adaptive,
        'msg_blocks': activity['blocks'],
        'pct_moved': activity['avg_pct_moved'],
        'completed': st['completed'],
        'increments': st['increments'],
        'depth_m': depth,
        'abort': (st['abort_reason'] or '')[:60],
    }


def main():
    workdir = config.workdir(STUDY)
    os.chdir(workdir)
    tee = report.start_log(os.path.join(workdir, STUDY + '.log'),
                           'INDENTER -- IMPLICIT ALE')
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
