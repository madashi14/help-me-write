"""Deterministic acceptance of spec §9 cases 1 (report from a work folder, Word and LaTeX)
and 3 (resume after two chapters): the script pipeline end to end, with no LLM."""
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict

import docx
import pytest

from conftest import FIX, ROOT
from fixtures.builders import EXAMPLE_TITLE_VALUES, build_example_work
from helpmewrite.layout import compute_layout
from helpmewrite.rules import load_rules

UNIBO = FIX / "linee-guida-unibo.yaml"
HMW = ROOT / "scripts" / "hmw.py"
needs_soffice = pytest.mark.needs_soffice
needs_xelatex = pytest.mark.needs_xelatex
ALL_CHECKS = ["pages", "font_family", "font_size", "lines_per_page", "chars_per_line",
              "page_numbers", "section:indice:present", "section:introduzione:present",
              "section:introduzione:pages", "section:conclusione:present",
              "section:conclusione:pages"]


def hmw(*args, expect=0):
    """Run the CLI as a subprocess; returns the parsed JSON of stdout when there is any."""
    done = subprocess.run([sys.executable, str(HMW), *map(str, args)], capture_output=True,
                          text=True, encoding="utf-8")
    assert done.returncode == expect, (args, done.returncode, done.stdout, done.stderr)
    try:
        return json.loads(done.stdout)
    except ValueError:
        return done.stdout


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def make_layout(folder):
    path = folder / "layout.json"
    hmw("layout", "--rules", UNIBO, "--font", "Times New Roman", "-o", path)
    return path


def make_chart(work, out_dir):
    """The figure of the example, drawn from the Italian CSV."""
    spec = write_json(out_dir / "metriche.json", {
        "type": "bar", "language": "it", "annotate": True, "xlabel": "Campagna",
        "ylabel": "Accuratezza",
        "csv": {"file": "../../dati/metriche.csv", "x": "campagna", "y": ["accuracy"],
                "labels": {"accuracy": "Accuratezza"}}})
    png = out_dir / "metriche.png"
    hmw("chart", spec, "-o", png)
    return png


def check_lines(m):
    checks = {c["rule"]: c for c in m["checks"]}
    return checks, [f"{r}: {'OK' if checks[r]['ok'] else 'FAIL'} {checks[r]['detail']}"
                    for r in ALL_CHECKS if r in checks]


def assert_all_ok(m):
    checks, lines = check_lines(m)
    print("\n".join(lines))
    for rule in ALL_CHECKS:
        assert rule in checks, (rule, sorted(checks))
    failed = [c for c in m["checks"] if not c["ok"]]
    assert not failed, failed


@needs_soffice
def test_case1_word_pipeline(tmp_path):
    ex = build_example_work(tmp_path / "lavoro")
    work = ex["folder"]
    # 1. no drafts; the state starts
    found = hmw("detect", work, "--json")
    assert found.get("drafts", []) == [], found
    hmw("state", "init", work, "--mode", "da-zero", "--format", "word")
    # 2. material: git history with three commits and reliable dates
    inv = hmw("material", work, "--json")
    assert inv["git"] is None  # the repository is nested in progetto/
    assert inv["git_repos"] == [{"path": "progetto", "commits": 3, "first": "2026-09-15",
                                 "last": "2026-11-05"}]
    assert inv["dates"]["reliable"] is True
    # 3. the figure from the CSV and the title page from the facsimile
    state_dir = work / ".help-me-write"
    chapters = state_dir / "capitoli"
    chapters.mkdir(parents=True, exist_ok=True)
    png = make_chart(work, chapters)
    assert png.is_file() and (chapters / "metriche.png.fonte.json").is_file()
    prov = json.loads((chapters / "metriche.png.fonte.json").read_text(encoding="utf-8"))
    assert "0.808" in json.dumps(prov)  # the decimal comma was read as a number
    values = write_json(state_dir / "frontespizio.json", EXAMPLE_TITLE_VALUES)
    hmw("titlepage", ex["facsimile"], "--values", values, "-o", state_dir / "frontespizio.docx")
    # 4. assemble from the expected chapters
    for src in ex["chapters"]:
        shutil.copy(src, chapters / src.name)
    layout = make_layout(state_dir)
    manifest = state_dir / "manifest.yaml"
    manifest.write_text(
        "layout: layout.json\ntitle_page: frontespizio.docx\nchapters:\n"
        + "".join(f"  - capitoli/{p.name}\n" for p in ex["chapters"]), encoding="utf-8")
    assert layout.is_file()
    out = work / "relazione.docx"
    stats = hmw("assemble", manifest, "-o", out, "--json")
    assert (stats["chapters"], stats["figures"]) == (4, 1)
    # 5. every form check of the Unibo rules
    m = hmw("measure", out, "--rules", UNIBO, "--json")
    assert_all_ok(m)
    # 6. record, then a hand edit is noticed
    hmw("state", "record", work, out)
    assert hmw("state", "modified", work, "--json") == {"relazione.docx": "unchanged"}
    document = docx.Document(str(out))
    document.add_paragraph("Un paragrafo aggiunto a mano.")
    edited = tmp_path / "edit.docx"
    document.save(str(edited))
    shutil.copy(edited, out)
    assert hmw("state", "modified", work, "--json") == {"relazione.docx": "modified"}


def md_to_tex(text):
    """The chapter sources written out by hand in LaTeX (same paragraphs), no heading."""
    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        block = block.strip()
        if block.startswith("# "):
            continue
        if block.startswith("## "):
            out.append(f"\\section{{{block[3:]}}}")
        elif block.startswith("!["):
            caption, label = re.match(r"!\[(.*?)\]\(.*?\)\{#fig:(\w+)", block).groups()
            out.append("\\begin{figure}[htbp]\n\\centering\n"
                       "\\includegraphics[width=0.8\\textwidth]{immagini/metriche.png}\n"
                       f"\\caption{{{caption}}}\\label{{fig:{label}}}\n\\end{{figure}}")
        else:
            out.append(block.replace("@fig:metriche", "Figura~\\ref{fig:metriche}"))
    return "\n\n".join(out) + "\n"


@needs_xelatex
def test_case1_latex_pipeline(tmp_path):
    ex = build_example_work(tmp_path / "lavoro")
    work = ex["folder"]
    hmw("state", "init", work, "--mode", "da-zero", "--format", "latex")
    layout = make_layout(tmp_path)
    ids = [("introduzione", "Introduzione", "introduzione"), ("attivita", "Attività svolte", "corpo"),
           ("risultati", "Risultati", "corpo"), ("conclusioni", "Conclusioni", "conclusione")]
    spec = write_json(tmp_path / "capitoli.json",
                      [{"id": i, "title": t, "kind": k} for i, t, k in ids])
    values = write_json(tmp_path / "v.json", {
        "anno_accademico": "2025/2026", "studente": "Mario Rossi", "matricola": "0000123456",
        "corso": "Ingegneria Informatica", "codice_corso": "8615", "struttura": "Acme S.r.l.",
        "argomento": "Diagnostica FEM con ML", "referente": "Anna Bianchi, responsabile"})
    out = work / "relazione-latex"
    hmw("latex-init", out, "--layout", layout, "--chapters", spec, "--values", values)
    make_chart(work, out / "immagini")
    for (cid, _, _), src in zip(ids, ex["chapters"]):
        path = next((out / "capitoli").glob(f"*-{cid}.tex"))
        text = path.read_text(encoding="utf-8").replace(
            "% help-me-write: testo da scrivere", md_to_tex(src.read_text(encoding="utf-8")))
        path.write_text(text, encoding="utf-8")
    m = hmw("measure", out / "main.tex", "--rules", UNIBO, "--json")
    assert_all_ok(m)


def test_case3_resume_after_two_chapters(tmp_path):
    work = tmp_path
    state_dir = work / ".help-me-write"
    hmw("state", "init", work, "--mode", "da-zero", "--format", "word")
    (state_dir / "materiale.md").write_text("# Materiale\n- progetto/\n", encoding="utf-8")
    (state_dir / "linee-guida.yaml").write_text(UNIBO.read_text(encoding="utf-8"),
                                                encoding="utf-8")
    hmw("state", "set", work, "outline_approved=true", "title_page_approved=true")
    ids = ["introduzione", "contesto", "attivita", "risultati", "conclusioni"]
    kinds = ["introduzione", "corpo", "corpo", "corpo", "conclusione"]
    outline = write_json(tmp_path / "o.json", [
        {"id": i, "title": i.capitalize(), "kind": k} for i, k in zip(ids, kinds)])
    hmw("state", "outline", work, "--from", outline)
    (state_dir / "capitoli").mkdir()
    (state_dir / "note").mkdir()
    for i in ids[1:3]:
        (state_dir / "capitoli" / f"{i}.md").write_text(f"# {i}\n\nTesto.\n", encoding="utf-8")
        hmw("state", "chapter", work, i, "--status", "approvato",
            "--source", f".help-me-write/capitoli/{i}.md")
    (state_dir / "note" / "risultati.md").write_text("Domande: metriche. Risposte: 0,912.\n",
                                                     encoding="utf-8")
    hmw("state", "chapter", work, "risultati", "--status", "intervista-fatta",
        "--notes", ".help-me-write/note/risultati.md")
    shown = hmw("state", "show", work, "--json")
    assert [c["status"] for c in shown["chapters"]] == [
        "da-fare", "approvato", "approvato", "intervista-fatta", "da-fare"]
    assert {k: shown["next"][k] for k in ("phase", "chapter")} == {
        "phase": "scrittura", "chapter": "risultati"}
    # no header field is lost by a set or a chapter update
    before = {k: v for k, v in shown.items() if k != "next"}
    hmw("state", "set", work, "language=it")
    hmw("state", "chapter", work, "risultati", "--status", "intervista-fatta")
    after = {k: v for k, v in hmw("state", "show", work, "--json").items() if k != "next"}
    assert after == before
