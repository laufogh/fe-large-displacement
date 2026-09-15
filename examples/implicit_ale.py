"""Implicit ALE. Same Standard model as implicit/, plus an adaptive mesh.

    abaqus cae noGUI=examples/implicit_ale.py

Abaqus/Standard ALE is limited. Expect it to fail in much the same place
as the implicit Lagrangian run. This file is complete. Diff it against
examples/implicit.py to see the extra lines.
"""

from __future__ import print_function

import os

from abaqus import mdb
from abaqusConstants import (
    THREE_D, DEFORMABLE_BODY, ON, OFF, C3D8R, HEX, STRUCTURED, STANDARD,
    MIDDLE_SURFACE, FROM_SECTION, UNIFORM, CARTESIAN, STEP, ANALYSIS,
    PERCENTAGE, DEFAULT, HARD, PENALTY,
    ISOTROPIC, FRACTION, GLOBAL, SELF)
import interaction
import mesh
import regionToolset
import step


# --- numbers you may want to change ---------------------------------------

SEED = 0.010             # same mesh on every formulation
SOIL_LEN = 0.30
SOIL_WID = SEED          # one element through the strip (plane strain)
SOIL_DEP = 0.20

IND_HALF = 0.0225
IND_THICK = 0.010
IND_DEPTH = 0.150

SOIL_E = 20.0e6
SOIL_NU = 0.30
SOIL_SY = 50.0e3         # Pa, von Mises, no hardening
SOIL_RHO = 1651.6
FRICTION = 0.5

JOB_NAME = 'implicit_ale'


# --- working directory ----------------------------------------------------

workdir = os.environ.get('FLD_WORKDIR')
if not workdir:
    workdir = os.path.join(os.path.expanduser('~'), 'abaqus-fld', JOB_NAME)
workdir = os.path.abspath(workdir)
if not os.path.isdir(workdir):
    os.makedirs(workdir)
os.chdir(workdir)
print('working directory: %s' % workdir)


# --- model (same as implicit/model.py until the ALE block) ----------------

# A new CAE session already has an empty Model-1. You cannot delete the last
# model in the database, so reuse it.
model = mdb.models['Model-1']

sketch = model.ConstrainedSketch(name='soil', sheetSize=10.0 * SOIL_LEN)
sketch.rectangle(point1=(-SOIL_LEN / 2.0, -SOIL_WID / 2.0),
                 point2=(SOIL_LEN / 2.0, SOIL_WID / 2.0))
soil = model.Part(name='Soil', dimensionality=THREE_D, type=DEFORMABLE_BODY)
soil.BaseSolidExtrude(sketch=sketch, depth=SOIL_DEP)

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

model.HomogeneousSolidSection(name='SoilSec', material='SoilMat')
model.HomogeneousSolidSection(name='IndSec', material='SteelMat')
soil.SectionAssignment(region=regionToolset.Region(cells=soil.cells),
                       sectionName='SoilSec', offsetType=MIDDLE_SURFACE,
                       thicknessAssignment=FROM_SECTION)
indenter.SectionAssignment(region=regionToolset.Region(cells=indenter.cells),
                           sectionName='IndSec', offsetType=MIDDLE_SURFACE,
                           thicknessAssignment=FROM_SECTION)

# ALE only works on first-order reduced-integration solids (C3D8R).
elem = mesh.ElemType(elemCode=C3D8R, elemLibrary=STANDARD)
for part in (soil, indenter):
    part.setElementType(regions=(part.cells,), elemTypes=(elem,))
    part.setMeshControls(regions=part.cells, elemShape=HEX, technique=STRUCTURED)
    part.seedPart(size=SEED, deviationFactor=0.1, minSizeFactor=0.1)
    part.generateMesh()
print('soil elements: %d' % len(soil.elements))

asm = model.rootAssembly
asm.DatumCsysByDefault(CARTESIAN)
soil_inst = asm.Instance(name='SoilInst', part=soil, dependent=ON)
ind_inst = asm.Instance(name='IndInst', part=indenter, dependent=ON)
asm.translate(instanceList=('SoilInst',), vector=(0.0, 0.0, -SOIL_DEP))
asm.translate(instanceList=('IndInst',), vector=(0.0, 0.0, 1.0e-6))

rp = asm.ReferencePoint(point=(0.0, 0.0, IND_THICK / 2.0))
rp_region = regionToolset.Region(
    referencePoints=(asm.referencePoints[rp.id],))
asm.Set(name='IndRP', referencePoints=(asm.referencePoints[rp.id],))
model.RigidBody(name='IndRigid', refPointRegion=rp_region,
                bodyRegion=regionToolset.Region(cells=ind_inst.cells),
                refPointAtCOM=ON)

# *Static, geometrically nonlinear. Automatic incrementation. No
# stabilisation: that is fictitious viscous damping.
model.StaticStep(
    name='Push', previous='Initial', nlgeom=ON, timePeriod=1.0,
    initialInc=0.01, minInc=1.0e-8, maxInc=0.5, maxNumInc=500)
model.TabularAmplitude(name='Ramp', timeSpan=STEP,
                       data=((0.0, 0.0), (1.0, 1.0)))
model.HistoryOutputRequest(
    name='Energies', createStepName='Push',
    variables=('ALLIE', 'ALLWK', 'ETOTAL'))
model.HistoryOutputRequest(
    name='RP', createStepName='Push', region=asm.sets['IndRP'],
    variables=('U1', 'U2', 'U3', 'RF1', 'RF2', 'RF3'))

zc = -SOIL_DEP / 2.0
for name, point, dof in (
        ('XMIN', (-SOIL_LEN / 2.0, 0.0, zc), 1),
        ('XMAX', (SOIL_LEN / 2.0, 0.0, zc), 1),
        ('YMIN', (0.0, -SOIL_WID / 2.0, zc), 2),
        ('YMAX', (0.0, SOIL_WID / 2.0, zc), 2)):
    faces = soil_inst.faces.findAt((point,))
    if len(faces) == 0:
        raise RuntimeError('missed soil face %s at %r' % (name, point))
    kwargs = {'name': 'Roller-' + name, 'createStepName': 'Initial',
              'region': regionToolset.Region(faces=faces),
              'distributionType': UNIFORM}
    kwargs['u%d' % dof] = 0.0
    model.DisplacementBC(**kwargs)
base = soil_inst.faces.findAt(((0.0, 0.0, -SOIL_DEP),))
if len(base) == 0:
    raise RuntimeError('missed the soil base')
model.EncastreBC(name='Base', createStepName='Initial',
                 region=regionToolset.Region(faces=base))

model.DisplacementBC(
    name='Push', createStepName='Push', region=asm.sets['IndRP'],
    u1=0.0, u2=0.0, u3=-IND_DEPTH, ur1=0.0, ur2=0.0, ur3=0.0,
    amplitude='Ramp', distributionType=UNIFORM)

prop = model.ContactProperty('Interface')
prop.NormalBehavior(pressureOverclosure=HARD, allowSeparation=ON,
                    constraintEnforcementMethod=DEFAULT)
prop.TangentialBehavior(
    formulation=PENALTY, directionality=ISOTROPIC, table=((FRICTION,),),
    maximumElasticSlip=FRACTION, fraction=0.005)
contact = model.ContactStd(name='GeneralContact', createStepName='Initial')
contact.includedPairs.setValuesInStep(stepName='Initial', useAllstar=True)
contact.contactPropertyAssignments.appendInStep(
    stepName='Initial', assignments=((GLOBAL, SELF, 'Interface'),))


# --- ALE (the only extra block versus implicit.py) ------------------
# Restrict the domain to a box around the indenter. An empty set is silent:
# Abaqus will not warn, and ALE will do nothing.

half = 3.0 * IND_HALF
zmin = max(-1.3 * IND_DEPTH, -SOIL_DEP + 2.0 * SEED)
ale_elems = soil_inst.elements.getByBoundingBox(
    xMin=-half, xMax=half, yMin=-SOIL_WID, yMax=SOIL_WID,
    zMin=zmin, zMax=0.0)
if len(ale_elems) == 0:
    raise RuntimeError('ALE box is empty. ALE would run and do nothing.')
asm.Set(name='ALE_Box', elements=ale_elems)
print('ALE elements: %d' % len(asm.sets['ALE_Box'].elements))

model.AdaptiveMeshControl(name='ALE_BC', smoothingPriority=UNIFORM)
# Standard has no initial mesh sweeps. Do not pass initialMeshSweeps.
model.steps['Push'].AdaptiveMeshDomain(
    region=asm.sets['ALE_Box'], controls='ALE_BC',
    frequency=10, meshSweeps=1)


# --- write, check, maybe submit -------------------------------------------

def _inject_hourglass(inp_path):
    """Standard ALE requires enhanced hourglass on C3D8R. CAE cannot write
    *Section Controls. *Diagnostics, adaptive mesh= is Explicit-only."""
    lines = open(inp_path).readlines()
    out, inserted = [], False
    for line in lines:
        out.append(line)
        if (not inserted) and line.upper().startswith('*PREPRINT'):
            out.append('*Section Controls, name=SoilSC, hourglass=ENHANCED\n')
            inserted = True
    text = ''.join(out)
    old = None
    for line in text.splitlines(True):
        u = line.upper()
        if u.startswith('*SOLID SECTION') and 'SOILMAT' in u and 'CONTROLS=' not in u:
            old = line
            break
    if old is None:
        raise RuntimeError('no *Solid Section for SoilMat to attach hourglass')
    text = text.replace(old, old.rstrip('\r\n') + ', controls=SoilSC\n', 1)
    fh = open(inp_path, 'w')
    fh.write(text)
    fh.close()

job = mdb.Job(name=JOB_NAME, model='Model-1', type=ANALYSIS,
              numCpus=1, multiprocessingMode=DEFAULT,
              memory=90, memoryUnits=PERCENTAGE)
job.writeInput()
inp = os.path.join(workdir, JOB_NAME + '.inp')
print('wrote %s' % inp)

_inject_hourglass(inp)

submit = os.environ.get('FLD_SUBMIT', '1').strip().lower() not in (
    '0', 'false', 'no', 'off')
if submit:
    job.submit(consistencyChecking=OFF)
    job.waitForCompletion()
    print('job finished. look at the .sta for the abort message.')
else:
    print('FLD_SUBMIT=0: deck written, not submitted.')
