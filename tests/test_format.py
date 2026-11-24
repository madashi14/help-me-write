import json

import docx
import pytest
from docx import Document
from docx.shared import Pt

from conftest import FIX
from fixtures.builders import italian_paragraphs, write_docx
from helpmewrite import cli
from helpmewrite.layout import LayoutError, apply_layout, compute_layout, load_layout
from helpmewrite.rules import load_rules

UNIBO = FIX / "linee-guida-unibo.yaml"


def unibo_layout(font="Times New Roman"):
    return compute_layout(load_rules(UNIBO), font)


def test_apply_layout_sets_margins_fonts_spacing(tmp_path):
    src = write_docx(tmp_path / "in.docx", italian_paragraphs(10))
    lay = unibo_layout()
    changes = apply_layout(src, lay, tmp_path / "out.docx")
    d = Document(tmp_path / "out.docx")
    assert d.sections[0].left_margin.cm == pytest.approx(lay.margins_cm["left"], abs=0.01)
    assert d.styles["Normal"].font.name == "Times New Roman" and d.styles["Normal"].font.size.pt == 12
    assert 'w:lineRule="exact"' in d.styles["Normal"].element.xml
    assert "PAGE" in "".join(s.footer._element.xml for s in d.sections)
    assert changes


def test_apply_layout_refuses_same_path(tmp_path):
    src = write_docx(tmp_path / "in.docx", ["x"])
    with pytest.raises(ValueError):
        apply_layout(src, compute_layout(load_rules(UNIBO), "Courier"), src)


def test_original_untouched_and_paper_set(tmp_path):
    src = write_docx(tmp_path / "in.docx", ["x"])
    before = src.read_bytes()
    apply_layout(src, unibo_layout(), tmp_path / "out.docx")
    assert src.read_bytes() == before
    d = Document(tmp_path / "out.docx")
    assert d.sections[0].page_width.cm == pytest.approx(21.0, abs=0.01)
    assert d.sections[0].page_height.cm == pytest.approx(29.7, abs=0.01)


def test_fonts_all_scripts_and_no_theme_on_headings(tmp_path):
    src = write_docx(tmp_path / "in.docx", [("Heading 1", "Titolo"), "testo"])
    apply_layout(src, unibo_layout(), tmp_path / "out.docx")
    d = Document(tmp_path / "out.docx")
    for name in ("Normal", "Heading 1", "Heading 2", "Heading 3"):
        xml = d.styles[name].element.xml
        for attr in ("ascii", "hAnsi", "cs", "eastAsia"):
            assert f'w:{attr}="Times New Roman"' in xml, (name, attr)
        assert "Theme=" not in xml.split("<w:rFonts")[1].split("/>")[0]


def test_localized_heading_style_matched(tmp_path):
    src = write_docx(tmp_path / "in.docx", ["x"])
    d = Document(src)
    st = d.styles.add_style("Titolo 9", docx.enum.style.WD_STYLE_TYPE.PARAGRAPH)
    st.element.set("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}styleId", "Titolo1")
    st.element.name_val = "heading 1"
    d.save(src)
    apply_layout(src, unibo_layout(), tmp_path / "out.docx")
    d = Document(tmp_path / "out.docx")
    el = [s for s in d.styles if s.style_id == "Titolo1"][0].element
    assert 'w:ascii="Times New Roman"' in el.xml


def test_direct_overrides_removed_but_emphasis_kept(tmp_path):
    src = tmp_path / "in.docx"
    d = Document()
    p = d.add_paragraph()
    r = p.add_run("grassetto")
    r.bold = True
    r.font.name = "Arial"
    r.font.size = Pt(20)
    p.paragraph_format.line_spacing = Pt(30)
    p.paragraph_format.space_after = Pt(7)
    d.save(src)
    apply_layout(src, unibo_layout(), tmp_path / "out.docx")
    out = Document(tmp_path / "out.docx")
    p = out.paragraphs[0]
    assert p.runs[0].bold is True
    assert p.runs[0].font.name is None and p.runs[0].font.size is None
    assert p.paragraph_format.line_spacing is None
    assert p.paragraph_format.space_after == Pt(7)


def test_based_on_normal_styles_get_exact_spacing(tmp_path):
    src = write_docx(tmp_path / "in.docx", [("List Bullet", "voce")])
    apply_layout(src, unibo_layout(), tmp_path / "out.docx")
    out = Document(tmp_path / "out.docx")
    assert out.styles["List Bullet"].base_style.name == "Normal"
    assert 'w:lineRule="exact"' in out.styles["List Bullet"].element.xml


def test_existing_page_field_is_kept(tmp_path):
    src = tmp_path / "in.docx"
    d = Document()
    d.add_paragraph("x")
    fp = d.sections[0].footer.paragraphs[0]
    from docx.oxml import parse_xml
    fp._p.append(parse_xml(
        '<w:fldSimple xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'w:instr=" PAGE "><w:r><w:t>1</w:t></w:r></w:fldSimple>'))
    d.save(src)
    apply_layout(src, unibo_layout(), tmp_path / "out.docx")
    out = Document(tmp_path / "out.docx")
    assert "".join(s.footer._element.xml for s in out.sections).count("PAGE") == 1


def test_footer_page_field_centered(tmp_path):
    src = write_docx(tmp_path / "in.docx", ["x"])
    apply_layout(src, unibo_layout(), tmp_path / "out.docx")
    out = Document(tmp_path / "out.docx")
    xml = out.sections[0].footer._element.xml
    assert "PAGE" in xml and 'w:val="center"' in xml


def test_no_line_pitch_leaves_spacing(tmp_path):
    lay = unibo_layout()
    lay.line_pitch_pt = None
    src = write_docx(tmp_path / "in.docx", ["x"])
    apply_layout(src, lay, tmp_path / "out.docx")
    out = Document(tmp_path / "out.docx")
    assert "exact" not in out.styles["Normal"].element.xml


def test_load_layout_bad_file(tmp_path):
    bad = tmp_path / "l.json"
    bad.write_text("{nope", encoding="utf-8")
    with pytest.raises(LayoutError):
        load_layout(bad)
    bad.write_text('{"family": "times"}', encoding="utf-8")
    with pytest.raises(LayoutError):
        load_layout(bad)
    with pytest.raises(LayoutError):
        load_layout(tmp_path / "missing.json")


def _layout_file(tmp_path):
    from dataclasses import asdict
    p = tmp_path / "layout.json"
    p.write_text(json.dumps(asdict(unibo_layout())), encoding="utf-8")
    return p


def test_format_command(tmp_path, capsys):
    src = write_docx(tmp_path / "in.docx", ["x"])
    out = tmp_path / "out.docx"
    code = cli.main(["format", str(src), "--layout", str(_layout_file(tmp_path)),
                     "-o", str(out), "--json"])
    assert code == 0 and out.exists()
    assert json.loads(capsys.readouterr().out)["changes"]


def test_format_command_refuses_overwrite(tmp_path):
    src = write_docx(tmp_path / "in.docx", ["x"])
    before = src.read_bytes()
    code = cli.main(["format", str(src), "--layout", str(_layout_file(tmp_path)), "-o", str(src)])
    assert code == 2 and src.read_bytes() == before


def test_format_command_bad_inputs(tmp_path):
    src = write_docx(tmp_path / "in.docx", ["x"])
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert cli.main(["format", str(src), "--layout", str(bad), "-o", str(tmp_path / "o.docx")]) == 2
    notdocx = tmp_path / "n.docx"
    notdocx.write_text("hello", encoding="utf-8")
    assert cli.main(["format", str(notdocx), "--layout", str(_layout_file(tmp_path)),
                     "-o", str(tmp_path / "o.docx")]) == 2
    assert cli.main(["format", str(tmp_path / "nope.docx"), "--layout", str(_layout_file(tmp_path)),
                     "-o", str(tmp_path / "o.docx")]) == 2
