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
! SUBROUTINE: VUFIELD
!
!> @author Patrick Staubach, patrick.staubach@yahoo.de
!          Bauhaus University Weimar, Ruhr-University Bochum
!
! DESCRIPTION:
!> @brief Contains the VUFIELD routine used to calculate effective interface friction according to the paper
!> @brief "Hydro-mechanically coupled CEL analyses with effective contact stresses" https://onlinelibrary.wiley.com/doi/10.1002/nag.3725 International Journal for Numerical and Analytical Methods in Geomechanics 
!
! REVISION HISTORY
!> @date 03.03.2024 - Initial version
!> @date 13.03.2026 - Support of up to 32 CPUs
!> @date 28.07.2026 - Distance-weighted mapping from several integration
!>                    points instead of nearest-neighbour mapping
!> @date 30.07.2026 - Allow field values above one to account for
!>                    negative pore-water pressures
!=======================================================================================================
      SUBROUTINE VUFIELD(FIELD, NBLOCK, NFIELD, KFIELD, NCOMP,
     1                   KSTEP, JFLAGS, JNODEUID, TIME,
     2                   COORDS, U, V, A)
C
      INCLUDE 'VABA_PARAM.INC'


C     indices for the time array TIME
      PARAMETER( i_ufld_Current   = 1,
     *           i_ufld_Increment = 2,
     *           i_ufld_Period    = 3,
     *           i_ufld_Total     = 4 )

C     indices for the coordinate array COORDS
      PARAMETER( i_ufld_CoordX = 1,
     *           i_ufld_CoordY = 2,
     *           i_ufld_CoordZ = 3 )

C     indices for the displacement array U
      PARAMETER( i_ufld_SpaDisplX = 1,
     *           i_ufld_SpaDisplY = 2,
     *           i_ufld_SpaDisplZ = 3,
     *           i_ufld_RotDisplX = 4,
     *           i_ufld_RotDisplY = 5,
     *           i_ufld_RotDisplZ = 6,
     *           i_ufld_AcoPress  = 7,
     *           i_ufld_Temp      = 8 )

C     indices for the velocity array V
      PARAMETER( i_ufld_SpaVelX   = 1,
     *           i_ufld_SpaVelY   = 2,
     *           i_ufld_SpaVelZ   = 3,
     *           i_ufld_RotVelX   = 4,
     *           i_ufld_RotVelY   = 5,
     *           i_ufld_RotVelZ   = 6,
     *           i_ufld_DAcoPress = 7,
     *           i_ufld_DTemp     = 8 )

C     indices for the acceleration array A
      PARAMETER( i_ufld_SpaAccelX  = 1,
     *           i_ufld_SpaAccelY  = 2,
     *           i_ufld_SpaAccelZ  = 3,
     *           i_ufld_RotAccelX  = 4,
     *           i_ufld_RotAccelY  = 5,
     *           i_ufld_RotAccelZ  = 6,
     *           i_ufld_DDAcoPress = 7,
     *           i_ufld_DDTemp     = 8 )

C     indices for JFLAGS
      PARAMETER( i_ufld_kInc   = 1,
     *           i_ufld_kPass  = 2 )
C
      DIMENSION FIELD(NBLOCK,NCOMP,NFIELD)
      DIMENSION JFLAGS(2), JNODEUID(NBLOCK), TIME(4),
     *          COORDS(3,NBLOCK)
      integer max_neighbors
      parameter(max_neighbors=32)
      DIMENSION U(8,NBLOCK), V(8,NBLOCK), A(8,NBLOCK),
     *          coords_field(5000,3)
      real(8) field_vusdfld(5000), pile_radius, min_coords3
      real(8) nearest_dist2(max_neighbors)
      real(8) nearest_field(max_neighbors)
      real(8) distance2, farthest_dist2, regularization2
      real(8) weight, weight_sum, weighted_field
      integer nline, n_stored, ios, jj, ii, k
      integer n_average, n_found, i_farthest
      logical file_exists
      integer frequency_update, bytes_per_line
      character*256 OUTDIR
      
      CALL VGETOUTDIR( OUTDIR, LENOUTDIR )
      
!# =============================================================================
!# Variables to be edited
!# =============================================================================
      pile_radius      = 1.0d0     !! only in the zone 1.4 times the pile radius the field variable is assigned
      frequency_update = 10        !! only in every 10th calculation increment the field variable is updated
      n_average        = 8         !! number of spatially closest integration-point values to be averaged
      min_coords3      = 11.0d0    !! for z-coords larger than this value the field variable is not assigned, change at end of file if needed!!
      bytes_per_line   = 62        !! bytes for one line of the files to be read, Check if subroutine is reading correct number of lines!!
      n_average = max(1,min(n_average,max_neighbors))
!# =============================================================================
!# Get processes
!# =============================================================================
      CALL VGETRANK( KPROCESSNUM )

      if(KPROCESSNUM == 0) then
        myunit = 105
      elseif(KPROCESSNUM == 1) then
        myunit = 106
      elseif(KPROCESSNUM == 2) then
        myunit = 107
      elseif(KPROCESSNUM == 3) then
        myunit = 108
      elseif(KPROCESSNUM == 4) then
        myunit = 109
      elseif(KPROCESSNUM == 5) then
        myunit = 110
      elseif(KPROCESSNUM == 6) then
        myunit = 111
      elseif(KPROCESSNUM == 7) then
        myunit = 112
      elseif(KPROCESSNUM == 8) then
        myunit = 113
      elseif(KPROCESSNUM == 9) then
        myunit = 114
      elseif(KPROCESSNUM == 10) then
        myunit = 115
      elseif(KPROCESSNUM == 11) then
        myunit = 116
      elseif(KPROCESSNUM == 12) then
        myunit = 117
      elseif(KPROCESSNUM == 13) then
        myunit = 118
      elseif(KPROCESSNUM == 14) then
        myunit = 119
      elseif(KPROCESSNUM == 15) then
        myunit = 120
      elseif(KPROCESSNUM == 16) then
        myunit = 121
      elseif(KPROCESSNUM == 17) then
        myunit = 122
      elseif(KPROCESSNUM == 18) then
        myunit = 123
      elseif(KPROCESSNUM == 19) then
        myunit = 124
      elseif(KPROCESSNUM == 20) then
        myunit = 125
      elseif(KPROCESSNUM == 21) then
        myunit = 126
      elseif(KPROCESSNUM == 22) then
        myunit = 127
      elseif(KPROCESSNUM == 23) then
        myunit = 128
      elseif(KPROCESSNUM == 24) then
        myunit = 129
      elseif(KPROCESSNUM == 25) then
        myunit = 130
      elseif(KPROCESSNUM == 26) then
        myunit = 131
      elseif(KPROCESSNUM == 27) then
        myunit = 132
      elseif(KPROCESSNUM == 28) then
        myunit = 133
      elseif(KPROCESSNUM == 29) then
        myunit = 134
      elseif(KPROCESSNUM == 30) then
        myunit = 135
      elseif(KPROCESSNUM == 31) then
        myunit = 136
      else
        write(*,*) 'ERROR SUBROUTINE VUFIELD: Not defined for the given number of processes'
      endif

      !! Operations are performed every 10th increment
      if (mod(JFLAGS(i_ufld_kInc),frequency_update) <= 0) then
        field(:,1,2) = 10
        if(KPROCESSNUM == 0) then
          inquire(file = 'vusdfld_out1.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out1.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out2.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out2.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out3.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out3.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out4.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out4.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out5.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out5.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out6.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out6.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out7.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out7.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out8.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out8.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out9.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out9.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out10.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out10.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out11.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out11.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out12.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out12.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out13.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out13.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out14.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out14.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out15.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out15.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out16.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out16.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out17.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out17.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out18.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out18.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out19.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out19.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out20.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out20.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out21.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out21.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out22.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out22.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out23.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out23.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out24.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out24.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out25.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out25.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out26.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out26.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out27.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out27.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out28.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out28.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out29.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out29.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out30.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out30.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out31.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out31.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out32.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out32.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          return
        else
          return
        endif
      endif

      !! Return and delete files for other increments
      if(any(field(:,1,2) <5)) then
        if(KPROCESSNUM == 0) then
          inquire(file = 'vusdfld_out1.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out1.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out2.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out2.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out3.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out3.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out4.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out4.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out5.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out5.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out6.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out6.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out7.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out7.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out8.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out8.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out9.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out9.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out10.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out10.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out11.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out11.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out12.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out12.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out13.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out13.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out14.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out14.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out15.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out15.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out16.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out16.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out17.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out17.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out18.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out18.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out19.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out19.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out20.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out20.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out21.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out21.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out22.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out22.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out23.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out23.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out24.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out24.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out25.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out25.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out26.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out26.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out27.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out27.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out28.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out28.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out29.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out29.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out30.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out30.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out31.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out31.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          inquire(file = 'vusdfld_out32.dat',
     1    exist=file_exists)
          if(file_exists) then
            open(unit = myunit, file = 'vusdfld_out32.dat',
     1      status='old', position="append", action="readwrite", iostat = ios)
            close(myunit, status='delete')
          endif
          return
        else
          return
        endif
      endif
!# =============================================================================
!# Start reading values to update field variables at nodes
!# =============================================================================
      !! the second field variable indicates that in the next increments no update is performed
      field(:,1,2) = 0

!# =============================================================================
!# For each thread an individual file is written. Currently only up to 32 threads are supported
!# First file from first process
!# =============================================================================
      file_exists = .false.
      inquire(file = 'vusdfld_out1.dat',
     1exist=file_exists,size=isize)
      if(file_exists) then
        open(unit = myunit, file = 'vusdfld_out1.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
      else
        RETURN
      endif
      nlines = int(isize/bytes_per_line) !! This solution was required because it appears that ios checking if end of file reached does not work with abaqus
      nline = 1
      if(isize>0) then
        read1: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read1
          nline = nline + 1
        end do read1
        close(myunit)
      endif

!# =============================================================================
!# Second file from second process
!# =============================================================================
      inquire(file = 'vusdfld_out2.dat',
     1exist=file_exists,size=isize,RECL=iRECL)
      nlines = int(isize/bytes_per_line) !! This solution was required because it appears that ios checking if end of file reached does not work with abaqus
      if(file_exists .and. isize > 0 ) then
        open(unit = myunit, file = 'vusdfld_out2.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read2: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read2
          nline = nline + 1
        end do read2
        close(myunit)
      endif

!# =============================================================================
!# Third file from third process
!# =============================================================================
      inquire(file = 'vusdfld_out3.dat',
     1exist=file_exists,size=isize,RECL=iRECL)
      nlines = int(isize/bytes_per_line) !! This solution was required because it appears that ios checking if end of file reached does not work with abaqus
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out3.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read3: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /=0) exit read3
          nline = nline + 1
        end do read3
        close(myunit)
      endif

!# =============================================================================
!# Fourth file from fourth process
!# =============================================================================
      inquire(file = 'vusdfld_out4.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line) !! This solution was required because it appears that ios checking if end of file reached does not work with abaqus
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out4.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read4: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read4
          nline = nline + 1
        end do read4
        close(myunit)
      endif
!# =============================================================================
!# Fifth file from fifth process
!# =============================================================================
      inquire(file = 'vusdfld_out5.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line) !! This solution was required because it appears that ios checking if end of file reached does not work with abaqus
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out5.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read5: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read5
          nline = nline + 1
        end do read5
        close(myunit)
      endif
!# =============================================================================
!# Sixth file from sixth process
!# =============================================================================
      inquire(file = 'vusdfld_out6.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line) !! This solution was required because it appears that ios checking if end of file reached does not work with abaqus
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out6.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read6: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read6
          nline = nline + 1
        end do read6
        close(myunit)
      endif
!# =============================================================================
!# Seventh file from seventh process
!# =============================================================================
      inquire(file = 'vusdfld_out7.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line) !! This solution was required because it appears that ios checking if end of file reached does not work with abaqus
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out7.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read7: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read7
          nline = nline + 1
        end do read7
        close(myunit)
      endif
      
!# =============================================================================
!# Eighth file from eighth process
!# =============================================================================
      inquire(file = 'vusdfld_out8.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line) !! This solution was required because it appears that ios checking if end of file reached does not work with abaqus
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out8.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read8: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read8
          nline = nline + 1
        end do read8
        close(myunit)
      endif

!# =============================================================================
!# Ninth file from ninth process
!# =============================================================================
      inquire(file = 'vusdfld_out9.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out9.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read9: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read9
          nline = nline + 1
        end do read9
        close(myunit)
      endif

!# =============================================================================
!# Tenth file from tenth process
!# =============================================================================
      inquire(file = 'vusdfld_out10.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out10.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read10: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read10
          nline = nline + 1
        end do read10
        close(myunit)
      endif

!# =============================================================================
!# Eleventh file from eleventh process
!# =============================================================================
      inquire(file = 'vusdfld_out11.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out11.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read11: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read11
          nline = nline + 1
        end do read11
        close(myunit)
      endif

!# =============================================================================
!# Twelfth file from twelfth process
!# =============================================================================
      inquire(file = 'vusdfld_out12.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out12.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read12: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read12
          nline = nline + 1
        end do read12
        close(myunit)
      endif

!# =============================================================================
!# Thirteenth file from thirteenth process
!# =============================================================================
      inquire(file = 'vusdfld_out13.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out13.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read13: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read13
          nline = nline + 1
        end do read13
        close(myunit)
      endif

!# =============================================================================
!# Fourteenth file from fourteenth process
!# =============================================================================
      inquire(file = 'vusdfld_out14.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out14.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read14: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read14
          nline = nline + 1
        end do read14
        close(myunit)
      endif

!# =============================================================================
!# Fifteenth file from fifteenth process
!# =============================================================================
      inquire(file = 'vusdfld_out15.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out15.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read15: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read15
          nline = nline + 1
        end do read15
        close(myunit)
      endif

!# =============================================================================
!# Sixteenth file from sixteenth process
!# =============================================================================
      inquire(file = 'vusdfld_out16.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out16.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read16: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read16
          nline = nline + 1
        end do read16
        close(myunit)
      endif

!# =============================================================================
!# Seventeenth file from seventeenth process
!# =============================================================================
      inquire(file = 'vusdfld_out17.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out17.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read17: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read17
          nline = nline + 1
        end do read17
        close(myunit)
      endif

!# =============================================================================
!# Eighteenth file from eighteenth process
!# =============================================================================
      inquire(file = 'vusdfld_out18.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out18.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read18: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read18
          nline = nline + 1
        end do read18
        close(myunit)
      endif

!# =============================================================================
!# Nineteenth file from nineteenth process
!# =============================================================================
      inquire(file = 'vusdfld_out19.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out19.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read19: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read19
          nline = nline + 1
        end do read19
        close(myunit)
      endif

!# =============================================================================
!# Twentieth file from twentieth process
!# =============================================================================
      inquire(file = 'vusdfld_out20.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out20.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read20: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read20
          nline = nline + 1
        end do read20
        close(myunit)
      endif

!# =============================================================================
!# Twenty-first file from twenty-first process
!# =============================================================================
      inquire(file = 'vusdfld_out21.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out21.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read21: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read21
          nline = nline + 1
        end do read21
        close(myunit)
      endif

!# =============================================================================
!# Twenty-second file from twenty-second process
!# =============================================================================
      inquire(file = 'vusdfld_out22.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out22.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read22: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read22
          nline = nline + 1
        end do read22
        close(myunit)
      endif

!# =============================================================================
!# Twenty-third file from twenty-third process
!# =============================================================================
      inquire(file = 'vusdfld_out23.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out23.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read23: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read23
          nline = nline + 1
        end do read23
        close(myunit)
      endif

!# =============================================================================
!# Twenty-fourth file from twenty-fourth process
!# =============================================================================
      inquire(file = 'vusdfld_out24.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out24.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read24: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read24
          nline = nline + 1
        end do read24
        close(myunit)
      endif

!# =============================================================================
!# Twenty-fifth file from twenty-fifth process
!# =============================================================================
      inquire(file = 'vusdfld_out25.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out25.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read25: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read25
          nline = nline + 1
        end do read25
        close(myunit)
      endif

!# =============================================================================
!# Twenty-sixth file from twenty-sixth process
!# =============================================================================
      inquire(file = 'vusdfld_out26.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out26.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read26: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read26
          nline = nline + 1
        end do read26
        close(myunit)
      endif

!# =============================================================================
!# Twenty-seventh file from twenty-seventh process
!# =============================================================================
      inquire(file = 'vusdfld_out27.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out27.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read27: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read27
          nline = nline + 1
        end do read27
        close(myunit)
      endif

!# =============================================================================
!# Twenty-eighth file from twenty-eighth process
!# =============================================================================
      inquire(file = 'vusdfld_out28.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out28.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read28: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read28
          nline = nline + 1
        end do read28
        close(myunit)
      endif

!# =============================================================================
!# Twenty-ninth file from twenty-ninth process
!# =============================================================================
      inquire(file = 'vusdfld_out29.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out29.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read29: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read29
          nline = nline + 1
        end do read29
        close(myunit)
      endif

!# =============================================================================
!# Thirtieth file from thirtieth process
!# =============================================================================
      inquire(file = 'vusdfld_out30.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out30.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read30: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read30
          nline = nline + 1
        end do read30
        close(myunit)
      endif

!# =============================================================================
!# Thirty-first file from thirty-first process
!# =============================================================================
      inquire(file = 'vusdfld_out31.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out31.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read31: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read31
          nline = nline + 1
        end do read31
        close(myunit)
      endif

!# =============================================================================
!# Thirty-second file from thirty-second process
!# =============================================================================
      inquire(file = 'vusdfld_out32.dat',
     1exist=file_exists,size=isize)
      nlines = int(isize/bytes_per_line)
      if(file_exists .and. isize > 0) then
        open(unit = myunit, file = 'vusdfld_out32.dat',
     1  status='unknown', action="read", iostat = ios, form="FORMATTED")
        read32: do ii = 1, nlines
          read(myunit,*,iostat=ios) coords_field(nline,1:3), field_vusdfld(nline)
          if(ios /= 0) exit read32
          nline = nline + 1
        end do read32
        close(myunit)
      endif
      
!# =============================================================================
!# Assign a distance-weighted average of nearby integration-point values
!# to the nodes. The n_average spatially closest points are used. This
!# provides a smooth coordinate-based projection without requiring
!# element-to-node connectivity.
!# =============================================================================

      !! nline always points to the next free array entry after reading.
      !! Therefore, the last valid entry is nline-1.
      n_stored = nline-1
      if(n_stored <= 0) return

      do k = 1, nblock

        if(sqrt(COORDS(1,k)**2+ COORDS(2,k)**2) < pile_radius*1.2 .and.
     1   sqrt(COORDS(1,k)**2+ COORDS(2,k)**2) > pile_radius*0.7 .and.
     2         COORDS(3,k)<min_coords3) then

          n_found = 0
          do ii = 1, max_neighbors
            nearest_dist2(ii) = 1.0d300
            nearest_field(ii) = 0.0d0
          enddo

          do jj = 1, n_stored

            distance2 = (COORDS(1,k)-coords_field(jj,1))**2
     1                + (COORDS(2,k)-coords_field(jj,2))**2
     2                + (COORDS(3,k)-coords_field(jj,3))**2

            if(n_found < n_average) then
              n_found = n_found+1
              nearest_dist2(n_found) = distance2
              nearest_field(n_found) = field_vusdfld(jj)
            else
              i_farthest = 1
              farthest_dist2 = nearest_dist2(1)
              do ii = 2, n_average
                if(nearest_dist2(ii) > farthest_dist2) then
                  i_farthest = ii
                  farthest_dist2 = nearest_dist2(ii)
                endif
              enddo

              if(distance2 < farthest_dist2) then
                nearest_dist2(i_farthest) = distance2
                nearest_field(i_farthest) = field_vusdfld(jj)
              endif
            endif
          enddo

          !! Inverse-distance-squared weighting. The small
          !! regularisation length prevents a singular weight if an
          !! integration point and a node have identical coordinates.
          regularization2 = (1.0d-6*pile_radius)**2
          weight_sum = 0.0d0
          weighted_field = 0.0d0

          do ii = 1, n_found
            weight = 1.0d0/(nearest_dist2(ii)+regularization2)
            weight_sum = weight_sum+weight
            weighted_field = weighted_field
     1                     + weight*nearest_field(ii)
          enddo

          if(weight_sum > 0.0d0) then
            field(k,1,1) = weighted_field/weight_sum
            !! Values above one are physically admissible when negative
            !! pore-water pressure increases effective normal stress
            !! relative to total normal stress.
            if(field(k,1,1) < 0.0d0) field(k,1,1) = 0.0d0
          endif
        endif

       enddo

c

      RETURN
      END
