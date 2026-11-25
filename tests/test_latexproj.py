import json
from dataclasses import asdict

import pdfplumber
import pytest

from conftest import FIX
from fixtures.builders import italian_paragraphs
from helpmewrite import cli
from helpmewrite.latexproj import new_latex_project, tex_escape
from helpmewrite.layout import compute_layout, setstretch_factor
from helpmewrite.measure import measure
from helpmewrite.rules import load_rules

UNIBO = FIX / "linee-guida-unibo.yaml"
needs_xelatex = pytest.mark.needs_xelatex

VALUES = {"anno_accademico": "2025/2026", "studente": "Mario Rossi", "matricola": "123456",
          "corso": "Ingegneria Informatica", "codice_corso": "8615",
          "struttura": "Acme S.r.l.", "argomento": "Pipeline di dati",
          "referente": "Anna Bianchi, responsabile"}
CHAPTERS = [{"id": "introduzione", "title": "Introduzione", "kind": "introduzione"},
            {"id": "attivita", "title": "R&D al 100%", "kind": "corpo"},
            {"id": "conclusioni", "title": "Conclusioni", "kind": "conclusione"}]


def _layout(tmp_path, font="Times"):
    layout = compute_layout(load_rules(UNIBO), font)
    path = tmp_path / "layout.json"
    path.write_text(json.dumps(asdict(layout)), encoding="utf-8")
    return layout, path


def test_tex_escape():
    assert tex_escape("R&D al 100% $5 #1 a_b {x} ~ ^") == \
        r"R\&D al 100\% \$5 \#1 a\_b \{x\} \textasciitilde{} \textasciicircum{}"
    assert tex_escape("a\\b") == r"a\textbackslash{}b"


def test_latex_init_files_and_escaping(tmp_path, capsys):
    layout, lpath = _layout(tmp_path)
    (tmp_path / "capitoli.json").write_text(json.dumps(CHAPTERS), encoding="utf-8")
    (tmp_path / "v.json").write_text(json.dumps(VALUES), encoding="utf-8")
    out = tmp_path / "proj"
    args = ["latex-init", str(out), "--layout", str(lpath),
            "--chapters", str(tmp_path / "capitoli.json"),
            "--values", str(tmp_path / "v.json"), "--bibliography"]
    assert cli.main(args) == 0
    for name in ["main.tex", "frontespizio.tex", ".latexmkrc", "bibliografia.bib",
                 "capitoli/01-introduzione.tex", "capitoli/02-attivita.tex",
                 "capitoli/03-conclusioni.tex"]:
        assert (out / name).is_file(), name
    assert (out / "immagini").is_dir()
    assert (out / ".latexmkrc").read_text(encoding="utf-8").strip() == "$pdf_mode = 5;"
    chapter = (out / "capitoli" / "02-attivita.tex").read_text(encoding="utf-8")
    assert r"\chapter{R\&D al 100\%}\label{cap:attivita}" in chapter
    assert "% help-me-write: testo da scrivere" in chapter
    main = (out / "main.tex").read_text(encoding="utf-8")
    assert main.splitlines()[0] == "% !TeX program = xelatex"
    assert r"\documentclass[12pt,a4paper,oneside]{report}" in main
    assert r"\IfFontExistsTF{Times New Roman}{\setmainfont{Times New Roman}}" \
           r"{\setmainfont{TeX Gyre Termes}}" in main
    assert rf"\setstretch{{{setstretch_factor(layout.line_pitch_pt, 12)}}}" in main
    assert r"\input{frontespizio}" in main and r"\include{capitoli/03-conclusioni}" in main
    assert r"\bibliographystyle{unsrt}" in main
    assert r"\newcommand{\studente}{Mario Rossi}" in main
    front = (out / "frontespizio.tex").read_text(encoding="utf-8")
    assert "ALMA MATER STUDIORUM - UNIVERSITÀ DI BOLOGNA" in front
    assert "(firma per approvazione della relazione finale)" in front
    # a non-empty folder is refused, nothing is touched
    assert cli.main(args) == 2
    assert "already exists" in capsys.readouterr().err
    # unknown keys and an unsupported size are usage errors
    (tmp_path / "bad.json").write_text(json.dumps({"colore": "blu"}), encoding="utf-8")
    assert cli.main(["latex-init", str(tmp_path / "p2"), "--layout", str(lpath),
                     "--chapters", str(tmp_path / "capitoli.json"),
                     "--values", str(tmp_path / "bad.json")]) == 2
    assert not (tmp_path / "p2").exists()
    odd = asdict(layout)
    odd["font_size_pt"] = 13
    (tmp_path / "odd.json").write_text(json.dumps(odd), encoding="utf-8")
    assert cli.main(["latex-init", str(tmp_path / "p3"), "--layout", str(tmp_path / "odd.json"),
                     "--chapters", str(tmp_path / "capitoli.json")]) == 2


def test_latex_init_missing_value_is_placeholder(tmp_path):
    layout, _ = _layout(tmp_path)
    out = tmp_path / "proj"
    new_latex_project(out, layout, CHAPTERS, values={"studente": "Mario Rossi"})
    main = (out / "main.tex").read_text(encoding="utf-8")
    assert r"\newcommand{\matricola}{[DA VERIFICARE: matricola]}" in main
    assert r"\newcommand{\studente}{Mario Rossi}" in main
    generic = tmp_path / "gen"
    new_latex_project(generic, layout, CHAPTERS, title_page="generico", language="en")
    text = (generic / "main.tex").read_text(encoding="utf-8")
    assert r"\newcommand{\titolo}{[DA VERIFICARE: titolo]}" in text
    assert r"\detokenize{[DA VERIFICARE: anno_accademico]}" in main
    assert r"\usepackage[english]{babel}" in text


@needs_xelatex
def test_latex_project_compiles_and_measures(tmp_path):
    layout, _ = _layout(tmp_path)
    out = tmp_path / "proj"
    new_latex_project(out, layout, CHAPTERS, values=VALUES)
    prose = italian_paragraphs(40)
    split = {"01-introduzione": prose[:2], "02-attivita": prose[2:36],
             "03-conclusioni": prose[36:38]}
    for name, paragraphs in split.items():
        path = out / "capitoli" / f"{name}.tex"
        text = path.read_text(encoding="utf-8").replace(
            "% help-me-write: testo da scrivere", "\n\n".join(paragraphs))
        path.write_text(text, encoding="utf-8")
    m = measure(out / "main.tex", load_rules(UNIBO), tmp_path / "w")
    checks = {c.rule: c for c in m.checks}
    for rule in ["pages", "font_family", "font_size", "lines_per_page", "chars_per_line",
                 "page_numbers", "section:indice:present"]:
        assert checks[rule].ok, (rule, checks[rule].detail)
    print({r: c.detail for r, c in checks.items()})
    with pdfplumber.open(m.pdf) as pdf:
        first = pdf.pages[0].extract_text(x_tolerance=1)
    assert "ALMA MATER" in first
    assert not any(line.strip().isdigit() for line in first.splitlines())
