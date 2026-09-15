!=======================================================================================================
! This file is combined with VUMAT_HMC_MohrCoulomb.f, which is derived from
! VUMAT_HMC_Staubach and is therefore distributed under the GNU General Public
! License version 3.
!
! This program is free software: you can redistribute it and/or modify it under
! the terms of the GNU General Public License as published by the Free Software
! Foundation, either version 3 of the License, or (at your option) any later
! version.
!
! Original Mohr-Coulomb UMAT: Johan Clausen. See LICENSE in this directory.
! Hydro-mechanical VUMAT instrumentation: Patrick Staubach, GPLv3.
! See PROVENANCE.md in this directory.
!=======================================================================================================
! Saturated Explicit suite. Pore pressure on the temperature DOF.
! user=call_explicit_saturated.f
      include'MohrCoulombAbaqus.for'
      include'VUMAT_HMC_MohrCoulomb.f'
