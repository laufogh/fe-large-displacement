"""Explicit Lagrangian strip indenter, plus the two cheap extras.

    abaqus cae noGUI=examples/indenter/explicit/model.py

Cases
-----
A  baseline velocity, no mass scaling, no section controls.
   Aborts on element distortion. Compare the depth with implicit.
B  four times the velocity. Same mesh. The energy test (`ALLKE/ALLIE`)
   is the check that the run is still quasi-static. See
   docs/01-explicit-quasi-static.md.
C  distortion control injected into the deck. The cheapest extra depth.
   Do not combine it with enhanced hourglass. See docs/04-section-controls.md.
"""

from __future__ import print_function

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
sys.path.insert(0, os.path.join(_ROOT, 'lib'))
sys.path.insert(0, os.path.join(_ROOT, 'examples'))

from fldlib import config, report, jobs, steps, inpedit
from common import indenter_model, runner
from postproc import energy


STUDY = 'indenter_explicit'
CASES = ['A', 'B', 'C']
SOIL_SECTION = r'^(\*Solid Section,[^\n]*material=SoilMat[^\n]*)$'
CASE_DOC = {
    'A': 'explicit Lagrangian, v = 1 m/s',
    'B': 'explicit Lagrangian, v = 4 m/s (energy test)',
    'C': 'explicit Lagrangian, distortion control',
}


def make_params():
    P = config.Params(STUDY)
    indenter_model.declare(P)
    P.add('fast_vel', 4.0, 'm/s', 'velocity used by case B')
    return P.resolve()


def run_case(case, workdir, P):
    print('  %s: %s' % (case, CASE_DOC[case]))
    if case == 'B':
        os.environ['FLD_IND_VEL'] = repr(P.fast_vel)
        try:
            Pc = make_params()
        finally:
            del os.environ['FLD_IND_VEL']
    else:
        Pc = P

    job_name = 'exp_%s' % case
    handles = indenter_model.build(Pc, model_name='Exp_' + case,
                                   solver='explicit')
    steps.report_time_budget(Pc.seed, Pc.soil_e, Pc.soil_nu, Pc.soil_rho,
                             Pc.ind_depth, Pc.ind_vel)

    n_cpus = int(os.environ.get('FLD_NCPU', Pc.n_cpus))
    job = jobs.make_explicit_job('Exp_' + case, job_name, n_cpus=n_cpus,
                                 description=CASE_DOC[case])
    inp = jobs.write_input(job, workdir)

    if case == 'C':
        keyword = inpedit.section_controls_keyword(
            'SC-Soil', distortion_control=True)
        inpedit.inject_section_controls(inp, keyword, SOIL_SECTION)
        print('  injected: %s' % keyword)

    chk = report.InpCheck(inp)
    chk.requires(r'^\*Dynamic, Explicit', 'explicit dynamics procedure')
    chk.requires(r'^\*Boundary,.*type=VELOCITY', 'velocity-driven indenter')
    chk.forbids(r'^\*Adaptive Mesh,', 'no ALE -- purely Lagrangian')
    chk.requires(r'ALLKE', 'kinetic energy in the history output')
    chk.requires(r'ALLIE', 'internal energy in the history output')
    if case == 'C':
        chk.requires(r'^\*Section Controls', 'distortion control defined')
        chk.requires(r'^\*Solid Section,.*controls=SC-Soil',
                     'the soil section references the control')
    else:
        chk.forbids(r'^\*Section Controls', 'no section controls in this case')
    chk.report()

    if not runner.flag('SUBMIT', True):
        return {'v': Pc.ind_vel, 'submitted': False}

    jobs.submit(job)
    st = jobs.status(job_name, workdir)
    depth = st['step_time'] * Pc.ind_vel if st['step_time'] else None
    row = {
        'v': Pc.ind_vel,
        'elements': handles['n_soil_elements'],
        'increments': st['increments'],
        'depth_m': depth,
        'distortion_abort': jobs.distortion_aborted(st),
        'completed': st['completed'],
        'abort': (st['abort_reason'] or '')[:50],
    }
    odb = os.path.join(workdir, job_name + '.odb')
    if os.path.isfile(odb):
        r = energy.ratios(energy.read_energies(odb))
        row['ke_peak_%'] = 100.0 * r['ALLKE/ALLIE']['peak']
        row['ae_peak_%'] = 100.0 * r['ALLAE/ALLIE']['peak']
        row['grade'] = energy.verdict(r)
    return row


def main():
    workdir = config.workdir(STUDY)
    os.chdir(workdir)
    tee = report.start_log(os.path.join(workdir, STUDY + '.log'),
                           'INDENTER -- EXPLICIT LAGRANGIAN')
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
