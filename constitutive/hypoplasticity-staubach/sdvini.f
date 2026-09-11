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
      SUBROUTINE SDVINI(STATEV,COORDS,NSTATV,NCRDS,NOEL,NPT,
     1 LAYER,KSPT,CMNAME,NAMES)
C
      implicit none
C
      REAL(8) STATEV(NSTATV),COORDS(NCRDS)
      integer NOEL,NCRDS,NPT,LAYER,KSPT,NSTATV
c
c     Variables for Bauer's void ratio profile
      real*8  bauer_ID, e_max, e_min, mc_phi, hs, n_bauer, N_g
      real*8  g_accel, rho_w, gamma_sat, gamma_w, gamma_sub, e0
      real*8  z_model, z_prototype, sigma_v_eff, p_eff, pi_const
      real*8  K_0, e0d, e0l, e0exp
c
      character*80 CMNAME, NAMES(NSTATV)
c
      statev(:)   = 0.0d0
c
      ! Bauer parameters for Ottawa sand (from sdvini_MRA_bauer.f)
      e_max     = 0.785d0            ! Maximum void ratio
      e_min     = 0.482d0            ! Minimum void ratio
      mc_phi    = 31.87d0            ! Friction angle (degrees)
      N_g       = 80.0d0            ! g-level (centrifuge)
      g_accel   = 9.81d0            ! Gravity (m/s^2)
      gamma_sat = 20.18d3           ! Saturated unit weight (N/m^3)
      rho_w     = 1000.0d0          ! Water density (kg/m^3)
      pi_const  = 3.14159265358979d0
c
      hs        = 170.0d6           ! Granular hardness (Pa)
      n_bauer   = 0.53d0            ! Exponent n
c
      gamma_w   = rho_w * g_accel
      K_0       = 1.0d0 - sin(mc_phi * pi_const / 180.0d0)
c
      e0d        = e_max - 0.80 * (e_max - e_min)
      e0l        = e_max - 0.20 * (e_max - e_min)
c
      e0exp        = e_max - 0.65 * (e_max - e_min)
c
!     --- Void Ratio Profile (Bauer's Equation) ---
      z_model      = ABS(COORDS(NCRDS)) ! Assuming vertical depth coordinate
      z_prototype  = z_model * N_g
      sigma_v_eff  = gamma_w * z_prototype
      p_eff        = MAX(0.0d0, sigma_v_eff * (1.0d0 + 2.0d0 * K_0) / 3.0d0)
c
      ! Calculation of initial void ratio statev(1)
!     --- Part 1: Initial Void Ratio 0.550 (Dense) or 0.726 (Loose) ---
      if (COORDS(NCRDS) .gt. -0.138d0) then
!          statev(1) = e0l * exp(-(p_eff / hs)**n_bauer)
      else
!          statev(1) = e0d * exp(-(p_eff / hs)**n_bauer)
      end if 
c
      statev(1) = e0exp * exp(-(3.0 * p_eff / hs)**n_bauer)
c
c     Keep initial intergranular strain as in original sdvini.f (do not alter)
c      statev(1+1) = -0.0001d0
c      statev(1+2) = -0.0001d0
      statev(1+3) = -0.0001d0
c
      RETURN
      END
