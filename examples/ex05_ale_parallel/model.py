"""Example 05 -- ALE and parallel decomposition: why one big adaptive region is
the wrong shape.

    abaqus cae noGUI=examples/ex05_ale_parallel/model.py

Run this one on the compute machine, not a laptop. It wants 15 CPUs and 15
domains to show what it is about (override with FLD_NCPU / FLD_NDOMAINS).

The problem
-----------
Abaqus/Explicit parallelises by splitting the model into domains, one per CPU,
and balancing the element count between them. An ALE adaptive region costs more
per element than a Lagrangian one -- sweeps plus advection -- and the packager
handles that by putting the whole adaptive region in **one** domain. On 15 CPUs
that domain ends up carrying 2.5x the balanced load, and every increment waits
for it.

Worse, nodes shared between parallel domains are marked **nonadaptive**. So
running an ALE model on many CPUs both unbalances the work and quietly disables
ALE across every domain boundary.

What was measured (15 CPUs, 15 domains, ~50 000 C3D8R)
------------------------------------------------------
=====  ========================================  ==========================  ============
case   configuration                             region -> parallel domain   max weight
=====  ========================================  ==========================  ============
A      no ALE                                    --                          6.67 (ideal)
B      one region, 5600 el                       R1 -> d15                   **15.15**
C      two non-adjacent regions, 2800 el each    R1 -> d15, R2 -> d14        8.22
D      four non-adjacent regions, 1400 el each   R1..R4 -> d1, d6, d10, d15  **6.67**
E      two adjacent regions sharing a face       R1 -> d15, R2 -> d15        15.15
=====  ========================================  ==========================  ============

Case D is the result worth remembering: **four small, well-separated regions
covering the same 5600 elements cost nothing at all in load balance.** Case E is
the caveat: regions that touch are treated as one region, so the separation has
to be real -- at least one band of non-adaptive elements between them.

The price of fragmenting is more nonadaptive nodes (1922 for one region, 3048
for four), because smaller regions have more surface per unit volume and
boundary nodes are suppressed. That is a genuine trade: D gives perfect load
balance and 59 % more suppressed nodes than B. Which matters more depends on
whether you are CPU-bound or mesh-quality-bound.

How several regions are defined
-------------------------------
CAE holds only one `AdaptiveMeshDomain` per step -- the second call silently
replaces the first. The solver has no such limit, so the first domain is
defined through the API (which also writes the controls block) and the rest are
injected as extra `*Adaptive Mesh` lines. See
`fldlib.inpedit.inject_extra_ale_domains`.

Reading the result
------------------
Each adaptive region writes its `Summary Diagnostics for Adaptive Meshing` block
**only to the `.msg.N` of the parallel domain that hosts it.** That is how the
region-to-domain mapping in the table above was obtained, and this script
reproduces it by scanning every `.msg.N`.
"""

from __future__ import print_function

import glob
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_ROOT, 'lib'))
sys.path.insert(0, os.path.join(_ROOT, 'examples'))

from abaqusConstants import UNIFORM                            # noqa: E402
from fldlib import config, report, jobs, ale, inpedit          # noqa: E402
from common import indenter_model, runner                      # noqa: E402


STUDY = 'ex05_ale_parallel'
CASES = ['A', 'B', 'C', 'D', 'E']

CASE_DOC = {
    'A': 'no ALE (balanced reference)',
    'B': 'one adaptive region',
    'C': 'two non-adjacent regions',
    'D': 'four non-adjacent regions   <- best load balance',
    'E': 'two adjacent regions sharing a face (behaves as one)',
}


def make_params():
    P = config.Params(STUDY)
    indenter_model.declare(P)
    P.add('band', 2, '-', 'element bands of non-adaptive material between regions')
    P.add('region_half_x', 0.0675, 'm', 'total adaptive half-width in x')
    P.add('region_depth', 0.060, 'm', 'adaptive depth below the surface')
    return P.resolve()


def region_boxes(P, case):
    """Boxes for each case, all covering the same total adaptive volume.

    Keeping the total adaptive element count equal across B, C, D and E is what
    makes the comparison mean anything: any difference in decomposition is then
    caused by the *shape* of the regions, not by how much ALE work there is.
    """
    hx, dz = P.region_half_x, P.region_depth
    gap = P.band * P.seed
    y = dict(ymin=-P.soil_wid, ymax=P.soil_wid)
    z = dict(zmin=-dz, zmax=0.0)

    if case == 'A':
        return []
    if case == 'B':
        return [dict(xmin=-hx, xmax=hx, **dict(y, **z))]
    if case == 'C':
        # two halves, pulled apart so a band of non-adaptive elements sits
        # between them
        w = hx - gap / 2.0
        return [dict(xmin=-hx, xmax=-hx + w, **dict(y, **z)),
                dict(xmin=hx - w, xmax=hx, **dict(y, **z))]
    if case == 'D':
        w = (2.0 * hx - 3.0 * gap) / 4.0
        out = []
        x = -hx
        for _ in range(4):
            out.append(dict(xmin=x, xmax=x + w, **dict(y, **z)))
            x += w + gap
        return out
    if case == 'E':
        # two regions sharing the face at x = 0 -- no gap
        return [dict(xmin=-hx, xmax=0.0, **dict(y, **z)),
                dict(xmin=0.0, xmax=hx, **dict(y, **z))]
    raise ValueError(case)


def parse_domain_map(workdir, job_name, n_regions):
    """Which parallel domain hosted each adaptive region.

    Scans every `<job>.msg.N`. A domain whose `.msg.N` contains adaptive
    diagnostics hosted at least one region.
    """
    pattern = os.path.join(workdir, job_name + '.msg*')
    hosts = []
    for path in sorted(glob.glob(pattern)):
        suffix = path.rsplit('.msg', 1)[-1]
        domain = int(suffix.lstrip('.')) if suffix.strip('.').isdigit() else 0
        info = ale.read_msg_activity(path)
        if info['blocks']:
            hosts.append((domain, info['blocks'], info['avg_pct_moved']))
    for domain, blocks, pct in hosts:
        print('    domain %-3d  %4d diagnostic block(s)  avg %.1f %% moved'
              % (domain, blocks, pct))
    if not hosts:
        print('    (no adaptive diagnostics in any .msg -- ALE was inert)')
    return hosts


def run_case(case, workdir, P):
    print('  %s: %s' % (case, CASE_DOC[case]))

    model_name = 'Ex05_' + case
    job_name = 'ex05_%s' % case
    handles = indenter_model.build(P, model_name=model_name, solver='explicit')
    model, asm = handles['model'], handles['assembly']
    soil_inst, step_name = handles['soil_inst'], handles['step_name']
    n_soil = handles['n_soil_elements']

    boxes = region_boxes(P, case)
    names, total_adaptive = [], 0
    if boxes:
        ale.make_controls(model, 'ALE_BC', smoothing=UNIFORM)
        for i, box in enumerate(boxes, start=1):
            name = 'ALE_R%d' % i
            n, bbox = ale.box_element_set(asm, soil_inst, name, box)
            ale.describe_box_set(name, n, bbox, total=n_soil)
            names.append(name)
            total_adaptive += n
        ale.add_domain(model, step_name, asm.sets[names[0]], 'ALE_BC',
                       initial_mesh_sweeps=5)

    n_cpus = int(os.environ.get('FLD_NCPU', 15))
    n_dom = int(os.environ.get('FLD_NDOMAINS', n_cpus))
    print('  parallel: %d CPU(s), %d domain(s)' % (n_cpus, n_dom))

    job = jobs.make_explicit_job(model_name, job_name, n_cpus=n_cpus,
                                 n_domains=n_dom, description=CASE_DOC[case])
    inp = jobs.write_input(job, workdir)
    inpedit.inject_diagnostics(inp, mode='summary')

    if len(names) > 1:
        n_extra = inpedit.inject_extra_ale_domains(inp, names[1:],
                                                   controls='ALE_BC',
                                                   initial_mesh_sweeps=5)
        print('  injected %d extra *Adaptive Mesh domain line(s)' % n_extra)

    chk = report.InpCheck(inp)
    chk.requires(r'^\*Diagnostics, adaptive mesh=summary', 'diagnostics on')
    chk.count(r'^\*Adaptive Mesh,', len(names),
              '%d adaptive mesh domain line(s)' % len(names))
    if names:
        chk.count(r'^\*Adaptive Mesh Controls', 1,
                  'one shared controls definition')
        for name in names:
            chk.requires(r'^\*Adaptive Mesh,.*elset=%s\b' % name,
                         'region %s has its own domain line' % name)
    chk.report()

    if not runner.flag('SUBMIT', True):
        return {'regions': len(names), 'adaptive_el': total_adaptive,
                'submitted': False}

    jobs.submit(job)
    st = jobs.status(job_name, workdir)

    print('  region -> parallel domain (from the per-domain .msg files):')
    hosts = parse_domain_map(workdir, job_name, len(names))

    return {
        'regions': len(names),
        'adaptive_el': total_adaptive,
        'host_domains': len(hosts),
        'distributed': (len(hosts) > 1) if len(names) > 1 else None,
        'increments': st['increments'],
        'wall_note': 'compare against case A',
        'completed': st['completed'],
    }


def main():
    workdir = config.workdir(STUDY)
    os.chdir(workdir)

    tee = report.start_log(os.path.join(workdir, STUDY + '.log'),
                           'EXAMPLE 05 -- ALE AND PARALLEL DECOMPOSITION')
    try:
        print(__doc__)
        P = make_params()
        P.show()
        P.write_json(os.path.join(workdir, STUDY + '_params.json'))

        rows = runner.run_study(
            STUDY, CASES, lambda c, w: run_case(c, w, P), workdir)
        runner.write_summary_csv(
            os.path.join(workdir, STUDY + '_summary.csv'), rows)

        report.banner('PRACTICAL RULE', level=1)
        print("""
  If you are running ALE on many CPUs, split the adaptive zone into several
  regions separated by at least one band of non-adaptive elements. Four regions
  cost nothing in load balance; one region costs you a 2.5x imbalance on every
  increment.

  Check the `.sta` decomposition report for the per-domain weights, and check
  every `.msg.N` for adaptive diagnostics. A region with no diagnostic block
  anywhere is inert.
""")
    finally:
        report.stop_log(tee)


main()
