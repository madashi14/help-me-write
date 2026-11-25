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


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _footer_xml(section, attr="footer"):
    return getattr(section, attr)._element.xml


def _multi_section_doc(path, titlepg=False, even=False):
    from docx.enum.section import WD_SECTION
    d = Document()
    d.add_paragraph("uno")
    d.sections[0].footer.paragraphs[0].text = "FOOTER TEXT"
    d.add_section(WD_SECTION.NEW_PAGE)
    d.add_paragraph("due")
    d.add_section(WD_SECTION.NEW_PAGE)
    d.add_paragraph("tre")
    if titlepg:
        d.sections[0].different_first_page_header_footer = True
        d.sections[1].different_first_page_header_footer = True
        d.sections[0].first_page_footer.paragraphs[0].text = "COVER"
    if even:
        d.settings.odd_and_even_pages_header_footer = True
    d.save(path)
    return path


def test_multi_section_linked_footers_keep_content(tmp_path):
    src = _multi_section_doc(tmp_path / "in.docx")
    apply_layout(src, unibo_layout(), tmp_path / "out.docx")
    d = Document(tmp_path / "out.docx")
    assert "FOOTER TEXT" in _footer_xml(d.sections[0]) and "PAGE" in _footer_xml(d.sections[0])
    assert d.sections[1].footer.is_linked_to_previous
    assert d.sections[2].footer.is_linked_to_previous


def test_title_page_first_footer_unnumbered_others_numbered(tmp_path):
    src = _multi_section_doc(tmp_path / "in.docx", titlepg=True)
    apply_layout(src, unibo_layout(), tmp_path / "out.docx")
    d = Document(tmp_path / "out.docx")
    assert "PAGE" not in _footer_xml(d.sections[0], "first_page_footer")
    assert "PAGE" in _footer_xml(d.sections[1], "first_page_footer")
    assert "PAGE" in _footer_xml(d.sections[0])


def test_even_odd_footers_numbered(tmp_path):
    src = _multi_section_doc(tmp_path / "in.docx", even=True)
    apply_layout(src, unibo_layout(), tmp_path / "out.docx")
    d = Document(tmp_path / "out.docx")
    assert "PAGE" in _footer_xml(d.sections[0], "even_page_footer")
    assert "PAGE" in _footer_xml(d.sections[0])


def test_section_without_own_page_field_gets_one(tmp_path):
    src = tmp_path / "in.docx"
    from docx.enum.section import WD_SECTION
    from docx.oxml import parse_xml
    d = Document()
    d.add_paragraph("a")
    fp = d.sections[0].footer.paragraphs[0]
    fp._p.append(parse_xml(f'<w:fldSimple xmlns:w="{W}" w:instr=" PAGE "><w:r><w:t>1</w:t></w:r></w:fldSimple>'))
    d.add_section(WD_SECTION.NEW_PAGE)
    d.sections[1].footer.is_linked_to_previous = False
    d.sections[1].footer.paragraphs[0].text = "altro"
    d.save(src)
    apply_layout(src, unibo_layout(), tmp_path / "out.docx")
    out = Document(tmp_path / "out.docx")
    assert "PAGE" in _footer_xml(out.sections[1])


def test_body_text_style_with_own_font_inherits_normal(tmp_path):
    src = write_docx(tmp_path / "in.docx", [("Body Text", "corpo")])
    d = Document(src)
    st = d.styles["Body Text"]
    st.font.name = "Arial"
    st.font.size = Pt(9)
    st.base_style = None
    d.save(src)
    apply_layout(src, unibo_layout(), tmp_path / "out.docx")
    out = Document(tmp_path / "out.docx")
    el = out.styles["Body Text"].element
    assert out.styles["Body Text"].font.name is None and out.styles["Body Text"].font.size is None
    assert 'w:lineRule="exact"' in el.xml
    assert out.styles["Body Text"].base_style.name == "Normal"
    assert out.styles["Normal"].font.size.pt == 12


def test_title_page_keeps_direct_formatting(tmp_path):
    src = tmp_path / "in.docx"
    d = Document()
    p = d.add_paragraph()
    r = p.add_run("FRONTESPIZIO")
    r.font.name = "Arial"
    r.font.size = Pt(30)
    d.add_page_break()
    q = d.add_paragraph()
    r2 = q.add_run("corpo")
    r2.font.name = "Arial"
    r2.font.size = Pt(30)
    d.save(src)
    apply_layout(src, unibo_layout(), tmp_path / "out.docx")
    out = Document(tmp_path / "out.docx")
    assert out.paragraphs[0].runs[0].font.size == Pt(30)
    assert out.paragraphs[-1].runs[0].font.size is None
    assert out.paragraphs[-1].runs[0].font.name is None


def test_textbox_paragraphs_keep_direct_formatting(tmp_path):
    from docx.oxml import parse_xml
    src = tmp_path / "in.docx"
    d = Document()
    for _ in range(3):
        d.add_paragraph("x")
    d.paragraphs[2]._p.append(parse_xml(
        f'<w:r xmlns:w="{W}"><w:pict><w:txbxContent><w:p><w:r><w:rPr><w:sz w:val="60"/></w:rPr>'
        f'<w:t>box</w:t></w:r></w:p></w:txbxContent></w:pict></w:r>'))
    d.save(src)
    apply_layout(src, unibo_layout(), tmp_path / "out.docx")
    out = Document(tmp_path / "out.docx")
    assert 'w:val="60"' in out.element.body.xml


def test_normal_spacing_zero_and_first_line_indent(tmp_path):
    from docx.shared import Twips
    src = write_docx(tmp_path / "in.docx", [("Heading 1", "Titolo"), "testo", ("List", "voce")])
    changes = apply_layout(src, unibo_layout(), tmp_path / "out.docx")
    d = Document(tmp_path / "out.docx")
    normal = d.styles["Normal"].paragraph_format
    assert normal.space_before == 0 and normal.space_after == 0
    assert normal.first_line_indent.cm == pytest.approx(1.0, abs=0.01)  # 567 twips
    defaults = d.styles.element.find(f"{{{W}}}docDefaults/{{{W}}}pPrDefault/{{{W}}}pPr/{{{W}}}spacing")
    assert defaults.get(f"{{{W}}}before") == "0" and defaults.get(f"{{{W}}}after") == "0"
    heading = d.styles["Heading 1"].paragraph_format
    assert heading.space_before == Twips(480) and heading.space_after == 0  # untouched
    for name in ("Heading 1", "Title", "Footer", "Caption"):  # keep their previous indent
        assert d.styles[name].paragraph_format.first_line_indent == 0, name
    assert d.styles["List"].paragraph_format.first_line_indent == -Twips(360)  # hanging kept
    assert any("spacing before/after 0" in c for c in changes)
    assert any("first-line indent 1 cm" in c for c in changes)


def test_first_line_indent_not_on_title_page_tables_centered(tmp_path):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    src = tmp_path / "in.docx"
    d = Document()
    d.add_paragraph("FRONTESPIZIO")
    d.add_page_break()
    d.add_paragraph("figura").alignment = WD_ALIGN_PARAGRAPH.CENTER
    d.add_table(rows=1, cols=1).cell(0, 0).text = "cella"
    d.add_paragraph("corpo")
    d.save(src)
    apply_layout(src, unibo_layout(), tmp_path / "out.docx")
    out = Document(tmp_path / "out.docx")
    first_line = {p.text: p.paragraph_format.first_line_indent for p in out.paragraphs}
    assert first_line["FRONTESPIZIO"] == 0 and first_line["figura"] == 0
    assert out.tables[0].cell(0, 0).paragraphs[0].paragraph_format.first_line_indent == 0
    assert first_line["corpo"] is None  # inherits the indent from Normal



def test_picture_paragraph_gets_auto_line_spacing(tmp_path):
    from docx.shared import Cm
    from fixtures.builders import write_png
    src = write_docx(tmp_path / "in.docx", ["prima"])
    d = Document(src)
    d.add_picture(str(write_png(tmp_path / "fig.png", 50, 50)), width=Cm(8))
    d.add_paragraph("dopo")
    d.save(src)
    apply_layout(src, unibo_layout(), tmp_path / "out.docx")
    out = Document(tmp_path / "out.docx")
    picture = next(p for p in out.paragraphs if p._p.xpath(".//w:drawing"))
    spacing = picture._p.find(f"{{{W}}}pPr/{{{W}}}spacing")
    assert spacing.get(f"{{{W}}}line") == "240" and spacing.get(f"{{{W}}}lineRule") == "auto"
    plain = next(p for p in out.paragraphs if p.text == "dopo")
    assert plain._p.find(f"{{{W}}}pPr/{{{W}}}spacing") is None


def test_format_command_never_overwrites_an_existing_copy(tmp_path, capsys):
    src = write_docx(tmp_path / "bozza-revisionato.docx", ["x"])
    out = tmp_path / "bozza-revisionato-formattato.docx"
    out.write_bytes(b"edited by hand")
    code = cli.main(["format", str(src), "--layout", str(_layout_file(tmp_path)), "-o", str(out)])
    assert code == 2 and out.read_bytes() == b"edited by hand"
    err = capsys.readouterr().err
    assert "already exists" in err and "bozza-revisionato-formattato-2.docx" in err


def test_even_page_footer_text_kept_in_later_sections(tmp_path):
    src = _multi_section_doc(tmp_path / "in.docx", even=True)
    d = Document(src)
    d.sections[0].even_page_footer.is_linked_to_previous = False
    d.sections[0].even_page_footer.paragraphs[0].text = "Mario Rossi - Relazione (pari)"
    d.save(src)
    apply_layout(src, unibo_layout(), tmp_path / "out.docx")
    out = Document(tmp_path / "out.docx")
    even = out.sections[0].even_page_footer
    assert "Mario Rossi - Relazione (pari)" in even._element.xml and "PAGE" in even._element.xml
    for section in out.sections[1:]:  # inherit the first section's even footer, text included
        assert section.even_page_footer.is_linked_to_previous


def _first_page_break_after(path, n):
    """n paragraphs with direct 20 pt Arial runs, a page break, then one more paragraph."""
    d = Document()
    for i in range(n):
        r = d.add_paragraph().add_run(f"Riga {i}")
        r.font.name, r.font.size = "Arial", Pt(20)
    d.add_page_break()
    d.add_paragraph().add_run("corpo").font.size = Pt(20)
    d.save(path)
    return path


@pytest.mark.parametrize("before_break, kept", [(10, True), (20, False)])
def test_title_page_window_is_15_paragraphs(tmp_path, before_break, kept):
    """Direct formatting before the first page break is a title page only within 15
    paragraphs (ruling R3): a first chapter of 20 paragraphs is body text."""
    src = _first_page_break_after(tmp_path / "in.docx", before_break)
    apply_layout(src, unibo_layout(), tmp_path / "out.docx")
    out = Document(tmp_path / "out.docx")
    assert (out.paragraphs[0].runs[0].font.size == Pt(20)) is kept
    assert out.paragraphs[-1].runs[0].font.size is None
