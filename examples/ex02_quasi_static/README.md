# Example 02 - making an explicit run honestly quasi-static

You are using a dynamic solver for a static problem. This is how you find out whether you got away with it.

```bash
set FLD_WORKDIR=C:\abq\run
abaqus cae noGUI=examples/ex02_quasi_static/model.py
```

Add `set FLD_SUBMIT=0` to build and verify the decks without solving.

## Cases

| id | configuration |
|---|---|
| `A` | v = 0.25 m/s, no mass scaling (reference) |
| `B` | v = 1.0 m/s, no mass scaling |
| `C` | v = 4.0 m/s, no mass scaling |
| `D` | v = 1.0 m/s, semi-automatic mass scaling |
| `E` | v = 4.0 m/s, semi-automatic mass scaling |

Run a subset with `set FLD_CASES=A,C`.

## What to expect

`ALLKE/ALLIE` rises from A to C. Cases C and E should be graded `not quasi-static`. Read the **peak**, not the final value: a run that spiked to 30 % during the ramp has already corrupted the early part of the curve.

## What to look at

* the energy table printed per case
* the added mass reported in the `.sta` for D and E
* `ALLAE/ALLIE` - hourglass energy, which example 03 attacks directly

## Reading

* [01-explicit-quasi-static.md](../../docs/01-explicit-quasi-static.md)

The full explanation is the module docstring at the top of
[`model.py`](model.py) - it is written to be read.
