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
!=======================================================================================================
! VUMAT_dry_Staubach
!
! Dry / uncoupled explicit VUMAT interface for the hypoplastic model with
! intergranular strain (HPP_Staubach_explicit_noclamp.f).
!
! Derived from VUMAT_HMC_Staubach_Abq2023.f (P. Staubach, GPLv3).
! All hydro-mechanical coupling has been removed:
!   - no hydrostatic / excess pore-water pressure,
!   - no use of the temperature DOF as pore-pressure carrier,
!   - no divergence-of-acceleration source term in enerInelas.
! Total stress = effective stress. Intended for ordinary Lagrangian
! continuum elements in *DYNAMIC, EXPLICIT.
!
! The state-variable layout of the original suite is retained so that
! post-processing scripts and SDV numbering stay valid.
!=======================================================================================================
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
c Variable declaration
c
      dimension props(nprops), density(nblock), coordMp(nblock,*),
     &  charLength(nblock),dtArray(2*(nblock)+1),
     &  strainInc(nblock, ndir+nshr),
     &  relSpinInc(nblock,nshr), tempOld(nblock),
     &  stretchOld(nblock,ndir+nshr),
     &  defGradOld(nblock, ndir+nshr+nshr),
     &  fieldOld(nblock,nfieldv), stressOld(nblock,ndir+nshr),
     &  stateOld(nblock,nstatev), enerInternOld(nblock),
     &  enerInelasOld(nblock), tempNew(nblock),
     &  stretchNew(nblock,ndir+nshr),
     &  defgradNew(nblock,ndir+nshr+nshr),
     &  fieldNew(nblock,nfieldv),
     &  stressNew(nblock,ndir+nshr), stateNew(nblock,nstatev),
     &  enerInternNew(nblock), enerInelasNew(nblock)

      character*80 cmname

      integer ntens, kinc, kstep
      integer i, iblock

      double precision time(2), predef(1), drot(3,3), dpred(1)
      double precision dfgrd0(3,3), dfgrd1(3,3)
      double precision tr_dstran, stressPower
      double precision stress(ndir+nshr), statev(nstatev)
      double precision ddsdde(ndir+nshr,ndir+nshr), ddsddt(ndir+nshr)
      double precision drplde(ndir+nshr), dstran(ndir+nshr)
      double precision stran(ndir+nshr), coords(3)

      double precision drpldt
      double precision dtime, dt
      double precision mat_props(nprops)
      double precision probeE, probeNu

      integer isfirstinc, ndi, nshrmat, nmat_props, nstatev_mat

!*************************************************************************
!! Output variables (unchanged layout, ntens = 6 in 3D)
!! statev(1)            : void ratio
!! statev(2:1+ntens)    : intergranular strain
!! statev(2+ntens:1+2*ntens) : viscous stress
!! statev(3+2*ntens)    : mean effective stress
!! statev(4+2*ntens)    : projection flag
!! statev(23)           : trace of strain increment (volumetric)
!! statev(24)           : hydrostatic pore pressure  -> always 0 (dry)
!! statev(25)           : excess pore pressure       -> always 0 (dry)
!! statev(26)           : divergence of acceleration -> always 0 (dry)
!! statev(27:26+ntens)  : effective stress ( = total stress here)
!*************************************************************************

      ntens       = ndir + nshr
      mat_props   = props
      time(1)     = stepTime
      time(2)     = totalTime
      dtime       = dtArray(1)
      dt          = dtArray(1)
      ndi         = ndir
      nshrmat     = nshr
      nmat_props  = nprops
      nstatev_mat = nstatev

      isfirstinc = 0
      if ((time(1).le.0.0d0).and.(time(2).le.0.10d0)) then
        isfirstinc = 1
        KSTEP = 1
        KINC  = 1
      else
        KSTEP = 10
        KINC  = 10
      endif

!*************************************************************************

      do iblock = 1, nblock

        statev(:) = stateOld(iblock,:)

        do i = 1, ndi
          stress(i) = stressOld(iblock,i)
          dstran(i) = strainInc(iblock,i)
          coords(i) = coordMp(iblock,i)
        enddo

c       Abaqus/Explicit shear order is 12, 23, 13 whereas the UMAT
c       expects 12, 13, 23. Shear strains are converted from tensorial
c       to engineering measure.
        stress(4) = stressOld(iblock,4)
        dstran(4) = 2.0d0 * strainInc(iblock,4)

        if (nshr > 1) then
          stress(6) = stressOld(iblock,5)
          stress(5) = stressOld(iblock,6)
          dstran(5) = 2.0d0 * strainInc(iblock,6)
          dstran(6) = 2.0d0 * strainInc(iblock,5)
        endif

c       Volumetric strain increment, kept for output only
        tr_dstran = 0.0d0
        do i = 1, ndi
          tr_dstran = tr_dstran + dstran(i)
        enddo

c       No pore water: these entries are held at zero
        statev(24) = 0.0d0
        statev(25) = 0.0d0
        statev(26) = 0.0d0

        if (isfirstinc == 1) then

c         Abaqus performs an initial dummy call to check the material.
c         The linear elastic response returned here is used ONLY to
c         estimate the initial stable time increment (Delta_t). The
c         branch fires only at the data-check probe call (totalTime
c         = 0); with this job's STEP 3 ORIGIN 2.0000 the second
c         condition (time(2).le.0.10) can never hold during the
c         solution, so no elastic response can leak into the
c         analysis.
c
c         Probe modulus derivation (SI units: Pa):
c           settled hypoplastic Delta_t ~ 1.2E-06 s for L_min
c           ~ 4.0E-04 m  ->  c = L_min/Delta_t ~ 333 m/s
c           -> constrained modulus M = rho*c^2 = 1651.6*333^2
c              ~ 1.83E+08 Pa
c           -> E = M*(1+nu)*(1-2*nu)/(1-nu) ~ 1.36E+08 Pa at nu=0.3
c         probeE = 3.0E+08 Pa is deliberately stiffer than that:
c           erring stiff costs runtime linearly (initial estimate
c           ~8E-07 s vs settled ~1.2E-06 s), erring soft is fatal
c           (the initial estimate then overshoots and the increment
c           collapses). nu = 0.3 is unchanged.
c
c         NOTE: this subroutine may be shared with other analyses.
c         If the model units or L_min differ, re-derive probeE for
c         that analysis before relying on the initial Delta_t
c         estimate.
          probeE  = 3.0d8
          probeNu = 0.3d0
          mat_props(1) = probeE
          mat_props(2) = probeNu

          call UMATElastic(stress,statev,ddsdde,0,0,0,
     &      0,ddsddt,drplde,drpldt,
     &      stran,dstran,time,dtime,0,0,predef,dpred,cmname,
     &      ndi,nshrmat,ntens,nstatev_mat,mat_props,nmat_props,coords,
     &      drot,1,0,dfgrd0,dfgrd1,1,0,0,0,kstep,kinc)

        else

          call umat(stress,statev,ddsdde,0,0,0,
     &      0,ddsddt,drplde,drpldt,
     &      stran,dstran,time,dtime,0,0,predef,dpred,cmname,
     &      ndi,nshrmat,ntens,nstatev_mat,mat_props,nmat_props,coords,
     &      drot,1,0,dfgrd0,dfgrd1,1,0,0,0,kstep,kinc)

        endif

        statev(23) = tr_dstran
        statev(27:26+ntens) = stress

c       Return stress to Abaqus (total = effective in the dry case)
        do i = 1, ndi
          stressNew(iblock,i) = stress(i)
        enddo

        stressNew(iblock,4) = stress(4)

        if (nshr > 1) then
          stressNew(iblock,6) = stress(5)
          stressNew(iblock,5) = stress(6)
        endif

c       Internal energy per unit mass. enerInelas is no longer abused as
c       a pore-pressure source term, so it is simply carried over.
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
        enerInelasNew(iblock) = enerInelasOld(iblock)

        stateNew(iblock,:) = statev(:)

      enddo

      end

!=======================================================================================================
! Linear elastic routine used for the initial check increment only.
! Identical to the one shipped with the original suite.
!=======================================================================================================
      SUBROUTINE UMATElastic(STRESS,STATEV,DDSDDE,SSE,SPD,SCD,
     1 RPL,DDSDDT,DRPLDE,DRPLDT,
     2 STRAN,DSTRAN,TIME,DTIME,TEMP,DTEMP,PREDEF,DPRED,CMNAME,
     3 NDI,NSHR,NTENS,NSTATEV,PROPSU,NPROPS,COORDS,DROT,PNEWDT,
     4 CELENT,DFGRD0,DFGRD1,NOEL,NPT,LAYER,KSPT,KSTEP,KINC)
C
      CHARACTER*80 CMNAME
      DIMENSION STATEV(NSTATEV),
     1 DDSDDE(NTENS,NTENS),DDSDDT(NTENS),DRPLDE(NTENS),
     2 STRAN(NTENS),TIME(2),PREDEF(1),DPRED(1),
     3 COORDS(3),DROT(3,3),DFGRD0(3,3),DFGRD1(3,3)
C
      real*8 PROPSU(nprops),STRESS(NTENS),DSTRAN(NTENS)
      PARAMETER (ONE=1.0D0, TWO=2.0D0)
      E=PROPSU(1)
      ANU=PROPSU(2)
      ALAMDA=ANU*E/ (ONE+ANU)/(ONE-TWO*ANU)
      AMU=E/TWO/(ONE+ANU)

      DO I=1,NTENS
       DO J=1,NTENS
        DDSDDE(I,J)=0.0D0
       ENDDO
      ENDDO
      DDSDDE(1,1)=ALAMDA+TWO*AMU
      DDSDDE(2,2)=DDSDDE(1,1)
      DDSDDE(3,3)=DDSDDE(1,1)
      DDSDDE(4,4)=AMU
      if (ntens==6) then
      DDSDDE(5,5)=AMU
      DDSDDE(6,6)=AMU
      endif
      DDSDDE(1,2)=ALAMDA
      DDSDDE(1,3)=ALAMDA
      DDSDDE(2,3)=ALAMDA
      DDSDDE(2,1)=DDSDDE(1,2)
      DDSDDE(3,1)=DDSDDE(1,3)
      DDSDDE(3,2)=DDSDDE(2,3)
C
      DO I=1,NTENS
        DO J=1,NTENS
        STRESS(I)=STRESS(I)+DDSDDE(I,J)*DSTRAN(J)
        ENDDO
      ENDDO

      RETURN
      END
