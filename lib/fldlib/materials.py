"""Soil and structural materials, including the user-subroutine hook.

The examples in this repository run out of the box on Abaqus built-in models so
that anyone can reproduce them with no Fortran compiler and no licence
negotiation. Built-in Mohr-Coulomb is a perfectly good vehicle for learning ALE
and CEL mechanics: the numerics of the adaptive mesh do not care what the
constitutive model is.

They are, however, a poor vehicle for *sand*. Perfect plasticity with a constant
friction angle cannot represent dilatancy, state dependence, or the stress-path
dependence that dominates the penetration resistance of a caisson. For that you
want a critical-state or hypoplastic model, which means a UMAT (Standard) or
VUMAT (Explicit). `user_material()` below is the hook, and
`constitutive/README.md` explains what is available.

Two traps worth knowing before you write your first `*User Material`:

* `Depvar(n=...)` must match the number of state variables the subroutine
  actually writes. Too few and Abaqus overruns silently into whatever follows;
  too many and you waste memory but at least you get correct answers. A VUMAT
  wrapper around a UMAT usually needs *more* slots than the UMAT itself (one as
  an initialisation latch), which is a classic source of NaNs on the first
  increment.
* State variables must be *initialised*. An elastoplastic sand model reading a
  void ratio of 0.0 at the first increment produces NaN, and an Abaqus/Explicit
  job that hits NaN does not stop -- it keeps integrating, and you get a
  finished job full of garbage. Use `*Initial Conditions, type=SOLUTION` (either
  a written table or the SDVINI user routine) and then check the ODB is finite
  (`tools/check_odb_finite.py`).
"""

from __future__ import print_function

import math
import os


# ---------------------------------------------------------------------------
# Structural
# ---------------------------------------------------------------------------

def steel(model, name='Steel', youngs=210e9, poisson=0.3, density=7850.0,
          yield_stress=None):
    """Linear elastic (optionally perfectly plastic) structural steel.

    For a penetration analysis the structure is normally so much stiffer than
    the soil that it might as well be rigid, and modelling it as a rigid body is
    both cheaper and better conditioned -- a stiff deformable body drives the
    stable time increment down hard. Use this when you need stresses in the
    structure itself, and `rigid_body()` in `geometry.py` otherwise.
    """
    mat = model.Material(name=name)
    mat.Density(table=((density,),))
    mat.Elastic(table=((youngs, poisson),))
    if yield_stress is not None:
        mat.Plastic(table=((yield_stress, 0.0),))
    return mat


# ---------------------------------------------------------------------------
# Soil -- built in
# ---------------------------------------------------------------------------

def elastic_soil(model, name='SoilMat', youngs=20e6, poisson=0.3,
                 density=1651.6):
    """The simplest possible soil. Use it to isolate numerics from constitutive
    behaviour: if an ALE or CEL study misbehaves, rerun it elastic. Almost every
    surprise in this repository was first reproduced on an elastic block."""
    mat = model.Material(name=name)
    mat.Density(table=((density,),))
    mat.Elastic(table=((youngs, poisson),))
    return mat


def mohr_coulomb_soil(model, name='SoilMat', youngs=20e6, poisson=0.3,
                      density=1651.6, friction=32.0, dilation=2.0,
                      cohesion=1.0e3, hardening=None, tension_cutoff=True):
    """Abaqus built-in Mohr-Coulomb plasticity.

    `cohesion` must be strictly positive and `friction`/`dilation` strictly
    non-zero: the Abaqus implementation divides by them. A truly cohesionless
    sand is modelled with a small nominal cohesion (1 kPa here), which also
    keeps the surface elements from going into tension and failing instantly at
    the start of a penetration analysis.

    `dilation` well below `friction` is deliberate. Associated flow
    (dilation = friction) grossly over-predicts volume change and therefore
    resistance in a confined problem such as caisson installation.
    """
    if cohesion <= 0.0:
        raise ValueError('Abaqus Mohr-Coulomb requires cohesion > 0 '
                         '(use a small nominal value such as 1 kPa for sand)')
    if friction <= 0.0 or dilation <= 0.0:
        raise ValueError('Abaqus Mohr-Coulomb requires friction and dilation '
                         'angles strictly greater than zero')

    mat = model.Material(name=name)
    mat.Density(table=((density,),))
    mat.Elastic(table=((youngs, poisson),))
    mat.MohrCoulombPlasticity(table=((friction, dilation),))
    mat.mohrCoulombPlasticity.MohrCoulombHardening(
        table=hardening or ((cohesion, 0.0),))
    if tension_cutoff:
        mat.mohrCoulombPlasticity.TensionCutOff(table=((0.0, 0.0),))
    return mat


def drucker_prager_soil(model, name='SoilMat', youngs=20e6, poisson=0.3,
                        density=1651.6, friction=32.0, dilation=2.0,
                        hardening=None):
    """Abaqus built-in linear Drucker-Prager.

    Smoother than Mohr-Coulomb in the deviatoric plane, so it converges more
    easily and is kinder to an explicit solver, at the cost of over-predicting
    strength in triaxial extension. For a first ALE or CEL study this is usually
    the better-behaved choice; for a quantitative answer it is not.

    Note the argument order in the Abaqus table is (beta, K, psi) where beta and
    psi are the *Drucker-Prager* angles, not the Mohr-Coulomb friction and
    dilation angles. `dp_from_mc()` converts.
    """
    mat = model.Material(name=name)
    mat.Density(table=((density,),))
    mat.Elastic(table=((youngs, poisson),))
    mat.DruckerPrager(table=((friction, 1.0, dilation),))
    mat.druckerPrager.DruckerPragerHardening(
        table=hardening or ((10.0e3, 0.0), (12.0e3, 0.05),
                            (15.0e3, 0.10), (18.0e3, 0.20)))
    return mat


def dp_from_mc(phi_deg, psi_deg=None, match='compression'):
    """Convert Mohr-Coulomb angles to linear Drucker-Prager angles.

    `match='compression'` matches the two surfaces in triaxial compression,
    which is the right choice for a penetration problem where the soil beneath
    the tip is in compression. Returns ``(beta_deg, psi_dp_deg)``.
    """
    phi = math.radians(phi_deg)
    if match != 'compression':
        raise ValueError("only match='compression' is implemented")
    beta = math.degrees(math.atan(6.0 * math.sin(phi) / (3.0 - math.sin(phi))))
    psi_dp = None
    if psi_deg is not None:
        psi = math.radians(psi_deg)
        psi_dp = math.degrees(math.atan(6.0 * math.sin(psi) /
                                        (3.0 - math.sin(psi))))
    return beta, psi_dp


# ---------------------------------------------------------------------------
# Soil -- user subroutine
# ---------------------------------------------------------------------------

def read_constants(path, comment='#'):
    """Read a whitespace/newline separated list of material constants.

    Keeping the constants in a text file next to the subroutine, rather than
    inline in the model script, is what lets one calibration serve every model
    and lets you diff a recalibration.

    Blank lines and anything after `comment` are ignored, so the file can be
    documented.
    """
    if not os.path.isfile(path):
        raise IOError('material constants file not found: %s' % path)
    values = []
    fh = open(path)
    try:
        for line in fh:
            line = line.split(comment)[0].strip()
            if not line:
                continue
            for token in line.replace(',', ' ').split():
                values.append(float(token))
    finally:
        fh.close()
    if not values:
        raise ValueError('no constants read from %s' % path)
    return values


def user_material(model, name, constants, n_sdv, density, unsymm=True):
    """`*User Material` + `*Depvar` + `*Density`.

    `constants` is the PROPS array the subroutine will receive, in the order the
    subroutine expects -- read it with `read_constants()` from the file that
    ships with the model, never retype it.

    `n_sdv` is the `*Depvar` count and must match what the subroutine writes.
    Get this wrong and there is no error, only wrong answers.

    `unsymm=True` emits `unsymm=YES`, which matters for Abaqus/Standard: most
    soil models have a non-symmetric consistent tangent (non-associated flow),
    and letting Standard assume symmetry costs you convergence. It is ignored by
    Explicit.
    """
    if n_sdv < 1:
        raise ValueError('n_sdv must be >= 1 for a state-dependent model')
    mat = model.Material(name=name)
    mat.Density(table=((density,),))
    mat.UserMaterial(mechanicalConstants=tuple(constants),
                     unsymm=(unsymm and 1 or 0))
    mat.Depvar(n=n_sdv)
    return mat


def write_sdv_initial_conditions(inp_path, elset, values, n_sdv):
    """Write `*Initial Conditions, type=SOLUTION` with an explicit SDV table.

    The alternative is `*Initial Conditions, type=SOLUTION, USER`, which makes
    Abaqus call the SDVINI user routine. Prefer the explicit table when the
    initial state is uniform or a simple function of depth: it is visible in the
    deck, diffable, and does not need a second subroutine to debug.

    `values` is a list of `n_sdv` numbers applied to every element in `elset`.
    Abaqus accepts at most 8 values per line, continuation lines follow.

    `*Initial Conditions` is model data, so the block goes immediately before
    the first `*Step` card.
    """
    from . import inpedit

    if len(values) != n_sdv:
        raise ValueError('given %d initial values but *Depvar is %d -- these '
                         'must match exactly' % (len(values), n_sdv))

    rows, row = [], []
    for v in values:
        row.append('%.10g' % v)
        if len(row) == 8:
            rows.append(', '.join(row))
            row = []
    if row:
        rows.append(', '.join(row))

    block = ('**\n'
             '** INITIAL STATE VARIABLES (injected by fldlib)\n'
             '*Initial Conditions, type=SOLUTION\n'
             + elset + ', ' + rows[0] + '\n'
             + ''.join(r + '\n' for r in rows[1:])
             + '**')
    return inpedit.insert_before(inp_path, r'^\*Step[,\s]', block, once=True)


def sdv_initial_conditions_user(inp_path):
    """Write `*Initial Conditions, type=SOLUTION, USER` instead of a table.

    Use this when the initial state genuinely depends on position -- a void
    ratio or mean stress varying with depth -- and you have an SDVINI routine
    compiled alongside the UMAT/VUMAT. Remember that SDVINI is called once per
    integration point *before* the first increment, and that it receives
    COORDS, which is how you make the state depth-dependent.
    """
    from . import inpedit
    block = ('**\n'
             '** INITIAL STATE VARIABLES FROM SDVINI (injected by fldlib)\n'
             '*Initial Conditions, type=SOLUTION, USER\n'
             '**')
    return inpedit.insert_before(inp_path, r'^\*Step[,\s]', block, once=True)
