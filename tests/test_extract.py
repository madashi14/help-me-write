import json

import pytest
from lxml import etree

from conftest import ROOT
from fixtures.builders import italian_paragraphs, write_docx
from helpmewrite import cli, render
from helpmewrite.extract import (
    extract,
    extract_docx,
    extract_pdf,
    extract_tex,
    iter_body_paragraphs,
    visible_text,
)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def test_extract_docx_ids_and_headings(tmp_path):
    p = write_docx(tmp_path / "a.docx", [("Heading 1", "Introduzione"), "Primo.", "Secondo."])
    paras = extract_docx(p)
    assert [x["id"] for x in paras] == [0, 1, 2]
    assert paras[0]["heading_level"] == 1 and paras[2]["text"] == "Secondo."
    assert paras[1]["heading_level"] is None


def test_extract_facsimile_textboxes_once():
    paras = extract_docx(ROOT / "docs/riferimenti/Facsimile_relazione_di_fine_tirocinio.docx")
    texts = [x["text"] for x in paras]
    assert sum("indicare nome e cognome" in t for t in texts) == 1
    assert any("RELAZIONE DI FINE TIROCINIO CURRICULARE" in t for t in texts)


def test_iter_body_paragraphs_matches_extract(tmp_path):
    import docx

    p = write_docx(tmp_path / "a.docx", italian_paragraphs(3))
    assert len(iter_body_paragraphs(docx.Document(str(p)))) == len(extract_docx(p)) == 3


def test_visible_text_skips_deleted_runs():
    p = etree.fromstring(
        f'<w:p xmlns:w="{W}"><w:r><w:t>testo</w:t></w:r>'
        '<w:del><w:r><w:delText>vecchio</w:delText></w:r></w:del>'
        '<w:ins><w:r><w:t xml:space="preserve"> nuovo</w:t></w:r></w:ins></w:p>'
    )
    assert visible_text(p) == "testo nuovo"


def test_visible_text_tab_break_hyperlink():
    p = etree.fromstring(
        f'<w:p xmlns:w="{W}"><w:r><w:t>a</w:t><w:tab/><w:t>b</w:t><w:br/></w:r>'
        '<w:hyperlink><w:r><w:t>c</w:t></w:r></w:hyperlink></w:p>'
    )
    assert visible_text(p) == "a\tb\nc"


def test_extract_tex_follows_input(tmp_path):
    (tmp_path / "main.tex").write_text("\\input{cap1}\n", encoding="utf-8")
    (tmp_path / "cap1.tex").write_text("% c\n\nTesto del capitolo.\n", encoding="utf-8")
    paras = extract_tex(tmp_path / "main.tex")
    assert {"file": "cap1.tex", "line": 3} == {k: paras[-1][k] for k in ("file", "line")}
    assert paras[-1]["text"] == "Testo del capitolo."
    assert [p["id"] for p in paras] == list(range(len(paras)))


def test_extract_tex_include_with_extension_and_subdir(tmp_path):
    (tmp_path / "sec").mkdir()
    (tmp_path / "main.tex").write_text("Inizio.\n\\include{sec/a.tex}\nFine.\n", encoding="utf-8")
    (tmp_path / "sec" / "a.tex").write_text("Dentro.\n", encoding="utf-8")
    paras = extract_tex(tmp_path / "main.tex")
    assert [(p["file"], p["text"]) for p in paras] == [
        ("main.tex", "Inizio."),
        ("sec/a.tex", "Dentro."),
        ("main.tex", "Fine."),
    ]


@pytest.mark.needs_soffice
def test_extract_pdf(tmp_path):
    import subprocess

    d = write_docx(tmp_path / "a.docx", italian_paragraphs(3))
    cmd = [render.find_soffice(), f"-env:UserInstallation={(tmp_path / 'prof').as_uri()}",
           "--headless", "--convert-to", "pdf", "--outdir", str(tmp_path), str(d)]
    subprocess.run(cmd, check=True, capture_output=True, timeout=180)
    paras = extract_pdf(tmp_path / "a.pdf")
    assert [p["page"] for p in paras] == [1, 1, 1]
    assert paras[0]["text"].startswith("Il tirocinio curriculare")
    assert paras[2]["text"].startswith("Dal confronto")


def test_extract_dispatch_and_command(tmp_path, capsys):
    p = write_docx(tmp_path / "a.docx", ["Uno."])
    data = extract(p)
    assert data["format"] == "docx" and data["paragraphs"][0]["text"] == "Uno."
    out = tmp_path / "o.json"
    assert cli.main(["extract", str(p), "-o", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["format"] == "docx"
    assert cli.main(["extract", str(tmp_path / "x.odt")]) == 2


def test_extract_toc_heading_is_level_1(tmp_path):
    import docx
    from docx.enum.style import WD_STYLE_TYPE

    p = write_docx(tmp_path / "a.docx", [("TOC Heading", "Indice"), ("Heading 1", "Introduzione"),
                                          "Testo."])
    document = docx.Document(str(p))
    italian = document.styles.add_style("Titolo sommario", WD_STYLE_TYPE.PARAGRAPH)
    document.add_paragraph("Sommario", style=italian)
    document.save(str(p))
    paras = extract_docx(p)
    assert [(x["text"], x["heading_level"]) for x in paras] == [
        ("Indice", 1), ("Introduzione", 1), ("Testo.", None), ("Sommario", 1)]


def test_italian_paragraphs_cycle():
    base = italian_paragraphs(100)
    assert len(base) == 100 and base[0] == base[len(set(base))]


def test_extract_refuses_output_equal_to_source(tmp_path):
    p = write_docx(tmp_path / "a.docx", ["Uno."])
    before = p.read_bytes()
    assert cli.main(["extract", str(p), "-o", str(p)]) == 2
    assert p.read_bytes() == before


@pytest.mark.parametrize("name", ["bad.docx", "bad.pdf"])
def test_extract_corrupt_file_exits_2(tmp_path, name, capsys):
    p = tmp_path / name
    p.write_text("not a real document", encoding="utf-8")
    assert cli.main(["extract", str(p)]) == 2
    assert "error" in capsys.readouterr().err
