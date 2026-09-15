# Multiple ALE adaptive regions and parallel-domain placement — findings

> **Provenance.** These are measured results, not a summary of the Abaqus
> manual. Every number below came from jobs that were actually run and whose
> `.inp`, `.sta`, `.msg` and `.dat` files were read. Where the documentation and
> the solver disagreed, the solver won and the disagreement is recorded.
> Verified on **Abaqus 2021**, Windows, `explicitPrecision=DOUBLE_PLUS_PACK`.
> Re-run it yourself with the companion example; if your Abaqus version behaves
> differently, that is worth a pull request.


**Date:** 2026-08-27
**Model:** standalone elastic soil block (0.5 × 0.5 × 0.2 m, ~50 000 C3D8R), rigid-plate indenter, general contact
**Setup:** `cpus = 15`, `domains = 15`, `explicitPrecision = DOUBLE_PLUS_PACK`, domain-level parallelization
**Runs:** all five cases from the former `examples/ex05_ale_parallel` script, each deliberately terminated after a few hundred increments to preserve the per-domain `.msg.N` files. That script is not a separate model in the current tree. The findings stand. The production pattern (several well-separated regions) is used in `examples/suction_caisson`.
**Scratch directory:** `$FLD_WORKDIR`

---

## 1. The answer in one paragraph

**Multiple separate (non-adjacent) adaptive mesh regions ARE distributed across different parallel domains.** Two well-separated regions landed in domains 14 and 15 (case C); four well-separated regions landed in four different domains (1, 6, 10 and 15 — case D), with a **perfectly balanced** decomposition. **Adjacent regions that share a face are NOT distributed** — case E placed both regions in the same parallel domain (15), identical to the single-region case B. The packager therefore offers a real way to spread ALE work: split the adaptive zone into several regions separated by at least one band of non-adaptive elements.

---

## 2. Parallel-domain placement per adaptive region

| Case | Config | Region → parallel domain | Distribution |
|---|---|---|---|
| A | no ALE | — | (reference: perfectly balanced, all weights ≈ 6.67) |
| B | one region, 5600 el (~11 %) | R1 → **d15** | single region, consolidated |
| C | two non-adjacent regions, 2800 el each (~5.6 %) | R1 → **d15**, R2 → **d14** | **DISTRIBUTED** |
| D | four non-adjacent regions, 1400 el each (~2.8 %) | R1 → **d1**, R2 → **d6**, R3 → **d10**, R4 → **d15** | **DISTRIBUTED** |
| E | two adjacent regions sharing face x=0, 2800 el each | R1 → **d15**, R2 → **d15** | CONSOLIDATED |

Region → domain mapping is taken from the per-domain `.msg.N` files: each adaptive region writes its
`Summary Diagnostics for Adaptive Meshing` block only to the message file of the parallel domain that
hosts it (verified empirically). Every region in every case produced at least one diagnostic block
(the increment-0 block with 5 mesh sweeps and ≈80 % of nodes moved), so **no region was defined-but-inert**.

---

## 3. Domain decomposition detail

Element counts / node counts / weight per parallel domain (from the packager's `.sta` report):

| Case | Domains 1–14 (typical) | Domain 14 | Domain 15 | Max weight |
|---|---|---|---|---|
| A | ~3330 el / ~4180 n, weight 6.67 | 3521 el / 6.667 | 3330 el / 6.6665 | 6.67 |
| B | ~3060 el / ~3950 n, weight 6.06 | 3052 el / 6.062 | **7260 el / 8464 n / 15.145** | 15.15 |
| C | ~3250 el / ~4250 n, weight 6.43 | **3960 el / 4784 n / 8.2229** | **3960 el / 4784 n / 8.2229** | 8.22 |
| D | ~3340 el / ~4300 n, weight 6.67 | 3563 el / 6.666 | 3254 el / 6.668 | 6.67 |
| E | ~3060 el / ~3950 n, weight 6.06 | 3052 el / 6.062 | **7260 el / 8464 n / 15.145** | 15.15 |

Notes:

- **B** inflates domain 15 to **weight 15.15** (2.5× the balanced 6.06) — the entire 5600-element region is consolidated there. This is the known single-region behaviour.
- **C** inflates **two** domains, one per region, to weight 8.22 each — a much smaller penalty than B, and the regions are on different ranks.
- **D** shows **no penalty at all**: the packager placed each 1400-element region in a different domain and still returned a perfectly balanced decomposition (all weights ≈ 6.67). Four small regions cost nothing in balance.
- **E** is byte-for-byte the same decomposition as B — the two adjacent regions behave exactly like one region of the same footprint.

---

## 4. NONADAPTIVE NODES counts (from `.dat`)

The `.dat` writes one `NONADAPTIVE NODES (INCLUDING LAGRANGIAN CORNER NODES)` section **per adaptive domain**; the totals below sum all sections. Same total adaptive element count (5600) in B, C, D and E.

| Case | NA nodes (total) | Per region | Adaptive elements | Ratio NA/adaptive |
|---|---|---|---|---|
| A | 0 | — | 0 | — |
| B | 1922 | R1: 1922 | 5600 | 0.343 |
| C | 2484 | R1: 1242, R2: 1242 | 5600 | 0.444 |
| D | 3048 | R1–R4: 762 each | 5600 | 0.544 |
| E | 1990 | R1: 995, R2: 995 | 5600 | 0.355 |

Interpretation:

- C and D show **more** nonadaptive nodes than B (+29 % and +59 % respectively) for the same total adaptive element count. This is **not** a sign of region boundaries being cut across parallel domains — every region remained fully active and none of its diagnostic blocks was split across two `.msg` files. The increase is the geometric cost of fragmenting a region: smaller regions have a larger surface-to-volume ratio, so more nodes sit on the boundary between adaptive and non-adaptive material and are suppressed.
- E (adjacent regions) costs almost nothing over B (+3.5 %): the shared face is internal, so little new boundary is created.
- The nonadaptive node counts in the ODB (per-region `GE/LE/NA` sets) match the `.dat` numbers exactly (e.g. D: `R1-1-NA-1 [762 nodes]`), confirming the counts are per-domain and correctly summed.

---

## 5. Timing

| Case | s/1000 increments | n_inc run | status |
|---|---|---|---|
| A | 39.4 | 432 | KILLED (deliberate) |
| B | 38.4 | 495 | KILLED (deliberate) |
| C | 32.8 | 519 | KILLED (deliberate) |
| D | 31.8 | 377 | KILLED (deliberate) |
| E | 31.9 | 439 | KILLED (deliberate) |

All runs were deliberately terminated after a few hundred increments (to preserve `.msg.N` files), so the timing is noisy and only indicative. The message is qualitative, not quantitative:

- **B is not dramatically slower than A** — a single 11 % region inflates one of 15 domains to weight 15.15, i.e. a 2.5× hot rank, but with 14 other ranks idle-ish this is far from the catastrophic whole-soil case (weight 99.85).
- **C, D and E are all faster than B in these short runs**, consistent with their lower max weights (8.22 / 6.67 / 15.15). The perfectly balanced D is the fastest of the ALE cases.
- Initial `Delta_t` (5.23676e-05 s, critical element 4205) is identical across all cases, as expected for the same mesh.

---

## 6. Case E: does the deck emit two regions or are they merged?

**The deck emits two regions, and the solver keeps them as two separate adaptive domains — but the packager consolidates both into one parallel domain.**

- Generated `.inp` contains **two** `*Adaptive Mesh` lines (`elset=R1` and `elset=R2`) with two distinct `*Elset` cards (2800 elements each).
- The `.dat` lists **two** solver-side adaptive domain names: `ASSEMBLY_R1-1-1` and `ASSEMBLY_R2-1-1`.
- The `.msg.15` file shows **both** domain names with their own diagnostic blocks (R1: 11 blocks, R2: 12 blocks) — both active, with the same %-moved values per increment (e.g. 74.52 % at increment 0, 0.20/0.16 % at increment 260), i.e. the shared-face nodes are handled consistently.
- Yet the domain decomposition is identical to case B: **both regions in domain 15, weight 15.145**.

So touching regions are not merged into one adaptive smoothing domain; they are two smoothing domains that happen to share nodes on the face, and the packager refuses to split them across parallel boundaries — exactly the documented
"adaptive smoothing domains cannot span parallel domain boundaries" constraint applied at the packager level.

---

## 7. Positive verification (each region active, correctly sized)

| Case | `.inp` elsets | `*Adaptive Mesh` lines | `.dat` domain names | `.msg` blocks (host domain) | ODB NA sets |
|---|---|---|---|---|---|
| B | R1 = 5600 | 1 | `ASSEMBLY_R1-1-1` | 17 in `.msg.15` | 1922 |
| C | R1 = 2800, R2 = 2800 | 2 | `ASSEMBLY_R1-1-1`, `ASSEMBLY_R2-1-1` | R1: 1 in `.msg.15`, R2: 1 in `.msg.14` | 1242 + 1242 |
| D | R1–R4 = 1400 each | 4 | `ASSEMBLY_R1-1-1` … `ASSEMBLY_R4-1-1` | R1: `.msg.1`, R2: `.msg.6`, R3: `.msg.10`, R4: `.msg.15` | 762 × 4 |
| E | R1 = 2800, R2 = 2800 | 2 | `ASSEMBLY_R1-1-1`, `ASSEMBLY_R2-1-1` | R1: 11 in `.msg.15`, R2: 12 in `.msg.15` | 995 + 995 |

- The elset member counts in the `.inp` match the box-filter counts exactly, so every region is defined at deck level with its own set.
- Every region produced at least one diagnostic block with ≈80 % nodes moved (the increment-0 initial mesh sweep) — no region is defined-but-inert.
- In C and D the blocks appear in *different* `.msg` files, proving the regions are hosted by different ranks and remain distinct during the run.

---

## 8. Guidance for production

### Because regions ARE distributed (the good news)

1. **Split a large adaptive zone into several well-separated regions to spread ALE work across ranks.** Case D shows four regions of 2.8 % each give a perfectly balanced decomposition with zero weight penalty. Case C (two 5.6 % regions) still reduces the hot-domain weight from 15.15 to 8.22.
2. **Separate the regions by at least one band of non-adaptive elements.** "Well-separated" means no shared nodes. Any shared node forces the packager to keep the touching regions on the same rank (case E → weight 15.15, exactly like one region). Keep at least a thin gap of non-adaptive elements between regions.
3. **Per-region nonadaptive-node overhead scales with region count.** Fragmenting 5600 elements into 4 regions raised NA nodes from 1922 to 3048 (+59 %). For a production model this is a modest, quantifiable cost that must be traded against the load-balance win; inspect the `.dat` per-domain NA sections to see it.
4. **How to confirm it in production:** run a short job with `*Diagnostics, adaptive mesh=summary` in the `.inp`, then
   - read the packager's `DOMAIN DECOMPOSITION` from the `.sta` and check that no single domain carries a weight much above 100/NDOM;
   - count the `NONADAPTIVE NODES` sections in the `.dat` — one per adaptive domain — and confirm the total is in line with expectation;
   - check the per-domain `.msg.N` files (retain them by terminating the job rather than letting it complete) and confirm each region's diagnostic block appears in the intended rank(s);
   - confirm the `.inp` contains one `*Adaptive Mesh` card per region with its own `*Elset`.
5. **Don't rely on "it ran without complaint":** with the CAE Python API, a second `AdaptiveMeshDomain` call silently overwrites the first, and a *defined-but-inert* region produces no error. Positive verification (elsets + diagnostics + decomposition) is the only reliable check. (This project's script builds the first region through the CAE API and injects the remaining `*Adaptive Mesh` cards directly into the `.inp`, then verifies them.)

### Caveats

- All measurements are for a ~50 000-element elastic model at 15×15. Element count and geometry influence the exact placement; the *qualitative* behaviour (separated → distributed, touching → consolidated) is expected to hold, but verify on the production mesh.
- Timing at a few hundred increments is noisy; use long-enough runs or the packager weights (which are available before the solver does meaningful work) for the load-balance comparison.
- These runs used `cpus = 15 = domains`; the "one domain per region" pattern is a packager decision that may vary with `numCpus`/`numDomains`, so re-check if those change.

---

## 9. Files

- Script: the former `examples/ex05_ale_parallel/model.py` (single invocation, per-case exception isolation, per-case log banners)
- Post-processed report: ``$FLD_WORKDIR`\ale_multi_region_parallel_post.txt`
- Per-case logs: `multireg_<case>_case.log` in the same directory
- Model/deck/result files: `multireg_<case>.{inp,dat,sta,msg.N,odb}` in the same directory
