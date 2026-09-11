# Provenance — Mohr-Coulomb and Tresca (Clausen)

## STATUS: NOT YET INCLUDED — permission required

**This directory is intentionally empty of source code.**

The subroutines intended for it are:

| File | What it is |
|---|---|
| `MohrCoulombAbaqus.for` | UMAT for Abaqus/Standard. Linear elastic – perfectly plastic, **non-associated** Mohr-Coulomb with exact stress return and explicit handling of the edges and the apex of the yield surface. |
| `TrescaAbaqus.for` | The same treatment for Tresca. |
| `VUMAT_MohrCoulomb.f` | VUMAT port for Abaqus/Explicit. |
| `call_mc.f` | Top-level include file. |

**Author: Johan Clausen (Aalborg University).** The source files carry **no
licence header of any kind**, which under copyright means all rights reserved.
They cannot be redistributed in a public repository without his written
permission, whatever their scientific provenance and however freely they have
been shared privately.

## To complete this directory

1. Obtain written permission from Johan Clausen to redistribute the files under
   a named licence. A draft request is in `PERMISSION-REQUEST.md`.
2. Copy the four files into this directory.
3. Add a `LICENSE` file with the agreed licence text, and record the licence,
   the date and the form of the permission in this file.
4. Delete this STATUS section.

Until step 1 is done, leave this directory as it is. An open-source repository
that redistributes someone's unlicensed code is a problem for the author, for
the institution and for anyone who then uses it downstream believing it was
cleared.

## Why it is worth the email

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

## What to do in the meantime

The examples fall back to the Abaqus built-in Mohr-Coulomb
(`fldlib.materials.mohr_coulomb_soil`), which is entirely adequate for learning
the ALE and CEL mechanics this repository is about. For sand specifically, the
`bolton-usdfld` model in the neighbouring directory is a cheap and useful
improvement on constant φ and ψ, and it is unencumbered.
