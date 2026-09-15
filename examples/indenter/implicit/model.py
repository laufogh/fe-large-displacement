"""Implicit Lagrangian strip indenter. Watch it stop converging.

    abaqus cae noGUI=examples/indenter/implicit/model.py

Same mesh, material and contact as the other indenter models. The step is
`*Static` with automatic stabilisation. Expect the increment size to collapse
towards `minInc` and the job to abort with 'Too many attempts made for this
increment'. That failure is the data, not a mistake.
"""

from __future__ import print_function

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
sys.path.insert(0, os.path.join(_ROOT, 'lib'))
sys.path.insert(0, os.path.join(_ROOT, 'examples'))

from fldlib import config, report, jobs
from common import indenter_model, runner


STUDY = 'indenter_implicit'
CASES = ['A']
CASE_DOC = {'A': 'implicit Standard, nlgeom, automatic stabilisation'}


def make_params():
    P = config.Params(STUDY)
    indenter_model.declare(P)
    return P.resolve()


def run_case(case, workdir, P):
    job_name = 'imp_%s' % case
    print('  %s: %s' % (case, CASE_DOC[case]))

    handles = indenter_model.build(P, model_name='Imp_' + case, solver='implicit')
    print('  soil elements: %d' % handles['n_soil_elements'])

    n_cpus = int(os.environ.get('FLD_NCPU', P.n_cpus))
    job = jobs.make_implicit_job('Imp_' + case, job_name, n_cpus=n_cpus,
                                 description=CASE_DOC[case])
    inp = jobs.write_input(job, workdir)

    chk = report.InpCheck(inp)
    chk.requires(r'^\*Step,.*nlgeom=YES', 'the step is geometrically nonlinear')
    chk.requires(r'^\*Static', 'static procedure')
    chk.forbids(r'^\*Adaptive Mesh,', 'no ALE -- purely Lagrangian')
    chk.report()

    if not runner.flag('SUBMIT', True):
        return {'elements': handles['n_soil_elements'], 'submitted': False}

    jobs.submit(job)
    st = jobs.status(job_name, workdir)
    depth = (st['step_time'] * P.ind_depth) if st['step_time'] is not None else None
    return {
        'elements': handles['n_soil_elements'],
        'completed': st['completed'],
        'increments': st['increments'],
        'depth_m': depth,
        'abort': (st['abort_reason'] or '')[:60],
    }


def main():
    workdir = config.workdir(STUDY)
    os.chdir(workdir)
    tee = report.start_log(os.path.join(workdir, STUDY + '.log'),
                           'INDENTER -- IMPLICIT LAGRANGIAN')
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
