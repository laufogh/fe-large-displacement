# Why large-displacement geotechnics needs a different toolkit

> Start here. Read this, then run example 01, then come back.

## The problem in one paragraph

Standard finite element analysis assumes the mesh follows the material. That is
an excellent assumption for a structure, and a poor one for a foundation being
installed. When a caisson skirt penetrates 10 m of sand, the soil beside it
strains hundreds of percent, flows around the tip, and closes up behind. A mesh
attached to that material stops being a usable mesh long before the installation
is complete — elements invert, the stable time increment collapses, and the job
aborts. The failure depth is set by the mesh, not by the soil, which means the
result is a property of your discretisation rather than of the problem.

Everything in this repository exists to get past that.

## The ladder

Each rung costs more than the one below it. Climb only as far as your problem
requires — a technique chosen because it is impressive rather than because it is
necessary is a technique whose failure modes you will not recognise.

| # | Approach | What it changes | Where it stops |
|---|---|---|---|
| 1 | **Implicit Lagrangian** (`*Static`) | nothing | convergence fails once the soil starts failing; typically a few percent of the diameter |
| 2 | **Explicit Lagrangian** (`*Dynamic, Explicit`) | no convergence to lose | element distortion; typically 10–40 % of the diameter |
| 3 | **+ section controls** | distortion control, enhanced hourglass | same failure, deferred; up to ~2.5× further in a marginal case |
| 4 | **ALE adaptive meshing** | nodes move relative to material, topology fixed | material has to change its topological relationship to the mesh — flow around a tip, closure behind an object |
| 5 | **CEL** | material flows through a fixed mesh | nothing, but the free surface becomes diffuse and the cost per useful element rises |

There is a sixth rung this repository does not cover — particle methods (MPM,
SPH) and adaptive remeshing with full solution mapping. If CEL is not enough,
that is where to look, and you will be leaving Abaqus.

## How to choose

Ask two questions about your problem.

**1. Does the material have to change its topological relationship to the mesh?**
Not "does it strain a lot" — a lot of strain is fine. The question is whether
material that starts on one side of something ends up on the other side, or
whether a surface that starts open closes. Caisson skirt penetration: yes, the
soil flows around the tip. Footing settlement, even a large one: no. Pile
driving: emphatically yes.

If no → ALE. If yes → CEL.

**2. Do you need the free surface sharp?**
Heave, scour, the exact shape of a soil plug. CEL reconstructs the surface inside
each element from volume fractions, so it is one element thick and no sharper.
If your answer depends on surface detail and you cannot afford the mesh to
resolve it, CEL will not give you what you want no matter how long you run it.

## What does not change

None of this removes the ordinary obligations.

* **The constitutive model still governs the answer.** ALE and CEL are numerical
  devices. They do not know about dilatancy, state dependence or stress-path
  effects. A perfect CEL analysis with Mohr-Coulomb is still a Mohr-Coulomb
  answer. See [06-constitutive-models.md](06-constitutive-models.md).
* **Explicit dynamics of a static problem must be shown to be quasi-static.**
  Every time, on every model. See [01-explicit-quasi-static.md](01-explicit-quasi-static.md).
* **Mesh convergence still applies.** It is harder to demonstrate, because you
  cannot refine indefinitely, but "I used CEL" is not a substitute for showing
  the answer stopped moving.
* **The deck is the ground truth.** Abaqus/CAE will accept arguments it does not
  implement and omit keywords whose values matched the default. Write the input
  file, read it, check it, and only then submit. Every example here does exactly
  that, and it is the habit most worth copying.

## The single most important warning

**An adaptive mesh domain that is defined but inert produces no error, no
warning, and a perfectly normal-looking ODB.** So does an Eulerian domain with no
void space for heave. So does a UMAT returning NaN in Abaqus/Explicit — the job
runs to completion and writes a complete results file.

Abaqus does not protect you from silent wrongness in this area. The examples in
this repository check for each of these explicitly, because checking is the only
thing that works.

## Reading order

1. This file.
2. [01-explicit-quasi-static.md](01-explicit-quasi-static.md) — the acceptance test you will use constantly.
3. Run `examples/ex01_lagrangian_limit` and `examples/ex02_quasi_static`.
4. [04-section-controls.md](04-section-controls.md) — cheapest wins first; run `ex03`.
5. [02-ale-adaptive-meshing.md](02-ale-adaptive-meshing.md) — run `ex04`.
6. [03-ale-multi-region-parallel.md](03-ale-multi-region-parallel.md) — run `ex05` on a many-core machine.
7. [05-cel.md](05-cel.md) — run `ex06`.
8. [06-constitutive-models.md](06-constitutive-models.md) — run `ex07`.
9. [07-suction-caisson.md](07-suction-caisson.md) — run `ex08`.
