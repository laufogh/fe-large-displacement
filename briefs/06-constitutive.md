# Brief 06 - example 07, single-element constitutive check

**Cost:** minutes per case once it compiles; possibly a day getting it to
compile. **Needs:** brief 00 `abaqus verify -user_std` and `-user_exp` passing.

## Step 1 - run with no subroutine

```bash
abaqus cae noGUI=examples/ex07_umat_single_element/model.py
```

With nothing configured it falls back to the built-in Mohr-Coulomb model. This
verifies the harness - geometry, one element, load paths, history output,
implicit/explicit switching - independently of any Fortran.

Expected: all six cases complete. Extract S33 against LE33 for each and confirm
the implicit and explicit runs agree. If the built-in model's implicit and
explicit runs disagree, the harness is wrong and no subroutine result will mean
anything.

## Step 2 - run the hypoplastic model

```bash
set FLD_UMAT_IMPLICIT=<repo>\constitutive\hypoplasticity-staubach\call_implicit.f
set FLD_UMAT_EXPLICIT=<repo>\constitutive\hypoplasticity-staubach\call_explicit.f
set FLD_UMAT_CONSTANTS=<repo>\constitutive\hypoplasticity-staubach\constants.txt
set FLD_UMAT_NSDV=14
abaqus cae noGUI=examples/ex07_umat_single_element/model.py
```

**Determine the correct `FLD_UMAT_NSDV` and report it.** The number above is a
guess. Read the subroutine, count what it writes, and check whether the VUMAT
wrapper needs extra slots. Getting this wrong produces NaN or silent corruption,
not an error.

**Determine whether SDVINI is needed, per solver.** `call_implicit.f` includes
`sdvini.f`, which sets the initial void ratio from a Bauer profile, so the
implicit path should work with `*Initial Conditions, type=SOLUTION, USER` (the
default when `FLD_SDV_INIT` is blank). The explicit call file does **not**
include an SDVINI. Work out what the explicit path needs and record it - either
an explicit SDV table via `FLD_SDV_INIT`, or adding `sdvini.f` to the explicit
call file.

Then:

* confirm the finite check passes for every case - not optional, because
  Abaqus/Explicit integrates NaN to the end of the step and writes a complete ODB;
* overlay implicit and explicit stress paths for each load path;
* pay particular attention to `cyc`: unload-reload is where intergranular-strain
  ports usually diverge.

## Report

The determined `*Depvar` count and how you determined it, the SDVINI answer for
both solvers, the stress-path overlays, and the finite-check results.
