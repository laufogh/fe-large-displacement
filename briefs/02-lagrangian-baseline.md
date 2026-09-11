# Brief 02 - examples 01 to 03, the Lagrangian baseline

**Cost:** a few hours of solve time. **Needs:** brief 01 passing.

## Example 01 - the Lagrangian limit

```bash
abaqus cae noGUI=examples/ex01_lagrangian_limit/model.py
```

**Expected outcome: every case aborts.** That is the point. The runner reports an
aborted job as a *successful case* - the case ran, the job failed, and the
failure is the data.

Check:

* case A (implicit) stops on convergence - the increment size collapsing towards
  `minInc` in the `.sta`, and `Too many attempts made for this increment`;
* cases B and C (explicit) stop on `Excessive distortion of element number N` or
  `The ratio of deformation speed to wave speed exceeds 1.0000`;
* **B and C reach different depths.** If they reach the same depth, either the
  coarse seed did not take (check the element count in the log) or something
  other than distortion is limiting the run.

If any case completes to full depth, something is wrong - most likely the
indenter never made contact, or `ind_depth` is being applied at the wrong scale.
Check the RP displacement history.

## Example 02 - quasi-static or not

```bash
abaqus cae noGUI=examples/ex02_quasi_static/model.py
```

Expected: `ALLKE/ALLIE` rises from case A to case C, and cases C and E are graded
`not quasi-static`. If case A is already above 5 %, the default rate is too high
for this mesh - report the numbers and suggest a rate that passes.

Verify item 7 of `KNOWN-UNCERTAINTIES.md` here: confirm the mass-scaling keyword
appears in the D and E decks and that the `.sta` reports added mass.

## Example 03 - section controls

```bash
abaqus cae noGUI=examples/ex03_section_controls/model.py
```

This is a **replication** of a measured study. `docs/04-section-controls.md`
records what happened on Abaqus 2021. Fill this in:

| Documented finding | Reproduced? |
|---|---|
| A aborts on distortion | |
| B, C, D reach the same depth as each other | |
| B reaches materially further than A | |
| length ratio (C vs D) changes nothing measurable | |
| E cuts ALLAE/ALLIE from ~16.5 % to ~3.8 % | |
| **F aborts much earlier than B/C/D** | |
| ALLDC is ~0 in every case | |

The depths in the doc came from a specific calibration (indenter half-width
0.0225 m, v = 1 m/s, target 0.15 m), which is the default here. If the absolute
depths differ but the ordering and relative behaviour hold, that is a pass -
report both.

If F does **not** abort earlier than B, that contradicts a documented
measurement. Report it prominently with version numbers; it may be a behaviour
change between Abaqus releases, which belongs in the doc.

## Report

The three summary tables plus the replication table filled in.
