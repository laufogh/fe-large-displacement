# Example 06 - Coupled Eulerian-Lagrangian

The same problem, third formulation. Material flows through a fixed mesh, so nothing ever distorts - and the free surface goes diffuse.

```bash
set FLD_WORKDIR=C:\abq\run
abaqus cae noGUI=examples/ex06_cel_indenter/model.py
```

Add `set FLD_SUBMIT=0` to build and verify the decks without solving.

## Cases

| id | configuration |
|---|---|
| `A` | no void space above the soil - the mistake, and what it costs |
| `B` | void = 0.5x the penetration depth |
| `C` | as B with half the element size |

Run a subset with `set FLD_CASES=A,C`.

## What to expect

No case aborts on distortion - Eulerian elements never deform. Case A gives a higher resistance than B at the same depth, for the wrong reason: heave had nowhere to go. Case C shows a visibly sharper surface for four times the element count.

## What to look at

* `EVF` plotted on the Eulerian instance - the surface is a band, not a line
* material piling against the top of the domain in case A
* the resistance curves against examples 01, 03 and 04 over the depth range all four reached

## Note

The mesh must be structured hex (`EC3D8R`). Refinement comes from partitioning into structured regions, not from local seeding. For a thin-walled structure you need about three elements across the wall or the soil merges through it.

## Reading

* [05-cel.md](../../docs/05-cel.md)

The full explanation is the module docstring at the top of
[`model.py`](model.py) - it is written to be read.
