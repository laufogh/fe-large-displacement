"""Report whether an Abaqus ODB contains any non-finite field values.

Run under 'abaqus python' (no CAE token):

    abaqus python check_odb_finite.py <job>.odb [instance-name-substring]

Exit code 0 = every checked value finite, 1 = NaN/Inf found, 2 = usage error.

Why this exists
---------------
A UMAT that returns NaN is not reported as an error by Abaqus/Standard. NaN
fails every comparison, so the residual convergence test passes trivially and
the job prints "THE ANALYSIS HAS COMPLETED SUCCESSFULLY" having written
nothing but NaN. The failure only surfaces much later -- e.g. when
Abaqus/Explicit imports that state and the packager reports "no element
available to control the stable time increment for Step N".

Abaqus/Explicit is worse: it has no convergence test at all, so it integrates
NaN forward to the end of the step and writes a complete, well-formed,
entirely meaningless ODB. This is not an edge case -- it is the normal outcome
of an uninitialised state variable in a user material.

Run this on every user-material job. Check the implicit ODB before trusting it,
and before launching any phase that imports from it.

See docs/06-constitutive-models.md.
"""

from __future__ import print_function

import sys

from odbAccess import openOdb

# Fields worth checking: the ones that propagate into an *IMPORT.
FIELDS = ('S', 'LE', 'U', 'SDV1')


def bad(x):
    # NaN fails every comparison with itself; Inf survives that but not this.
    return x != x or x > 1.0e30 or x < -1.0e30


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2

    path = argv[1]
    want = argv[2].upper() if len(argv) > 2 else None

    odb = openOdb(path, readOnly=True)
    try:
        instances = [n for n in odb.rootAssembly.instances.keys()
                     if want is None or want in n.upper()]
        if not instances:
            print('no instance matching %r in %s' % (want, path))
            return 2

        problems = 0
        for step_name in odb.steps.keys():
            step = odb.steps[step_name]
            if not len(step.frames):
                continue
            frame = step.frames[-1]
            for inst_name in instances:
                region = odb.rootAssembly.instances[inst_name]
                for key in FIELDS:
                    if key not in frame.fieldOutputs.keys():
                        continue
                    try:
                        vals = frame.fieldOutputs[key].getSubset(
                            region=region).values
                    except Exception:
                        continue
                    nbad = 0
                    ntot = 0
                    for v in vals:
                        d = v.data
                        try:
                            comps = list(d)
                        except TypeError:
                            comps = [d]
                        ntot += 1
                        for c in comps:
                            if bad(c):
                                nbad += 1
                                break
                    if ntot == 0:
                        continue
                    flag = 'NON-FINITE' if nbad else 'ok'
                    print('%-22s %-34s %-5s %7d / %-7d %s'
                          % (step_name[:22], inst_name[:34], key,
                             nbad, ntot, flag))
                    problems += nbad

        print('')
        if problems:
            print('FAIL: %d non-finite values found in %s' % (problems, path))
            return 1
        print('PASS: all checked values finite in %s' % path)
        return 0
    finally:
        odb.close()


if __name__ == '__main__':
    sys.exit(main(sys.argv))
