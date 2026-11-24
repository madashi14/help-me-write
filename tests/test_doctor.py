import json

from helpmewrite import render
from helpmewrite.cli import main
from helpmewrite.doctor import check_environment


def test_doctor_reports_python_and_packages():
    env = check_environment()
    assert env["python_ok"] is True
    assert set(env["packages"]) == {"docx", "lxml", "pdfplumber", "yaml", "bibtexparser"}


def test_doctor_lists_missing_tool_with_install_hint(monkeypatch):
    monkeypatch.setattr(render, "find_soffice", lambda: None)
    env = check_environment()
    item = next(m for m in env["missing"] if m["what"] == "LibreOffice")
    assert "libreoffice.org" in item["how_to_install"]


def test_cli_doctor_json(capsys):
    assert main(["doctor", "--json"]) == 0
    assert "python_ok" in json.loads(capsys.readouterr().out)
