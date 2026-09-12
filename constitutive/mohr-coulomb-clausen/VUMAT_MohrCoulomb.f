!=======================================================================
! VUMAT_MohrCoulomb
!
! Abaqus/Explicit VUMAT interface for the linear elastic - perfectly
! plastic Mohr-Coulomb UMAT of Clausen & Andersen (MohrCoulombAbaqus.for).
!
! The constitutive model itself is NOT reimplemented. This file is a thin
! per-block adapter that converts the Abaqus/Explicit calling convention
! into the Abaqus/Standard UMAT convention, calls the unmodified UMAT once
! per material point, and converts the answer back.
!
! It is safe to do this because the Clausen UMAT is a closed-form return
! map: elastic predictor -> exact return in principal stress space. There
! is no Newton iteration, no substepping, no PNEWDT cutback, and the
! consistent tangent DDSDDE is a by-product that the stress update does
! not depend on. In explicit the tangent is simply discarded.
!
! Structure follows VUMAT_dry_Staubach.f from the hypoplasticity suite.
!
! Material constants (*USER MATERIAL, CONSTANTS=5), unchanged from the UMAT:
!   props(1) = E    Young's modulus
!   props(2) = nu   Poisson's ratio
!   props(3) = c    cohesion
!   props(4) = phi  friction angle [degrees]   (must not be 0)
!   props(5) = psi  dilation angle  [degrees]   (must not be 0)
!
! State variables (*DEPVAR 1):
!   statev(1) = region  0 elastic, 1 single surface, 2 compression
!                       meridian, 3 tension meridian, 4 apex
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
      integer i, iblock, kstep, kinc, ischeck

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

      double precision dtime, stressPower
      double precision alam, amu, trde

c     Material constants promoted to double precision. In a SINGLE
c     precision Abaqus/Explicit build vaba_param.inc declares the VUMAT
c     dummy arguments as "implicit real", so props arrives as real*4
c     while the UMAT declares real(8) PROPS(NPROPS). Passing props
c     straight through would reinterpret the bits and silently corrupt
c     E, nu, c, phi and psi. The copy makes the wrapper correct in both
c     single and double precision builds.
      double precision mat_props(nprops)

      ntens       = ndir + nshr
      ndi         = ndir
      nshrmat     = nshr
      nmat_props  = nprops
      nstatev_mat = nstatev

      do i = 1, nprops
        mat_props(i) = props(i)
      enddo

      time(1) = stepTime
      time(2) = totalTime
      dtime   = dtArray(1)

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

c     NOEL/NPT are passed as 0 so the one-off banner write to unit 6 in
c     the UMAT (guarded by NOEL==1 .and. NPT==1) can never fire. Writing
c     to unit 6 from inside a VUMAT is unsafe under domain parallelism.
      kstep = 1
      kinc  = 1

c     Abaqus/Explicit makes an initial data-check call with zero stress
c     and a probe strain increment, and derives the first stable time
c     increment from the stress it gets back. Mohr-Coulomb cannot serve
c     that call: at zero stress with zero cohesion the apex sits at the
c     origin, so the return map would give zero stress back and no wave
c     speed. The branch below answers it with the model's own linear
c     elastic predictor using props(1) and props(2), which is exactly the
c     dilatational wave speed of the material -- so unlike the hypoplastic
c     wrapper no hand-tuned probe modulus is needed here.
c
c     totalTime is the value at the START of the increment, so this is
c     true for the data-check call and for the first real increment of
c     the analysis. At most one increment (order 1e-6 s) is elastic, at
c     t = 0 where the stress state is the initial one.
      ischeck = 0
      if (totalTime .le. 0.0d0) ischeck = 1

      do iblock = 1, nblock

        statev(:) = stateOld(iblock,:)

        do i = 1, ndi
          stress(i) = stressOld(iblock,i)
          dstran(i) = strainInc(iblock,i)
        enddo

c       Component order. Abaqus/Explicit uses 11,22,33,12,23,13 whereas
c       the UMAT expects 11,22,33,12,13,23, so slots 5 and 6 swap.
c       Shear strains are converted from tensorial to engineering measure;
c       shear stresses need no scaling.
        stress(4) = stressOld(iblock,4)
        dstran(4) = 2.0d0 * strainInc(iblock,4)

        if (nshr .gt. 1) then
          stress(5) = stressOld(iblock,6)
          stress(6) = stressOld(iblock,5)
          dstran(5) = 2.0d0 * strainInc(iblock,6)
          dstran(6) = 2.0d0 * strainInc(iblock,5)
        endif

c       No DROT handling: Abaqus/Explicit already supplies stressOld in
c       the corotational frame, and the UMAT ignores DROT in any case.

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

c         NOTE predef(1)/dpred(1): this UMAT declares PREDEF and DPRED as
c         scalars, not as the arrays of the standard UMAT signature, so
c         array elements are passed rather than whole arrays.
          call umat(stress,statev,ddsdde,zsse,zspd,zscd,
     &      zrpl,ddsddt,drplde,zdrpldt,
     &      stran,dstran,time,dtime,ztemp,zdtemp,predef(1),dpred(1),
     &      cmname,
     &      ndi,nshrmat,ntens,nstatev_mat,mat_props,nmat_props,coords,
     &      drot,zpnewdt,zcelent,dfgrd0,dfgrd1,0,0,0,0,kstep,kinc)

        endif

c       Return stress to Abaqus, undoing the slot swap.
        do i = 1, ndi
          stressNew(iblock,i) = stress(i)
        enddo

        stressNew(iblock,4) = stress(4)

        if (nshr .gt. 1) then
          stressNew(iblock,5) = stress(6)
          stressNew(iblock,6) = stress(5)
        endif

        stateNew(iblock,:) = statev(:)

c       Internal energy per unit mass. strainInc is tensorial, so the
c       off-diagonal terms are counted twice (sigma_ij eps_ij summed over
c       both i,j orderings), hence the missing factor 1/2 on the shears.
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

c       Perfectly plastic Mohr-Coulomb dissipates, but the UMAT does not
c       report the dissipated work, so the inelastic energy is carried
c       over unchanged. ALLPD from this material is therefore not
c       meaningful; ALLIE remains correct.
        enerInelasNew(iblock) = enerInelasOld(iblock)

      enddo

      end
