import json

from helpmewrite.cli import main
from helpmewrite.detect import detect


def _w(path, text="", mode="w"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _docx(path, text):
    import docx
    d = docx.Document()
    d.add_paragraph(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    d.save(str(path))


def test_detect_partial_latex_draft(tmp_path):
    body = "Testo di prova abbastanza lungo. " * 12
    inputs = "".join(f"\\input{{capitoli/0{i}}}\n" for i in range(1, 7))
    _w(tmp_path / "Relazione" / "main.tex",
       "\\documentclass{report}\n\\begin{document}\n" + inputs + "\\end{document}\n")
    for i in range(1, 6):
        _w(tmp_path / "Relazione" / "capitoli" / f"0{i}.tex", f"\\chapter{{C{i}}}\n{body}\n")
    _w(tmp_path / "Relazione" / "capitoli" / "06.tex", "\\chapter{Conclusioni}\n% da scrivere\n")
    _docx(tmp_path / "Facsimile.docx", "modello")
    _docx(tmp_path / "bozza-revisionato.docx", "copia")
    (tmp_path / "script.zip").write_bytes(b"PK")
    _w(tmp_path / "Relazione-help-me-write" / "x.tex", "\\documentclass{report}")
    d = detect(tmp_path)
    assert d["drafts"][0]["format"] == "latex"
    assert d["drafts"][0]["path"] == "Relazione/main.tex"
    assert d["drafts"][0]["empty_parts"] == ["Relazione/capitoli/06.tex"]
    assert len(d["drafts"][0]["parts"]) == 6 and d["drafts"][0]["words"] > 50
    assert d["guidelines"] == ["Facsimile.docx"]
    assert all("revisionato" not in x["path"] and "help-me-write" not in x["path"]
               for x in d["drafts"])
    assert len(d["drafts"]) == 1 and d["state"] is None


def test_detect_other_formats_and_state(tmp_path, capsys):
    _docx(tmp_path / "Relazione finale.docx", "uno due tre quattro")
    _docx(tmp_path / "~$Relazione finale.docx", "lock")
    _w(tmp_path / "note.md", "non una bozza")
    _w(tmp_path / "bozza tesi.md", "uno due tre")
    _w(tmp_path / "relazione.txt", "a b")
    (tmp_path / "Relazione finale.pdf").write_bytes(b"%PDF")
    (tmp_path / "altro-report.pdf").write_bytes(b"%PDF")
    _w(tmp_path / "Regolamento.md", "norme")
    _w(tmp_path / ".help-me-write" / "progetto.md", "---\n---\n")
    _w(tmp_path / "node_modules" / "relazione.md", "x")
    d = detect(tmp_path)
    got = {x["path"]: x for x in d["drafts"]}
    assert set(got) == {"Relazione finale.docx", "bozza tesi.md", "relazione.txt",
                        "altro-report.pdf"}
    assert got["Relazione finale.docx"]["words"] == 4 and got["bozza tesi.md"]["words"] == 3
    assert got["bozza tesi.md"]["format"] == "markdown"
    assert got["relazione.txt"]["format"] == "text" and got["altro-report.pdf"]["format"] == "pdf"
    assert d["guidelines"] == ["Regolamento.md"]
    assert d["state"] == ".help-me-write/progetto.md"
    capsys.readouterr()
    assert main(["detect", str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == ".help-me-write/progetto.md"
    assert main(["detect", str(tmp_path / "nope")]) == 2


def test_detect_survives_corrupt_docx(tmp_path):
    _docx(tmp_path / "Relazione buona.docx", "uno due")
    (tmp_path / "Relazione rotta.docx").write_bytes(b"")
    d = {x["path"]: x for x in detect(tmp_path)["drafts"]}
    assert d["Relazione buona.docx"]["words"] == 2
    assert d["Relazione rotta.docx"]["words"] is None
