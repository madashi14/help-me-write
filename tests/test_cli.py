"""The command line itself: Python version guard, lazy imports, errors without tracebacks."""
import json
import runpy
import subprocess
import sys

import pytest

from conftest import ROOT
from fixtures.builders import write_docx
from helpmewrite import cli, doctor

HMW = ROOT / "scripts" / "hmw.py"
PACKAGES = ("docx", "lxml", "pdfplumber", "yaml", "bibtexparser", "matplotlib")


# --- Python version ----------------------------------------------------------------------

def test_hmw_refuses_an_old_python_before_importing_anything(monkeypatch, capsys):
    monkeypatch.setattr(sys, "version_info", (3, 9, 18, "final", 0))
    monkeypatch.delitem(sys.modules, "helpmewrite.cli", raising=False)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(HMW), run_name="__main__")
    assert exc.value.code == 3
    err = capsys.readouterr().err
    assert "needs Python 3.10 or newer" in err and "3.9.18" in err
    assert "python.org" in err and "Traceback" not in err
    assert "helpmewrite.cli" not in sys.modules  # the guard runs before the package import


# --- missing packages --------------------------------------------------------------------

def _hide(monkeypatch, *names):
    """Make `import <name>` fail as if the package were not installed."""
    for name in names:
        monkeypatch.setitem(sys.modules, name, None)


def test_doctor_runs_without_any_package(monkeypatch, capsys):
    _hide(monkeypatch, *PACKAGES)
    assert cli.main(["doctor", "--json"]) == 0
    env = json.loads(capsys.readouterr().out)
    assert env["packages"] == {name: None for name in PACKAGES}
    hints = [m["how_to_install"] for m in env["missing"] if "package" in m["what"]]
    assert len(hints) == len(PACKAGES)
    requirements = str(ROOT / "requirements.txt")
    assert all(f'"{sys.executable}" -m pip install -r "{requirements}"' in h for h in hints)
    assert all("externally-managed-environment" in h for h in hints)


def test_command_with_a_missing_package_exits_3_with_the_install_command(
        monkeypatch, capsys, tmp_path):
    src = write_docx(tmp_path / "a.docx", ["Uno."])
    _hide(monkeypatch, "lxml")
    assert cli.main(["extract", str(src)]) == 3
    err = capsys.readouterr().err
    assert "missing Python package(s): lxml" in err
    assert f'"{sys.executable}" "{HMW}" doctor' in err
    assert str(ROOT / "requirements.txt") in err and "Traceback" not in err


def test_yaml_missing_only_blocks_the_commands_that_need_it(monkeypatch, capsys, tmp_path):
    _hide(monkeypatch, "yaml")
    rules = tmp_path / "r.yaml"
    rules.write_text("document_type: x\n", encoding="utf-8")
    assert cli.main(["rules", "validate", str(rules)]) == 3
    assert "PyYAML" in capsys.readouterr().err
    assert cli.main(["doctor"]) == 0


def test_hmw_without_site_packages_doctor_and_extract():
    """`python -S`: only the standard library, as on a fresh Python."""
    probe = subprocess.run([sys.executable, "-S", "-c", "import docx"], capture_output=True)
    if probe.returncode == 0:
        pytest.skip("python-docx is importable without site-packages here")
    run = subprocess.run([sys.executable, "-S", str(HMW), "doctor", "--json"],
                         capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["packages"]["docx"] is None
    run = subprocess.run([sys.executable, "-S", str(HMW), "extract", "x.docx"],
                         capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 3
    assert "missing Python package(s)" in run.stderr and "Traceback" not in run.stderr


def test_install_hint_lists_the_packages_without_requirements(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "REQUIREMENTS", tmp_path / "missing.txt")
    hint = cli.install_hint()
    assert " -m pip install " in hint
    for name in ('"python-docx>=1.2"', "lxml", "pdfplumber", "PyYAML", '"bibtexparser>=1.4,<2"', '"matplotlib>=3.7"'):
        assert name in hint


def test_install_hint_uses_running_python():
    import sys

    assert f'"{sys.executable}" -m pip install' in cli.install_hint()
    assert f'"{sys.executable}"' in cli.doctor_command()


# --- output and unexpected errors ---------------------------------------------------------

def test_emit_creates_the_output_folder(tmp_path, capsys):
    out = tmp_path / "new" / "deeper" / "doctor.json"
    assert cli.main(["doctor", "-o", str(out)]) == 0
    assert "python_ok" in json.loads(out.read_text(encoding="utf-8"))


def test_emit_unwritable_output_is_a_clean_error(tmp_path, capsys):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    assert cli.main(["doctor", "-o", str(blocker / "doctor.json")]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: cannot write") and "Traceback" not in err
    assert f"{blocker} is a file, not a folder" in err


def test_unexpected_exception_exits_2_without_traceback(monkeypatch, capsys):
    def boom(args):
        raise RuntimeError("boom")

    monkeypatch.setattr(doctor, "run", boom)
    assert cli.main(["doctor"]) == 2
    err = capsys.readouterr().err
    assert err.strip() == "error: RuntimeError: boom"


def test_parser_builds_every_command():
    parser = cli._build_parser()
    for name in cli._COMMANDS:
        args = {"assemble": ["m.yaml", "-o", "x.docx"],
                "bib": ["x.docx"], "chart": ["s.json", "-o", "g.png"],
                "diagram": ["d.json", "-o", "d.png"], "detect": ["w"], "state": ["show", "w"], "doctor": [], "extract": ["x.docx"],
                "format": ["x.docx", "--layout", "l.json", "-o", "y.docx"],
                "latex-init": ["p", "--layout", "l.json", "--chapters", "c.json"],
                "layout": ["--rules", "r.yaml", "--font", "Times"],
                "material": ["w"], "notebook": ["n.ipynb", "-o", "n.md"],
                "measure": ["x.docx", "--rules", "r.yaml"], "pdftext": ["x.pdf"],
                "rules": ["validate", "r.yaml"], "texdiff": ["a.tex", "b.tex", "-o", "d.pdf"],
                "titlepage": ["x.docx", "--values", "v.json", "-o", "y.docx"],
                "track": ["x.docx", "--edits", "e.json", "-o", "y.docx"]}[name]
        assert parser.parse_args([name] + args).handler


# --- never overwrite ----------------------------------------------------------------------

def test_next_free_name(tmp_path):
    doc = tmp_path / "bozza-revisionato.docx"
    assert cli.next_free_name(doc) == doc
    doc.write_text("x")
    assert cli.next_free_name(doc) == tmp_path / "bozza-revisionato-2.docx"
    (tmp_path / "bozza-revisionato-2.docx").write_text("x")
    assert cli.next_free_name(doc) == tmp_path / "bozza-revisionato-3.docx"
    folder = tmp_path / "tesi-revisionato"
    folder.mkdir()
    assert cli.next_free_name(folder) == tmp_path / "tesi-revisionato-2"


def test_same_file_uses_samefile(tmp_path):
    a = tmp_path / "a.docx"
    a.write_text("x")
    link = tmp_path / "link.docx"
    try:
        link.symlink_to(a)
    except OSError:
        pytest.skip("symlinks not available")
    assert cli.same_file(a, link) and not cli.same_file(a, tmp_path / "b.docx")
