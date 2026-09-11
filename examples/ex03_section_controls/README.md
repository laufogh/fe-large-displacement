# Example 03 - section controls, the cheapest thing that buys you depth

Distortion control and enhanced hourglass control cost nothing and require no change to the model. One combination of them is a trap.

```bash
set FLD_WORKDIR=C:\abq\run
abaqus cae noGUI=examples/ex03_section_controls/model.py
```

Add `set FLD_SUBMIT=0` to build and verify the decks without solving.

## Cases

| id | configuration |
|---|---|
| `A` | baseline, no `*Section Controls` - aborts |
| `B` | `distortion control=YES`, default length ratio |
| `C` | `distortion control=YES, length ratio=0.05` |
| `D` | `distortion control=YES, length ratio=0.20` |
| `E` | `hourglass=enhanced` |
| `F` | `hourglass=enhanced, distortion control=YES` - the trap |

Run a subset with `set FLD_CASES=A,C`.

## What to expect

B, C and D reach the same depth as each other and materially further than A - `length ratio` changes nothing measurable across a 4x range. E cuts `ALLAE/ALLIE` from ~16.5 % to ~3.8 % without preventing the abort. **F aborts far earlier than B, C or D**: combining enhanced hourglass with distortion control negates the rescue.

## What to look at

* the depth column, against example 01 and example 04
* `ALLAE/ALLIE` for A versus E
* `ALLDC` - it should be essentially zero in every case

## Note

`mdb.models[...].SectionControl` does not exist in Abaqus 2021, so the keyword is injected into the written deck. Placement is mandatory: immediately after `*Preprint`. Mid-file placement corrupts the parse of the later `SMOOTH STEP` amplitude, with an error that points at the amplitude and never mentions section controls.

## Reading

* [04-section-controls.md](../../docs/04-section-controls.md)

The full explanation is the module docstring at the top of
[`model.py`](model.py) - it is written to be read.
