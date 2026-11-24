import pytest
from conftest import FIX

from helpmewrite import cli
from helpmewrite.rules import Range, RulesError, load_rules


def test_load_unibo_rules():
    r = load_rules(FIX / "linee-guida-unibo.yaml")
    assert r.chars_per_line == Range(60, 70) and r.lines_per_page.mid() == 32.5
    assert [s.name for s in r.sections if s.required] == [
        "frontespizio", "indice", "introduzione", "corpo", "conclusione"]
    assert r.format is None and r.page_numbers is True
    assert len(r.content_rules) == 3


def test_rules_errors_are_all_reported(tmp_path):
    (tmp_path / "x.yaml").write_text("document_type: x\nfont_size_pt: dodici\npages: {min: 30, max: 10}\n")
    with pytest.raises(RulesError) as e:
        load_rules(tmp_path / "x.yaml")
    assert len(e.value.problems) == 2


def test_range_equality_and_mid():
    assert Range(60, 70) == Range(60.0, 70.0)
    assert Range(None, 5).mid() is None
    assert Range(1, 2).mid() == 1.5


def test_many_problem_kinds(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text(
        "document_type: x\nformat: odt\nchars_per_lines: {min: 1}\n"
        "lines_per_page: {min: -1, max: 3}\npage_numbers: maybe\n"
        "sections:\n  - required: true\n  - name: a\n    headings: x\n"
    )
    with pytest.raises(RulesError) as e:
        load_rules(p)
    text = "\n".join(e.value.problems)
    for needle in ("format", "chars_per_lines", "lines_per_page", "page_numbers", "name", "headings"):
        assert needle in text


def test_not_a_mapping_and_missing_file(tmp_path):
    (tmp_path / "l.yaml").write_text("- a\n")
    with pytest.raises(RulesError):
        load_rules(tmp_path / "l.yaml")
    with pytest.raises(RulesError):
        load_rules(tmp_path / "nope.yaml")


def test_minimal_file_defaults(tmp_path):
    (tmp_path / "m.yaml").write_text("document_type: x\n")
    r = load_rules(tmp_path / "m.yaml")
    assert r.language == "it" and r.sections == [] and r.pages is None


def test_cli_validate(tmp_path, capsys):
    assert cli.main(["rules", "validate", str(FIX / "linee-guida-unibo.yaml")]) == 0
    bad = tmp_path / "b.yaml"
    bad.write_text("document_type: x\nfont_size_pt: dodici\npages: {min: 30, max: 10}\n")
    assert cli.main(["rules", "validate", str(bad)]) == 2
    out = capsys.readouterr()
    assert "font_size_pt" in out.err and "pages" in out.err


def test_cli_validate_json(capsys):
    assert cli.main(["rules", "validate", str(FIX / "linee-guida-unibo.yaml"), "--json"]) == 0
    assert '"valid": true' in capsys.readouterr().out
