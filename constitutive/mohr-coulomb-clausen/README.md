# Clausen Mohr-Coulomb and Tresca

Johan Clausen's non-associated Mohr-Coulomb and Tresca UMATs use an exact
principal-stress return with explicit handling of yield-surface edges and the
apex. `VUMAT_MohrCoulomb.f` adapts the Mohr-Coulomb UMAT to Abaqus/Explicit.

## Licence and citation

The original Clausen sources are included with permission and are not covered
by the repository-root MIT licence. The repository-authored adapter, tests, and
documentation are MIT-licensed. Read [`LICENSE`](LICENSE): whenever the model is
used, any publication, technical report, presentation, or distributed analysis
must cite all three papers listed in [`PROVENANCE.md`](PROVENANCE.md).

## Material definition

The five constants are, in order:

1. Young's modulus, E
2. Poisson's ratio, nu
3. cohesion, c
4. friction angle, phi, in degrees and nonzero
5. dilation angle, psi, in degrees and nonzero

One state variable is required. `SDV1` records the return region: 0 elastic,
1 surface, 2 compression meridian, 3 tension meridian, and 4 apex.

Use `MohrCoulombAbaqus.for` as the user-subroutine source for Standard and
`call_mc.f` for Explicit. The latter includes the original UMAT and the VUMAT
adapter. A sample material property file is provided as `constants.txt`; it is
illustrative, not a soil calibration. Set `FLD_UMAT_NSDV=1` and
`FLD_SDV_INIT=0` in example 07 or 08; the zero explicitly initialises the
diagnostic SDV without requesting an `SDVINI` routine that is not in this
bundle.

## Verification

From `verification/`, run:

```bat
run_checks.cmd
```

This needs gfortran but not Abaqus. Before using the model in an analysis, also
compile and run it in a single element with the target Abaqus release. The VUMAT
currently uses the `dtArray` interface used by Abaqus 2022 and later; older
releases require a version-specific interface.
