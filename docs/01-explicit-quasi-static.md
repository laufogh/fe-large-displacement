# Using a dynamic solver for a static problem

Companion to `examples/ex02_quasi_static`.

## The bargain

Abaqus/Explicit integrates the equations of motion forward in time with no
equilibrium iteration, so it never fails to converge. That is why it is the right
solver for a penetration problem. The price is that it is solving a *dynamic*
problem, and your problem is not dynamic.

The stable time increment is set by how fast a wave crosses the smallest element:

```
dt_stable ≈ L_min / c_d          c_d = sqrt( E (1-ν) / (ρ (1+ν)(1-2ν)) )
```

For E = 20 MPa, ν = 0.3, ρ = 1650 kg/m³ the dilatational wave speed is about
130 m/s, so a 10 mm element gives `dt ≈ 7.7 × 10⁻⁵ s`. Installing a caisson
0.5 m at a realistic 1 mm/s takes 500 s of physical time — **6.5 million
increments.** That run does not happen.

`fldlib.steps.report_time_budget()` prints this number before you submit. Run it
first, every time.

## The three levers

| Lever | Effect on `dt` | Effect on inertia | Cost |
|---|---|---|---|
| Raise the loading rate by *f* | none | inertial forces ∝ *f*² | run time ÷ *f* |
| Scale mass by *f* | × √*f* | inertial forces × *f* | run time ÷ √*f* |
| Coarsen the mesh | × (coarsening) | none directly | accuracy |

Rate scaling and mass scaling are not independent — both amount to increasing
the ratio of inertial to static forces. Use them together and the effects
compound.

**Semi-automatic mass scaling to a target increment** is usually the right form:
it scales only the elements that limit `dt`. Note what that means in a
large-displacement run — the limiting elements are the small, badly-shaped ones
next to the structure, which is exactly where the physics is. A factor of 100 on
those elements is not the same as a factor of 100 on the whole domain. Read the
total added mass Abaqus reports in the `.sta`; more than a few percent of model
mass should make you uncomfortable.

## The acceptance test

Request the energy history (`fldlib.steps.energy_output`) and check:

| Ratio | Acceptable | Publishable | Meaning |
|---|---|---|---|
| `ALLKE / ALLIE` | < 5 % | < 1 % | kinetic vs internal energy — is inertia carrying load? |
| `ALLAE / ALLIE` | < 5 % | < 2 % | hourglass energy — is the stiffness fictitious? |
| `\|ETOTAL\| / ALLIE` | < 1 % | < 0.5 % | energy balance — is energy leaking in or out? |
| `ALLDC` | ≈ 0 | ≈ 0 | distortion control work — is the penalty holding the mesh together? |
| `ALLSD` | ≈ 0 | ≈ 0 | *(implicit only)* automatic stabilisation — fictitious damping |

`lib/postproc/energy.py` extracts all of these and grades the run:

```bash
abaqus python lib/postproc/energy.py my_job.odb
```

### Read the peak, not the final value

A run whose kinetic energy is 0.5 % at the end but spiked to 30 % during the
ramp has already corrupted the early part of the penetration curve — often the
part you care about most. The tool reports the peak and the time at which it
occurred for exactly this reason.

### These are guides, not physics

0.06 is not a failure and 0.04 is not a certificate. What matters is that you
looked, that you report what you found, and that the trend is right: if halving
the rate halves `ALLKE/ALLIE` and does not move the resistance, you are
converged in rate. That demonstration is worth more than any single ratio.

## What not to do

**Do not add damping until the kinetic energy goes away.** Material damping and
bulk viscosity remove the symptom and leave the error. If a case fails the test,
slow it down or scale less. If you cannot afford to, say so in the write-up and
quote the ratio you achieved.

**Do not skip the ramp.** A velocity boundary condition applied as a step change
sends a stress wave through the entire model on the first increment. A
`SMOOTH STEP` amplitude over the first 5 % of the step removes it at negligible
cost. `fldlib.steps.smooth_ramp()`.

**Do not use single precision.** `explicitPrecision=DOUBLE_PLUS_PACK` and
`nodalOutputPrecision=FULL`. Over a few hundred thousand increments single
precision accumulates enough error to visibly corrupt a penetration curve, and
it interacts badly with user subroutines written in double precision.

## Bulk viscosity

Abaqus applies linear bulk viscosity (default 0.06) to damp ringing at the
element level, and quadratic bulk viscosity (default 1.2) to smear shocks. Both
defaults are fine for this work and you should leave them alone. Their
contribution appears in `ALLVD`; if `ALLVD` is a significant fraction of `ALLIE`
you have a genuinely dynamic problem and should stop pretending otherwise.
