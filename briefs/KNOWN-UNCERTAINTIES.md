# Known uncertainties

Written by the author of the code, who did not have Abaqus available. This is the
list of things most likely to be wrong, ranked by how likely and how expensive.

Nothing below is a guess about *whether* the concept works — the ALE, section
control and parallel findings in `docs/` are all measured results from real runs.
These are uncertainties about the **new code in this repository** that
re-implements them.

---

## High likelihood — expect to fix these

### 1. `findAt` coordinates

Every `findAt` in `examples/common/indenter_model.py`, `ex06_cel_indenter` and
`ex08_suction_caisson` was written from the geometry on paper, not from a
running model.

The scripts **raise** when a pick returns nothing, rather than silently applying
a boundary condition to an empty region, so failures will be loud and the error
message names the coordinate. Fix the coordinate.

Watch particularly for:
* the soil block is translated by `(0, 0, -D)` **after** instancing, so all
  assembly-level picks use `z ∈ [-D, 0]` while part-level geometry is `z ∈ [0, D]`;
* the indenter is translated up by `1e-6` to give a small initial gap.

### 2. `mesh.ElemType` and section assignment argument names

`hourglassControl`, `secondOrderAccuracy`, `distortionControl` and the
`offsetType` / `thicknessAssignment` arguments on `SectionAssignment` vary
between Abaqus versions. If CAE raises on an unexpected keyword argument, drop
the argument rather than guessing a replacement, and note it in the report.

### 3. `ex08` caisson sketch and revolve

`build_caisson_part()` draws an r–z section and revolves it 90°. The centreline
assignment (`sk.assignCenterline(line=sk.geometry.findAt((0.0, 0.0)))`) is the
fragile part — `findAt` on sketch geometry needs a point *on* the construction
line, and `(0.0, 0.0)` may not be it. Expect to adjust.

The lid geometry (a disc from r=0 to R spanning z=0 to t_lid, joined to a skirt
annulus) may produce a self-intersecting or non-manifold profile. If the revolve
fails, simplify: draw the skirt and lid as two separate revolved parts and tie
them, or merge them in the assembly.

### 4. `ex08` `_soil_bcs` outer face picking

```python
arr = inst.faces[0:0]
for f in outer:
    arr = arr + inst.faces[f.index:f.index + 1]
```

This is the "stitch an array out of slices" idiom that `fldlib.ale.box_element_set`
needs for *elements*. Whether `faces` supports the same slicing and concatenation
is **not verified**. If it does not, build the region from
`getByBoundingCylinder` directly and accept that it may include the top and
bottom annular faces.

### 5. `ex08` `_refine_near_skirt`

`part.edges.getByBoundingCylinder(...)` followed by `seedEdgeBySize` is wrapped
in a try/except that prints a warning and continues with a uniform coarse seed —
the one deliberate exception to the "no silent fallback" rule, because a
too-coarse mesh is visible in the result whereas a missing boundary condition is
not. If it warns, the run is a mesh-convergence exercise and not a result.
Replace it with a proper partition into a fine inner cylinder and a coarse outer
annulus.

---

## Medium likelihood

### 6. `contact.friction_property` argument set

`NormalBehavior` and `TangentialBehavior` take a long list of arguments whose
names and defaults drift between versions. In particular `allowSeparation` on a
`HARD` normal behaviour, and `maximumElasticSlip=FRACTION` with `fraction=0.005`.

### 7. `steps.mass_scaling` tuple layout

The `massScaling` argument is a tuple of 12-element tuples whose layout is
documented but easy to get wrong:

```python
(SEMI_AUTOMATIC, region, THROUGHOUT_STEP, 0.0, target_dt, BELOW_MIN,
 1, 0, 0.0, 0.0, 0, None)
```

Verify against the deck: the keyword should come out as
`*Variable Mass Scaling, dt=..., type=below min, frequency=1`. If the tuple is
wrong CAE may accept it and write nothing.

### 8. `.msg` diagnostic parsing

`fldlib.ale.read_msg_activity()` matches:

```
Summary Diagnostics for Adaptive Meshing
Avg. pctg. of Nodes Moved
Mesh Sweeps
```

The exact wording and spacing came from a 2021 `.msg`. **Paste a real block into
the report** so the regexes can be checked against it. This matters more than it
looks: the whole "was ALE actually active" check rests on it, and a regex that
never matches produces a false "inert" report.

### 9. `jobs.status()` `.sta` parsing

The last-increment line is parsed as `fields[0]` = increment, `fields[3]` = step
time. Verify against a real `.sta` from both Standard and Explicit; the column
layouts differ.

### 10. `*Section Controls` injection anchor

`inpedit.inject_section_controls` anchors on the `*Preprint` line and requires the
soil `*Solid Section` line to match `material=SoilMat` exactly once. Both were
tested against a synthetic deck locally and pass. Confirm against a real one —
in particular whether CAE writes `*Solid Section, elset=..., material=SoilMat`
with that exact spacing.

---

## Lower likelihood, but check

### 11. `cel.eulerian_section` instance key convention

`model.EulerianSection(name=..., data={'soilmat-1': 'SoilMat'})`. The key is the
Eulerian material instance name. The lowercase-with-`-1` convention is what CAE
generates interactively; confirm it, because the EVF output is keyed off it.

### 12. `inpedit.inject_extra_ale_domains` placement

Extra `*Adaptive Mesh` lines are injected immediately after the last one CAE
wrote, i.e. in step data. Confirm the solver accepts several in one step —
the source study did exactly this, so it should, but confirm the generated deck
matches the verbatim lines in `docs/03-ale-multi-region-parallel.md`.

### 13. `ex08` `model.boundaryConditions['Jacking'].deactivate('Suction')`

Deactivating a velocity BC in a later step so the caisson responds to a force
instead. Verify the deck shows `*Boundary, op=NEW` (or the BC simply absent) in
the Suction step, and — more importantly — verify the caisson does not inherit a
zero velocity and stop dead.

### 14. `materials.write_sdv_initial_conditions` elset name

Assembly-level set names are written differently from instance-level ones. The
function is passed a bare set name; confirm that is what `*Initial Conditions,
type=SOLUTION` wants, or whether it needs `INSTANCE.SETNAME`.

---

## Things that are verified

So you do not waste time on them:

* `fldlib.config` — parameter handling, env overrides, type casting, choice
  validation, the unknown-variable warning. Unit-tested locally.
* `fldlib.inpedit` — section control injection, diagnostics injection,
  `insert_before` / `insert_after`, and the `report.InpCheck` machinery. Tested
  against a synthetic deck locally; the resulting deck was inspected by eye.
* The `docs/02`, `docs/03` and `docs/04` findings. Those are transcribed from
  real runs on Abaqus 2021 and the numbers in them are measurements. If your runs
  contradict them, that is a genuine finding and belongs in the report.
