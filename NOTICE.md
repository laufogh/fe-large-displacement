# Third-party notices

## Scope of the root licence

The `LICENSE` at the root of this repository is the MIT licence, and it covers
the original work here: `examples/`, `lib/`, `documentation/` and the repository
scaffolding.

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
(Abaqus/Explicit), including the hydro-mechanically coupled Explicit VUMAT that
carries pore pressure on the temperature DOF.

**This is copyleft.** If you redistribute a modified version of these files, or a
work that includes them, that distribution must also be GPL-3.0. Using them
privately is unrestricted.

The source trees are distributed together as separate works, so the root MIT
licence continues to govern the repository's original Python and documentation.
The Python merely supplies a source path to Abaqus. This notice does not make a
legal determination about redistribution of binaries produced when Abaqus
compiles and links the GPL-covered Fortran; review the GPL and the applicable
Abaqus terms before distributing such binaries.

Files modified here: `VUMAT_dry_Staubach.f`, `sdvini.f`, `call_implicit.f`,
`call_explicit_dry.f`, `call_explicit_saturated.f` and `vuamp.f` had GPL-3.0
notices **added** (they are derivative works or are combined with GPL code and
carried no notice). Call files were renamed so dry versus saturated is in the
filename. No numerical content was changed.

The constitutive model itself — hypoplasticity for granular materials with the
intergranular strain extension — is the work of Kolymbas, Gudehus, von
Wolffersdorff, Bauer, Niemunis and Herle over many years. Cite the model papers
as well as the implementation.

---

## constitutive/mohr-coulomb-clausen/ — MIT, citation required

Non-associated Mohr-Coulomb UMAT with exact stress return, by
**Johan Clausen** (Aalborg University).

The source files are included with permission. Copyright in the original UMATs
remains with Johan Clausen, and the repository-root MIT licence does not apply
to those original files. The repository-authored adapter, verification drivers,
and documentation are MIT-licensed, subject to the original-source conditions
whenever the model is used or the source bundle is redistributed.

Use and redistribution require retaining the directory permission notice and
crediting Johan Clausen. Publications, technical reports, presentations, and
other distributed analyses that use the model must cite:

- Clausen, Damkilde and Andersen (2006), *Int. J. Numer. Meth. Engng* 66(6),
  1036–1059. https://doi.org/10.1002/nme.1595
- Clausen, Damkilde and Andersen (2007), *Computers & Structures* 85(23),
  1795–1807. https://doi.org/10.1016/j.compstruc.2007.04.002
- Clausen, Damkilde and Andersen (2015), *Engineering Computations* 32(6),
  1722–1752. https://doi.org/10.1108/EC-01-2014-0008

BibTeX is in `constitutive/mohr-coulomb-clausen/references.bib`.

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
