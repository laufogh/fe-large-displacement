"""Example 06 -- Coupled Eulerian-Lagrangian: the same problem, third formulation.

    abaqus cae noGUI=examples/ex06_cel_indenter/model.py

Examples 01 to 05 kept the mesh attached to the material and worked increasingly
hard to keep it usable. This one gives up on that entirely. The soil becomes a
fixed box of space through which material flows; the indenter stays Lagrangian;
the two meet through general contact.

The benefit is that there is no distortion limit at all. Elements never deform,
so no element ever inverts and no run ever aborts on distortion. You can push
the indenter to any depth you like.

The costs are real and you should see them here rather than discover them later:

* **The free surface is diffuse.** The material boundary is reconstructed inside
  each element from volume fractions, so it is roughly one element thick. Heave
  looks blurred and the contact surface is only as sharp as your mesh.
* **You need empty space.** If the soil fills the mesh to the top, heave has
  nowhere to go and your resistance is wrong -- silently. Case A shows this.
* **There is no geostatic procedure for an Eulerian domain.** You cannot run
  `*Geostatic`. Either settle it dynamically (slow, and it rings) or initialise
  the stress field directly.
* **It is expensive per unit of answer.** Most of your elements are empty most
  of the time, and you still pay for them.

Cases
-----
A  no void space above the soil          -- the mistake, and what it costs
B  void = 0.5x the penetration depth     -- the sensible configuration
C  as B with half the element size       -- how much of the answer was mesh

What to compare against
-----------------------
The depth column from examples 01, 03 and 04 on the same physical problem.
Lagrangian aborts somewhere; ALE gets further; CEL does not abort at all. Then
compare the *resistance* at a depth all four reached. Agreement there is the
evidence that the CEL model is solving the same problem, and it is the check
most people skip.
"""

from __future__ import print_function

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_ROOT, 'lib'))
sys.path.insert(0, os.path.join(_ROOT, 'examples'))

from abaqus import mdb                                          # noqa: E402
from abaqusConstants import (THREE_D, EULERIAN, DEFORMABLE_BODY, ON, OFF,
                             MIDDLE_SURFACE, FROM_SECTION, UNIFORM, CARTESIAN,
                             XYPLANE, C3D8R, EXPLICIT, HEX, STRUCTURED)  # noqa: E402
import mesh                                                     # noqa: E402
import regionToolset                                            # noqa: E402

from fldlib import (config, report, jobs, steps, materials, contact, cel,
                    inpedit)                                    # noqa: E402
from common import indenter_model, runner                       # noqa: E402
from postproc import energy                                     # noqa: E402


STUDY = 'ex06_cel_indenter'
CASES = ['A', 'B', 'C']

CASE_DOC = {
    'A': 'no void above the soil (heave has nowhere to go)',
    'B': 'void = 0.5 x penetration depth',
    'C': 'void = 0.5 x penetration depth, seed halved',
}


def make_params():
    P = config.Params(STUDY)
    indenter_model.declare(P)
    P.add('void_mult', 0.5, '-', 'void thickness / penetration depth (case B)')
    return P.resolve()


def build_cel(P, model_name, void_thickness, seed):
    """Build the Eulerian version of the benchmark.

    Returns the same handle dict shape as `indenter_model.build`, so the
    post-processing is identical.
    """
    if model_name in mdb.models:
        del mdb.models[model_name]
    model = mdb.Model(name=model_name)

    L, W, D = P.soil_len, P.soil_wid, P.soil_dep
    H = void_thickness

    # -- Eulerian part: soil PLUS the empty space above it -----------------
    sk = model.ConstrainedSketch(name='eul_plan', sheetSize=10.0 * L)
    sk.rectangle(point1=(-L / 2.0, -W / 2.0), point2=(L / 2.0, W / 2.0))
    eul = model.Part(name='Eulerian', dimensionality=THREE_D, type=EULERIAN)
    eul.BaseSolidExtrude(sketch=sk, depth=D + H)   # part z in [0, D+H]

    # Partition at the soil surface so the filled region is a cell, not an
    # element-by-element guess. A partition is exact; a bounding-box filter on
    # element centroids is not, and for the *initial* volume fraction you want
    # exactness.
    if H > 0.0:
        datum = eul.DatumPlaneByPrincipalPlane(principalPlane=XYPLANE,
                                               offset=D)
        eul.PartitionCellByDatumPlane(datumPlane=eul.datums[datum.id],
                                      cells=eul.cells)

    # -- indenter ----------------------------------------------------------
    a, t = P.ind_half, P.ind_thick
    ski = model.ConstrainedSketch(name='ind_plan', sheetSize=10.0 * L)
    ski.rectangle(point1=(-a, -W / 2.0), point2=(a, W / 2.0))
    ind = model.Part(name='Indenter', dimensionality=THREE_D,
                     type=DEFORMABLE_BODY)
    ind.BaseSolidExtrude(sketch=ski, depth=t)

    # -- materials ---------------------------------------------------------
    if P.soil_model == 'elastic':
        materials.elastic_soil(model, 'SoilMat', P.soil_e, P.soil_nu,
                               P.soil_rho)
    elif P.soil_model == 'mc':
        materials.mohr_coulomb_soil(model, 'SoilMat', P.soil_e, P.soil_nu,
                                    P.soil_rho, P.soil_phi, P.soil_psi,
                                    P.soil_coh)
    else:
        raise ValueError('example 06 supports soil_model elastic or mc '
                         '(got %r)' % P.soil_model)
    materials.steel(model, name='SteelMat')

    section, evf_key = cel.eulerian_section(model, 'EulSec', 'SoilMat')
    print('  Eulerian material instance key: %s' % evf_key)
    eul.SectionAssignment(region=regionToolset.Region(cells=eul.cells),
                          sectionName='EulSec')

    model.HomogeneousSolidSection(name='IndSec', material='SteelMat',
                                  thickness=None)
    ind.SectionAssignment(region=regionToolset.Region(cells=ind.cells),
                          sectionName='IndSec', offsetType=MIDDLE_SURFACE,
                          thicknessAssignment=FROM_SECTION)

    # -- mesh --------------------------------------------------------------
    cel.set_eulerian_element_type(eul)
    eul.seedPart(size=seed, deviationFactor=0.1, minSizeFactor=0.1)
    eul.generateMesh()

    ind.setElementType(regions=(ind.cells,),
                       elemTypes=(mesh.ElemType(elemCode=C3D8R,
                                                elemLibrary=EXPLICIT),))
    ind.setMeshControls(regions=ind.cells, elemShape=HEX, technique=STRUCTURED)
    ind.seedPart(size=seed, deviationFactor=0.1, minSizeFactor=0.1)
    ind.generateMesh()

    n_eul = len(eul.elements)
    if n_eul == 0:
        raise RuntimeError('the Eulerian mesh is empty. EC3D8R requires a '
                           'structured hex mesh; check the partition did not '
                           'create a cell that cannot be swept.')

    # -- assembly ----------------------------------------------------------
    asm = model.rootAssembly
    asm.DatumCsysByDefault(CARTESIAN)
    eul_inst = asm.Instance(name='EulInst', part=eul, dependent=ON)
    ind_inst = asm.Instance(name='IndInst', part=ind, dependent=ON)
    asm.translate(instanceList=('EulInst',), vector=(0.0, 0.0, -D))
    asm.translate(instanceList=('IndInst',), vector=(0.0, 0.0, 1.0e-6))

    # -- initial volume fraction ------------------------------------------
    # Everything below z = 0 starts full; everything above starts empty.
    filled = eul_inst.cells.getByBoundingBox(
        zMin=-D - 1e-6, zMax=0.0 + 1e-6)
    if len(filled) == 0:
        raise RuntimeError('no Eulerian cells found below z = 0 -- the '
                           'material assignment would be empty and the whole '
                           'domain would start as void.')
    filled_set = asm.Set(name='SoilFilled', cells=filled)
    cel.assign_material(model, asm, eul_inst, filled_set)
    cel.check_void_fraction(asm, eul_inst, 'SoilFilled')

    # -- rigid indenter ----------------------------------------------------
    rp = asm.ReferencePoint(point=(0.0, 0.0, t / 2.0))
    rp_region = regionToolset.Region(
        referencePoints=(asm.referencePoints[rp.id],))
    asm.Set(name='IndRP', referencePoints=(asm.referencePoints[rp.id],))
    model.RigidBody(name='IndRigid', refPointRegion=rp_region,
                    bodyRegion=regionToolset.Region(cells=ind_inst.cells),
                    refPointAtCOM=ON)

    # -- step and output ---------------------------------------------------
    time_period = P.ind_depth / float(P.ind_vel)
    step_name = 'Push'
    steps.explicit_step(model, step_name, 'Initial', time_period, nlgeom=True)
    steps.smooth_ramp(model, 'Ramp', P.ramp_frac, time_period)
    steps.energy_output(model, step_name, interval=200)
    model.HistoryOutputRequest(
        name='RP', createStepName=step_name, region=asm.sets['IndRP'],
        variables=('U1', 'U2', 'U3', 'RF1', 'RF2', 'RF3'), numIntervals=500)
    model.fieldOutputRequests['F-Output-1'].setValues(
        variables=('S', 'PE', 'PEEQ', 'LE', 'U', 'V', 'A', 'RF', 'CSTRESS',
                   'EVF', 'STATUS'),
        numIntervals=20)

    # -- boundary conditions ----------------------------------------------
    # The Eulerian domain is a fixed box: no material may leave through its
    # sides or base, so the normal velocity is zero there. The TOP is left free
    # -- it is the outflow boundary, and closing it is another way to lose heave.
    _eulerian_walls(model, asm, eul_inst, L, W, D, H)

    model.VelocityBC(name='Push', createStepName=step_name,
                     region=asm.sets['IndRP'],
                     v1=0.0, v2=0.0, v3=-P.ind_vel,
                     vr1=0.0, vr2=0.0, vr3=0.0,
                     amplitude='Ramp', distributionType=UNIFORM)

    contact.friction_property(model, 'Interface', mu=P.friction, hard=True)
    contact.general_contact(model, step_name, 'Interface')

    return {'model': model, 'assembly': asm, 'step_name': step_name,
            'n_elements': n_eul, 'time_period': time_period,
            'evf_key': evf_key}


def _eulerian_walls(model, asm, inst, L, W, D, H):
    """Zero normal velocity on the four sides and the base of the Eulerian box."""
    top = H
    picks = {
        'XMIN': ((-L / 2.0, 0.0, (top - D) / 2.0), 1),
        'XMAX': ((L / 2.0, 0.0, (top - D) / 2.0), 1),
        'YMIN': ((0.0, -W / 2.0, (top - D) / 2.0), 2),
        'YMAX': ((0.0, W / 2.0, (top - D) / 2.0), 2),
    }
    for name, (point, dof) in picks.items():
        faces = inst.faces.findAt((point,))
        if len(faces) == 0:
            raise RuntimeError('findAt missed the %s Eulerian wall at %r -- '
                               'material would be free to leave the domain '
                               'sideways' % (name, point))
        kwargs = {'name': 'Wall-' + name, 'createStepName': 'Initial',
                  'region': regionToolset.Region(faces=faces),
                  'distributionType': UNIFORM}
        kwargs['u%d' % dof] = 0.0
        model.DisplacementBC(**kwargs)

    base = inst.faces.findAt(((0.0, 0.0, -D),))
    if len(base) == 0:
        raise RuntimeError('findAt missed the Eulerian base at (0, 0, %g)' % -D)
    model.DisplacementBC(name='Wall-BASE', createStepName='Initial',
                         region=regionToolset.Region(faces=base),
                         u3=0.0, distributionType=UNIFORM)


def run_case(case, workdir, P):
    print('  %s: %s' % (case, CASE_DOC[case]))

    void = 0.0 if case == 'A' else P.void_mult * P.ind_depth
    seed = P.seed / 2.0 if case == 'C' else P.seed

    model_name = 'Ex06_' + case
    job_name = 'ex06_%s' % case
    handles = build_cel(P, model_name, void, seed)
    print('  Eulerian elements: %d  (void thickness %.4g m, seed %.4g m)'
          % (handles['n_elements'], void, seed))

    steps.report_time_budget(seed, P.soil_e, P.soil_nu, P.soil_rho,
                             P.ind_depth, P.ind_vel)

    n_cpus = int(os.environ.get('FLD_NCPU', P.n_cpus))
    job = jobs.make_explicit_job(model_name, job_name, n_cpus=n_cpus,
                                 description=CASE_DOC[case])
    inp = jobs.write_input(job, workdir)

    chk = report.InpCheck(inp)
    chk.requires(r'^\*Eulerian Section', 'the soil uses an Eulerian section')
    chk.requires(r'type=EC3D8R|EC3D8R', 'Eulerian elements EC3D8R')
    chk.requires(r'^\*Initial Conditions, type=VOLUME FRACTION',
                 'initial volume fraction assigned')
    chk.requires(r'^\*Contact\b', 'general contact (mandatory for CEL)')
    chk.forbids(r'^\*Adaptive Mesh,',
                'no ALE -- the Eulerian mesh never moves')
    chk.report()

    if not runner.flag('SUBMIT', True):
        return {'void_m': void, 'seed': seed,
                'elements': handles['n_elements'], 'submitted': False}

    jobs.submit(job)
    st = jobs.status(job_name, workdir)
    depth = st['step_time'] * P.ind_vel if st['step_time'] else None

    row = {
        'void_m': void,
        'seed': seed,
        'elements': handles['n_elements'],
        'increments': st['increments'],
        'depth_m': depth,
        'completed': st['completed'],
        'distortion_abort': jobs.distortion_aborted(st),
        'abort': (st['abort_reason'] or '')[:50],
    }
    odb = os.path.join(workdir, job_name + '.odb')
    if os.path.isfile(odb):
        r = energy.ratios(energy.read_energies(odb))
        row['ke_peak_%'] = 100.0 * r['ALLKE/ALLIE']['peak']
    return row


def main():
    workdir = config.workdir(STUDY)
    os.chdir(workdir)

    tee = report.start_log(os.path.join(workdir, STUDY + '.log'),
                           'EXAMPLE 06 -- COUPLED EULERIAN-LAGRANGIAN')
    try:
        print(__doc__)
        P = make_params()
        P.show()
        P.write_json(os.path.join(workdir, STUDY + '_params.json'))

        rows = runner.run_study(
            STUDY, CASES, lambda c, w: run_case(c, w, P), workdir)
        runner.write_summary_csv(
            os.path.join(workdir, STUDY + '_summary.csv'), rows)

        report.banner('WHAT TO LOOK AT IN THE ODB', level=1)
        print("""
  Plot EVF on the Eulerian instance. You will see:

    * the soil surface as a band of partially-filled elements rather than a
      line -- that band is your surface resolution;
    * in case A, material piling up against the top of the domain with nowhere
      to go, and a resistance that is too high for the wrong reason;
    * in case C, a visibly sharper surface for four times the element count.

  CEL does not abort on distortion. That is not the same as CEL being right.
  The check is still the energy balance, plus agreement with the Lagrangian and
  ALE runs over the depth range where all three are valid.
""")
    finally:
        report.stop_log(tee)


main()
