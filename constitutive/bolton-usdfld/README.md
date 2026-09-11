# Bolton stress-dependent friction and dilation (USDFLD)

**Licence: MIT**, same as the repository root. This is original work.

## What it does

This is not a constitutive model. It is a `USDFLD` user subroutine that makes the
**built-in** Abaqus Mohr-Coulomb model stress-dependent, by computing the peak
friction angle φ and the dilation angle ψ at each integration point from the
current mean effective stress, using Bolton's relative dilatancy index:

```
I_R = I_D (Q - ln p') - R
ψ    = 1.25 I_R                    (degrees, plane strain form)
φ    = φ_cv + 0.8 ψ
```

with `Q ≈ 10` and `R ≈ 1` for silica sand. The three values are handed to Abaqus
as field variables:

| Field | Quantity |
|---|---|
| `FIELD(1)` | mean effective stress `p'` [Pa], compression positive |
| `FIELD(2)` | friction angle φ [degrees] |
| `FIELD(3)` | dilation angle ψ [degrees] |

You then define `*Mohr Coulomb` as a table dependent on field variables 2 and 3,
and Abaqus interpolates.

## Why bother

Constant φ and ψ is the single worst assumption in a routine sand model. Real
sand is much stronger at low confining stress than at high, which is exactly the
gradient a shallow foundation or a caisson skirt experiences — and the strength
near the surface is what governs the early installation resistance.

This gets you a large part of the way from "constant φ" to "sand" for:

* no state variables,
* no `*Depvar`,
* no initialisation problem,
* essentially no run-time cost,
* and no NaN risk.

It is the right first step before committing to hypoplasticity or SANISAND.

## What it does not do

* **No history.** φ is a function of the *current* stress only. There is no
  fabric, no memory of the installation, no softening from peak to critical
  state along a shear band. Once a shear band forms, this model keeps giving it
  peak strength.
* **No void ratio evolution.** `I_D` is a fixed parameter, so the soil cannot
  densify or loosen.
* **Plane-strain form.** The 1.25 coefficient is Bolton's plane-strain
  relation. Triaxial conditions want 0.8·I_R for ψ and 3·I_R for the strength
  increment. The subroutine as written is plane strain; change it if your
  problem is not.

If your question is about cyclic behaviour, plug densification, or post-peak
localisation, this is not enough and you need a real state-dependent model.

## Step control

The subroutine keys off `KSTEP`:

* `KSTEP = 1` — geostatic step. Computes the field variables from the current
  stress and stores them in state variables.
* `KSTEP = 2` — loading step. Uses the stored values.
* other steps — keeps the initial values.

**That numbering is hard-coded.** If your model has a different step order you
must edit the subroutine, and nothing will warn you if you do not — you will get
a model with whatever φ happened to be stored, which may well look reasonable.

## Parameters

Currently hard-coded as `PARAMETER` statements near the top of the file, calibrated
for Ottawa-65 sand:

```fortran
PHI_CV  = 32.0     ! critical state friction angle [deg]
ID      = 0.5      ! relative density [-]
Q_PARAM = 10.0     ! Bolton Q [-]
R_PARAM = 1.0      ! Bolton R [-]
```

Edit them for your sand. Moving them to `PROPS` would be a welcome contribution.

## Using it

```bash
abaqus job=my_job input=my_job.inp user=constitutive/bolton-usdfld/usdfld.for cpus=8
```

Remember the path rules in [`docs/abaqus-launch-guide.md`](../../docs/abaqus-launch-guide.md):
no spaces, and stage the file into the working directory
(`fldlib.subroutines.stage()` does this).

## Reference

Bolton, M.D. (1986). The strength and dilatancy of sands. *Géotechnique* 36(1),
65–78.
