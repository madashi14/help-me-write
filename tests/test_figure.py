import json

import pytest

from helpmewrite import cli
from helpmewrite.figure import (FigureError, diagram_ranks, json_value, load_table,
                                render_chart, render_diagram, to_number)

PNG = b"\x89PNG\r\n\x1a\n"


def N(*ids):
    return [{"id": i, "label": i} for i in ids]


def E(*pairs):
    return [{"from": p[0], "to": p[1]} for p in pairs]


def test_chart_italian_csv(tmp_path):
    (tmp_path / "c.csv").write_bytes(
        "﻿experiment;acc\n01_raw;0,808\n03_eta;0,88\n".encode("utf-8"))
    spec = {"type": "bar", "csv": {"file": "c.csv", "x": "experiment", "y": ["acc"]}}
    prov = render_chart(spec, tmp_path, tmp_path / "g.png")
    assert [v["value"] for v in prov["values"]] == [0.808, 0.88]
    assert prov["values"][0]["file"] == "c.csv" and prov["values"][0]["where"] == "acc, row 1"
    assert (tmp_path / "g.png").read_bytes()[:8] == PNG


@pytest.mark.parametrize("text,value", [("0,808", 0.808), ("1.234,5", 1234.5),
                                        ("0.808", 0.808), (" 12 ", 12.0)])
def test_to_number(text, value):
    assert to_number(text) == value


def test_to_number_rejects_text():
    with pytest.raises(FigureError):
        to_number("abc")


def test_load_table_separators(tmp_path):
    for sep in (",", ";", "\t"):
        p = tmp_path / "t.csv"
        p.write_text(f"a{sep}b\n1{sep}2\n", encoding="utf-8")
        assert load_table(p) == [{"a": "1", "b": "2"}]


def test_chart_values_from_json_keys(tmp_path):
    (tmp_path / "m.json").write_text(
        json.dumps({"test": {"accuracy": 0.82}, "per_class": [{"f1": 0.6}]}))
    spec = {"type": "barh", "annotate": True, "language": "it", "values": [
        {"label": "Accuracy", "series": "test", "file": "m.json", "key": "test.accuracy"},
        {"label": "F1 class 0", "series": "test", "file": "m.json", "key": "per_class.0.f1"}]}
    prov = render_chart(spec, tmp_path, tmp_path / "g.svg")
    assert [v["value"] for v in prov["values"]] == [0.82, 0.6]
    assert prov["values"][1]["where"] == "per_class.0.f1"
    assert json_value(tmp_path / "m.json", "per_class.0.f1") == 0.6
    assert (tmp_path / "g.svg").read_text(encoding="utf-8").lstrip().startswith(("<?xml", "<svg"))


def test_chart_missing_key_names_file_and_key(tmp_path, capsys):
    (tmp_path / "m.json").write_text(json.dumps({"test": {}}))
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps({"type": "bar", "values": [
        {"label": "A", "series": "s", "file": "m.json", "key": "test.accuracy"}]}))
    assert cli.main(["chart", str(spec), "-o", str(tmp_path / "g.png")]) == 2
    err = capsys.readouterr().err
    assert "m.json" in err and "test.accuracy" in err and "Traceback" not in err
    assert not (tmp_path / "g.png").exists()


def test_chart_values_repeated_label_and_series_exit_2(tmp_path, capsys):
    """Ledger must-fix: the same label twice in one series would plot only the last value
    while the provenance lists both; it is refused (exit 2), nothing is written."""
    (tmp_path / "m.json").write_text(json.dumps({"a": 0.82, "b": 0.75}))
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps({"type": "bar", "values": [
        {"label": "Accuracy", "series": "test", "file": "m.json", "key": "a"},
        {"label": "Accuracy", "series": "test", "file": "m.json", "key": "b"}]}))
    assert cli.main(["chart", str(spec), "-o", str(tmp_path / "g.png")]) == 2
    err = capsys.readouterr().err
    assert "Accuracy" in err and "test" in err and "Traceback" not in err
    assert not (tmp_path / "g.png").exists() and not (tmp_path / "g.png.fonte.json").exists()
    # the same label in two series is fine
    spec.write_text(json.dumps({"type": "bar", "values": [
        {"label": "Accuracy", "series": "train", "file": "m.json", "key": "a"},
        {"label": "Accuracy", "series": "test", "file": "m.json", "key": "b"}]}))
    assert cli.main(["chart", str(spec), "-o", str(tmp_path / "g.png")]) == 0


def test_chart_cli_writes_provenance_and_refuses_existing(tmp_path, capsys):
    (tmp_path / "c.csv").write_text("x,y\na,1\nb,2\n")
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps({"type": "line", "csv": {"file": "c.csv", "x": "x", "y": ["y"]}}))
    out = tmp_path / "g.png"
    assert cli.main(["chart", str(spec), "-o", str(out)]) == 0
    prov = json.loads((tmp_path / "g.png.fonte.json").read_text(encoding="utf-8"))
    assert [v["value"] for v in prov["values"]] == [1.0, 2.0]
    capsys.readouterr()
    assert cli.main(["chart", str(spec), "-o", str(out)]) == 2
    assert "g-2.png" in capsys.readouterr().err


def test_chart_bad_spec_exit_2(tmp_path, capsys):
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps({"type": "pie"}))
    assert cli.main(["chart", str(spec), "-o", str(tmp_path / "g.png")]) == 2
    assert "Traceback" not in capsys.readouterr().err


def test_diagram_ranks_and_cycle_error():
    assert diagram_ranks({"nodes": N("a", "b", "c"),
                          "edges": E("ab", "bc", "ac")}) == {"a": 0, "b": 1, "c": 2}
    with pytest.raises(FigureError, match="a.*b"):
        diagram_ranks({"nodes": N("a", "b"), "edges": E("ab", "ba")})


def test_diagram_renders_png(tmp_path):
    spec = {"direction": "TB", "nodes": [{"id": "a", "label": "Raw data collection step"},
                                          {"id": "b", "label": "Model"}],
            "edges": [{"from": "a", "to": "b", "label": "features"}]}
    out = tmp_path / "d.png"
    render_diagram(spec, out)
    assert out.read_bytes()[:8] == PNG


def test_diagram_cli(tmp_path):
    spec = tmp_path / "d.json"
    spec.write_text(json.dumps({"direction": "LR", "nodes": N("a", "b"), "edges": E("ab")}))
    assert cli.main(["diagram", str(spec), "-o", str(tmp_path / "d.png")]) == 0
    assert (tmp_path / "d.png").is_file()


def test_chart_csv_row_longer_than_header(tmp_path, capsys):
    (tmp_path / "c.csv").write_text("a;b\nx;1,5\ny;2;9\n")
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps({"type": "bar", "csv": {"file": "c.csv", "x": "a", "y": ["b"]}}))
    assert cli.main(["chart", str(spec), "-o", str(tmp_path / "g.png")]) == 2
    err = capsys.readouterr().err
    assert "c.csv" in err and "row 2" in err and "AttributeError" not in err


@pytest.mark.parametrize("content,msg", [("a;b\n", "no data rows"), ("", "no data rows"),
                                          ("a;c\n", "column 'b'")])
def test_chart_csv_without_rows_or_columns(tmp_path, capsys, content, msg):
    (tmp_path / "c.csv").write_text(content)
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps({"type": "bar", "csv": {"file": "c.csv", "x": "a", "y": ["b"]}}))
    assert cli.main(["chart", str(spec), "-o", str(tmp_path / "g.png")]) == 2
    err = capsys.readouterr().err
    assert msg in err or "column 'a'" in err
    assert "ZeroDivisionError" not in err and "Traceback" not in err


def test_chart_sidecar_only_hint_names_image(tmp_path, capsys):
    (tmp_path / "c.csv").write_text("a,b\nx,1\n")
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps({"type": "bar", "csv": {"file": "c.csv", "x": "a", "y": ["b"]}}))
    (tmp_path / "ok.png.fonte.json").write_text("{}")
    assert cli.main(["chart", str(spec), "-o", str(tmp_path / "ok.png")]) == 2
    assert "ok-2.png" in capsys.readouterr().err
