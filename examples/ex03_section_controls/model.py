"""Example 03 -- section controls: the cheapest thing that buys you depth.

    abaqus cae noGUI=examples/ex03_section_controls/model.py

Before changing the formulation, change the element controls. Distortion control
and enhanced hourglass control cost nothing, require no change to the mesh or
the model, and are the single highest-value-per-effort intervention available
for a Lagrangian penetration analysis.

There is a catch, and it is the reason this example exists rather than a
one-line recommendation.

Cases
-----
A  baseline, no `*Section Controls`                              -- aborts
B  `distortion control=YES` (default length ratio 0.1)
C  `distortion control=YES, length ratio=0.05`
D  `distortion control=YES, length ratio=0.20`
E  `hourglass=enhanced`
F  `hourglass=enhanced, distortion control=YES`                  -- the trap

What was measured
-----------------
* **Distortion control is inert while the mesh is healthy.** Over the first half
  of the baseline run the reaction force deviated by 0.16 %. It is not adding
  stiffness; it acts only when elements approach collapse.
* **When it acts, it can be decisive**: 2.5x the penetration depth at one
  calibration. At another, where the collapse was not marginal, it bought 2.6 %.
  It rescues a marginal analysis; it does not rescue a doomed one.
* **`length ratio` did nothing measurable.** Cases B, C and D terminated at
  identical depth with identical energies across a 4x range of the parameter.
  Do not spend a week tuning it.
* **Enhanced hourglass control cut ALLAE/ALLIE from 16.5 % to 3.8 %** -- a 77 %
  reduction in artificial strain energy -- stiffened the response and delayed
  the abort by 10 %. It did not prevent it.
* **Do not combine them.** Case F aborted at 0.069 m where B, C and D completed
  to 0.15 m. Combining enhanced hourglass with distortion control adds a viscous
  term to the element formulation that negates the distortion-control rescue.
  `fldlib.inpedit.section_controls_keyword` raises if you ask for both; case F
  bypasses the guard deliberately, because seeing the failure is the lesson.

Energy channel: `ALLDC`. It stayed **exactly zero** in every run except one
reading of 1.085e-6 J. The penalty does energetically negligible work -- it
redirects deformation rather than absorbing energy.

Why the keyword is injected rather than set through the API
-----------------------------------------------------------
`mdb.models[...].SectionControl` does not exist in Abaqus 2021. The keyword is
written into the deck after `writeInput()`. Placement is mandatory: it must go
at the top of the model data immediately after `*Preprint`. Mid-file placement
(after `*Part`, before `*Material`) corrupts the parse of the later
`*Amplitude, definition=SMOOTH STEP` -- an error that points at the amplitude
and says nothing about section controls.
"""

from __future__ import print_function

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_ROOT, 'lib'))
sys.path.insert(0, os.path.join(_ROOT, 'examples'))

from fldlib import config, report, jobs, inpedit                # noqa: E402
from common import indenter_model, runner                       # noqa: E402
from postproc import energy                                     # noqa: E402


STUDY = 'ex03_section_controls'
CASES = ['A', 'B', 'C', 'D', 'E', 'F']

SOIL_SECTION = r'^(\*Solid Section,[^\n]*material=SoilMat[^\n]*)$'

CASE_KEYWORD = {
    'A': None,
    'B': '*Section Controls, name=SC-Soil, distortion control=YES',
    'C': '*Section Controls, name=SC-Soil, distortion control=YES, length ratio=0.05',
    'D': '*Section Controls, name=SC-Soil, distortion control=YES, length ratio=0.20',
    'E': '*Section Controls, name=SC-Soil, hourglass=enhanced',
    # Written literally rather than through section_controls_keyword(), which
    # refuses this combination. The refusal is the recommendation; this case is
    # the evidence behind it.
    'F': '*Section Controls, name=SC-Soil, hourglass=enhanced, distortion control=YES',
}
CASE_DOC = {
    'A': 'baseline, no section controls',
    'B': 'distortion control, default length ratio',
    'C': 'distortion control, length ratio 0.05',
    'D': 'distortion control, length ratio 0.20',
    'E': 'enhanced hourglass only',
    'F': 'enhanced hourglass + distortion control (do not do this)',
}


def make_params():
    P = config.Params(STUDY)
    indenter_model.declare(P)
    return P.resolve()


def run_case(case, workdir, P):
    print('  %s: %s' % (case, CASE_DOC[case]))

    model_name = 'Ex03_' + case
    job_name = 'ex03_%s' % case
    indenter_model.build(P, model_name=model_name, solver='explicit')

    n_cpus = int(os.environ.get('FLD_NCPU', P.n_cpus))
    job = jobs.make_explicit_job(model_name, job_name, n_cpus=n_cpus,
                                 description=CASE_DOC[case])
    inp = jobs.write_input(job, workdir)

    keyword = CASE_KEYWORD[case]
    if keyword:
        inpedit.inject_section_controls(inp, keyword, SOIL_SECTION)
        print('  injected: %s' % keyword)

    chk = report.InpCheck(inp)
    if keyword:
        chk.count(r'^\*Section Controls', 1, 'exactly one control definition')
        chk.requires(r'^\*Solid Section,.*controls=SC-Soil',
                     'the soil section references the control')
        if 'distortion control' in keyword:
            chk.requires(r'distortion control=YES', 'distortion control on')
        if 'hourglass' in keyword:
            chk.requires(r'hourglass=enhanced', 'enhanced hourglass on')
    else:
        chk.forbids(r'^\*Section Controls', 'baseline has no section controls')
        chk.forbids(r'controls=SC-Soil', 'and nothing references one')
    # The placement bug this guards against is silent until the amplitude is
    # parsed, so check the amplitude survived the injection.
    chk.requires(r'^\*Amplitude, name=Ramp, definition=SMOOTH STEP',
                 'the SMOOTH STEP amplitude survived the injection')
    chk.report()

    if not runner.flag('SUBMIT', True):
        return {'controls': (keyword or 'none')[18:60], 'submitted': False}

    jobs.submit(job)
    st = jobs.status(job_name, workdir)
    depth = st['step_time'] * P.ind_vel if st['step_time'] else None

    row = {
        'controls': (keyword or 'none').replace('*Section Controls, name=SC-Soil, ', ''),
        'increments': st['increments'],
        'depth_m': depth,
        'depth_pct': (100.0 * depth / P.ind_depth) if depth else None,
        'distortion_abort': jobs.distortion_aborted(st),
        'completed': st['completed'],
    }

    odb = os.path.join(workdir, job_name + '.odb')
    if os.path.isfile(odb):
        r = energy.ratios(energy.read_energies(odb))
        row['ae_peak_%'] = 100.0 * r['ALLAE/ALLIE']['peak']
        row['ke_peak_%'] = 100.0 * r['ALLKE/ALLIE']['peak']
        row['alldc_peak'] = r['ALLDC/ALLIE']['peak'] * r['ALLIE_max']
    return row


def main():
    workdir = config.workdir(STUDY)
    os.chdir(workdir)

    tee = report.start_log(os.path.join(workdir, STUDY + '.log'),
                           'EXAMPLE 03 -- SECTION CONTROLS')
    try:
        print(__doc__)
        P = make_params()
        P.show()
        P.write_json(os.path.join(workdir, STUDY + '_params.json'))

        rows = runner.run_study(
            STUDY, CASES, lambda c, w: run_case(c, w, P), workdir)
        runner.write_summary_csv(
            os.path.join(workdir, STUDY + '_summary.csv'), rows)

        report.banner('RECOMMENDATION', level=1)
        print("""
  For a Lagrangian penetration analysis in Abaqus/Explicit:

    * turn ON distortion control, leave `length ratio` at the default;
    * OR turn on enhanced hourglass control if ALLAE/ALLIE is your problem;
    * never both.

  Compare the depth column here with example 01. Then compare it with example 04.
  Section controls extend the Lagrangian range; ALE extends it further; neither
  makes it unlimited.
""")
    finally:
        report.stop_log(tee)


main()
