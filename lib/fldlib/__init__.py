"""fldlib -- a small, readable helper library for large-displacement FE in Abaqus.

Design rules (please keep them if you extend this):

1. **Every function is a thin, documented wrapper over one Abaqus API call or one
   well-defined idiom.** If you cannot say in one line what keyword a function
   emits, it does not belong here.
2. **No hidden state.** Nothing reads a global model or a shelve database. You
   pass in the model / assembly / step you mean.
3. **Nothing is silently skipped.** If a helper cannot do what it was asked, it
   raises. Geotechnical models fail quietly and expensively; this library does not.
4. **Python 2.7 and 3 compatible.** Abaqus releases through 2023 use Python 2.7;
   Abaqus 2024 and later use Python 3.10+. `from __future__ import
   print_function` keeps the shared source valid across that transition.

Import from a script that Abaqus runs::

    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(REPO), 'lib'))
    from fldlib import ale, cel, steps, materials, report

`bootstrap()` below does that path insertion for you when a script is invoked as
``abaqus cae noGUI=examples/exNN_.../model.py``, where ``__file__`` is not always
set the way you would expect.
"""

from __future__ import print_function

__version__ = '0.1.0'

import os
import sys


def repo_root(start=None):
    """Return the repository root by walking up from `start` until LICENSE is found.

    Abaqus does not reliably set `__file__` for the top-level script, so callers
    should pass an explicit path when they have one, and fall back to the
    current working directory otherwise.
    """
    here = os.path.abspath(start or os.getcwd())
    if os.path.isfile(here):
        here = os.path.dirname(here)
    for _ in range(8):
        if os.path.isfile(os.path.join(here, 'LICENSE')) and \
           os.path.isdir(os.path.join(here, 'lib', 'fldlib')):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            break
        here = parent
    raise RuntimeError(
        'Could not locate the fe-large-displacement repository root from %r. '
        'Pass the path explicitly, or set the FLD_REPO environment variable.'
        % (start or os.getcwd()))


def bootstrap(start=None):
    """Put `<repo>/lib` on sys.path and return the repository root.

    Call this as the first thing in an example script::

        from fldlib import bootstrap      # only works if lib is already on path
        # ...or, for a cold start:
        import sys, os
        sys.path.insert(0, os.environ.get('FLD_REPO', r'C:\building\fe-large-displacement') + '/lib')
    """
    root = os.environ.get('FLD_REPO') or repo_root(start)
    libdir = os.path.join(root, 'lib')
    if libdir not in sys.path:
        sys.path.insert(0, libdir)
    return root
