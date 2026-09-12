"""The run loop every example shares.

Each example is a list of **cases**. A case builds a model, writes a deck,
checks the deck, submits, and reports. The loop below does that for every case
in one Abaqus invocation, isolating failures so that one bad case does not cost
you the other five, and writing a per-case log plus a cross-case summary table.

Running every case of a study in one invocation matters more than it looks.
Abaqus/CAE takes 20-60 s to start, an interactive session is a poor place to
make a change you want to remember, and six separate runs produce six sets of
files whose differences nobody can reconstruct a week later. One invocation, one
master log, one summary table.

Environment variables the loop understands:

    FLD_WORKDIR    where to write job files (must have no spaces if you compile
                   a user subroutine)
    FLD_CASES      comma-separated subset, e.g. 'A,C'
    FLD_SUBMIT     0 to build and verify the decks without solving
    FLD_NCPU       CPUs per job
    FLD_NDOMAINS   parallel domains (default: same as FLD_NCPU)
"""

from __future__ import print_function

import os
import sys
import time
import traceback


def selected_cases(all_cases):
    """Filter `all_cases` (a list of case ids) by FLD_CASES."""
    want = os.environ.get('FLD_CASES', '').strip()
    if not want:
        return list(all_cases)
    ids = [c.strip() for c in want.split(',') if c.strip()]
    unknown = [c for c in ids if c not in all_cases]
    if unknown:
        raise ValueError('FLD_CASES names unknown case(s) %r; this study has %r'
                         % (unknown, list(all_cases)))
    return ids


def flag(name, default=True):
    raw = os.environ.get('FLD_' + name.upper())
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def run_study(study, cases, case_fn, workdir, printer=print):
    """Run `case_fn(case_id, workdir)` for each selected case, isolating errors.

    `case_fn` returns a dict which is merged into the summary row for that case.
    Anything it raises is caught, logged with a full traceback, and recorded as
    a failed row -- the study continues.

    Returns the list of summary rows.
    """
    from fldlib import report

    ids = selected_cases(cases)
    rows = []
    t_study = time.time()

    report.banner('STUDY %s  --  cases %s' % (study, ', '.join(ids)), level=0)
    printer('  work dir : %s' % workdir)
    printer('  submit   : %s' % flag('SUBMIT', True))

    for case_id in ids:
        report.banner('CASE %s' % case_id, level=1)
        t0 = time.time()
        row = {'case': case_id, 'ok': False, 'wall_s': 0.0, 'error': ''}
        try:
            result = case_fn(case_id, workdir) or {}
            row.update(result)
            row['ok'] = True
        except Exception as exc:                       # noqa: BLE001 - deliberate
            row['error'] = '%s: %s' % (type(exc).__name__, exc)
            printer('')
            printer('  *** CASE %s FAILED ***' % case_id)
            printer('  %s' % row['error'])
            printer('')
            traceback.print_exc(file=sys.stdout)
        row['wall_s'] = time.time() - t0
        rows.append(row)
        printer('  case %s finished in %.1f s (ok=%s)'
                % (case_id, row['wall_s'], row['ok']))

    report.banner('SUMMARY  %s   (%.1f s total)'
                  % (study, time.time() - t_study), level=0)
    summary_table(rows, printer=printer)
    return rows


def summary_table(rows, printer=print, columns=None):
    """Print a cross-case table. Columns are inferred from the rows unless given."""
    if not rows:
        printer('  (no cases run)')
        return

    skip = ('case', 'ok', 'error')
    if columns is None:
        columns = []
        for row in rows:
            for key in row:
                if key not in skip and key not in columns:
                    columns.append(key)

    widths = {}
    for col in columns:
        widths[col] = max(len(col),
                          max(len(_fmt(r.get(col))) for r in rows))

    header = '  %-6s %-4s ' % ('case', 'ok')
    header += ' '.join('%-*s' % (widths[c], c) for c in columns)
    printer(header)
    printer('  ' + '-' * (len(header) - 2))
    for row in rows:
        line = '  %-6s %-4s ' % (row['case'], 'yes' if row['ok'] else 'NO')
        line += ' '.join('%-*s' % (widths[c], _fmt(row.get(c)))
                         for c in columns)
        printer(line)
    printer('')
    failed = [r['case'] for r in rows if not r['ok']]
    if failed:
        printer('  FAILED CASES: %s' % ', '.join(failed))
        for row in rows:
            if not row['ok']:
                printer('    %s: %s' % (row['case'], row['error']))
    else:
        printer('  all %d case(s) completed' % len(rows))


def _fmt(value):
    if value is None:
        return '-'
    if isinstance(value, bool):
        return 'yes' if value else 'no'
    if isinstance(value, float):
        return '%.4g' % value
    return str(value)


def write_summary_csv(path, rows):
    """Write the summary rows to CSV so a sweep can be compared across runs."""
    if not rows:
        return None
    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    fh = open(path, 'w')
    try:
        fh.write(','.join(columns) + '\n')
        for row in rows:
            fh.write(','.join(
                '"%s"' % str(row.get(c, '')).replace('"', "'")
                for c in columns) + '\n')
    finally:
        fh.close()
    return path
