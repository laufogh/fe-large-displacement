# Third-party notices

## Scope of the root licence

The `LICENSE` at the root of this repository is the MIT licence, and it covers
the original work here: `docs/`, `examples/`, `lib/`, `tools/`, `briefs/` and the
repository scaffolding.

It does **not** cover everything under `constitutive/`. Each subdirectory there
carries its own licence and provenance file, and those terms govern. This file
summarises what is there and under what terms; the `PROVENANCE.md` in each
subdirectory is authoritative.

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

The source trees are distributed together as separate works, so the root MIT
licence continues to govern the repository's original Python and documentation.
The Python merely supplies a source path to Abaqus. This notice does not make a
legal determination about redistribution of binaries produced when Abaqus
compiles and links the GPL-covered Fortran; review the GPL and the applicable
Abaqus terms before distributing such binaries.

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

## constitutive/mohr-coulomb-clausen/ — PERMISSION GRANTED; CITATION REQUIRED

Non-associated Mohr-Coulomb and Tresca UMATs with exact stress return, by
**Johan Clausen** (Aalborg University).

The source files are included with permission. Copyright in the original UMATs
remains with Johan Clausen, and the repository-root MIT licence does not apply
to those original files. The repository-authored adapter, verification drivers,
and documentation are MIT-licensed, subject to the original-source conditions
whenever the model is used or the source bundle is redistributed.

Use and redistribution require retaining the directory permission notice and
crediting Johan Clausen. Publications, technical reports, presentations, and
other distributed analyses that use the model must cite all three implementation
papers recorded in that directory's `LICENSE` and `PROVENANCE.md`.

The VUMAT adapter has standalone gfortran equivalence tests. It has not yet been
compiled and run through Abaqus on the target release; see `PORT-REPORT.md`.

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
