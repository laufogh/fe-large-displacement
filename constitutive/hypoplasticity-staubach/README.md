# Hypoplasticity with intergranular strain (Staubach)

GPL-3.0. Read [`LICENSE`](LICENSE) and [`PROVENANCE.md`](PROVENANCE.md).

Point `user=` at one of these files. Abaqus compiles only that file; everything
else is pulled in by `include`.

| File | What it is |
|---|---|
| `call_implicit.f` | Abaqus/Standard UMAT |
| `call_explicit_dry.f` | Explicit, dry. Total stress = effective stress. |
| `call_explicit_saturated.f` | Explicit, saturated. Pore pressure on the temperature DOF. |

## Dry (total stress)

`user=call_implicit.f` or `user=call_explicit_dry.f`. Standard needs `*Depvar`
14. Dry Explicit includes `HPP_Staubach_explicit_noclamp.f`.

## Saturated (pore pressure on the temperature DOF)

`user=call_explicit_saturated.f`. That file includes `HPP_Staubach_explicit.f`,
the hydro-mechanically coupled VUMAT, plus VUAMP, VUSDFLD and VUFIELD.

The step must be `*Dynamic, temperature-displacement, explicit`. `NT11` is pore
pressure, not temperature. A saturated job also needs:

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

The example scripts in this repository are dry / total-stress. Saturated
analysis is this subroutine stack, not a second example.

Cite the coupling papers listed in the VUMAT header as well as the hypoplasticity
model papers.
