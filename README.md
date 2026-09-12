# fe-large-displacement

Abaqus scripts, documentation and measured findings for **large-displacement
finite element analysis in geotechnics** — ALE adaptive meshing, Coupled
Eulerian-Lagrangian, and a worked suction caisson installation.

Eight examples, from "watch an ordinary Lagrangian analysis fail" to "install a
suction caisson", each one runnable in a single command.

```bash
set FLD_WORKDIR=C:\abq\run
abaqus cae noGUI=examples/ex01_lagrangian_limit/model.py
```

> **Status: the code has never been run.** It was written on a machine without
> Abaqus. The Python parses and the deck-editing logic is unit-tested, but no
> Abaqus API call has been executed. See [`briefs/`](briefs/) for the test plan
> and [`briefs/KNOWN-UNCERTAINTIES.md`](briefs/KNOWN-UNCERTAINTIES.md) for an
> honest list of what is most likely wrong. The **findings in [`docs/`](docs/)
> are measured results** from real runs on Abaqus 2021 and are trustworthy.

---

## What this is for

A caisson skirt penetrating sand strains the soil beside it by hundreds of
percent. The soil flows around the tip and closes up behind it. A finite element
mesh attached to that material stops being usable long before installation is
complete — and the depth at which it fails is set by your mesh, not by the soil.

That is a numerical problem with well-understood solutions, and almost all of the
practical knowledge about applying them in Abaqus lives in people's heads, in
half-remembered forum threads, and in documentation that is in places simply
wrong. This repository writes it down, with the evidence.

## The ladder

| # | Approach | Example | Where it stops |
|---|---|---|---|
| 1 | Implicit Lagrangian | [`ex01`](examples/ex01_lagrangian_limit/) | convergence, at a few percent of the diameter |
| 2 | Explicit Lagrangian | [`ex01`](examples/ex01_lagrangian_limit/) | element distortion |
| — | Making explicit honestly quasi-static | [`ex02`](examples/ex02_quasi_static/) | — |
| 3 | Section controls | [`ex03`](examples/ex03_section_controls/) | same failure, deferred |
| 4 | ALE adaptive meshing | [`ex04`](examples/ex04_ale_indenter/), [`ex05`](examples/ex05_ale_parallel/) | material changing its topological relationship to the mesh |
| 5 | CEL | [`ex06`](examples/ex06_cel_indenter/) | nothing — but the free surface goes diffuse |
| — | Constitutive models | [`ex07`](examples/ex07_umat_single_element/) | — |
| ★ | **Suction caisson installation** | [`ex08`](examples/ex08_suction_caisson/) | — |

Examples 01–05 all use **the same benchmark model** — a rigid strip indenter in a
soil block. Nothing changes between them except the technique under study, so any
difference in the result is caused by the technique and not by a quietly
different mesh.

## Start here

1. [`docs/00-why-large-displacement.md`](docs/00-why-large-displacement.md) — the
   problem, the ladder, and how to choose a rung.
2. [`docs/01-explicit-quasi-static.md`](docs/01-explicit-quasi-static.md) — the
   acceptance test you will use on every single explicit run.
3. Run `examples/ex01_lagrangian_limit` and watch it fail.

## The three silent failures

Abaqus does not protect you from any of these. Each produces no error, no
warning, and a perfectly normal-looking ODB. Each has a check in this repository
because checking is the only thing that works.

| Failure | Check |
|---|---|
| An ALE domain that is **defined but never sweeps** — empty elset, wrong element type, wrong step type | `fldlib.ale.assert_active()` reads the `.msg` for actual node movement |
| A CEL domain with **no void space** for heave — resistance silently too high | `fldlib.cel.check_void_fraction()` |
| A user material returning **NaN** — Abaqus/Explicit integrates it to the end of the step and writes a complete ODB | `tools/check_odb_finite.py` |

And the habit that catches most of the rest: **write the input file, read it,
assert on it, and only then submit.** Abaqus/CAE accepts arguments it does not
implement and omits keywords whose values happened to match the default. The deck
is the only ground truth. `fldlib.report.InpCheck` makes this one line per
assertion, and every example uses it.

## Documentation

| File | Contents |
|---|---|
| [`00-why-large-displacement.md`](docs/00-why-large-displacement.md) | the problem and the ladder |
| [`01-explicit-quasi-static.md`](docs/01-explicit-quasi-static.md) | rate scaling, mass scaling, the energy acceptance test |
| [`02-ale-adaptive-meshing.md`](docs/02-ale-adaptive-meshing.md) | **measured.** Exact keywords, what CAE writes and omits, two documentation errors found, and how to prove ALE actually ran |
| [`03-ale-multi-region-parallel.md`](docs/03-ale-multi-region-parallel.md) | **measured.** Why one big adaptive region costs you a 2.5× load imbalance on 15 CPUs, and why four small ones cost nothing |
| [`04-section-controls.md`](docs/04-section-controls.md) | **measured.** Distortion control and enhanced hourglass — including the combination that silently negates the benefit |
| [`05-cel.md`](docs/05-cel.md) | when CEL is the right answer and the four things that go wrong |
| [`06-constitutive-models.md`](docs/06-constitutive-models.md) | UMAT/VUMAT workflow, `*Depvar`, state initialisation |
| [`07-suction-caisson.md`](docs/07-suction-caisson.md) | the capstone, and what it deliberately does not model |
| [`abaqus-launch-guide.md`](docs/abaqus-launch-guide.md) | launcher, compiler, paths with spaces, reading a finished job |

The three marked **measured** are transcriptions of real verification studies —
every number came from a job that was run and whose `.inp`, `.sta`, `.msg` and
`.dat` were read. Where the Abaqus documentation and the solver disagreed, the
solver won and the disagreement is recorded.

## Layout

```
docs/           the written-down knowledge
examples/       eight runnable studies; examples/common/ holds the shared benchmark
lib/fldlib/     model-building helpers (runs inside abaqus cae)
lib/postproc/   ODB post-processing (runs inside abaqus python)
constitutive/   UMAT/VUMAT sources -- SEE THE LICENCE NOTE BELOW
tools/          standalone utilities
briefs/         work orders for the agent that will test all of this
```

`lib/fldlib` is deliberately small and readable. Every function is a thin,
documented wrapper over one Abaqus API call or one well-defined idiom; nothing
reads hidden global state; and nothing is silently skipped — if a helper cannot
do what it was asked, it raises. Geotechnical models fail quietly and
expensively, so this library does not.

## Running the examples

Every example accepts the same environment variables:

| Variable | Effect |
|---|---|
| `FLD_WORKDIR` | where job files go (**no spaces** if compiling a subroutine) |
| `FLD_SUBMIT=0` | build and verify the decks without solving — fast, catches most mistakes |
| `FLD_CASES` | run a subset, e.g. `A,C` |
| `FLD_NCPU`, `FLD_NDOMAINS` | parallelism |
| `FLD_<PARAM>` | override any declared parameter, e.g. `FLD_IND_VEL=2.0` |

Each run prints its full parameter table into the log before building anything,
writes a `_params.json`, and produces a `_summary.csv` comparing every case. The
log alone tells you what was run.

`FLD_SUBMIT=0` is the one to start with on an unfamiliar machine.

## Tests available without Abaqus

The parameter, deck-editing, ALE-selection, and post-processing helpers have a
small pure-Python regression suite:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

GitHub Actions runs this suite on every push and pull request. It does not
replace the Abaqus verification briefs: the CAE API calls and solver behavior
still require the target Abaqus installation.

## Licence

**MIT** for the repository-authored files in `docs/`, `examples/`, `lib/`,
`tools/`, `briefs/`, `tests/`, and `.github/`, plus the root project files.

**Not MIT** for `constitutive/`. Each subdirectory there carries its own licence
and provenance:

| Directory | Licence |
|---|---|
| `constitutive/hypoplasticity-staubach/` | **GPL-3.0** (© Patrick Staubach; tensor tools © A. Niemunis) |
| `constitutive/bolton-usdfld/` | MIT |
| `constitutive/mohr-coulomb-clausen/` | Original sources: custom permission and mandatory three-paper citation — © Johan Clausen; repository-authored adapter/tests: MIT |

See [`NOTICE.md`](NOTICE.md) and [`constitutive/README.md`](constitutive/README.md).

## Contributing

The most valuable contribution is a **measured** one. If you run something on a
different Abaqus version and get a different answer from what `docs/` records,
that is a finding and it belongs in a pull request — with the version number, the
job files, and the lines from the `.msg` or `.dat` that show it.

The second most valuable is a check. If you have been bitten by a silent failure
mode that is not in the list above, add it and add the assertion that catches it.
