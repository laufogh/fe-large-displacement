# Hypoplasticity with intergranular strain (Staubach)

GPL-3.0. Read [`LICENSE`](LICENSE) and [`PROVENANCE.md`](PROVENANCE.md).

## Dry (total stress)

`user=call_implicit.f` for Abaqus/Standard. `user=call_explicit.f` for
Abaqus/Explicit. Standard needs `*Depvar` 14.

## Coupled (pore pressure on the temperature DOF)

`user=call2023.f`. That file includes the hydro-mechanically coupled VUMAT,
plus VUAMP, VUSDFLD and VUFIELD.

The step must be `*Dynamic, temperature-displacement, explicit`. `NT11` is pore
pressure, not temperature. A coupled job also needs:

- `*Depvar` 36
- `*User defined field`
- `*Conductivity` and `*Specific heat` (they set the pore-pressure diffusivity)
- `*Inelastic heat fraction` 1.0 (the VUMAT writes the fluid mass-balance residual there)
- `*Field, user` on the soil instance
- `NT11 = 0` on faces that should drain

Permeability, viscosity, water table and cavitation are hardcoded at the top of
`VUMAT_HMC_Staubach_Abq2023.f`. Pile radius and centre for the effective-contact
field are hardcoded in `vusdfld_parallel.f`. Edit those. They are not in
`constants.txt`.

The example scripts in this repository are dry / total-stress. Coupled analysis
is this subroutine stack, not a second example.

Cite the coupling papers listed in the VUMAT header as well as the hypoplasticity
model papers.
