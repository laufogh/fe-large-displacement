# Provenance — hypoplasticity with intergranular strain (Staubach)

## Licence

**GNU General Public License v3.0.** The full text is in `LICENSE` in this
directory. The `LICENSE` at the repository root (MIT) does **not** apply to this
subdirectory.

This is a copyleft licence. If you distribute a modified version of these files,
or a work that includes them, you must distribute it under GPL-3.0 as well. That
does not restrict private use. The source trees are distributed as separate
works, so the repository's original Python and documentation retain their MIT
licence. This statement does not determine the licensing of binaries produced
when Abaqus compiles and links the GPL-covered Fortran.

## Origin

| | |
|---|---|
| Upstream | <https://github.com/patrickstaubach/abaqus-explicit> |
| Author | Patrick Staubach — Bauhaus University Weimar / Ruhr-University Bochum |
| Tensor tools (`tools.f`) | A. Niemunis, KIT Karlsruhe |
| Upstream licence | GPL-3.0 |
| Retrieved | 2026-09 |

The constitutive model itself is the hypoplastic model for granular materials
with the intergranular strain extension, developed over many years by
Kolymbas, Gudehus, von Wolffersdorff, Bauer, Niemunis and Herle. Cite the
underlying model papers as well as Staubach's implementation papers; the
implementation is not the model.

## Files

| File | What it is |
|---|---|
| `HPP_Staubach_implicit.f` | UMAT for Abaqus/Standard |
| `HPP_Staubach_explicit.f` | Explicit-integration version of the model |
| `HPP_Staubach_explicit_noclamp.f` | As above, without the state clamping. This is the variant `call_explicit.f` includes. |
| `VUMAT_dry_Staubach.f` | Dry / uncoupled VUMAT interface. Derived from the upstream hydro-mechanically coupled `VUMAT_HMC_Staubach_Abq2023.f` with all pore-fluid coupling removed: total stress = effective stress. |
| `tools.f` | Tensor operations (Niemunis) |
| `sdvini.f` | SDVINI routine setting the initial void ratio from a Bauer profile |
| `call_implicit.f` | Top-level file for `user=` in Abaqus/Standard |
| `call_explicit.f` | Top-level file for `user=` in Abaqus/Explicit |
| `constants.txt` | A calibration. **See the warning below.** |

## The calibration is not part of the model

`constants.txt` holds a calibration for **Ottawa sand**, produced for a specific
research programme. It is included so the examples run, not because it applies to
your soil.

The file here is a set of constants for **Ottawa F65 sand**, adapted from
Fasano (Table 4) for the von Wolffersdorff (1996) hypoplastic model, with
several parameters retuned -- the retuned ones are marked `- changed` in the
file. The intergranular-strain parameters in particular are a working
calibration, not a published one.

Using someone else's hypoplastic constants for a different sand is not a small
approximation — the model is state-dependent, and the constants encode the
critical state line, the granular hardness and the intergranular strain
behaviour of one specific material. Recalibrate, or say clearly in your write-up
whose calibration you used.

## Hydro-mechanical coupling

The upstream repository contains the hydro-mechanically coupled VUMAT
(`VUMAT_HMC_Staubach_Abq2023.f`), which carries pore pressure as a state variable
and solves the fluid mass balance alongside the momentum equation, including
cavitation and effective contact stress. That is **not** vendored here, because
this repository's examples are all dry/total-stress.

It is the right starting point if you need the seepage part of suction caisson
installation — see [`docs/07-suction-caisson.md`](../../docs/07-suction-caisson.md).
Get it from the upstream repository, with the accompanying PDF, and read the
papers it references first.

## Modifications made here

1. Files were renamed for clarity: upstream `call.f` → `call_implicit.f`,
   upstream `call_dry.f` → `call_explicit.f`.
2. GPL-3.0 notices were added to `VUMAT_dry_Staubach.f`, `sdvini.f` and the two
   call files, which are derivative works or are combined with GPL code and
   carried no notice of their own.
3. Nothing in the numerical content of any file has been changed.

## Verifying it works

Before using this in a large model, run it on one element:

```bash
set FLD_UMAT_IMPLICIT=<repo>\constitutive\hypoplasticity-staubach\call_implicit.f
set FLD_UMAT_EXPLICIT=<repo>\constitutive\hypoplasticity-staubach\call_explicit.f
set FLD_UMAT_CONSTANTS=<repo>\constitutive\hypoplasticity-staubach\constants.txt
set FLD_UMAT_NSDV=14
abaqus cae noGUI=constitutive/single_element/model.py
```

Check the `*Depvar` count against what the subroutine actually writes — the
hypoplastic model with intergranular strain needs 14 in the implicit form, and
the VUMAT wrapper may need more. Getting this wrong produces NaN or silent
corruption, not an error.
