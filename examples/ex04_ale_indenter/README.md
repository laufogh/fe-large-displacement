# Example 04 - ALE adaptive meshing

Defining it, restricting it, controlling it, and - the part everyone skips - proving it actually ran.

```bash
set FLD_WORKDIR=C:\abq\run
abaqus cae noGUI=examples/ex04_ale_indenter/model.py
```

Add `set FLD_SUBMIT=0` to build and verify the decks without solving.

## Cases

| id | configuration |
|---|---|
| `A` | no ALE (reference) |
| `B` | ALE over the whole soil part, default controls |
| `C` | ALE over a restricted element set around the indenter **- use this in production** |
| `D` | as B with `frequency=2` |
| `E` | as B with `smoothing objective=GRADED, curvature refinement=0` |

Run a subset with `set FLD_CASES=A,C`.

## What to expect

Cases B-E reach further than A. Case C shows a much higher percentage of nodes moved than B, simply because the box contains only the elements that need moving.

## What to look at

* the `pct_moved` column - this is the proof ALE was active
* the verbatim `*Adaptive Mesh` lines printed for each case
* the printed centroid extent of the box element set

## Note

**A defined adaptive mesh domain that never sweeps produces no error, no warning and a normal-looking ODB.** The only evidence is a `Summary Diagnostics for Adaptive Meshing` block in the `.msg`, and only if you injected `*Diagnostics`. This example asserts activity for B-E and asserts *absence* for A, which is what makes the check trustworthy. Copy this habit.

## Reading

* [02-ale-adaptive-meshing.md](../../docs/02-ale-adaptive-meshing.md)

The full explanation is the module docstring at the top of
[`model.py`](model.py) - it is written to be read.
