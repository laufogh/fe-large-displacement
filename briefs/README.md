# Briefs for the test agent

These are work orders for a coding agent running on a machine that **has
Abaqus**. Everything in this repository was written on a machine that does not,
so no Abaqus script here has ever been executed. The Python parses; the Abaqus
API calls are unverified.

That is the job. Work through the briefs in order, fix what is broken, and report
back.

## Before you start

Read [`KNOWN-UNCERTAINTIES.md`](KNOWN-UNCERTAINTIES.md) first. It is an honest
list of the specific things most likely to be wrong, written by the person who
wrote the code. It will save you a lot of bisecting.

## Order

| Brief | What it covers | Needs |
|---|---|---|
| [00](00-environment-smoke-test.md) | Abaqus version, compiler, working directory, `abaqus verify` | Abaqus |
| [01](01-deck-generation.md) | Build every deck with `FLD_SUBMIT=0`. **Catches most errors, costs minutes.** | Abaqus/CAE |
| [02](02-lagrangian-baseline.md) | Examples 01–03: Lagrangian limit, quasi-static, section controls | solve time |
| [03](03-ale.md) | Example 04: ALE, and the "defined but inert" check | solve time |
| [04](04-ale-parallel.md) | Example 05: parallel decomposition | ≥15 CPUs |
| [05](05-cel.md) | Example 06: CEL | solve time |
| [06](06-constitutive.md) | Example 07: single-element UMAT/VUMAT | Fortran compiler |
| [07](07-suction-caisson.md) | Example 08: the capstone | solve time, patience |

**Do brief 01 before anything else that costs machine time.** It runs the entire
build-and-verify pipeline for all eight examples without solving a single
increment, and it will find the great majority of the API errors.

## Ground rules

1. **Fix forward, do not work around.** If `findAt` misses a face, fix the
   coordinate — do not wrap it in a try/except. The scripts raise loudly on
   purpose; a silent fallback in a geotechnical model is how wrong answers get
   published.
2. **Keep the teaching intact.** These scripts are documentation as much as
   code. If you change behaviour, update the docstring that describes it, and if
   you discover something that contradicts `docs/`, fix the doc too — those
   files claim to be measured results.
3. **Every fix gets a one-line reason.** In the commit message, not just the
   diff.
4. **Do not tune away a failure.** If a case aborts, that may well be the point
   of the case. Check the brief's "expected outcome" before deciding something
   is broken.
5. **Do not commit job files.** `.gitignore` covers them. Do commit the summary
   CSVs and logs you are asked for, under `briefs/results/`.

## Environment

```bash
set FLD_WORKDIR=C:\abq\run          # no spaces -- the Fortran compile needs this
set FLD_REPO=C:\path\to\fe-large-displacement
```

Every example accepts:

| Variable | Effect |
|---|---|
| `FLD_WORKDIR` | where job files go |
| `FLD_CASES` | run a subset, e.g. `A,C` |
| `FLD_SUBMIT=0` | build and verify decks, do not solve |
| `FLD_NCPU`, `FLD_NDOMAINS` | parallelism |
| `FLD_<PARAM>` | override any declared parameter |

Run an example with:

```bash
abaqus cae noGUI=examples/ex04_ale_indenter/model.py
```

See [`docs/abaqus-launch-guide.md`](../docs/abaqus-launch-guide.md) for the
launcher and path traps, which are real and will cost you an afternoon if you
skip them.

## Reporting back

For each brief, write `briefs/results/<brief-number>-report.md` containing:

```markdown
# Brief NN — report

- Abaqus version:
- Platform / CPUs:
- Date:

## Outcome
PASS / PASS WITH FIXES / BLOCKED

## What was run
(exact commands)

## Fixes applied
| File | Line | What was wrong | What it is now |

## Results
(the summary table printed by the runner, verbatim)

## Anything that contradicts docs/
(be specific — these files claim to be measured results)

## Still broken / not attempted
```

Attach the `*_summary.csv` and the master `.log` from each study.

## If you get stuck

Say so in the report and move to the next brief. A blocked brief with a precise
description of the blockage is more useful than a brief that was quietly skipped
or bodged into passing.
