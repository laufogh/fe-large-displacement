program driver_sp
! Test 4: SINGLE PRECISION build. All VUMAT-facing arrays are real(4),
! exactly as Abaqus/Explicit passes them when vaba_param.inc resolves to
! vaba_param_sp.inc ("implicit real"). This is the configuration in which
! passing props straight to the real(8) UMAT corrupts the constants.
  implicit none
  integer, parameter :: nb=1, ndir=3, nshr=3, ntens=6
  integer, parameter :: nstatev=1, nfieldv=1, nprops=5

  real(4) :: props(nprops), density(nb), coordMp(nb,3), charLength(nb)
  real(4) :: dtArray(2*nb+1), strainInc(nb,ntens), relSpinInc(nb,nshr)
  real(4) :: tempOld(nb), stretchOld(nb,ntens), defgradOld(nb,9)
  real(4) :: fieldOld(nb,nfieldv), stressOld(nb,ntens), stateOld(nb,nstatev)
  real(4) :: enerInternOld(nb), enerInelasOld(nb)
  real(4) :: tempNew(nb), stretchNew(nb,ntens), defgradNew(nb,9)
  real(4) :: fieldNew(nb,nfieldv), stressNew(nb,ntens), stateNew(nb,nstatev)
  real(4) :: enerInternNew(nb), enerInelasNew(nb)
  character(80) :: cmname
  integer :: lanneal, k, nfail
  real(8) :: E, nu, coh, phi, kf, sigc, Mexp, Mgot, resid, scal, tol

  E = 50.0d6; nu = 0.30d0; coh = 1.0d3; phi = 30.0d0
  props = [real(E,4), real(nu,4), real(coh,4), real(phi,4), 5.0_4]
  cmname = 'MC'
  nfail = 0

  density=2000.0_4; coordMp=0.0_4; charLength=1.0_4; dtArray=1.0e-6_4
  relSpinInc=0.0_4; tempOld=0.0_4; tempNew=0.0_4
  stretchOld=0.0_4; stretchNew=0.0_4; defgradOld=0.0_4; defgradNew=0.0_4
  fieldOld=0.0_4; fieldNew=0.0_4
  enerInternOld=0.0_4; enerInelasOld=0.0_4; lanneal=0

  !---- 4a: probe branch returns the constrained modulus ----
  stressOld=0.0_4; stateOld=0.0_4; strainInc=0.0_4
  strainInc(1,1) = 1.0e-6_4
  call vumat(nb,ndir,nshr,nstatev,nfieldv,nprops,lanneal, &
             0.0_4, 0.0_4, dtArray, cmname, coordMp, charLength, &
             props, density, strainInc, relSpinInc, &
             tempOld, stretchOld, defgradOld, fieldOld, &
             stressOld, stateOld, enerInternOld, enerInelasOld, &
             tempNew, stretchNew, defgradNew, fieldNew, &
             stressNew, stateNew, enerInternNew, enerInelasNew)

  Mexp = E*(1.0d0-nu)/((1.0d0+nu)*(1.0d0-2.0d0*nu))
  Mgot = real(stressNew(1,1),8) / 1.0d-6
  write(*,'(a,es13.6,a,es13.6)') '4a probe modulus : got ', Mgot, '  expect ', Mexp
  if (abs(Mgot-Mexp)/Mexp > 1.0d-5) then
     nfail = nfail + 1; write(*,*) '   -> FAIL (E or nu corrupted)'
  else
     write(*,*) '   -> ok'
  end if

  !---- 4b: drive to yield, check the Mohr-Coulomb criterion is honoured ----
  ! Triaxial compression, no shear, so principal stresses are the diagonal.
  stressOld = 0.0_4; stressOld(1,1:3) = -100.0e3_4
  stateOld = 0.0_4; strainInc = 0.0_4
  do k = 1, 400
     strainInc(1,1) = -2.0e-5_4
     strainInc(1,2) =  0.6e-5_4
     strainInc(1,3) =  0.6e-5_4
     call vumat(nb,ndir,nshr,nstatev,nfieldv,nprops,lanneal, &
                real(k,4)*1.0e-6_4, real(k,4)*1.0e-6_4, dtArray, cmname, &
                coordMp, charLength, props, density, strainInc, relSpinInc, &
                tempOld, stretchOld, defgradOld, fieldOld, &
                stressOld, stateOld, enerInternOld, enerInelasOld, &
                tempNew, stretchNew, defgradNew, fieldNew, &
                stressNew, stateNew, enerInternNew, enerInelasNew)
     stressOld = stressNew; stateOld = stateNew
     enerInternOld = enerInternNew; enerInelasOld = enerInelasNew
  end do

  kf   = (1.0d0+sin(phi*acos(-1.0d0)/180.0d0)) &
       / (1.0d0-sin(phi*acos(-1.0d0)/180.0d0))
  sigc = 2.0d0*coh*sqrt(kf)
  ! sigma1 = lateral (least compressive), sigma3 = axial (most compressive)
  resid = kf*real(stressNew(1,2),8) - real(stressNew(1,1),8) - sigc
  scal  = maxval(abs(real(stressNew(1,1:3),8)))
  tol   = 1.0d-4 * scal

  write(*,'(a,i2)')             '4b region flag   : ', nint(real(stateNew(1,1),8))
  write(*,'(a,es13.6,a,es13.6)')'4b yield residual: ', resid, '   tol ', tol
  write(*,'(a,f7.4,a,f9.2)')    '   implied k = ', &
       real(stressNew(1,1),8)/real(stressNew(1,2),8), &
       '  (expect 3.0 for phi=30) , sigma_c = ', sigc
  if (nint(real(stateNew(1,1),8)) == 0) then
     nfail = nfail + 1; write(*,*) '   -> FAIL (never yielded)'
  else if (abs(resid) > tol) then
     nfail = nfail + 1; write(*,*) '   -> FAIL (c or phi corrupted)'
  else
     write(*,*) '   -> ok'
  end if

  write(*,*)
  if (nfail == 0) then
     write(*,*) 'PASS: single precision build reads the material constants correctly.'
  else
     write(*,'(a,i2,a)') ' FAIL: ', nfail, ' single-precision check(s) failed.'
     call exit(1)
  end if
end program driver_sp
