import hashlib
import shutil
import subprocess
import sys

import pytest

from helpmewrite.edits import Edit, EditSet, EditsError, dump_edits
from helpmewrite.render import RenderError
from helpmewrite.track_tex import apply_edits_tex, texdiff

MAIN = (b"\\documentclass{article}\n\\begin{document}\nPrimo paragrafo con un errorre.\n"
        b"\\input{cap}\n\\end{document}\n")
CAP = "Secondo capitolo: citt\u00e0 e perch\u00e9.\r\nUn altro errorre qui.\r\nFine.\r\n"


def edit(find, replace, file="main.tex", line=3, comment=None):
    return Edit(None, file, line, find, replace, comment, "r", "revisore")


@pytest.fixture
def project(tmp_path):
    src = tmp_path / "Tesi Universit\u00e0"
    src.mkdir()
    (src / "main.tex").write_bytes(MAIN)
    (src / "cap.tex").write_bytes(CAP.encode("utf-8"))
    (src / "main.aux").write_text("junk")
    (src / ".help-me-write").mkdir()
    return src


def hashes(folder):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*") if p.is_file()}


def test_edit_applied_on_exact_line_and_originals_untouched(project, tmp_path):
    before = hashes(project)
    out = tmp_path / "out"
    r = apply_edits_tex(project / "main.tex", EditSet("a", [edit("errorre", "errore")]), out)
    assert r.applied == [0] and r.failed == []
    assert b"un errore." in (out / "main.tex").read_bytes()
    assert not (out / "main.aux").exists() and not (out / ".help-me-write").exists()
    assert hashes(project) == before


def test_line_shifted_found_in_window(project, tmp_path):
    out = tmp_path / "out"
    r = apply_edits_tex(project / "main.tex", EditSet("a", [edit("errorre", "errore", line=5)]), out)
    assert r.applied == [0]
    r2 = apply_edits_tex(project / "main.tex", EditSet("a", [edit("errorre", "errore", line=7)]),
                         tmp_path / "out2")
    assert r2.failed[0]["reason"] == "not found"


def test_ambiguous_and_multiline_fail(project, tmp_path):
    (project / "main.tex").write_bytes(b"x errorre errorre\ny\n")
    r = apply_edits_tex(project / "main.tex", EditSet("a", [
        edit("errorre", "e", line=1), edit("x", "y\nz", line=1), edit("a\nb", "c", line=1)]),
        tmp_path / "o1")
    assert [f["reason"] for f in r.failed] == ["ambiguous", "multi-line", "multi-line"]
    (project / "main.tex").write_bytes(b"x\nerrorre\nerrorre\n")
    r = apply_edits_tex(project / "main.tex", EditSet("a", [edit("errorre", "e", line=1)]),
                        tmp_path / "o2")
    assert r.failed[0]["reason"] == "ambiguous"


def test_encoding_and_crlf_preserved_and_comment_only(project, tmp_path):
    out = tmp_path / "out"
    r = apply_edits_tex(project / "main.tex", EditSet("a", [
        edit("errorre", "errore", file="cap.tex", line=2),
        edit("Fine", None, file="cap.tex", line=3, comment="boh")]), out)
    assert r.applied == [0, 1] and r.failed == []
    assert (out / "cap.tex").read_bytes() == CAP.replace("errorre", "errore").encode("utf-8")


def test_latin1_file_reported(project, tmp_path):
    (project / "cap.tex").write_bytes("citt\u00e0 errorre\n".encode("latin-1"))
    r = apply_edits_tex(project / "main.tex", EditSet("a", [
        edit("errorre", "errore", file="cap.tex", line=1)]), tmp_path / "out")
    assert r.applied == [0] and r.notes
    assert (tmp_path / "out" / "cap.tex").read_bytes() == "citt\u00e0 errore\n".encode("latin-1")


def test_bad_file_fails(project, tmp_path):
    r = apply_edits_tex(project / "main.tex", EditSet("a", [
        edit("x", "y", file="../main.tex", line=1), edit("x", "y", file="nope.tex", line=1)]),
        tmp_path / "out")
    assert len(r.failed) == 2


def test_out_dir_rules(project, tmp_path):
    with pytest.raises(EditsError):
        apply_edits_tex(project / "main.tex", EditSet("a", []), project / "sub")
    with pytest.raises(EditsError):
        apply_edits_tex(project / "main.tex", EditSet("a", []), tmp_path)
    full = tmp_path / "full"
    full.mkdir()
    (full / "x").write_text("x")
    with pytest.raises(EditsError):
        apply_edits_tex(project / "main.tex", EditSet("a", []), full)
    empty = tmp_path / "empty"
    empty.mkdir()
    apply_edits_tex(project / "main.tex", EditSet("a", []), empty)
    assert (empty / "main.tex").exists()


def test_cli_track_tex(project, tmp_path):
    ed = tmp_path / "e.json"
    dump_edits(EditSet("a", [edit("errorre", "errore")]), ed)
    from helpmewrite import cli
    out = tmp_path / "outcli"
    assert cli.main(["track", str(project / "main.tex"), "--edits", str(ed), "-o", str(out)]) == 0
    assert b"errore." in (out / "main.tex").read_bytes()
    assert cli.main(["track", str(project / "main.tex"), "--edits", str(ed),
                     "-o", str(project / "x")]) == 2


def test_texdiff_missing_tool(project, tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(RenderError) as exc:
        texdiff(project / "main.tex", project / "main.tex", tmp_path / "d.pdf")
    assert exc.value.missing_tool == "latexdiff"


@pytest.mark.needs_latex
def test_texdiff_produces_pdf(project, tmp_path):
    out = tmp_path / "out"
    apply_edits_tex(project / "main.tex", EditSet("a", [edit("errorre", "errore")]), out)
    pdf = texdiff(project / "main.tex", out / "main.tex", tmp_path / "diff.pdf")
    assert pdf.read_bytes().startswith(b"%PDF")
    with pytest.raises(RenderError):
        texdiff(project / "main.tex", out / "main.tex", out / "main.tex")
    from helpmewrite import cli
    assert cli.main(["texdiff", str(project / "main.tex"), str(out / "main.tex"),
                     "-o", str(tmp_path / "d2.pdf")]) == 0
