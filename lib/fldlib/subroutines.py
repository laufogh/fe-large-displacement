"""Getting a UMAT/VUMAT to actually compile and run.

Most of the pain of user subroutines in Abaqus has nothing to do with the
mechanics. It is build-system pain, and it is the same handful of problems every
time.

1. **Spaces in the path.** Abaqus hands the source path to the Intel Fortran
   driver without quoting it. If your model lives under
   ``C:\\Users\\you\\OneDrive - Some University\\...`` the compile fails, and the
   error message says nothing about spaces. The fix is to copy the subroutine
   (and everything it INCLUDEs) into a space-free working directory before
   submitting. `stage()` below does that.

2. **The `call` file pattern.** Abaqus compiles exactly one source file per job.
   Multi-file models therefore use a tiny top-level file that does nothing but
   ``include`` the real sources::

       include 'HPP_Staubach_implicit.f'
       include 'sdvini.f'

   You must copy the included files too, or the compile fails on the include.

3. **Precision.** Abaqus/Explicit compiled with `explicitPrecision=DOUBLE` or
   `DOUBLE_PLUS_PACK` expects the subroutine to use double precision
   consistently. A VUMAT written with `REAL` rather than `REAL*8` will build and
   run and give you slightly wrong answers that look plausible. Always
   `DOUBLE_PLUS_PACK` for the work in this repository.

4. **NaN does not stop Abaqus/Explicit.** A UMAT that returns NaN on increment
   one produces a job that runs to completion and writes a full ODB. Check
   explicitly -- `tools/check_odb_finite.py`.

5. **Compiler and Abaqus versions must match.** Abaqus 2021 wants a specific
   Intel Fortran; 2023 wants a different one. `abaqus verify -user_std` and
   `abaqus verify -user_exp` are the fastest way to find out whether your
   toolchain works at all, and they should be the first thing you run on a new
   machine. See docs/abaqus-launch-guide.md.
"""

from __future__ import print_function

import os
import re
import shutil


_INCLUDE = re.compile(r"^\s*include\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)


def find_includes(path, seen=None):
    """Recursively collect the files INCLUDEd by a Fortran source.

    Returns a list of absolute paths, in include order, excluding `path`
    itself. Includes are resolved relative to the including file's directory,
    which is how the Intel driver resolves them.
    """
    seen = seen if seen is not None else set()
    out = []
    base = os.path.dirname(os.path.abspath(path))
    fh = open(path)
    try:
        lines = fh.readlines()
    finally:
        fh.close()
    for line in lines:
        m = _INCLUDE.match(line)
        if not m:
            continue
        inc = os.path.normpath(os.path.join(base, m.group(1).strip()))
        key = os.path.normcase(inc)
        if key in seen:
            continue
        seen.add(key)
        if not os.path.isfile(inc):
            raise IOError('%s includes %r, which does not exist (looked in %s)'
                          % (path, m.group(1), base))
        out.append(inc)
        out.extend(find_includes(inc, seen))
    return out


def stage(source, workdir, printer=print):
    """Copy a subroutine and everything it includes into `workdir`.

    Returns the path of the copied top-level file, which is what you pass to
    `mdb.Job(userSubroutine=...)`.

    Always call this. Even when your current path has no spaces in it, the next
    person's will, and the failure mode is a compiler error that does not
    mention the cause.
    """
    if not source:
        return ''
    source = os.path.abspath(source)
    if not os.path.isfile(source):
        raise IOError('user subroutine not found: %s' % source)
    if not os.path.isdir(workdir):
        os.makedirs(workdir)

    if ' ' in os.path.abspath(workdir):
        raise RuntimeError(
            'the working directory %r contains a space. The Intel Fortran '
            'driver that Abaqus invokes does not quote the path and the '
            'compile will fail with an error that does not mention this. '
            'Set FLD_WORKDIR to a path without spaces.' % workdir)

    files = [source] + find_includes(source)
    copied_main = None
    for src in files:
        dst = os.path.join(workdir, os.path.basename(src))
        if os.path.normcase(dst) != os.path.normcase(src):
            shutil.copy2(src, dst)
            printer('  staged subroutine: %s -> %s'
                    % (os.path.basename(src), workdir))
        else:
            printer('  already staged: %s' % os.path.basename(src))
        if src == source:
            copied_main = dst
    return copied_main


def describe(source, printer=print):
    """Print what a subroutine file contains. Cheap orientation before you run.

    Reports which Abaqus user routines it defines (UMAT, VUMAT, SDVINI, USDFLD,
    VUSDFLD, VUAMP...) and which files it includes.
    """
    if not source or not os.path.isfile(source):
        printer('  (no subroutine)')
        return {}
    fh = open(source)
    try:
        text = fh.read()
    finally:
        fh.close()

    routines = sorted(set(
        m.group(1).upper() for m in re.finditer(
            r'^\s*(?:pure\s+|recursive\s+)?subroutine\s+'
            r'(umat|vumat|sdvini|usdfld|vusdfld|vuamp|vufield|uexternaldb|'
            r'vexternaldb|dload|vdload|uel|vuel)\b',
            text, re.IGNORECASE | re.MULTILINE)))
    includes = [os.path.basename(p) for p in find_includes(source)]
    printer('  subroutine file : %s' % os.path.basename(source))
    printer('  defines         : %s' % (', '.join(routines) or '(none found)'))
    printer('  includes        : %s' % (', '.join(includes) or '(none)'))
    return {'routines': routines, 'includes': includes}
