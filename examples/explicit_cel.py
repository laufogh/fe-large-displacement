"""Explicit CEL. The soil is a fixed box of space. The indenter stays Lagrangian.

    abaqus cae noGUI=examples/explicit_cel.py

This file is complete. Diff it against examples/explicit.py. The soil part
is the part that changes.
"""

from __future__ import print_function

import os

from abaqus import mdb
from abaqusConstants import (
    THREE_D, DEFORMABLE_BODY, EULERIAN, ON, OFF, C3D8R, EC3D8R, HEX,
    STRUCTURED, EXPLICIT, MIDDLE_SURFACE, FROM_SECTION, UNIFORM, CARTESIAN,
    STEP, ANALYSIS, PERCENTAGE, DEFAULT, HARD, PENALTY, ISOTROPIC, FRACTION,
    GLOBAL, SELF, DOMAIN, DOUBLE_PLUS_PACK, FULL, XYPLANE)
import interaction
import mesh
import regionToolset
import step


# --- numbers you may want to change ---------------------------------------

SEED = 0.025             # same mesh on every formulation
SOIL_LEN = 0.30
SOIL_WID = SEED          # one element through the strip (plane strain)
SOIL_DEP = 0.20

IND_HALF = 0.0225
IND_THICK = 0.010
IND_DEPTH = 0.150
IND_VEL = 0.1            # m/s. Slow enough that ALLKE/ALLIE stays small.
RAMP_FRAC = 0.05
VOID = 0.5 * IND_DEPTH   # empty space above the soil. do not set this to 0

SOIL_E = 20.0e6
SOIL_NU = 0.30
SOIL_SY = 50.0e3         # Pa, von Mises, no hardening
SOIL_RHO = 1651.6
FRICTION = 0.5

JOB_NAME = 'explicit_cel'


# --- working directory ----------------------------------------------------

workdir = os.environ.get('FLD_WORKDIR')
if not workdir:
    workdir = os.path.join(os.path.expanduser('~'), 'abaqus-fld', JOB_NAME)
workdir = os.path.abspath(workdir)
if not os.path.isdir(workdir):
    os.makedirs(workdir)
os.chdir(workdir)
print('working directory: %s' % workdir)


# --- model ----------------------------------------------------------------

# A new CAE session already has an empty Model-1. You cannot delete the last
# model in the database, so reuse it.
model = mdb.models['Model-1']

# Eulerian box: soil depth PLUS empty space above it for heave.
H = VOID
sketch = model.ConstrainedSketch(name='eul', sheetSize=10.0 * SOIL_LEN)
sketch.rectangle(point1=(-SOIL_LEN / 2.0, -SOIL_WID / 2.0),
                 point2=(SOIL_LEN / 2.0, SOIL_WID / 2.0))
eul = model.Part(name='Eulerian', dimensionality=THREE_D, type=EULERIAN)
eul.BaseSolidExtrude(sketch=sketch, depth=SOIL_DEP + H)

# Partition at the soil surface so the filled region is a cell, not a guess.
if H > 0.0:
    datum = eul.DatumPlaneByPrincipalPlane(principalPlane=XYPLANE,
                                           offset=SOIL_DEP)
    eul.PartitionCellByDatumPlane(datumPlane=eul.datums[datum.id],
                                  cells=eul.cells)

sketch_i = model.ConstrainedSketch(name='indenter', sheetSize=10.0 * SOIL_LEN)
sketch_i.rectangle(point1=(-IND_HALF, -SOIL_WID / 2.0),
                   point2=(IND_HALF, SOIL_WID / 2.0))
indenter = model.Part(name='Indenter', dimensionality=THREE_D,
                      type=DEFORMABLE_BODY)
indenter.BaseSolidExtrude(sketch=sketch_i, depth=IND_THICK)

soil_mat = model.Material(name='SoilMat')
soil_mat.Density(table=((SOIL_RHO,),))
soil_mat.Elastic(table=((SOIL_E, SOIL_NU),))
soil_mat.Plastic(table=((SOIL_SY, 0.0),))
steel = model.Material(name='SteelMat')
steel.Density(table=((7850.0,),))
steel.Elastic(table=((210.0e9, 0.3),))

# Eulerian section, not a solid section. The instance name is the EVF handle.
eul_key = 'soilmat-1'
model.EulerianSection(name='EulSec', data={eul_key: 'SoilMat'})
eul.SectionAssignment(region=regionToolset.Region(cells=eul.cells),
                      sectionName='EulSec')
model.HomogeneousSolidSection(name='IndSec', material='SteelMat')
indenter.SectionAssignment(region=regionToolset.Region(cells=indenter.cells),
                           sectionName='IndSec', offsetType=MIDDLE_SURFACE,
                           thicknessAssignment=FROM_SECTION)

eul.setElementType(
    regions=(eul.cells,),
    elemTypes=(mesh.ElemType(elemCode=EC3D8R, elemLibrary=EXPLICIT),))
eul.setMeshControls(regions=eul.cells, elemShape=HEX, technique=STRUCTURED)
eul.seedPart(size=SEED, deviationFactor=0.1, minSizeFactor=0.1)
eul.generateMesh()
indenter.setElementType(
    regions=(indenter.cells,),
    elemTypes=(mesh.ElemType(elemCode=C3D8R, elemLibrary=EXPLICIT),))
indenter.setMeshControls(regions=indenter.cells, elemShape=HEX,
                         technique=STRUCTURED)
indenter.seedPart(size=SEED, deviationFactor=0.1, minSizeFactor=0.1)
indenter.generateMesh()
print('Eulerian elements: %d' % len(eul.elements))

asm = model.rootAssembly
asm.DatumCsysByDefault(CARTESIAN)
eul_inst = asm.Instance(name='EulInst', part=eul, dependent=ON)
ind_inst = asm.Instance(name='IndInst', part=indenter, dependent=ON)
asm.translate(instanceList=('EulInst',), vector=(0.0, 0.0, -SOIL_DEP))
asm.translate(instanceList=('IndInst',), vector=(0.0, 0.0, 1.0e-6))

# Cells below z = 0 start full. Everything else starts empty.
filled = eul_inst.cells.getByBoundingBox(
    zMin=-SOIL_DEP - 1e-6, zMax=0.0 + 1e-6)
if len(filled) == 0:
    raise RuntimeError('no Eulerian cells below z = 0')
filled_set = asm.Set(name='SoilFilled', cells=filled)
model.MaterialAssignment(
    name='Eulerian material assignment',
    instanceList=(eul_inst,),
    useFields=False,
    assignmentList=((filled_set, (1.0,)),))
n_total = len(eul_inst.elements)
n_filled = len(filled_set.elements)
print('void fraction: %.0f %%' % (100.0 * (n_total - n_filled) / float(n_total)))

rp = asm.ReferencePoint(point=(0.0, 0.0, IND_THICK / 2.0))
rp_region = regionToolset.Region(
    referencePoints=(asm.referencePoints[rp.id],))
asm.Set(name='IndRP', referencePoints=(asm.referencePoints[rp.id],))
model.RigidBody(name='IndRigid', refPointRegion=rp_region,
                bodyRegion=regionToolset.Region(cells=ind_inst.cells),
                refPointAtCOM=ON)

time_period = IND_DEPTH / float(IND_VEL)
model.ExplicitDynamicsStep(
    name='Push', previous='Initial', timePeriod=time_period,
    nlgeom=ON, improvedDtMethod=ON)
model.SmoothStepAmplitude(
    name='Ramp', timeSpan=STEP,
    data=((0.0, 0.0), (RAMP_FRAC * time_period, 1.0)))
model.HistoryOutputRequest(
    name='Energies', createStepName='Push',
    variables=('ALLIE', 'ALLKE', 'ALLAE', 'ALLDC', 'ALLVD', 'ALLWK',
               'ETOTAL'),
    numIntervals=200)
model.HistoryOutputRequest(
    name='RP', createStepName='Push', region=asm.sets['IndRP'],
    variables=('U1', 'U2', 'U3', 'RF1', 'RF2', 'RF3'), numIntervals=500)
model.fieldOutputRequests['F-Output-1'].setValues(
    variables=('S', 'PE', 'LE', 'U', 'V', 'RF', 'EVF', 'STATUS'),
    numIntervals=20)

# Walls: zero normal motion on sides and base. The top is open.
top = H
for name, point, dof in (
        ('XMIN', (-SOIL_LEN / 2.0, 0.0, (top - SOIL_DEP) / 2.0), 1),
        ('XMAX', (SOIL_LEN / 2.0, 0.0, (top - SOIL_DEP) / 2.0), 1),
        ('YMIN', (0.0, -SOIL_WID / 2.0, (top - SOIL_DEP) / 2.0), 2),
        ('YMAX', (0.0, SOIL_WID / 2.0, (top - SOIL_DEP) / 2.0), 2)):
    faces = eul_inst.faces.findAt((point,))
    if len(faces) == 0:
        raise RuntimeError('missed Eulerian wall %s at %r' % (name, point))
    kwargs = {'name': 'Wall-' + name, 'createStepName': 'Initial',
              'region': regionToolset.Region(faces=faces),
              'distributionType': UNIFORM}
    kwargs['u%d' % dof] = 0.0
    model.DisplacementBC(**kwargs)
base = eul_inst.faces.findAt(((0.0, 0.0, -SOIL_DEP),))
if len(base) == 0:
    raise RuntimeError('missed the Eulerian base')
model.DisplacementBC(name='Wall-BASE', createStepName='Initial',
                     region=regionToolset.Region(faces=base),
                     u3=0.0, distributionType=UNIFORM)

model.VelocityBC(
    name='Push', createStepName='Push', region=asm.sets['IndRP'],
    v1=0.0, v2=0.0, v3=-IND_VEL, vr1=0.0, vr2=0.0, vr3=0.0,
    amplitude='Ramp', distributionType=UNIFORM)

prop = model.ContactProperty('Interface')
prop.NormalBehavior(pressureOverclosure=HARD, allowSeparation=ON,
                    constraintEnforcementMethod=DEFAULT)
prop.TangentialBehavior(
    formulation=PENALTY, directionality=ISOTROPIC, table=((FRICTION,),),
    maximumElasticSlip=FRACTION, fraction=0.005)
# General contact is mandatory for CEL.
contact = model.ContactExp(name='GeneralContact', createStepName='Push')
contact.includedPairs.setValuesInStep(stepName='Push', useAllstar=True)
contact.contactPropertyAssignments.appendInStep(
    stepName='Push', assignments=((GLOBAL, SELF, 'Interface'),))


# --- write, check, maybe submit -------------------------------------------

job = mdb.Job(
    name=JOB_NAME, model='Model-1', type=ANALYSIS,
    explicitPrecision=DOUBLE_PLUS_PACK, nodalOutputPrecision=FULL,
    numCpus=1, numDomains=1, parallelizationMethodExplicit=DOMAIN,
    multiprocessingMode=DEFAULT, memory=90, memoryUnits=PERCENTAGE)
job.writeInput()
inp = os.path.join(workdir, JOB_NAME + '.inp')
print('wrote %s' % inp)
print('open that file and check: *Eulerian Section, EC3D8R, VOLUME FRACTION')

submit = os.environ.get('FLD_SUBMIT', '1').strip().lower() not in (
    '0', 'false', 'no', 'off')
if submit:
    job.submit(consistencyChecking=OFF)
    job.waitForCompletion()
    print('job finished. plot EVF to see where the soil is.')
else:
    print('FLD_SUBMIT=0: deck written, not submitted.')
