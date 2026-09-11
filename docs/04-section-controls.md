# Section Controls Verification — Findings

> **Provenance.** These are measured results, not a summary of the Abaqus
> manual. Every number below came from jobs that were actually run and whose
> `.inp`, `.sta`, `.msg` and `.dat` files were read. Where the documentation and
> the solver disagreed, the solver won and the disagreement is recorded.
> Verified on **Abaqus 2021**, Windows, `explicitPrecision=DOUBLE_PLUS_PACK`.
> Re-run it yourself with the companion example; if your Abaqus version behaves
> differently, that is worth a pull request.

### Distortion control + enhanced hourglass in Abaqus/Explicit (`*Section Controls`)

This file records the answers to the seven verification questions and a
recommendation for production use. It is written so that someone implementing
section controls in the production model does not have to rediscover any of this.

Supporting data: `ex03_section_controls_summary.csv` (post-processed per-case
numbers + cross-case tables), the per-case logs `ex03_<case>.log`, and the
per-case `.inp`/`.sta` files. Raw jobs live in `$FLD_WORKDIR`.

---

## 0. Bottom line

| Setting | Documented effect | What actually happened here |
|---|---|---|
| `distortion control=YES` | Penalty forces preventing element inversion; offset = `length ratio` × initial characteristic length | **Inert while the mesh is healthy (0.16% force deviation over the first half of the baseline run), then can rescue the analysis when elements approach collapse** (2.5× penetration at the primary calibration) or extend it marginally (+2.6%) when the collapse is not marginal. |
| `length ratio` (r) | Default `0.1`; penalty offset distance = r × L0 | Parsed and accepted, but **changing r from 0.05 to 0.20 changed nothing measurable** (B/C/D terminated at identical depth with identical energies at both calibrations). |
| `hourglass=enhanced` | Recommended by Abaqus; reduces artificial strain energy | **Cuts ALLAE/ALLIE from 16.5% to ~3.8% (−77%)** over the matched range, stiffens the response, delays the baseline collapse by 10%, does not rescue it. |
| `hourglass=enhanced` + `distortion control=YES` (case F) | Docs: combining them adds a small viscous damping to the element formulation (energy into ALLAE) | **Negates the distortion-control rescue**: F aborts at 0.069 m while B/C/D complete to 0.15 m. Do not combine. |

Energy channel for distortion-control work: **ALLDC** ("Energy dissipated by
distortion control"). It stayed **exactly 0 in every run** except a single
`1.085e-6 J` reading in case D (r=0.20) at the clean-abort calibration — proving
the channel exists but the penalty does energetically negligible work here. The
penalty acts as a constraint that redirects deformation (B's ALLAE fraction is
~2× A's), not as an energy sink.

---

## 1. Test model and calibration

SI units, elastic materials only, `explicitPrecision=DOUBLE_PLUS_PACK`,
`nodalOutputPrecision=FULL`, 4 CPUs. Soil block 0.30×0.20×0.20 m, C3D8R, seed
0.01 m, E=20e6, ν=0.3, ρ=1651.6; rollers on the four vertical faces, encastre on
the base. Rigid flat plate indenter (sharp lower edges, full soil width) via
`model.RigidBody(refPointAtCOM=ON)`; penalty contact, `weightingFactor=1.0`,
µ=0.5, HARD overclosure. Prescribed velocity `v3=-VEL` on the indenter RP with a
SMOOTH STEP ramp over the first 5% of the step.

Two calibrated configurations (env-overridable: `SV_HALF/SV_VEL/SV_DEPTH`):

| cfg | HALF | VEL | DEPTH | Baseline A termination | Baseline A abort message (verbatim) |
|---|---|---|---|---|---|
| **p0225** (primary) | 0.0225 m | 1.0 m/s | 0.15 m | p = 0.0600 m (analysis time 0.0646 s) | `***ERROR: The ratio of deformation speed to wave speed exceeds 1.0000 in at least one element. This usually indicates an error with the model definition. Additional diagnostic information may be found in the message file.` (no "excessively distorted element" count — the corner element 4806 blows up so fast the distortion detector does not trip first) |
| **p0235** (clean-abort) | 0.0235 m | 1.0 m/s | 0.15 m | p = 0.0623 m (analysis time 0.0663 s) | `***ERROR: Excessive distortion of element number 6807 of instance SOILINST` and `***ERROR: There is only one excessively distorted element` (followed by the deformation-speed lines) |

The p0235 calibration gives the verbatim "excessively distorted element" abort the
task asks the baseline to produce; p0225 gives the strongest rescue signal for the
Q2–Q7 comparisons. Both are reported throughout.

Calibration context: the abort is a dynamic corner-shear collapse at the sharp
plate edge. Sweeps across HALF=0.0225–0.0235 at VEL=1.0 show the failure is
extremely sensitive to the plate width and step length (a 0.0001 m width change
shifts the failure depth 35%; at HALF=0.0226–0.0227 distortion control can even
make the collapse slightly more explosive). Any production comparison must keep
geometry, velocity and step length fixed between cases — earlier contaminated
runs in this project compared HALF=0.024 (A/C/D) against HALF=0.0225 (B/E/F) and
produced a spurious "rescue".

---

## 2. Positive verification that each setting took effect

Every generated `.inp` was checked directly. The `*Section Controls` keyword is
injected at the TOP of the model data (immediately after `*Preprint`), and the
soil `*Solid Section` references it by name:

```
*Section Controls, name=SC-Soil, distortion control=YES                      (B, default r=0.1)
*Section Controls, name=SC-Soil, distortion control=YES, length ratio=0.05   (C)
*Section Controls, name=SC-Soil, distortion control=YES, length ratio=0.20   (D)
*Section Controls, name=SC-Soil, hourglass=enhanced                          (E)
*Section Controls, name=SC-Soil, hourglass=enhanced, distortion control=YES  (F)
*Solid Section, elset=_PickedSet5, material=SoilMat, controls=SC-Soil        (all B–F)
```

Case A contains no `*Section Controls` line. An unreferenced definition would be a
silent no-op; the reference by name is verified line-by-line in the script's
`verify_inp()` and echoed in every per-case log.

Placement note (costly to rediscover): `*Section Controls` MUST be placed before
`*Amplitude` in the model data. Placing it mid-file (after *Parts, before
*Material) corrupts the `SMOOTH STEP` amplitude parse in Abaqus 2021 — the job
fails at input with a spurious amplitude error. This was isolated empirically.

---

## 3. Answers to the seven questions

### Q1 — What is the length ratio, its default, and does changing it change behaviour?

**Documented** (Abaqus keyword reference, *Section Controls): the distortion-control
penalty forces are applied when a node moves to a small offset distance away from
the plane of constraint; that offset distance = `length ratio` (r) × the initial
element characteristic length. **Default r = 0.1, range 0 < r ≤ 1.** (For C3D10,
a volume ratio replaces the length ratio, same default 0.1.)

**Empirical**: cases B (r=0.1 default), C (r=0.05) and D (r=0.20) were compared at
both calibrations:

- **p0225**: B, C, D are identical to displayed precision — all COMPLETED the full
  0.1500 m depth with the same energies (ALLIE=986.3 J, ALLAE=719.6 J, ...), same
  RF3, same final Δt. r made zero difference.
- **p0235**: B and C are again identical (both clean-abort at 0.0639 m, element
  5202). D also terminates at 0.0639 m with the same energies, but with a
  different failure signature: **no** "excessively distorted element" count
  (def-speed-only abort) and a tiny nonzero `ALLDC = 1.085e-6 J` — the only
  nonzero ALLDC observed anywhere in the study.

**Conclusion**: r is parsed and accepted (positive .inp verification, no errors),
and r=0.20 does measurably engage the penalty marginally earlier (the μJ of ALLDC
and the different failure mode at p0235), but in this model the r value never
changed the outcome — termination depth and all energies were identical. The
collapse is dominated by the dynamic corner failure, and per the docs distortion
control "cannot prevent elements from being distorted due to temporal
instabilities". We could not produce a configuration where r changed the result;
this is reported rather than substituting a manufactured difference.

### Q2 — Where does the penalty energy go?

**Documented channel**: `ALLDC` = "Energy dissipated by distortion control", a
member of `ALLIE = ALLSE + ALLPD + ALLCD + ALLAE + ALLDMD + ALLDC + ALLFC`.
`ALLDMD` is the separate "Energy dissipated by damage" (material damage). The
docs also note that combining distortion control with enhanced hourglass adds a
small viscous damping whose dissipation is included in ALLAE.

**Empirical** (p0225, matched range [0, 0.0600] m, the whole of A's run):

| channel | ΔA / ΔALLIE (A, baseline) | ΔB / ΔALLIE (B, distortion control) |
|---|---|---|
| ALLIE | 1.000 | 1.000 |
| ALLSE | 0.835 | 0.698 |
| ALLAE | 0.165 | 0.302 |
| ALLVD | 0.028 | 0.074 |
| ALLKE | 0.065 | 0.217 |
| **ALLDC** | **0.000** | **0.000** |
| **ALLDMD** | **0.000** | **0.000** |
| ETOTAL | 0.054 | 0.095 |

ALLDC is **exactly 0 in both A and B** over the matched range, and ALLDMD too.
No channel captures a distortion-control contribution: B's internal energy is
*lower* than A's over the same range (1606 vs 2116 J) and its ALLAE fraction is
*double* A's. The penalty acts as a constraint that redirects the deformation into
different modes rather than dissipating energy. At p0235, D's terminal ALLDC of
1.085e-6 J (vs ΔALLIE ≈ 2500 J, ratio ≈ 5e-10) proves the channel is written and
populated when the penalty acts — the work is just energetically negligible.

**Answer**: ALLDC. Magnitude as a fraction of ΔALLIE: 0 in the baseline and
distortion-control cases over the matched range; ≤ 5e-10 in the one case where it
became nonzero. **If you implement distortion control in production, request ALLDC
and check ALLDC/ΔALLIE stays ≪ 1%** (see Recommendation).

### Q3 — Is it inert when not needed?

Force-displacement response of B vs A over A's successful range [0, 0.0600] m
(p0225):

| range | max |ΔRF3| | as % of max|RF3| (1.08e5 N) |
|---|---|---|
| [0, 0.5·p_end] = [0, 0.030] | 173 N | **0.16%** |
| [0, 0.9·p_end] = [0, 0.054] | 3031 N | 2.8% |
| full [0, 0.0600] | 4.81e4 N at p=0.0600 | 44.5% |

Deviation first exceeds 1% of max|RF3| at p = 0.0361 m (60% of A's range).

**Answer**: essentially inert in the genuinely-safe regime — the early half of the
baseline run matches to 0.16% of the force scale. The penalty begins to stiffen
the response (≥1% deviation) from p ≈ 0.036 m, which is where the elements under
the plate are already heavily compressed past the 10% offset (r·L0 = 0.1 × 0.01 m
= 1 mm) — i.e. it engages gradually during compression, not only at inversion.
The 44.5% number at the very end is contaminated by A's own collapse transient
(A's element 4806 is blowing up there), so it is not a clean reference.

### Q4 — How much further does distortion control let the analysis run?

Indenter penetration at termination (p0225 / p0235):

| case | p0225 | p0235 |
|---|---|---|
| A (baseline) | 0.0600 m (abort) | 0.0623 m (abort) |
| B (r=0.1) | **0.1500 m (COMPLETED)** | 0.0639 m (abort) |
| C (r=0.05) | 0.1500 m (COMPLETED) | 0.0639 m (abort) |
| D (r=0.20) | 0.1500 m (COMPLETED) | 0.0639 m (abort) |

**Answer**: at the primary calibration distortion control lets the analysis run
the **full depth, 2.5× further** (0.0600 → 0.1500 m). At the clean-abort
calibration, where the collapse is already marginal, it extends the run by only
2.6% (0.0623 → 0.0639 m). The benefit is steeply dependent on how close the model
starts to the collapse threshold; in a narrow near-threshold band (HALF
0.0226–0.0227) distortion control can even shorten the run. Production models
with a generous safety margin will see little benefit; models pushing deep
penetration near the limit can be rescued entirely.

### Q5 — What is the cost?

| case | Δt at increment 0 (both configs) | wall clock p0225 / p0235 |
|---|---|---|
| A | 5.23676e-5 s | 21.7 / 21.9 s |
| B | 5.23676e-5 s | 32.0 / 24.1 s (completes at p0225 → longer) |
| C | 5.23676e-5 s | 28.8 / 21.8 s |
| D | 5.23676e-5 s | 26.2 / 21.9 s |
| E | 5.23676e-5 s | 24.0 / 22.3 s |
| F | **4.97493e-5 s (−5.0%)** | 24.1 / 22.8 s |

**Answer**: distortion control alone costs nothing — the initial Δt is unchanged
and wall time is identical to baseline for the same amount of analysis. The only
measurable Δt change is **case F (−5.0%)**, caused by the viscous damping the docs
say is added when distortion control is combined with enhanced hourglass. B/C/D's
higher wall clock at p0225 is simply because they run 2.5× longer analysis, not a
per-increment cost.

### Q6 — Hourglass: does ENHANCED reduce ALLAE, and does the response change?

p0225, A (default) vs E (ENHANCED), matched range [0, 0.0600] m:

- **max ALLAE/ALLIE: 0.165 → 0.043 (−73.9%)**
- **end ALLAE/ALLIE: 0.165 → 0.038 (−76.8%)**

Force-displacement: E is stiffer — max |ΔRF3| over the full range 3.09e4 N (25.7%
of max|RF3|), 6.9% over the early half; ALLSE fraction rises from 0.835 to 0.962,
ALLKE falls. E terminates at 0.0662 m vs A's 0.0600 m (+10%): enhanced hourglass
delays the collapse slightly but does not prevent it.

**Answer**: ENHANCED reduces the hourglass energy fraction by ~77% in this model.
It does change the force-displacement response (stiffer, ~7% early / 26% near
collapse), which matters for force calibration. Applied to the production model's
11–14% ALLAE/ΔALLIE, it would bring the fraction down to roughly 3–4%.

### Q7 — Do the two settings interact?

p0225 (primary):

| case | status | p_end | RF3 at termination | ALLIE | ALLKE | ALLVD |
|---|---|---|---|---|---|---|
| B (distortion only) | COMPLETED | 0.1500 m | −5.80e4 N | 986 J | 86 J | 696 J |
| E (hourglass only) | ABORTED | 0.0662 m | −9.17e4 N | 2582 J | 270 J | 95 J |
| F (both) | **ABORTED** | 0.0692 m | **−1.42e5 N** | 3610 J | 6.9 J | 3.7 J |

F's force trace deviates from B by up to 97% of max|RF3| (75% over [0, 0.9·p_end])
and from E by up to 32%.

**Answer**: yes, and the interaction is negative in this model. The combination
**negates the distortion-control rescue** (F aborts at 0.0692 m while B/C/D
complete to 0.15 m). F fails with a stiff, explosive signature — the highest
terminal force of all cases, near-zero terminal KE and viscous dissipation — which
matches the documented mechanism: combining the two adds a small viscous damping
to the element formulation, and here that extra stiffness turns the absorbable
corner collapse into an explosive one.

---

## 4. Per-case report (every case, every number)

Values at termination (last output frame). Aborts include the verbatim message in
section 1 / in the per-case logs. `nDist` = elements reported excessively
distorted; `el` = the fatal element number; ETOTAL drift = ETOTAL/ALLIE at
termination (ΔALLIE ≈ ALLIE since ALLIE starts at 0).

### Config p0225 (primary, HALF=0.0225 VEL=1.0 DEPTH=0.15)

| case | status | p_end (m) | RF3 (N) | ALLIE | ALLKE | ALLAE | ALLVD | ALLDC | ALLDMD | ETOTAL | drift | nDist | el | initΔt | wall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | ABORTED | 0.0600 | −8.91e4 | 2116 | 137 | 349 | 60 | 0 | 0 | 115 | 5.4% | 0 | — | 5.24e-5 | 21.7 s |
| B | COMPLETED | 0.1500 | −5.80e4 | 986 | 86 | 720 | 696 | 0 | 0 | 260 | 26.3% | 0 | — | 5.24e-5 | 32.0 s |
| C | COMPLETED | 0.1500 | −5.80e4 | 986 | 86 | 720 | 696 | 0 | 0 | 260 | 26.3% | 0 | — | 5.24e-5 | 28.8 s |
| D | COMPLETED | 0.1500 | −5.80e4 | 986 | 86 | 720 | 696 | 0 | 0 | 260 | 26.3% | 0 | — | 5.24e-5 | 26.2 s |
| E | ABORTED | 0.0662 | −9.17e4 | 2582 | 270 | 458 | 95 | 0 | 0 | 129 | 5.0% | 0 | — | 5.24e-5 | 24.0 s |
| F | ABORTED | 0.0692 | −1.42e5 | 3610 | 6.9 | 255 | 3.7 | 0 | 0 | 94 | 2.6% | 0 | — | 4.97e-5 | 24.1 s |

### Config p0235 (clean-abort, HALF=0.0235 VEL=1.0 DEPTH=0.15)

| case | status | p_end (m) | RF3 (N) | ALLIE | ALLKE | ALLAE | ALLVD | ALLDC | ALLDMD | ETOTAL | drift | nDist | el | initΔt | wall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | ABORTED | 0.0623 | −6.46e4 | 2807 | 371 | 773 | 88 | 0 | 0 | 282 | 10.0% | 1 | 6807 | 5.24e-5 | 21.9 s |
| B | ABORTED | 0.0639 | −3.93e4 | 2474 | 543 | 953 | 118 | 0 | 0 | 269 | 10.9% | 1 | 5202 | 5.24e-5 | 24.1 s |
| C | ABORTED | 0.0639 | −3.93e4 | 2474 | 543 | 953 | 118 | 0 | 0 | 269 | 10.9% | 1 | 5202 | 5.24e-5 | 21.8 s |
| D | ABORTED | 0.0639 | −3.93e4 | 2474 | 543 | 953 | 118 | 1.1e-6 | 0 | 269 | 10.9% | 0 | — | 5.24e-5 | 21.9 s |
| E | ABORTED | 0.0715 | −1.41e5 | 4105 | 101 | 367 | 33 | 0 | 0 | 138 | 3.4% | 0 | — | 5.24e-5 | 22.3 s |
| F | ABORTED | 0.0700 | −1.49e5 | 4255 | 65 | 418 | 8.0 | 0 | 0 | 405 | 9.5% | 0 | — | 4.97e-5 | 22.8 s |

Notes:
- `p_end` is the indenter displacement at the last output frame; the `.sta`
  termination analysis time is slightly larger (e.g. p0235 A: 0.0623 m at
  0.0663 s).
- B's 26% ETOTAL drift at p0225 occurs in the deep post-collapse-rescue stage
  (massive viscous dissipation, ALLVD = 70% of ALLIE); over the matched baseline
  range [0, 0.0600] the drift is 9.5%.
- `nDist`=0 for def-speed aborts: the collapse is so fast the "excessively
  distorted element" detector never trips first; the fatal element is still an
  excessively distorted corner element.

---

## 5. Caveats and scope limits

1. **Elastic soil only.** The production hypoplastic UMAT is not exercised here;
   the section-control mechanics (penalty on inversion, hourglass formulation)
   are material-independent, but the collapse regime a UMAT produces will differ.
2. **Dynamic collapse, not quasi-static.** The 1.0 m/s indentation is dynamic; the
   failure is a corner-shear instability. The results (rescue magnitude, inert
   threshold) are specific to this loading rate and geometry. The *qualitative*
   findings — ALLDC is the channel and stays ~0, r is inconsequential here,
   ENHANCED+distortion control interact badly — are robust to the rate in the
   ranges swept (VEL 0.5–2.0 m/s in calibration sweeps showed the same patterns).
3. **Extreme sensitivity near the threshold.** Plate width changes of 0.0001 m
   flip the outcome (complete vs abort) and even the sign of the distortion-control
   benefit. Treat any single-number "benefit" as calibration-specific.
4. **`ALLFC`, `ALLIHE`, `ALLJD` are invalid history outputs** for this explicit
   elastic step (verified; they raise AbaqusException). The energy-balance
   identity `ALLIE = ALLSE+ALLPD+ALLCD+ALLAE+ALLDMD+ALLDC+ALLFC` cannot be fully
   audited with ALLFC unavailable.
5. **Keyword placement**: `*Section Controls` must precede `*Amplitude` in the
   `.inp` (Abaqus 2021 quirk, empirically isolated). The CAE API
   (`mdb.models.SectionControl`) does not exist in this build, so the keyword must
   be injected into the generated `.inp` (or written by a template).

---

## 6. RECOMMENDATION for the production soil section

**Add `distortion control=YES` with the default `length ratio` (0.1) to the
production soil section, and do NOT combine it with `hourglass=enhanced`.**

- **Distortion control, default r=0.1**: the only option that can extend the
  analysis when elements approach inversion (2.5× in the primary calibration), it
  is inert while the mesh is healthy (0.16% force deviation over the early range),
  costs nothing in Δt, and r=0.05/0.20 buys nothing in this model. Keep the
  default.
- **Do not add `hourglass=enhanced` on the same section.** Case F shows the
  combination loses the rescue and fails explosively. If the 11–14% ALLAE/ΔALLIE
  must be reduced, that is a separate decision: `hourglass=enhanced` alone cuts it
  ~77% but stiffens the force response (~7% early) and does not help survive
  collapse. Given the production model is pushing deep penetration where collapse
  margin matters, distortion control alone is the safer default.
- **Monitor `ALLDC`** (request it in history output alongside ALLIE) and assert
  **`ALLDC/ΔALLIE < 0.01`** as the check that distortion control is not doing
  significant mechanical work. Measured here: exactly 0 in all distortion-control
  runs, ≤ 5e-10 in the one nonzero case. Also watch `ALLAE/ΔALLIE` (should stay
  ≪ 0.1; ENHANCED would take it from ~0.14 to ~0.04) and ETOTAL drift.
- Before committing, re-verify on a production-scale run that the model is not in
  the near-threshold chaotic regime (where distortion control can shorten the run);
  if ALLDC stays ~0 and the analysis completes, the setting is safe and inert.
