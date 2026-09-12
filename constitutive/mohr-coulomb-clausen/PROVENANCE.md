# Provenance — Mohr-Coulomb and Tresca (Clausen)

## Status and permission record

The source and port are included with permission. Copyright in the original
Mohr-Coulomb and Tresca implementations remains with Johan Clausen; inclusion
here does not place them under the repository-root MIT licence.

| | |
|---|---|
| Permission | Public redistribution and use, with mandatory citation of the three implementation papers listed below |
| Confirmed | 12 September 2026, by the repository maintainer, who retains the underlying permission record |
| Terms | [`LICENSE`](LICENSE) in this directory |
| Attribution | Johan Clausen, Aalborg University at the time of the work |

Included files:

| File | What it is |
|---|---|
| `MohrCoulombAbaqus.for` | UMAT for Abaqus/Standard. Linear elastic – perfectly plastic, **non-associated** Mohr-Coulomb with exact stress return and explicit handling of the edges and the apex of the yield surface. |
| `TrescaAbaqus.for` | The same treatment for Tresca. |
| `VUMAT_MohrCoulomb.f` | VUMAT adapter for Abaqus/Explicit. |
| `call_mc.f` | Top-level include file. |
| `verification/` | Standalone gfortran equivalence checks. |
| `PORT-REPORT.md` | Port design, verification results and limitations. |

The permission does not transfer copyright or make the original sources MIT.
Read the directory licence before redistributing or using the model.

## Required citations

Use of the model in a publication, technical report, presentation, or other
distributed analysis must cite all three papers:

1. Clausen, J., Damkilde, L. and Andersen, L. (2006). “Efficient return
   algorithms for associated plasticity with multiple yield planes.”
   *International Journal for Numerical Methods in Engineering*, 66(6),
   1036–1059. <https://doi.org/10.1002/nme.1595>
2. Clausen, J., Damkilde, L. and Andersen, L. (2007). “An efficient return
   algorithm for non-associated plasticity with linear yield criteria in
   principal stress space.” *Computers & Structures*, 85(23–24), 1795–1807.
   <https://doi.org/10.1016/j.compstruc.2007.04.002>
3. Clausen, J., Damkilde, L. and Andersen, L. (2015). “Robust and efficient
   handling of yield surface discontinuities in elasto-plastic finite element
   calculations.” *Engineering Computations*, 32(6), 1722–1752.
   <https://doi.org/10.1108/EC-01-2014-0008>

## Why the model is included

Abaqus has a built-in Mohr-Coulomb model, so this is not about availability.
It is about the return algorithm. The Abaqus implementation rounds the corners of
the yield surface; Clausen's returns exactly to the edges and the apex, using the
closed-form principal-stress solution. For a penetration problem that matters,
because a large fraction of the integration points near the tip sit **on** an
edge or at the apex, and a rounded surface both changes the strength there and
makes the consistent tangent worse.

It also handles the apex properly, which is where a cohesionless sand ends up
under the tensile conditions that occur behind a penetrating object — the exact
situation Abaqus' own implementation struggles with.

## Verification status

The standalone checks in `verification/` reproduce the UMAT stress update
through the VUMAT adapter in double and single precision. They do not replace an
Abaqus compile/data-check and single-element run on the target Abaqus release.
See `PORT-REPORT.md` for the exact coverage and remaining limitations.
