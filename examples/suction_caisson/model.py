"""Suction caisson installation, lab scale: jacked phase then suction-assisted
phase.

    abaqus cae noGUI=examples/suction_caisson/model.py

An introduction to the problem. A large penetration, a thin skirt that the
soil has to flow around, two phases with different driving mechanisms, and a
choice of formulation.

    FLD_METHOD=ale   quarter-symmetry Lagrangian soil with a two-region
                     adaptive mesh domain (default)
    FLD_METHOD=cel   quarter-symmetry Eulerian soil

Geometry (quarter model, lab scale)
-----------------------------------
::

           y
           ^            . - .                   caisson radius   R
           |        .         .                 skirt length     L
           |      .   +-----+   .               wall thickness   t
           |     .    |     |    .              lid at z = 0 initially
           +-----.----|-----|----.-----> x      soil: radius 5R, depth 4L
                 .    |  o  |    .
                  .   +-----+   .               o = axis
                    .         .
                        . - .

Symmetry planes at x = 0 and y = 0; only the quarter x >= 0, y >= 0 is modelled.
That is a factor of four in run time for free, and it is legitimate here because
the problem and the loading are both axisymmetric. It stops being legitimate the
moment you apply a lateral load or a moment, which is why this example installs
the caisson and stops.

The two phases
--------------
**Phase 1, jacked.** The caisson is pushed down at a constant rate to
`jack_depth`, as in a displacement-controlled laboratory installation.

**Phase 2, suction.** Water is pumped out of the caisson, so the pressure inside
drops by `delta_p` relative to ambient. That does two things in reality:

  (a) a net downward force on the lid of ``delta_p * pi * R^2``;
  (b) an upward seepage gradient through the soil plug, which loosens the plug,
      reduces the tip resistance at the skirt and reduces inner skirt friction.

**This model captures (a) and NOT (b).** Effect (b) requires a coupled
pore-fluid analysis (`*Soils, consolidation` in Standard, or a hydro-mechanically
coupled VUMAT in Explicit -- see `constitutive/` for one). Ignoring it means this
model *over-predicts* the suction required, because the real mechanism that makes
suction installation work is exactly the part that has been left out.

That limitation is stated here, in the log, and in the README, because a suction
caisson model that silently omits seepage is the single most common way to get a
plausible-looking and completely wrong installation curve.

Cases
-----
J    jacked only, to full depth                       -- the reference resistance
S    jacked to `jack_depth`, then suction to full depth
S2   as S with twice the suction                      -- shows the load path, not
                                                         a different resistance
"""

from __future__ import print_function

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_ROOT, 'lib'))
sys.path.insert(0, os.path.join(_ROOT, 'examples'))

from abaqus import mdb                                          # noqa: E402
from abaqusConstants import (THREE_D, DEFORMABLE_BODY, EULERIAN, ON, OFF,
                             C3D8R, EC3D8R, HEX, STRUCTURED, SWEEP, EXPLICIT,
                             MIDDLE_SURFACE, FROM_SECTION, UNIFORM, CARTESIAN,
                             XYPLANE, XZPLANE, YZPLANE, UNIFORM as UNI,
                             COUNTERCLOCKWISE)                  # noqa: E402
import mesh                                                     # noqa: E402
import regionToolset                                            # noqa: E402

from fldlib import (config, report, jobs, steps, materials, contact, ale, cel,
                    inpedit, subroutines)                       # noqa: E402
from common import runner                                       # noqa: E402
from postproc import energy                                     # noqa: E402


STUDY = 'suction_caisson'
CASES = ['J', 'S', 'S2']

CASE_DOC = {
    'J': 'jacked to full depth (reference)',
    'S': 'jacked to jack_depth, then suction-assisted',
    'S2': 'as S with twice the suction',
}


def make_params():
    P = config.Params(STUDY)

    # -- caisson (lab scale, matching the ALE box defaults in the source model)
    P.add('r_caisson', 0.100, 'm', 'caisson outer radius')
    P.add('l_skirt', 0.150, 'm', 'skirt length')
    P.add('t_wall', 0.002, 'm', 'skirt wall thickness')
    P.add('t_lid', 0.005, 'm', 'lid thickness')

    # -- soil domain
    P.add('r_soil_mult', 5.0, '-', 'soil radius / caisson radius')
    P.add('d_soil_mult', 4.0, '-', 'soil depth / skirt length')
    P.add('void_mult', 0.4, '-', 'void above the surface / skirt length (CEL)')

    # -- installation
    P.add('method', 'ale', '-', 'ale | cel', choices=('ale', 'cel'))
    P.add('jack_depth', 0.045, 'm', 'depth reached in the jacked phase')
    P.add('final_depth', 0.140, 'm', 'total target penetration')
    P.add('ind_vel', 0.20, 'm/s', 'penetration rate (scaled; check ALLKE)')
    P.add('delta_p', 20.0e3, 'Pa', 'suction (underpressure) in phase 2')
    P.add('ramp_frac', 0.05, '-', 'SMOOTH STEP ramp fraction')

    # -- mesh
    P.add('seed_fine', 0.0040, 'm', 'element size near the skirt')
    P.add('seed_coarse', 0.020, 'm', 'element size at the domain boundary')

    # -- soil
    P.add('soil_model', 'mc', '-', 'elastic | mc | dp | umat',
          choices=('elastic', 'mc', 'dp', 'umat'))
    P.add('soil_e', 20.0e6, 'Pa', 'Young modulus')
    P.add('soil_nu', 0.30, '-', 'Poisson ratio')
    P.add('soil_rho', 1651.6, 'kg/m3', 'submerged density')
    P.add('soil_phi', 32.0, 'deg', 'friction angle')
    P.add('soil_psi', 2.0, 'deg', 'dilation angle')
    P.add('soil_coh', 1.0e3, 'Pa', 'nominal cohesion')
    P.add('friction', 0.4, '-', 'steel-soil interface friction')

    P.add('umat_source', '', '-', 'VUMAT source (soil_model=umat)')
    P.add('umat_constants', '', '-', 'material constants file')
    P.add('umat_nsdv', 40, '-', 'number of state variables')
    P.add('sdv_init', '', '-', 'comma-separated initial SDV values')

    P.add('n_cpus', 4, '-', 'CPUs')
    P.add('n_domains', 0, '-', '0 -> same as n_cpus')
    return P.resolve()


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def build_caisson_part(model, P):
    """A quarter caisson: skirt plus lid, revolved 90 degrees.

    Modelled as a **rigid body**. A real installation analysis with a deformable
    skirt is a different study (skirt buckling, structural stresses) and needs a
    much finer shell mesh; making it rigid here keeps the stable time increment
    governed by the soil, which is where the physics is.
    """
    R, L, t, tl = P.r_caisson, P.l_skirt, P.t_wall, P.t_lid

    sk = model.ConstrainedSketch(name='caisson_section', sheetSize=10.0 * R)
    sk.ConstructionLine(point1=(0.0, -10.0 * R), point2=(0.0, 10.0 * R))
    sk.sketchOptions.setValues(constructionGeometry=ON)
    sk.assignCenterline(line=sk.geometry.findAt((0.0, 0.0)))

    # r-z section: skirt from z = -L to 0, lid from z = 0 to tl across the
    # full radius. Drawn in sketch coordinates (x -> r, y -> z).
    sk.Line(point1=(R - t, -L), point2=(R, -L))
    sk.Line(point1=(R, -L), point2=(R, tl))
    sk.Line(point1=(R, tl), point2=(0.0, tl))
    sk.Line(point1=(0.0, tl), point2=(0.0, 0.0))
    sk.Line(point1=(0.0, 0.0), point2=(R - t, 0.0))
    sk.Line(point1=(R - t, 0.0), point2=(R - t, -L))

    part = model.Part(name='Caisson', dimensionality=THREE_D,
                      type=DEFORMABLE_BODY)
    part.BaseSolidRevolve(sketch=sk, angle=90.0, flipRevolveDirection=OFF)
    return part


def build_soil_part(model, P, eulerian, seed):
    """The soil: a quarter cylinder.

    For ALE it is a deformable solid meshed with C3D8R. For CEL it is an
    Eulerian part that extends `void_mult * l_skirt` **above** the soil surface,
    because heave must have somewhere to go.
    """
    Rs = P.r_caisson * P.r_soil_mult
    Ds = P.l_skirt * P.d_soil_mult
    H = (P.void_mult * P.l_skirt) if eulerian else 0.0

    sk = model.ConstrainedSketch(name='soil_plan', sheetSize=10.0 * Rs)
    sk.ArcByCenterEnds(center=(0.0, 0.0), point1=(Rs, 0.0), point2=(0.0, Rs),
                       direction=COUNTERCLOCKWISE)
    sk.Line(point1=(0.0, 0.0), point2=(Rs, 0.0))
    sk.Line(point1=(0.0, 0.0), point2=(0.0, Rs))

    part = model.Part(name='Soil', dimensionality=THREE_D,
                      type=(EULERIAN if eulerian else DEFORMABLE_BODY))
    part.BaseSolidExtrude(sketch=sk, depth=Ds + H)   # part z in [0, Ds+H]

    # Partition at the soil surface (CEL) so the filled region is exact.
    if eulerian and H > 0.0:
        datum = part.DatumPlaneByPrincipalPlane(principalPlane=XYPLANE,
                                                offset=Ds)
        part.PartitionCellByDatumPlane(datumPlane=part.datums[datum.id],
                                       cells=part.cells)
    return part, Rs, Ds, H


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build(P, model_name, case):
    eulerian = (P.method == 'cel')
    if model_name in mdb.models:
        del mdb.models[model_name]
    model = mdb.Model(name=model_name)

    caisson = build_caisson_part(model, P)
    soil, Rs, Ds, H = build_soil_part(model, P, eulerian, P.seed_fine)

    # -- materials ---------------------------------------------------------
    _soil_material(model, P)
    materials.steel(model, name='SteelMat')

    if eulerian:
        _section, evf_key = cel.eulerian_section(model, 'SoilSec', 'SoilMat')
        soil.SectionAssignment(region=regionToolset.Region(cells=soil.cells),
                               sectionName='SoilSec')
    else:
        evf_key = None
        model.HomogeneousSolidSection(name='SoilSec', material='SoilMat',
                                      thickness=None)
        soil.SectionAssignment(region=regionToolset.Region(cells=soil.cells),
                               sectionName='SoilSec',
                               offsetType=MIDDLE_SURFACE,
                               thicknessAssignment=FROM_SECTION)

    model.HomogeneousSolidSection(name='CaissonSec', material='SteelMat',
                                  thickness=None)
    caisson.SectionAssignment(
        region=regionToolset.Region(cells=caisson.cells),
        sectionName='CaissonSec', offsetType=MIDDLE_SURFACE,
        thicknessAssignment=FROM_SECTION)

    # -- mesh --------------------------------------------------------------
    if eulerian:
        cel.set_eulerian_element_type(soil)
    else:
        soil.setElementType(
            regions=(soil.cells,),
            elemTypes=(mesh.ElemType(elemCode=C3D8R, elemLibrary=EXPLICIT),))
        soil.setMeshControls(regions=soil.cells, elemShape=HEX,
                             technique=SWEEP)
    soil.seedPart(size=P.seed_coarse, deviationFactor=0.1, minSizeFactor=0.1)
    _refine_near_skirt(soil, P, Rs, Ds, H)
    soil.generateMesh()

    caisson.setElementType(
        regions=(caisson.cells,),
        elemTypes=(mesh.ElemType(elemCode=C3D8R, elemLibrary=EXPLICIT),))
    caisson.setMeshControls(regions=caisson.cells, elemShape=HEX,
                            technique=SWEEP)
    caisson.seedPart(size=P.t_wall * 2.0, deviationFactor=0.1,
                     minSizeFactor=0.1)
    caisson.generateMesh()

    n_soil = len(soil.elements)
    if n_soil == 0:
        raise RuntimeError('the soil mesh is empty')

    # -- assembly ----------------------------------------------------------
    asm = model.rootAssembly
    asm.DatumCsysByDefault(CARTESIAN)
    soil_inst = asm.Instance(name='SoilInst', part=soil, dependent=ON)
    cai_inst = asm.Instance(name='CaissonInst', part=caisson, dependent=ON)
    asm.translate(instanceList=('SoilInst',), vector=(0.0, 0.0, -Ds))
    asm.translate(instanceList=('CaissonInst',), vector=(0.0, 0.0, 1.0e-6))
    if not eulerian:
        asm.Set(name='SoilAll', elements=soil_inst.elements)

    # -- rigid caisson -----------------------------------------------------
    rp = asm.ReferencePoint(point=(0.0, 0.0, P.t_lid / 2.0))
    rp_region = regionToolset.Region(
        referencePoints=(asm.referencePoints[rp.id],))
    asm.Set(name='CaissonRP', referencePoints=(asm.referencePoints[rp.id],))
    model.RigidBody(name='CaissonRigid', refPointRegion=rp_region,
                    bodyRegion=regionToolset.Region(cells=cai_inst.cells),
                    refPointAtCOM=ON)

    # -- Eulerian initial volume fraction ----------------------------------
    if eulerian:
        filled = soil_inst.cells.getByBoundingBox(zMin=-Ds - 1e-6,
                                                  zMax=0.0 + 1e-6)
        if len(filled) == 0:
            raise RuntimeError('no Eulerian cells below z = 0')
        cel.assign_material(model, asm, soil_inst,
                            asm.Set(name='SoilFilled', cells=filled))
        cel.check_void_fraction(asm, soil_inst, 'SoilFilled')

    # -- steps -------------------------------------------------------------
    jack_depth = P.final_depth if case == 'J' else P.jack_depth
    t_jack = jack_depth / float(P.ind_vel)
    steps.explicit_step(model, 'Jack', 'Initial', t_jack, nlgeom=True)
    steps.smooth_ramp(model, 'Ramp', P.ramp_frac, t_jack)
    steps.energy_output(model, 'Jack', interval=200)

    t_suction = 0.0
    if case != 'J':
        t_suction = (P.final_depth - P.jack_depth) / float(P.ind_vel)
        steps.explicit_step(model, 'Suction', 'Jack', t_suction, nlgeom=True)
        steps.smooth_ramp(model, 'SuctionRamp', P.ramp_frac, t_suction)

    for step_name in (['Jack'] + (['Suction'] if case != 'J' else [])):
        model.HistoryOutputRequest(
            name='RP_' + step_name, createStepName=step_name,
            region=asm.sets['CaissonRP'],
            variables=('U1', 'U2', 'U3', 'RF1', 'RF2', 'RF3'),
            numIntervals=500)
    model.fieldOutputRequests['F-Output-1'].setValues(
        variables=('S', 'PE', 'PEEQ', 'LE', 'U', 'V', 'A', 'RF', 'CSTRESS',
                   'EVF', 'SDV', 'STATUS'),
        numIntervals=25)

    # -- boundary conditions ----------------------------------------------
    _soil_bcs(model, asm, soil_inst, Rs, Ds, H)

    # Quarter symmetry on the caisson reference point: it may translate in z
    # and nothing else.
    model.DisplacementBC(name='CaissonGuide', createStepName='Initial',
                         region=asm.sets['CaissonRP'],
                         u1=0.0, u2=0.0, ur1=0.0, ur2=0.0, ur3=0.0,
                         distributionType=UNIFORM)

    model.VelocityBC(name='Jacking', createStepName='Jack',
                     region=asm.sets['CaissonRP'], v3=-P.ind_vel,
                     amplitude='Ramp', distributionType=UNIFORM)

    suction = 0.0
    if case != 'J':
        suction = P.delta_p * (2.0 if case == 'S2' else 1.0)
        _apply_suction(model, asm, cai_inst, P, suction)

    # -- contact -----------------------------------------------------------
    contact.friction_property(model, 'Interface', mu=P.friction, hard=True)
    contact.general_contact(model, 'Jack', 'Interface')

    # -- ALE ---------------------------------------------------------------
    ale_elements = 0
    if not eulerian:
        ale_elements = _add_ale(model, asm, soil_inst, P, n_soil,
                                ['Jack'] + (['Suction'] if case != 'J' else []))

    return {'model': model, 'assembly': asm, 'soil_inst': soil_inst,
            'n_soil': n_soil, 'ale_elements': ale_elements,
            'suction': suction, 'eulerian': eulerian,
            't_jack': t_jack, 't_suction': t_suction, 'jack_depth': jack_depth}


def _apply_suction(model, asm, cai_inst, P, delta_p):
    """Phase 2 loading: the net downward force from the underpressure.

    Applied as a concentrated force on the caisson reference point rather than
    as a distributed pressure, because the caisson is a rigid body and the
    resultant is what it responds to. The magnitude is the underpressure times
    the plan area of the **quarter** model:

        F = delta_p * (pi * R^2) / 4

    The caisson is released from velocity control in this step and allowed to
    penetrate under the applied force. That is what makes
    this phase physically different from jacking: the penetration rate is an
    *outcome*, not an input, and it is the quantity a designer actually wants.

    Remember what is missing: the seepage gradient that loosens the plug and
    cuts the tip resistance is not modelled. This will over-predict the suction
    needed.
    """
    R = P.r_caisson
    area_quarter = math.pi * R * R / 4.0
    force = delta_p * area_quarter

    # Release the prescribed velocity so the caisson responds to the force.
    model.boundaryConditions['Jacking'].deactivate('Suction')
    model.ConcentratedForce(name='SuctionForce', createStepName='Suction',
                            region=asm.sets['CaissonRP'], cf3=-force,
                            amplitude='SuctionRamp', distributionType=UNIFORM)
    print('  suction %.1f kPa -> %.2f N on the quarter model '
          '(plan area %.5f m2)' % (delta_p / 1e3, force, area_quarter))
    return force


def _add_ale(model, asm, soil_inst, P, n_soil, step_names):
    """Two adaptive regions: one around the skirt tip, one inside the plug.

    Two regions rather than one because the two zones deform for different
    reasons -- the tip shears a narrow band, the plug heaves as a body -- and
    because two well-separated regions parallelise far better than one large
    one (see docs/03-ale-multi-region-parallel.md).

    They must not touch: regions sharing a face are treated as one region.
    """
    from abaqusConstants import UNIFORM as UNIFORM_SMOOTH
    ale.make_controls(model, 'ALE_BC', smoothing=UNIFORM_SMOOTH)

    R, L, t = P.r_caisson, P.l_skirt, P.t_wall
    depth = P.final_depth
    gap = 2.0 * P.seed_fine
    z_min = -(depth + 6.0 * P.seed_fine)

    # Region 1 is a true cylindrical annulus around the skirt. The previous
    # rectangular selector contained the entire plug selector, so the overlap
    # guard below correctly rejected every default ALE build.
    tip_r_min = R - t - gap
    tip_r_max = R + 4.0 * t
    plug_r_max = tip_r_min - gap
    if plug_r_max <= 0.0:
        raise ValueError('ALE gap is too large for the caisson radius')

    n_tip, bbox_tip = ale.cylindrical_element_set(
        asm, soil_inst, 'ALE_Tip', tip_r_min, tip_r_max, z_min, 0.0)
    ale.describe_box_set('ALE_Tip', n_tip, bbox_tip, total=n_soil)
    n_plug, bbox_plug = ale.cylindrical_element_set(
        asm, soil_inst, 'ALE_Plug', 0.0, plug_r_max, z_min, 0.0)
    ale.describe_box_set('ALE_Plug', n_plug, bbox_plug, total=n_soil)

    # Overlapping domains are a real error: an element in two domains is
    # smoothed twice per adaptive increment with no warning. Keep the explicit
    # check as a regression guard even though the radial selectors are disjoint.
    tip_labels = set(e.label for e in asm.sets['ALE_Tip'].elements)
    plug_labels = set(e.label for e in asm.sets['ALE_Plug'].elements)
    overlap = tip_labels & plug_labels
    if overlap:
        raise RuntimeError(
            '%d element(s) are in BOTH adaptive regions. Overlapping adaptive '
            'mesh domains are smoothed twice per increment and Abaqus does not '
            'warn about it. Increase the gap between the boxes, or build the '
            'tip region as an annulus.' % len(overlap))

    for step_name in step_names[:1]:
        ale.add_domain(model, step_name, asm.sets['ALE_Tip'], 'ALE_BC',
                       initial_mesh_sweeps=5)
    return n_tip + n_plug


def _soil_material(model, P):
    kw = dict(name='SoilMat', youngs=P.soil_e, poisson=P.soil_nu,
              density=P.soil_rho)
    if P.soil_model == 'elastic':
        return materials.elastic_soil(model, **kw)
    if P.soil_model == 'mc':
        return materials.mohr_coulomb_soil(model, friction=P.soil_phi,
                                           dilation=P.soil_psi,
                                           cohesion=P.soil_coh, **kw)
    if P.soil_model == 'dp':
        beta, psi = materials.dp_from_mc(P.soil_phi, P.soil_psi)
        return materials.drucker_prager_soil(model, friction=beta,
                                             dilation=psi, **kw)
    if P.soil_model == 'umat':
        if not P.umat_constants:
            raise ValueError('soil_model=umat needs FLD_UMAT_CONSTANTS')
        constants = materials.read_constants(P.umat_constants)
        return materials.user_material(model, 'SoilMat', constants,
                                       P.umat_nsdv, P.soil_rho)
    raise ValueError(P.soil_model)


def _refine_near_skirt(part, P, Rs, Ds, H):
    """Bias the seed towards the skirt.

    A uniform mesh fine enough at the skirt would be ruinously expensive over a
    domain five radii wide. Edge bias is the cheapest way to get resolution
    where the gradients are. Kept simple here on purpose -- a production model
    would partition the domain into a fine inner cylinder and a coarse outer
    annulus, which is what the source model in `Old scripts/caissonInstall.py`
    does.
    """
    from abaqusConstants import FINER

    try:
        near = part.edges.getByBoundingCylinder(
            center1=(0.0, 0.0, -1e-3), center2=(0.0, 0.0, Ds + H + 1e-3),
            radius=P.r_caisson * 1.5)
        if len(near) == 0:
            raise RuntimeError('no edges found within 1.5 R of the axis')
        part.seedEdgeBySize(edges=near, size=P.seed_fine,
                            deviationFactor=0.1, constraint=FINER)
        print('  refined %d edge(s) near the skirt to %.4g m'
              % (len(near), P.seed_fine))
    except Exception as exc:                  # noqa: BLE001
        print('  *** could not apply local refinement (%s). Falling back to a '
              'uniform coarse seed: the skirt will be under-resolved. Treat '
              'this run as a mesh-convergence exercise, not a result. ***'
              % exc)


def _soil_bcs(model, asm, inst, Rs, Ds, H):
    """Symmetry on x = 0 and y = 0, roller on the outer curved face, encastre base."""
    model.XsymmBC(name='SymX', createStepName='Initial',
                  region=regionToolset.Region(
                      faces=inst.faces.getByBoundingBox(
                          xMin=-1e-6, xMax=1e-6)))
    model.YsymmBC(name='SymY', createStepName='Initial',
                  region=regionToolset.Region(
                      faces=inst.faces.getByBoundingBox(
                          yMin=-1e-6, yMax=1e-6)))

    curved = inst.faces.getByBoundingCylinder(
        center1=(0.0, 0.0, -Ds - 1e-3), center2=(0.0, 0.0, H + 1e-3),
        radius=Rs * 1.001)
    outer = [f for f in curved
             if abs((f.pointOn[0][0] ** 2 + f.pointOn[0][1] ** 2) ** 0.5 - Rs)
             < 1e-4]
    if outer:
        arr = inst.faces[0:0]
        for f in outer:
            arr = arr + inst.faces[f.index:f.index + 1]
        model.DisplacementBC(name='OuterRoller', createStepName='Initial',
                             region=regionToolset.Region(faces=arr),
                             u1=0.0, u2=0.0, distributionType=UNIFORM)
    else:
        raise RuntimeError(
            'the outer curved face was not found, so the soil domain would be '
            'laterally unrestrained. Check the geometry and face selector.')

    base = inst.faces.getByBoundingBox(zMin=-Ds - 1e-6, zMax=-Ds + 1e-6)
    if len(base) == 0:
        raise RuntimeError('soil base face not found at z = %g' % -Ds)
    model.EncastreBC(name='Base', createStepName='Initial',
                     region=regionToolset.Region(faces=base))


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

def run_case(case, workdir, P):
    print('  %s: %s  [method=%s]' % (case, CASE_DOC[case], P.method))

    if P.soil_model == 'umat' and not P.umat_source:
        raise ValueError('soil_model=umat needs FLD_UMAT_SOURCE')

    model_name = 'Sc_' + case
    job_name = 'sc_%s_%s' % (P.method, case)
    h = build(P, model_name, case)
    print('  soil elements: %d   adaptive: %d' % (h['n_soil'],
                                                  h['ale_elements']))

    steps.report_time_budget(P.seed_fine, P.soil_e, P.soil_nu, P.soil_rho,
                             P.final_depth, P.ind_vel)

    staged = ''
    if P.soil_model == 'umat' and P.umat_source:
        subroutines.describe(P.umat_source)
        staged = subroutines.stage(P.umat_source, workdir)

    n_cpus = int(os.environ.get('FLD_NCPU', P.n_cpus))
    n_dom = int(os.environ.get('FLD_NDOMAINS', P.n_domains or n_cpus))
    job = jobs.make_explicit_job(model_name, job_name, n_cpus=n_cpus,
                                 n_domains=n_dom, user_subroutine=staged,
                                 description=CASE_DOC[case])
    inp = jobs.write_input(job, workdir)

    if P.method == 'ale':
        inpedit.inject_diagnostics(inp, mode='summary')
        # The plug region needs its own *Adaptive Mesh line: CAE wrote only one.
        inpedit.inject_extra_ale_domains(inp, ['ALE_Plug'], controls='ALE_BC',
                                         initial_mesh_sweeps=5)
    if P.soil_model == 'umat':
        if P.sdv_init.strip():
            values = [float(v) for v in P.sdv_init.replace(' ', '').split(',')]
            initial_set = 'SoilFilled' if P.method == 'cel' else 'SoilAll'
            materials.write_sdv_initial_conditions(inp, initial_set, values,
                                                   P.umat_nsdv)
        else:
            materials.sdv_initial_conditions_user(inp)

    chk = report.InpCheck(inp)
    chk.requires(r'^\*Dynamic, Explicit', 'explicit dynamics')
    chk.requires(r'^\*Contact\b', 'general contact')
    if P.method == 'ale':
        chk.count(r'^\*Adaptive Mesh,', 2, 'two adaptive regions (tip, plug)')
        chk.requires(r'^\*Adaptive Mesh,.*elset=ALE_Tip', 'tip region')
        chk.requires(r'^\*Adaptive Mesh,.*elset=ALE_Plug', 'plug region')
        chk.requires(r'^\*Diagnostics, adaptive mesh=summary', 'ALE diagnostics')
    else:
        chk.requires(r'^\*Eulerian Section', 'Eulerian soil')
        chk.requires(r'^\*Initial Conditions, type=VOLUME FRACTION',
                     'initial volume fraction')
    if case != 'J':
        chk.requires(r'^\*Step, name=Suction', 'the suction step exists')
        chk.requires(r'^\*Cload', 'the suction force is applied')
    chk.report()

    if not runner.flag('SUBMIT', True):
        return {'method': P.method, 'suction_kPa': h['suction'] / 1e3,
                'elements': h['n_soil'], 'submitted': False}

    jobs.submit(job)
    st = jobs.status(job_name, workdir)

    row = {'method': P.method,
           'suction_kPa': h['suction'] / 1e3,
           'elements': h['n_soil'],
           'adaptive_el': h['ale_elements'],
           'increments': st['increments'],
           'completed': st['completed'],
           'abort': (st['abort_reason'] or '')[:45]}

    if P.method == 'ale':
        msg = os.path.join(workdir, job_name + '.msg')
        if os.path.isfile(msg):
            info = ale.read_msg_activity(msg)
            row['pct_moved'] = info['avg_pct_moved']
            if not info['active']:
                print('  *** ALE was DEFINED BUT INERT -- see docs/02-ale-adaptive-meshing.md ***')

    odb = os.path.join(workdir, job_name + '.odb')
    if os.path.isfile(odb):
        r = energy.ratios(energy.read_energies(odb))
        row['ke_peak_%'] = 100.0 * r['ALLKE/ALLIE']['peak']
        row['grade'] = energy.verdict(r)
    return row


def main():
    workdir = config.workdir(STUDY)
    os.chdir(workdir)

    tee = report.start_log(os.path.join(workdir, STUDY + '.log'),
                           'SUCTION CAISSON INSTALLATION')
    try:
        print(__doc__)
        P = make_params()
        P.show()
        P.write_json(os.path.join(workdir, STUDY + '_params.json'))

        report.banner('MODELLING LIMITATION -- READ THIS', level=1)
        print("""
  This model applies suction as a net downward force on the caisson lid. It does
  NOT model the seepage gradient through the soil plug.

  In reality the upward flow inside the caisson loosens the plug, reduces the
  effective stress at the skirt tip and cuts inner friction. That is the
  mechanism that makes suction installation work in dense sand. Without it this
  model over-predicts the required suction, and it cannot reproduce plug heave
  or piping failure at all.

  Modelling it properly needs a coupled pore-fluid formulation. The Staubach
  upstream repository has a hydro-mechanically coupled VUMAT; it is not
  vendored here. See `docs/07-suction-caisson.md` for what would have to change.
""")

        rows = runner.run_study(
            STUDY, CASES, lambda c, w: run_case(c, w, P), workdir)
        runner.write_summary_csv(
            os.path.join(workdir, STUDY + '_summary.csv'), rows)

        report.banner('WHAT TO EXTRACT', level=1)
        print("""
  abaqus python lib/postproc/history.py sc_ale_J.odb CAISSONRP curve_J.csv

  Plot resistance against depth for case J. That is your jacked installation
  curve, and it is the reference every suction case should be read against:
  at the depth where suction takes over, the force the caisson needs is exactly
  the resistance from curve J.

  Then plot depth against time for cases S and S2. Penetration rate under a
  fixed suction is an outcome of the model, and its shape tells you whether the
  caisson is accelerating (resistance falling away -- check for plug failure) or
  stalling (resistance growing faster than the applied force).
""")
    finally:
        report.stop_log(tee)


main()
