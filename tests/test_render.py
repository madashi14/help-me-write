import shutil
from pathlib import Path

import pytest

from fixtures.builders import italian_paragraphs, write_docx
from helpmewrite import render
from helpmewrite.render import RenderError, render_pdf, soffice_command

needs_soffice = pytest.mark.needs_soffice


def test_soffice_command_uses_private_profile(tmp_path):
    cmd = soffice_command(Path("a.docx"), tmp_path, tmp_path / "prof")
    assert any(c.startswith("-env:UserInstallation=file:") for c in cmd) and "--headless" in cmd
    assert cmd[cmd.index("--convert-to") + 1] == "pdf"
    assert cmd[cmd.index("--outdir") + 1] == str(tmp_path)
    assert cmd[-1] == str(Path("a.docx"))


@needs_soffice
def test_render_path_with_spaces_and_accents(tmp_path):
    src = write_docx(tmp_path / "Relazione finale Università.docx", italian_paragraphs(3))
    pdf = render_pdf(src, tmp_path / "work")
    assert pdf.exists() and pdf.suffix == ".pdf"
    assert pdf.stem == "Relazione finale Università"


@needs_soffice
def test_render_workdir_with_spaces_and_accents_keeps_no_profile(tmp_path):
    src = write_docx(tmp_path / "a.docx", italian_paragraphs(1))
    work = tmp_path / "lavoro è qui"
    pdf = render_pdf(src, work)
    assert pdf.name == "a.pdf" and pdf.exists() and pdf.parent.parent == work
    assert list(work.iterdir()) == [pdf.parent]  # temporary profile removed


def test_render_tex_without_latexmk_reports_missing_tool(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(RenderError) as e:
        render_pdf(tmp_path / "main.tex", tmp_path)
    assert e.value.missing_tool == "latexmk"


def test_render_docx_without_soffice_reports_missing_tool(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "find_soffice", lambda: None)
    src = write_docx(tmp_path / "a.docx", ["Uno."])
    with pytest.raises(RenderError) as e:
        render_pdf(src, tmp_path / "w")
    assert e.value.missing_tool == "soffice"
    assert "LibreOffice" in str(e.value)


def test_render_pdf_is_returned_as_is(tmp_path):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    assert render_pdf(pdf, tmp_path / "w") == pdf


def test_render_unsupported_format(tmp_path):
    with pytest.raises(RenderError) as e:
        render_pdf(tmp_path / "a.odt", tmp_path / "w")
    assert e.value.missing_tool is None


def test_render_reports_soffice_failure(tmp_path, monkeypatch):
    import subprocess

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout=b"", stderr=b"boom: bad file")

    monkeypatch.setattr(render, "find_soffice", lambda: "/usr/bin/soffice")
    monkeypatch.setattr(subprocess, "run", fake_run)
    src = write_docx(tmp_path / "a.docx", ["Uno."])
    with pytest.raises(RenderError) as e:
        render_pdf(src, tmp_path / "w")
    assert e.value.missing_tool is None and "boom" in str(e.value)


@needs_soffice
def test_render_never_touches_files_in_workdir(tmp_path):
    src = write_docx(tmp_path / "Relazione.docx", italian_paragraphs(1))
    own = tmp_path / "Relazione.pdf"
    own.write_bytes(b"%PDF-1.4 the student's own export")
    pdf = render_pdf(src, tmp_path)
    assert own.read_bytes() == b"%PDF-1.4 the student's own export"
    assert pdf != own and pdf.parent.parent == tmp_path


def test_render_tex_into_fresh_subfolder(tmp_path, monkeypatch):
    import subprocess

    calls = []

    def fake_run(cmd, cwd=None, **kwargs):
        calls.append((cmd, cwd))
        outdir = Path(next(c for c in cmd if c.startswith("-outdir=")).split("=", 1)[1])
        (outdir / "main.pdf").write_bytes(b"%PDF-1.4")
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/latexmk")
    monkeypatch.setattr(subprocess, "run", fake_run)
    tex = tmp_path / "main.tex"
    tex.write_text("\\documentclass{article}", encoding="utf-8")
    (tmp_path / "main.pdf").write_bytes(b"own")
    pdf = render_pdf(tex, tmp_path)
    assert (tmp_path / "main.pdf").read_bytes() == b"own"
    assert pdf.parent.parent == tmp_path and pdf.read_bytes() == b"%PDF-1.4"
    cmd, cwd = calls[0]
    assert cmd[:3] == ["/usr/bin/latexmk", "-pdf", "-interaction=nonstopmode"] and cwd == tmp_path
