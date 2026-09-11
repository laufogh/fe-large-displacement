# ALE adaptive mesh in Abaqus/Explicit — implementation verification findings

> **Provenance.** These are measured results, not a summary of the Abaqus
> manual. Every number below came from jobs that were actually run and whose
> `.inp`, `.sta`, `.msg` and `.dat` files were read. Where the documentation and
> the solver disagreed, the solver won and the disagreement is recorded.
> Verified on **Abaqus 2021**, Windows, `explicitPrecision=DOUBLE_PLUS_PACK`.
> Re-run it yourself with the companion example; if your Abaqus version behaves
> differently, that is worth a pull request.


Verified 2026-08-25 on **Abaqus 2021** (Windows, `explicitPrecision=DOUBLE_PLUS_PACK`,
`nodalOutputPrecision=FULL`, serial single-domain). All job artifacts in
`$FLD_WORKDIR`; companion script `examples/ex04_ale_indenter/model.py` runs
all five cases A–E in one invocation.

This is an **implementation verification only**: nothing here assesses whether ALE changes the
load–displacement response.

---

## Verdict (read this first)

- Defining, restricting and controlling an ALE adaptive mesh domain works exactly as documented.
  There is **no compatibility blocker** for the production model from any of the four features
  under test (rigid bodies, general contact, Standard→Explicit import, VUMAT SDVs).
- The **restricted element-set domain (case C) is the configuration to port into `the production model`**;
  a ready-to-adapt code block is in §7.
- ALE was **proven ACTIVE in the runs**, not merely defined: `.msg` per-increment diagnostics
  show mesh sweeps with a nonzero percentage of nodes moved in every ALE case (§4).
- Two documentation landmines found (report before they bite you):
  1. The `*ADAPTIVE MESH` keyword reference says the default `MESH SWEEPS` is **5**, while the
     ALE guide section and the actual CAE/solver default is **1** (§3.1).
  2. Older docs (2016 and earlier) state "All nodes in a general contact domain are
     nonadaptive." That statement is **not observed in Abaqus 2021** (ALE stayed active, the
     automatic NA node set contained 1 node) and was **removed from the current docs** (§Compat b).

---

## 1. Defining an adaptive mesh domain — exact keyword and CAE API call

### 1.1 Keyword (`*ADAPTIVE MESH`)

Step data, inside a `*DYNAMIC, EXPLICIT` step, geometrically nonlinear:

```
*Adaptive Mesh, elset=elset_name, controls=controls_name, frequency=10, mesh sweeps=1, op=NEW
```

Only `ELSET` is required. The domain can contain **only first-order reduced-integration solid
elements** (C3D8R etc.); all other element types are nonadaptive.

### 1.2 CAE API — the argument names actually used (verified against the generated `.inp`)

```python
# Model data: controls definition (one per model; several domains can share it)
mdb.models[name].AdaptiveMeshControl(
    name='ALE_BC',
    smoothingPriority=UNIFORM,      # 'smoothingPriority' maps to *Adaptive Mesh Controls SMOOTHING OBJECTIVE
    curvatureRefinement=1.0,        # maps to CURVATURE REFINEMENT (default 1.0)
    )                               # all other controls left at default

# Step data: the adaptive mesh domain
mdb.models[name].steps[stepName].AdaptiveMeshDomain(
    region=region,                  # a Set OR a Region; see §2
    controls='ALE_BC',
    frequency=10,                   # *Adaptive Mesh FREQUENCY
    meshSweeps=1,                   # *Adaptive Mesh MESH SWEEPS
    initialMeshSweeps=5,            # *Adaptive Mesh INITIAL MESH SWEEPS
    )
```

Abaqus/CAE supports only **one** adaptive mesh domain per step. `op=NEW` is written
automatically when the domain is first defined in a step.

### 1.3 Generated `.inp` verbatim

From `alemver_B.inp` (case B — whole soil domain, default controls), step data:

```text
*Boundary, amplitude=Ramp, type=VELOCITY
IndRP, 1, 1
IndRP, 2, 2
IndRP, 3, 3, -1.
*Adaptive Mesh Controls, name=ALE_BC
1., 0., 0.
*Adaptive Mesh, elset=_PickedSet13, controls=ALE_BC, initial mesh sweeps=5, op=NEW
```

From `alemver_C.inp` (case C — restricted box element set, default controls):

```text
*Boundary, amplitude=Ramp, type=VELOCITY
IndRP, 1, 1
IndRP, 2, 2
IndRP, 3, 3, -1.
*Adaptive Mesh Controls, name=ALE_BC
1., 0., 0.
*Adaptive Mesh, elset=ALE_Box, controls=ALE_BC, initial mesh sweeps=5, op=NEW
```

Notes on what is (and is not) written:

- `*Adaptive Mesh Controls, name=ALE_BC` has no parameters (all controls at default — itself
  proof the defaults are UNIFORM objective, curvature refinement 1.0, etc.) and the data line
  is exactly `1., 0., 0.` (volume / Laplacian / equipotential weights — **3 weights for both
  smoothing objectives**; the keyword reference documents no 4th "graded" weight).
- `frequency=10` and `mesh sweeps=1` are **omitted** because they equal the CAE/solver
  defaults (so "written=False" in the verification logs is expected, not a failure).
- `initial mesh sweeps=5` is written because it differs from the CAE default of 0 (CAE default
  differs from the documented solver default of 5 for UNIFORM — see §3.1).
- `op=NEW` is written by CAE on first definition.

### 1.4 The elset the domain points to

For a whole-part region (case B) CAE writes a generated internal set in model data:

```text
*Elset, elset=_PickedSet13, internal, instance=SoilInst, generate
1, 12000, 1
```

For a user element set (case C) it writes your named set; because a box is non-contiguous in
element numbering it is written as an explicit list, not `generate`:

```text
*Elset, elset=ALE_Box, instance=SoilInst
3001, 3002, 3003, ..., 11993
```

---

## 2. Restricting the domain to an element set (case C — the production configuration)

Three steps: **build the element set**, **reference it** in `AdaptiveMeshDomain`, and the `.inp`
shows the set name on the `*Adaptive Mesh` line.

1. **Build the set.** The set must live at the **assembly** level and its elements must come
   from the part instance. The box filter in the script selects every soil element whose
   node-average (centroid) coordinates lie inside the box:

   ```python
   BOX = dict(xmin=-0.08, xmax=0.08, ymin=0.0, ymax=0.20, zmin=0.0, zmax=0.10)
   n = make_box_set(a, soilInst, 'ALE_Box', BOX)   # -> 1600 of 12000 soil elements
   ```

   **Critical kernel gotcha (verified empirically):** `Set(elements=...)` on a dependent
   instance **rejects a Python `list`/`tuple` of `Element` objects** with
   `AbaqusException: Feature creation failed`. It accepts only the `ElementArray` itself or
   slices of it. The workaround is to collect the selected indices and stitch the maximal runs
   of consecutive indices back into an `ElementArray` by concatenating slices, then pass that
   to `assembly.Set(...)` — see `make_box_set()` in the script (this exact function is ready to
   lift into `the production model`).

2. **Reference it.** Pass the set to the domain API: `region = a.sets['ALE_Box']` and then
   `push.AdaptiveMeshDomain(region=region, ...)`. A `regionToolset.Region(cells=...)` works for
   the whole-part case; a named assembly `Set` works for the restricted case.

3. **`.inp` appearance.** The domain line references the set by name:
   `*Adaptive Mesh, elset=ALE_Box, controls=ALE_BC, ...` (§1.3). The verification script asserts
   the domain line references `elset=ALE_Box` **and not** the whole-instance set.

---

## 3. Every control parameter, its default, and what measurably changed ALE activity

### 3.1 `*Adaptive Mesh` (domain) parameters

| Parameter | Default | Effect |
|---|---|---|
| `ELSET` | required | element set defining the domain |
| `CONTROLS` | none | name of the `*Adaptive Mesh Controls` definition |
| `OP` | `MOD` | modify existing or define new domain; `NEW` removes all existing domains first |
| `FREQUENCY` | **10** (default **1** if a spatial mesh constraint or Eulerian boundary region is present, or for acoustic domains) | number of increments between adaptive-mesh increments |
| `MESH SWEEPS` | **contradictory in docs**: keyword reference says 5; ALE guide says 1 | sweeps per adaptive-mesh increment |
| `INITIAL MESH SWEEPS` | **5** for UNIFORM objective, **2** for GRADED (Explicit only) | sweeps at the start of the first step the domain is active |

**Documentation landmine — `MESH SWEEPS` default.** The 2025 `*ADAPTIVE MESH` keyword
reference states "The default number of mesh sweeps is 5", while the ALE guide section
"ALE Adaptive Meshing and Remapping in Abaqus/Explicit" states "The default number of mesh
sweeps is one." The **effective** default, confirmed three ways on Abaqus 2021: the CAE API
omits `mesh sweeps=1` from the `.inp` (so CAE's default is 1), and the `.msg` diagnostics show
`Mesh Sweeps: 1` in every regular adaptive-mesh increment. Treat **1** as the real default.

### 3.2 `*Adaptive Mesh Controls` parameters

All documented defaults from the current keyword reference (`*ADAPTIVE MESH CONTROLS`):

| Parameter (Explicit) | Default | Effect |
|---|---|---|
| `SMOOTHING OBJECTIVE` | `UNIFORM` (default if no Eulerian boundary regions) | `UNIFORM` minimises distortion/aspect ratios, diffuses initial gradation; `GRADED` preserves initial gradation, for low-to-moderate deformation |
| `CURVATURE REFINEMENT` | `1.0` | solution-dependence weight αC; concentrates refinement near evolving boundary curvature |
| `ADVECTION` | `SECOND ORDER` | advection algorithm for remapping solution variables (first order = donor-cell, diffusive) |
| `MOMENTUM ADVECTION` | `ELEMENT CENTER PROJECTION` | momentum advection method (half-index shift = costlier, better dispersion) |
| `GEOMETRIC ENHANCEMENT` | `YES` (Explicit) | geometry-enhanced smoothing based on evolving element geometry |
| `MESHING PREDICTOR` | `CURRENT` (if no Eulerian boundaries) | node positions used as the smoothing starting location |
| `INITIAL FEATURE ANGLE` | `30°` | θI; detection of geometric edges/corners; `180°` disables |
| `TRANSITION FEATURE ANGLE` | `30°` | θT; when a geometric feature is deactivated so remeshing can cross it; `0°` never deactivates |
| `MESH CONSTRAINT ANGLE` | `60°` | θC; abort angle when spatial mesh constraints approach boundary normals |
| `RESET` | — | reset all controls to defaults |

The weight data line is always 3 values (volume / Laplacian / equipotential, defaults
`1., 0., 0.`), for **both** objectives.

### 3.3 Measured effect of `FREQUENCY` — case D (`FREQUENCY=2`) vs case B (`FREQUENCY=10`)

Both whole-domain, UNIFORM, everything else identical:

| quantity | B (freq 10) | D (freq 2) | interpretation |
|---|---|---|---|
| `.msg` per-increment diagnostic blocks | 418 | **1859** | adaptive meshing runs ~5× more often |
| end-of-step avg % nodes moved | 33.55 | **10.24** | more frequent smoothing keeps the mesh better → less movement needed per increment |
| avg advection sweeps / increment | 1.00 | 1.00 | no change (automatic, and stays 1) |
| wall clock | 48.3 s | 55.1 s | ~14% costlier |

**FREQUENCY is clearly ACTIVE**: it controls *how often* ALE runs; the per-increment %-moved
drops as the mesh is kept smoother.

### 3.4 Measured effect of smoothing controls — case E (`SMOOTHING OBJECTIVE=GRADED`,
`CURVATURE REFINEMENT=0`) vs case B (UNIFORM, curvature 1)

| quantity | B (UNIFORM, curv 1) | E (GRADED, curv 0) |
|---|---|---|
| increment-0 diagnostic: `Mesh Sweeps` | 5 | **2** |
| `.msg` per-increment diagnostic blocks | 418 | 272 |
| end-of-step avg % nodes moved | 33.55 | 35.53 |
| avg advection sweeps / increment | 1.00 | 1.00 |
| wall clock | 48.3 s | 42.6 s |

**The smoothing controls are ACTIVE**, and one specific finding is worth knowing:

- **`SMOOTHING OBJECTIVE=GRADED` overrides `INITIAL MESH SWEEPS`.** Case E wrote
  `initial mesh sweeps=5` in the deck (verified in the `.inp`), yet the run performed **2**
  initial mesh sweeps at increment 0 — exactly the documented GRADED default. The GRADED
  objective performed its 2 "no-gradation" pre-smoothing sweeps and ignored the specified 5.
  Do not rely on `INITIAL MESH SWEEPS > 2` when GRADED is selected.

### 3.5 Which parameters appear inert in this model

- `MESH CONSTRAINT ANGLE` — only acts when explicit adaptive mesh constraints
  (`*Adaptive Mesh Constraint`) are defined. No constraints here → inert.
- `INITIAL / TRANSITION FEATURE ANGLE` — only act on geometric edges/corners. A uniform block
  has no meaningful features (the ODB GE set held 1 node) → not exercised.
- `ADVECTION`, `MOMENTUM ADVECTION`, `GEOMETRIC ENHANCEMENT`, `MESHING PREDICTOR` — control the
  advection algorithm and predictor, not the %-moved; not varied here. Their documented roles
  are unchanged by this test.

---

## 4. Output variables — how to distinguish ALE ACTIVE from ALE DEFINED BUT INERT

An adaptive mesh domain that is defined but never sweeps raises **no error**. The evidence of
actual activity comes from three places:

### 4.1 `.msg` diagnostics (quantitative; the primary evidence)

Request them with `*Diagnostics, adaptive mesh=summary` (CAE has **no** GUI equivalent —
"Adaptive mesh diagnostics are not supported in Abaqus/CAE"). The keyword is **step-dependent**:
it must follow the `*Dynamic, Explicit` procedure card. Empirically verified placements that
fail: before the first `*Step` → `KEYWORD CARDS FOR STEP DEPENDENT INPUT MUST APPEAR AFTER THE
FIRST *STEP CARD`; immediately after `*Step` → `A PROCEDURE OPTION IS MISSING FOR STEP`.
The verification script injects it after the `*Dynamic` card automatically.

Per increment (with `=SUMMARY`) the `.msg` gains blocks like:

```text
Summary Diagnostics for Adaptive Meshing: Step     1 Increment       0
   Domain Name: ASSEMBLY_ALE_BOX-1-1
   Mesh Sweeps:       5  Advection Sweeps:       1  Avg pctg. of Nodes Moved:  79.93
```

and at end of step:

```text
Step Summary Diagnostics for Adaptive Meshing: Step   1
   Domain Name: ASSEMBLY_ALE_BOX-1-1
   Avg number of Advection Sweeps:  1.00
   Avg pctg. of Nodes Moved:    86.16
   Min pctg. of Nodes Moved:    0.000
   Max pctg. of Nodes Moved:    99.92
```

**How to distinguish the two states:**

- **DEFINED BUT INERT** — the `.msg` shows the end-of-step summary (or nothing) with
  **0 % nodes moved / 0 advection sweeps**, or no per-increment blocks at all; the ODB still
  contains the LE/GE/NA node sets. No error is raised.
- **ACTIVE** — any per-increment block with `Mesh Sweeps` and `Avg pctg. of Nodes Moved > 0`
  (per-increment blocks are written only for increments in which at least one node is moved).
  A single 0%-moved block is normal (the mesh happened not to need smoothing that increment).

The domain is also always subdivided/split automatically; `Domain Name` in the block is
`<elset>-<subdivision>-<step>`, e.g. `ASSEMBLY_ALE_BOX-1-1`.

### 4.2 ODB node sets (qualitative; created whether or not ALE sweeps)

Abaqus writes up to three automatic node sets per domain per step into the `.odb`, named
`<elset>-<subdivision>-<LE|GE|NA>-<step>`: **LE** = Lagrangian edge nodes, **GE** = geometric
edge/corner nodes, **NA** = nonadaptive nodes (including Lagrangian corners). Observed:

| case | sets |
|---|---|
| A (no ALE) | none |
| B, D, E (whole domain) | `..._PICKEDSET13-1-LE-1 [1]`, `..._PICKEDSET13-1-NA-1 [1]` |
| C (box) | `ASSEMBLY_ALE_BOX-1-LE-1 [1]`, `ASSEMBLY_ALE_BOX-1-GE-1 [1]`, `ASSEMBLY_ALE_BOX-1-NA-1 [1]` |

Lagrangian edges/corners, geometric edges and nonadaptive nodes are also echoed to the `.dat`
file when a history definition summary printout is requested.

### 4.3 There is no dedicated field output variable for "ALE activity"

The mesh motion itself shows up as nodal displacement/current coordinates, but those mix
material motion with mesh motion. For material-point time histories inside an adaptive domain,
use tracer particles (`*Tracer Particle`; **not supported in CAE**). The reliable activity
measures are the `.msg` diagnostics above.

---

## 5. How ALE interacts with the free surface and with contact surfaces

Boundary regions of an adaptive mesh domain are the mechanism. Region types (from "Defining
ALE Adaptive Mesh Domains in Abaqus/Explicit"):

- **Lagrangian region** (default on the free exterior, and for loads/BCs): the mesh is
  constrained to move **with the material in the direction normal to the boundary**; nodes are
  free to move within/along the boundary ("a mesh patch that follows the material"), and no
  material crosses it. A free top surface therefore stays a material surface: mesh follows it
  normally and slides tangentially.
- **Sliding region** (default created when you define a **surface** on the domain boundary):
  same normal constraint, but completely unconstrained tangentially. This is the appropriate
  region type for **contact surfaces**, since contact involves relative sliding.
- **Eulerian region** (only on the exterior): material flows across the boundary; requires
  spatial mesh constraints to fix the mesh.

Contact-specific rules (current docs; the 2016 docs are quoted in §Compat b for general
contact):

- "Lagrangian and sliding boundary regions created using surfaces can be used in general
  contact and contact pairs; they have the same meaning as surfaces defined on nonadaptive
  regions."
- "Surfaces defined on Eulerian boundary regions cannot be used in the contact definition."
- "The nodes of an element-based surface in a **no-separation** contact interaction are
  nonadaptive."
- Contact-**pair** restrictions only: self-contact pairs cannot involve adaptive nodes
  (contact not enforced); **small-sliding** pairs make all nodes on both surfaces nonadaptive.
- A surface in the **interior** of a domain moves independently of the material (no boundary
  region is created there).
- Geometric features (edges/corners) are respected on Lagrangian/sliding boundaries
  (controlled by `INITIAL FEATURE ANGLE` / `TRANSITION FEATURE ANGLE`).

---

## COMPATIBILITY — the four production features

### a. `*Rigid Body` constraints — COMPATIBLE (tested directly)

The test indenter is a discrete rigid body (`m.RigidBody(refPointAtCOM=ON)` on an
assembly-level RP, `*Rigid Body, ref node=IndRP, elset=IndBody, position=CENTER OF MASS` in the
deck) in general contact with the ALE soil. Runs complete the ALE setup without error, and ALE
stays active. Documented basis: **"All nodes and elements on a rigid body are nonadaptive."**
The rigid body is simply inert to ALE; it does not disable ALE elsewhere. (The indenter's mesh
is outside the ALE domain, which is the normal arrangement.)

### b. General contact `*Contact, op=NEW` — COMPATIBLE (tested directly)

The test deck uses exactly the production form:

```text
*Contact, op=NEW
*Contact Inclusions, ALL EXTERIOR
*Contact Property Assignment
 ,  , Friction
```

Combined with ALE over the soil, the runs show full ALE activity (e.g. case B: 418
per-increment blocks, avg 33.55 % nodes moved; case C: 125 blocks, avg 86.16 %). **The general
contact nodes were NOT made nonadaptive**: the automatic NA set contained exactly 1 node in
every ALE case.

**Docs landmine to be aware of:** the 2016 Abaqus documentation (section "Defining ALE adaptive
mesh domains in Abaqus/Explicit") stated "All nodes in a general contact domain are
nonadaptive". That statement:
- is **not observed in Abaqus 2021** with `ALL EXTERIOR` general contact + ALE (see above);
- has been **removed from the current (2025) docs**, which now restrict only contact *pairs*
  (self-contact, small-sliding, no-separation) and allow general contact surfaces as sliding
  boundary regions ("Lagrangian and sliding boundary regions created using surfaces can be used
  in general contact and contact pairs").
The general contact algorithm places "more restrictions on adaptive meshing than the contact
pair algorithm" — but no restriction that blocks the production configuration. If the
production version differs from 2021, re-run case B/C to confirm.

Minor note: the `.dat` echo shows `***WARNING: OP=NEW on *CONTACT is ignored when the general
contact definition is specified as model data.` — benign, and the production deck already uses
this same `*Contact, op=NEW` form.

### c. Standard→Explicit import (`*Instance, library=compliant_implicit`, `*Import, state=yes, update=no`) — COMPATIBLE

Documented (section "Transferring results between Abaqus/Explicit and Abaqus/Standard"):
- The **only** documented ALE↔import restriction is in the **opposite** direction:
  **"An Abaqus/Standard import analysis where the reference configuration is not updated is
  not allowed if the adaptive meshing capability was used in the previous Abaqus/Explicit
  analysis."** The production direction (Standard→Explicit with `UPDATE=NO`) is not covered by
  this restriction, and no restriction on subsequently using ALE in the Explicit analysis is
  documented.
- With `STATE=YES` the material state is imported: "stress, equivalent plastic strain (PEEQ),
  and solution-dependent state variables (SDV) for UMAT and VUMAT will be continuous."
- Beware of what is **not** imported and must be redefined in the Explicit deck: "Contact pair
  definitions and general contact definitions are not imported"; loads, BCs, MPCs and
  coupling constraints are not imported. (The production deck already redefines `*Contact,
  op=NEW` in the Explicit phase.)
- For user-material state to survive the import, "you must ensure that the UMAT and VUMAT are
  consistent."

### d. VUMAT with `*Depvar 14` (fourteen SDVs) — COMPATIBLE

- ALE **advects** VUMAT SDVs. Documented verbatim ("Defining ALE adaptive mesh domains in
  Abaqus/Explicit"): **"Solution-dependent state variables defined in user subroutine VUMAT
  will be remapped to the new mesh when adaptive meshing is performed."** The remapping section
  adds: "stress, history variables, density, and internal energy are always solution
  variables" transferred in each advection sweep.
- Import side: with `*Import, state=yes`, the 14 SDVs are imported provided the UMAT/VUMAT
  state-variable definitions are consistent (§c). Then ALE advects them across sweeps. There
  is **no documented limit on the number of SDVs advected**; nothing in the docs closes the
  VUMAT route.

**Bottom line for (c)+(d):** the single most valuable outputs of this task are:
1. ALE **can** be combined with `*Import` in the production direction; the only ALE-import
   restriction documented is Explicit→Standard with `UPDATE=NO`.
2. ALE **can** advect user-material SDVs; VUMAT SDVs are explicitly remapped.

---

## 6. Implementation notes / gotchas for `the production model`

1. **Windows parallelism (critical).** Loop-level parallelization is **not available on
   Windows** (job aborts with "Loop level parallelization is not available on this platform").
   DOMAIN-level parallelization requires `numDomains` to be a multiple of `numCpus`, and with
   multiple parallel domains Abaqus marks nodes shared by adjacent domains **nonadaptive** —
   which cripples ALE. Use **`numCpus=1, numDomains=1`** (or any combination with
   `numDomains % numCpus == 0`) for ALE runs.
2. **`*Diagnostics, adaptive mesh=summary` must be injected after the `*Dynamic` card** —
   not before `*Step`, not immediately after `*Step`. CAE cannot define it.
3. **Element set creation**: pass `ElementArray` slices, never Python lists of `Element`
   objects, to `Set(elements=...)` on dependent instances ("Feature creation failed").
4. **Python 2 kernel**: no `splitlines(keepends=True)`, no `sum()` over generator
   expressions, no `open(..., errors='replace')` (use `codecs.open`). The embedded kernel is
   Python 2 in Abaqus 2021.
5. **The `.inp` omits parameters equal to the CAE default** (e.g. `frequency=10`,
   `mesh sweeps=1`). Absence in the deck is proof of the default, not of a bug.
6. **`INITIAL MESH SWEEPS` is overridden by GRADED** (fixed 2 sweeps) — do not expect a
   larger specified value to take effect with `SMOOTHING OBJECTIVE=GRADED` (§3.4).
7. `*Diagnostics` values are the only reliable ALE-activity evidence; "it ran without
   complaint" is insufficient (a defined-but-inert domain raises no error).

---

## 7. Ready-to-adapt code block — restricted ALE domain (case C configuration)

```python
# ---------------------------------------------------------------------------
# Restricted ALE adaptive mesh domain for the production soil, ported from
# examples/ex04_ale_indenter/model.py case C. All verified on Abaqus 2021.
#
# Requirements on the model:
#   - soil instance is first-order reduced-integration solids (C3D8R)
#   - the push step is geometrically nonlinear (*Dynamic, Explicit)
#   - job: numCpus=1, numDomains=1, explicitPrecision=DOUBLE_PLUS_PACK
# ---------------------------------------------------------------------------

import regionToolset
from abaqusConstants import UNIFORM, GRADED

def make_box_set(assemblyObj, inst, name, box):
    """Assembly-level element set from an element-centroid box filter.
    IMPORTANT: the kernel rejects Set(elements=[...list of Element...]) with
    'Feature creation failed'; only ElementArray slices are accepted, so the
    selected indices are stitched back into an ElementArray via maximal runs."""
    els, idxs = [], []
    for i, el in enumerate(inst.elements):
        nds = el.getNodes()
        nn = float(len(nds))
        cx = sum(nd.coordinates[0] for nd in nds) / nn
        cy = sum(nd.coordinates[1] for nd in nds) / nn
        cz = sum(nd.coordinates[2] for nd in nds) / nn
        if (box['xmin'] <= cx <= box['xmax'] and box['ymin'] <= cy <= box['ymax']
                and box['zmin'] <= cz <= box['zmax']):
            els.append(el)
            idxs.append(i)
    assert els, 'box element set is EMPTY'
    arr, run_start, run_end = None, idxs[0], idxs[0]
    for i in idxs[1:] + [-1]:
        if i == run_end + 1:
            run_end = i
        else:
            chunk = inst.elements[run_start:run_end + 1]
            arr = chunk if arr is None else arr + chunk
            run_start = run_end = i
    assemblyObj.Set(name=name, elements=arr)
    n_set = len(assemblyObj.sets[name].elements)
    assert n_set == len(els), 'box set size mismatch: CAE=%d filter=%d' % (n_set, len(els))
    return len(els)

# --- in the model build, after meshing and assembly -------------------------
a = m.rootAssembly
soilInst = a.instances['SoilInst']

# 1) element set restricted to a box around the indenter tip
BOX = dict(xmin=-0.08, xmax=0.08, ymin=0.0, ymax=0.20, zmin=0.0, zmax=0.10)
make_box_set(a, soilInst, 'ALE_Box', BOX)   # 1600 of 12000 soil elements

# 2) adaptive mesh controls (defaults unless changed)
m.AdaptiveMeshControl(name='ALE_BC', smoothingPriority=UNIFORM)

# 3) adaptive mesh domain in the push step
push = m.steps['Push']
push.AdaptiveMeshDomain(region=a.sets['ALE_Box'], controls='ALE_BC',
                        frequency=10, meshSweeps=1, initialMeshSweeps=5)

# 4) after writeInput(), inject *Diagnostics, adaptive mesh=summary after the
#    *Dynamic, Explicit procedure card so the .msg reports per-increment
#    activity (step-dependent input; see examples/ex04_ale_indenter/model.py
#    inject_diagnostics()).
```

To check the domain **actually did something**, open the `.msg` after the run and confirm
`Summary Diagnostics for Adaptive Meshing` blocks with nonzero `Avg pctg. of Nodes Moved`
(see §4).

---

## Appendix — run summary (all five cases, one script invocation)

Model: 0.30×0.20×0.20 m C3D8R soil (seed 0.01, E=20 MPa, ν=0.3, ρ=1651.6), rollers on
vertical faces, encastre base; rigid plate indenter (full width) driven by a velocity BC on
the RP, SMOOTH STEP ramp over first 5 % of step; general contact, µ=0.5. All cases aborted on
element distortion / negative mass (expected with a sharp indenter; the ALE activity numbers
below are the implementation evidence, not a response comparison).

| case | ALE | domain | controls | .msg blocks | avg % moved | inc-0 sweeps | wall | status |
|---|---|---|---|---|---|---|---|---|
| A | none | — | — | 0 | 0 | — | 36.5 s | ABORTED (distortion) |
| B | whole part | UNIFORM, curv 1, freq 10 | 418 | 33.55 | 5 | 48.3 s | ABORTED (distortion) |
| C | box (1600 els) | UNIFORM, curv 1, freq 10 | 125 | 86.16 | 5 | 38.2 s | ABORTED (distortion) |
| D | whole part | UNIFORM, curv 1, **freq 2** | 1859 | 10.24 | 5 | 55.1 s | ABORTED (distortion) |
| E | whole part | **GRADED, curv 0**, freq 10 | 272 | 35.53 | **2** | 42.6 s | ABORTED (distortion) |

Verbatim `.inp` adaptive-mesh lines, all cases (from the generated files):

```
case A: (no *Adaptive Mesh; only the *Contact block and the injected diagnostics differ
        from B)
case B: *Adaptive Mesh Controls, name=ALE_BC
        1., 0., 0.
        *Adaptive Mesh, elset=_PickedSet13, controls=ALE_BC, initial mesh sweeps=5, op=NEW
case C: *Adaptive Mesh Controls, name=ALE_BC
        1., 0., 0.
        *Adaptive Mesh, elset=ALE_Box, controls=ALE_BC, initial mesh sweeps=5, op=NEW
case D: *Adaptive Mesh Controls, name=ALE_BC
        1., 0., 0.
        *Adaptive Mesh, elset=_PickedSet13, controls=ALE_BC, frequency=2, initial mesh sweeps=5, op=NEW
case E: *Adaptive Mesh Controls, name=ALE_EE, smoothing objective=GRADED, curvature refinement=0.
        1., 0., 0.
        *Adaptive Mesh, elset=_PickedSet13, controls=ALE_EE, initial mesh sweeps=5, op=NEW
```

## Sources

- Defining ALE adaptive mesh domains in Abaqus/Explicit — docs.software.vt.edu/abaqusv2025
  `/English/SIMACAEANLRefMap/simaanl-c-aledomains.htm` (VUMAT SDV remap quote; rigid-body
  quote; boundary-region types; contact rules)
- ALE Adaptive Meshing and Remapping in Abaqus/Explicit — `.../simaanl-c-aleremesh.htm`
  (advection sweeps; "stress, history variables, density, and internal energy are always
  solution variables"; mesh-sweeps default = 1)
- Output and Diagnostics for ALE Adaptive Meshing — `.../simaanl-c-aleoutput.htm`
  (LE/GE/NA node sets; `*Diagnostics` levels)
- `*ADAPTIVE MESH` and `*ADAPTIVE MESH CONTROLS` keyword reference —
  `.../SIMACAEKEYRefMap/simakey-r-adaptivemesh.htm` and `simakey-r-adaptivemeshcontrols.htm`
  (parameter defaults; MESH SWEEPS default stated as 5 — contradicted by the guide, §3.1)
- Transferring results between Abaqus/Explicit and Abaqus/Standard —
  `.../simaanl-c-exptostd.htm` (ALE-import restriction; UMAT/VUMAT SDV import; what is not
  imported)
- 2016 docs, section 12.2.2 — "All nodes in a general contact domain are nonadaptive"
  (superseded in 2021 behavior / removed in current docs; §Compat b)
