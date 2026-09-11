# Third-party notices

## Scope of the root licence

The `LICENSE` at the root of this repository is the MIT licence, and it covers
the original work here: `docs/`, `examples/`, `lib/`, `tools/`, `briefs/` and the
repository scaffolding.

It does **not** cover everything under `constitutive/`. Each subdirectory there
carries its own licence and provenance file, and those terms govern. This file
summarises what
is there and under what terms; the `PROVENANCE.md` in each subdirectory is
authoritative.

---

## constitutive/hypoplasticity-staubach/ — GPL-3.0

| | |
|---|---|
| **Licence** | GNU General Public License v3.0 — full text in that directory |
| **Copyright** | Patrick Staubach (Bauhaus University Weimar / Ruhr-University Bochum) |
| **Tensor tools (`tools.f`)** | A. Niemunis, KIT Karlsruhe |
| **Upstream** | <https://github.com/patrickstaubach/abaqus-explicit> |

Hypoplasticity with intergranular strain, as UMAT (Abaqus/Standard) and VUMAT
(Abaqus/Explicit). The upstream repository also contains a hydro-mechanically
coupled VUMAT which is **not** vendored here.

**This is copyleft.** If you redistribute a modified version of these files, or a
work that includes them, that distribution must also be GPL-3.0. Using them
privately is unrestricted.

The GPL-3.0 here does not affect the MIT licence on the rest of this repository.
Nothing in `lib/` or `examples/` links against this Fortran: Abaqus performs the
compilation and linking at job submission, from a path supplied at run time. The
Python merely names a file.

Files modified here: `VUMAT_dry_Staubach.f`, `sdvini.f`, `call_implicit.f` and
`call_explicit.f` had GPL-3.0 notices **added** (they are derivative works or are
combined with GPL code and carried no notice). Two files were renamed. No
numerical content was changed.

The constitutive model itself — hypoplasticity for granular materials with the
intergranular strain extension — is the work of Kolymbas, Gudehus, von
Wolffersdorff, Bauer, Niemunis and Herle over many years. Cite the model papers
as well as the implementation.

---

## constitutive/bolton-usdfld/ — MIT

Original work, covered by the repository-root licence. A `USDFLD` subroutine that
makes the built-in Abaqus Mohr-Coulomb model stress-dependent using Bolton's
relative dilatancy index.

Reference: Bolton, M.D. (1986). The strength and dilatancy of sands.
*Géotechnique* 36(1), 65–78.

---

## constitutive/mohr-coulomb-clausen/ — NOT INCLUDED

Non-associated Mohr-Coulomb and Tresca UMATs with exact stress return, by
**Johan Clausen** (Aalborg University).

**The source files are not in this repository.** They carry no licence header of
any kind, which under copyright means all rights reserved, and they cannot be
redistributed publicly without written permission.

The directory contains a `PROVENANCE.md` explaining what is missing and why, and
a `PERMISSION-REQUEST.md` with a draft request. Complete those steps before
adding the files.

---

## Calibration data

`constants.txt` files distributed alongside constitutive models are calibrations
for specific soils from specific research programmes. They are included so the
examples run, not because they apply to anyone else's material. For a
state-dependent model a calibration is not a detail — it encodes the critical
state line, the granular hardness and the small-strain behaviour of one
particular sand.

---

## Abaqus

Abaqus, Abaqus/Standard, Abaqus/Explicit, Abaqus/CAE and SIMULIA are trademarks
of Dassault Systèmes. This repository is not affiliated with, endorsed by or
supported by Dassault Systèmes. You need your own Abaqus licence to run any of
it.

Keyword names, argument names and diagnostic message text quoted throughout the
documentation are quoted for interoperability and to record measured behaviour.
No Abaqus source code or documentation text is reproduced here.
