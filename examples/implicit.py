"""Implicit Lagrangian strip indenter.

    abaqus cae noGUI=examples/implicit.py

Abaqus/Standard, *Static, displacement control. Expect it to stop
converging. That failure is the point of this script.

This file is complete. Read it top to bottom. The other scripts in
examples/ are the same model with the extra lines that each formulation
needs.
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

SEED = 0.010             # m, element size. Same on every formulation.
SOIL_LEN = 0.30          # m, block size in x
SOIL_WID = SEED          # one element through the strip (plane strain)
SOIL_DEP = 0.20          # m, block size in z

IND_HALF = 0.0225        # m, half-width of the strip
IND_THICK = 0.010        # m, thickness of the strip
IND_DEPTH = 0.150        # m, how far to push (it will not get this far)

SOIL_E = 20.0e6          # Pa
SOIL_NU = 0.30
SOIL_SY = 50.0e3         # Pa, von Mises, no hardening
SOIL_RHO = 1651.6        # kg/m3  (unused by *Static, kept so the files match)
FRICTION = 0.5

JOB_NAME = 'implicit'


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

# Soil block. Extruded in +z, then moved so the top surface sits at z = 0.
sketch = model.ConstrainedSketch(name='soil', sheetSize=10.0 * SOIL_LEN)
sketch.rectangle(point1=(-SOIL_LEN / 2.0, -SOIL_WID / 2.0),
                 point2=(SOIL_LEN / 2.0, SOIL_WID / 2.0))
soil = model.Part(name='Soil', dimensionality=THREE_D, type=DEFORMABLE_BODY)
soil.BaseSolidExtrude(sketch=sketch, depth=SOIL_DEP)

# Strip indenter.
sketch_i = model.ConstrainedSketch(name='indenter', sheetSize=10.0 * SOIL_LEN)
sketch_i.rectangle(point1=(-IND_HALF, -SOIL_WID / 2.0),
                   point2=(IND_HALF, SOIL_WID / 2.0))
indenter = model.Part(name='Indenter', dimensionality=THREE_D,
                      type=DEFORMABLE_BODY)
indenter.BaseSolidExtrude(sketch=sketch_i, depth=IND_THICK)

# von Mises soil. Density is written so this file matches the Explicit ones.
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

# First-order reduced-integration hex, Standard library.
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
    initialInc=0.01, minInc=1.0e-8, maxInc=0.5)
model.TabularAmplitude(name='Ramp', timeSpan=STEP,
                       data=((0.0, 0.0), (1.0, 1.0)))
model.HistoryOutputRequest(
    name='Energies', createStepName='Push',
    variables=('ALLIE', 'ALLWK', 'ETOTAL'))
model.HistoryOutputRequest(
    name='RP', createStepName='Push', region=asm.sets['IndRP'],
    variables=('U1', 'U2', 'U3', 'RF1', 'RF2', 'RF3'))

# Rollers on the four sides, encastre on the base.
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

# Displacement control: push the rigid body down by IND_DEPTH over the step.
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


# --- write, check, maybe submit -------------------------------------------

job = mdb.Job(name=JOB_NAME, model='Model-1', type=ANALYSIS,
              numCpus=1, multiprocessingMode=DEFAULT,
              memory=90, memoryUnits=PERCENTAGE)
job.writeInput()
inp = os.path.join(workdir, JOB_NAME + '.inp')
print('wrote %s' % inp)
print('open that file and check: *Static, nlgeom=YES, no *Adaptive Mesh')

submit = os.environ.get('FLD_SUBMIT', '1').strip().lower() not in (
    '0', 'false', 'no', 'off')
if submit:
    job.submit(consistencyChecking=OFF)
    job.waitForCompletion()
    print('job finished. look at the .sta for the abort message.')
else:
    print('FLD_SUBMIT=0: deck written, not submitted.')
