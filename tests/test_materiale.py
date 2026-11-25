import base64
import json
import os
import re
import shutil
import subprocess
import time
import zipfile

import pytest

from conftest import ROOT
from helpmewrite import materiale
from helpmewrite.cli import main
from helpmewrite.materiale import MaterialError, inventory, kind_of, notebook_markdown

PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 24)


def _w(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _zip(path, members, date=(2026, 10, 2, 12, 0, 0)):
    """members: name -> bytes | (bytes, external_attr)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            attr = 0
            if isinstance(data, tuple):
                data, attr = data
            info = zipfile.ZipInfo(name, date_time=date)
            info.external_attr = attr
            zf.writestr(info, data)


def _all_files(root):
    return {p for p in root.rglob("*") if p.is_file()}


def test_kind_of():
    assert kind_of("a.PY") == "code"
    assert kind_of("x/n.ipynb") == "notebook"
    assert kind_of("d.csv") == "data"
    assert kind_of("r.pdf") == "document"
    assert kind_of("f.jpeg") == "image"
    assert kind_of("z.tgz") == "archive"
    assert kind_of("m.npz") == "model"
    assert kind_of("README") == "other"


def test_material_inventory_kinds_and_skips(tmp_path):
    for rel in ("a.py", "d/metrics.csv", "n.ipynb", "m.joblib", ".git/x",
                "node_modules/y.js", ".help-me-write/z.md", ".pytest_cache/c", "env/e.py"):
        _w(tmp_path / rel)
    inv = inventory(tmp_path)
    assert {f["path"]: f["kind"] for f in inv["files"]} == {
        "a.py": "code", "d/metrics.csv": "data", "n.ipynb": "notebook", "m.joblib": "model"}
    assert {"size", "modified"} <= set(inv["files"][0])
    assert {".git", "node_modules", ".help-me-write", ".pytest_cache", "env"} <= \
        {d.split("/")[-1] for d in inv["skipped_dirs"]}
    assert inv["truncated"] is False


def test_material_zip_extracts_text_members_only(tmp_path):
    work = tmp_path / "lavoro"
    _zip(work / "rf.zip", {"rf/train.py": b"print(1)", "rf/metrics (2).json": b"{}",
                           "rf/model.joblib": b"\x00", "rf/fig.png": PNG,
                           "rf/inner.zip": b"PK"})
    out = tmp_path / "estratti"
    inv = inventory(work, out)
    arc = inv["archives"][0]
    assert arc["path"] == "rf.zip" and arc["opened"] is True
    dest = out / "rf"
    assert {p.relative_to(dest).as_posix() for p in _all_files(dest)} == \
        {"rf/train.py", "rf/metrics (2).json", "rf/fig.png"}
    reasons = {s["name"]: s["reason"] for s in arc["skipped"]}
    assert reasons["rf/model.joblib"] == "model file: listed, never loaded"
    assert reasons["rf/inner.zip"] == "nested archive: not opened"
    assert {m["name"] for m in arc["members"]} >= {"rf/train.py", "rf/model.joblib"}
    assert arc["members"][0]["date"] == "2026-10-02"
    # a second run does not rewrite
    again = inventory(work, out)["archives"][0]
    assert again["note"] == "already extracted" and "extracted_to" in again


def test_material_zip_hostile_members(tmp_path, monkeypatch):
    work = tmp_path / "lavoro"
    monkeypatch.setattr(materiale, "MAX_MEMBER_BYTES", 10)
    _zip(work / "h.zip", {
        "../evil.py": b"1", "/abs.py": b"1", "C:/x.py": b"1",
        "link.py": (b"/etc/passwd", 0o120777 << 16),
        "big.py": b"x" * 50, "cafX.py": b"ok", "sub/../../up.py": b"1"})
    raw = (work / "h.zip").read_bytes().replace(b"cafX.py", b"caf\x82.py")
    (work / "h.zip").write_bytes(raw)
    before = _all_files(tmp_path)
    out = tmp_path / "estratti"
    arc = inventory(work, out)["archives"][0]
    dest = out / "h"
    new = _all_files(tmp_path) - before
    assert all(dest in p.parents for p in new)
    assert [p.name for p in new] == ["café.py"]
    skipped = {s["name"]: s["reason"] for s in arc["skipped"]}
    for name in ("../evil.py", "/abs.py", "C:/x.py", "link.py", "big.py", "sub/../../up.py"):
        assert skipped.get(name), name


def test_material_zip_corrupt_member(tmp_path, capsys):
    work = tmp_path / "w"
    work.mkdir()
    with zipfile.ZipFile(work / "c.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bad.py", bytes(range(256)) * 40)
        zf.writestr("good.py", b"print(1)\n" * 50)
        offset = zf.getinfo("bad.py").header_offset + 30 + len("bad.py")
    raw = bytearray((work / "c.zip").read_bytes())
    for i in range(offset + 5, offset + 25):
        raw[i] ^= 0xFF
    (work / "c.zip").write_bytes(bytes(raw))
    assert main(["material", str(work), "--extract", str(tmp_path / "e")]) == 0
    arc = inventory(work, tmp_path / "e2")["archives"][0]
    assert [e["name"] for e in arc["extracted"]] == ["good.py"]
    assert [s["name"] for s in arc["skipped"]] == ["bad.py"]
    assert arc["skipped"][0]["reason"].startswith("corrupt member")
    assert not (tmp_path / "e2" / "c" / "bad.py").exists()


def test_material_zip_backslash_members(tmp_path):
    work = tmp_path / "w"
    _zip(work / "b.zip", {"..\\x.py": b"1", "C:\\x.py": b"1", "\\abs.py": b"1"})
    before = _all_files(tmp_path)
    arc = inventory(work, tmp_path / "e")["archives"][0]
    assert _all_files(tmp_path) == before
    assert len(arc["skipped"]) == 3 and not arc["extracted"]


def test_material_zip_member_caps(tmp_path, capsys):
    """I6: a zipped repository with more than 2000 members neither floods the inventory nor
    the extraction folder; the author's notes are extracted first."""
    work = tmp_path / "w"
    members = {f"repo/node_modules/p{i // 100:02}/f{i:04}.js": b"" for i in range(2500)}
    members.update({f"repo/build/o{i:04}.o": b"" for i in range(2100)})
    members["repo/README.md"] = b"leggimi"
    _zip(work / "repo.zip", members)
    out = tmp_path / "e"
    inv = inventory(work, out)
    arc = inv["archives"][0]
    assert arc["member_count"] == 4601 and arc["truncated"] is True
    assert len(arc["members"]) == materiale.MAX_MEMBERS == 2000
    assert arc["counts_by_dir"] == {"repo": 1, "repo/build": 2100, "repo/node_modules": 2500}
    assert len(arc["extracted"]) == materiale.MAX_EXTRACT_MEMBERS == 2000
    assert len(_all_files(out)) == 2000
    assert arc["extracted"][0]["name"] == "repo/README.md"
    assert len(arc["skipped"]) == materiale.MAX_MEMBERS
    assert arc["skipped_not_listed"] == 100
    assert arc["extract_note"].startswith("501 members not extracted")
    assert len(json.dumps(inv)) < 1_000_000
    # in total too: a second archive is listed within what is left
    _zip(work / "altro.zip", {f"x/{i:04}.txt": b"t" for i in range(10)})
    inv = inventory(work, tmp_path / "e2")
    altro = next(a for a in inv["archives"] if a["path"] == "altro.zip")
    assert altro["member_count"] == 10 and len(altro["members"]) == 10
    assert sum(len(a.get("extracted", [])) for a in inv["archives"]) == 2000
    assert main(["material", str(work)]) == 0
    assert "archive repo.zip: 4601 members (2000 listed)" in capsys.readouterr().out


def test_material_total_extract_limit(tmp_path, monkeypatch):
    work = tmp_path / "w"
    monkeypatch.setattr(materiale, "MAX_EXTRACT_BYTES", 15)
    _zip(work / "a.zip", {"a.py": b"x" * 10, "b.py": b"y" * 10})
    arc = inventory(work, tmp_path / "e")["archives"][0]
    assert len(arc["extracted"]) == 1 and len(arc["skipped"]) == 1


def test_material_non_zip_archive_listed_not_opened(tmp_path):
    (tmp_path / "x.tar.gz").write_bytes(b"\x1f\x8b")
    arc = inventory(tmp_path)["archives"][0]
    assert arc == {"path": "x.tar.gz", "opened": False}


def test_material_dates_unreliable_and_archive_dates(tmp_path):
    _zip(tmp_path / "a.zip", {"a.py": b"1"}, date=(2026, 10, 2, 12, 0, 0))
    _zip(tmp_path / "b.zip", {"b.py": b"1"}, date=(2026, 11, 24, 12, 0, 0))
    _w(tmp_path / "c.py")
    stamp = time.mktime((2026, 11, 24, 12, 0, 0, 0, 0, -1))
    for p in tmp_path.iterdir():
        os.utime(p, (stamp, stamp))
    inv = inventory(tmp_path)
    assert inv["dates"]["reliable"] is False
    assert inv["dates"]["archives"] == {"first": "2026-10-02", "last": "2026-11-24"}
    assert "upload" in inv["dates"]["note"] or "copy" in inv["dates"]["note"]


@pytest.mark.skipif(shutil.which("git") is None, reason="git missing")
def test_material_git_history(tmp_path):
    def git(*args, date=None):
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        if date:
            env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, env=env,
                       capture_output=True)
    git("init", "-q")
    _w(tmp_path / "a.py", "1")
    git("add", ".")
    git("commit", "-qm", "one", date="2026-10-01T12:00:00")
    _w(tmp_path / "a.py", "2")
    git("commit", "-qam", "two", date="2026-11-20T12:00:00")
    inv = inventory(tmp_path)
    assert inv["git"] == {"commits": 2, "first": "2026-10-01", "last": "2026-11-20"}
    assert inv["dates"]["reliable"] is True


@pytest.mark.skipif(shutil.which("git") is None, reason="git missing")
def test_material_nested_git_repository(tmp_path):
    repo = tmp_path / "progetto"
    _w(repo / "a.py", "1")
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

    def git(*args, date=None):
        e = dict(env)
        if date:
            e["GIT_AUTHOR_DATE"] = e["GIT_COMMITTER_DATE"] = date
        subprocess.run(["git", "-C", str(repo), *args], check=True, env=e, capture_output=True)
    git("init", "-q")
    git("add", ".")
    git("commit", "-qm", "one", date="2026-10-01T12:00:00")
    _w(repo / "a.py", "2")
    git("commit", "-qam", "two", date="2026-11-20T12:00:00")
    inv = inventory(tmp_path)
    assert inv["git"] is None
    assert inv["git_repos"] == [{"path": "progetto", "commits": 2, "first": "2026-10-01",
                                 "last": "2026-11-20"}]
    assert inv["dates"]["reliable"] is True
    assert not any(f["path"].startswith("progetto/.git/") for f in inv["files"])


def test_material_no_git_is_null(tmp_path):
    _w(tmp_path / "a.py")
    assert inventory(tmp_path)["git"] is None
    assert inventory(tmp_path)["git_repos"] == []


def test_material_truncates_large_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(materiale, "MAX_FILES", 50)
    for i in range(120):
        _w(tmp_path / ("sub" if i % 2 else "other") / f"f{i:03}.txt")
    inv = inventory(tmp_path)
    assert len(inv["files"]) == 50 and inv["truncated"] is True
    assert inv["counts_by_dir"] == {"other": 60, "sub": 60}


def _notebook(path):
    nb = {"nbformat": 4, "cells": [
        {"cell_type": "markdown", "source": ["# Title\n", "text"]},
        {"cell_type": "code", "source": "print(1)", "outputs": [
            {"output_type": "stream", "name": "stdout",
             "text": [f"line {i}\n" for i in range(40)]},
            {"output_type": "display_data", "data": {
                "image/png": base64.b64encode(PNG).decode(), "text/plain": "<Figure>"}},
            {"output_type": "display_data", "data": {
                "image/png": base64.b64encode(b"not a png").decode()}},
            {"output_type": "error", "ename": "ValueError", "evalue": "bad", "traceback": []}]},
    ]}
    path.write_text(json.dumps(nb), encoding="utf-8")


def test_notebook_markdown_images_and_truncation(tmp_path):
    nbf = tmp_path / "travi.ipynb"
    _notebook(nbf)
    md, images = notebook_markdown(nbf, tmp_path / "img")
    assert "## Cell 1 (markdown)" in md and "## Cell 2 (code)" in md
    assert "```python\nprint(1)\n```" in md
    assert "line 29" in md and "line 30" not in md and "[... 10 more lines]" in md
    assert "ValueError: bad" in md
    assert [p.name for p in images] == ["travi-cell2-1.png"]
    assert images[0].read_bytes() == PNG and "travi-cell2-1.png" in md


def test_notebook_invalid_json(tmp_path):
    bad = tmp_path / "b.ipynb"
    bad.write_text("{nope", encoding="utf-8")
    with pytest.raises(MaterialError):
        notebook_markdown(bad, None)


def test_cli_material_and_notebook(tmp_path, capsys):
    work = tmp_path / "w"
    _w(work / "a.py")
    _notebook(work / "n.ipynb")
    out = tmp_path / "inv.json"
    assert main(["material", str(work), "-o", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["files"]
    assert main(["material", str(work), "-o", str(out)]) == 0   # JSON output is rewritten
    assert main(["material", str(work)]) == 0
    assert "code" in capsys.readouterr().out
    md = tmp_path / "n.md"
    assert main(["notebook", str(work / "n.ipynb"), "-o", str(md),
                 "--images", str(tmp_path / "im")]) == 0
    assert "## Cell 1" in md.read_text(encoding="utf-8")
    assert main(["notebook", str(work / "n.ipynb"), "-o", str(md)]) == 2
    assert "n-2.md" in capsys.readouterr().err
    assert main(["notebook", str(work / "n.ipynb"), "-o", str(tmp_path / "n3.md"),
                 "--images", str(tmp_path / "im")]) == 2
    assert "new --images folder" in capsys.readouterr().err
    (work / "bad.ipynb").write_text("{", encoding="utf-8")
    assert main(["notebook", str(work / "bad.ipynb"), "-o", str(tmp_path / "b.md")]) == 2


def test_material_module_never_loads_user_code():
    src = (ROOT / "scripts/helpmewrite/materiale.py").read_text(encoding="utf-8")
    banned = "pickle|joblib|runpy|importlib|marshal|dill|cloudpickle"
    assert not re.search(rf"^\s*(import|from)\s+({banned})\b", src, re.MULTILINE)
    assert not re.search(r"\b(exec|eval|__import__)\(", src)
