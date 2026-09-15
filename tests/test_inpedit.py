from fldlib import inpedit
from fldlib.report import InpCheck


def test_section_controls_are_inserted_and_attached(tmp_path):
    deck = tmp_path / 'model.inp'
    deck.write_text(
        '*Heading\n'
        '*Preprint, echo=NO\n'
        '*Solid Section, elset=SOIL, material=SoilMat\n'
        '*Step, name=Push\n'
        '*Dynamic, Explicit\n'
        ', 1.0\n'
        '*End Step\n'
    )

    keyword = inpedit.section_controls_keyword(
        'SoilControl', distortion_control=True, length_ratio=0.1)
    inpedit.inject_section_controls(
        str(deck), keyword,
        r'^(\*Solid Section,[^\n]*material=SoilMat[^\n]*)$')

    check = InpCheck(str(deck))
    check.requires(r'^\*Section Controls, name=SoilControl', 'defined')
    check.requires(r'^\*Solid Section,.*controls=SoilControl', 'attached')
    assert check.report(raise_on_fail=False)


def test_diagnostics_follow_explicit_procedure_data(tmp_path):
    deck = tmp_path / 'model.inp'
    deck.write_text(
        '*Step, name=Push\n'
        '*Dynamic, Explicit\n'
        ', 1.0\n'
        '*End Step\n'
    )

    inpedit.inject_diagnostics(str(deck))
    lines = deck.read_text().splitlines()

    assert lines[3] == '*Diagnostics, adaptive mesh=summary'


def test_diagnostics_follow_static_procedure_when_requested(tmp_path):
    deck = tmp_path / 'model.inp'
    deck.write_text(
        '*Step, name=Push, nlgeom=YES\n'
        '*Static\n'
        '0.005, 1.0, 1e-08, 0.05\n'
        '*End Step\n'
    )

    inpedit.inject_diagnostics(str(deck), include_static=True)
    lines = deck.read_text().splitlines()

    assert lines[3] == '*Diagnostics, adaptive mesh=summary'
