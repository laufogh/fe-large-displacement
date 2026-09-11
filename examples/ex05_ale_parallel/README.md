# Example 05 - ALE and parallel decomposition

Why one large adaptive region is the wrong shape, and why four small ones cost nothing. Run this on the compute machine.

```bash
set FLD_WORKDIR=C:\abq\run
abaqus cae noGUI=examples/ex05_ale_parallel/model.py
```

Add `set FLD_SUBMIT=0` to build and verify the decks without solving.

## Cases

| id | configuration |
|---|---|
| `A` | no ALE (balanced reference) |
| `B` | one adaptive region |
| `C` | two non-adjacent regions |
| `D` | four non-adjacent regions **- best load balance** |
| `E` | two adjacent regions sharing a face |

Run a subset with `set FLD_CASES=A,C`.

## What to expect

On 15 CPUs: B inflates one domain to weight ~15.1 against a balanced 6.67. C inflates two domains to ~8.2 each. **D is perfectly balanced** with the same total adaptive element count. E is byte-for-byte identical to B, because regions sharing a face are one region.

## What to look at

* the packager decomposition weights in the `.sta`
* which `.msg.N` each region reported to
* the NONADAPTIVE node counts - the price of fragmenting

## Note

Abaqus/CAE holds only **one** `AdaptiveMeshDomain` per step - a second call silently replaces the first. The solver has no such limit, so the first domain is defined through the API and the rest are injected as extra `*Adaptive Mesh` lines.

## Reading

* [03-ale-multi-region-parallel.md](../../docs/03-ale-multi-region-parallel.md)

The full explanation is the module docstring at the top of
[`model.py`](model.py) - it is written to be read.
