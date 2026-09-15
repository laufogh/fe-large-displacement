@echo off
REM Standalone verification of VUMAT_MohrCoulomb against MohrCoulombAbaqus.for.
REM Needs gfortran on PATH; does not need Abaqus.
REM The vaba_param.inc files here are one-line stubs standing in for the
REM Abaqus headers: the top-level one matches vaba_param_dp.inc, sp\ matches
REM vaba_param_sp.inc.

setlocal
cd /d "%~dp0"

echo === Building double precision ===
gfortran -c -ffixed-form -ffixed-line-length-none -I. -I.. ..\call_explicit.f -o call_explicit.o || goto :fail
gfortran -O2 -ffree-form .\driver.f90  call_explicit.o -o driver.exe  || goto :fail
gfortran -O2 -ffree-form .\driver2.f90 call_explicit.o -o driver2.exe || goto :fail

echo === Building single precision ===
gfortran -c -ffixed-form -ffixed-line-length-none -Isp -I.. ..\call_explicit.f -o call_explicit_sp.o || goto :fail
gfortran -O2 -ffree-form .\driver_sp.f90 call_explicit_sp.o -o driver_sp.exe || goto :fail

echo.
echo === Test 1: 3D, all six components (double) ===
.\driver.exe || goto :fail
echo.
echo === Tests 2 and 3: plane strain, and the data-check branch (double) ===
.\driver2.exe || goto :fail
echo.
echo === Test 4: single precision material constants ===
.\driver_sp.exe || goto :fail

echo.
echo All checks passed.
set result=0
goto :cleanup

:fail
set result=1

:cleanup
del /q call_explicit.o call_explicit_sp.o driver.exe driver2.exe driver_sp.exe >nul 2>&1
endlocal & exit /b %result%
