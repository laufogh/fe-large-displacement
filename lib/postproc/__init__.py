"""Post-processing that runs under `abaqus python` (odbAccess), not in CAE.

Split from `fldlib` deliberately: these modules open ODBs and must run in the
`abaqus python` interpreter, whereas `fldlib` builds models and must run in
`abaqus cae`. Keeping them apart stops you importing something that cannot work
in the interpreter you happen to be in.

Run them as::

    abaqus python -m postproc.energy  job-name.odb
    abaqus python lib/postproc/energy.py job-name.odb
"""

__version__ = '0.1.0'
