"""Creating, writing, verifying and submitting jobs.

The workflow every example here follows, and the reason for each step:

    job = make_explicit_job(...)      # build it
    job.writeInput()                  # write the deck WITHOUT submitting
    inpedit.inject_*(...)             # apply keywords CAE cannot write
    InpCheck(...).report()            # prove the deck says what you think
    submit(job)                       # only now spend machine time

Writing the input first and checking it is the habit that separates a
productive week from a wasted one. A three-day explicit job that turns out to
have had an empty ALE domain is three days you do not get back, and Abaqus will
not tell you.

Parallelisation notes for large-displacement work
-------------------------------------------------
* **Loop-level parallelisation is not available on Windows.** The job aborts at
  the first increment with 'Loop level parallelization is not available on this
  platform'. Use domain-level.
* **Domain-level requires `numDomains` to be a multiple of `numCpus`.**
* With multiple domains, **nodes shared between parallel domains are marked
  nonadaptive**, which cripples ALE across a domain boundary. For a *study* of
  ALE mechanics, run single-domain. For *production*, split the adaptive zone
  into several well-separated regions so the packager distributes them -- see
  docs/03-ale-multi-region-parallel.md.
* A single ALE region is consolidated into one parallel domain and unbalances
  the decomposition badly (measured weight 15.1 against a balanced 6.1 on
  15 CPUs). That is a 2.5x load imbalance you pay for on every increment.
"""

from __future__ import print_function

import os
import re
import time


def make_explicit_job(model_name, job_name, n_cpus=1, n_domains=None,
                      user_subroutine='', double=True, description='',
                      memory_percent=90):
    """An Abaqus/Explicit job configured the way this repository assumes.

    `double=True` sets `explicitPrecision=DOUBLE_PLUS_PACK` and
    `nodalOutputPrecision=FULL`. This is not optional for soil: single precision
    accumulates enough error over a few hundred thousand increments to visibly
    corrupt a penetration curve, and it interacts badly with user subroutines
    written in double precision.

    `n_domains` defaults to `n_cpus`. Domain-level parallelisation is used
    because loop-level is unavailable on Windows.
    """
    from abaqus import mdb
    from abaqusConstants import (ANALYSIS, DOMAIN, DOUBLE_PLUS_PACK, SINGLE,
                                 FULL, OFF, ON, PERCENTAGE, DEFAULT)

    n_domains = n_domains or n_cpus
    if n_domains % n_cpus != 0:
        raise ValueError('numDomains (%d) must be a multiple of numCpus (%d) '
                         'for domain-level parallelisation'
                         % (n_domains, n_cpus))

    return mdb.Job(
        name=job_name, model=model_name, description=description,
        type=ANALYSIS,
        explicitPrecision=DOUBLE_PLUS_PACK if double else SINGLE,
        nodalOutputPrecision=FULL if double else SINGLE,
        numCpus=n_cpus, numDomains=n_domains,
        parallelizationMethodExplicit=DOMAIN,
        multiprocessingMode=DEFAULT,
        userSubroutine=user_subroutine,
        memory=memory_percent, memoryUnits=PERCENTAGE,
        echoPrint=OFF, modelPrint=OFF, historyPrint=OFF, contactPrint=OFF,
        getMemoryFromAnalysis=True,
    )


def make_implicit_job(model_name, job_name, n_cpus=1, user_subroutine='',
                      description='', memory_percent=90):
    """An Abaqus/Standard job, for the geostatic and small-strain baselines."""
    from abaqus import mdb
    from abaqusConstants import ANALYSIS, OFF, PERCENTAGE, THREADS, DEFAULT

    return mdb.Job(
        name=job_name, model=model_name, description=description,
        type=ANALYSIS,
        numCpus=n_cpus, numDomains=n_cpus,
        multiprocessingMode=DEFAULT,
        userSubroutine=user_subroutine,
        memory=memory_percent, memoryUnits=PERCENTAGE,
        echoPrint=OFF, modelPrint=OFF, historyPrint=OFF, contactPrint=OFF,
        getMemoryFromAnalysis=True,
    )


def write_input(job, workdir=None, printer=print):
    """Write the deck and return its path. Does not submit."""
    job.writeInput()
    path = os.path.join(workdir or os.getcwd(), job.name + '.inp')
    if not os.path.isfile(path):
        raise IOError('writeInput() did not produce %s -- check the working '
                      'directory Abaqus is using (os.getcwd() is %s)'
                      % (path, os.getcwd()))
    printer('  wrote deck: %s (%d lines)'
            % (path, sum(1 for _ in open(path))))
    return path


def submit(job, wait=True, printer=print):
    """Submit and (by default) block until the job finishes.

    Returns the wall time in seconds. Does not raise when the job aborts:
    an aborted job is a legitimate and often *expected* outcome in this
    repository -- the whole point of the first example is to watch a Lagrangian
    mesh fail. Use `status()` to find out what happened.
    """
    t0 = time.time()
    printer('  submitting %s ...' % job.name)
    from abaqusConstants import OFF
    job.submit(consistencyChecking=OFF)
    if wait:
        job.waitForCompletion()
    dt = time.time() - t0
    printer('  %s finished in %.1f s' % (job.name, dt))
    return dt


# ---------------------------------------------------------------------------
# Reading what happened
# ---------------------------------------------------------------------------

_ABORT = re.compile(r'^\s*\*\*\*ERROR[:\s]*(.+)$', re.MULTILINE)
_WARN = re.compile(r'^\s*\*\*\*WARNING[:\s]*(.+)$', re.MULTILINE)


def status(job_name, workdir=None, printer=print):
    """Summarise a finished job from its `.sta`, `.msg` and `.dat`.

    Returns a dict with `completed`, `increments`, `step_time`, `errors` and
    `warnings`. Print it after every run. In particular, an explicit job that
    stopped early still writes a valid ODB, and if you do not read the `.sta`
    you will happily post-process half an analysis.
    """
    base = os.path.join(workdir or os.getcwd(), job_name)
    out = {'job': job_name, 'completed': False, 'increments': None,
           'step_time': None, 'errors': [], 'warnings': [], 'abort_reason': ''}

    sta = base + '.sta'
    if os.path.isfile(sta):
        lines = [ln.rstrip() for ln in open(sta)]
        out['completed'] = any('THE ANALYSIS HAS COMPLETED SUCCESSFULLY' in ln
                               for ln in lines)
        for ln in reversed(lines):
            fields = ln.split()
            if len(fields) >= 4 and fields[0].isdigit():
                try:
                    out['increments'] = int(fields[0])
                    out['step_time'] = float(fields[3])
                except (ValueError, IndexError):
                    pass
                break

    for ext in ('.msg', '.dat'):
        path = base + ext
        if not os.path.isfile(path):
            continue
        text = open(path).read()
        out['errors'].extend(m.strip() for m in _ABORT.findall(text))
        out['warnings'].extend(m.strip() for m in _WARN.findall(text))

    printer('  job %-28s completed=%s  increments=%s  step time=%s'
            % (job_name, out['completed'], out['increments'], out['step_time']))
    if out['errors']:
        out['abort_reason'] = out['errors'][0]
        printer('  first error: %s' % out['errors'][0][:150])
        for err in out['errors'][1:4]:
            printer('        also : %s' % err[:150])
    seen = set()
    for w in out['warnings']:
        key = w[:60]
        if key in seen:
            continue
        seen.add(key)
        if len(seen) <= 5:
            printer('  warning    : %s' % w[:150])
    return out


def distortion_aborted(status_dict):
    """True when a job stopped for the reasons a Lagrangian mesh stops.

    The two messages you will meet constantly:

    * 'Excessive distortion of element number N'
    * 'The ratio of deformation speed to wave speed exceeds 1.0000 in at least
      one element'

    The second usually means an element has collapsed so fast that the
    distortion detector never tripped -- it is the same failure, further along.
    """
    text = ' '.join(status_dict.get('errors', [])).lower()
    return ('excessive distortion' in text
            or 'deformation speed to wave speed' in text
            or 'negative element volume' in text
            or 'negative eigenvalue' in text)
