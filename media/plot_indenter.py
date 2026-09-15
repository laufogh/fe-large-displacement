"""Overlay strip-indenter load-displacement curves.

    python media/plot_indenter.py

Reads the CSVs next to this script (from lib/postproc/history.py) and writes
media/indenter-load-displacement.png. Explicit force is the filtered column.
"""
from __future__ import print_function

import csv
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'indenter-load-displacement.png')

CURVES = (
    ('implicit.csv', 'implicit'),
    ('implicit_ale.csv', 'implicit ALE'),
    ('explicit.csv', 'explicit'),
    ('explicit_ale.csv', 'explicit ALE'),
    ('explicit_cel.csv', 'explicit CEL'),
)


def load_csv(path):
    depth, force = [], []
    with open(path, 'r') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            depth.append(float(row['depth_m']) * 1000.0)
            key = 'resistance_N_filtered' if 'explicit' in os.path.basename(path) else 'resistance_N_raw'
            if key not in row:
                key = 'resistance_N_raw'
            force.append(float(row[key]) / 1000.0)
    return cutoff_collapse(depth, force)


def cutoff_collapse(depth, force):
    """Drop the tail after the result snaps back toward zero."""
    if len(depth) < 3:
        return depth, force
    dmax = 0.0
    cut = 0
    for i, d in enumerate(depth):
        if dmax > 1.0 and d < 0.5 * dmax:
            break
        if d >= dmax:
            dmax = d
        cut = i + 1
    return depth[:cut], force[:cut]


def main():
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for fname, label in CURVES:
        path = os.path.join(HERE, fname)
        if not os.path.isfile(path):
            print('missing %s' % path)
            continue
        depth, force = load_csv(path)
        if not depth:
            print('empty %s' % path)
            continue
        ax.plot(depth, force, label=label, lw=1.6)
    ax.set_xlabel('penetration (mm)')
    ax.set_ylabel('resistance (kN)')
    ax.legend(frameon=False)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT, dpi=160)
    print('wrote %s' % OUT)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
