# Constitutive models for large-displacement geotechnics

Companion to `constitutive/single_element` and `constitutive/`.

## Why the built-in models are not enough

Every example in this repository runs by default on Abaqus built-in Mohr-Coulomb
or Drucker-Prager. That is deliberate — it means anyone can reproduce the results
with no Fortran compiler — and for learning ALE and CEL mechanics it is entirely
adequate. The numerics of an adaptive mesh do not care what the constitutive
model is.

For *sand*, they are not adequate at all:

* **No state dependence.** A constant friction angle cannot represent the fact
  that dense sand and loose sand at the same stress behave completely
  differently, or that the same sand behaves differently at 10 kPa and 1 MPa.
* **No dilatancy evolution.** Real sand dilates, reaches a peak, then softens
  towards critical state. Perfect plasticity has no peak and no softening, so it
  cannot reproduce either the peak resistance or the post-peak behaviour that
  governs plug stability in a caisson.
* **No memory.** Installation is a large monotonic event followed by cyclic
  service loading. A model with no fabric or intergranular strain cannot carry
  the installation history into the service analysis, which is the entire point
  of modelling installation.

For a caisson in sand, the constitutive model, not the formulation, dominates the
answer. ALE and CEL are how you get the model to *run*; the constitutive model
is what makes the number mean something.

## What is available here

See [`constitutive/README.md`](../constitutive/README.md) for the current
contents and their licences. In summary:

| Model | Type | Where |
|---|---|---|
| Hypoplasticity with intergranular strain (Niemunis-Herle), dry/uncoupled implementation | UMAT + VUMAT | `constitutive/hypoplasticity-staubach/` (GPL-3.0) |
| Mohr-Coulomb with exact stress return and corner handling (Clausen) | UMAT + VUMAT | `constitutive/mohr-coulomb-clausen/` (custom permission; three citations required) |
## The workflow that works

### 1. Verify the subroutine on one element first

`constitutive/single_element` runs a single element through oedometric
compression, drained triaxial compression and strain cycles, in **both**
Abaqus/Standard (UMAT) and Abaqus/Explicit (VUMAT), and compares them.

For a rate-independent model the two must give the same stress path. When they
do not:

* a constant offset → different constants or a unit-convention mismatch between
  the two constants files;
* divergence growing with strain → the explicit integration is substepping too
  coarsely;
* a difference only on unloading → the intergranular-strain or elastic-predictor
  part of the port;
* NaN in explicit but not implicit → `*Depvar` or uninitialised state.

Debugging any of these inside a 50 000-element penetration analysis costs weeks.
On one element it costs seconds.

### 2. Get `*Depvar` right

The `*Depvar` count must match what the subroutine actually writes. A VUMAT
wrapper around a UMAT usually needs **more** slots than the UMAT — commonly one
extra as an initialisation latch. Too few and Abaqus overruns into whatever
follows, silently.

### 3. Initialise the state

An elastoplastic sand model reading a void ratio of 0.0 on the first increment
produces NaN. Two routes:

```
*Initial Conditions, type=SOLUTION            ← explicit table, visible in the deck
*Initial Conditions, type=SOLUTION, USER      ← Abaqus calls your SDVINI routine
```

Prefer the table when the initial state is uniform or a simple function of depth:
it is diffable, reviewable, and does not need a second subroutine to debug. Use
SDVINI when the state genuinely depends on position — it receives `COORDS`, which
is how you make void ratio or mean stress depth-dependent.

### 4. Check the ODB is finite

**Abaqus/Explicit does not stop on NaN.** It integrates NaN happily to the end of
the step and writes a complete, well-formed, entirely meaningless ODB. This is
not an edge case — it is the normal outcome of an uninitialised state variable.

```bash
abaqus python tools/check_odb_finite.py my_job.odb
```

Run it on every user-material job. Every one.

### 5. Only then put it in the big model

And when you do, expect the run time to rise by a large factor. A hypoplastic
model with intergranular strain costs perhaps 5–20× a built-in Mohr-Coulomb
evaluation per integration point, and in an explicit analysis you are doing
several million of those.

## Compiling

See [abaqus-launch-guide.md](abaqus-launch-guide.md). The short version:

* launch through the Abaqus command wrapper, never `ABQLauncher.exe` directly,
  or the Fortran/MSVC environment is not set up and the link fails;
* the source path must contain **no spaces** — `fldlib.subroutines.stage()`
  copies the subroutine and everything it `include`s into a space-free working
  directory for exactly this reason;
* `abaqus verify -user_std` and `abaqus verify -user_exp` tell you in two minutes
  whether your toolchain works at all. Run them first on any new machine.

## Adding your own

Drop it under `constitutive/<name>/` with:

* the Fortran source and any `include` files;
* a `constants.txt` — one calibration per file, documented, so one calibration
  can serve every model and a recalibration is a diff;
* a `README.md` recording what the model is, the constant order, the SDV layout
  and the `*Depvar` count;
* a `PROVENANCE.md` recording where it came from and under what licence.

Then run `constitutive/single_element` against it and commit the resulting
stress paths as the reference. That is what makes the next port checkable.
