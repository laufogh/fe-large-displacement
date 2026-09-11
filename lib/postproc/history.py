"""Penetration curves: force and displacement of the structure, out of the ODB.

    abaqus python lib/postproc/history.py <job>.odb RP-SET-NAME [out.csv]

The quantity you almost always want from a penetration analysis is resistance
against depth. In an explicit analysis with a rigid structure driven by a
velocity boundary condition on a reference point, that is the reaction force at
the RP against its displacement.

Two things that catch people out:

* **Use the reaction force, not the contact force**, unless you have a specific
  reason. RF at a constrained RP is the exact work-conjugate of the prescribed
  motion and includes everything: tip resistance, skirt friction, inertia of the
  structure. Summing contact forces over a surface misses whatever is not in
  that surface.
* **The force history is noisy.** It is a dynamic analysis; there is real
  oscillation at the natural frequency of the soil column plus numerical noise
  from contact. Filter it before you plot it, and say in the caption that you
  did. `moving_average` here is deliberately the dumbest possible filter so that
  nobody mistakes it for signal processing -- if the answer depends on the
  filter, the run was not quasi-static and no filter will save it.
"""

from __future__ import print_function

import sys


def read_rp_history(odb_path, set_name, step_name=None):
    """Reaction force and displacement history at a node set (normally one RP).

    Returns ``{'time': [], 'u1': [], 'u2': [], 'u3': [], 'rf1': [], ...}``.

    The set must contain exactly one node. A set with several nodes has no
    single displacement, and summing RF over it is usually not what you want
    either.
    """
    from odbAccess import openOdb

    odb = openOdb(odb_path, readOnly=True)
    try:
        keys = ('U1', 'U2', 'U3', 'RF1', 'RF2', 'RF3')
        out = dict((k.lower(), []) for k in keys)
        out['time'] = []
        t_offset = 0.0

        steps = [step_name] if step_name else list(odb.steps.keys())
        for sname in steps:
            step = odb.steps[sname]
            matches = [k for k in step.historyRegions
                       if set_name.upper() in k.upper()]
            if not matches:
                available = ', '.join(sorted(step.historyRegions.keys())[:8])
                raise KeyError(
                    'no history region matching %r in step %r. Available: %s. '
                    'Did you request history output at the reference point?'
                    % (set_name, sname, available))
            region = step.historyRegions[matches[0]]

            times = None
            for key in keys:
                if key not in region.historyOutputs:
                    continue
                data = region.historyOutputs[key].data
                if times is None:
                    times = [t for t, _ in data]
                out[key.lower()].extend([v for _, v in data])
            if times:
                out['time'].extend([t + t_offset for t in times])
                t_offset += times[-1]
        return out
    finally:
        odb.close()


def moving_average(series, window=25):
    """A centred boxcar filter. Deliberately the simplest thing that works.

    If your conclusion changes when you change `window`, the underlying result
    is dominated by dynamics and the fix is a slower loading rate or less mass
    scaling, not a better filter.
    """
    if window <= 1 or len(series) < window:
        return list(series)
    half = window // 2
    out = []
    for i in range(len(series)):
        lo = max(0, i - half)
        hi = min(len(series), i + half + 1)
        chunk = series[lo:hi]
        out.append(sum(chunk) / float(len(chunk)))
    return out


def penetration_curve(hist, direction=3, sign=-1.0, filter_window=25):
    """Depth and resistance as positive-increasing quantities.

    `direction` is the global axis of penetration (3 = z by default here) and
    `sign` is -1 when penetration is in the negative axis direction, which it
    normally is. The result is ``(depth, resistance, resistance_raw)`` with both
    positive going into the soil, which is what you want to plot.
    """
    u = hist['u%d' % direction]
    rf = hist['rf%d' % direction]
    depth = [sign * v for v in u]
    raw = [sign * v for v in rf]
    return depth, moving_average(raw, filter_window), raw


def write_csv(path, columns, headers):
    """Write columns to CSV. No dependency on numpy or pandas: Abaqus python
    does not always have them, and this needs to run on the compute node."""
    n = min(len(c) for c in columns)
    fh = open(path, 'w')
    try:
        fh.write(','.join(headers) + '\n')
        for i in range(n):
            fh.write(','.join('%.10g' % c[i] for c in columns) + '\n')
    finally:
        fh.close()
    return path


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) < 2:
        print(__doc__)
        print('usage: abaqus python history.py <job>.odb <RP set name> [out.csv]')
        return 2
    odb_path, set_name = argv[0], argv[1]
    out_csv = argv[2] if len(argv) > 2 else odb_path.replace('.odb', '_rp.csv')

    hist = read_rp_history(odb_path, set_name)
    depth, resistance, raw = penetration_curve(hist)

    write_csv(out_csv,
              [hist['time'], depth, raw, resistance],
              ['time_s', 'depth_m', 'resistance_N_raw', 'resistance_N_filtered'])

    print('  %d points written to %s' % (len(depth), out_csv))
    if depth:
        print('  max depth       %.6g m' % max(depth))
        print('  peak resistance %.6g N (raw)  %.6g N (filtered)'
              % (max(raw), max(resistance)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
