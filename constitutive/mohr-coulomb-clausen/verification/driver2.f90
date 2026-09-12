program driver2
! Test 2: plane strain / axisymmetric (ndir=3, nshr=1, ntens=4), nblock=3.
! Test 3: the totalTime=0 data-check branch returns the correct linear
!         elastic constrained modulus, so Abaqus gets the right wave speed.
  implicit none
  integer, parameter :: nb = 3, ndir = 3, nshr = 1, ntens = 4
  integer, parameter :: nstatev = 1, nfieldv = 1, nprops = 5, nstep = 300

  real(8) :: props(nprops)
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
  real(8) :: defgradOld(nb,5), defgradNew(nb,5)
  real(8) :: fieldOld(nb,nfieldv), fieldNew(nb,nfieldv)
  real(8) :: enerInternOld(nb), enerInternNew(nb)
  real(8) :: enerInelasOld(nb), enerInelasNew(nb)
  real(8) :: gapmax, gap, scale, E, nu, Mexp, Mgot
  integer :: k, i, j, lanneal, maxreg

  props = [50.0d6, 0.30d0, 1.0d3, 30.0d0, 5.0d0]
  cmname = 'MC'
  E = props(1); nu = props(2)

  sse=0; spd=0; scd=0; rpl=0; drpldt=0; temp=0; dtemp=0; predef=0; dpred=0
  pnewdt=1; celent=0; stranU=0; coords=0
  drot=0; drot(1,1)=1; drot(2,2)=1; drot(3,3)=1; dfgrd0=0; dfgrd1=0
  dtArray=1.0d-6; coordMp=0; charLength=1; density=2000
  relSpinInc=0; tempOld=0; tempNew=0; stretchOld=0; stretchNew=0
  defgradOld=0; defgradNew=0; fieldOld=0; fieldNew=0
  enerInternOld=0; enerInelasOld=0; lanneal=0

  !=================== Test 2: plane strain, nblock=3 ===================
  sU = 0.0d0; sU(1:3) = -100.0d3; statU = 0.0d0
  stressOld = 0.0d0
  do j = 1, nb
     stressOld(j,1:3) = -100.0d3
  end do
  stateOld = 0.0d0
  gapmax = 0.0d0
  maxreg = 0

  do k = 1, nstep
     if (k > nstep/2) then; scale = -1.0d0; else; scale = 1.0d0; end if

     dstranU = scale * [-8.0d-5, 2.4d-5, 0.0d0, 4.8d-5]   ! engineering gamma_12
     time(1) = (k-1)*1.0d-6; time(2) = time(1)
     call umat(sU, statU, ddsdde, sse, spd, scd, rpl, ddsddt, drplde, drpldt, &
               stranU, dstranU, time, 1.0d-6, temp, dtemp, predef, dpred, cmname, &
               ndir, nshr, ntens, nstatev, props, nprops, coords, drot, pnewdt, &
               celent, dfgrd0, dfgrd1, 1, 1, 0, 0, 1, k)

     do j = 1, nb
        strainInc(j,1:3) = scale * [-8.0d-5, 2.4d-5, 0.0d0]
        strainInc(j,4)   = scale * 4.8d-5 * 0.5d0          ! tensorial eps_12
     end do

     call vumat(nb, ndir, nshr, nstatev, nfieldv, nprops, lanneal, &
                time(1)+1.0d-6, time(2)+1.0d-6, dtArray, cmname, coordMp, charLength, &
                props, density, strainInc, relSpinInc, &
                tempOld, stretchOld, defgradOld, fieldOld, &
                stressOld, stateOld, enerInternOld, enerInelasOld, &
                tempNew, stretchNew, defgradNew, fieldNew, &
                stressNew, stateNew, enerInternNew, enerInelasNew)

     stressOld = stressNew; stateOld = stateNew
     enerInternOld = enerInternNew; enerInelasOld = enerInelasNew

     do j = 1, nb
        if (nint(statU(1)) > maxreg) maxreg = nint(statU(1))
        do i = 1, ntens
           gap = abs(stressNew(j,i) - sU(i))
           if (gap > gapmax) gapmax = gap
        end do
     end do
  end do

  write(*,'(a,i2,a,es12.5,a)') 'Test 2  plane strain (ntens=4, nblock=', nb, &
       '): max |dSig| = ', gapmax, ' Pa'
  write(*,'(a,i2)') '        max region reached = ', maxreg

  !=================== Test 3: data-check branch ===================
  ! totalTime = 0, uniaxial strain probe -> expect constrained modulus M.
  stressOld = 0.0d0; stateOld = 0.0d0; strainInc = 0.0d0
  strainInc(1,1) = 1.0d-6
  call vumat(nb, ndir, nshr, nstatev, nfieldv, nprops, lanneal, &
             0.0d0, 0.0d0, dtArray, cmname, coordMp, charLength, &
             props, density, strainInc, relSpinInc, &
             tempOld, stretchOld, defgradOld, fieldOld, &
             stressOld, stateOld, enerInternOld, enerInelasOld, &
             tempNew, stretchNew, defgradNew, fieldNew, &
             stressNew, stateNew, enerInternNew, enerInelasNew)

  Mexp = E*(1.0d0-nu)/((1.0d0+nu)*(1.0d0-2.0d0*nu))
  Mgot = stressNew(1,1) / 1.0d-6
  write(*,'(a,es12.5,a,es12.5)') 'Test 3  probe modulus: got ', Mgot, '  expected M = ', Mexp
  write(*,'(a,es12.5)')          '        relative error = ', abs(Mgot-Mexp)/Mexp
  write(*,'(a,f8.2,a)')          '        -> dilatational wave speed ', sqrt(Mexp/2000.0d0), ' m/s'

  if (gapmax < 1.0d-6 .and. abs(Mgot-Mexp)/Mexp < 1.0d-12) then
     write(*,*) 'PASS'
  else
     write(*,*) 'FAIL'
  end if
end program driver2
