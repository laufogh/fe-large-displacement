# Constitutive models

> **Licence warning.** The repository-root MIT licence does **not** cover every
> subdirectory here. Each one carries its own `LICENSE` and/or `PROVENANCE.md`,
> and those terms govern. Read them before you redistribute anything.

| Directory | Model | Licence | Status |
|---|---|---|---|
| [`hypoplasticity-staubach/`](hypoplasticity-staubach/) | Hypoplasticity with intergranular strain (Niemunis–Herle), UMAT + VUMAT | **GPL-3.0** | included |
| [`mohr-coulomb-clausen/`](mohr-coulomb-clausen/) | Non-associated Mohr-Coulomb and Tresca with exact stress return, UMAT + VUMAT | originals: custom permission and three citations; adapter/tests: MIT | included; Abaqus verification pending |

## Which one do you need?

**None of them, to begin with.** Every example in this repository runs on the
Abaqus built-in Mohr-Coulomb or Drucker-Prager model, with no Fortran compiler
required. Learn the ALE and CEL mechanics first: the numerics of an adaptive
mesh do not care what the constitutive model is.

Then, roughly in order of effort:

1. **Clausen Mohr-Coulomb.** Same constitutive model as the built-in one, but
   with exact return to the edges and the apex of the yield surface. Matters for
   penetration problems, where many integration points near the tip sit exactly
   on an edge. No state variables and no initialisation, so it is the right first
   step away from the built-in model. Cite Clausen et al. (2006, 2007, 2015);
   the three papers and a `.bib` file are in
   [`mohr-coulomb-clausen/`](mohr-coulomb-clausen/).
2. **Hypoplasticity with intergranular strain.** A genuinely state-dependent
   model: critical state, dilatancy evolution, small-strain stiffness and cyclic
   memory. This is what you need for anything involving installation history,
   cyclic loading, or plug densification. It is also 5–20× the cost per
   integration point and needs a real calibration.

## Before you put any of them in a large model

Run `constitutive/single_element`. It pushes one element through
oedometric compression, drained triaxial compression and strain cycles, in both
Abaqus/Standard and Abaqus/Explicit, and compares the two. For a rate-independent
model they must agree; when they do not, the difference tells you which one is
wrong.

Debugging a UMAT inside a 50 000-element penetration analysis costs weeks. On one
element it costs seconds.

Getting `*Depvar` wrong, or leaving state variables uninitialised, produces
NaN. Abaqus/Explicit integrates NaN to the end of the step and writes a
complete ODB. Check the ODB is finite before trusting it.

## Adding your own

```
constitutive/<name>/
    <source>.f              the subroutine, plus everything it `include`s
    constants.txt           one documented calibration per file
    README.md               what it is; constant order; SDV layout; *Depvar count
    PROVENANCE.md           where it came from, under what licence
    LICENSE                 if not the repository default
```

Then run `constitutive/single_element` against it and commit the resulting stress paths as the
reference. That is what makes the next port checkable — and the next port is
usually yours, six months later, when you cannot remember what "right" looked
like.

## A note on calibrations

A calibration is not part of a model. The `constants.txt` files here are for
specific sands from specific research programmes, and they are included so the
examples run, not because they apply to your soil.

For a state-dependent model this is not a small approximation: the constants
encode the critical state line, the granular hardness and the small-strain
behaviour of one particular material. Recalibrate, or say clearly whose
calibration you used.
