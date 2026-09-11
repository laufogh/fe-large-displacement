# Brief 03 - example 04, ALE adaptive meshing

**Cost:** a few hours. **Needs:** brief 01 passing. **Run single-CPU.**

```bash
set FLD_NCPU=1
abaqus cae noGUI=examples/ex04_ale_indenter/model.py
```

This is the most important brief. The repository rests on ALE working and on
being able to *prove* it worked.

## The critical check

The script asserts, per case:

* case A (no ALE): the `.msg` reports **no** adaptive activity;
* cases B-E: the `.msg` reports a **nonzero** average percentage of nodes moved.

Case A is the control. If case A reports activity, the parser is wrong. If cases
B-E report none, either ALE is genuinely inert or the parser is wrong - and you
must distinguish those two, because from the script's side they look identical.

**Do it by hand for at least one case:** open `ex04_B.msg`, find a
`Summary Diagnostics for Adaptive Meshing` block, and **paste it verbatim into
your report.** The regexes in `fldlib/ale.py` (`_MSG_BLOCK`, `_PCT_MOVED`,
`_SWEEPS`) were written from a 2021 `.msg` and may not match yours. This is
item 8 in `KNOWN-UNCERTAINTIES.md` and the highest-value single thing here.

## Replication against docs/02-ale-adaptive-meshing.md

| Documented | Reproduced? |
|---|---|
| the verbatim `*Adaptive Mesh` lines (section 1.3) | |
| `frequency` and `mesh sweeps` omitted when equal to the defaults | |
| `initial mesh sweeps=5` written (CAE default 0 differs from solver default) | |
| `*Adaptive Mesh Controls` data line is `1., 0., 0.` | |
| case C (box) shows a much higher % nodes moved than case B (whole) | |
| case D (frequency=2) shows about 5x the diagnostic blocks of case B | |
| case E writes `smoothing objective=GRADED, curvature refinement=0.` | |
| ALE stays active under general contact | |

The last row matters. Abaqus documentation up to 2016 claimed general contact
makes all nodes nonadaptive; that was measured to be false in 2021. Confirm it
for your version.

## Also check

* Does ALE buy depth over example 01 case B? Compare the `depth_m` columns. If
  not, the box is probably in the wrong place - check the printed centroid
  extent against where the indenter actually goes.
* The `.dat` writes a `NONADAPTIVE NODES` section per adaptive domain. Record the
  counts.

## Report

The summary table, the verbatim `.msg` block, the replication table, and a depth
comparison against example 01.
