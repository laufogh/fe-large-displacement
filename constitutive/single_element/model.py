"""Verify a constitutive subroutine on ONE element before you trust it in a
large model.

    abaqus cae noGUI=constitutive/single_element/model.py

Debugging a UMAT inside a 50 000-element penetration analysis is a bad way to
spend a month. One element, prescribed strain path, a few seconds per run, and
you can see the stress path directly.

This example runs the same element through the same load paths in Abaqus/Standard
(UMAT) and Abaqus/Explicit (VUMAT) and compares them. That comparison is the
single most useful test there is: a UMAT and its VUMAT port should give the same
stress path for a rate-independent model, and when they do not, the difference
tells you which one is wrong.

Load paths
----------
oedo   one-dimensional compression: e11 = e22 = 0, e33 prescribed. Tests the
       stiffness and, for a critical-state model, the compression line.
triax  drained triaxial compression at constant cell pressure. Tests the failure
       surface, dilatancy and the critical state.
cyc    a small strain cycle repeated. Tests the unload-reload stiffness and, for
       models with intergranular strain, the small-strain stiffness recovery.
       This is where most VUMAT ports first go wrong.

Configure it
------------
    set FLD_UMAT_IMPLICIT=C:\\path\\to\\call.f
    set FLD_UMAT_EXPLICIT=C:\\path\\to\\call_dry.f
    set FLD_UMAT_CONSTANTS=C:\\path\\to\\constants.txt
    set FLD_UMAT_NSDV=40
    abaqus cae noGUI=constitutive/single_element/model.py

With no subroutine configured the example runs on the Abaqus built-in
Mohr-Coulomb model instead, which still exercises the whole harness and gives
you a reference stress path to compare your model against.

Things that will bite you
-------------------------
* **`*Depvar` must match what the subroutine writes.** A VUMAT wrapper around a
  UMAT usually needs one extra slot as an initialisation latch. Too few slots
  produces NaN on the first increment, or silent corruption.
* **State variables must be initialised.** A void ratio of 0.0 gives NaN in
  essentially every sand model. See `FLD_SDV_INIT` below.
* **Abaqus/Explicit does not stop on NaN.** The job runs to completion and
  writes a complete ODB full of NaN. This example checks the ODB explicitly;
  `tools/check_odb_finite.py` does the same for any job.
* **Paths with spaces break the Fortran compile.** The subroutine and everything
  it includes are staged into a space-free working directory first.
"""

from __future__ import print_function

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_ROOT, 'lib'))
sys.path.insert(0, os.path.join(_ROOT, 'examples'))

from abaqus import mdb                                          # noqa: E402
from abaqusConstants import (THREE_D, DEFORMABLE_BODY, ON, OFF, C3D8R, HEX,
                             STRUCTURED, EXPLICIT, STANDARD, MIDDLE_SURFACE,
                             FROM_SECTION, UNIFORM, CARTESIAN, STEP)  # noqa: E402
import mesh                                                     # noqa: E402
import regionToolset                                            # noqa: E402

from fldlib import (config, report, jobs, steps, materials, subroutines,
                    inpedit)                                    # noqa: E402
from common import runner                                       # noqa: E402


STUDY = 'umat_single_element'

PATHS = ['oedo', 'triax', 'cyc']
SOLVERS = ['implicit', 'explicit']
CASES = ['%s_%s' % (p, s) for p in PATHS for s in SOLVERS]

PATH_DOC = {
    'oedo': 'oedometric compression (e11 = e22 = 0)',
    'triax': 'drained triaxial compression at constant cell pressure',
    'cyc': 'strain cycles (unload-reload and small-strain stiffness)',
}


def make_params():
    P = config.Params(STUDY)
    P.add('side', 0.01, 'm', 'cube side length')
    P.add('soil_rho', 1651.6, 'kg/m3', 'density')
    P.add('umat_implicit', '', '-', 'UMAT source for Abaqus/Standard')
    P.add('umat_explicit', '', '-', 'VUMAT source for Abaqus/Explicit')
    P.add('umat_constants', '', '-', 'material constants file')
    P.add('umat_nsdv', 40, '-', 'number of state variables (*Depvar)')
    P.add('sdv_init', '', '-',
          'comma-separated initial SDV values (blank -> SDVINI user routine)')
    P.add('axial_strain', 0.10, '-', 'target axial strain magnitude')
    P.add('cell_pressure', 100.0e3, 'Pa', 'triaxial cell pressure')
    P.add('n_cycles', 5, '-', 'number of strain cycles (cyc path)')
    P.add('cyc_strain', 0.002, '-', 'amplitude of each cycle')
    P.add('explicit_time', 1.0, 's', 'step period for the explicit runs')
    # Fallback so the example is runnable with no Fortran at all.
    P.add('soil_e', 20.0e6, 'Pa', 'Young modulus (fallback model)')
    P.add('soil_nu', 0.30, '-', 'Poisson ratio (fallback model)')
    P.add('soil_phi', 32.0, 'deg', 'friction angle (fallback model)')
    P.add('soil_psi', 2.0, 'deg', 'dilation angle (fallback model)')
    P.add('soil_coh', 1.0e3, 'Pa', 'cohesion (fallback model)')
    return P.resolve()


def build_cube(P, model_name, path, solver):
    if model_name in mdb.models:
        del mdb.models[model_name]
    model = mdb.Model(name=model_name)
    s = P.side

    sk = model.ConstrainedSketch(name='cube', sheetSize=10.0 * s)
    sk.rectangle(point1=(0.0, 0.0), point2=(s, s))
    part = model.Part(name='Cube', dimensionality=THREE_D,
                      type=DEFORMABLE_BODY)
    part.BaseSolidExtrude(sketch=sk, depth=s)

    # -- material ----------------------------------------------------------
    source = P.umat_implicit if solver == 'implicit' else P.umat_explicit
    if bool(source) != bool(P.umat_constants):
        raise ValueError(
            '%s user-material run needs both its FLD_UMAT_%s source and '
            'FLD_UMAT_CONSTANTS; configure both or neither'
            % (solver, solver.upper()))
    using_umat = bool(source and P.umat_constants)
    if using_umat:
        constants = materials.read_constants(P.umat_constants)
        print('  %d material constants from %s'
              % (len(constants), P.umat_constants))
        materials.user_material(model, 'SoilMat', constants, P.umat_nsdv,
                                P.soil_rho)
    else:
        print('  no subroutine configured for %s -- falling back to the '
              'built-in Mohr-Coulomb model' % solver)
        materials.mohr_coulomb_soil(
            model, 'SoilMat', P.soil_e, P.soil_nu, P.soil_rho,
            P.soil_phi, P.soil_psi, P.soil_coh)

    model.HomogeneousSolidSection(name='Sec', material='SoilMat',
                                  thickness=None)
    part.SectionAssignment(region=regionToolset.Region(cells=part.cells),
                           sectionName='Sec', offsetType=MIDDLE_SURFACE,
                           thicknessAssignment=FROM_SECTION)

    # -- one element -------------------------------------------------------
    library = STANDARD if solver == 'implicit' else EXPLICIT
    part.setElementType(regions=(part.cells,),
                        elemTypes=(mesh.ElemType(elemCode=C3D8R,
                                                 elemLibrary=library),))
    part.setMeshControls(regions=part.cells, elemShape=HEX,
                         technique=STRUCTURED)
    part.seedPart(size=s, deviationFactor=0.1, minSizeFactor=0.1)
    part.generateMesh()
    if len(part.elements) != 1:
        raise RuntimeError('expected exactly one element, got %d -- adjust '
                           'the seed' % len(part.elements))

    asm = model.rootAssembly
    asm.DatumCsysByDefault(CARTESIAN)
    inst = asm.Instance(name='CubeInst', part=part, dependent=ON)
    asm.Set(name='AllElements', elements=inst.elements)

    # -- symmetry faces ----------------------------------------------------
    for name, point, dof in (('X0', (0.0, s / 2, s / 2), 1),
                             ('Y0', (s / 2, 0.0, s / 2), 2),
                             ('Z0', (s / 2, s / 2, 0.0), 3)):
        faces = inst.faces.findAt((point,))
        if len(faces) == 0:
            raise RuntimeError('findAt missed face %s at %r' % (name, point))
        kwargs = {'name': 'Sym-' + name, 'createStepName': 'Initial',
                  'region': regionToolset.Region(faces=faces),
                  'distributionType': UNIFORM}
        kwargs['u%d' % dof] = 0.0
        model.DisplacementBC(**kwargs)

    top = inst.faces.findAt(((s / 2, s / 2, s),))
    side_x = inst.faces.findAt(((s, s / 2, s / 2),))
    side_y = inst.faces.findAt((( s / 2, s, s / 2),))
    for label, faces in (('top', top), ('x', side_x), ('y', side_y)):
        if len(faces) == 0:
            raise RuntimeError('findAt missed the %s loaded face' % label)

    # -- step and loading path --------------------------------------------
    # Triaxial loading needs a separate confinement step. Applying the cell
    # pressure in the axial loading step made it ramp in Standard but jump in
    # Explicit, so the supposedly matched solvers followed different paths and
    # neither started axial shearing at constant cell pressure.
    previous = 'Initial'
    if path == 'triax':
        if solver == 'implicit':
            model.StaticStep(name='Confinement', previous='Initial', nlgeom=ON,
                             timePeriod=1.0, initialInc=0.01, minInc=1e-9,
                             maxInc=0.05, maxNumInc=1000)
            confinement_period = 1.0
        else:
            confinement_period = P.explicit_time
            steps.explicit_step(model, 'Confinement', 'Initial',
                                confinement_period, nlgeom=True)
        model.SmoothStepAmplitude(
            name='CellRamp', timeSpan=STEP,
            data=((0.0, 0.0), (confinement_period, 1.0)))
        model.Pressure(
            name='CellX', createStepName='Confinement',
            region=asm.Surface(side1Faces=side_x, name='SurfX'),
            magnitude=P.cell_pressure, amplitude='CellRamp',
            distributionType=UNIFORM)
        model.Pressure(
            name='CellY', createStepName='Confinement',
            region=asm.Surface(side1Faces=side_y, name='SurfY'),
            magnitude=P.cell_pressure, amplitude='CellRamp',
            distributionType=UNIFORM)
        model.Pressure(
            name='CellZ', createStepName='Confinement',
            region=asm.Surface(side1Faces=top, name='SurfZ'),
            magnitude=P.cell_pressure, amplitude='CellRamp',
            distributionType=UNIFORM)
        steps.energy_output(model, 'Confinement', interval=100)
        previous = 'Confinement'

    step_name = 'Load'
    if solver == 'implicit':
        model.StaticStep(name=step_name, previous=previous, nlgeom=ON,
                         timePeriod=1.0, initialInc=0.005, minInc=1e-9,
                         maxInc=0.02, maxNumInc=10000)
        period = 1.0
    else:
        steps.explicit_step(model, step_name, previous, P.explicit_time,
                            nlgeom=True)
        period = P.explicit_time
    steps.energy_output(model, step_name, interval=200)

    _amplitude(model, path, period, P)
    _loading(model, path, step_name, P, s, top, side_x, side_y)

    model.HistoryOutputRequest(
        name='Element', createStepName=step_name,
        region=asm.sets['AllElements'],
        variables=('S11', 'S22', 'S33', 'S12', 'S13', 'S23',
                   'LE11', 'LE22', 'LE33', 'SDV'),
        numIntervals=400)

    return {'model': model, 'step_name': step_name, 'using_umat': using_umat,
            'period': period}


def _amplitude(model, path, period, P):
    if path == 'cyc':
        data = [(0.0, 0.0)]
        n = P.n_cycles
        for i in range(n):
            t0 = period * (i + 0.5) / n
            t1 = period * (i + 1.0) / n
            data.append((t0, 1.0))
            data.append((t1, 0.0))
        model.TabularAmplitude(name='Path', timeSpan=STEP, data=tuple(data))
    else:
        model.SmoothStepAmplitude(name='Path', timeSpan=STEP,
                                  data=((0.0, 0.0), (period, 1.0)))


def _loading(model, path, step_name, P, s, top, side_x, side_y):
    """Prescribe the strain path.

    All three paths are displacement-controlled on the top face. The difference
    is what the lateral faces do: fixed (oedometric) or loaded to a constant
    cell pressure (triaxial).
    """
    strain = P.cyc_strain if path == 'cyc' else P.axial_strain
    u3 = -strain * s

    model.DisplacementBC(
        name='Axial', createStepName=step_name,
        region=regionToolset.Region(faces=top),
        u3=u3, amplitude='Path', distributionType=UNIFORM)

    if path in ('oedo', 'cyc'):
        # Lateral strain suppressed -> oedometric conditions.
        model.DisplacementBC(
            name='LatX', createStepName=step_name,
            region=regionToolset.Region(faces=side_x), u1=0.0,
            distributionType=UNIFORM)
        model.DisplacementBC(
            name='LatY', createStepName=step_name,
            region=regionToolset.Region(faces=side_y), u2=0.0,
            distributionType=UNIFORM)
    else:
        # Cell pressure was established in the Confinement step and propagates
        # at its full value through this axial loading step.
        pass


def check_finite(odb_path, printer=print):
    """Confirm the ODB contains no NaN or Inf.

    Abaqus/Explicit will happily integrate NaN to the end of the step and write
    a complete, well-formed, entirely meaningless ODB. This is not an edge case;
    it is the normal outcome of an uninitialised state variable.
    """
    from odbAccess import openOdb

    odb = openOdb(odb_path, readOnly=True)
    bad = []
    try:
        for step in odb.steps.values():
            for frame in step.frames:
                for fname in ('S', 'LE', 'U', 'SDV1'):
                    if fname not in frame.fieldOutputs:
                        continue
                    for value in frame.fieldOutputs[fname].values:
                        data = value.data
                        items = data if hasattr(data, '__len__') else [data]
                        for v in items:
                            if v != v or v in (float('inf'), float('-inf')):
                                bad.append('%s in %s' % (fname, step.name))
                                break
    finally:
        odb.close()
    if bad:
        printer('  *** NON-FINITE VALUES: %s ***' % ', '.join(sorted(set(bad))))
        return False
    printer('  ODB is finite (no NaN or Inf in S, LE, U, SDV1)')
    return True


def run_case(case, workdir, P):
    path, solver = case.rsplit('_', 1)
    print('  %s: %s, %s' % (case, PATH_DOC[path], solver))

    model_name = 'Umat_' + case
    job_name = 'umat_%s' % case
    handles = build_cube(P, model_name, path, solver)

    source = P.umat_implicit if solver == 'implicit' else P.umat_explicit
    staged = ''
    if handles['using_umat']:
        subroutines.describe(source)
        staged = subroutines.stage(source, workdir)

    if solver == 'implicit':
        job = jobs.make_implicit_job(model_name, job_name, n_cpus=1,
                                     user_subroutine=staged)
    else:
        job = jobs.make_explicit_job(model_name, job_name, n_cpus=1,
                                     user_subroutine=staged)
    inp = jobs.write_input(job, workdir)

    if handles['using_umat']:
        if P.sdv_init.strip():
            values = [float(v) for v in P.sdv_init.replace(' ', '').split(',')]
            materials.write_sdv_initial_conditions(
                inp, 'AllElements', values, P.umat_nsdv)
            print('  wrote %d initial SDV values into the deck' % len(values))
        else:
            materials.sdv_initial_conditions_user(inp)
            print('  *Initial Conditions, type=SOLUTION, USER -- your SDVINI '
                  'routine must be compiled in')

    chk = report.InpCheck(inp)
    if handles['using_umat']:
        chk.requires(r'^\*User Material', 'user material defined')
        chk.requires(r'^\*Depvar', 'state variables declared')
        chk.requires(r'^\*Initial Conditions, type=SOLUTION',
                     'state variables initialised (NaN otherwise)')
    else:
        chk.requires(r'^\*Mohr Coulomb', 'fallback built-in model')
    chk.count(r'^\*Element,', 1, 'exactly one element block')
    chk.report()

    if not runner.flag('SUBMIT', True):
        return {'path': path, 'solver': solver, 'umat': handles['using_umat'],
                'submitted': False}

    jobs.submit(job)
    st = jobs.status(job_name, workdir)

    odb = os.path.join(workdir, job_name + '.odb')
    finite = check_finite(odb) if os.path.isfile(odb) else None

    return {'path': path, 'solver': solver, 'umat': handles['using_umat'],
            'increments': st['increments'], 'completed': st['completed'],
            'finite': finite, 'abort': (st['abort_reason'] or '')[:50]}


def main():
    workdir = config.workdir(STUDY)
    os.chdir(workdir)

    tee = report.start_log(os.path.join(workdir, STUDY + '.log'),
                           'SINGLE-ELEMENT CONSTITUTIVE CHECK')
    try:
        print(__doc__)
        P = make_params()
        P.show()
        P.write_json(os.path.join(workdir, STUDY + '_params.json'))

        rows = runner.run_study(
            STUDY, CASES, lambda c, w: run_case(c, w, P), workdir)
        runner.write_summary_csv(
            os.path.join(workdir, STUDY + '_summary.csv'), rows)

        report.banner('COMPARING IMPLICIT AND EXPLICIT', level=1)
        print("""
  For each load path, plot S33 against LE33 from the implicit and the explicit
  run on the same axes. For a rate-independent model they should lie on top of
  each other.

  When they do not:

    * a constant offset usually means different constants or a different unit
      convention between the two constants files;
    * divergence that grows with strain usually means the explicit integration
      is substepping too coarsely -- check for a substepping tolerance in the
      VUMAT;
    * a difference only on unloading points at the intergranular-strain or
      elastic-predictor part of the port;
    * NaN in the explicit run and not the implicit one is almost always
      `*Depvar` or uninitialised state.

  Only once these agree should the model go anywhere near a penetration job.
""")
    finally:
        report.stop_log(tee)


main()
