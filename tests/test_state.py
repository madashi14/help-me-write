import json

import pytest

from helpmewrite.cli import main
from helpmewrite.state import (Chapter, ProjectState, StateError, fingerprint, load_state,
                               modified, next_step, save_state)

BODY = "## Decisioni\n- Word\n\n## Domande aperte\nnote libere\n"
DONE = {"format": "word", "outline_approved": True, "title_page_approved": True}
ALL = ["materiale.md", "linee-guida.yaml"]


def _project(work, files=(), fields=None, chapters=(), mode="da-zero"):
    (work / ".help-me-write").mkdir(exist_ok=True)
    for name in files:
        (work / ".help-me-write" / name).write_text("x", encoding="utf-8")
    state = ProjectState(mode=mode, body=BODY, **{"format": None, **(fields or {})})
    state.chapters = [Chapter(id=c[0], title=c[0], kind=c[1], status=c[2])
                      for c in chapters]  # given as (id, kind, status)
    save_state(work, state)
    return load_state(work)


def test_state_round_trip_and_next_step(tmp_path):
    assert main(["state", "init", str(tmp_path), "--mode", "da-zero"]) == 0
    s = load_state(tmp_path)
    assert s.mode == "da-zero" and s.format is None
    assert next_step(tmp_path, s)["phase"] == "materiale"
    assert main(["state", "init", str(tmp_path), "--mode", "da-zero"]) == 2


@pytest.mark.parametrize("files,fields,chapters,phase,chapter", [
    (["materiale.md"], {}, [], "linee-guida", None),
    (ALL, {"format": None}, [], "formato", None),
    (ALL, {"format": "word"}, [], "struttura", None),
    (ALL, {"format": "word", "outline_approved": True}, [], "frontespizio", None),
    (ALL, {"format": "word", "outline_approved": True, "title_page_approved": True},
     [("01-a", "corpo", "approvato"), ("02-b", "corpo", "intervista-fatta"),
      ("00-intro", "introduzione", "da-fare")], "scrittura", "02-b"),
    (ALL, DONE, [("01-a", "corpo", "approvato"), ("00-intro", "introduzione", "da-fare")],
     "intervista", "00-intro"),
    (ALL, DONE, [("01-a", "corpo", "scritto")], "approvazione", "01-a"),
    (ALL, DONE, [("01-a", "corpo", "approvato")], "revisione", None),
    (ALL, DONE, [("01-a", "corpo", "revisionato")], "fine", None),
])
def test_next_step_phases(tmp_path, files, fields, chapters, phase, chapter):
    s = _project(tmp_path, files, fields, chapters)
    step = next_step(tmp_path, s)
    assert step["phase"] == phase and step["chapter"] == chapter and step["why"]


def test_next_step_solo_revisione(tmp_path):
    s = _project(tmp_path, ["materiale.md"], mode="solo-revisione")
    assert next_step(tmp_path, s)["phase"] == "linee-guida"
    s = _project(tmp_path, ALL, mode="solo-revisione")
    assert next_step(tmp_path, s)["phase"] == "revisione"


def test_state_set_preserves_body(tmp_path):
    _project(tmp_path)
    w = str(tmp_path)
    assert main(["state", "set", w, "format=word", "outline_approved=true",
                 "language=en"]) == 0
    outline = tmp_path / "o.json"
    outline.write_text(json.dumps([{"id": "01-a", "title": "A", "kind": "corpo"}]))
    assert main(["state", "outline", w, "--from", str(outline)]) == 0
    assert main(["state", "chapter", w, "01-a", "--status", "scritto"]) == 0
    s = load_state(tmp_path)
    assert s.body == BODY and s.format == "word" and s.outline_approved is True
    assert s.chapters[0].status == "scritto"
    assert main(["state", "set", w, "format=null"]) == 0
    assert load_state(tmp_path).format is None
    assert main(["state", "set", w, "chapters=x"]) == 2
    assert main(["state", "set", w, "outline_approved=maybe"]) == 2


@pytest.mark.parametrize("bad,needle", [
    ("---\nmode: [da-zero\n---\n", "line"),
    ("---\nmode: da-zero\nchapters:\n  - {id: a, title: A, kind: corpo, status: fatto}\n---\n",
     "status"),
    ("---\nmode: da-zero\nformato: word\n---\n", "formato"),
    ("---\nmode: sconosciuta\n---\n", "mode"),
    ("no header\n", "---"),
])
def test_state_hand_edited_invalid(tmp_path, capsys, bad, needle):
    (tmp_path / ".help-me-write").mkdir()
    f = tmp_path / ".help-me-write" / "progetto.md"
    f.write_text(bad, encoding="utf-8")
    before = f.read_bytes()
    for argv in (["show", str(tmp_path)], ["set", str(tmp_path), "language=en"],
                 ["chapter", str(tmp_path), "a", "--status", "scritto"]):
        capsys.readouterr()
        assert main(["state", *argv]) == 2
        assert needle in capsys.readouterr().err
        assert f.read_bytes() == before


def test_state_paths_are_relative(tmp_path, capsys):
    _project(tmp_path)
    (tmp_path / "b.docx").write_bytes(b"x")
    assert main(["state", "record", str(tmp_path), str(tmp_path / "b.docx")]) == 0
    assert list(load_state(tmp_path).fingerprints) == ["b.docx"]
    outside = tmp_path.parent / "fuori.docx"
    outside.write_bytes(b"x")
    assert main(["state", "record", str(tmp_path), str(outside)]) == 2
    assert main(["state", "set", str(tmp_path), f"draft={tmp_path / 'x' / 'm.tex'}"]) == 0
    assert load_state(tmp_path).draft == "x/m.tex"
    assert main(["state", "set", str(tmp_path), f"draft={outside}"]) == 2


def test_state_modified_reports_hand_edits(tmp_path, capsys):
    _project(tmp_path)
    folder = tmp_path / "Out"
    folder.mkdir()
    (folder / "a.tex").write_text("uno", encoding="utf-8")
    (tmp_path / "b.docx").write_bytes(b"docx")
    assert main(["state", "record", str(tmp_path), str(folder), str(tmp_path / "b.docx")]) == 0
    s = load_state(tmp_path)
    assert modified(tmp_path, s) == {"Out": "unchanged", "b.docx": "unchanged"}
    (folder / "a.tex").write_text("due", encoding="utf-8")
    assert modified(tmp_path, s) == {"Out": "modified", "b.docx": "unchanged"}
    (tmp_path / "b.docx").unlink()
    assert modified(tmp_path, s)["b.docx"] == "missing"
    capsys.readouterr()
    assert main(["state", "modified", str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["Out"] == "modified"


def test_fingerprint_ignores_other_files(tmp_path):
    (tmp_path / "a.tex").write_text("x")
    before = fingerprint(tmp_path)
    (tmp_path / "a.aux").write_text("noise")
    assert fingerprint(tmp_path) == before
    (tmp_path / "a.tex").write_text("y")
    assert fingerprint(tmp_path) != before


def test_outline_keeps_progress(tmp_path, capsys):
    _project(tmp_path, chapters=[("01", "corpo", "approvato"), ("02", "corpo", "scritto")])
    s = load_state(tmp_path)
    s.chapters[1].source = "out/02.tex"
    save_state(tmp_path, s)
    outline = tmp_path / "o.json"
    outline.write_text(json.dumps([{"id": "02", "title": "Due", "kind": "corpo"},
                                   {"id": "03", "title": "Tre", "kind": "conclusione"}]))
    capsys.readouterr()
    assert main(["state", "outline", str(tmp_path), "--from", str(outline), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["removed"] == ["01"]
    ch = {c.id: c for c in load_state(tmp_path).chapters}
    assert ch["02"].status == "scritto" and ch["02"].source == "out/02.tex"
    assert ch["02"].title == "Due" and ch["03"].status == "da-fare"
    outline.write_text(json.dumps([{"id": "Bad Id", "title": "x", "kind": "corpo"}]))
    assert main(["state", "outline", str(tmp_path), "--from", str(outline)]) == 2


def test_state_show_and_chapter_errors(tmp_path, capsys):
    _project(tmp_path, chapters=[("01", "corpo", "da-fare")])
    capsys.readouterr()
    assert main(["state", "show", str(tmp_path), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["next"]["phase"] == "materiale" and data["chapters"][0]["id"] == "01"
    assert main(["state", "chapter", str(tmp_path), "zz", "--status", "scritto"]) == 2
    assert main(["state", "chapter", str(tmp_path), "01", "--status", "boh"]) == 2
    assert main(["state", "chapter", str(tmp_path), "01", "--source",
                 str(tmp_path / "c.tex"), "--notes", "n.md"]) == 0
    ch = load_state(tmp_path).chapters[0]
    assert ch.source == "c.tex" and ch.notes == "n.md"
    assert main(["state", "show", str(tmp_path / "nope")]) == 2
