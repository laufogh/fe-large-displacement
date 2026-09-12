"""Coupled Eulerian-Lagrangian (CEL) modelling in Abaqus/Explicit.

When to reach for CEL instead of ALE
------------------------------------
ALE keeps the mesh attached to the material and merely smooths it. That works
until the material has to do something the mesh topology cannot follow: flow
around the tip of a skirt, close back over a penetrating object, form a cavity,
or separate and rejoin. At that point no amount of smoothing helps, and you move
the material through a fixed mesh instead.

In CEL the Eulerian mesh is a *fixed box of space*. Elements do not deform at
all. Each element carries a volume fraction (EVF) of each Eulerian material, and
the material is transported between elements every increment. The structure
stays Lagrangian and interacts with the Eulerian material through general
contact.

The three things beginners get wrong
------------------------------------
1. **The Eulerian part must be bigger than the material.** You need empty
   elements (EVF = 0) above the soil surface for heave to move into. If the soil
   fills the mesh to the top, heave is simply lost and your resistance is wrong
   -- with no warning at all. `void_thickness` in the examples exists for this.

2. **No free surface is tracked exactly.** The material boundary is
   reconstructed inside each element from the volume fractions, so it is only as
   sharp as your mesh. Expect a diffuse surface one element thick. This is the
   price you pay for the topology freedom, and it is why CEL is the wrong tool
   for a small-strain bearing-capacity problem.

3. **Geostatic equilibrium is harder.** There is no `*Geostatic` procedure for
   an Eulerian domain. You either apply gravity and let the domain settle
   dynamically (slow, and it rings), or you initialise the stress field
   directly. The examples here do the latter and then verify the domain is at
   rest before the structure moves.

Element type is `EC3D8R` from the EXPLICIT library, and the mesh must be a
structured hex grid. A swept or free mesh will be rejected.
"""

from __future__ import print_function


def eulerian_section(model, name, material, instance_key=None):
    """Create an `*Eulerian Section`.

    The `data` argument is a dict mapping the **Eulerian material instance
    name** to the **material name**. The instance name is an arbitrary label you
    choose; it is the handle that `MaterialAssignment` and the EVF output
    variables use. The convention `'<material>-1'` lowercased is what CAE
    generates interactively, and the examples here follow it so that decks
    written by hand and by CAE look the same.

    Returns ``(section, instance_key)``.
    """
    key = instance_key or (material.lower().replace(' ', '_') + '-1')
    section = model.EulerianSection(name=name, data={key: material})
    return section, key


def assign_material(model, assembly, instance, filled_region, name=None,
                    fraction=1.0, extra=()):
    """Assign the initial volume fraction of Eulerian material.

    `filled_region` is the assembly-level Set of cells (or elements) that start
    full. Everything outside it starts empty -- that empty space is what the
    material flows into, so it is not optional padding, it is part of the model.

    `extra` lets you add further ``(region, fraction)`` pairs for layered
    profiles, e.g. a denser lower layer.

    The keyword this emits is `*Initial Conditions, type=VOLUME FRACTION`.
    """
    assignments = [(filled_region, (fraction,))]
    for region, frac in extra:
        assignments.append((region, (frac,)))
    return model.MaterialAssignment(
        name=name or 'Eulerian material assignment',
        instanceList=(instance,),
        useFields=False,
        assignmentList=tuple(assignments),
    )


def set_eulerian_element_type(part, cells=None):
    """Set EC3D8R on the Eulerian part and enforce a structured hex mesh.

    Raises if the cells cannot take a structured hex mesh, rather than letting
    Abaqus fall back to a technique the Eulerian formulation will reject later
    with a much less obvious message.
    """
    import mesh
    from abaqusConstants import EC3D8R, EXPLICIT, HEX, STRUCTURED

    regions = (cells if cells is not None else part.cells,)
    part.setElementType(regions=regions,
                        elemTypes=(mesh.ElemType(elemCode=EC3D8R,
                                                 elemLibrary=EXPLICIT),))
    part.setMeshControls(regions=regions[0], elemShape=HEX,
                         technique=STRUCTURED)
    return part


def check_void_fraction(assembly, instance, filled_set_name, printer=print,
                        min_void=0.15):
    """Warn if too little of the Eulerian domain is empty.

    A CEL model with no room for heave silently under-predicts resistance. This
    is a cheap guard: count elements in the filled set against the total, and
    complain if the void share is below `min_void` (15 % by default, which is a
    rule of thumb, not a law -- deep penetration into a tall domain needs more).
    """
    total = len(instance.elements)
    filled = len(assembly.sets[filled_set_name].elements)
    void = total - filled
    share = void / float(total) if total else 0.0
    printer('  Eulerian domain: %d elements, %d filled, %d void (%.1f %% void)'
            % (total, filled, void, 100.0 * share))
    if share < min_void:
        printer('  *** WARNING: only %.1f %% of the Eulerian domain is empty. '
                'Heave has nowhere to go and penetration resistance will be '
                'over-predicted. Increase the void thickness above the soil '
                'surface. ***' % (100.0 * share))
    return share


def evf_output(step, variables=('EVF',)):
    """Request the Eulerian volume fraction field output.

    Without EVF in the .odb you cannot see where the material actually is, which
    makes a CEL result almost impossible to debug. Always request it.
    """
    return tuple(variables)


# ---------------------------------------------------------------------------
# Post-processing helper
# ---------------------------------------------------------------------------

def surface_from_evf(odb, instance_name, frame, threshold=0.5):
    """Approximate the material surface from the EVF field at one frame.

    Returns a list of ``(x, y, z, evf)`` for elements whose volume fraction
    straddles `threshold` -- i.e. the reconstructed free surface, one element
    thick. Use it to plot heave, or to check that the soil has not quietly
    flowed out of the domain.

    This deliberately returns raw points rather than a fitted surface: the
    diffuseness is real information about your mesh resolution and you should
    see it.
    """
    field = frame.fieldOutputs['EVF']
    inst = odb.rootAssembly.instances[instance_name]
    sub = field.getSubset(region=inst)
    out = []
    for value in sub.values:
        evf = value.data
        if 0.0 < evf < 1.0 or abs(evf - threshold) < 1e-9:
            el = inst.getElementFromLabel(value.elementLabel)
            nodes = [inst.getNodeFromLabel(lab) for lab in el.connectivity]
            n = float(len(nodes))
            cx = sum(nd.coordinates[0] for nd in nodes) / n
            cy = sum(nd.coordinates[1] for nd in nodes) / n
            cz = sum(nd.coordinates[2] for nd in nodes) / n
            out.append((cx, cy, cz, evf))
    return out
