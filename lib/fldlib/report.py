"""Logging, banners and .inp verification.

Two jobs:

* **Tee everything to a file.** Abaqus/CAE's console scrollback is lost the
  moment the session ends, and `noGUI` runs on a compute node have no console at
  all. Every example writes a `.log` next to its job files.

* **Verify the generated .inp.** This is the single most useful habit in this
  repository. The CAE API will happily accept an argument it does not
  understand, or silently omit a keyword because your value equalled the
  default. The only ground truth is the deck Abaqus actually writes. So every
  example asserts on its own .inp before submitting.
"""

from __future__ import print_function

import codecs
import os
import re
import sys
import time


try:                      # pragma: no cover - Python 2 / 3 straddle
    unicode_type = unicode
except NameError:         # pragma: no cover
    unicode_type = str


class Tee(object):
    """Write to the console and to a log file at once."""

    def __init__(self, path, echo=True):
        self.path = path
        self.echo = echo
        self._fh = codecs.open(path, 'w', 'utf-8')
        self._t0 = time.time()

    def write(self, text):
        if self.echo:
            sys.__stdout__.write(text)
            sys.__stdout__.flush()
        self._fh.write(text if isinstance(text, unicode_type) else text.decode('utf-8', 'replace'))
        self._fh.flush()

    def flush(self):
        self._fh.flush()

    def close(self):
        self._fh.close()

    def elapsed(self):
        return time.time() - self._t0


def start_log(path, title):
    """Redirect stdout to a Tee and print an opening banner. Returns the Tee."""
    tee = Tee(path)
    sys.stdout = tee
    banner(title, level=0)
    print('log file : %s' % path)
    print('started  : %s' % time.strftime('%Y-%m-%d %H:%M:%S'))
    print('python   : %s' % sys.version.split()[0])
    return tee


def stop_log(tee):
    print('')
    banner('finished in %.1f s' % tee.elapsed(), level=1)
    sys.stdout = sys.__stdout__
    tee.close()


def banner(text, level=0):
    """Print a section banner. level 0 = heavy rule, 1 = light rule, 2 = dashes."""
    rules = {0: '=', 1: '-', 2: '.'}
    rule = rules.get(level, '-') * 95
    print('')
    print(rule)
    print(text)
    print(rule)


def kv(key, value, width=34):
    """Print an aligned key/value line. Use it for every input you care about."""
    print('  {0:<{1}} {2}'.format(key, width, value))


# ---------------------------------------------------------------------------
# .inp verification
# ---------------------------------------------------------------------------

class InpCheck(object):
    r"""Assert that a written .inp contains (or does not contain) what you expect.

    Usage::

        chk = InpCheck('job-ale-box.inp')
        chk.requires(r'^\*Adaptive Mesh,', 'adaptive mesh domain defined')
        chk.requires(r'elset=ALE_Box', 'domain is restricted to the box elset')
        chk.forbids(r'^\*Adaptive Mesh Controls.*smoothing objective=GRADED',
                    'controls left at the UNIFORM default')
        chk.report()          # raises AssertionError listing every failure

    The `report()` call raises once with the complete list rather than dying on
    the first failure, so a single run tells you everything that is wrong.
    """

    def __init__(self, inp_path):
        if not os.path.isfile(inp_path):
            raise IOError('no such .inp: %s' % inp_path)
        self.path = inp_path
        with open(inp_path) as fh:
            self.text = fh.read()
        self.results = []

    def _search(self, pattern):
        return re.search(pattern, self.text, re.IGNORECASE | re.MULTILINE)

    def requires(self, pattern, why):
        m = self._search(pattern)
        self.results.append((bool(m), 'REQUIRE', pattern, why,
                             m.group(0).strip() if m else ''))
        return bool(m)

    def forbids(self, pattern, why):
        m = self._search(pattern)
        self.results.append((not m, 'FORBID ', pattern, why,
                             m.group(0).strip() if m else ''))
        return not m

    def count(self, pattern, expected, why):
        n = len(re.findall(pattern, self.text, re.IGNORECASE | re.MULTILINE))
        self.results.append((n == expected, 'COUNT=%d' % expected, pattern,
                             why, 'found %d' % n))
        return n == expected

    def report(self, raise_on_fail=True):
        banner('.inp verification: %s' % os.path.basename(self.path), level=1)
        failures = []
        for ok, kind, pattern, why, hit in self.results:
            mark = 'PASS' if ok else 'FAIL'
            print('  [%s] %s  %s' % (mark, kind, why))
            if hit:
                print('         matched: %s' % hit[:110])
            if not ok:
                failures.append('%s %s  (%s)' % (kind, pattern, why))
        print('  %d checks, %d failed' % (len(self.results), len(failures)))
        if failures and raise_on_fail:
            raise AssertionError(
                'deck verification failed for %s:\n    %s'
                % (self.path, '\n    '.join(failures)))
        return not failures


def show_keyword_block(inp_path, keyword, context=3):
    """Print every occurrence of a keyword in the .inp with surrounding lines.

    Teaching aid: run this on `*Adaptive Mesh`, `*Section Controls`,
    `*Eulerian Section` or `*Depvar` to see exactly what CAE wrote (and,
    just as importantly, what it left out because it equalled the default).
    """
    with open(inp_path) as fh:
        lines = fh.readlines()
    pat = re.compile(re.escape(keyword), re.IGNORECASE)
    hits = [i for i, ln in enumerate(lines) if pat.search(ln)]
    if not hits:
        print('  (%s not present in %s)' % (keyword, os.path.basename(inp_path)))
        return
    for i in hits:
        lo, hi = max(0, i - context), min(len(lines), i + context + 1)
        print('  --- %s line %d ---' % (os.path.basename(inp_path), i + 1))
        for j in range(lo, hi):
            print('  %s%s' % ('>>' if j == i else '  ', lines[j].rstrip()))
