"""The benchmark model shared by examples 01-05: a rigid strip indenter pushed
into a soil block.

One model, several formulations. Examples 01 to 05 differ only in what they do
*to* this model -- nothing else changes -- so any difference you see in the
results is caused by the formulation and not by a quietly different mesh, a
different friction coefficient or a different loading rate. That discipline is
the whole point of a benchmark, and it is worth more than any individual result
in this repository.

Geometry and conventions
------------------------
::

        z = 0  (soil surface)
            +-------------------+---+-------------------+   <- indenter, 2*a wide
            |                                           |
            |               soil block                  |   x in [-L/2, +L/2]
            |                                           |   y in [-W/2, +W/2]
            +-------------------------------------------+   z in [-D, 0]
        z = -D   (encastre)

* **z is depth, negative downwards, and the soil surface is z = 0.** Penetration
  is in -z. Every box, set and boundary condition here uses that convention, and
  so does the caisson example.
* Rollers on the four vertical faces, encastre on the base.
* The indenter is a **rigid body** driven by a prescribed velocity on an
  assembly-level reference point. A rigid indenter is both physically sensible
  (steel against sand) and numerically sensible: a stiff deformable body would
  drive the stable time increment through the floor for no benefit.
* The indenter spans the full model width in y, so the problem is plane strain
  in all but name. That keeps the element count low enough to run these examples
  on a laptop while still exercising the full 3D ALE and CEL machinery.

Default material is elastic. That is deliberate: when an ALE or CEL study
misbehaves, the first thing to do is rerun it elastic, and every surprise
documented in `docs/` was first reproduced on an elastic block.
"""

from __future__ import print_function

from abaqus import mdb
from abaqusConstants import (THREE_D, DEFORMABLE_BODY, ON, OFF, C3D8R, HEX,
                             STRUCTURED, EXPLICIT, STANDARD, MIDDLE_SURFACE,
                             FROM_SECTION, UNIFORM, CARTESIAN, STEP,
                             DISSIPATED_ENERGY_FRACTION)
import mesh
import regionToolset

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), 'lib'))

from fldlib import materials, contact, steps, report


# ---------------------------------------------------------------------------
# Parameter declaration -- shared by every example that uses this model
# ---------------------------------------------------------------------------

def declare(P):
    """Add the benchmark parameters to a `fldlib.config.Params`."""
    P.add('soil_len', 0.30, 'm', 'soil block length, x')
    P.add('soil_wid', 0.20, 'm', 'soil block width, y')
    P.add('soil_dep', 0.20, 'm', 'soil block depth, z')
    P.add('seed', 0.010, 'm', 'global element seed (0.01 -> 12000 elements)')

    P.add('ind_half', 0.0225, 'm', 'indenter half-width in x')
    P.add('ind_thick', 0.010, 'm', 'indenter thickness in z')
    P.add('ind_vel', 1.0, 'm/s', 'prescribed penetration velocity')
    P.add('ind_depth', 0.150, 'm', 'target penetration depth')
    P.add('ramp_frac', 0.05, '-', 'SMOOTH STEP ramp as a fraction of the step')

    P.add('soil_model', 'elastic', '-', 'elastic | mc | dp | umat',
          choices=('elastic', 'mc', 'dp', 'umat'))
    P.add('soil_e', 20.0e6, 'Pa', 'Young modulus')
    P.add('soil_nu', 0.30, '-', 'Poisson ratio')
    P.add('soil_rho', 1651.6, 'kg/m3', 'soil density')
    P.add('soil_phi', 32.0, 'deg', 'friction angle (mc / dp)')
    P.add('soil_psi', 2.0, 'deg', 'dilation angle (mc / dp)')
    P.add('soil_coh', 1.0e3, 'Pa', 'cohesion (mc) -- must be > 0 in Abaqus')

    P.add('umat_source', '', '-', 'path to the UMAT/VUMAT source (soil_model=umat)')
    P.add('umat_constants', '', '-', 'path to the material constants file')
    P.add('umat_nsdv', 40, '-', 'number of state variables (*Depvar)')

    P.add('friction', 0.5, '-', 'interface friction coefficient')
    P.add('n_cpus', 1, '-', 'CPUs (1 keeps ALE single-domain; see docs)')
    P.add('n_domains', 0, '-', '0 -> same as n_cpus')
    return P


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build(P, model_name='Indenter', solver='explicit'):
    """Build the benchmark model and return a dict of handles.

    `solver` is 'explicit' or 'implicit'. The implicit path exists so that
    example 01 can show the familiar Abaqus/Standard analysis failing first --
    that failure is the motivation for everything that follows. It uses the same
    mesh, the same material and the same contact, and differs only in the
    element library (STANDARD), the step type (*Static with automatic
    stabilisation) and how the motion is prescribed (displacement, not
    velocity).

    Returns::

        {'model', 'assembly', 'soil_part', 'soil_inst', 'ind_inst',
         'rp_set', 'step_name', 'n_soil_elements', 'time_period'}
    """
    if model_name in mdb.models:
        del mdb.models[model_name]
    model = mdb.Model(name=model_name)

    L, W, D = P.soil_len, P.soil_wid, P.soil_dep

    # -- soil part ---------------------------------------------------------
    sk = model.ConstrainedSketch(name='soil_plan', sheetSize=10.0 * L)
    sk.rectangle(point1=(-L / 2.0, -W / 2.0), point2=(L / 2.0, W / 2.0))
    soil = model.Part(name='Soil', dimensionality=THREE_D,
                      type=DEFORMABLE_BODY)
    soil.BaseSolidExtrude(sketch=sk, depth=D)       # part occupies z in [0, D]

    # -- indenter part -----------------------------------------------------
    a, t = P.ind_half, P.ind_thick
    ski = model.ConstrainedSketch(name='ind_plan', sheetSize=10.0 * L)
    ski.rectangle(point1=(-a, -W / 2.0), point2=(a, W / 2.0))
    ind = model.Part(name='Indenter', dimensionality=THREE_D,
                     type=DEFORMABLE_BODY)
    ind.BaseSolidExtrude(sketch=ski, depth=t)

    # -- materials and sections -------------------------------------------
    _soil_material(model, P)
    materials.steel(model, name='SteelMat')

    model.HomogeneousSolidSection(name='SoilSec', material='SoilMat',
                                  thickness=None)
    model.HomogeneousSolidSection(name='IndSec', material='SteelMat',
                                  thickness=None)
    soil.SectionAssignment(region=regionToolset.Region(cells=soil.cells),
                           sectionName='SoilSec',
                           offsetType=MIDDLE_SURFACE,
                           thicknessAssignment=FROM_SECTION)
    ind.SectionAssignment(region=regionToolset.Region(cells=ind.cells),
                          sectionName='IndSec',
                          offsetType=MIDDLE_SURFACE,
                          thicknessAssignment=FROM_SECTION)

    # -- mesh --------------------------------------------------------------
    library = EXPLICIT if solver == 'explicit' else STANDARD
    # Hourglass control is left at the element-type default here. Example 03
    # changes it through *Section Controls instead: that is how you change it
    # for an existing mesh, and it is the same keyword that carries distortion
    # control.
    elem = mesh.ElemType(elemCode=C3D8R, elemLibrary=library)
    soil.setElementType(regions=(soil.cells,), elemTypes=(elem,))
    soil.setMeshControls(regions=soil.cells, elemShape=HEX,
                         technique=STRUCTURED)
    soil.seedPart(size=P.seed, deviationFactor=0.1, minSizeFactor=0.1)
    soil.generateMesh()

    ind.setElementType(regions=(ind.cells,), elemTypes=(elem,))
    ind.setMeshControls(regions=ind.cells, elemShape=HEX,
                        technique=STRUCTURED)
    ind.seedPart(size=P.seed, deviationFactor=0.1, minSizeFactor=0.1)
    ind.generateMesh()

    n_soil = len(soil.elements)
    if n_soil == 0:
        raise RuntimeError('the soil mesh is empty -- generateMesh() produced '
                           'nothing. Check the seed against the geometry.')

    # -- assembly ----------------------------------------------------------
    asm = model.rootAssembly
    asm.DatumCsysByDefault(CARTESIAN)
    soil_inst = asm.Instance(name='SoilInst', part=soil, dependent=ON)
    ind_inst = asm.Instance(name='IndInst', part=ind, dependent=ON)

    # move soil so its top surface sits at z = 0, and rest the indenter on it
    asm.translate(instanceList=('SoilInst',), vector=(0.0, 0.0, -D))
    # a small initial gap avoids an over-closure spike on increment 1
    asm.translate(instanceList=('IndInst',), vector=(0.0, 0.0, 1.0e-6))

    # -- rigid body for the indenter --------------------------------------
    rp = asm.ReferencePoint(point=(0.0, 0.0, t / 2.0))
    rp_region = regionToolset.Region(
        referencePoints=(asm.referencePoints[rp.id],))
    asm.Set(name='IndRP', referencePoints=(asm.referencePoints[rp.id],))
    model.RigidBody(name='IndRigid', refPointRegion=rp_region,
                    bodyRegion=regionToolset.Region(cells=ind_inst.cells),
                    refPointAtCOM=ON)

    # -- step --------------------------------------------------------------
    step_name = 'Push'
    if solver == 'explicit':
        time_period = P.ind_depth / float(P.ind_vel)
        steps.explicit_step(model, step_name, 'Initial', time_period,
                            nlgeom=True)
        steps.smooth_ramp(model, 'Ramp', P.ramp_frac, time_period)
    else:
        # Automatic stabilisation is switched ON deliberately. Without it this
        # analysis stops converging almost immediately once the soil starts to
        # fail, and the point of example 01 is to see WHERE it stops rather than
        # to watch it stop at increment 3. Note that stabilisation is a fictitious
        # viscous force: always check ALLSD against ALLIE afterwards.
        time_period = 1.0
        model.StaticStep(name=step_name, previous='Initial', nlgeom=ON,
                         timePeriod=time_period,
                         initialInc=0.005, minInc=1.0e-8, maxInc=0.05,
                         maxNumInc=1000,
                         stabilizationMethod=DISSIPATED_ENERGY_FRACTION,
                         stabilizationMagnitude=2.0e-4,
                         adaptiveDampingRatio=0.05,
                         continueDampingFactors=ON)
        model.TabularAmplitude(name='Ramp', timeSpan=STEP,
                               data=((0.0, 0.0), (time_period, 1.0)))
    steps.energy_output(model, step_name, interval=200)
    model.HistoryOutputRequest(
        name='RP', createStepName=step_name,
        region=asm.sets['IndRP'],
        variables=('U1', 'U2', 'U3', 'RF1', 'RF2', 'RF3'),
        numIntervals=500)
    model.fieldOutputRequests['F-Output-1'].setValues(
        variables=('S', 'PE', 'PEEQ', 'LE', 'U', 'V', 'A', 'RF', 'CSTRESS',
                   'EVF', 'SDV', 'STATUS'),
        numIntervals=20)

    # -- boundary conditions ----------------------------------------------
    _soil_bcs(model, asm, soil_inst, P)
    if solver == 'explicit':
        # A prescribed VELOCITY is the natural drive for an explicit run: it
        # gives a constant penetration rate, which is what makes the resistance
        # curve interpretable, and the SMOOTH STEP ramp keeps the first
        # increment from sending a stress wave through the whole model.
        model.VelocityBC(name='Push', createStepName=step_name,
                         region=asm.sets['IndRP'],
                         v1=0.0, v2=0.0, v3=-P.ind_vel,
                         vr1=0.0, vr2=0.0, vr3=0.0,
                         amplitude='Ramp', distributionType=UNIFORM)
    else:
        model.DisplacementBC(name='Push', createStepName=step_name,
                             region=asm.sets['IndRP'],
                             u1=0.0, u2=0.0, u3=-P.ind_depth,
                             ur1=0.0, ur2=0.0, ur3=0.0,
                             amplitude='Ramp', distributionType=UNIFORM)

    # -- contact -----------------------------------------------------------
    contact.friction_property(model, 'Interface', mu=P.friction, hard=True)
    if solver == 'explicit':
        contact.general_contact(model, step_name, 'Interface')
    else:
        contact.general_contact_std(model, step_name, 'Interface')

    return {
        'model': model,
        'assembly': asm,
        'soil_part': soil,
        'ind_part': ind,
        'soil_inst': soil_inst,
        'ind_inst': ind_inst,
        'rp_set': asm.sets['IndRP'],
        'step_name': step_name,
        'n_soil_elements': n_soil,
        'time_period': time_period,
        'solver': solver,
    }


# ---------------------------------------------------------------------------
# Pieces
# ---------------------------------------------------------------------------

def _soil_material(model, P):
    kw = dict(name='SoilMat', youngs=P.soil_e, poisson=P.soil_nu,
              density=P.soil_rho)
    if P.soil_model == 'elastic':
        return materials.elastic_soil(model, **kw)
    if P.soil_model == 'mc':
        return materials.mohr_coulomb_soil(
            model, friction=P.soil_phi, dilation=P.soil_psi,
            cohesion=P.soil_coh, **kw)
    if P.soil_model == 'dp':
        beta, psi_dp = materials.dp_from_mc(P.soil_phi, P.soil_psi)
        return materials.drucker_prager_soil(
            model, friction=beta, dilation=psi_dp, **kw)
    if P.soil_model == 'umat':
        if not P.umat_constants:
            raise ValueError('soil_model=umat needs FLD_UMAT_CONSTANTS '
                             '(path to the material constants file)')
        constants = materials.read_constants(P.umat_constants)
        print('  UMAT constants: %d values from %s'
              % (len(constants), P.umat_constants))
        return materials.user_material(model, 'SoilMat', constants,
                                       P.umat_nsdv, P.soil_rho)
    raise ValueError('unknown soil_model %r' % P.soil_model)


def _soil_bcs(model, asm, soil_inst, P):
    """Rollers on the four vertical faces, encastre on the base.

    Faces are picked with `findAt` on face-centre points in **assembly**
    coordinates (the soil has already been translated so its top is at z = 0).
    `findAt` is the fragile part of every Abaqus script: it silently returns an
    empty sequence when the point misses, and the boundary condition is then
    applied to nothing without any error. So each pick is checked.
    """
    L, W, D = P.soil_len, P.soil_wid, P.soil_dep
    zc = -D / 2.0

    picks = {
        'XMIN': ((-L / 2.0, 0.0, zc), 1),
        'XMAX': ((L / 2.0, 0.0, zc), 1),
        'YMIN': ((0.0, -W / 2.0, zc), 2),
        'YMAX': ((0.0, W / 2.0, zc), 2),
    }
    for name, (point, dof) in picks.items():
        faces = soil_inst.faces.findAt((point,))
        if len(faces) == 0:
            raise RuntimeError(
                'findAt missed the %s soil face at %r. Nothing would have been '
                'restrained and the model would run with a free face. Check '
                'the geometry and the translate() call.' % (name, point))
        region = regionToolset.Region(faces=faces)
        kwargs = {'name': 'Roller-' + name, 'createStepName': 'Initial',
                  'region': region, 'distributionType': UNIFORM}
        kwargs['u%d' % dof] = 0.0
        model.DisplacementBC(**kwargs)

    base = soil_inst.faces.findAt(((0.0, 0.0, -D),))
    if len(base) == 0:
        raise RuntimeError('findAt missed the soil base face at (0, 0, %g)' % -D)
    model.EncastreBC(name='Base', createStepName='Initial',
                     region=regionToolset.Region(faces=base))
