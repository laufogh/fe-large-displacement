# Example 01 - where a Lagrangian mesh gives up

The motivation for everything else. Watch an ordinary analysis fail, and confirm the failure depth is a property of the mesh rather than of the soil.

```bash
set FLD_WORKDIR=C:\abq\run
abaqus cae noGUI=examples/ex01_lagrangian_limit/model.py
```

Add `set FLD_SUBMIT=0` to build and verify the decks without solving.

## Cases

| id | configuration |
|---|---|
| `A` | implicit Abaqus/Standard, nlgeom, automatic stabilisation |
| `B` | explicit Abaqus/Explicit, Lagrangian, seed 0.010 m |
| `C` | as B with a seed of 0.020 m |

Run a subset with `set FLD_CASES=A,C`.

## What to expect

**Every case aborts.** That is the intended outcome and the runner reports it as a successful case. B and C must stop at *different* depths: if they do not, the coarse seed did not take.

## What to look at

* `_summary.csv` - depth reached per case
* the abort message printed for each case
* the deformed elements under the indenter corner in the ODB

## Reading

* [00-why-large-displacement.md](../../docs/00-why-large-displacement.md)

The full explanation is the module docstring at the top of
[`model.py`](model.py) - it is written to be read.
