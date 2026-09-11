# Brief 07 - example 08, suction caisson installation

**Cost:** substantial. **Needs:** briefs 01, 03 and 05 passing.

The capstone, and the most likely to need real work. See items 3, 4, 5 and 13 in
`KNOWN-UNCERTAINTIES.md` - the caisson geometry and the outer-face picking are
the least-verified code in the repository.

## Step 1 - geometry only

```bash
set FLD_SUBMIT=0
abaqus cae noGUI=examples/ex08_suction_caisson/model.py
```

Get the parts built and meshed before anything else. Then **open the model in CAE
and look at it.** This is one case where eyes beat assertions: check that the
skirt is an annulus of the right thickness, that the lid is attached, that the
quarter symmetry is on the right planes, and that the soil mesh really is refined
near the skirt - the refinement is wrapped in a try/except and will warn rather
than fail.

## Step 2 - ALE method, case J

```bash
set FLD_METHOD=ale
set FLD_CASES=J
abaqus cae noGUI=examples/ex08_suction_caisson/model.py
```

Jacked penetration to full depth. Check:

* both adaptive regions are in the deck and both report activity in the `.msg` -
  the plug region is injected rather than defined through the API, so it is the
  more likely of the two to be inert;
* the overlap check did not fire (it raises if it does);
* `ALLKE/ALLIE` - the default 0.2 m/s is scaled well above reality and may fail
  the test. If it does, report the ratio and the rate at which it passes.

Extract the installation curve:

```bash
abaqus python lib/postproc/history.py ex08_ale_J.odb CAISSONRP curve_J.csv
```

**Sanity-check the magnitude.** For a 0.1 m radius caisson with a 0.15 m skirt in
the default Mohr-Coulomb sand, total resistance at full penetration should be of
the order of a few hundred newtons on the quarter model. Kilonewtons or
millinewtons means something is wrong by orders of magnitude, and that is worth
finding before anything else.

## Step 3 - suction cases

```bash
set FLD_CASES=S,S2
```

The critical check is item 13: **does the caisson keep moving in the suction
step?** The jacking velocity BC is deactivated and replaced by a concentrated
force. If the caisson stops dead, the deactivation did not work and the reference
point is still velocity-constrained to zero.

Plot depth against time. Under a fixed suction the rate is an outcome, and S2
should penetrate faster than S.

## Step 4 - CEL method

```bash
set FLD_METHOD=cel
set FLD_CASES=J
```

Expect this to be expensive and quite possibly under-resolved: the skirt wall is
2 mm and the default `seed_fine` is 4 mm, so **the wall is thinner than one
element**. `docs/05-cel.md` says three elements across the wall. Either refine
drastically and report the cost, or report that the CEL caisson needs a
partitioned mesh and leave it as a stated limitation.

It is entirely honest to conclude that CEL for a thin-walled caisson needs more
than a teaching example can carry. If that is the conclusion, say so, and say
what it would take.

## Step 5 - the physics caveat

The model applies suction as a force on the lid and does **not** model seepage.
Confirm the warning appears in the run log, and confirm
`docs/07-suction-caisson.md` accurately describes what the script does. If the
script and the doc drift apart, the doc is the one people will believe.

## Report

Geometry screenshots, the case J installation curve with a magnitude sanity
check, the suction-phase depth-time plots, ALE activity for both regions, and a
clear recommendation on whether the CEL variant is worth keeping.
