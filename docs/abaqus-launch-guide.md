# Launching Abaqus so that user subroutines actually compile

Practical notes, mostly Windows, mostly learned the hard way. Verified against
Abaqus 2021 and 2023 with Intel oneAPI.

## The golden rule

**Never call `ABQLauncher.exe` directly when a user subroutine is involved.**

It does not set up the Intel Fortran and MSVC environment, so the job fails at
link time with

```
'LINK' is not recognized as an internal or external command
```

which says nothing about the actual cause. Launch through the command wrapper,
which sources the compiler environment first:

```
C:\SIMULIA\Commands\abq2021.bat
```

`abaqus` on `PATH` normally resolves to `C:\SIMULIA\Commands\abaqus.bat`, which
forwards to the versioned wrapper. The wrapper runs Intel oneAPI `vars.bat`,
`vcvars64.bat` and `setvars.bat`, then `ABQLauncher.exe`.

Expected noise from the wrapper, **non-fatal**:

```
[ERROR:vcvarsall.bat] Invalid argument found : intel64
[ERROR:vcvarsall.bat] Invalid argument found : vs2022
...
oneAPI environment initialized ::        <-- this line is what matters
```

If you do not see the `oneAPI environment initialized` line, nothing involving a
subroutine will work.

## Verify the toolchain before anything else

On a new machine, two minutes well spent:

```bash
abaqus verify -user_std
abaqus verify -user_exp
```

These compile and run Abaqus' own reference subroutine jobs. If they fail, your
model will fail, and you will waste a day deciding it is your Fortran.

Compiler versions are tied to Abaqus versions. Abaqus 2021 wants a different
Intel Fortran from 2023. Check the release notes for your version before
installing a compiler.

## Spaces in paths

Two separate problems, both silent about their real cause.

### 1. Command-line parsing

```
ABQLauncher.exe cae noGUI=C:\Users\me\OneDrive - Some University\model.py
```

fails with

```
Abaqus Error: Command line option "University" may not be used with "cae"
```

Wrap the whole invocation and quote the inner path:

```bash
cmd /c ""C:\SIMULIA\Commands\abq2021.bat" cae noGUI="C:\path with spaces\model.py" -noenvstartup -noSavedOptions -noSavedGuiPrefs"
```

In PowerShell use the call operator and quote the path:

```powershell
& "C:\SIMULIA\Commands\abq2021.bat" cae noGUI="C:\path with spaces\model.py" -noenvstartup
```

### 2. The Fortran compile

The Intel Fortran driver that Abaqus invokes does **not** quote the source path.
A subroutine living under a path with a space in it fails to compile, with an
error that never mentions the space.

This is why `fldlib.subroutines.stage()` copies the subroutine **and everything
it `include`s** into the working directory before submitting, and why
`fldlib.config.workdir()` refuses a working directory containing a space when a
subroutine is in play. Set `FLD_WORKDIR` to something like `C:\abq\run`.

## Running the examples in this repository

```bash
set FLD_WORKDIR=C:\abq\run
abaqus cae noGUI=examples/indenter/explicit_ale/model.py
```

Useful environment variables, understood by every example:

| Variable | Effect |
|---|---|
| `FLD_WORKDIR` | where job files go (no spaces if compiling a subroutine) |
| `FLD_CASES` | run a subset, e.g. `A,C` |
| `FLD_SUBMIT=0` | build and verify the decks without solving — fast, and it catches most mistakes |
| `FLD_NCPU` | CPUs per job |
| `FLD_NDOMAINS` | parallel domains (must be a multiple of `FLD_NCPU`) |
| `FLD_<PARAM>` | override any declared parameter, e.g. `FLD_IND_VEL=2.0` |

`FLD_SUBMIT=0` is the one to reach for first on an unfamiliar machine. It runs
the whole build-and-verify pipeline in a minute or two and tells you whether the
decks are right before you spend hours solving.

## Submitting a deck directly

```bash
abaqus job=my_job input=my_job.inp user=call.f cpus=15 interactive
```

Notes:

* `interactive` keeps it in the foreground. For long runs, drop it and poll the
  `.sta`.
* The `user=` file must already be in the working directory, along with anything
  it `include`s.
* For Abaqus/Explicit with domain-level parallelisation, `domains` must be a
  multiple of `cpus`.
* **Loop-level parallelisation is not available on Windows.** The job aborts at
  the first increment with `Loop level parallelization is not available on this
  platform`. Use domain-level.

## Reading a finished job

Do not open the ODB first. Read, in order:

1. **`.sta`** — did it complete? How far did it get? For explicit, the header
   carries the initial stable time increment and the critical element.
2. **`.msg`** — per-increment diagnostics. Adaptive-meshing activity (if you
   injected `*Diagnostics`), mass scaling, contact diagnostics, and the warning
   that preceded the abort.
3. **`.dat`** — model summary, element counts, nonadaptive node counts.
4. **`.odb`** — only now.

With domain-level parallelisation each domain writes its own `.msg.N`. An ALE
region reports only to the `.msg` of the domain that hosts it, so scan all of
them.

`fldlib.jobs.status()` does steps 1–3 and prints the result.

## A job that "succeeded" and is wrong

The three ways this repository has seen it happen, none of which produce an
error:

* an ALE domain that was defined but never swept — check the `.msg`;
* an Eulerian domain with no void space — check the volume fractions;
* a user material returning NaN — Abaqus/Explicit integrates NaN to the end of
  the step and writes a complete ODB. Run `tools/check_odb_finite.py`.
