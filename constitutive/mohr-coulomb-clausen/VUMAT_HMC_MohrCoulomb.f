!=======================================================================
! VUMAT_HMC_MohrCoulomb
!
! Hydro-mechanically coupled Abaqus/Explicit VUMAT for the Clausen
! Mohr-Coulomb UMAT (MohrCoulombAbaqus.for).
!
! The constitutive model is NOT reimplemented. This file is the dry
! adapter VUMAT_MohrCoulomb.f plus the temperature-DOF / pore-pressure
! instrumentation from VUMAT_HMC_Staubach_Abq2023.f (P. Staubach,
! GPLv3). Abaqus/Explicit has no pore-pressure DOF, so the coupled
! temperature-displacement solver is used as a diffusion analogy:
!
!   NT11  (tempOld/tempNew)  <->  excess pore pressure u_w
!   *CONDUCTIVITY            <->  hydraulic conductivity analog
!   *SPECIFIC HEAT           <->  storage analog n/K_w
!   *INELASTIC HEAT FRACTION=1  turns Delta(enerInelas) into the
!                               volumetric source of the heat equation
!
! Reference: Staubach et al., Soils and Foundations 61 (2021)
!   "Vibratory pile driving in water-saturated sand: Back-analysis
!    of model tests using a hydro-mechanically coupled CEL method"
!   https://doi.org/10.1016/j.sandf.2020.11.005
!
! Material constants (*USER MATERIAL, CONSTANTS=5), unchanged:
!   props(1) = E    Young's modulus
!   props(2) = nu   Poisson's ratio
!   props(3) = c    cohesion
!   props(4) = phi  friction angle [degrees]   (must not be 0)
!   props(5) = psi  dilation angle  [degrees]   (must not be 0)
!
! State variables (*DEPVAR 36), layout mirrored from Staubach HMC
! so vusdfld_parallel.f / vufield_parallel.f keep working:
!   statev(1)           MC region (0 elastic, 1-4 yield)
!   statev(23)          trace of strain increment
!   statev(24)          hydrostatic pore pressure
!   statev(25)          excess pore pressure
!   statev(26)          divergence of acceleration
!   statev(27:26+ntens) effective stress (UMAT component order)
!   statev(33)          1 above water table, 2 below
!   statev(34)          cavitation flag
!
! Hydraulic constants below are job parameters (edit to match the
! *CONDUCTIVITY / *SPECIFIC HEAT / *DENSITY block of the .inp).
!=======================================================================
! This file is derived from VUMAT_HMC_Staubach_Abq2023.f, which is
! part of VUMAT_HMC_Staubach and licensed under GPLv3.
!
! VUMAT_HMC_Staubach is free software: you can redistribute it and/or
! modify it under the terms of the GNU General Public License as
! published by the Free Software Foundation, either version 3 of the
! License, or (at your option) any later version.
!=======================================================================
      subroutine vumat(
c Read only (unmodifiable) variables -
     &  nblock, ndir, nshr, nstatev, nfieldv, nprops, lanneal,
     &  stepTime, totalTime, dtArray, cmname, coordMp, charLength,
     &  props, density, strainInc, relSpinInc,
     &  tempOld, stretchOld, defgradOld, fieldOld,
     &  stressOld, stateOld, enerInternOld, enerInelasOld,
     &  tempNew, stretchNew, defgradNew, fieldNew,
c Write only (modifiable) variables -
     &  stressNew, stateNew, enerInternNew, enerInelasNew)
c
      include 'vaba_param.inc'
c
      dimension props(nprops), density(nblock), coordMp(nblock,*),
     &  charLength(nblock), dtArray(2*(nblock)+1),
     &  strainInc(nblock, ndir+nshr),
     &  relSpinInc(nblock,nshr), tempOld(nblock),
     &  stretchOld(nblock,ndir+nshr),
     &  defgradOld(nblock, ndir+nshr+nshr),
     &  fieldOld(nblock,nfieldv), stressOld(nblock,ndir+nshr),
     &  stateOld(nblock,nstatev), enerInternOld(nblock),
     &  enerInelasOld(nblock), tempNew(nblock),
     &  stretchNew(nblock,ndir+nshr),
     &  defgradNew(nblock,ndir+nshr+nshr),
     &  fieldNew(nblock,nfieldv),
     &  stressNew(nblock,ndir+nshr), stateNew(nblock,nstatev),
     &  enerInternNew(nblock), enerInelasNew(nblock)

      character*80 cmname

      integer ntens, ndi, nshrmat, nmat_props, nstatev_mat
      integer i, iblock, kstep, kinc, ischeck, idirg

c     Scratch in UMAT (Abaqus/Standard) layout.
      double precision stress(6), dstran(6), stran(6)
      double precision statev(nstatev)
      double precision ddsdde(6,6), ddsddt(6), drplde(6)
      double precision time(2), coords(3), drot(3,3)
      double precision predef(1), dpred(1)
      double precision dfgrd0(3,3), dfgrd1(3,3)

c     Unused UMAT arguments. Declared as real*8 zeros rather than passed
c     as integer literals, so the types match the UMAT's dummy arguments
c     (MohrCoulombAbaqus.for is implicit none / real(8) throughout).
      double precision zsse, zspd, zscd, zrpl, zdrpldt
      double precision ztemp, zdtemp, zpnewdt, zcelent

      double precision dtime, dt, stressPower
      double precision alam, amu, trde
      double precision tr_dstran, div_acc, dot_pw, source
      double precision KPerm, viscosity, density2, gamma_w
      double precision KO, water_table, dir_grav, cavitation

      double precision mat_props(nprops)

!xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
c     Variables for pore water pressure. Edit together with the
c     *CONDUCTIVITY / *SPECIFIC HEAT / *DENSITY keywords of the deck.
c     Numbers match VUMAT_HMC_Staubach_Abq2023.f / step.inp.
      KPerm       = 1.00d-10
      viscosity   = 1.00d-6
      density2    = 1.8649d0
      gamma_w     = 10.0d0
      KO          = 0.4d0
      water_table = -1.0d0
      dir_grav    = 3.0d0
      cavitation  = -100.0d0
!xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

      ntens       = ndir + nshr
      ndi         = ndir
      nshrmat     = nshr
      nmat_props  = nprops
      nstatev_mat = nstatev
      idirg       = int(dir_grav)

      do i = 1, nprops
        mat_props(i) = props(i)
      enddo

      time(1) = stepTime
      time(2) = totalTime
      dtime   = dtArray(1)
      dt      = dtArray(1)

      zsse    = 0.0d0
      zspd    = 0.0d0
      zscd    = 0.0d0
      zrpl    = 0.0d0
      zdrpldt = 0.0d0
      ztemp   = 0.0d0
      zdtemp  = 0.0d0
      zpnewdt = 1.0d0
      zcelent = 0.0d0

      predef(1) = 0.0d0
      dpred(1)  = 0.0d0
      stran(:)  = 0.0d0
      coords(:) = 0.0d0
      drot(:,:) = 0.0d0
      drot(1,1) = 1.0d0
      drot(2,2) = 1.0d0
      drot(3,3) = 1.0d0
      dfgrd0(:,:) = 0.0d0
      dfgrd1(:,:) = 0.0d0
      stress(:) = 0.0d0
      dstran(:) = 0.0d0

c     NOEL/NPT are passed as 0 so the one-off banner write to unit 6 in
c     the UMAT (guarded by NOEL==1 .and. NPT==1) can never fire.
      kstep = 1
      kinc  = 1

c     Data-check / first-increment elastic branch. Same reason as the
c     dry wrapper: Mohr-Coulomb at zero stress with zero cohesion has
c     no wave speed. Uses the material's own E, nu.
      ischeck = 0
      if (totalTime .le. 0.0d0) ischeck = 1

      do iblock = 1, nblock

        statev(:) = stateOld(iblock,:)

        do i = 1, ndi
          stress(i) = stressOld(iblock,i)
          dstran(i) = strainInc(iblock,i)
        enddo

        coords(1) = coordMp(iblock,1)
        coords(2) = coordMp(iblock,2)
        coords(3) = coordMp(iblock,3)

c       Component order. Abaqus/Explicit uses 11,22,33,12,23,13 whereas
c       the UMAT expects 11,22,33,12,13,23, so slots 5 and 6 swap.
c       Shear strains are converted from tensorial to engineering measure.
        stress(4) = stressOld(iblock,4)
        dstran(4) = 2.0d0 * strainInc(iblock,4)

        if (nshr .gt. 1) then
          stress(5) = stressOld(iblock,6)
          stress(6) = stressOld(iblock,5)
          dstran(5) = 2.0d0 * strainInc(iblock,6)
          dstran(6) = 2.0d0 * strainInc(iblock,5)
        endif

        tr_dstran = 0.0d0
        do i = 1, ndi
          tr_dstran = tr_dstran + dstran(i)
        enddo

        div_acc = 0.0d0
        dot_pw  = 0.0d0
        if (dt .gt. 1.0d-11) then
          div_acc = (tr_dstran - statev(23)) / dt / 2.0d0
     &            + statev(26) / 2.0d0
          dot_pw  = (tempNew(iblock) - tempOld(iblock)) / dt
        endif

c       Hydrostatic pore pressure from the water table. Positive in
c       compression, zero above the phreatic surface.
        statev(24) = (coords(idirg) + water_table) * gamma_w
        if (statev(24) .lt. 0.0d0) statev(24) = 0.0d0
        if (statev(24) .gt. 0.0d0) then
          statev(33) = 2.0d0
        else
          statev(33) = 1.0d0
        endif

c       Total -> effective. Excess pore pressure at the start of the
c       increment; hydrostatic with K0 on the horizontal components,
c       matching Staubach's geostatic initial-condition convention.
c       Abaqus compression-negative, u compression-positive:
c       sigma' = sigma_tot + u.
        if (idirg .eq. 3) then
          stress(1) = stress(1) + statev(25) + statev(24)*KO
          stress(2) = stress(2) + statev(25) + statev(24)*KO
          stress(3) = stress(3) + statev(25) + statev(24)
        else
          stress(1) = stress(1) + statev(25) + statev(24)*KO
          stress(2) = stress(2) + statev(25) + statev(24)
          stress(3) = stress(3) + statev(25) + statev(24)*KO
        endif

c       Excess pore pressure at the end of the increment (Abaqus has
c       already placed the updated NT11 in tempNew).
        statev(25) = statev(25) + dot_pw*dt

        if (ischeck .eq. 1) then

          alam = mat_props(1) * mat_props(2)
     &         / ((1.0d0 + mat_props(2))
     &            * (1.0d0 - 2.0d0*mat_props(2)))
          amu  = mat_props(1) / (2.0d0 * (1.0d0 + mat_props(2)))

          trde = 0.0d0
          do i = 1, ndi
            trde = trde + dstran(i)
          enddo

          do i = 1, ndi
            stress(i) = stress(i) + alam*trde + 2.0d0*amu*dstran(i)
          enddo
          do i = ndi+1, ntens
            stress(i) = stress(i) + amu*dstran(i)
          enddo

        else

          call umat(stress,statev,ddsdde,zsse,zspd,zscd,
     &      zrpl,ddsddt,drplde,zdrpldt,
     &      stran,dstran,time,dtime,ztemp,zdtemp,predef(1),dpred(1),
     &      cmname,
     &      ndi,nshrmat,ntens,nstatev_mat,mat_props,nmat_props,coords,
     &      drot,zpnewdt,zcelent,dfgrd0,dfgrd1,0,0,0,0,kstep,kinc)

        endif

        statev(23) = tr_dstran
        statev(26) = div_acc
        statev(27:26+ntens) = stress(1:ntens)

c       Volumetric source for the heat / pore-pressure equation.
c       With *INELASTIC HEAT FRACTION = 1, Abaqus takes
c       r = rho * (enerInelasNew - enerInelasOld) / dt.
c       The cavitation branch freezes the source (and writes
c       enerInelasNew = enerInelasOld) so Abaqus never sees an
c       uninitialised write-only array. Staubach's original left
c       that assignment out.
        source = -tr_dstran/density2
     &         + div_acc*KPerm/viscosity/density2
        if ( ((statev(25)+statev(24)) .lt. cavitation) .and.
     &       (source .lt. 0.0d0) ) then
          statev(34) = 1.0d0
          enerInelasNew(iblock) = enerInelasOld(iblock)
        else
          enerInelasNew(iblock) = enerInelasOld(iblock) + source
        endif

c       Effective -> total, using excess pore pressure at t_{n+1}.
        if (idirg .eq. 3) then
          stressNew(iblock,1) = stress(1) - statev(25)
     &                        - statev(24)*KO
          stressNew(iblock,2) = stress(2) - statev(25)
     &                        - statev(24)*KO
          stressNew(iblock,3) = stress(3) - statev(25)
     &                        - statev(24)
        else
          stressNew(iblock,1) = stress(1) - statev(25)
     &                        - statev(24)*KO
          stressNew(iblock,2) = stress(2) - statev(25)
     &                        - statev(24)
          stressNew(iblock,3) = stress(3) - statev(25)
     &                        - statev(24)*KO
        endif

        stressNew(iblock,4) = stress(4)

        if (nshr .gt. 1) then
          stressNew(iblock,5) = stress(6)
          stressNew(iblock,6) = stress(5)
        endif

        stateNew(iblock,:) = statev(:)

c       Internal energy per unit mass from the TOTAL stress that
c       Abaqus uses in the momentum residual.
        stressPower = 0.0d0
        do i = 1, ndi
          stressPower = stressPower + 0.5d0
     &      * (stressOld(iblock,i) + stressNew(iblock,i))
     &      * strainInc(iblock,i)
        enddo
        do i = ndi+1, ntens
          stressPower = stressPower
     &      + (stressOld(iblock,i) + stressNew(iblock,i))
     &      * strainInc(iblock,i)
        enddo

        enerInternNew(iblock) = enerInternOld(iblock)
     &                        + stressPower / density(iblock)

      enddo

      end
