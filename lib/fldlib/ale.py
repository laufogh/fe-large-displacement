"""Arbitrary Lagrangian-Eulerian (ALE) adaptive meshing.

Abaqus/Explicit is the production tool. Abaqus/Standard also has ALE, on
geometrically nonlinear ``*Static`` (and a few coupled) steps, with a single
smoothing algorithm, no initial mesh sweeps, and Lagrangian domains only. That
path is enough to attach a domain in the implicit-ALE model. It is not enough
for skirt penetration. Use Explicit ALE, then CEL, when Standard ALE stops
helping.

What ALE actually is, in one paragraph
--------------------------------------
The mesh stays topologically fixed -- same elements, same connectivity, same
element count -- but the *nodes* are allowed to move independently of the
material. Every `frequency` increments Abaqus performs `meshSweeps` sweeps that
relocate nodes towards a smoother configuration, then *advects* the solution
(stress, state variables, momentum) from the old node positions to the new ones.
You get a Lagrangian boundary (the free surface is still tracked exactly) with a
partially Eulerian interior. That is why ALE is the right first tool for a
problem such as caisson or footing penetration, where the boundary matters and
the distortion is concentrated in a known region.

What it is not: it is not a remesh. It cannot recover from a mesh that is
already tangled, it cannot add elements where you need them, and it cannot
handle material separating and rejoining. When the deformation is large enough
that material has to flow around the structure and close behind it, you need CEL
(see `cel.py`).

Hard-won facts, all verified on Abaqus 2021 (see docs/02-ale-adaptive-meshing.md)
--------------------------------------------------------------------------------
* The domain may contain **only first-order reduced-integration solids**
  (C3D8R, CAX4R, CPE4R...). Every other element type in the set is silently
  nonadaptive.
* CAE supports exactly **one adaptive mesh domain per step**. Multiple regions
  need either `AdaptiveMeshDomain` called once per region on different steps, or
  keyword editing. `add_domain` below raises rather than letting the second call
  silently replace the first.
* The `*ADAPTIVE MESH` keyword reference says the default `MESH SWEEPS` is 5.
  The ALE guide and the actual CAE/solver default is **1**. Trust the solver.
* CAE omits `frequency` and `mesh sweeps` from the .inp when they equal the
  defaults (10 and 1). A missing keyword parameter is *not* evidence that the
  setting did not take.
* A domain that is defined but never sweeps raises no error and writes no
  warning. The only proof that ALE ran is a `Summary Diagnostics for Adaptive
  Meshing` block in the `.msg` with a nonzero percentage of nodes moved --
  which is why `inject_diagnostics()` exists and why every ALE example here
  calls it.
* With **domain-level parallelisation**, nodes shared between parallel domains
  are marked nonadaptive. A single adaptive region is consolidated into one
  parallel domain and unbalances the decomposition badly (weight 15.1 against a
  balanced 6.1 on 15 CPUs). Several *well-separated* regions are distributed
  across different domains and cost nothing. Adjacent regions sharing a face
  behave as one. See docs/03-ale-multi-region-parallel.md.
"""

from __future__ import print_function

import math
import re


# ---------------------------------------------------------------------------
# Element sets for restricted domains
# ---------------------------------------------------------------------------

def box_element_set(assembly, instance, name, box, required=True):
    """Assembly-level element set of every element whose centroid is in `box`.

    `box` is a dict with keys xmin, xmax, ymin, ymax, zmin, zmax.
    Returns ``(n_elements, centroid_bbox)`` where centroid_bbox is
    ``((xmin, xmax), (ymin, ymax), (zmin, zmax))`` of the elements actually
    selected -- always print it, because it is how you find out that your box
    caught two rows of elements instead of the twenty you intended.

    Implementation note, found the hard way: the Abaqus kernel **rejects**
    ``assembly.Set(elements=[...])`` when handed a plain Python list of Element
    objects belonging to a dependent instance. It fails with the unhelpful
    'Feature creation failed'. It accepts only an ElementArray, or slices of
    one. So the selected indices are stitched back into an ElementArray by
    concatenating slices over maximal runs of consecutive indices.
    """
    idxs, xs, ys, zs = [], [], [], []
    for i, el in enumerate(instance.elements):
        nodes = el.getNodes()
        n = float(len(nodes))
        cx = cy = cz = 0.0
        for nd in nodes:
            c = nd.coordinates
            cx += c[0]
            cy += c[1]
            cz += c[2]
        cx, cy, cz = cx / n, cy / n, cz / n
        if (box['xmin'] <= cx <= box['xmax'] and
                box['ymin'] <= cy <= box['ymax'] and
                box['zmin'] <= cz <= box['zmax']):
            idxs.append(i)
            xs.append(cx)
            ys.append(cy)
            zs.append(cz)

    if not idxs:
        if not required:
            return 0, None
        raise RuntimeError(
            'ALE box element set %r is EMPTY -- the adaptive mesh domain would '
            'contain nothing and ALE would silently do nothing. Box was %r. '
            'Check it against the actual mesh extent.' % (name, box))

    arr = None
    run_start = run_end = idxs[0]
    for i in idxs[1:] + [-1]:
        if i == run_end + 1:
            run_end = i
        else:
            chunk = instance.elements[run_start:run_end + 1]
            arr = chunk if arr is None else arr + chunk
            run_start = run_end = i

    assembly.Set(name=name, elements=arr)
    n_set = len(assembly.sets[name].elements)
    if n_set != len(idxs):
        raise AssertionError('ALE box set size mismatch: CAE=%d filter=%d'
                             % (n_set, len(idxs)))
    bbox = ((min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs)))
    return len(idxs), bbox


def cylindrical_element_set(assembly, instance, name, r_min, r_max,
                            z_min, z_max, required=True):
    """Assembly element set selected by centroid radius and elevation.

    This is the appropriate selector for axisymmetric geometry represented by
    a 3-D sector. A rectangular bounding box cannot distinguish a soil plug
    from the annulus around a circular skirt and can therefore create
    overlapping adaptive-mesh domains.
    """
    if r_min < 0.0 or r_max <= r_min:
        raise ValueError('need 0 <= r_min < r_max (got %g, %g)'
                         % (r_min, r_max))
    if z_max <= z_min:
        raise ValueError('need z_min < z_max (got %g, %g)'
                         % (z_min, z_max))

    idxs, xs, ys, zs = [], [], [], []
    for i, el in enumerate(instance.elements):
        nodes = el.getNodes()
        n = float(len(nodes))
        cx = sum(nd.coordinates[0] for nd in nodes) / n
        cy = sum(nd.coordinates[1] for nd in nodes) / n
        cz = sum(nd.coordinates[2] for nd in nodes) / n
        radius = math.sqrt(cx * cx + cy * cy)
        if r_min <= radius <= r_max and z_min <= cz <= z_max:
            idxs.append(i)
            xs.append(cx)
            ys.append(cy)
            zs.append(cz)

    if not idxs:
        if not required:
            return 0, None
        raise RuntimeError(
            'cylindrical element set %r is EMPTY -- radius %g..%g, '
            'z %g..%g. Check the selector against the actual mesh.'
            % (name, r_min, r_max, z_min, z_max))

    arr = None
    run_start = run_end = idxs[0]
    for i in idxs[1:] + [-1]:
        if i == run_end + 1:
            run_end = i
        else:
            chunk = instance.elements[run_start:run_end + 1]
            arr = chunk if arr is None else arr + chunk
            run_start = run_end = i

    assembly.Set(name=name, elements=arr)
    n_set = len(assembly.sets[name].elements)
    if n_set != len(idxs):
        raise AssertionError('cylindrical set size mismatch: CAE=%d filter=%d'
                             % (n_set, len(idxs)))
    bbox = ((min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs)))
    return len(idxs), bbox


def describe_box_set(name, n, bbox, total=None, printer=print):
    """Print what `box_element_set` selected. Call this every single time."""
    share = ('' if total is None else '  (%.1f %% of %d)'
             % (100.0 * n / float(total), total))
    printer('  element set %-18s %6d elements%s' % (name, n, share))
    if bbox is not None:
        printer('    centroid extent  x: %+.4f .. %+.4f' % bbox[0])
        printer('                     y: %+.4f .. %+.4f' % bbox[1])
        printer('                     z: %+.4f .. %+.4f' % bbox[2])


# ---------------------------------------------------------------------------
# Controls and domain
# ---------------------------------------------------------------------------

def make_controls(model, name, smoothing=None, curvature_refinement=None,
                  **kwargs):
    """Create `*Adaptive Mesh Controls`.

    `smoothing` is the abaqusConstants value UNIFORM (default) or GRADED; the
    CAE argument is confusingly called `smoothingPriority` but maps to the
    keyword parameter SMOOTHING OBJECTIVE.

    Leaving both arguments as None reproduces the solver defaults, and CAE then
    writes a bare `*Adaptive Mesh Controls, name=...` with the data line
    `1., 0., 0.` -- the volume / Laplacian / equipotential smoothing weights.
    There is no fourth weight for GRADED, whatever you may have read.
    """
    opts = {}
    if smoothing is not None:
        opts['smoothingPriority'] = smoothing
    if curvature_refinement is not None:
        opts['curvatureRefinement'] = curvature_refinement
    opts.update(kwargs)
    return model.AdaptiveMeshControl(name=name, **opts)


def add_domain(model, step_name, region, controls, frequency=10,
               mesh_sweeps=1, initial_mesh_sweeps=5):
    """Attach the (single) adaptive mesh domain to `step_name`.

    `region` may be an assembly Set or a Region. Passing an assembly Set is
    strongly preferred: the .inp then references *your* set name, so you can
    read the deck and see immediately what the domain covers. A Region built
    from `cells=...` makes CAE emit an internal `_PickedSetNN` and you lose that.

    `initial_mesh_sweeps` is an Explicit option. Pass ``None`` on a Standard
    ``*Static`` step: Abaqus/Standard has no initial mesh sweeps.

    Raises if a domain already exists on the step, because CAE would replace it
    without a word.
    """
    step = model.steps[step_name]
    if getattr(step, 'adaptiveMeshDomains', None):
        raise RuntimeError(
            'step %r already has an adaptive mesh domain (%s). Abaqus/CAE '
            'supports only one per step and would silently replace it.'
            % (step_name, list(step.adaptiveMeshDomains.keys())))
    kwargs = dict(
        region=region,
        controls=controls,
        frequency=frequency,
        meshSweeps=mesh_sweeps,
    )
    if initial_mesh_sweeps is not None:
        kwargs['initialMeshSweeps'] = initial_mesh_sweeps
    return step.AdaptiveMeshDomain(**kwargs)


# ---------------------------------------------------------------------------
# Diagnostics: proving the domain was ACTIVE, not merely defined
# ---------------------------------------------------------------------------

# The *Diagnostics keyword has no CAE API and must be injected into the written
# deck. The surgery lives in inpedit.py with the rest of the deck editing; it is
# re-exported here because it is, in practice, always used together with ALE.
from .inpedit import inject_diagnostics          # noqa: F401  (re-export)


_MSG_BLOCK = re.compile(
    r'Summary Diagnostics for Adaptive Meshing(.*?)(?=\n\s*\n|\Z)',
    re.DOTALL | re.IGNORECASE)
_PCT_MOVED = re.compile(r'Avg\.?\s*pctg\.?\s*of\s*Nodes\s*Moved\s*[:=]?\s*'
                        r'([0-9.eE+-]+)', re.IGNORECASE)
_SWEEPS = re.compile(r'Mesh\s*Sweeps\s*[:=]?\s*(\d+)', re.IGNORECASE)


def read_msg_activity(msg_path):
    """Parse a `.msg` for adaptive-meshing activity.

    Returns a dict::

        {'blocks': 418, 'pct_moved': [33.5, ...], 'avg_pct_moved': 33.55,
         'sweeps': [5, 1, 1, ...], 'active': True}

    `active` is the question you actually care about: did any sweep move any
    node? If `blocks` is 0 the domain never reported, and if `avg_pct_moved` is
    0.0 it reported but did nothing. Both mean your ALE is not working, and
    neither produces an error message from Abaqus.

    With domain-level parallelisation each parallel domain writes its own
    `.msg.N`; pass each in turn (a region reports only to the `.msg` of the
    domain that hosts it).
    """
    with open(msg_path) as fh:
        text = fh.read()

    blocks = _MSG_BLOCK.findall(text)
    pct = [float(v) for b in blocks for v in _PCT_MOVED.findall(b)]
    sweeps = [int(v) for b in blocks for v in _SWEEPS.findall(b)]
    avg = (sum(pct) / len(pct)) if pct else 0.0
    return {
        'path': msg_path,
        'blocks': len(blocks),
        'pct_moved': pct,
        'avg_pct_moved': avg,
        'sweeps': sweeps,
        'active': bool(blocks) and avg > 0.0,
    }


def assert_active(msg_path, printer=print, required=True):
    """Raise unless the .msg proves ALE actually moved nodes.

    Abaqus/Standard does not write the Explicit per-increment diagnostic
    block. Pass ``required=False`` on a Standard deck so a missing block is
    reported rather than treated as proof that the domain was inert.
    """
    info = read_msg_activity(msg_path)
    printer('  ALE activity in %s: %d diagnostic block(s), avg %.2f %% of '
            'nodes moved' % (msg_path, info['blocks'], info['avg_pct_moved']))
    if info['active']:
        return info
    msg = (
        'ALE was DEFINED BUT INERT in %s (%d blocks, avg %.3f %% nodes '
        'moved). Common causes: the domain elset is empty; the elements are '
        'not first-order reduced-integration; the step is not one ALE '
        'supports; *Diagnostics was never injected.'
        % (msg_path, info['blocks'], info['avg_pct_moved']))
    if required:
        raise AssertionError(msg)
    printer('  *** %s' % msg)
    printer('  (required=False: Standard .msg files may simply omit this block)')
    return info
