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
! See PROVENANCE.md in this directory.
!=======================================================================================================
      SUBROUTINE VUAMP(
     *     ampName, time, ampValueOld, dt, nprops, props, nSvars, 
     *     svars, lFlagsInfo, nSensor, sensorValues, sensorNames,	
     *	 jSensorLookUpTable,
     *     AmpValueNew,
     *     lFlagsDefine,
     *     AmpDerivative, AmpSecDerivative, AmpIncIntegral)

      INCLUDE 'VABA_PARAM.INC'

C     time indices
      parameter (iStepTime        = 1,
     *           iTotalTime       = 2,
     *           nTime            = 2)
C     flags passed in for information
      parameter (iInitialization   = 1,
     *           iRegularInc       = 2,
     *           ikStep            = 3,
     *           nFlagsInfo        = 3)
C     optional flags to be defined
      parameter (iComputeDeriv     = 1,
     *           iComputeSecDeriv  = 2,
     *           iComputeInteg     = 3,
     *           iStopAnalysis     = 4,
     *           iConcludeStep     = 5,
     *           nFlagsDefine      = 5)
      dimension time(nTime), lFlagsInfo(nFlagsInfo),
     *          lFlagsDefine(nFlagsDefine),
     *          sensorValues(nSensor),
     *          props(nprops),
     *          sVars(nSvars)

      character*80 sensorNames(nSensor)
      character*80 ampName
      dimension jSensorLookUpTable(*)

      real*8 omega,sinus
!!--------------------------------------------------------------------
      omega = 3.14d0 * 2.0d0 * 0.65d0
      sinus = Sin(omega*time(1))
      if(sinus>0.96d0) then
	    AmpValueNew = 300.0d0
      else 
	    AmpValueNew = 0.0d0
      endif
	  
      RETURN
      END	  