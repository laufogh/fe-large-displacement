# Coupled Eulerian-Lagrangian (CEL)

Companion to `examples/ex06_cel_indenter`.

## What it is

The Eulerian mesh is a fixed box of space. Elements never deform. Each element
carries a **volume fraction** (EVF, between 0 and 1) of each Eulerian material,
and material is transported between elements every increment by an advection
step. Lagrangian bodies — your structure — move through the Eulerian mesh and
interact with the material through general contact.

Because no element ever deforms, no element can ever invert. There is no
distortion limit. You can push to any depth.

## When it is the right answer

Use CEL when material has to change its **topological** relationship to the mesh:

* flow around a thin skirt or a pile tip;
* soil closing back over a penetrating object;
* a cavity opening and then collapsing;
* anything where a free surface folds onto itself.

ALE cannot do any of these. It smooths a mesh; it does not re-topologise one.

Do **not** use CEL because the strains are large. Large strain alone is an ALE
problem, and ALE keeps your free surface sharp.

## The four things that go wrong

### 1. No void space

The Eulerian part must extend **above** the soil surface. Heave needs somewhere
to go. If the soil fills the mesh to the top, the displaced material piles up
against a boundary and your penetration resistance is too high — with no warning
whatsoever.

`fldlib.cel.check_void_fraction()` counts the empty elements and complains below
15 %. That is a rule of thumb, not a law: deep penetration needs more. Case A of
example 06 exists to show what the mistake costs.

The top face must also stay **free** (no normal restraint). It is the outflow
boundary; closing it is a second way to lose heave.

### 2. The free surface is diffuse

The material boundary is reconstructed inside each element from the volume
fractions, so it is roughly one element thick. Expect a blurred surface and a
contact interface that is only as sharp as your mesh. Compare cases B and C of
example 06: four times the elements for a visibly sharper surface.

This has a practical consequence for skirt penetration: **the skirt wall must be
several Eulerian elements thick**, or the soil either side of it merges through
the wall. A rule of thumb is three elements across the wall thickness, which for
a lab-scale 2 mm wall means sub-millimetre elements, which drives the model size
hard. This is the usual reason a CEL caisson model is expensive.

### 3. Geostatic equilibrium

There is no `*Geostatic` procedure for an Eulerian domain. Two options:

* **Settle dynamically** under gravity in a preliminary explicit step. Honest,
  slow, and it rings — you need damping or a long enough settling time, and you
  must check the domain is actually at rest before the structure moves.
* **Initialise the stress field directly** with `*Initial Conditions,
  type=STRESS, GEOSTATIC`. Faster and cleaner, but you have to get `K₀` right
  yourself, and the field is only in equilibrium if it is consistent with the
  density and the boundary conditions.

Whichever you choose, verify it: run the model with no structure motion for a
short step and confirm nothing moves.

### 4. Cost per useful element

Most elements are empty most of the time and you pay for all of them. A CEL model
of the same problem is typically several times more expensive than the ALE model,
and much more than the Lagrangian one. That is the price of the topology freedom.

## Mechanics of setting it up

```python
part = model.Part(name='Eulerian', dimensionality=THREE_D, type=EULERIAN)
part.BaseSolidExtrude(sketch=sk, depth=soil_depth + void_thickness)

section, evf_key = cel.eulerian_section(model, 'EulSec', 'SoilMat')
# evf_key is the Eulerian material instance name, e.g. 'soilmat-1'

cel.set_eulerian_element_type(part)      # EC3D8R, HEX, STRUCTURED
```

The mesh **must** be structured hex. A swept or free mesh is rejected. That is
the main geometric constraint on CEL models and the reason Eulerian domains are
almost always simple boxes or cylinders, with refinement achieved by partitioning
into concentric structured regions rather than by local seeding.

Initial material placement:

```python
filled = eul_inst.cells.getByBoundingBox(zMax=0.0)      # everything below z=0
cel.assign_material(model, asm, eul_inst, asm.Set(name='SoilFilled', cells=filled))
```

which emits `*Initial Conditions, type=VOLUME FRACTION`. Use a **partition** to
define the filled region rather than a bounding-box filter over elements: a
partition is exact, and for the initial volume fraction you want exactness.

Contact **must** be general contact — the Eulerian-Lagrangian interaction is not
available through a contact pair.

## Output

Always request `EVF`. Without it you cannot see where the material is, and a CEL
result is close to impossible to debug blind. `fldlib.cel.surface_from_evf()`
pulls out the partially-filled elements so you can plot the reconstructed
surface.

## Verifying a CEL model

Two checks beyond the usual energy balance:

1. **Mass conservation.** Sum the volume fraction over the domain at the first
   and last frame. Material should not appear or disappear. Loss usually means
   material flowed out through a boundary you meant to close.
2. **Agreement with ALE and Lagrangian over their valid range.** All three
   formulations are solving the same problem, so over the depth range where all
   three are valid they must agree. If they do not, at least two of them are
   wrong. This check is the one most people skip and it is the one that finds
   real errors.
