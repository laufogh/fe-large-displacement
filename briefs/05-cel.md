# Brief 05 - example 06, Coupled Eulerian-Lagrangian

**Cost:** several hours; CEL is expensive and case C quadruples the element
count. **Needs:** brief 01 passing.

```bash
abaqus cae noGUI=examples/ex06_cel_indenter/model.py
```

Consider `FLD_CASES=A,B` first, adding C once A and B work.

## What to verify

1. **The deck is genuinely Eulerian.** `*Eulerian Section`, `EC3D8R`,
   `*Initial Conditions, type=VOLUME FRACTION`. Confirm the Eulerian material
   instance key in the section matches what the EVF output uses - item 11 in
   `KNOWN-UNCERTAINTIES.md`.

2. **No case aborts on distortion.** CEL elements never deform. An abort on
   excessive distortion means something is not actually Eulerian. An abort for
   another reason (contact, time increment) is a different problem.

3. **Case A under-predicts.** With no void space, heave has nowhere to go, and
   the expectation is that A gives a *higher* resistance than B at the same depth
   for the wrong reason. Extract and compare:

   ```bash
   abaqus python lib/postproc/history.py ex06_A.odb INDRP a.csv
   abaqus python lib/postproc/history.py ex06_B.odb INDRP b.csv
   ```

   If A and B agree, either the void genuinely was not needed at this depth
   (plausible - the indenter is shallow) or `void_mult` is not taking effect.
   Check the element counts in the log.

4. **Mass conservation.** Sum EVF over the domain at the first and last frame.
   Material should not appear or disappear. Loss means it left through a boundary
   that was meant to be closed.

5. **Cross-formulation agreement.** The real test. Over the depth range that
   example 01 case B and example 04 case C both reached, do the CEL resistance
   curves agree? Plot all three. Disagreement means at least two of the three are
   wrong, and finding out which is worth more than any individual run.

## Report

The summary table, the A-vs-B resistance comparison, the mass-conservation
numbers, and the three-formulation overlay.
