"""hmw assemble: a .docx from Markdown chapter sources, with TOC, captions and bibliography."""
import json
import re
import zipfile
from dataclasses import asdict

import pytest
import yaml

from conftest import FIX, ROOT
from fixtures.builders import italian_paragraphs, write_png
from helpmewrite import assemble as assemble_module
from helpmewrite.assemble import (
    Figure,
    ListBlock,
    Paragraph,
    Table,
    assemble,
    parse_chapter,
    validate_manifest,
)
from helpmewrite.cli import main
from helpmewrite.extract import extract
from helpmewrite.layout import compute_layout
from helpmewrite.render import RenderError
from helpmewrite.rules import load_rules

UNIBO = FIX / "linee-guida-unibo.yaml"
FACSIMILE = ROOT / "docs/riferimenti/Facsimile_relazione_di_fine_tirocinio.docx"
needs_soffice = pytest.mark.needs_soffice

BIB = """@article{k1,
  author = {Rossi, Mario and Bianchi, Luca},
  title = {Pipeline di integrazione continua},
  journal = {Rivista di Ingegneria del Software},
  year = {2021},
  doi = {10.1000/xyz123}
}
@book{k2,
  author = {Verdi, Anna},
  title = {Contenitori in produzione},
  publisher = {Editore Tecnico},
  year = {2019}
}
@misc{k3,
  title = {Documentazione interna},
  year = {2024}
}
"""

CHAPTER_1 = """# Introduzione

Il tirocinio è descritto in questa relazione [@k1]. Il flusso è riassunto nello schema,
come mostra la @fig:schema, e i tempi sono nella @tab:tempi.

## Contesto

L'azienda usa **strumenti** *interni* e il comando `make` [@k2; @k1].

![Schema del flusso](schema.png){#fig:schema width=8cm}

- uno
- due
"""

CHAPTER_2 = """# Risultati

Tabella: Risultati {#tab:tempi}

| Fase | Minuti |
|------|-------:|
| Compilazione | 4 |
| Test | 12 |

1. primo passo
2. secondo passo

Il valore finale è [DA VERIFICARE: tempo medio dopo l'ottimizzazione].
"""


def write_layout(folder):
    layout = compute_layout(load_rules(UNIBO), "Times New Roman")
    path = folder / "layout.json"
    path.write_text(json.dumps(asdict(layout)), encoding="utf-8")
    return path


def write_project(tmp_path, chapters, manifest_extra=None, bib=BIB, images=("schema.png",)):
    """A manifest in tmp_path/.help-me-write with chapters in capitoli/; returns its path."""
    state = tmp_path / ".help-me-write"
    folder = state / "capitoli"
    folder.mkdir(parents=True)
    names = []
    for i, text in enumerate(chapters, start=1):
        name = f"{i:02d}.md"
        (folder / name).write_text(text, encoding="utf-8")
        names.append(f"capitoli/{name}")
    for image in images:
        write_png(folder / image, 400, 200)
    manifest = {"layout": write_layout(state).name, "chapters": names}
    if bib is not None:
        (state / "fonti.bib").write_text(bib, encoding="utf-8")
        manifest["bibliography"] = "fonti.bib"
    manifest.update(manifest_extra or {})
    path = state / "manifest.yaml"
    path.write_text(yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")
    return path


def no_soffice(monkeypatch):
    def fail(src, workdir, engine=None):
        raise RenderError("LibreOffice is needed", missing_tool="soffice")
    monkeypatch.setattr(assemble_module, "render_pdf", fail)


# --- chapter sources ----------------------------------------------------------------------

def test_parse_chapter_blocks():
    blocks = parse_chapter("# Attività\n\nTesto *a* [@k1].\n\n![Schema](s.png){#fig:s width=10cm}\n\n- uno\n- due\n")
    assert [type(b).__name__ for b in blocks] == ["Heading", "Paragraph", "Figure", "ListBlock"]
    assert blocks[2].label == "fig:s" and blocks[2].width_cm == 10.0


def test_parse_chapter_table_lists_and_wrapped_paragraph():
    text = ("Prima riga\nseconda riga.\n\nTable: Tempi {#tab:t}\n\n| A | B |\n|:--|:-:|\n"
            "| 1 | 2 |\n\n1. uno\n2. due\n   continua\n\n![Senza etichetta](x.png)\n")
    blocks = parse_chapter(text)
    assert [type(b) for b in blocks] == [Paragraph, Table, ListBlock, Figure]
    assert blocks[0].text == "Prima riga seconda riga."
    table = blocks[1]
    assert (table.caption, table.label, table.header, table.rows) == ("Tempi", "tab:t", ["A", "B"],
                                                                      [["1", "2"]])
    assert table.align == ["left", "center"]
    assert blocks[2].ordered and blocks[2].items == ["uno", "due continua"]
    assert blocks[3].label is None and blocks[3].width_cm is None
    assert parse_chapter("  - a\n  - b\n\n  - c\n")[0].items == ["a", "b", "c"]
    problems = []
    parse_chapter("- a\n    - b\n", problems)
    assert problems == [(2, "nested lists are not supported: use a single level")]


# --- assembling ---------------------------------------------------------------------------

def test_assemble_minimal_document(tmp_path):
    manifest = write_project(tmp_path, [CHAPTER_1, CHAPTER_2])
    out = tmp_path / "relazione.docx"
    stats = assemble(manifest, out)
    assert (stats["chapters"], stats["figures"], stats["tables"], stats["citations"]) == (2, 1, 1, 2)
    paras = extract(out)["paragraphs"]
    assert [(p["text"], p["heading_level"]) for p in paras if p["heading_level"]][:3] == [
        ("Indice", 1), ("Introduzione", 1), ("Contesto", 2)]
    texts = [p["text"] for p in paras]
    assert "Figura 1: Schema del flusso" in texts and "Tabella 1: Risultati" in texts
    assert any("come mostra la Figura 1, e i tempi sono nella Tabella 1" in t for t in texts)
    assert any("Il tirocinio è descritto in questa relazione [1]." in t for t in texts)
    assert any("il comando make [1, 2]." in t for t in texts)  # numbers in order of first citation
    assert any(t.startswith("[1] Rossi") for t in texts)
    assert "[1] Rossi, Mario; Bianchi, Luca. Pipeline di integrazione continua. Rivista di " \
           "Ingegneria del Software, 2021. DOI: 10.1000/xyz123." in texts
    assert "[2] Verdi, Anna. Contenitori in produzione. Editore Tecnico, 2019." in texts
    assert not any("Documentazione interna" in t for t in texts)  # k3 is never cited
    assert ("Bibliografia", 1) in [(p["text"], p["heading_level"]) for p in paras]
    xml = zipfile.ZipFile(out).read("word/document.xml").decode()
    assert 'w:val="yellow"' in xml
    assert 'TOC \\o "1-3" \\h \\z \\u' in xml and "SEQ Figura" in xml and "SEQ Tabella" in xml
    settings = zipfile.ZipFile(out).read("word/settings.xml").decode()
    assert re.search(r'<w:updateFields w:val="(true|1)"/>', settings)
    assert any("[DA VERIFICARE" in w for w in stats["warnings"])


def test_assemble_without_soffice_keeps_00_and_warns(tmp_path, monkeypatch, capsys):
    no_soffice(monkeypatch)
    manifest = write_project(tmp_path, [CHAPTER_1, CHAPTER_2])
    out = tmp_path / "relazione.docx"
    assert main(["assemble", str(manifest), "-o", str(out), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert "table of contents without page numbers: update it in Word (F9)" in data["warnings"]
    toc = [p["text"] for p in extract(out)["paragraphs"]
           if re.fullmatch(r"toc [1-3]", p["style"].lower())]
    assert toc[:3] == ["Introduzione\t00", "Contesto\t00", "Risultati\t00"]
    assert toc[-1] == "Bibliografia\t00"


def test_assemble_english_labels(tmp_path, monkeypatch):
    no_soffice(monkeypatch)
    chapter = CHAPTER_1.replace("Introduzione", "Introduction") + CHAPTER_2.replace(
        "Tabella:", "Table:")
    manifest = write_project(tmp_path, [chapter], {"language": "en"})
    out = tmp_path / "report.docx"
    assemble(manifest, out)
    texts = [p["text"] for p in extract(out)["paragraphs"]]
    assert "Contents" in texts and "References" in texts
    assert "Figure 1: Schema del flusso" in texts and "Table 1: Risultati" in texts
    assert any("come mostra la Figure 1" in t for t in texts)


def test_assemble_without_toc_and_bibliography(tmp_path):
    manifest = write_project(tmp_path, ["# Uno\n\nTesto.\n"], {"toc": False}, bib=None,
                             images=())
    out = tmp_path / "a.docx"
    stats = assemble(manifest, out)
    texts = [p["text"] for p in extract(out)["paragraphs"]]
    assert texts == ["Uno", "Testo."] and stats["citations"] == 0


def test_assemble_reports_missing_figure_and_label(tmp_path, capsys):
    chapter = "# Uno\n\n![x](manca.png){#fig:x}\n\nVedi @fig:assente e [@nessuna].\n"
    manifest = write_project(tmp_path, [chapter])
    out = tmp_path / "a.docx"
    assert main(["assemble", str(manifest), "-o", str(out)]) == 2 and not out.exists()
    err = capsys.readouterr().err
    assert "manca.png" in err and "fig:assente" in err and "nessuna" in err
    assert "Traceback" not in err


def test_validate_manifest_problems(tmp_path):
    chapter = ("# Uno\n\n![a](schema.png){#fig:a}\n\n![b](schema.png){#fig:a}\n\n"
               "#### Troppo profondo\n\nCita [@k1, p. 3].\n\n| a | b |\n|---|---|\n| 1 |\n")
    manifest = write_project(tmp_path, [chapter], {"colore": "blu", "language": "fr"})
    problems = "\n".join(validate_manifest(manifest))
    for expected in ("unknown key 'colore'", "language", "fig:a", "####", "[@k1, p. 3]",
                     "1 cell"):
        assert expected in problems, problems
    assert validate_manifest(tmp_path / "manca.yaml") == [f"manifest not found: {tmp_path / 'manca.yaml'}"]


def test_validate_manifest_requires_layout_and_chapters(tmp_path):
    path = tmp_path / "manifest.yaml"
    path.write_text("language: it\n", encoding="utf-8")
    problems = validate_manifest(path)
    assert any("layout" in p for p in problems) and any("chapters" in p for p in problems)
    path.write_text("chapters: [a.md\n", encoding="utf-8")
    assert validate_manifest(path)[0].startswith(f"cannot read {path}")


def test_assemble_never_overwrites(tmp_path, capsys):
    manifest = write_project(tmp_path, ["# Uno\n\nTesto.\n"], {"toc": False}, bib=None, images=())
    out = tmp_path / "a.docx"
    out.write_bytes(b"x")
    assert main(["assemble", str(manifest), "-o", str(out)]) == 2
    assert out.read_bytes() == b"x" and "a-2.docx" in capsys.readouterr().err


# --- with the guidelines' title page -------------------------------------------------------

TITLE_VALUES = {"start_at": "ALMA MATER STUDIORUM", "replace": [
    {"find": "Anno Accademico 20…./20….", "with": "Anno Accademico 2025/2026"},
    {"find": "indicare nome e cognome  (matricola nr.              )",
     "with": "Mario Rossi (matricola nr. 0000123456)"},
    {"find": "indicare la denominazione della Struttura Ospitante", "with": "Acme S.r.l."},
    {"find": "inserire titolo o argomento delle attività di tirocinio",
     "with": "Diagnostica FEM con ML"}]}


def _prose(start, n):
    return "\n\n".join(italian_paragraphs(start + n)[start:])


def report_chapters():
    """Four chapters of about twelve pages in all, with a figure, a table and citations."""
    intro = (f"# Introduzione\n\n{_prose(0, 4)} Le fonti principali sono citate [@k1].\n")
    activities = (f"# Attività svolte\n\n{_prose(1, 4)}\n\n## Analisi del processo\n\n"
                  f"{_prose(3, 4)} Il flusso è nella @fig:schema.\n\n"
                  "![Schema del flusso di rilascio](schema.png){#fig:schema}\n\n"
                  f"{_prose(5, 3)} Per i contenitori si veda [@k2].\n")
    results = (f"# Risultati\n\n{_prose(2, 3)} I tempi sono nella @tab:tempi.\n\n"
               "Tabella: Tempi della pipeline {#tab:tempi}\n\n| Fase | Minuti |\n|---|---:|\n"
               "| Compilazione | 4 |\n| Test | 12 |\n| Pubblicazione | 2 |\n\n"
               f"## Confronto\n\n{_prose(4, 5)}\n")
    conclusions = f"# Conclusioni\n\n{_prose(6, 4)}\n"
    return [intro, activities, results, conclusions]


def test_inline_emphasis_code_escapes_and_placeholders():
    from helpmewrite.assemble import _tokens

    def view(text):
        return [(t.kind, t.value, t.bold, t.italic) for t in _tokens(text)]

    assert view("a **b *c* d** e") == [("text", "a ", False, False), ("text", "b ", True, False),
                                       ("text", "c", True, True), ("text", " d", True, False),
                                       ("text", " e", False, False)]
    assert view("2 * 3 * 4 e \\*x\\*") == [("text", "2 * 3 * 4 e *x*", False, False)]
    assert view("`a*b*` [DA VERIFICARE: [x] y] @tab:t-1.") == [
        ("code", "a*b*", False, False), ("text", " ", False, False),
        ("todo", "[DA VERIFICARE: [x] y]", False, False), ("text", " ", False, False),
        ("ref", "tab:t-1", False, False), ("text", ".", False, False)]
    problems = []
    assert view("[@a; @b] e mario@fig:x") == [("cite", ["a", "b"], False, False),
                                             ("text", " e mario@fig:x", False, False)]
    _tokens("[@a, p. 3]", problems)
    assert problems and "[@a, p. 3]" in problems[0]


def test_assemble_title_page_without_soffice(tmp_path, monkeypatch):
    import docx
    from docx.oxml.ns import qn

    from helpmewrite.titlepage import fill_title_page

    no_soffice(monkeypatch)
    manifest = write_project(tmp_path, [CHAPTER_1, CHAPTER_2], {"title_page": "frontespizio.docx"})
    model = manifest.parent / "frontespizio.docx"
    fill_title_page(FACSIMILE, [(r["find"], r["with"]) for r in TITLE_VALUES["replace"]], model,
                    TITLE_VALUES["start_at"])
    original = model.read_bytes()
    out = tmp_path / "relazione.docx"
    stats = assemble(manifest, out)
    assert "table of contents without page numbers: update it in Word (F9)" in stats["warnings"]
    assert model.read_bytes() == original  # the model is never modified
    before = [p["text"] for p in extract(model)["paragraphs"]]
    after = [p["text"] for p in extract(out)["paragraphs"]]
    assert after[:len(before)] == before and after[len(before)] == "Indice"
    document = docx.Document(str(out))
    first, text = document.sections
    assert first.different_first_page_header_footer and not text.different_first_page_header_footer
    assert not text.header.is_linked_to_previous and not text.header.paragraphs[0].text
    assert text.footer.is_linked_to_previous and "PAGE" in first.footer._element.xml
    # the title page keeps the model's margins and direct formatting; the text gets the layout
    assert round(first.left_margin.cm, 2) == 2.0 and round(text.left_margin.cm, 2) == 4.83
    body = zipfile.ZipFile(out).read("word/document.xml").decode()
    assert body.count('w:ascii="Helvetica"') >= zipfile.ZipFile(model).read(
        "word/document.xml").decode().count('w:ascii="Helvetica"')
    names = zipfile.ZipFile(out).namelist()
    assert any(n.startswith("word/numbering") for n in names)  # lists in a model without one
    types = zipfile.ZipFile(out).read("[Content_Types].xml").decode()
    assert "numbering+xml" in types
    paras = docx.Document(str(out)).paragraphs
    assert any(p._p.find(f"{qn('w:pPr')}/{qn('w:numPr')}") is not None for p in paras)


@needs_soffice
def test_assemble_with_facsimile_title_page(tmp_path):
    from helpmewrite.measure import measure
    from helpmewrite.titlepage import fill_title_page

    manifest = write_project(tmp_path, report_chapters(), {"title_page": "frontespizio.docx"})
    fill_title_page(FACSIMILE, [(r["find"], r["with"]) for r in TITLE_VALUES["replace"]],
                    manifest.parent / "frontespizio.docx", TITLE_VALUES["start_at"])
    out = tmp_path / "relazione.docx"
    stats = assemble(manifest, out)
    assert not any("without page numbers" in w for w in stats["warnings"]), stats["warnings"]

    m = measure(out, load_rules(UNIBO), tmp_path / "w")
    checks = {c.rule: c for c in m.checks}
    for rule in ("pages", "font_family", "font_size", "lines_per_page", "chars_per_line",
                 "page_numbers", "section:indice:present", "section:introduzione:present",
                 "section:conclusione:present"):
        assert checks[rule].ok, checks[rule].detail
    assert "ALMA MATER" in m.pages[0].text and not m.pages[0].has_page_number
    assert "Mario Rossi" in m.pages[0].text and "Indice" not in m.pages[0].text
    toc = m.pages[1].text            # the TOC entry of Introduzione carries its printed page number
    assert toc.splitlines()[0] == "Indice"
    spans = {s.title: s for s in m.sections}
    for title in ("Introduzione", "Attività svolte", "Analisi del processo", "Conclusioni",
                  "Bibliografia"):
        page = m.pages[spans[title].start_page - 1]
        printed = page.text.splitlines()[-1].strip()    # the footer: the page number
        assert printed.isdigit(), page.text
        entry = next(line for line in toc.splitlines() if line.startswith(title))
        assert re.sub(r"[.\s]+", " ", entry).strip() == f"{title} {printed}", toc
    assert "00" not in toc
    # a page opening with a chapter title is a full page (the title is not a running header)
    assert m.pages[spans["Introduzione"].start_page - 1].is_full
    assert sum(p.is_full for p in m.pages) >= 4
