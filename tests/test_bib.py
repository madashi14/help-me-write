import json
from pathlib import Path

import pytest

from fixtures.builders import write_docx, write_pdf_from_paragraphs
from helpmewrite import cli
from helpmewrite.bib import (
    BibEntry,
    expand_numeric,
    extract_bibliography,
    find_local_sources,
    pdf_pages_text,
    split_sentences,
)

needs_soffice = pytest.mark.needs_soffice

NUMERIC = ["La build dura 12 minuti [1].", "Come mostrato in [2, 4].",
           ("Heading 1", "Bibliografia"),
           "[1] Rossi, M. (2021). Tempi di build. Rivista X.",
           "[2] Bianchi, L. (2019). Pipeline. Conf Y.",
           "[3] Verdi, A. (2020). Test. Z."]


def test_numeric_citations_and_missing(tmp_path):
    doc = write_docx(tmp_path / "d.docx", NUMERIC)
    r = extract_bibliography(doc)
    assert r.style == "numeric" and r.missing_entries == ["[4]"] and r.uncited_entries == ["[3]"]
    assert r.citations[0].sentence == "La build dura 12 minuti [1]."
    assert r.entries[0].year == "2021" and r.entries[0].key == "[1]"
    assert r.entries[0].title == "Tempi di build" and r.entries[0].venue == "Rivista X"
    assert r.citations[0].paragraph == 0 and r.entries[0].paragraph == 3
    assert [c.key for c in r.citations] == ["[1]", "[2]", "[4]"]


def test_numeric_ranges_and_ignored_brackets():
    for dash in "–—-":
        assert expand_numeric(f"2{dash}4, 7") == [2, 3, 4, 7]


def test_numeric_ignores_placeholders_and_years(tmp_path):
    doc = write_docx(tmp_path / "d.docx", [
        "Vedi [2–3] e [DA VERIFICARE: fonte] nel [2021] (Figura [A]).",
        ("Heading 1", "References"), "[1] A. (2020). T. V.", "[2] B. (2019). U. W.",
        "[3] C. (2018). V. X."])
    r = extract_bibliography(doc)
    assert [c.key for c in r.citations] == ["[2]", "[3]"]
    assert r.missing_entries == []


def test_position_keys_without_brackets(tmp_path):
    doc = write_docx(tmp_path / "d.docx", [
        "Testo [1] e [2].", ("Heading 1", "Riferimenti bibliografici"),
        "Rossi, M. (2021). Tempi. Rivista.", "Bianchi, L. (2019). Pipeline. Conf."])
    r = extract_bibliography(doc)
    assert r.style == "numeric"
    assert [e.key for e in r.entries] == ["[1]", "[2]"]
    assert r.missing_entries == [] and r.uncited_entries == []


def test_author_year_keys(tmp_path):
    doc = write_docx(tmp_path / "d.docx", [
        "Lo mostra (Rossi et al., 2021; Bianchi 2019). Inoltre De Luca (2020) e "
        "van der Berg (2018a) concordano.",
        ("Heading 1", "Bibliografia"),
        "Rossi, M., Verdi, A. (2021). Tempi di build. Rivista X. doi:10.1234/abc.5",
        "Bianchi, L. (2019). Pipeline. Conf Y.",
        "Zeta, Q. (2000). Mai citato. Z."])
    r = extract_bibliography(doc)
    assert r.style == "author-year"
    assert [c.key for c in r.citations] == ["rossi2021", "bianchi2019", "deluca2020",
                                            "vanderberg2018a"]
    assert [e.key for e in r.entries] == ["rossi2021", "bianchi2019", "zeta2000"]
    assert r.entries[0].doi == "10.1234/abc.5"
    assert r.uncited_entries == ["zeta2000"]
    assert r.missing_entries == ["deluca2020", "vanderberg2018a"]


def test_latex_cites_with_bibfile(tmp_path):
    (tmp_path / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\nCome mostrato \\parencite{rossi21,bianchi19}.\n"
        "\\bibliography{refs}\n\\end{document}\n", encoding="utf-8")
    (tmp_path / "refs.bib").write_text(
        "@article{rossi21,\n author={Rossi, M. and Verdi, A.},\n title={Tempi di {build}},\n"
        " year={2021},\n journal={Rivista X},\n doi={10.1234/abc}\n}\n", encoding="utf-8")
    r = extract_bibliography(tmp_path / "main.tex")
    assert r.style == "latex"
    assert r.missing_entries == ["bianchi19"] and r.uncited_entries == []
    c = r.citations[0]
    assert c.file == "main.tex" and c.line == 3 and c.key == "rossi21"
    e = r.entries[0]
    assert (e.title, e.year, e.doi, e.venue) == ("Tempi di build", "2021", "10.1234/abc", "Rivista X")
    assert e.authors == ["Rossi, M.", "Verdi, A."]


def test_latex_explicit_bib_and_addbibresource(tmp_path):
    (tmp_path / "main.tex").write_text(
        "\\addbibresource{a.bib}\nTesto \\citet{x1} e \\autocite[p.~3]{x2}.\n", encoding="utf-8")
    (tmp_path / "a.bib").write_text("@book{x1, title={A}, year={2000}}\n", encoding="utf-8")
    (tmp_path / "b.bib").write_text("@misc{x2, title={B}, year={2001}}\n", encoding="utf-8")
    assert extract_bibliography(tmp_path / "main.tex").missing_entries == ["x2"]
    r = extract_bibliography(tmp_path / "main.tex", bib=tmp_path / "b.bib")
    assert r.missing_entries == ["x1"] and r.uncited_entries == []


def test_split_sentences_keeps_abbreviations_and_brackets():
    t = "Come in Rossi et al. (2021) e es. [3] si vede. Poi? Fine [1, p. 4]. Ultima"
    assert split_sentences(t) == ["Come in Rossi et al. (2021) e es. [3] si vede.", "Poi?",
                                  "Fine [1, p. 4].", "Ultima"]


def test_unknown_style(tmp_path):
    doc = write_docx(tmp_path / "d.docx", ["Solo testo."])
    r = extract_bibliography(doc)
    assert r.style == "unknown" and r.entries == [] and r.citations == []


@needs_soffice
def test_find_local_sources_by_title(tmp_path):
    fonti = tmp_path / "fonti" / "sub"
    fonti.mkdir(parents=True)
    write_pdf_from_paragraphs(fonti / "a.pdf", [
        "Tempi di build nelle pipeline di integrazione continua", "Rossi M. Abstract del lavoro."])
    write_pdf_from_paragraphs(fonti / "b.pdf", ["Altro documento", "doi 10.9999/zz.1"])
    (fonti / "rotto.pdf").write_bytes(b"not a pdf")
    entries = [
        BibEntry("[1]", "r", "Tempi di build nelle pipeline", [], "2021", None, None, 3),
        BibEntry("[2]", "r", None, [], None, "10.9999/ZZ.1", None, 4),
        BibEntry("[3]", "r", "Argomento completamente diverso", [], None, None, None, 5),
        BibEntry("[4]", "r", None, [], None, None, None, 6),
    ]
    skipped = []
    found = find_local_sources(tmp_path / "fonti", entries, skipped=skipped)
    assert set(found) == {"[1]", "[2]"}
    assert found["[1]"].endswith("a.pdf") and found["[2]"].endswith("b.pdf")
    assert any(s.endswith("rotto.pdf") for s in skipped)


@needs_soffice
def test_pdftext_and_cli(tmp_path, capsys):
    pdf = write_pdf_from_paragraphs(tmp_path / "p.pdf", ["Contenuto della prima pagina."])
    assert "prima pagina" in pdf_pages_text(pdf)[0]
    assert cli.main(["pdftext", str(pdf), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["pages"][0]["page"] == 1 and "prima pagina" in data["pages"][0]["text"]


def test_bib_cli_and_errors(tmp_path, capsys):
    doc = write_docx(tmp_path / "d.docx", NUMERIC)
    assert cli.main(["bib", str(doc), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["style"] == "numeric" and data["missing_entries"] == ["[4]"]
    assert cli.main(["bib", str(doc)]) == 0
    assert "missing" in capsys.readouterr().out.lower()
    assert cli.main(["bib", str(tmp_path / "nope.docx")]) == 2
    bad = tmp_path / "bad.docx"
    bad.write_bytes(b"x")
    assert cli.main(["bib", str(bad)]) == 2
    assert cli.main(["bib", str(doc), "-o", str(doc)]) == 2
    assert cli.main(["bib", str(doc), "--sources", str(tmp_path / "no")]) == 2
    assert cli.main(["pdftext", str(bad)]) == 2
    err = capsys.readouterr().err
    assert "Traceback" not in err


def test_sitografia_entries_and_stop_heading(tmp_path):
    doc = write_docx(tmp_path / "d.docx", [
        "Testo [1] e [4].", ("Heading 1", "Bibliografia"),
        "Rossi, M. (2021). Tempi. Rivista.", "Bianchi, L. (2019). Pipeline. Conf.",
        ("Heading 1", "Sitografia"), "https://a.example/x", "https://b.example/y",
        ("Heading 1", "Allegati"), "Tabella A"])
    r = extract_bibliography(doc)
    assert [e.key for e in r.entries] == ["[1]", "[2]", "[3]", "[4]"]
    assert all("Sitografia" not in e.raw and "Allegati" not in e.raw for e in r.entries)
    assert r.uncited_entries == ["[2]", "[3]"]


def test_split_sentences_italian_abbreviations():
    t = "Poi l'Ing. Rossi disse [1]. Dott. Bianchi della Acme S.p.A. confermò. Vale 3.5 punti."
    assert split_sentences(t) == ["Poi l'Ing. Rossi disse [1].",
                                  "Dott. Bianchi della Acme S.p.A. confermò.", "Vale 3.5 punti."]


def test_code_and_url_brackets_are_not_citations(tmp_path):
    doc = write_docx(tmp_path / "d.docx", [
        "Codice: a[1] = x; url http://x.it/a[2]. Testo vero [3].",
        ("Heading 1", "Bibliografia"), "[3] Rossi, M. (2021). T. V."])
    r = extract_bibliography(doc)
    assert [c.key for c in r.citations] == ["[3]"] and r.missing_entries == []


# --- final review: pdftext pages, the document's own PDFs, headings and LaTeX commands -----

def test_page_range():
    from helpmewrite.bib import page_range

    assert page_range("3") == (3, 3) and page_range("2-5") == (2, 5)
    assert page_range("2–5") == (2, 5) and page_range(" 4- ") == (4, None)
    for bad in ["0", "5-3", "x", "1,2", "", "-3"]:
        with pytest.raises(ValueError):
            page_range(bad)


@needs_soffice
def test_pdftext_pages_option(tmp_path, capsys):
    from fixtures.builders import write_pdf_pages

    pdf = write_pdf_pages(tmp_path / "fonte.pdf", [["Pagina uno."], ["Pagina due."],
                                                   ["Pagina tre."]])
    assert cli.main(["pdftext", str(pdf), "--pages", "2-3", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["page_count"] == 3 and [p["page"] for p in data["pages"]] == [2, 3]
    assert "due" in data["pages"][0]["text"] and "tre" in data["pages"][1]["text"]
    out = tmp_path / "rev" / "fonti" / "fonte.json"  # the folder does not exist yet
    assert cli.main(["pdftext", str(pdf), "--pages", "2-9", "-o", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [p["page"] for p in data["pages"]] == [2, 3]
    assert cli.main(["pdftext", str(pdf), "--pages", "3"]) == 0
    text = capsys.readouterr().out
    assert "--- page 3 of 3 ---" in text and "uno" not in text
    assert cli.main(["pdftext", str(pdf), "--pages", "4"]) == 2
    assert cli.main(["pdftext", str(pdf), "--pages", "3-2"]) == 2
    err = capsys.readouterr().err
    assert "has 3 page(s)" in err and "invalid --pages" in err and "Traceback" not in err


def _sources_folder(tmp_path, monkeypatch):
    """A work folder whose every PDF has the entry's title on its first page."""
    from helpmewrite import bib

    work = tmp_path / "Relazione"
    for name in ["bozza.pdf", "Bozza-revisionato.pdf", "bozza-revisionato-formattato.pdf",
                 "bozza-differenze.pdf", "bozza-differenze-2.pdf",
                 "bozza-revisionato/main.pdf", "Relazione-revisionato-2/x.pdf",
                 ".help-me-write/revisioni/r/pdf-1/bozza.pdf", "fonti/rossi2021.pdf",
                 "fonti/bozza di rossi.pdf"]:
        (work / name).parent.mkdir(parents=True, exist_ok=True)
        (work / name).write_bytes(b"%PDF-1.4 stub")
    monkeypatch.setattr(bib, "pdf_pages_text",
                        lambda pdf, max_pages=None: ["Tempi di build nelle pipeline"])
    return work


def test_the_documents_own_pdfs_are_never_sources(tmp_path, monkeypatch):
    work = _sources_folder(tmp_path, monkeypatch)
    entries = [BibEntry("[1]", "r", "Tempi di build nelle pipeline", [], "2021", None, None, 3)]
    excluded = []
    found = find_local_sources(work, entries, document=work / "bozza.docx", excluded=excluded)
    # a source whose name merely starts with the document's name is still a source
    assert found == {"[1]": str(work / "fonti" / "bozza di rossi.pdf")}
    names = sorted(Path(p).relative_to(work).as_posix() for p in excluded)
    assert names == ["Bozza-revisionato.pdf", "Relazione-revisionato-2/x.pdf",
                     "bozza-differenze-2.pdf", "bozza-differenze.pdf",
                     "bozza-revisionato-formattato.pdf", "bozza-revisionato/main.pdf",
                     "bozza.pdf"]


def test_unrelated_differenze_pdf_is_a_source(tmp_path, monkeypatch):
    work = _sources_folder(tmp_path, monkeypatch)
    (work / "Confronto-differenze.pdf").write_bytes(b"%PDF-1.4 stub")
    (work / "fonti" / "rossi2021.pdf").unlink()
    (work / "fonti" / "bozza di rossi.pdf").unlink()
    entries = [BibEntry("[1]", "r", "Tempi di build nelle pipeline", [], "2021", None, None, 3)]
    excluded = []
    found = find_local_sources(work, entries, document=work / "bozza.docx", excluded=excluded)
    assert found == {"[1]": str(work / "Confronto-differenze.pdf")}
    assert str(work / "bozza-differenze.pdf") in excluded


def test_find_local_sources_uppercase_suffix(tmp_path, monkeypatch):
    from helpmewrite import bib

    work = tmp_path / "w"
    (work / "fonti").mkdir(parents=True)
    (work / "fonti" / "Articolo.PDF").write_bytes(b"%PDF-1.4 stub")
    (work / "fonti" / "Altro.Pdf").write_bytes(b"%PDF-1.4 stub")
    monkeypatch.setattr(bib, "pdf_pages_text",
                        lambda pdf, max_pages=None: ["Tempi di build nelle pipeline"])
    entries = [BibEntry("[1]", "r", "Tempi di build nelle pipeline", [], "2021", None, None, 3)]
    found = find_local_sources(work, entries)
    assert found == {"[1]": str(work / "fonti" / "Altro.Pdf")}
    entries = [BibEntry("[2]", "r", "Tempi di build nelle pipeline", [], "2021", None, None, 3)]
    (work / "fonti" / "Altro.Pdf").unlink()
    assert find_local_sources(work, entries) == {"[2]": str(work / "fonti" / "Articolo.PDF")}


def test_bib_command_lists_excluded_pdfs(tmp_path, monkeypatch, capsys):
    work = _sources_folder(tmp_path, monkeypatch)
    doc = write_docx(work / "bozza.docx", NUMERIC)
    assert cli.main(["bib", str(doc), "--sources", str(work), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert not data["local_sources"]["[1]"].endswith(("bozza.pdf", "main.pdf"))
    assert "fonti" in data["local_sources"]["[1]"]
    assert any(p.endswith("bozza.pdf") and ".help-me-write" not in p
               for p in data["excluded_sources"])
    assert not any(".help-me-write" in p for p in data["excluded_sources"])


@pytest.mark.parametrize("heading", ["Bibliografia e sitografia", "Fonti", "Riferimenti",
                                     "Bibliografia e riferimenti", "5. Fonti bibliografiche"])
def test_more_bibliography_headings(tmp_path, heading):
    doc = write_docx(tmp_path / "d.docx", [NUMERIC[0], NUMERIC[1], ("Heading 1", heading)]
                     + NUMERIC[3:])
    r = extract_bibliography(doc)
    assert [e.key for e in r.entries] == ["[1]", "[2]", "[3]"], heading


def test_more_latex_citation_commands(tmp_path):
    (tmp_path / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\n"
        "Come in \\footcite{a1} e \\citeauthor{a2} (\\citeyear{a3}).\n"
        "Vedi \\cites[p.~3]{a4}[][5]{a5,a6} e \\citealp{a7} \\citealt[cfr.][]{a8}.\n"
        "Anche \\citeauthor*{a9}, \\textcites(x)(y){b1}{b2}, \\Textcite{b3}. % \\cite{zz}\n"
        "\\end{document}\n", encoding="utf-8")
    r = extract_bibliography(tmp_path / "main.tex")
    assert [c.key for c in r.citations] == ["a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8",
                                             "a9", "b1", "b2", "b3"]
    assert [c.line for c in r.citations if c.key in ("a4", "b3")] == [4, 5]
