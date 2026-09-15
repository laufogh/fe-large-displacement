"""Surgery on the generated `.inp`.

Some Abaqus keywords that matter enormously for large-displacement analysis have
no Abaqus/CAE scripting API at all. `*Section Controls` is the worst offender:
distortion control and enhanced hourglass control are the difference between a
job that finishes and a job that aborts on element distortion, and there is no
`mdb.models[...].SectionControl(...)` in Abaqus 2021. `*Diagnostics` is the
same story.

The honest way to handle that is to let CAE write the deck, then edit the deck,
then verify the edit -- never to pretend the API did something it did not. Every
function here therefore:

* asserts that its anchor exists before editing (so a future Abaqus version that
  changes the preamble fails loudly instead of silently not injecting);
* returns enough information for the caller to log what it did;
* is paired with a check in `report.InpCheck` in the examples.

**Placement is not cosmetic.** Two placements were found empirically to break
things in Abaqus 2021:

* `*Section Controls` placed mid-file (after `*Part`, before `*Material`)
  corrupts the parse of a later `*Amplitude, definition=SMOOTH STEP`. It must go
  at the top of the model data, immediately after `*Preprint`.
* `*Diagnostics` is step-dependent input. Before the first `*Step` it is
  rejected with 'KEYWORD CARDS FOR STEP DEPENDENT INPUT MUST APPEAR AFTER THE
  FIRST *STEP CARD'; immediately after `*Step` it is rejected with 'A PROCEDURE
  OPTION IS MISSING FOR STEP'. It must follow the procedure card.
"""

from __future__ import print_function

import re


_PREPRINT = re.compile(r'^\*Preprint[^\n]*$', re.IGNORECASE | re.MULTILINE)
_PROC_CARD_EXPLICIT = re.compile(r'^\*Dynamic,\s*Explicit', re.IGNORECASE)
_PROC_CARD_STATIC = re.compile(r'^\*Static\b', re.IGNORECASE)


def _read(path):
    fh = open(path)
    try:
        return fh.read()
    finally:
        fh.close()


def _write(path, text):
    fh = open(path, 'w')
    try:
        fh.write(text)
    finally:
        fh.close()


# ---------------------------------------------------------------------------
# *Section Controls
# ---------------------------------------------------------------------------

def section_controls_keyword(name, distortion_control=None, length_ratio=None,
                             hourglass=None):
    """Build the `*Section Controls` keyword line.

    * `distortion_control` -- True/False/None. Adds penalty forces that resist
      element inversion. Inert while the mesh is healthy (0.16 % force
      deviation measured over the first half of a baseline run) and can rescue
      an analysis that would otherwise abort -- 2.5x the penetration depth in
      the calibrated test case.
    * `length_ratio` -- penalty offset as a fraction of the initial
      characteristic length; documented default 0.1. In the verification study
      changing it from 0.05 to 0.20 changed **nothing** measurable, so do not
      spend time tuning it before you have evidence it matters for your model.
    * `hourglass` -- 'ENHANCED' cuts artificial strain energy ALLAE/ALLIE from
      16.5 % to 3.8 % and stiffens the response.

    **Do not combine `hourglass=ENHANCED` with `distortion control=YES`.** The
    combination negated the distortion-control rescue in testing: the combined
    case aborted at 0.069 m where distortion control alone completed to 0.15 m.
    This function raises if you ask for both, because it is a trap rather than a
    trade-off.
    """
    if hourglass and str(hourglass).upper() == 'ENHANCED' and distortion_control:
        raise ValueError(
            'hourglass=ENHANCED combined with distortion control=YES negated '
            'the distortion-control rescue in verification (aborted at 0.069 m '
            'vs 0.15 m for distortion control alone). Pick one. See '
            'docs/04-section-controls.md.')

    parts = ['*Section Controls, name=%s' % name]
    if distortion_control is not None:
        parts.append('distortion control=%s' % ('YES' if distortion_control else 'NO'))
    if length_ratio is not None:
        parts.append('length ratio=%g' % length_ratio)
    if hourglass is not None:
        parts.append('hourglass=%s' % hourglass)
    return ', '.join(parts)


def inject_section_controls(inp_path, keyword_line, section_pattern):
    """Insert `keyword_line` after `*Preprint` and attach it to a solid section.

    `section_pattern` is a regex matching the `*Solid Section` line to modify,
    e.g. ``r'^(\\*Solid Section,[^\\n]*material=SoilMat[^\\n]*)$'``. It must match
    exactly once; matching zero or several times raises, because a section
    control that is defined but referenced by nothing is completely silent.

    Returns the control name that was attached.
    """
    text = _read(inp_path)

    m = _PREPRINT.search(text)
    if not m:
        raise AssertionError('*Preprint line not found in %s -- cannot place '
                             '*Section Controls safely' % inp_path)
    name = re.search(r'name=([^\s,]+)', keyword_line).group(1)

    text = (text[:m.end()] + '\n**\n** SECTION CONTROLS (injected by fldlib)\n'
            + keyword_line + '\n' + text[m.end():])

    pat = re.compile(section_pattern, re.MULTILINE | re.IGNORECASE)
    text, n = pat.subn(lambda mm: mm.group(1) + ', controls=' + name, text)
    if n != 1:
        raise AssertionError(
            'section pattern %r matched %d times in %s (expected exactly 1). '
            'A *Section Controls definition that nothing references has no '
            'effect and produces no warning.' % (section_pattern, n, inp_path))

    _write(inp_path, text)
    return name


# ---------------------------------------------------------------------------
# *Diagnostics
# ---------------------------------------------------------------------------

def inject_diagnostics(inp_path, mode='summary', include_static=False):
    """Insert `*Diagnostics, adaptive mesh=<mode>` after each matching procedure card.

    Without this, the `.msg` carries only an end-of-step summary and an ALE
    domain that never swept looks identical to one that swept perfectly. With
    it, Abaqus/Explicit writes a per-adaptive-increment block reporting mesh
    sweeps and the percentage of nodes moved.

    `include_static=True` also attaches the keyword after `*Static`, which is
    the Abaqus/Standard ALE path. Standard may still omit the Explicit-style
    diagnostic block. The injection is then a no-harm request, not proof.

    Returns the number of insertions.
    """
    lines = open(inp_path).readlines()

    out, inserted, i = [], 0, 0
    while i < len(lines):
        out.append(lines[i])
        strip = lines[i].strip()
        matched = _PROC_CARD_EXPLICIT.match(strip)
        if not matched and include_static:
            matched = _PROC_CARD_STATIC.match(strip)
        if matched:
            i += 1
            # the procedure data line (increment, step period) follows the card
            if i < len(lines) and not lines[i].lstrip().startswith('*'):
                out.append(lines[i])
                i += 1
            out.append('*Diagnostics, adaptive mesh=%s\n' % mode)
            inserted += 1
            continue
        i += 1

    if not inserted:
        raise RuntimeError(
            'no matching procedure card in %s -- nothing to attach '
            '*Diagnostics to. Explicit decks need "*Dynamic, Explicit"; '
            'Standard ALE decks need include_static=True.' % inp_path)

    _write(inp_path, ''.join(out))
    return inserted


# ---------------------------------------------------------------------------
# Extra *Adaptive Mesh domains
# ---------------------------------------------------------------------------

_AM_DOMAIN = re.compile(r'^\*Adaptive Mesh,[^\n]*$', re.IGNORECASE | re.MULTILINE)


def inject_extra_ale_domains(inp_path, elsets, controls='ALE_BC',
                             frequency=None, mesh_sweeps=None,
                             initial_mesh_sweeps=5):
    """Add further `*Adaptive Mesh` domain lines beside the one CAE wrote.

    Abaqus/CAE holds exactly **one** `AdaptiveMeshDomain` per step -- a second
    call silently replaces the first. The solver has no such limit. So the way
    to get several adaptive regions is: define the first through the API (which
    also emits the `*Adaptive Mesh Controls` block and gets the placement right),
    then inject the rest here.

    This is not a workaround for its own sake. Several *well-separated* regions
    are placed in different parallel domains by the packager, whereas one large
    region is consolidated into a single domain and unbalances the whole
    decomposition. See docs/03-ale-multi-region-parallel.md.

    `elsets` are the additional assembly-level element set names. Each must be
    separated from the others by at least one band of non-adaptive elements --
    regions that share a face behave as a single region.

    Returns the number of lines injected.
    """
    text = _read(inp_path)
    anchors = list(_AM_DOMAIN.finditer(text))
    if not anchors:
        raise AssertionError(
            'no *Adaptive Mesh domain line in %s to anchor to. Define the '
            'first domain through the CAE API before calling this.' % inp_path)
    last = anchors[-1]

    extra = []
    for name in elsets:
        parts = ['*Adaptive Mesh, elset=%s, controls=%s' % (name, controls)]
        if frequency is not None:
            parts.append('frequency=%d' % frequency)
        if mesh_sweeps is not None:
            parts.append('mesh sweeps=%d' % mesh_sweeps)
        if initial_mesh_sweeps is not None:
            parts.append('initial mesh sweeps=%d' % initial_mesh_sweeps)
        parts.append('op=NEW')
        extra.append(', '.join(parts))

    block = '\n' + '\n'.join(extra)
    _write(inp_path, text[:last.end()] + block + text[last.end():])
    return len(extra)


# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------

def insert_after(inp_path, anchor_pattern, block, once=True):
    """Insert `block` after the first (or every) line matching `anchor_pattern`.

    The escape hatch for keywords this module does not wrap yet. Raises if the
    anchor is absent.
    """
    text = _read(inp_path)
    pat = re.compile(anchor_pattern, re.MULTILINE | re.IGNORECASE)
    matches = list(pat.finditer(text))
    if not matches:
        raise AssertionError('anchor %r not found in %s'
                             % (anchor_pattern, inp_path))
    if not block.endswith('\n'):
        block += '\n'
    for m in reversed(matches[:1] if once else matches):
        text = text[:m.end()] + '\n' + block + text[m.end():]
    _write(inp_path, text)
    return len(matches[:1] if once else matches)


def insert_before(inp_path, anchor_pattern, block, once=True):
    """Insert `block` immediately before the first (or every) anchor match.

    Model data such as `*Initial Conditions` must appear before the first
    `*Step` card, so this is the counterpart to `insert_after`.
    """
    text = _read(inp_path)
    pat = re.compile(anchor_pattern, re.MULTILINE | re.IGNORECASE)
    matches = list(pat.finditer(text))
    if not matches:
        raise AssertionError('anchor %r not found in %s'
                             % (anchor_pattern, inp_path))
    if not block.endswith('\n'):
        block += '\n'
    for m in reversed(matches[:1] if once else matches):
        text = text[:m.start()] + block + text[m.start():]
    _write(inp_path, text)
    return len(matches[:1] if once else matches)


def keyword_lines(inp_path, keyword):
    """Return every line in the deck starting with `keyword`. For logging."""
    kw = keyword.lower()
    return [ln.rstrip() for ln in open(inp_path)
            if ln.strip().lower().startswith(kw)]
