import json

from helpmewrite import render
from helpmewrite.cli import main
from helpmewrite.doctor import check_environment, summary


def test_doctor_reports_python_and_packages():
    env = check_environment()
    assert env["python_ok"] is True
    assert set(env["packages"]) == {"docx", "lxml", "pdfplumber", "yaml", "bibtexparser", "matplotlib"}


def test_doctor_lists_missing_tool_with_install_hint(monkeypatch):
    monkeypatch.setattr(render, "find_soffice", lambda: None)
    env = check_environment()
    item = next(m for m in env["missing"] if m["what"] == "LibreOffice")
    assert "libreoffice.org" in item["how_to_install"]


def test_cli_doctor_json(capsys):
    assert main(["doctor", "--json"]) == 0
    assert "python_ok" in json.loads(capsys.readouterr().out)


def test_doctor_reports_matplotlib(monkeypatch):
    import importlib

    real = importlib.import_module

    def fake(name, *a, **k):
        if name == "matplotlib":
            raise ImportError("no")
        return real(name, *a, **k)

    monkeypatch.setattr(importlib, "import_module", fake)
    env = check_environment()
    assert env["packages"]["matplotlib"] is None
    # optional: charts and diagrams only, never among the required missing packages
    assert not any("matplotlib" in m["what"] for m in env["missing"])
    item = next(m for m in env["optional_missing"] if "matplotlib" in m["what"])
    assert item["needed_for"] == "charts and diagrams"
    assert "pip install" in item["how_to_install"]
    text = summary(env)
    assert "package matplotlib: MISSING (optional: charts and diagrams)" in text
    assert "Missing:" not in text or "matplotlib" not in text.split("Missing:")[1].split("Optional")[0]


def test_doctor_matplotlib_missing_does_not_block_the_review(monkeypatch, capsys):
    """Part 1 commands never need matplotlib; only chart and diagram exit 3 without it."""
    import importlib

    real = importlib.import_module

    def fake(name, *a, **k):
        if name == "matplotlib" or name.startswith("matplotlib."):
            raise ImportError("no", name="matplotlib")
        return real(name, *a, **k)

    monkeypatch.setattr(importlib, "import_module", fake)
    from helpmewrite import cli

    for command in ("measure", "extract", "track", "bib", "texdiff", "format", "rules"):
        assert "matplotlib" not in cli._COMMANDS[command][4]
    assert main(["chart", "dati.csv", "--x", "a", "--y", "b", "-o", "g.png"]) == 3
    assert "matplotlib" in capsys.readouterr().err
    assert main(["diagram", "s.json", "-o", "s.png"]) == 3
