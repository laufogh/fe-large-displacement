# Single-element constitutive check

Verify a UMAT/VUMAT on one element, in seconds, before putting it in a 50 000-element analysis where debugging it costs weeks.

```bash
set FLD_WORKDIR=C:\abq\run
abaqus cae noGUI=constitutive/single_element/model.py
```

Add `set FLD_SUBMIT=0` to build and verify the decks without solving.

## Cases

| id | configuration |
|---|---|
| `oedo` | one-dimensional compression |
| `triax` | drained triaxial compression at constant cell pressure |
| `cyc` | strain cycles - unload-reload and small-strain stiffness |

Run a subset with, for example, `set FLD_CASES=triax_implicit,triax_explicit`.

Using the Clausen Mohr-Coulomb model requires citing Clausen et al. (2006, 2007,
2015). See [`mohr-coulomb-clausen/README.md`](../mohr-coulomb-clausen/README.md).

For the included Clausen Mohr-Coulomb implementation, use the original UMAT
for Standard and the adapter bundle for Explicit:

```bat
set FLD_UMAT_IMPLICIT=<repo>\constitutive\mohr-coulomb-clausen\MohrCoulombAbaqus.for
set FLD_UMAT_EXPLICIT=<repo>\constitutive\mohr-coulomb-clausen\call_mc.f
set FLD_UMAT_CONSTANTS=<repo>\constitutive\mohr-coulomb-clausen\constants.txt
set FLD_UMAT_NSDV=1
set FLD_SDV_INIT=0
```

`FLD_SDV_INIT=0` is intentional: `SDV1` is a return-region diagnostic and this
source bundle does not contain an `SDVINI` routine.

## What to expect

Each path runs in both Abaqus/Standard (UMAT) and Abaqus/Explicit (VUMAT). For a rate-independent model the two stress paths must lie on top of each other. With no subroutine configured it falls back to the built-in Mohr-Coulomb model, which still exercises the whole harness.

## What to look at

* S33 against LE33, implicit and explicit overlaid, per path
* the `finite` column - Abaqus/Explicit integrates NaN happily to the end
* the `cyc` path especially: unload-reload is where ports diverge

## Note

Configure with `FLD_UMAT_IMPLICIT`, `FLD_UMAT_EXPLICIT`, `FLD_UMAT_CONSTANTS` and `FLD_UMAT_NSDV`. Getting `*Depvar` wrong, or leaving state variables uninitialised, produces NaN or silent corruption - never an error.

## Reading

* [06-constitutive-models.md](../../docs/06-constitutive-models.md)
* [README.md](../README.md)

The full explanation is the module docstring at the top of
[`model.py`](model.py) - it is written to be read.
