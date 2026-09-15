---
title: "Mohr--Coulomb for Abaqus/Explicit"
subtitle: "Porting the Clausen UMAT to a VUMAT"
date: "8 September 2026"
geometry: "a4paper, margin=2.4cm"
fontsize: 11pt
colorlinks: true
---

# Summary

`MohrCoulombAbaqus.for` (Clausen \& Andersen, linear elastic -- perfectly plastic
Mohr--Coulomb) now has a standalone-verified Abaqus/Explicit adapter. The
constitutive model was **not** rewritten. `VUMAT_MohrCoulomb.f` adapts the
Abaqus/Explicit calling convention to the Abaqus/Standard one and calls the
existing UMAT once per material point. `MohrCoulombAbaqus.for` is untouched.

The wrapper follows `VUMAT_dry_Staubach.f` from the hypoplasticity suite, which
is the working precedent in this project.

Verified outside Abaqus against the UMAT on identical strain paths: **the stresses agree to the
last bit** (max difference exactly 0 Pa over 400 steps in 3D and 300 in plane
strain, both paths passing through yield and back), and the material constants
survive a **single precision** build. An Abaqus compile/data-check and
single-element run remain required on the target release.

# Files added

All in `constitutive/mohr-coulomb-clausen/`.

| File | Lines | Purpose |
|:--|--:|:--|
| `VUMAT_MohrCoulomb.f` | 220 | The wrapper |
| `call_explicit.f` | 2 | Build glue: `include`s the UMAT and the wrapper |
| `verification/` | -- | Standalone gfortran checks, no Abaqus needed |

# Why a wrapper is enough

The Clausen UMAT is a *closed-form* return map: elastic predictor, then an exact
return in principal stress space. That matters because it has

- no Newton iteration and no substepping,
- no `PNEWDT` cutback request,
- and no dependence of the stress update on the consistent tangent `DDSDDE`.

An explicit solver needs none of those things, and `DDSDDE` --- the one output a
VUMAT cannot return --- is a by-product here, not an input to the answer. So the
wrapper computes it and throws it away, and the stress update is unchanged.

This is a *smaller* job than the hypoplastic port, where the stiffness grows with
mean stress and the stable time increment has to be managed carefully. Here $E$ is
constant, so $\Delta t$ is constant and predictable.

# What the wrapper converts

| # | Abaqus/Explicit gives | The UMAT wants | Fix |
|:--|:--|:--|:--|
| 1 | one block of `nblock` points | one point | loop `iblock = 1, nblock` |
| 2 | order 11,22,33,**12,23,13** | order 11,22,33,**12,13,23** | swap slots 5 and 6 |
| 3 | tensorial shear strain $\varepsilon_{12}$ | engineering shear $\gamma_{12}$ | multiply strains by 2 |
| 4 | corotational stress, already rotated | `DROT` | ignore `DROT` (the UMAT ignores it too) |
| 5 | probe call at $t=0$ to size $\Delta t$ | -- | elastic branch, see next section |

Items 2 and 3 are the only ones that can silently give wrong answers, so they are
the ones the verification targets. Unpacking:

```fortran
        do i = 1, ndi
          stress(i) = stressOld(iblock,i)
          dstran(i) = strainInc(iblock,i)
        enddo

c       Component order. Abaqus/Explicit uses 11,22,33,12,23,13 whereas
c       the UMAT expects 11,22,33,12,13,23, so slots 5 and 6 swap.
c       Shear strains are converted from tensorial to engineering measure;
c       shear stresses need no scaling.
        stress(4) = stressOld(iblock,4)
        dstran(4) = 2.0d0 * strainInc(iblock,4)

        if (nshr .gt. 1) then
          stress(5) = stressOld(iblock,6)
          stress(6) = stressOld(iblock,5)
          dstran(5) = 2.0d0 * strainInc(iblock,6)
          dstran(6) = 2.0d0 * strainInc(iblock,5)
        endif
```

and repacking, which undoes the swap and applies no scaling to stress:

```fortran
        do i = 1, ndi
          stressNew(iblock,i) = stress(i)
        enddo
        stressNew(iblock,4) = stress(4)
        if (nshr .gt. 1) then
          stressNew(iblock,5) = stress(6)
          stressNew(iblock,6) = stress(5)
        endif
```

The `nshr .gt. 1` guard means plane strain and axisymmetric elements
(`ntens = 4`) work as well as 3D. That is free: `DlinElas`, `Invariants`,
`PrinStressAna`, `PrinDirect` and `TransMatrix` in the UMAT all already branch
on `nsigma == 4` versus `nsigma == 6`.

# The one genuinely awkward part: the $t=0$ probe call

Abaqus/Explicit calls the VUMAT once before the analysis with a probe strain
increment, and infers the initial stable time increment from the stress it gets
back. Mohr--Coulomb cannot answer that call honestly: at zero stress with zero
cohesion the apex of the yield surface sits at the origin, so the return map
would hand back zero stress, no stiffness, and no wave speed.

The hypoplastic wrapper solves this with a hand-tuned `probeE = 3.0d8` and a
long comment warning that it must be re-derived whenever the mesh or units
change. **Mohr--Coulomb needs no such tuning**, because `props(1)` and `props(2)`
*are* $E$ and $\nu$ --- the exact linear elastic response is available for free:

```fortran
      ischeck = 0
      if (totalTime .le. 0.0d0) ischeck = 1
      ...
        if (ischeck .eq. 1) then
          alam = props(1) * props(2)
     &         / ((1.0d0 + props(2)) * (1.0d0 - 2.0d0*props(2)))
          amu  = props(1) / (2.0d0 * (1.0d0 + props(2)))
          trde = 0.0d0
          do i = 1, ndi
            trde = trde + dstran(i)
          enddo
          do i = 1, ndi
            stress(i) = stress(i) + alam*trde + 2.0d0*amu*dstran(i)
          enddo
          do i = ndi+1, ntens
            stress(i) = stress(i) + amu*dstran(i)
          enddo
        else
          call umat(...)
        endif
```

`totalTime` is the value at the *start* of the increment, so this branch is taken
for the data-check call and for the first real increment of the analysis. The
cost is therefore at most one elastic increment (order $10^{-6}$ s) at $t=0$,
where the stress is still the initial state. Unlike the hypoplastic version, the
condition contains no job-specific constant, so it does not need revisiting per
analysis.

# Three defects found while porting

All three were caught by compiling the wrapper and the UMAT as a single translation
unit, which lets the compiler cross-check the call.

**1. `PREDEF` and `DPRED` are scalars in this UMAT.** The standard UMAT signature
declares them as arrays, and the hypoplastic wrapper passes whole arrays
accordingly. `MohrCoulombAbaqus.for:115` declares them as plain scalars. Passing
arrays is a rank mismatch --- a hard compile error here, and silent memory
misuse in a build where the two files are compiled separately. The wrapper passes
array *elements*:

```fortran
     &      stran,dstran,time,dtime,ztemp,zdtemp,predef(1),dpred(1),
```

**2. The banner `write` to unit 6.** `MohrCoulombAbaqus.for:194` prints the model
name once, guarded by `NOEL == 1 .and. NPT == 1`. Writing to unit 6 from inside a
VUMAT is unsafe under domain parallelism. The wrapper passes `NOEL = 0` and
`NPT = 0`, so the guard can never fire. Verified: the banner appears when the
test driver calls the UMAT directly, and never via the VUMAT path.

**3. `props` must be promoted to double precision.** This one is invisible in a
double precision build and silently wrong in a single precision one. Abaqus
resolves `vaba_param.inc` to `vaba_param_sp.inc` for
`Single Precision Abaqus/Explicit`, and that header is nothing but
`implicit real (a-h,o-z)` --- so every VUMAT argument declared in the `dimension`
statement, `props` included, arrives as `real*4`. The UMAT declares
`real(8) PROPS(NPROPS)`. Handing `props` straight over reinterprets the bit
pattern and corrupts all five constants. The wrapper copies first:

```fortran
      double precision mat_props(nprops)
      ...
      do i = 1, nprops
        mat_props(i) = props(i)
      enddo
```

and passes `mat_props`. This is what `mat_props` is doing in
`VUMAT_dry_Staubach.f` --- it is not only there to inject the probe modulus.
Every other argument the wrapper hands the UMAT is a locally declared
`double precision` variable filled element by element, so `props` was the only
one exposed.

Separately, the unused UMAT arguments (`SSE`, `SPD`, `SCD`, `RPL`, `TEMP`,
`DTEMP`, `PNEWDT`, `CELENT`) are passed as declared `real*8` zeros rather than
the integer literals used in the hypoplastic wrapper, so the actual and dummy
argument types match.

# Verification

`verification/run_checks.cmd` builds and runs four checks with
gfortran alone --- no Abaqus licence needed. Each drives one identical *physical*
strain path twice, once straight through the UMAT and once through the VUMAT,
then maps the VUMAT answer back and compares.

Shear is non-zero in all three components, and every path yields and then
elastically unloads, so the slot swap, the factor of 2, and both the elastic and
plastic code paths are all exercised.

| Test | Configuration | Result |
|:--|:--|:--|
| 1 | 3D, `ntens = 6`, 400 steps, reaches region 1 | max $|\Delta\sigma|$ = **0.0 Pa** |
| 2 | Plane strain, `ntens = 4`, `nblock = 3`, reaches region 1 | max $|\Delta\sigma|$ = **0.0 Pa** |
| 3 | $t=0$ probe returns constrained modulus $M$ | relative error **0.0** |
| 4 | Single precision, `real*4` interface arrays, reaches region 2 | constants intact, yield residual $8\times10^{-3}$ Pa |

Test 3 confirms the probe branch returns $M = E(1-\nu)/[(1+\nu)(1-2\nu)]$ exactly,
which is what Abaqus needs for the wave speed --- $183.45$ m/s for
$E = 50$ MPa, $\nu = 0.3$, $\rho = 2000$ kg/m$^3$.

Zero difference rather than merely small difference is expected and is the right
result: the wrapper only permutes and scales, so the UMAT sees the identical
floating-point inputs in both runs.

Test 4 builds the same code against a single precision `vaba_param.inc` and
declares every interface array `real*4`, as Abaqus does. It checks that the probe
still returns $M$ exactly, and that after being driven to yield the returned
stresses satisfy the Mohr--Coulomb criterion $k\sigma_1-\sigma_3-\sigma_c=0$ to
within $8\times10^{-3}$ Pa on stresses of order $4\times10^{5}$ Pa --- which is
only true if $c$ and $\varphi$ were read correctly. Run against the unfixed
wrapper the same test does not merely fail, it does not compile:
`Type mismatch in argument 'props'; passed REAL(4) to REAL(8)`.

# Running it in Abaqus/Explicit

Material definition is unchanged from the UMAT --- same five constants, in the
same order:

```
*MATERIAL, NAME=MC
*DENSITY
 2000.,
*USER MATERIAL, CONSTANTS=5
 50.0E6, 0.3, 1.0E3, 30.0, 5.0
*DEPVAR
 1,
```

$E$, $\nu$, $c$, $\varphi$ [deg], $\psi$ [deg]. Neither $\varphi$ nor $\psi$ may be
zero. `SDV1` carries the return region: 0 elastic, 1 single surface, 2 compression
meridian, 3 tension meridian, 4 apex.

For Explicit, submit against **`call_explicit`**, not against the VUMAT file,
exactly as the hypoplasticity suite submits against `call_explicit_dry`:

```
abaqus job=myjob inp=myjob cpus=4 user=call_explicit
```

`call_explicit.f` is two lines, and it is the whole reason the link works:

```fortran
      include'MohrCoulombAbaqus.for'
      include'VUMAT_MohrCoulomb.f'
```

Abaqus compiles only the one file named by `user=`. Pointing it at
`VUMAT_MohrCoulomb.f` directly compiles the wrapper without the model, and the
link fails with

```
VUMAT_MohrCoulomb.obj : error LNK2019: unresolved external
symbol umat referenced in function vumat
```

Both source files and `call_explicit.f` must sit in the job directory (or be reachable
from it), since the `include`s are resolved relative to the file being compiled.
`double=both` is optional --- the wrapper is correct in single precision too ---
but is worth adding for a geotechnical job that accumulates small strains over
many increments.

# Limitations

The first two items describe verification/build coverage; the remainder are
properties of the model in an explicit setting rather than adapter defects.

- **Standalone coverage is not full constitutive validation.** The
  double-precision UMAT/VUMAT equivalence paths reach elastic response and
  return region 1. The single-precision smoke test reaches region 2 but checks
  its yield residual rather than UMAT/VUMAT equivalence. Dedicated equivalence
  paths for regions 2--4, plus an Abaqus single-element run, are still required.
- **Extended fixed-form source is required.** The inherited `.for` source has
  significant text beyond column 72. The standalone build uses
  `-ffixed-line-length-none`; confirm the target Abaqus compiler configuration
  enables extended fixed source.

- **No regularisation.** Perfect plasticity with no softening length scale means
  shear bands localise to one element and results are mesh-dependent.
- **Unbounded dilation** for $\psi > 0$: there is no critical state, so shearing
  dilates without limit.
- **Start away from the apex.** With $c = 0$ the apex is at the origin, so a job
  starting from zero stress has no stiffness. Use a geostatic initial stress
  (`*INITIAL CONDITIONS, TYPE=STRESS`) or a small cohesion.
- **`ALLPD` is not meaningful.** The UMAT does not report plastic dissipation, so
  `enerInelas` is carried over unchanged. `ALLIE` is computed correctly.
- **`dtArray` convention.** The wrapper takes the time increment as
  `dtArray(1)`, matching every other VUMAT in this project (Abaqus 2022 and
  later). On older Abaqus versions the argument is a scalar `dt` and that one
  declaration would need changing.

# Suggested next step

Compile the UMAT and the VUMAT adapter with the target Abaqus release and run
a one-element job. That adds the actual Abaqus ABI, data-check call, element
integration and ODB output to the standalone coverage here.
