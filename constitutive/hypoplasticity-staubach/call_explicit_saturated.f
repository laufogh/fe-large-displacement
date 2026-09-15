!=======================================================================================================
! This file is part of, or is combined with, VUMAT_HMC_Staubach and is therefore
! distributed under the GNU General Public License version 3.
!
! This program is free software: you can redistribute it and/or modify it under
! the terms of the GNU General Public License as published by the Free Software
! Foundation, either version 3 of the License, or (at your option) any later
! version.
!
! This program is distributed in the hope that it will be useful, but WITHOUT ANY
! WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
! PARTICULAR PURPOSE. See the GNU General Public License for more details.
!
! You should have received a copy of the GNU General Public License along with
! this program. If not, see <https://www.gnu.org/licenses/>.
!
! Original hypoplastic model and hydro-mechanical VUMAT: Patrick Staubach.
! Tensor tools: A. Niemunis (KIT Karlsruhe).
! See PROVENANCE.md in this directory.
!=======================================================================================================
! Saturated Explicit suite. Pore pressure on the temperature DOF.
! user=call_explicit_saturated.f
      include'tools.f'
      include'HPP_Staubach_explicit.f'
      include'VUMAT_HMC_Staubach_Abq2023.f'
      include'vuamp.f'
      include'vusdfld_parallel.f'
      include'vufield_parallel.f'

