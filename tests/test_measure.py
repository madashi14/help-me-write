import json
import statistics

import docx
import pdfplumber
import pytest
from docx.enum.text import WD_BREAK

from conftest import FIX
from fixtures.builders import italian_paragraphs, write_docx, write_png, write_tex_report
from helpmewrite import cli, render
from helpmewrite.layout import apply_layout, compute_layout
from helpmewrite.measure import (
    Check, PageStats, SectionSpan, _chars_per_full_line, _merge_overlapping, check_rules,
    margin_positions, measure, measure_pdf, section_spans, slot_counts,
)
from helpmewrite.render import render_pdf
from helpmewrite.rules import load_rules

UNIBO = FIX / "linee-guida-unibo.yaml"
needs_soffice = pytest.mark.needs_soffice
needs_xelatex = pytest.mark.needs_xelatex


# --- on rendered documents (LibreOffice) -------------------------------------------------

@needs_soffice
@pytest.mark.parametrize("font", ["Times New Roman", "Courier", "Helvetica"])
def test_layout_meets_unibo_rules_after_measure(tmp_path, font):
    rules = load_rules(FIX / "linee-guida-unibo.yaml")
    src = write_docx(tmp_path / "in.docx", [("Heading 1", "Introduzione")] + italian_paragraphs(40))
    apply_layout(src, compute_layout(rules, font), tmp_path / "out.docx")
    m = measure(tmp_path / "out.docx", rules, tmp_path / "w")
    by = {c.rule: c for c in m.checks}
    assert by["chars_per_line"].ok, by["chars_per_line"].detail
    assert by["lines_per_page"].ok, by["lines_per_page"].detail
    assert by["font_family"].ok and by["page_numbers"].ok
    # calibration: near the targets (65 chars, 33 lines), not at the edges of the ranges
    full = [p for p in m.pages if p.number != 1 and p.is_full]
    assert 63 <= statistics.median(p.chars_per_full_line for p in full) <= 67, by["chars_per_line"].detail
    assert all(32 <= p.body_lines <= 34 for p in full), by["lines_per_page"].detail


@needs_soffice
def test_bad_layout_is_flagged(tmp_path):
    src = write_docx(tmp_path / "bad.docx", italian_paragraphs(30), font="Calibri", size_pt=11, margins_cm=1.5)
    m = measure(src, load_rules(FIX / "linee-guida-unibo.yaml"), tmp_path / "w")
    by = {c.rule: c for c in m.checks}
    assert not by["font_family"].ok and not by["font_size"].ok and not by["chars_per_line"].ok
    measured = [p.chars_per_full_line for p in m.pages if p.number != 1 and p.is_full]
    assert measured and statistics.median(measured) > 70   # ~80+ caratteri
    # every page but the title page is evaluated, the last one too
    assert by["chars_per_line"].pages == [p.number for p in m.pages
                                          if p.number != 1 and p.chars_per_full_line is not None]
    assert m.page_count in by["chars_per_line"].pages


def _report_with_sections(path, intro_paragraphs, conclusion_paragraphs):
    """Title page, page break, Introduzione + text, Conclusione + text, Unibo layout (Times)."""
    items = ([("Title", "Relazione di fine tirocinio"), ("Heading 1", "Introduzione")]
             + italian_paragraphs(intro_paragraphs)
             + [("Heading 1", "Conclusione")] + italian_paragraphs(conclusion_paragraphs))
    raw = write_docx(path.with_name("raw.docx"), items)
    d = docx.Document(str(raw))
    d.paragraphs[0].add_run().add_break(WD_BREAK.PAGE)
    d.save(str(raw))
    apply_layout(raw, compute_layout(load_rules(UNIBO), "Times New Roman"), path)
    return path


@needs_soffice
def test_section_pages_for_introduction(tmp_path):
    # Heading "Introduzione" + 4 pagine di testo + Heading "Conclusione" + 1 pagina
    src = _report_with_sections(tmp_path / "relazione.docx", 15, 3)
    m = measure(src, load_rules(UNIBO), tmp_path / "w")
    by = {c.rule: c for c in m.checks}
    assert not by["section:introduzione:pages"].ok and by["section:conclusione:pages"].ok
    spans = {s.title: s for s in m.sections}
    assert spans["Introduzione"].start_page == 2
    assert spans["Introduzione"].end_page - spans["Introduzione"].start_page + 1 >= 4
    assert spans["Conclusione"].end_page == m.page_count
    assert by["section:introduzione:present"].ok and not by["section:indice:present"].ok
    assert "allowed 1–2" in by["section:introduzione:pages"].detail
    assert m.pages[2].is_full and not m.pages[-1].is_full  # the text ends on the last page


@needs_soffice
def test_last_page_is_never_full(tmp_path):
    # 25 one-line paragraphs fit a page: the last page holds 22 (88%), but the text ends there
    lines = [f"Riga numero {i} di un elenco di prova." for i in range(47)]
    src = write_docx(tmp_path / "a.docx", lines, font="Times New Roman", size_pt=12, margins_cm=2.5)
    pages = measure_pdf(render_pdf(src, tmp_path / "w"))
    assert [p.body_lines for p in pages] == [25, 22]
    assert pages[0].is_full and not pages[1].is_full


@needs_soffice
def test_measure_pdf_source_reads_sections_from_bookmarks(tmp_path):
    src = _report_with_sections(tmp_path / "relazione.docx", 4, 2)
    pdf = render_pdf(src, tmp_path / "pdf")  # LibreOffice writes a bookmark per heading
    m = measure(pdf, load_rules(UNIBO), tmp_path / "w")
    by = {c.rule: c for c in m.checks}
    assert m.headings_source == "pdf-bookmarks" and m.pdf == str(pdf)
    assert m.sections and by["section:introduzione:present"].ok
    assert "cannot determine" not in by["section:introduzione:present"].detail
    assert by["font_family"].ok and by["font_size"].ok


@needs_soffice
def test_measure_command_json_and_exit_code(tmp_path, capsys):
    src = write_docx(tmp_path / "Relazione Università.docx", italian_paragraphs(12),
                     font="Calibri", size_pt=11)
    out = tmp_path / "measure.json"
    code = cli.main(["measure", str(src), "--rules", str(UNIBO),
                     "--workdir", str(tmp_path / "w"), "-o", str(out)])
    assert code == 1
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["page_count"] == len(data["pages"]) >= 2
    assert {c["rule"] for c in data["checks"]} >= {"pages", "font_family", "chars_per_line"}
    assert "text" not in data["pages"][0]
    assert cli.main(["measure", str(src), "--rules", str(UNIBO), "--workdir", str(tmp_path / "w")]) == 1
    text = capsys.readouterr().out
    assert "FAIL font_family" in text and "OK" in text


# --- command errors ----------------------------------------------------------------------

def test_measure_command_missing_soffice(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(render, "find_soffice", lambda: None)
    src = write_docx(tmp_path / "a.docx", ["Uno."])
    assert cli.main(["measure", str(src), "--rules", str(UNIBO), "--workdir", str(tmp_path)]) == 3
    err = capsys.readouterr().err
    assert "LibreOffice" in err and "Traceback" not in err


def test_measure_command_bad_input(tmp_path, capsys):
    src = write_docx(tmp_path / "a.docx", ["Uno."])
    assert cli.main(["measure", str(tmp_path / "nope.docx"), "--rules", str(UNIBO)]) == 2
    bad = tmp_path / "bad.yaml"
    bad.write_text("pages: 3\n", encoding="utf-8")
    assert cli.main(["measure", str(src), "--rules", str(bad)]) == 2
    assert cli.main(["measure", str(src), "--rules", str(UNIBO), "-o", str(src)]) == 2
    assert cli.main(["measure", str(tmp_path / "a.odt"), "--rules", str(UNIBO)]) == 2


# --- rules on measured pages (no rendering) ----------------------------------------------

def page(n, lines=33, chars=65.0, fonts=None, size=12.0, number=True, full=True, text=""):
    return PageStats(number=n, body_lines=lines, line_slots=lines if full else None,
                     chars_per_full_line=chars,
                     font_chars=fonts or {"LiberationSerif": 2000}, body_size_pt=size,
                     has_page_number=number, is_full=full, text=text)


def unibo_without_sections():
    rules = load_rules(UNIBO)
    rules.sections = []
    return rules


def good_pages(count=12):
    return [page(1, lines=8, chars=None, number=False, full=False)] + \
        [page(n) for n in range(2, count + 1)]


def test_check_rules_all_ok_and_ids():
    checks = check_rules(good_pages(), [], unibo_without_sections())
    assert all(isinstance(c, Check) for c in checks)
    assert [c.rule for c in checks] == ["pages", "font_family", "font_size", "lines_per_page",
                                        "chars_per_line", "page_numbers"]
    assert all(c.ok for c in checks), [c.detail for c in checks if not c.ok]


def test_check_rules_chars_detail_names_page():
    pages = good_pages()
    pages[3] = page(4, chars=82)
    by = {c.rule: c for c in check_rules(pages, [], unibo_without_sections())}
    assert not by["chars_per_line"].ok and by["chars_per_line"].pages == [4]
    assert "page 4: 82 chars per full line (allowed 60–70)" in by["chars_per_line"].detail


def test_check_rules_skip_title_page_and_partial_pages():
    pages = good_pages()
    pages[0] = page(1, lines=50, chars=90, number=False, full=True)
    pages[-1] = page(12, lines=10, chars=None, full=False)
    by = {c.rule: c for c in check_rules(pages, [], unibo_without_sections())}
    assert by["chars_per_line"].ok and by["lines_per_page"].ok and by["page_numbers"].ok
    # characters per line are measured on the last page too, when it has enough full lines
    pages[-1] = page(12, lines=10, chars=90, full=False)
    by = {c.rule: c for c in check_rules(pages, [], unibo_without_sections())}
    assert by["lines_per_page"].ok
    assert not by["chars_per_line"].ok and by["chars_per_line"].pages == [12]


def test_check_rules_failures():
    calibri = {"Carlito": 1900, "LiberationSerif": 100}
    pages = [page(1, number=False, fonts=calibri, size=11.0),
             page(2, lines=38, number=False, fonts=calibri, size=11.0),
             page(3, lines=29, fonts=calibri, size=11.0)]
    by = {c.rule: c for c in check_rules(pages, [], unibo_without_sections())}
    assert not by["pages"].ok and "3 pages" in by["pages"].detail
    assert not by["font_family"].ok and "Carlito" in by["font_family"].detail
    assert not by["font_size"].ok and "11" in by["font_size"].detail
    assert not by["lines_per_page"].ok and by["lines_per_page"].pages == [2, 3]
    assert "page 2: 38 body lines" in by["lines_per_page"].detail
    assert not by["page_numbers"].ok and by["page_numbers"].pages == [2]
    assert "in the header or footer (the lines above the text or below it)" in by["page_numbers"].detail


def test_check_rules_font_family_tolerates_five_percent():
    pages = good_pages()
    pages[5] = page(6, fonts={"LiberationSerif": 1900, "LiberationSerif-Italic": 50,
                              "Carlito": 50})
    by = {c.rule: c for c in check_rules(pages, [], unibo_without_sections())}
    assert by["font_family"].ok, by["font_family"].detail


def test_check_rules_nothing_to_evaluate_is_not_ok():
    pages = [page(1, full=False), page(2, chars=None, full=False), page(3, chars=None)]
    by = {c.rule: c for c in check_rules(pages, [], unibo_without_sections())}
    assert not by["chars_per_line"].ok and "could not evaluate" in by["chars_per_line"].detail
    assert "1 (title page)" in by["chars_per_line"].detail
    assert ("2–3 (fewer than 5 full-width lines of prose (a table of contents, a table or a "
            "list))") in by["chars_per_line"].detail
    assert by["lines_per_page"].ok  # page 3 is full: its line slots count
    assert "2 (not a full page" in by["lines_per_page"].detail
    assert "a heading or caption counts for the lines it takes" in by["lines_per_page"].detail
    pages = [page(1, full=False), page(2, full=False), page(3, full=False)]
    by = {c.rule: c for c in check_rules(pages, [], unibo_without_sections())}
    assert not by["lines_per_page"].ok and "could not evaluate" in by["lines_per_page"].detail


def test_check_rules_detail_names_skipped_pages():
    pages = good_pages()
    pages[5] = page(6, lines=20, full=False)
    by = {c.rule: c for c in check_rules(pages, [], unibo_without_sections())}
    assert by["lines_per_page"].ok
    assert "not evaluated: 1 (title page); 6 (not a full page" in by["lines_per_page"].detail


def test_check_rules_sections():
    rules = load_rules(UNIBO)
    spans = [SectionSpan("Indice", 1, 2, 2), SectionSpan("1. Introduzione", 1, 3, 5),
             SectionSpan("Conclusioni e sviluppi futuri", 1, 9, 10)]
    by = {c.rule: c for c in check_rules(good_pages(), spans, rules)}
    assert by["section:indice:present"].ok
    assert by["section:introduzione:present"].ok
    assert not by["section:introduzione:pages"].ok and by["section:introduzione:pages"].pages == [3, 4, 5]
    assert "3 pages" in by["section:introduzione:pages"].detail
    assert by["section:conclusione:pages"].ok
    assert by["section:allegati:present"].ok  # optional
    assert "section:frontespizio:present" not in by and "section:corpo:present" not in by


def test_check_rules_sections_unknown_for_pdf_or_tex():
    by = {c.rule: c for c in check_rules(good_pages(), None, load_rules(UNIBO))}
    assert not by["section:indice:present"].ok
    assert "cannot determine sections" in by["section:indice:present"].detail
    assert "section:allegati:present" not in by and "section:introduzione:pages" not in by


# --- section spans -----------------------------------------------------------------------

def test_section_spans_levels_and_ends():
    texts = ["Relazione\nIntroduzione", "Introduzione\nprimo testo", "testo\nAttività   svolte\naltro",
             "DETTAGLI\ntesto", "testo in conclusione del lavoro\nConclusione\ntesto", "testo"]
    pages = [page(i + 1, text=t) for i, t in enumerate(texts)]
    headings = [{"text": "Introduzione", "heading_level": 1},
                {"text": "Attività svolte", "heading_level": 1},
                {"text": "Dettagli", "heading_level": 2},
                {"text": "Conclusione", "heading_level": 1}]
    spans = section_spans(pages, headings)
    assert [(s.title, s.level, s.start_page, s.end_page) for s in spans] == [
        ("Introduzione", 1, 2, 2), ("Attività svolte", 1, 3, 4),
        ("Dettagli", 2, 4, 4), ("Conclusione", 1, 5, 6)]


def test_section_spans_skip_table_of_contents_lines():
    texts = ["Relazione", "Indice\nIntroduzione 3\nConclusione 4", "1 Introduzione\ntesto",
             "Conclusione\ntesto"]
    pages = [page(i + 1, text=t) for i, t in enumerate(texts)]
    headings = [{"text": "Indice", "heading_level": 1},
                {"text": "1 Introduzione", "heading_level": 1},
                {"text": "Conclusione", "heading_level": 1}]
    spans = {s.title: (s.start_page, s.end_page) for s in section_spans(pages, headings)}
    assert spans == {"Indice": (2, 2), "1 Introduzione": (3, 3), "Conclusione": (4, 4)}


def test_section_spans_wrapped_title_and_missing_heading():
    pages = [page(1, text="x"), page(2, text="Analisi dei requisiti\ndel sistema\ntesto"),
             page(3, text="testo")]
    headings = [{"text": "Analisi dei requisiti del sistema", "heading_level": 1},
                {"text": "Titolo che non compare", "heading_level": 1}]
    spans = section_spans(pages, headings)
    assert [(s.title, s.start_page, s.end_page) for s in spans] == [
        ("Analisi dei requisiti del sistema", 2, 3)]


def test_section_spans_heading_on_page_one_without_title_page():
    texts = ["Introduzione\ntesto", "testo dell'introduzione\naltro", "Conclusione\ntesto"]
    pages = [page(i + 1, text=t) for i, t in enumerate(texts)]
    headings = [{"text": "Introduzione", "heading_level": 1},
                {"text": "Conclusione", "heading_level": 1}]
    spans = [(s.title, s.start_page, s.end_page) for s in section_spans(pages, headings)]
    assert spans == [("Introduzione", 1, 2), ("Conclusione", 3, 3)]



def _docx_with(path, before, insert, after, **fmt):
    """A docx with paragraphs `before`, then insert(document), then paragraphs `after`."""
    raw = write_docx(path, before, **fmt)
    d = docx.Document(str(raw))
    insert(d)
    for text in after:
        d.add_paragraph(text)
    d.save(str(raw))
    return raw


@needs_soffice
def test_wide_table_does_not_void_chars_per_line(tmp_path):
    def table(d):
        t = d.add_table(rows=3, cols=3)  # as wide as the 1.5 cm margins: overflows the layout
        for i, row in enumerate(t.rows):
            for j, cell in enumerate(row.cells):
                cell.text = f"cella {i} {j}"

    paras = italian_paragraphs(40)
    raw = _docx_with(tmp_path / "raw.docx", paras[:20], table, paras[20:])
    apply_layout(raw, compute_layout(load_rules(UNIBO), "Times New Roman"), tmp_path / "out.docx")
    m = measure(tmp_path / "out.docx", load_rules(UNIBO), tmp_path / "w")
    by = {c.rule: c for c in m.checks}
    assert by["chars_per_line"].ok, by["chars_per_line"].detail
    full = [p for p in m.pages if p.number != 1 and p.is_full]
    assert len(full) >= m.page_count - 3
    assert all(60 <= p.chars_per_full_line <= 70 for p in full)


@needs_soffice
@pytest.mark.parametrize("before", [5, 8])  # figure inside a page / pushed to the next page
def test_figure_pages_are_not_full(tmp_path, before):
    from docx.shared import Cm

    png = write_png(tmp_path / "fig.png", 200, 200)
    paras = italian_paragraphs(30)
    src = _docx_with(tmp_path / "fig.docx", paras[:before],
                     lambda d: d.add_picture(str(png), width=Cm(10)), paras[before:],
                     font="Times New Roman", size_pt=12, margins_cm=2.5, line_spacing=1.5)
    pdf = render_pdf(src, tmp_path / "pdf")
    with pdfplumber.open(str(pdf)) as doc:
        figure_page = next(i for i, p in enumerate(doc.pages, start=1) if p.images)
    m = measure(pdf, load_rules(UNIBO), tmp_path / "w")
    by = {c.rule: c for c in m.checks}
    lines = {p.number: p.body_lines for p in m.pages}
    if before == 8:  # the figure did not fit: the page before it ends early
        assert lines[figure_page - 1] <= max(lines.values()) - 4
    for n in (figure_page - 1, figure_page):
        if n > 1:
            assert not m.pages[n - 1].is_full, (n, lines)
            assert n not in by["lines_per_page"].pages, by["lines_per_page"].detail


@needs_soffice
def test_measure_leaves_existing_pdf_in_workdir(tmp_path):
    src = write_docx(tmp_path / "Relazione.docx", italian_paragraphs(3))
    own = tmp_path / "Relazione.pdf"
    own.write_bytes(b"%PDF-1.4 the student's own export")
    assert cli.main(["measure", str(src), "--rules", str(UNIBO), "--workdir", str(tmp_path),
                     "-o", str(tmp_path / "m.json")]) == 1
    assert own.read_bytes() == b"%PDF-1.4 the student's own export"
    assert json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))["pdf"] != str(own)


# --- full pages: line slots (final review, finding 8) ------------------------------------

def _line(top, height=12.0, size=12.0, text="testo"):
    from collections import Counter

    from helpmewrite.measure import _Line
    return _Line(text, top, top + height, 70.0, 520.0, Counter({size: 5}), Counter())


def test_overlapping_fragments_are_one_line():  # "−" raised by 2.3 pt + the rest of the formula
    lines = _merge_overlapping([_line(100.0), _line(102.3)])
    assert len(lines) == 1 and len(_merge_overlapping([_line(100.0), _line(119.5)])) == 2
    assert (lines[0].top, lines[0].bottom) == (100.0, 114.3)


def test_slot_counts_heading_inside_is_occupied():
    pitch, top = 19.5, 96.0
    bottom = top + 33 * pitch + 12.0
    body = [_line(top + i * pitch) for i in range(15)] + [_line(top + (i + 18) * pitch) for i in range(16)]
    empty, occupied = slot_counts(body, [_line(top + 16 * pitch, size=14.4)], top, bottom, pitch, pitch)
    assert round(empty) == 0 and round(occupied) == 3     # line_slots = 31 + 3 = 34


def test_slot_counts_figure_and_early_end_are_empty():
    pitch, top = 19.5, 96.0
    bottom = top + 33 * pitch + 12.0
    figure_at_top = [_line(top + (i + 7) * pitch) for i in range(27)]
    early_end = [_line(top + i * pitch) for i in range(28)]
    assert round(slot_counts(figure_at_top, [], top, bottom, pitch, pitch)[0]) == 7
    assert round(slot_counts(early_end, [], top, bottom, pitch, pitch)[0]) == 6
    # with paragraph spacing (pitch 14, 10 pt after each paragraph of 4 lines): none empty
    spaced, y = [], top
    for i in range(40):
        spaced.append(_line(y, 11.0))
        y += 14.0 + (10.0 if i % 4 == 3 else 0.0)
    assert slot_counts(spaced, [], top, spaced[-1].bottom, 14.0, 24.0) == (0.0, 0.0)


def test_slot_counts_sum_fractions_before_rounding():
    # 0.4 above + 0.6 inside + 0.4 below = 1.4 -> 1 (full); 0.6 + 0.6 + 0.6 = 1.8 -> 2
    pitch, top = 19.5, 96.0
    bottom = top + 33.8 * pitch + 12.0

    def at(*offsets):  # body lines at these offsets from the top, in pitches
        return [_line(top + o * pitch) for o in offsets]

    # a step of 1.6 pitches (0.6 inside) and, before the last line, a step of 1.4 pitches:
    # a paragraph break narrower than paragraph step + half a pitch, not counted
    a = at(*[0.4 + i for i in range(15)], *[16.0 + i for i in range(17)], 33.4)
    b = at(*[0.6 + i for i in range(15)], *[16.2 + i for i in range(18)])
    empty_a, occupied_a = slot_counts(a, [], top, bottom, pitch, pitch)
    empty_b, occupied_b = slot_counts(b, [], top, bottom, pitch, pitch)
    assert round(empty_a) == 1 and round(empty_b) == 2 and occupied_a == occupied_b == 0
    assert abs(empty_a - 1.4) < 1e-6 and abs(empty_b - 1.8) < 1e-6


def test_margin_positions_find_footer_not_last_body_line():
    # 10 pages: 30 body lines from 96.0 at pitch 19.5, footer "N" at 771.7;
    # page 11: body lines down to 783.0 and no footer
    pitch = 19.5
    pages = [[_line(96.0 + i * pitch) for i in range(30)] + [_line(771.7, text=str(n))]
             for n in range(1, 11)]
    pages.append([_line(783.0 - i * pitch) for i in reversed(range(35))])
    headers, footers = margin_positions(pages, 19.5)
    assert headers == [] and len(footers) == 1 and abs(footers[0] - 771.7) <= 2.0


def _spread_line(words, last_gap=4.0, top=100.0):
    """A body line of words 5 pt per character wide, 4 pt apart (last_gap before the last)."""
    from helpmewrite.measure import _make_line
    placed, x = [], 70.0
    for i, text in enumerate(words):
        if i:
            x += last_gap if i == len(words) - 1 else 4.0
        placed.append({"text": text, "x0": x, "x1": x + 5.0 * len(text), "top": top,
                       "bottom": top + 12.0, "size": 12.0, "fontname": "TeXGyreTermes"})
        x += 5.0 * len(text)
    return _make_line(placed)


def test_mostly_non_prose_page_has_no_chars_per_line():
    prose = [_spread_line(["parola"] * 11)] * 30                      # 370 pt, 76 characters
    # table-of-contents entries: the page number 16 pt away (under the prose rule's 24 pt),
    # with no leader dots (they look like prose) or with 3 of them
    toc_plain = [_spread_line(["2.3"] + ["sezione"] * 8 + ["7"], last_gap=16.0)] * 6
    toc_leaders = [_spread_line(["2.1"] + ["sezione"] * 8 + [".", ".", "."] + ["4"])] * 8
    reference = prose[0].width
    assert all(0.9 * reference <= line.width <= 1.1 * reference
               for line in (prose[0], toc_plain[0], toc_leaders[0]))
    assert _chars_per_full_line(toc_plain + toc_leaders, reference, 12.0) is None  # 6 vs 8
    assert _chars_per_full_line(prose + toc_leaders[:2], reference, 12.0) == 76.0
    # as many prose lines as other full lines: evaluated
    assert _chars_per_full_line(toc_plain + toc_leaders[:6], reference, 12.0) == \
        float(len(toc_plain[0].text))
    assert _chars_per_full_line(prose[:4], reference, 12.0) is None    # fewer than 5


@needs_xelatex
def test_latex_report_like_real_draft(tmp_path):
    main = write_tex_report(tmp_path / "rel")
    m = measure(main, load_rules(UNIBO), tmp_path / "w")
    checks = {c.rule: c for c in m.checks}
    assert checks["page_numbers"].ok, checks["page_numbers"].detail
    assert checks["lines_per_page"].ok and "could not evaluate" not in checks["lines_per_page"].detail, \
        checks["lines_per_page"].detail
    full = [p for p in m.pages if p.is_full]
    assert len(full) >= 4 and all(33 <= p.line_slots <= 35 for p in full), \
        [(p.number, p.body_lines, p.line_slots) for p in full]
    cpl = checks["chars_per_line"]
    assert not cpl.ok and "could not evaluate" not in cpl.detail, cpl.detail  # 13.2 cm: ~76 characters
    evaluated = [p for p in m.pages if p.number != 1 and p.chars_per_full_line is not None]
    assert 2 not in [p.number for p in evaluated]                       # table of contents
    assert all(72 <= p.chars_per_full_line <= 84 for p in evaluated), cpl.detail


@needs_xelatex
def test_running_header_text_is_margin(tmp_path):
    main = write_tex_report(tmp_path / "rel", running_header=True)
    m = measure(main, load_rules(UNIBO), tmp_path / "w")
    checks = {c.rule: c for c in m.checks}
    assert checks["page_numbers"].ok and checks["lines_per_page"].ok, \
        (checks["page_numbers"].detail, checks["lines_per_page"].detail)
    assert all(p.line_slots <= 35 for p in m.pages if p.is_full)


def _one_liners(n, start=0):
    return [f"Riga di prova numero {i}." for i in range(start, start + n)]


@needs_soffice
def test_figure_at_top_and_heading_with_early_end_are_not_full(tmp_path):
    """The plugin's own formatted copy (finding 8): a page with a heading that ends early
    because the next figure does not fit (28 body lines), then a page that starts with that
    figure (26 body lines). They have fewer lines by design: lines_per_page (30-35) must
    not fail on them."""
    from docx.shared import Cm

    png = write_png(tmp_path / "fig.png", 400, 170)
    d = docx.Document()
    d.add_paragraph("Relazione", style="Title")
    for text in italian_paragraphs(12):
        p = d.add_paragraph(text)
        if len(d.paragraphs) == 2:
            p.paragraph_format.page_break_before = True
    for i, text in enumerate(_one_liners(12)):
        p = d.add_paragraph(text)
        p.paragraph_format.page_break_before = i == 0
    d.add_paragraph("Analisi", style="Heading 1")
    for text in _one_liners(16, 12):
        d.add_paragraph(text)
    d.add_paragraph().add_run().add_picture(str(png), width=Cm(12))  # 3 slots left: too tall
    for text in _one_liners(26, 28) + italian_paragraphs(12):
        d.add_paragraph(text)
    raw = tmp_path / "raw.docx"
    d.save(str(raw))
    rules = load_rules(UNIBO)
    out = tmp_path / "formattato.docx"
    apply_layout(raw, compute_layout(rules, "Times New Roman"), out)
    m = measure(out, rules, tmp_path / "w")
    by = {c.rule: c for c in m.checks}
    lines = {p.number: p.body_lines for p in m.pages}
    heading_page = next(p.number for p in m.pages if "\nAnalisi\n" in p.text)
    figure_page = heading_page + 1
    assert lines[heading_page] == 28 and 24 <= lines[figure_page] <= 28, lines
    assert not m.pages[heading_page - 1].is_full and not m.pages[figure_page - 1].is_full
    assert by["lines_per_page"].ok, by["lines_per_page"].detail
    full = [p for p in m.pages if p.is_full]
    assert full and all(32 <= p.body_lines <= 34 for p in full), lines


# --- headings typed as plain text, roman page numbers ---------------------------------------

def test_unstyled_heading_is_found_but_reported_as_not_styled():
    rules = load_rules(UNIBO)
    pages = good_pages()
    pages[1] = page(2, text="Indice\nIntroduzione 3\nConclusioni 9")  # a typed table of contents
    pages[2] = page(3, text="1. Introduzione\nIl tirocinio si è svolto")
    pages[8] = page(9, text="testo\nConclusioni e sviluppi futuri\naltro testo")
    by = {c.rule: c for c in check_rules(pages, [], rules)}
    intro = by["section:introduzione:present"]
    assert intro.ok and intro.pages == [3]
    assert "'1. Introduzione' found on page 3, but not styled as a heading" in intro.detail
    assert not by["section:introduzione:pages"].ok
    assert "cannot determine the length" in by["section:introduzione:pages"].detail
    assert by["section:conclusione:present"].ok and by["section:conclusione:present"].pages == [9]
    assert by["section:indice:present"].ok  # "Indice" alone on page 2
    assert by["section:allegati:present"].ok and "no heading" in by["section:allegati:present"].detail


def test_unstyled_heading_not_matched_in_prose_or_contents():
    rules = load_rules(UNIBO)
    pages = good_pages()
    pages[1] = page(2, text="Introduzione 3\nIntroduzione del nuovo sistema di build in azienda.\n"
                            "Conclusione, il lavoro è finito")
    by = {c.rule: c for c in check_rules(pages, [], rules)}
    assert not by["section:introduzione:present"].ok
    assert not by["section:conclusione:present"].ok


@needs_soffice
def test_bold_plain_heading_is_present(tmp_path):
    d = docx.Document()
    d.add_paragraph("Relazione")
    d.add_paragraph().add_run("Introduzione").bold = True
    d.paragraphs[-1].paragraph_format.page_break_before = True
    for text in italian_paragraphs(6):
        d.add_paragraph(text)
    src = tmp_path / "bozza.docx"
    d.save(str(src))
    m = measure(src, load_rules(UNIBO), tmp_path / "w")
    by = {c.rule: c for c in m.checks}
    assert by["section:introduzione:present"].ok, by["section:introduzione:present"].detail
    assert "not styled as a heading" in by["section:introduzione:present"].detail


@pytest.mark.parametrize("text, expected", [
    ("12", True), ("- 3 -", True), ("iv", True), ("XXXIX", True), ("ii.", True),
    ("Pag. iv", True), ("pagina 7", True), ("xl", False), ("iiii", False), ("ivx", False),
    ("Introduzione", False), ("pag. ivy", False)])
def test_page_number_pattern_accepts_roman_numerals(text, expected):
    from helpmewrite.measure import _PAGE_NUMBER
    assert bool(_PAGE_NUMBER.match(text)) is expected


@needs_soffice
def test_roman_page_numbers_in_footer_are_found(tmp_path):
    from docx.oxml import parse_xml

    src = write_docx(tmp_path / "a.docx", italian_paragraphs(12), font="Times New Roman",
                     size_pt=12)
    d = docx.Document(str(src))
    d.sections[0].footer.paragraphs[0]._p.append(parse_xml(
        '<w:fldSimple xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'w:instr=" PAGE \\* roman "><w:r><w:t>i</w:t></w:r></w:fldSimple>'))
    d.save(str(src))
    pages = measure_pdf(render_pdf(src, tmp_path / "w"))
    assert len(pages) >= 2 and all(p.has_page_number for p in pages)
    assert "ii" in pages[1].text.splitlines()


# --- headings from LaTeX sources and PDF bookmarks -------------------------------------------

@needs_xelatex
def test_measure_latex_sections(tmp_path):
    m = measure(write_tex_report(tmp_path / "r"), load_rules(UNIBO), tmp_path / "w")
    checks = {c.rule: c for c in m.checks}
    assert m.headings_source == "tex"
    for rid in ("section:indice:present", "section:introduzione:present",
                "section:conclusione:present", "section:introduzione:pages"):
        assert rid in checks and "cannot determine" not in checks[rid].detail
    assert checks["section:indice:present"].ok


@needs_xelatex
def test_measure_pdf_with_bookmarks(tmp_path):
    pdf = render_pdf(write_tex_report(tmp_path / "r"), tmp_path / "w")
    m = measure(pdf, load_rules(UNIBO), tmp_path / "w2")
    assert m.headings_source == "pdf-bookmarks"
    by = {c.rule: c for c in m.checks}
    assert by["section:introduzione:present"].ok and by["section:conclusione:present"].ok


@needs_soffice
def test_measure_pdf_without_bookmarks_message(tmp_path):
    from fixtures.builders import write_pdf_from_paragraphs
    pdf = write_pdf_from_paragraphs(tmp_path / "x.pdf", ["a"])
    m = measure(pdf, load_rules(UNIBO), tmp_path / "w")
    assert m.headings_source == "none"
    detail = {c.rule: c for c in m.checks}["section:indice:present"].detail
    assert ("cannot determine sections: this PDF has no bookmarks (headings are read from .docx, "
            "from .tex sources or from PDF bookmarks); check by hand for a heading") in detail


@pytest.mark.parametrize("source, expected", [
    ("tex", "'1. Introduzione' found on page 3 as plain text, not as \\chapter or \\section"),
    ("pdf-bookmarks", "'1. Introduzione' found on page 3 as plain text, not among the PDF bookmarks"),
    ("docx", "'1. Introduzione' found on page 3, but not styled as a heading")])
def test_unstyled_heading_message_by_source(source, expected):
    pages = good_pages()
    pages[2] = page(3, text="1. Introduzione\nIl tirocinio si è svolto")
    by = {c.rule: c for c in check_rules(pages, [], load_rules(UNIBO), source)}
    assert expected in by["section:introduzione:present"].detail


def test_section_spans_find_heading_wrapped_over_lines():
    pages = [page(1, text="Titolo"),
             page(2, text="Indice\nIntroduzione 3"),
             page(3, text="1. Introduzione\ntesto"),
             page(4, text="2. Familiarizzazione con ANSYS e studio prelimi-\nnare\n2.1 Primo\ntesto"),
             page(5, text="3. Automazione delle simulazioni\nFEM mediante\nPython\ntesto")]
    spans = section_spans(pages, [
        {"text": "Introduzione", "heading_level": 1},
        {"text": "Familiarizzazione con ANSYS e studio preliminare", "heading_level": 1},
        {"text": "Automazione delle simulazioni FEM mediante Python", "heading_level": 1}])
    assert [(s.title[:5], s.start_page, s.end_page) for s in spans] == [
        ("Intro", 3, 3), ("Famil", 4, 4), ("Autom", 5, 5)]
