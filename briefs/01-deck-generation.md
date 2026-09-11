# Brief 01 - build every deck without solving

**Cost:** 15-30 minutes. **Needs:** Abaqus/CAE.
**Do this before any brief that costs machine time.**

`FLD_SUBMIT=0` runs the whole pipeline - build the model, write the `.inp`,
apply the keyword injections, run every `InpCheck` assertion - and stops before
submitting. It exercises essentially all of the Abaqus API surface in this
repository for a few minutes of CPU.

Most of the errors in `KNOWN-UNCERTAINTIES.md` will surface here.

## Do

```bash
set FLD_WORKDIR=C:\abq\run
set FLD_SUBMIT=0

abaqus cae noGUI=examples/ex01_lagrangian_limit/model.py
abaqus cae noGUI=examples/ex02_quasi_static/model.py
abaqus cae noGUI=examples/ex03_section_controls/model.py
abaqus cae noGUI=examples/ex04_ale_indenter/model.py
abaqus cae noGUI=examples/ex05_ale_parallel/model.py
abaqus cae noGUI=examples/ex06_cel_indenter/model.py
abaqus cae noGUI=examples/ex07_umat_single_element/model.py
abaqus cae noGUI=examples/ex08_suction_caisson/model.py
```

Each study isolates failures per case, so one invocation tells you about every
broken case in that study rather than only the first.

## Then read the decks

For each study, open the generated `.inp` and confirm by eye:

| Study | Look for |
|---|---|
| ex01 | `*Static` vs `*Dynamic, Explicit`; `nlgeom=YES`; no `*Adaptive Mesh` |
| ex02 | `*Variable Mass Scaling` in D and E and absent in A/B/C; `ALLKE` and `ALLIE` in history output |
| ex03 | `*Section Controls` immediately after `*Preprint`; `controls=SC-Soil` on the soil `*Solid Section`; the `*Amplitude ... SMOOTH STEP` block intact |
| ex04 | the verbatim `*Adaptive Mesh` lines - compare against `docs/02-ale-adaptive-meshing.md` section 1.3 |
| ex05 | one `*Adaptive Mesh Controls` and N `*Adaptive Mesh` domain lines |
| ex06 | `*Eulerian Section`; `EC3D8R`; `*Initial Conditions, type=VOLUME FRACTION`; `*Contact` |
| ex07 | exactly one element; `*User Material` + `*Depvar` + `*Initial Conditions, type=SOLUTION` when a subroutine is configured |
| ex08 | two `*Adaptive Mesh` lines (ALE) or `*Eulerian Section` (CEL); `*Step, name=Suction`; `*Cload` |

The ex04 comparison against the documented verbatim lines is the most valuable
check in this brief: those lines are measured ground truth from a real run.

## Expected outcome

PASS WITH FIXES. Expect several `findAt` corrections and possibly one or two
argument-name changes. See `KNOWN-UNCERTAINTIES.md` items 1-5.

## Report

The fixes table, and for ex04 the verbatim `*Adaptive Mesh` lines from your decks
alongside the documented ones.
