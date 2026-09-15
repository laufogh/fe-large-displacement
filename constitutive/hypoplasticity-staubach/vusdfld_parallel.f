!=======================================================================================================
!This file is part of VUMAT_HMC_Staubach.
!
!VUMAT_HMC_Staubach is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License !as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
!
!VUMAT_HMC_Staubach is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied !warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
!
!You should have received a copy of the GNU General Public License along with VUMAT_HMC_Staubach. If not, see <https://www.gnu.org/licenses/>. 
!=======================================================================================================
!
! SUBROUTINE: VUSDFLD
!
!> @author Patrick Staubach, patrick.staubach@yahoo.de
!          Bauhaus University Weimar, Ruhr-University Bochum
!
! DESCRIPTION:
!> @brief Contains the VUSDFLD routine used to calculate effective interface friction according to the paper
!> @brief "Hydro-mechanically coupled CEL analyses with effective contact stresses" https://onlinelibrary.wiley.com/doi/10.1002/nag.3725 International Journal for Numerical and Analytical Methods in Geomechanics 
!
! REVISION HISTORY
!> @date 03.03.2024 - Initial version
!> @date 13.03.2026 - Support of up to 32 CPUs
!> @date 30.07.2026 - Account for negative pore-water pressures and
!>                    protect against vanishing total normal stress
!=======================================================================================================
      subroutine vusdfld(
c Read only variables -
     1   nblock, nstatev, nfieldv, nprops, ndir, nshr,
     2   jElem, kIntPt, kLayer, kSecPt,
     3   stepTime, totalTime, dt, cmname,
     4   coordMp, direct, T, charLength, props,
     5   stateOld,
c Write only variables -
     6   stateNew, field )
c
      include 'vaba_param.inc'
c
      dimension jElem(nblock), coordMp(nblock,*),
     1 direct(nblock,3,3), T(nblock,3,3),
     2          charLength(nblock), props(nprops),
     3          stateOld(nblock,nstatev),
     4          stateNew(nblock,nstatev),
     5          field(nblock,nfieldv)
      character*80 cmname
c
c     Local arrays from vgetvrm are dimensioned to
c     maximum block size (maxblk)
c
      parameter( nrData=6 )
      character*3 cData(maxblk*nrData)
      dimension rData(maxblk*nrData), jData(maxblk*nrData)
      real(8) normal_vector(2), normal_stress(2), pile_center(2)
      real(8) pile_radius, min_coords3
      real(8) effective_normal_value, total_normal_value
      integer KPROCESSNUM, myunit

      logical file_exists
      character*256 OUTDIR
      
      CALL VGETOUTDIR( OUTDIR, LENOUTDIR )
      
!# =============================================================================
!# Variables to be edited
!# =============================================================================
      pile_radius      = 1.0d0      !! only in the zone 1.4 times the pile radius the field variable is assigned
      min_coords3      = 11.0d0     !! for z-coords larger than this value the field variable is not assigned, change at end of file if needed!!
      pile_center(1:2) = [0.0d0,0.0d0] !! define pile center
!# =============================================================================
!# Get processes
!# =============================================================================
      !! field(:,2) is filled by vufield
      if(any(field(:,2)<5)) return

      file_exists = .false.

      CALL VGETRANK(KPROCESSNUM) !! This gives the process number 

      if(KPROCESSNUM == 0) then
        myunit =105
        inquire(file = 'vusdfld_out1.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out1.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out1.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 1) then
        myunit =106
        inquire(file = 'vusdfld_out2.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out2.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out2.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 2) then
        myunit =107
        inquire(file = 'vusdfld_out3.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out3.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out3.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 3) then
        myunit =108
        inquire(file = 'vusdfld_out4.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out4.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out4.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 4) then
        myunit =109
        inquire(file = 'vusdfld_out5.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out5.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out5.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 5) then
        myunit =110
        inquire(file = 'vusdfld_out6.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out6.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out6.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 6) then
        myunit =111
        inquire(file = 'vusdfld_out7.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out7.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out7.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 7) then
        myunit =112
        inquire(file = 'vusdfld_out8.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out8.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out8.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 8) then
        myunit =113
        inquire(file = 'vusdfld_out9.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out9.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out9.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 9) then
        myunit =114
        inquire(file = 'vusdfld_out10.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out10.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out10.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 10) then
        myunit =115
        inquire(file = 'vusdfld_out11.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out11.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out11.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 11) then
        myunit =116
        inquire(file = 'vusdfld_out12.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out12.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out12.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 12) then
        myunit =117
        inquire(file = 'vusdfld_out13.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out13.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out13.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 13) then
        myunit =118
        inquire(file = 'vusdfld_out14.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out14.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out14.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 14) then
        myunit =119
        inquire(file = 'vusdfld_out15.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out15.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out15.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 15) then
        myunit =120
        inquire(file = 'vusdfld_out16.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out16.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out16.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 16) then
        myunit =121
        inquire(file = 'vusdfld_out17.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out17.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out17.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 17) then
        myunit =122
        inquire(file = 'vusdfld_out18.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out18.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out18.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 18) then
        myunit =123
        inquire(file = 'vusdfld_out19.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out19.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out19.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 19) then
        myunit =124
        inquire(file = 'vusdfld_out20.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out20.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out20.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 20) then
        myunit =125
        inquire(file = 'vusdfld_out21.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out21.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out21.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 21) then
        myunit =126
        inquire(file = 'vusdfld_out22.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out22.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out22.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 22) then
        myunit =127
        inquire(file = 'vusdfld_out23.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out23.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out23.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 23) then
        myunit =128
        inquire(file = 'vusdfld_out24.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out24.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out24.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 24) then
        myunit =129
        inquire(file = 'vusdfld_out25.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out25.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out25.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 25) then
        myunit =130
        inquire(file = 'vusdfld_out26.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out26.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out26.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 26) then
        myunit =131
        inquire(file = 'vusdfld_out27.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out27.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out27.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 27) then
        myunit =132
        inquire(file = 'vusdfld_out28.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out28.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out28.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 28) then
        myunit =133
        inquire(file = 'vusdfld_out29.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out29.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out29.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 29) then
        myunit =134
        inquire(file = 'vusdfld_out30.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out30.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out30.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 30) then
        myunit =135
        inquire(file = 'vusdfld_out31.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out31.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out31.dat',
     1    status='new', action="write", iostat = ios)
        endif
      elseif(KPROCESSNUM == 31) then
        myunit =136
        inquire(file = 'vusdfld_out32.dat',
     1   exist=file_exists)

        if(file_exists) then
          open(unit = myunit, file = 'vusdfld_out32.dat',
     1    status="old", position="append", action="readwrite", iostat = ios)
        else
          open(unit = myunit, file = 'vusdfld_out32.dat',
     1    status='new', action="write", iostat = ios)
        endif
      else
        write(*,*) 'ERROR SUBROUTINE VUFIELD: Not defined for the given number of processes'
      endif
	  
!# =============================================================================
!# Calculate field variable
!# =============================================================================
      do 100 k = 1, nblock


        if(sqrt(coordMp(k,1)**2+ coordMp(k,2)**2) < pile_radius*1.4 .and.
     1   sqrt(coordMp(k,1)**2+ coordMp(k,2)**2) > pile_radius*0.7 .and.
     2          coordMp(k,3)<min_coords3) then
     
         !! The normal vector has to point inward (multiply with -1)
         normal_vector(1:2) = -(coordMp(k,1:2)-pile_center(1:2))/norm2(coordMp(k,1:2)-pile_center(1:2))

         !! The pile has a radius of pile_radius, inside of the pile the normal vector has to point outward
         if(sqrt(coordMp(k,1)**2+coordMp(k,2)**2) <= pile_radius)
     1    normal_vector(1:2) = - normal_vector(1:2)

         normal_stress(1) = stateOld(k,27)*normal_vector(1) + stateOld(k,30)*normal_vector(2)
         normal_stress(2) = stateOld(k,28)*normal_vector(2) + stateOld(k,30)*normal_vector(1)

         effective_normal_value =
     1     abs(dot_product(normal_stress,normal_vector))

         !! Retain the original state-variable layout. The magnitude of
         !! total normal stress is reconstructed from effective normal
         !! stress, hydrostatic pore pressure (STATEV 24), and excess
         !! pore pressure (STATEV 25).
         total_normal_value = effective_normal_value
     1                      + stateOld(k,24) + stateOld(k,25)

         !! Avoid division by a vanishing or tensile total normal stress.
         !! Negative pore-water pressures can give a valid ratio above
         !! one and are therefore not capped.
         if(total_normal_value <= 0.01d0) then
           field(k,1) = 0.0d0
         else
           field(k,1) = effective_normal_value/total_normal_value
           if(isnan(field(k,1))) field(k,1) = 0.0d0
           if(field(k,1) < 0.01d0) field(k,1) = 0.0d0
         endif

          write(myunit,*) coordMp(k,1:3),field(k,1)

        endif

  100 continue

      close(myunit)


c
      return
      end
