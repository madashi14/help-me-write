"""hmw titlepage: fill the title-page model of the guidelines (text boxes included)."""
import json
import zipfile

import pytest

from conftest import ROOT
from helpmewrite.cli import main
from helpmewrite.extract import extract

FACSIMILE = ROOT / "docs/riferimenti/Facsimile_relazione_di_fine_tirocinio.docx"
ORIGINAL = zipfile.ZipFile(FACSIMILE).read("word/document.xml").decode()
needs_soffice = pytest.mark.needs_soffice

VALUES = {"start_at": "ALMA MATER STUDIORUM", "replace": [
    {"find": "Anno Accademico 20…./20….", "with": "Anno Accademico 2025/2026"},
    {"find": "indicare nome e cognome  (matricola nr.              )",
     "with": "Mario Rossi (matricola nr. 0000123456)"},
    {"find": "indicare la denominazione della Struttura Ospitante", "with": "Acme S.r.l."},
    {"find": "inserire titolo o argomento delle attività di tirocinio",
     "with": "Diagnostica FEM con ML"}]}


def write_json(tmp_path, data, name="valori.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_titlepage_fills_facsimile(tmp_path):
    out = tmp_path / "f.docx"
    assert main(["titlepage", str(FACSIMILE), "--values", str(write_json(tmp_path, VALUES)),
                 "-o", str(out)]) == 0
    texts = [p["text"] for p in extract(out)["paragraphs"] if p["text"].strip()]
    assert texts[0].startswith("ALMA MATER") and not any(t.startswith("Finalità") for t in texts)
    for v in ("Anno Accademico 2025/2026", "Mario Rossi", "Acme S.r.l.", "Diagnostica FEM con ML"):
        assert sum(v in t for t in texts) == 1
    xml = zipfile.ZipFile(out).read("word/document.xml").decode()
    assert "indicare nome e cognome" not in xml
    assert xml.count("Mario Rossi") == ORIGINAL.count("indicare nome e") == 2


def test_titlepage_reports_not_found(tmp_path, capsys):
    values = {"replace": VALUES["replace"] + [{"find": "testo inesistente", "with": "x"}]}
    out = tmp_path / "f.docx"
    assert main(["titlepage", str(FACSIMILE), "--values", str(write_json(tmp_path, values)),
                 "-o", str(out), "--json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["not_found"] == ["testo inesistente"] and out.exists()
    assert data["replaced"]["Anno Accademico 20…./20…."] == 1


def test_titlepage_never_overwrites(tmp_path):
    out = tmp_path / "f.docx"
    out.write_bytes(b"x")
    assert main(["titlepage", str(FACSIMILE), "--values",
                 str(write_json(tmp_path, VALUES)), "-o", str(out)]) == 2
    assert out.read_bytes() == b"x"


def test_titlepage_bad_values(tmp_path):
    bad = write_json(tmp_path, {"replace": [{"find": "a"}]})
    assert main(["titlepage", str(FACSIMILE), "--values", str(bad),
                 "-o", str(tmp_path / "o.docx")]) == 2


@needs_soffice
def test_titlepage_renders_one_page(tmp_path):
    import pdfplumber

    from helpmewrite.render import render_pdf
    out = tmp_path / "f.docx"
    assert main(["titlepage", str(FACSIMILE), "--values", str(write_json(tmp_path, VALUES)),
                 "-o", str(out)]) == 0
    pdf = render_pdf(out, tmp_path / "work")
    with pdfplumber.open(pdf) as doc:
        assert len(doc.pages) == 1
        text = doc.pages[0].extract_text()
    assert "ALMA MATER" in text and "Mario Rossi" in text
