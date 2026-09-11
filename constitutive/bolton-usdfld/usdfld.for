      SUBROUTINE USDFLD(FIELD,STATEV,PNEWDT,DIRECT,T,CELENT,
     1 TIME,DTIME,CMNAME,ORNAME,NFIELD,NSTATV,NOEL,NPT,LAYER,
     2 KSPT,KSTEP,KINC,NDI,NSHR,COORD,JMAC,JMATYP,MATLAYO,LACCFLA)
C
C     User subroutine to define field variables for Bolton's method
C     FIELD(1): mean effective stress sigma_m [Pa] (compression positive)
C     FIELD(2): friction angle phi [degrees]
C     FIELD(3): dilation angle psi [degrees]
C
C     STEP CONTROL:
C     - KSTEP = 1: Geostatic step - calculate field variables from stress + store in state variables
C     - KSTEP = 2: Loading step - use field variables directly from state variables
C     - Other steps: keep initial values
C
      INCLUDE 'ABA_PARAM.INC'
C
      CHARACTER*80 CMNAME,ORNAME
      CHARACTER*3  FLGRAY(15)
      REAL*8 FIELD(NFIELD),STATEV(NSTATV),DIRECT(3,3),
     1 T(3,3),TIME(2)
      REAL*8 ARRAY(15)
      INTEGER JARRAY(15)
      DIMENSION JMAC(*),JMATYP(*),COORD(*)

C----- Locals (ALL declarations before any executable statements)
      INTEGER I, J, JRCD
      REAL*8  S(6)
      REAL*8  S_TENSOR(3,3)
      REAL*8  I1, SIGMA_M, PP
      REAL*8  PHI_CV, ID, B_PARAM, Q_PARAM, R_PARAM
      REAL*8  IR, PSI_PEAK, PHI_PEAK, P_KPA
      REAL*8  PI

C----- Bolton parameters (Ottawa-65 sand)
      PARAMETER (PHI_CV = 32.0D0)      ! Critical state friction angle [deg]
      PARAMETER (ID = 0.5D0)           ! Relative density [-]
      PARAMETER (Q_PARAM = 10.0D0)     ! Bolton parameter Q [-]
      PARAMETER (R_PARAM = 1.0D0)      ! Bolton parameter R [-]
      PARAMETER (PI = 3.14159265358979D0)

C======================================================================
C     STEP CONTROL
C======================================================================
      IF (KSTEP .EQ. 1) THEN
C           GEOSTATIC STEP: Calculate field variables from stress and store in state variables
            GOTO 100
      ELSE IF (KSTEP .GE. 2) THEN
C         LOADING STEP: Use field variables directly from state variables
            FIELD(1) = STATEV(1)  ! Mean effective stress from geostatic
            FIELD(2) = STATEV(2)  ! Friction angle from geostatic
            FIELD(3) = STATEV(3)  ! Dilation angle from geostatic
            RETURN
      END IF

C======================================================================
C     GEOSTATIC STEP: Calculate stress-based field variables
C======================================================================
  100 CONTINUE
C     Call GETVRM to get stress components
      CALL GETVRM('S',ARRAY,JARRAY,FLGRAY,JRCD,JMAC,JMATYP,
     1            MATLAYO,LACCFLA)
      
C     Copy stress components from ARRAY to S
      DO I = 1, 6
         S(I) = ARRAY(I)
      END DO

C----- Convert Voigt stress to symmetric 3x3 tensor
      DO I = 1,3
         DO J = 1,3
            S_TENSOR(I,J) = 0.D0
         END DO
      END DO

      S_TENSOR(1,1)=S(1)
      S_TENSOR(2,2)=S(2)
      S_TENSOR(3,3)=S(3)
      S_TENSOR(1,2)=S(4)  ;  S_TENSOR(2,1)=S(4)
      S_TENSOR(1,3)=S(5)  ;  S_TENSOR(3,1)=S(5)
      S_TENSOR(2,3)=S(6)  ;  S_TENSOR(3,2)=S(6)

C----- First invariant I1 and mean stress
      I1 = S_TENSOR(1,1) + S_TENSOR(2,2) + S_TENSOR(3,3)

C----- Pore pressure (drained default = 0)
      PP = 0.D0

C----- Mean effective stress (Abaqus tension+ -> geo compression+)
      SIGMA_M = -I1/3.D0 - PP

C======================================================================
C     Bolton's method: Calculate friction and dilation angles
C======================================================================
C     Convert mean stress to kPa for Bolton's equations
      P_KPA = MAX(0.1D0, SIGMA_M / 1000.D0)  ! Minimum 0.1 kPa

C     Calculate relative dilatancy index IR (Bolton 1986)
C     IR = ID * (Q - ln(p')) - R, where p' is in kPa
C     Note: LOG() in Fortran is natural logarithm (ln)
      IR = ID * (Q_PARAM - LOG(P_KPA)) - R_PARAM
      
C     Apply bounds to IR (typically 0 to 4)
      IR = MAX(0.D0, MIN(4.D0, IR))

C     Calculate peak dilation angle (Bolton 1986)
C     psi = 1.25 * 3 * IR = 3.75 * IR
      PSI_PEAK = 3.75D0 * IR

C     Calculate peak friction angle for plane strain (Bolton 1986, Eq. 16)
C     phi_peak = phi_cv + 3 * IR
      PHI_PEAK = PHI_CV + 3.0D0 * IR

C======================================================================
C     Store field variables and state variables
C======================================================================
      FIELD(1) = MAX(100.D0, SIGMA_M)  ! Mean stress [Pa], minimum 0.1 kPa
      FIELD(2) = PHI_PEAK              ! Friction angle [degrees]
      FIELD(3) = PSI_PEAK              ! Dilation angle [degrees]

C     Store in state variables for use in loading step
      STATEV(1) = FIELD(1)         ! Store mean effective stress
      STATEV(2) = FIELD(2)         ! Store friction angle
      STATEV(3) = FIELD(3)         ! Store dilation angle

      RETURN
      END
