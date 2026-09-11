# Suction caisson installation

Companion to `examples/ex08_suction_caisson`.

## The physics you are trying to capture

A suction caisson is an inverted bucket. Installation has two phases.

**Self-weight (or jacked) penetration.** The caisson sinks under its own weight
until the resistance — skirt tip bearing plus inner and outer friction — balances
it. In dense sand this typically gets you 10–30 % of the skirt length.

**Suction-assisted penetration.** The lid is sealed and water is pumped out.
The pressure inside drops by Δp relative to ambient. Two things follow:

1. **A net downward force on the lid**, `Δp · π R²`. Straightforward.
2. **An upward seepage gradient through the soil plug.** Water flows from outside
   the caisson, down past the skirt tip, up through the plug and out of the pump.
   That upward flow reduces effective stress inside the caisson: it loosens the
   plug, cuts the tip resistance at the skirt and cuts inner skirt friction.

**Effect 2 is the mechanism that makes suction installation work in dense sand.**
Without it, the required Δp would be so large that the plug would fail in piping
first. It is not a second-order correction.

## What the example models, and what it does not

`examples/ex08_suction_caisson` models **effect 1 only.** Suction is applied as a
concentrated downward force on the caisson reference point, equal to Δp times the
plan area.

It does **not** model effect 2. There is no pore fluid in the analysis.

Consequences, stated plainly:

* the model **over-predicts** the suction required, because the resistance
  reduction that makes suction work is absent;
* it cannot reproduce plug heave driven by seepage;
* it cannot predict piping or plug failure, which is the governing limit state
  for the maximum allowable suction;
* the ratio of inner to outer friction will be wrong, because in reality seepage
  reduces the inner friction specifically.

This is stated in the script's own documentation, in its run log, and here.
A suction caisson model that silently omits seepage is the single most common way
to produce a plausible-looking and completely wrong installation curve.

## What it would take to model effect 2

Three routes, in increasing order of effort and fidelity.

### a. Prescribed pore pressure field (cheap, approximate)

Solve the steady seepage problem separately (analytically, or with a simple flow
FE model) for the given Δp and penetration depth, then impose the resulting pore
pressure field as a predefined field that modifies the effective stress in the
soil model. Cheap, and it captures the first-order resistance reduction. It does
not couple — the flow field does not respond to the deformation — so it cannot
predict piping.

### b. Coupled pore fluid in Abaqus/Standard

`*Soils, consolidation` with pore-pressure elements (C3D8P) gives a genuinely
coupled analysis. The problem is that Abaqus/Standard cannot get through the
large deformation: you are back at the convergence wall of example 01, and ALE
adaptive meshing is not available for `*Soils`. The practical use of this route is
for the *final* penetration increment, or for a small-deformation seepage study
at a fixed depth.

### c. Hydro-mechanically coupled VUMAT in Abaqus/Explicit

Carry the pore pressure as a state variable inside the constitutive subroutine
and solve the fluid mass balance alongside the momentum equation. This is what
`constitutive/hypoplasticity-staubach/` implements, and it is the route used in
the published vibratory pile driving and cyclic pile work that model came from.
It is the correct answer and it is a substantial undertaking: you inherit the
subroutine's stability characteristics, its time-step requirements and its
calibration.

If the visiting scholar's project needs installation resistance in sand, route
(a) is where to start. If it needs plug stability or maximum allowable suction,
only (c) will do.

## Modelling choices in the example, and why

**Quarter symmetry.** The problem and the loading are both axisymmetric during
installation, so a quarter model is exact and costs a quarter of the run time.
This stops being legitimate the moment a lateral load or moment is applied, which
is why the example installs the caisson and stops. An installation-then-loading
study needs a half model at minimum.

**Rigid caisson.** The caisson is a rigid body. A deformable skirt is a different
study — skirt buckling and structural stresses — and needs a much finer shell
mesh, which would drive the stable time increment down for no benefit to the
installation resistance. Make it deformable when the skirt is what you are asking
about.

**Two adaptive regions (ALE method).** One around the skirt tip, one inside the
plug, separated by a band of non-adaptive elements. Two rather than one because:

* the two zones deform for different reasons — the tip shears a narrow band, the
  plug heaves as a body — and benefit from being treated separately;
* two well-separated regions are placed in different parallel domains, whereas
  one large region is consolidated into a single domain and unbalances the whole
  decomposition. See [03-ale-multi-region-parallel.md](03-ale-multi-region-parallel.md).

They must not touch. Regions sharing a face are treated as one region. The
example checks for overlap explicitly and raises, because an element in two
adaptive domains is smoothed twice per increment and Abaqus does not warn.

**Rate.** The default penetration rate is scaled far above reality. Check
`ALLKE/ALLIE` before believing any resistance from it, and see
[01-explicit-quasi-static.md](01-explicit-quasi-static.md).

## ALE or CEL for a caisson?

Both are provided (`FLD_METHOD=ale` or `cel`), and the honest answer is that it
depends on the skirt.

**CEL is formally more correct** — soil genuinely flows around the skirt tip and
the topology changes. But it needs about three Eulerian elements across the wall
thickness or the soil merges through the wall, and for a thin skirt that makes
the model very large. For a lab-scale 2 mm wall you are looking at sub-millimetre
elements.

**ALE is cheaper and keeps the free surface sharp**, and works well as long as
the mesh topology can still describe the deformed state. For a caisson it usually
can, provided the initial mesh already has the skirt path resolved and the
adaptive regions are placed around it.

In practice: use ALE to get the installation resistance curve, and use CEL to
check it at one or two depths. If they disagree, find out why before trusting
either.

## What to extract

```bash
abaqus python lib/postproc/history.py ex08_ale_J.odb CAISSONRP curve_J.csv
```

* **Resistance against depth, case J.** The jacked installation curve. This is
  the reference: at the depth where suction takes over, the force the caisson
  needs is exactly the resistance from this curve.
* **Depth against time, cases S and S2.** Under a fixed suction the penetration
  rate is an *outcome*, not an input, and it is what a designer actually wants.
  An accelerating caisson means resistance is falling away — check whether the
  plug is failing. A stalling caisson means resistance is growing faster than the
  applied force, and you need more suction.
* **Plug heave.** In ALE, the vertical displacement of the soil surface inside
  the skirt. In CEL, the EVF field. Remember that without seepage the heave here
  is the *mechanical* plug displacement only.
