"""Explicit CEL. The soil is a fixed box of space. The indenter stays Lagrangian.

    abaqus cae noGUI=examples/indenter/explicit_cel/model.py

Elements never invert. The free surface is one element thick. Heave needs
empty space above the soil. There is no `*Geostatic` for an Eulerian domain.

Cases
-----
A  no void above the soil. The mistake. Resistance is silently too high.
B  void = 0.5 times the penetration depth. The configuration to use.

Compare resistance, at a depth the Lagrangian and ALE runs also reached,
against those runs. Agreement there is the check most people skip.
See docs/05-cel.md.
"""

from __future__ import print_function

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
sys.path.insert(0, os.path.join(_ROOT, 'lib'))
sys.path.insert(0, os.path.join(_ROOT, 'examples'))

from abaqus import mdb
from abaqusConstants import (THREE_D, EULERIAN, DEFORMABLE_BODY, ON, OFF,
                             MIDDLE_SURFACE, FROM_SECTION, UNIFORM, CARTESIAN,
                             XYPLANE, C3D8R, EXPLICIT, HEX, STRUCTURED)
import mesh
import regionToolset

from fldlib import config, report, jobs, steps, materials, contact, cel
from common import indenter_model, runner
from postproc import energy


STUDY = 'indenter_explicit_cel'
CASES = ['A', 'B']
CASE_DOC = {
    'A': 'no void above the soil (heave has nowhere to go)',
    'B': 'void = 0.5 x penetration depth',
}


def make_params():
    P = config.Params(STUDY)
    indenter_model.declare(P)
    P.add('void_mult', 0.5, '-', 'void thickness / penetration depth (case B)')
    return P.resolve()


def build_cel(P, model_name, void_thickness, seed):
    """Eulerian version of the shared indenter. Same handle keys as needed."""
    if model_name in mdb.models:
        del mdb.models[model_name]
    model = mdb.Model(name=model_name)

    L, W, D = P.soil_len, P.soil_wid, P.soil_dep
    H = void_thickness

    sk = model.ConstrainedSketch(name='eul_plan', sheetSize=10.0 * L)
    sk.rectangle(point1=(-L / 2.0, -W / 2.0), point2=(L / 2.0, W / 2.0))
    eul = model.Part(name='Eulerian', dimensionality=THREE_D, type=EULERIAN)
    eul.BaseSolidExtrude(sketch=sk, depth=D + H)

    if H > 0.0:
        datum = eul.DatumPlaneByPrincipalPlane(principalPlane=XYPLANE,
                                               offset=D)
        eul.PartitionCellByDatumPlane(datumPlane=eul.datums[datum.id],
                                      cells=eul.cells)

    a, t = P.ind_half, P.ind_thick
    ski = model.ConstrainedSketch(name='ind_plan', sheetSize=10.0 * L)
    ski.rectangle(point1=(-a, -W / 2.0), point2=(a, W / 2.0))
    ind = model.Part(name='Indenter', dimensionality=THREE_D,
                     type=DEFORMABLE_BODY)
    ind.BaseSolidExtrude(sketch=ski, depth=t)

    if P.soil_model == 'elastic':
        materials.elastic_soil(model, 'SoilMat', P.soil_e, P.soil_nu,
                               P.soil_rho)
    elif P.soil_model == 'mc':
        materials.mohr_coulomb_soil(model, 'SoilMat', P.soil_e, P.soil_nu,
                                    P.soil_rho, P.soil_phi, P.soil_psi,
                                    P.soil_coh)
    else:
        raise ValueError('explicit CEL supports soil_model elastic or mc '
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
                           'structured hex mesh.')

    asm = model.rootAssembly
    asm.DatumCsysByDefault(CARTESIAN)
    eul_inst = asm.Instance(name='EulInst', part=eul, dependent=ON)
    ind_inst = asm.Instance(name='IndInst', part=ind, dependent=ON)
    asm.translate(instanceList=('EulInst',), vector=(0.0, 0.0, -D))
    asm.translate(instanceList=('IndInst',), vector=(0.0, 0.0, 1.0e-6))

    filled = eul_inst.cells.getByBoundingBox(
        zMin=-D - 1e-6, zMax=0.0 + 1e-6)
    if len(filled) == 0:
        raise RuntimeError('no Eulerian cells found below z = 0')
    filled_set = asm.Set(name='SoilFilled', cells=filled)
    cel.assign_material(model, asm, eul_inst, filled_set)
    cel.check_void_fraction(asm, eul_inst, 'SoilFilled')

    rp = asm.ReferencePoint(point=(0.0, 0.0, t / 2.0))
    rp_region = regionToolset.Region(
        referencePoints=(asm.referencePoints[rp.id],))
    asm.Set(name='IndRP', referencePoints=(asm.referencePoints[rp.id],))
    model.RigidBody(name='IndRigid', refPointRegion=rp_region,
                    bodyRegion=regionToolset.Region(cells=ind_inst.cells),
                    refPointAtCOM=ON)

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
            raise RuntimeError('findAt missed the %s Eulerian wall at %r'
                               % (name, point))
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
    job_name = 'expcel_%s' % case
    handles = build_cel(P, 'ExpCel_' + case, void, P.seed)
    print('  Eulerian elements: %d  (void thickness %.4g m)'
          % (handles['n_elements'], void))
    steps.report_time_budget(P.seed, P.soil_e, P.soil_nu, P.soil_rho,
                             P.ind_depth, P.ind_vel)

    n_cpus = int(os.environ.get('FLD_NCPU', P.n_cpus))
    job = jobs.make_explicit_job('ExpCel_' + case, job_name, n_cpus=n_cpus,
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
        return {'void_m': void, 'elements': handles['n_elements'],
                'submitted': False}

    jobs.submit(job)
    st = jobs.status(job_name, workdir)
    depth = st['step_time'] * P.ind_vel if st['step_time'] else None
    row = {
        'void_m': void,
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
                           'INDENTER -- EXPLICIT CEL')
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
