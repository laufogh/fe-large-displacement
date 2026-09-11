# Example 08 - suction caisson installation

The capstone. Quarter-symmetry lab-scale caisson, jacked phase then suction-assisted phase, in ALE or CEL.

```bash
set FLD_WORKDIR=C:\abq\run
abaqus cae noGUI=examples/ex08_suction_caisson/model.py
```

Add `set FLD_SUBMIT=0` to build and verify the decks without solving.

## Cases

| id | configuration |
|---|---|
| `J` | jacked to full depth - the reference resistance |
| `S` | jacked to `jack_depth`, then suction |
| `S2` | as S with twice the suction |

Run a subset with `set FLD_CASES=A,C`.

## What to expect

Case J gives the installation resistance curve. In S and S2 the jacking velocity BC is released and the caisson responds to the suction force, so the **penetration rate is an outcome, not an input** - which is the quantity a designer actually wants.

## What to look at

* resistance against depth for J - the reference every suction case is read against
* depth against time for S and S2
* plug heave
* `ALLKE/ALLIE` - the default rate is scaled well above reality

## Note

**This model applies suction as a downward force on the lid and does NOT model the seepage gradient through the soil plug.** The upward flow that loosens the plug and cuts tip resistance is the mechanism that makes suction installation work in dense sand, and it is absent. The model therefore over-predicts the required suction and cannot predict piping or plug failure at all. See the doc for what it would take to fix.

## Reading

* [07-suction-caisson.md](../../docs/07-suction-caisson.md)

The full explanation is the module docstring at the top of
[`model.py`](model.py) - it is written to be read.
