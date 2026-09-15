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
| `HPP_Staubach_explicit_noclamp.f` | As above, without the state clamping. Dry Explicit includes this. |
| `VUMAT_dry_Staubach.f` | Dry / uncoupled VUMAT interface. Derived from the hydro-mechanically coupled `VUMAT_HMC_Staubach_Abq2023.f` with all pore-fluid coupling removed: total stress = effective stress. |
| `VUMAT_HMC_Staubach_Abq2023.f` | Hydro-mechanically coupled VUMAT. Pore pressure is carried on the temperature DOF. |
| `call_explicit_saturated.f` | Top-level file for a saturated Explicit job (`user=`). |
| `vuamp.f` | User amplitude used by the coupled pile-driving example. |
| `vusdfld_parallel.f` | VUSDFLD: effective contact stress from pore pressure. |
| `vufield_parallel.f` | VUFIELD: maps that contact field onto the slave surface. |
| `tools.f` | Tensor operations (Niemunis) |
| `sdvini.f` | SDVINI routine setting the initial void ratio from a Bauer profile |
| `call_implicit.f` | Top-level file for `user=` in Abaqus/Standard |
| `call_explicit_dry.f` | Top-level file for a dry Explicit job (`user=`) |
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

`VUMAT_HMC_Staubach_Abq2023.f` carries pore pressure as a state variable and on
the temperature DOF, and solves the fluid mass balance alongside the momentum
equation, including cavitation. `vusdfld_parallel.f` and `vufield_parallel.f`
map that pore pressure onto the contact surface as an effective friction field.
Compile them through `call_explicit_saturated.f`. How to set the Abaqus keywords is in
[`README.md`](README.md).

These coupled files came from the same Staubach GPL-3.0 suite as the dry
wrapper, via the Ottawa-sand constitutive collection. They are not a
re-implementation. Read the papers cited in the VUMAT and VUFIELD headers
before changing the hardcoded permeability, water table, or pile geometry.

## Modifications made here

1. Files were renamed for clarity: upstream `call.f` → `call_implicit.f`,
   upstream `call_dry.f` → `call_explicit_dry.f`, upstream `call2023.f` →
   `call_explicit_saturated.f`.
2. GPL-3.0 notices were added to `VUMAT_dry_Staubach.f`, `sdvini.f`,
   `call_implicit.f`, `call_explicit_dry.f`, `call_explicit_saturated.f` and
   `vuamp.f`, which are derivative works or are combined with GPL code and
   carried no notice of their own.
3. Nothing in the numerical content of any file has been changed.

## Verifying it works

Before using this in a large model, run it on one element in Standard and
Explicit.

Check the `*Depvar` count against what the subroutine actually writes. The
hypoplastic model with intergranular strain needs 14 in the implicit form. The
coupled Explicit VUMAT needs 36. Getting this wrong produces NaN or silent
corruption, not an error.
