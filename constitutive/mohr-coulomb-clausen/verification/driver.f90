program driver
! Drive one identical physical strain path twice:
!   (a) straight through the Clausen UMAT   (order 11,22,33,12,13,23; engineering shear)
!   (b) through VUMAT_MohrCoulomb           (order 11,22,33,12,23,13; tensorial shear)
! and compare. Shear is non-zero in all three components so the 5<->6 slot
! swap and the factor-2 strain conversion are both exercised.
  implicit none

  integer, parameter :: nb = 1, ndir = 3, nshr = 3, ntens = 6
  integer, parameter :: nstatev = 1, nfieldv = 1, nprops = 5, nstep = 400

  real(8) :: props(nprops)
  real(8) :: d1, d2, d3, g12, g13, g23
  real(8) :: sU(ntens), dstranU(ntens), stranU(ntens), statU(nstatev)
  real(8) :: ddsdde(ntens,ntens), ddsddt(ntens), drplde(ntens)
  real(8) :: time(2), coords(3), drot(3,3), dfgrd0(3,3), dfgrd1(3,3)
  real(8) :: sse, spd, scd, rpl, drpldt, temp, dtemp, predef, dpred
  real(8) :: pnewdt, celent
  character(80) :: cmname

  real(8) :: stressOld(nb,ntens), stressNew(nb,ntens)
  real(8) :: stateOld(nb,nstatev), stateNew(nb,nstatev)
  real(8) :: strainInc(nb,ntens), relSpinInc(nb,nshr)
  real(8) :: dtArray(2*nb+1), coordMp(nb,3), charLength(nb), density(nb)
  real(8) :: tempOld(nb), tempNew(nb), stretchOld(nb,ntens), stretchNew(nb,ntens)
  real(8) :: defgradOld(nb,9), defgradNew(nb,9)
  real(8) :: fieldOld(nb,nfieldv), fieldNew(nb,nfieldv)
  real(8) :: enerInternOld(nb), enerInternNew(nb)
  real(8) :: enerInelasOld(nb), enerInelasNew(nb)
  real(8) :: sVmapped(ntens), gapmax, gap, scale
  integer :: k, i, lanneal

  props = [50.0d6, 0.30d0, 1.0d3, 30.0d0, 5.0d0]
  cmname = 'MC'

  ! isotropic start at -100 kPa (compression negative)
  sU = 0.0d0
  sU(1:3) = -100.0d3
  statU = 0.0d0
  stressOld = 0.0d0
  stressOld(1,1:3) = -100.0d3
  stateOld = 0.0d0

  ! physical increment: axial compression, lateral extension, plus shear
  d1  = -2.0d-5
  d2  =  0.6d-5
  d3  =  0.6d-5
  g12 =  1.2d-5
  g13 = -0.8d-5
  g23 =  0.5d-5

  ! UMAT-side constants
  sse = 0.0d0; spd = 0.0d0; scd = 0.0d0; rpl = 0.0d0; drpldt = 0.0d0
  temp = 0.0d0; dtemp = 0.0d0; predef = 0.0d0; dpred = 0.0d0
  pnewdt = 1.0d0; celent = 0.0d0
  stranU = 0.0d0; coords = 0.0d0
  drot = 0.0d0; drot(1,1) = 1.0d0; drot(2,2) = 1.0d0; drot(3,3) = 1.0d0
  dfgrd0 = 0.0d0; dfgrd1 = 0.0d0

  ! VUMAT-side constants
  dtArray = 1.0d-6
  coordMp = 0.0d0; charLength = 1.0d0; density = 2000.0d0
  relSpinInc = 0.0d0; tempOld = 0.0d0; tempNew = 0.0d0
  stretchOld = 0.0d0; stretchNew = 0.0d0
  defgradOld = 0.0d0; defgradNew = 0.0d0
  fieldOld = 0.0d0; fieldNew = 0.0d0
  enerInternOld = 0.0d0; enerInelasOld = 0.0d0
  lanneal = 0

  gapmax = 0.0d0

  do k = 1, nstep

     ! reverse the path halfway to exercise elastic unloading off the surface
     if (k > nstep/2) then
        scale = -1.0d0
     else
        scale =  1.0d0
     end if

     ! ---- (a) UMAT: 11,22,33,12,13,23, engineering shear ----
     dstranU = scale * [d1, d2, d3, g12, g13, g23]
     time(1) = (k-1) * 1.0d-6
     time(2) = time(1)
     call umat(sU, statU, ddsdde, sse, spd, scd, rpl, ddsddt, drplde, drpldt, &
               stranU, dstranU, time, 1.0d-6, temp, dtemp, predef, dpred, cmname, &
               ndir, nshr, ntens, nstatev, props, nprops, coords, drot, pnewdt, &
               celent, dfgrd0, dfgrd1, 1, 1, 0, 0, 1, k)

     ! ---- (b) VUMAT: 11,22,33,12,23,13, tensorial shear ----
     strainInc(1,1) = scale * d1
     strainInc(1,2) = scale * d2
     strainInc(1,3) = scale * d3
     strainInc(1,4) = scale * g12 * 0.5d0
     strainInc(1,5) = scale * g23 * 0.5d0
     strainInc(1,6) = scale * g13 * 0.5d0

     ! totalTime > 0 so the data-check elastic branch is not taken
     call vumat(nb, ndir, nshr, nstatev, nfieldv, nprops, lanneal, &
                time(1)+1.0d-6, time(2)+1.0d-6, dtArray, cmname, coordMp, charLength, &
                props, density, strainInc, relSpinInc, &
                tempOld, stretchOld, defgradOld, fieldOld, &
                stressOld, stateOld, enerInternOld, enerInelasOld, &
                tempNew, stretchNew, defgradNew, fieldNew, &
                stressNew, stateNew, enerInternNew, enerInelasNew)

     stressOld = stressNew
     stateOld  = stateNew
     enerInternOld = enerInternNew
     enerInelasOld = enerInelasNew

     ! map VUMAT result back to UMAT ordering and compare
     sVmapped(1:4) = stressNew(1,1:4)
     sVmapped(5)   = stressNew(1,6)   ! 13
     sVmapped(6)   = stressNew(1,5)   ! 23

     do i = 1, ntens
        gap = abs(sVmapped(i) - sU(i))
        if (gap > gapmax) gapmax = gap
     end do

     if (mod(k,100) == 0 .or. k == 1) then
        write(*,'(a,i4,a,i2,a,6(1x,es11.4))') 'step', k, '  region=', &
             nint(statU(1)), '  sig(UMAT)=', sU
        write(*,'(a,es11.4)')                 '                              max|dSig| so far = ', gapmax
     end if
  end do

  write(*,*)
  write(*,'(a,es12.5,a)') 'max |stress difference| over path = ', gapmax, ' Pa'
  write(*,'(a,es12.5)')   'relative to |sig| ~ 1e5 Pa        = ', gapmax/1.0d5
  if (gapmax < 1.0d-6) then
     write(*,*) 'PASS: VUMAT reproduces UMAT bit-for-bit within roundoff.'
  else
     write(*,*) 'FAIL: adapter changes the answer.'
  end if
end program driver
