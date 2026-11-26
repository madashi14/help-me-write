import pytest

from conftest import FIX
from fixtures.builders import write_pdf_from_paragraphs, write_tex_report
from helpmewrite.headings import document_headings, pdf_headings, tex_headings, tex_parts
from helpmewrite.render import render_pdf

needs_xelatex = pytest.mark.needs_xelatex
needs_soffice = pytest.mark.needs_soffice


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _titles(headings):
    return [(h["text"], h["heading_level"]) for h in headings]


def test_tex_headings_follow_include_and_input(tmp_path):
    main = _write(tmp_path / "main.tex", "\\documentclass{report}\n\\usepackage[italian]{babel}\n"
                  "\\begin{document}\n\\tableofcontents\n\\include{capitoli/01_intro}\n"
                  "%\\include{capitoli/03}\n\\input{capitoli/02.tex}\n\\bibliography{bib}\n"
                  "\\end{document}\n\\chapter{Dopo la fine}\n")
    _write(tmp_path / "capitoli" / "01_intro.tex",
           "\\chapter{Introduzione}\n\\section{Obiettivi \\emph{del} tirocinio\\label{s:o}}\n")
    _write(tmp_path / "capitoli" / "03.tex", "\\chapter{Non incluso}\n")
    _write(tmp_path / "capitoli" / "02.tex", "\\chapter*{Conclusioni}\n")
    found = tex_headings(main)
    assert _titles(found) == [
        ("Indice", 1), ("Introduzione", 1), ("Obiettivi del tirocinio", 2),
        ("Conclusioni", 1), ("Bibliografia", 1)]
    by_text = {h["text"]: h for h in found}
    assert by_text["Introduzione"]["file"] == "capitoli/01_intro.tex"
    assert by_text["Introduzione"]["line"] == 1
    assert by_text["Obiettivi del tirocinio"]["line"] == 2
    assert by_text["Conclusioni"]["file"] == "capitoli/02.tex"


def test_tex_headings_input_variants(tmp_path):
    main = _write(tmp_path / "main.tex",
                  "\\documentclass{report}\n\\begin{document}\n"
                  "\\input{sotto cartella/parte}\n\\input{./parte2.tex}\n\\include{manca}\n"
                  "% \\input{commentato}\n\\input{parte2}\n\\input{sotto cartella/parte}\n"
                  "\\end{document}\n")
    _write(tmp_path / "sotto cartella" / "parte.tex", "\\chapter{Prima parte}\n\\input{../main}\n")
    _write(tmp_path / "parte2.tex", "\\chapter{Seconda parte}\n")
    _write(tmp_path / "commentato.tex", "\\chapter{Commentato}\n")
    assert _titles(tex_headings(main)) == [("Prima parte", 1), ("Seconda parte", 1)]
    assert tex_parts(main) == [tmp_path / "sotto cartella" / "parte.tex", tmp_path / "parte2.tex"]


def test_tex_headings_article_english(tmp_path):
    main = _write(tmp_path / "main.tex",
                  "\\documentclass{article}\n\\begin{document}\n\\tableofcontents\n"
                  "\\section{Intro \\& aims}\n\\subsection*{Caf\\'e -- a \\textbf{bold} start"
                  "\\footnote{note}}\n\\listoffigures\n\\bibliography{b}\n\\end{document}\n")
    assert _titles(tex_headings(main)) == [
        ("Contents", 1), ("Intro & aims", 1), ("Café – a bold start", 2),
        ("List of Figures", 1), ("References", 1)]


def test_tex_headings_short_title_and_nested_braces(tmp_path):
    main = _write(tmp_path / "main.tex",
                  "\\documentclass{report}\n\\usepackage{polyglossia}\n\\setmainlanguage{italian}\n"
                  "\\begin{document}\n\\chapter[Breve]{Titolo {lungo} di~prova\\label{x}}\n"
                  "\\printbibliography\n\\end{document}\n")
    assert _titles(tex_headings(main)) == [("Titolo lungo di prova", 1), ("Bibliografia", 1)]


@pytest.mark.parametrize("cls, babel, expected", [
    ("report", "[main=italian,english]", ["Indice", "Elenco delle tabelle", "Conclusioni",
                                          "Bibliografia"]),
    ("report", "[italian,english]", ["Contents", "List of Tables", "Conclusioni",
                                     "Bibliography"]),
    ("article", "[english, main = italian]", ["Indice", "Elenco delle tabelle", "Conclusioni",
                                              "Riferimenti bibliografici"]),
    ("article", "[italian]", ["Indice", "Elenco delle tabelle", "Conclusioni",
                              "Riferimenti bibliografici"]),
])
def test_tex_headings_thebibliography_listoftables_and_babel_main(tmp_path, cls, babel, expected):
    """I8: \\begin{thebibliography} and \\listoftables yield headings; babel's main= wins."""
    main = _write(tmp_path / "main.tex",
                  f"\\documentclass{{{cls}}}\n\\usepackage{babel}{{babel}}\n\\begin{{document}}\n"
                  "\\tableofcontents\n\\listoftables\n\\section{Conclusioni}\nTesto.\n"
                  "\\begin{thebibliography}{9}\n\\bibitem{a} A. Autore, Titolo.\n"
                  "\\end{thebibliography}\n\\begin{figure}x\\end{figure}\n\\end{document}\n")
    found = tex_headings(main)
    assert [h["text"] for h in found] == expected
    assert found[-1]["line"] == 8 and found[-1]["heading_level"] == 1


def test_document_headings_none_for_unknown_source(tmp_path):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    assert document_headings(pdf, pdf) == (None, "none")


@needs_soffice
def test_pdf_without_bookmarks_is_none(tmp_path):
    assert pdf_headings(write_pdf_from_paragraphs(tmp_path / "x.pdf", ["a"])) is None


@needs_xelatex
def test_pdf_headings_from_bookmarks(tmp_path):
    pdf = render_pdf(write_tex_report(tmp_path / "r"), tmp_path / "w")
    titles = _titles(pdf_headings(pdf))
    assert ("Introduzione", 1) in titles and ("Conclusioni", 1) in titles
    assert document_headings(pdf, pdf)[1] == "pdf-bookmarks"
