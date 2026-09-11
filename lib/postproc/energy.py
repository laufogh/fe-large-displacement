"""The quasi-static acceptance test.

Run this on every explicit result before you believe any number that came out
of it. It answers the only question that matters about an explicit run of a
static problem: *did the dynamics stay negligible?*

    abaqus python lib/postproc/energy.py <job>.odb

Thresholds used here, and where they come from
----------------------------------------------
``ALLKE/ALLIE < 0.05``   Widely used rule of thumb for "quasi-static enough to
                         look at". Above this the inertia is carrying load and
                         your resistance is too high.
``ALLKE/ALLIE < 0.01``   The bar to clear before quoting a number in a paper.
``ALLAE/ALLIE < 0.05``   Hourglass energy. Above this the reduced-integration
                         elements are deforming in zero-energy modes and the
                         stiffness is fictitious. Enhanced hourglass control
                         took this from 16.5 % to 3.8 % in the verification
                         study -- see docs/04-section-controls.md.
``|ETOTAL|/ALLIE < 0.01``Total energy balance. A drifting ETOTAL means energy is
                         entering or leaving the model through something you did
                         not intend: mass scaling, contact, or a user material
                         that is not thermodynamically consistent.
``ALLDC``                Distortion-control work. Expected to be ~0. A nonzero
                         value means the penalty is doing real work and is
                         holding your mesh together -- the result may still be
                         usable but the mesh is at its limit.

These are guides, not physics. A ratio of 0.06 is not a failure and 0.04 is not
a certificate. Look at the *history*: a kinetic energy that is small at the end
but spiked to 40 % during the ramp has already damaged your early penetration
curve.
"""

from __future__ import print_function

import sys


CHANNELS = ('ALLIE', 'ALLKE', 'ALLAE', 'ALLDC', 'ALLVD', 'ALLWK', 'ALLPD',
            'ALLSE', 'ETOTAL')

LIMITS = {
    'ALLKE/ALLIE': (0.05, 0.01),   # (acceptable, publishable)
    'ALLAE/ALLIE': (0.05, 0.02),
    'ETOTAL/ALLIE': (0.01, 0.005),
}


def read_energies(odb_path, step_name=None):
    """Extract the whole-model energy histories from an ODB.

    Returns ``{'time': [...], 'ALLIE': [...], ...}``. Missing channels come back
    as empty lists rather than raising, because which channels exist depends on
    what you requested and on the analysis type.
    """
    from odbAccess import openOdb

    odb = openOdb(odb_path, readOnly=True)
    try:
        steps = ([step_name] if step_name else list(odb.steps.keys()))
        out = dict((c, []) for c in CHANNELS)
        out['time'] = []
        t_offset = 0.0

        for sname in steps:
            step = odb.steps[sname]
            region = None
            for key in step.historyRegions:
                if key.lower().startswith('assembly'):
                    region = step.historyRegions[key]
                    break
            if region is None:
                continue

            times = None
            for channel in CHANNELS:
                if channel not in region.historyOutputs:
                    continue
                data = region.historyOutputs[channel].data
                if times is None:
                    times = [t for t, _ in data]
                out[channel].extend([v for _, v in data])
            if times:
                out['time'].extend([t + t_offset for t in times])
                t_offset += times[-1]
        return out
    finally:
        odb.close()


def ratios(energies):
    """Peak and final ratios of the diagnostic channels against ALLIE."""
    allie = energies.get('ALLIE') or []
    if not allie:
        raise ValueError('no ALLIE in this ODB -- request the energy history '
                         'output (steps.energy_output) and rerun. Without it '
                         'there is no way to judge whether the run was '
                         'quasi-static.')
    ref = max(abs(v) for v in allie) or 1.0

    def ratio_series(name):
        series = energies.get(name) or []
        return [abs(v) / ref for v in series]

    out = {}
    for name in ('ALLKE', 'ALLAE', 'ALLDC', 'ALLVD', 'ETOTAL'):
        r = ratio_series(name)
        out[name + '/ALLIE'] = {
            'peak': max(r) if r else 0.0,
            'final': r[-1] if r else 0.0,
            'peak_at': (energies['time'][r.index(max(r))]
                        if r and energies.get('time') else None),
        }
    out['ALLIE_max'] = ref
    return out


def verdict(r, printer=print):
    """Print the acceptance table and return 'publishable' / 'acceptable' /
    'not quasi-static'."""
    printer('')
    printer('  %-16s %10s %10s %10s   %s'
            % ('ratio', 'peak', 'final', 'peak at', 'verdict'))
    printer('  ' + '-' * 72)

    worst = 'publishable'
    for key, (acceptable, publishable) in sorted(LIMITS.items()):
        info = r.get(key)
        if info is None:
            continue
        peak = info['peak']
        if peak > acceptable:
            grade = 'NOT QUASI-STATIC (> %.0f %%)' % (100 * acceptable)
            worst = 'not quasi-static'
        elif peak > publishable:
            grade = 'acceptable (> %.1f %%)' % (100 * publishable)
            if worst == 'publishable':
                worst = 'acceptable'
        else:
            grade = 'good'
        at = info['peak_at']
        printer('  %-16s %9.3f%% %9.3f%% %10s   %s'
                % (key, 100 * peak, 100 * info['final'],
                   ('%.4g s' % at) if at is not None else '-', grade))

    dc = r.get('ALLDC/ALLIE', {}).get('peak', 0.0)
    if dc > 1e-9:
        printer('  %-16s %9.3f%% %9s %10s   distortion control is doing real '
                'work -- the mesh is at its limit'
                % ('ALLDC/ALLIE', 100 * dc, '', ''))

    printer('  ' + '-' * 72)
    printer('  ALLIE peak = %.6g J' % r['ALLIE_max'])
    printer('  VERDICT: %s' % worst.upper())
    return worst


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(__doc__)
        print('usage: abaqus python energy.py <job>.odb [step name]')
        return 2
    odb_path = argv[0]
    step = argv[1] if len(argv) > 1 else None

    print('=' * 74)
    print('QUASI-STATIC ENERGY CHECK: %s' % odb_path)
    print('=' * 74)
    energies = read_energies(odb_path, step)
    r = ratios(energies)
    grade = verdict(r)
    return 0 if grade != 'not quasi-static' else 1


if __name__ == '__main__':
    sys.exit(main())
