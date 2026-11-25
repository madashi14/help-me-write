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


# --- tracked changes are rendered accepted -------------------------------------------------

def _page_count(pdf):
    import pdfplumber

    with pdfplumber.open(str(pdf)) as doc:
        return len(doc.pages)


@needs_soffice
def test_docx_with_tracked_deletions_renders_as_accepted(tmp_path):
    """Deleted text would be laid out struck through: pages, lines and sections measured
    must be those of the text with the changes accepted (the user's file is untouched)."""
    from helpmewrite.edits import Edit, EditSet
    from helpmewrite.track_docx import apply_edits_docx

    paragraphs = italian_paragraphs(24)
    src = write_docx(tmp_path / "bozza.docx", paragraphs)
    deleted = range(4, 20)
    edits = EditSet("help-me-write", [Edit(i, None, None, paragraphs[i], "", None, "r", "revisore")
                                      for i in deleted])
    tracked = tmp_path / "bozza-revisionato.docx"
    assert apply_edits_docx(src, edits, tracked).failed == []
    accepted = write_docx(tmp_path / "accettato.docx",
                          ["" if i in deleted else t for i, t in enumerate(paragraphs)])
    before = tracked.read_bytes()
    original_pages = _page_count(render_pdf(src, tmp_path / "w1"))
    accepted_pages = _page_count(render_pdf(accepted, tmp_path / "w2"))
    assert original_pages > accepted_pages  # the deletion is long enough to matter
    assert _page_count(render_pdf(tracked, tmp_path / "w3")) == accepted_pages
    assert tracked.read_bytes() == before


def test_accepted_view_settings_replaces_and_orders_revision_view():
    xml = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           b'<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           b'<w:zoom w:percent="100"/><w:revisionView w:insDel="true"/><w:trackRevisions/>'
           b'<w:defaultTabStop w:val="708"/></w:settings>')
    out = render.accepted_view_settings(xml).decode("utf-8")
    assert out.count("revisionView") == 1
    assert ('<w:zoom w:percent="100"/><w:revisionView w:markup="false" w:insDel="false" '
            'w:formatting="false"/><w:trackRevisions/>') in out
    bare = (b'<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            b'</w:settings>')
    assert b"<w:revisionView" in render.accepted_view_settings(bare)
    assert render.accepted_view_settings(b"<settings/>") is None


def test_unreadable_docx_is_passed_to_libreoffice_as_is(tmp_path):
    bad = tmp_path / "bad.docx"
    bad.write_bytes(b"not a zip")
    assert render._accepted_copy(bad, tmp_path) == bad


# --- LaTeX engine --------------------------------------------------------------------------

def _tex(folder, text, name="main.tex"):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize("first_line, engine", [
    ("% !TEX program = xelatex", "-xelatex"),
    ("% !TeX TS-program = lualatex", "-lualatex"),
    ("%!TEX program=pdflatex", "-pdf"),
])
def test_tex_engine_from_magic_comment(tmp_path, first_line, engine):
    main = _tex(tmp_path, first_line + "\n\\documentclass{article}\n\\usepackage{fontspec}\n")
    assert render.tex_engine(main) == [engine]


def test_tex_engine_from_packages_in_included_files(tmp_path, monkeypatch):
    main = _tex(tmp_path, "\\documentclass{article}\n\\input{preambolo}\n"
                          "% \\usepackage{luacode}\n\\begin{document}x\\end{document}\n")
    _tex(tmp_path, "\\usepackage[italian]{babel}\n\\usepackage[a,b]{xcolor,polyglossia}\n",
         "preambolo.tex")
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    assert render.tex_engine(main) == ["-xelatex"]
    monkeypatch.setattr(shutil, "which",
                        lambda name: None if name == "xelatex" else f"/usr/bin/{name}")
    assert render.tex_engine(main) == ["-lualatex"]


def test_tex_engine_default_and_latexmkrc(tmp_path):
    main = _tex(tmp_path, "\\documentclass{article}\n% \\usepackage{fontspec}\n")
    assert render.tex_engine(main) == ["-pdf"]
    (tmp_path / "latexmkrc").write_text("# $pdf_mode = 5;\n$out_dir = 'build';\n")
    assert render.tex_engine(main) == ["-pdf"]  # the rc does not choose an engine
    (tmp_path / ".latexmkrc").write_text("$pdf_mode = 5;\n")
    assert render.tex_engine(main) == []


def test_tex_engine_reaches_latexmk(tmp_path, monkeypatch):
    import subprocess

    calls = []

    def fake_run(cmd, cwd=None, **kwargs):
        calls.append(cmd)
        outdir = Path(next(c for c in cmd if c.startswith("-outdir=")).split("=", 1)[1])
        (outdir / "main.pdf").write_bytes(b"%PDF-1.4")
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    main = _tex(tmp_path / "p", "\\documentclass{article}\n\\usepackage{fontspec}\n")
    render_pdf(main, tmp_path / "w")
    render_pdf(main, tmp_path / "w", engine=[])
    assert calls[0][:2] == ["/usr/bin/latexmk", "-xelatex"]
    assert calls[1][:2] == ["/usr/bin/latexmk", "-interaction=nonstopmode"]


@pytest.mark.needs_latex
def test_latex_error_message_has_the_log_error(tmp_path):
    main = _tex(tmp_path / "p", "\\documentclass{article}\n\\begin{document}\n"
                                "\\comandoinesistente\n\\end{document}\n")
    with pytest.raises(RenderError) as e:
        render_pdf(main, tmp_path / "w")
    assert "! Undefined control sequence." in str(e.value) and "l.3" in str(e.value)
    assert "-pdf" in str(e.value)


@pytest.mark.needs_latex
@pytest.mark.skipif(shutil.which("xelatex") is None, reason="xelatex not installed")
def test_fontspec_document_compiles_with_xelatex(tmp_path):
    main = _tex(tmp_path / "p", "\\documentclass{article}\n\\usepackage{fontspec}\n"
                                "\\begin{document}\nCittà e perché.\n\\end{document}\n")
    assert render.tex_engine(main) == ["-xelatex"]
    assert render_pdf(main, tmp_path / "w").read_bytes().startswith(b"%PDF")


@needs_soffice
def test_render_accepts_changes_without_settings_part(tmp_path):
    import zipfile

    import pdfplumber

    src = write_docx(tmp_path / "t.docx", ["Testo di base."])
    body = ('<w:p><w:r><w:t>Inizio </w:t></w:r>'
            '<w:del w:id="901" w:author="A" w:date="2026-01-01T00:00:00Z"><w:r>'
            '<w:delText>TESTOCANCELLATO</w:delText></w:r></w:del>'
            '<w:ins w:id="902" w:author="A" w:date="2026-01-01T00:00:00Z"><w:r>'
            '<w:t>TESTOINSERITO</w:t></w:r></w:ins></w:p>')
    out = tmp_path / "nosettings.docx"
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w") as zout:
        for item in zin.infolist():
            data = zin.read(item)
            if item.filename == "word/settings.xml":
                continue
            if item.filename == "[Content_Types].xml":
                data = data.replace(
                    b"</Types>",
                    b'<Override PartName="/word/settings.xml" ContentType="x"/></Types>')
                import re
                data = re.sub(rb'<Override PartName="/word/settings.xml"[^>]*/>', b"", data)
            if item.filename == "word/_rels/document.xml.rels":
                import re
                data = re.sub(rb"<Relationship [^>]*relationships/settings[^>]*/>", b"", data)
            if item.filename == "word/document.xml":
                text = data.decode("utf-8")
                text = text.replace("<w:body>", "<w:body>" + body, 1)
                data = text.encode("utf-8")
            zout.writestr(item, data)
    with zipfile.ZipFile(out) as z:
        assert "word/settings.xml" not in z.namelist()
    pdf = render_pdf(out, tmp_path / "work")
    with pdfplumber.open(pdf) as doc:
        text = "\n".join(p.extract_text() or "" for p in doc.pages)
    assert "TESTOINSERITO" in text and "TESTOCANCELLATO" not in text
