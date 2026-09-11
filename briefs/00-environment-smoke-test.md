# Brief 00 - environment smoke test

**Cost:** ~10 minutes. **Needs:** Abaqus.

Establish that the machine can do the work at all, and record what it is, so that
every later result has a known provenance.

## Do

1. Record the environment.

   ```bash
   abaqus information=release
   abaqus information=system
   ```

   Record: Abaqus version, platform, CPU count, memory, and which Fortran
   compiler and MSVC the command wrapper sets up.

2. Confirm the launcher sets up the compiler environment. Launch through the
   command wrapper (`abq20XX.bat` / `abaqus`), never `ABQLauncher.exe` directly.
   You should see `oneAPI environment initialized ::` in the output; the
   `vcvarsall.bat` "Invalid argument" lines are expected noise.

3. Verify the user-subroutine toolchain.

   ```bash
   abaqus verify -user_std
   abaqus verify -user_exp
   ```

   If these fail, stop and fix the toolchain. Nothing in brief 06, or the UMAT
   path of brief 07, will work until they pass.

4. Create a working directory **with no spaces in the path**:

   ```bash
   set FLD_WORKDIR=C:\abq\run
   ```

   Confirm Abaqus can write there.

5. Confirm the library imports in the Abaqus interpreter:

   ```bash
   abaqus python -c "import sys; sys.path.insert(0, r'<repo>/lib'); from fldlib import config, inpedit, report; print('ok')"
   ```

   `fldlib.ale`, `cel`, `steps`, `contact`, `jobs` and `materials` import
   `abaqusConstants` lazily **inside functions**, so they should import outside
   CAE too. If any of them fails, that is a bug - a stray module-level Abaqus
   import - and worth fixing now rather than later.

## Expected outcome

All five pass. If `abaqus verify -user_exp` fails, record the exact error; it is
almost always a compiler-version mismatch with the Abaqus release.

## Report

Environment table, the verify results, and anything unexpected in the launcher
output.
