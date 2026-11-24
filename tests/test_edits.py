import json

import pytest

from helpmewrite.edits import Edit, EditSet, EditsError, dump_edits, load_edits, merge_edits


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _edit(paragraph, find, replace=None, comment=None, by="revisore"):
    return Edit(paragraph, None, None, find, replace, comment, "motivo", by)


def test_load_valid_edits(tmp_path):
    path = _write(tmp_path / "e.json", {"author": "help-me-write", "edits": [
        {"paragraph": 12, "find": "e stato", "replace": "è stato",
         "reason": "accento", "by": "revisore"},
        {"paragraph": 3, "find": "Rossi 2020", "comment": "Manca l'anno nella bibliografia",
         "reason": "citazione", "by": "bibliografia"},
        {"file": "cap1.tex", "line": 7, "find": "teh", "replace": "the",
         "reason": "refuso", "by": "revisore"},
    ]})
    es = load_edits(path)
    assert es.author == "help-me-write"
    assert es.edits[0] == Edit(12, None, None, "e stato", "è stato", None, "accento", "revisore")
    assert es.edits[1].comment == "Manca l'anno nella bibliografia" and es.edits[1].replace is None
    assert (es.edits[2].file, es.edits[2].line, es.edits[2].paragraph) == ("cap1.tex", 7, None)


def test_empty_replace_is_a_deletion_not_missing(tmp_path):
    path = _write(tmp_path / "e.json", {"author": "help-me-write", "edits": [
        {"paragraph": 0, "find": "molto ", "replace": "", "reason": "ridondante",
         "by": "revisore"}]})
    assert load_edits(path).edits[0].replace == ""


def test_edit_without_replace_or_comment_is_an_error(tmp_path):
    path = _write(tmp_path / "e.json", {"author": "help-me-write", "edits": [
        {"paragraph": 0, "find": "testo", "reason": "niente da fare", "by": "revisore"}]})
    with pytest.raises(EditsError) as info:
        load_edits(path)
    assert any("edits[0]" in p and "replace" in p and "comment" in p
               for p in info.value.problems)


def test_load_lists_every_problem(tmp_path):
    path = _write(tmp_path / "e.json", {"author": "help-me-write", "extra": 1, "edits": [
        {"paragraph": -1, "find": "", "replace": "x", "reason": "r", "by": "revisore"},
        {"paragraph": 1, "find": "a", "replace": 5, "reason": "r", "by": "tutor"},
        {"find": "a", "comment": "c", "reason": "r", "by": "revisore"},
        {"paragraph": 2, "find": "a", "comment": "c", "by": "revisore", "replacement": "b"},
        "not an edit",
    ]})
    with pytest.raises(EditsError) as info:
        load_edits(path)
    problems = info.value.problems
    joined = "\n".join(problems)
    assert "extra" in joined
    assert any(p.startswith("edits[0]") and "paragraph" in p for p in problems)
    assert any(p.startswith("edits[0]") and "find" in p for p in problems)
    assert any(p.startswith("edits[1]") and "replace" in p for p in problems)
    assert any(p.startswith("edits[1]") and "by" in p for p in problems)
    assert any(p.startswith("edits[2]") and "paragraph" in p for p in problems)
    assert any(p.startswith("edits[3]") and "reason" in p for p in problems)
    assert any(p.startswith("edits[3]") and "replacement" in p for p in problems)
    assert any(p.startswith("edits[4]") for p in problems)


def test_text_that_cannot_go_in_a_document_is_an_error(tmp_path):
    path = tmp_path / "e.json"
    path.write_text(json.dumps({"author": "help-me-write", "edits": [
        {"paragraph": 0, "find": "a", "replace": "b\u000bc", "reason": "r", "by": "revisore"},
        {"paragraph": 0, "find": "a", "comment": "x\ud800", "reason": "r", "by": "revisore"},
    ]}), encoding="utf-8")
    with pytest.raises(EditsError) as info:
        load_edits(path)
    assert any(p.startswith("edits[0]") and "replace" in p for p in info.value.problems)
    assert any(p.startswith("edits[1]") and "comment" in p for p in info.value.problems)


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", '{"author": "x"}'])
def test_load_rejects_malformed_files(tmp_path, content):
    path = tmp_path / "e.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(EditsError):
        load_edits(path)


def test_load_missing_file(tmp_path):
    with pytest.raises(EditsError):
        load_edits(tmp_path / "missing.json")


def test_dump_and_load_roundtrip(tmp_path):
    es = EditSet("help-me-write", [
        _edit(4, "perchè", "perché"),
        _edit(5, "dato", comment="Da dove viene questo dato?", by="bibliografia"),
        Edit(None, "main.tex", 9, "teh", "the", None, "refuso", "revisore"),
    ])
    dump_edits(es, tmp_path / "out.json")
    data = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert data["edits"][0] == {"paragraph": 4, "find": "perchè", "replace": "perché",
                                "reason": "motivo", "by": "revisore"}
    assert load_edits(tmp_path / "out.json") == es


def test_merge_keeps_first_of_overlapping_finds():
    texts = {0: "Il sistema e stato installato nel 2020.", 1: "Secondo paragrafo."}
    first = EditSet("help-me-write", [_edit(0, "e stato installato", "è stato installato"),
                                      _edit(1, "Secondo", "Il secondo")])
    second = EditSet("help-me-write", [_edit(0, "installato nel", comment="Quando?",
                                             by="bibliografia"),
                                       _edit(0, "2020", comment="Fonte?", by="bibliografia")])
    merged, conflicts = merge_edits(first, second, texts=texts)
    assert merged.author == "help-me-write"
    assert [e.find for e in merged.edits] == ["e stato installato", "Secondo", "2020"]
    assert len(conflicts) == 1
    assert conflicts[0]["edit"]["find"] == "installato nel"
    assert conflicts[0]["edit"]["by"] == "bibliografia"
    assert "overlap" in conflicts[0]["reason"]


def test_merge_adjacent_spans_do_not_conflict():
    texts = {0: "abcdef"}
    merged, conflicts = merge_edits(
        EditSet("help-me-write", [_edit(0, "abc", "x")]),
        EditSet("help-me-write", [_edit(0, "def", "y")]), texts=texts)
    assert len(merged.edits) == 2 and conflicts == []


def test_merge_same_find_in_different_paragraphs_is_fine():
    texts = {0: "la parola", 1: "la parola"}
    merged, conflicts = merge_edits(
        EditSet("help-me-write", [_edit(0, "parola", "voce")]),
        EditSet("help-me-write", [_edit(1, "parola", "voce")]), texts=texts)
    assert len(merged.edits) == 2 and conflicts == []


def test_merge_unlocatable_find_is_not_a_conflict():
    texts = {0: "uno due uno"}
    merged, conflicts = merge_edits(
        EditSet("help-me-write", [_edit(0, "uno", "1"), _edit(0, "tre", "3")]),
        EditSet("help-me-write", [_edit(0, "uno due", "x")]), texts=texts)
    # "uno" is ambiguous and "tre" absent: apply reports them; "uno due" is kept
    assert [e.find for e in merged.edits] == ["uno", "tre", "uno due"]
    assert conflicts == []


def test_merge_overlap_inside_one_set_and_duplicates():
    texts = {0: "Il sistema e stato installato."}
    merged, conflicts = merge_edits(EditSet("help-me-write", [
        _edit(0, "e stato", "è stato"), _edit(0, "e stato", "è stato")]), texts=texts)
    assert len(merged.edits) == 1
    assert len(conflicts) == 1 and "duplicate" in conflicts[0]["reason"]


def test_merge_without_texts_detects_contained_finds():
    merged, conflicts = merge_edits(
        EditSet("help-me-write", [_edit(0, "e stato installato", "è stato installato")]),
        EditSet("help-me-write", [_edit(0, "stato", comment="?"), _edit(1, "stato", "x")]))
    assert [e.paragraph for e in merged.edits] == [0, 1]
    assert len(conflicts) == 1 and conflicts[0]["edit"]["paragraph"] == 0
