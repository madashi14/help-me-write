import json
import statistics

import docx
import pytest
from docx.enum.text import WD_BREAK

from conftest import FIX
from fixtures.builders import italian_paragraphs, write_docx
from helpmewrite import cli, render
from helpmewrite.layout import apply_layout, compute_layout
from helpmewrite.measure import (
    Check, PageStats, SectionSpan, check_rules, measure, measure_pdf, section_spans,
)
from helpmewrite.render import render_pdf
from helpmewrite.rules import load_rules

UNIBO = FIX / "linee-guida-unibo.yaml"
needs_soffice = pytest.mark.needs_soffice


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
    by = {c.rule: c for c in measure(src, load_rules(FIX / "linee-guida-unibo.yaml"), tmp_path / "w").checks}
    assert not by["font_family"].ok and not by["font_size"].ok and not by["chars_per_line"].ok
    assert "7" in by["chars_per_line"].detail or "8" in by["chars_per_line"].detail   # ~80+ caratteri


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
def test_measure_pdf_source_cannot_determine_sections(tmp_path):
    src = _report_with_sections(tmp_path / "relazione.docx", 4, 2)
    pdf = render_pdf(src, tmp_path / "pdf")
    m = measure(pdf, load_rules(UNIBO), tmp_path / "w")
    by = {c.rule: c for c in m.checks}
    assert m.sections == [] and m.pdf == str(pdf)
    assert not by["section:introduzione:present"].ok
    assert "cannot determine sections" in by["section:introduzione:present"].detail
    assert "section:introduzione:pages" not in by and "section:allegati:present" not in by
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
    return PageStats(number=n, body_lines=lines, chars_per_full_line=chars,
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
    pages[-1] = page(12, lines=10, chars=90, full=False)
    by = {c.rule: c for c in check_rules(pages, [], unibo_without_sections())}
    assert by["chars_per_line"].ok and by["lines_per_page"].ok and by["page_numbers"].ok


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


def test_check_rules_font_family_tolerates_five_percent():
    pages = good_pages()
    pages[5] = page(6, fonts={"LiberationSerif": 1900, "LiberationSerif-Italic": 50,
                              "Carlito": 50})
    by = {c.rule: c for c in check_rules(pages, [], unibo_without_sections())}
    assert by["font_family"].ok, by["font_family"].detail


def test_check_rules_no_full_pages_is_not_evaluated():
    by = {c.rule: c for c in check_rules([page(1, full=False)], [], unibo_without_sections())}
    assert by["chars_per_line"].ok and "not evaluated" in by["chars_per_line"].detail


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
