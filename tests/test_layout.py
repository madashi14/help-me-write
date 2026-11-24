import json
import math

import pytest

from conftest import FIX
from helpmewrite import cli
from helpmewrite.fonts import AVG_CHAR_WIDTH_EM, DOCX_FONT, normalize_font
from helpmewrite.layout import Layout, LayoutError, compute_layout, load_layout
from helpmewrite.rules import Range, Rules, load_rules

UNIBO = FIX / "linee-guida-unibo.yaml"


@pytest.mark.parametrize("raw,fam", [
    ("ABCDEF+LiberationSerif-Bold", "times"), ("ArialMT", "helvetica"),
    ("TeXGyreCursor-Regular", "courier"), ("Calibri", None),
    ("TimesNewRomanPSMT", "times"), ("Times New Roman", "times"),
    ("TimesNewRoman,Italic", "times"), ("CourierNewPSMT", "courier"),
    ("NimbusRomNo9L-Regu", "times"), ("Nimbus Roman", "times"),
    ("TeXGyreTermes-Regular", "times"), ("LiberationMono", "courier"),
    ("Helvetica-Bold", "helvetica"), ("  helvetica  ", "helvetica"),
    ("Liberation Sans", "helvetica"), ("TeX Gyre Heros", "helvetica"),
    ("NimbusSanL-Regu", "helvetica"), ("Nimbus Sans", "helvetica"),
    ("Courier", "courier"), ("Nimbus Mono", "courier"),
    ("Cambria", None), ("", None),
])
def test_normalize_font(raw, fam):
    assert normalize_font(raw) == fam


def test_constants():
    assert DOCX_FONT["courier"] == "Courier New"
    assert AVG_CHAR_WIDTH_EM["courier"] == 0.60


def test_courier_layout_unibo():
    lay = compute_layout(load_rules(UNIBO), "Courier")
    assert lay.target_chars == 65 and lay.target_lines == 33
    assert lay.margins_cm["left"] == pytest.approx(2.25, abs=0.05)
    assert lay.margins_cm["left"] == lay.margins_cm["right"]
    assert lay.margins_cm["top"] == lay.margins_cm["bottom"] == 2.5
    assert lay.line_pitch_pt == pytest.approx(21.1, abs=0.1)
    assert lay.family == "courier" and lay.docx_font == "Courier New"


def test_font_not_allowed():
    with pytest.raises(LayoutError):
        compute_layout(load_rules(UNIBO), "Calibri")


def test_family_not_in_rules_fonts():
    rules = load_rules(UNIBO)
    rules.fonts = ["Times New Roman"]
    with pytest.raises(LayoutError):
        compute_layout(rules, "Courier")
    assert compute_layout(rules, "Liberation Serif").family == "times"


def test_empty_fonts_allows_any_known():
    rules = load_rules(UNIBO)
    rules.fonts = []
    assert compute_layout(rules, "Arial").family == "helvetica"


def test_half_up_rounding():
    rules = Rules(font_size_pt=12, lines_per_page=Range(30, 35), chars_per_line=Range(60, 70))
    assert compute_layout(rules, "Courier").target_lines == 33
    rules.chars_per_line = Range(60, 65)  # 62.5 -> 63
    assert compute_layout(rules, "Courier").target_chars == 63


def test_missing_font_size():
    with pytest.raises(LayoutError):
        compute_layout(Rules(), "Courier")


def test_missing_ranges_defaults():
    lay = compute_layout(Rules(font_size_pt=12), "Times")
    assert lay.line_pitch_pt is None and lay.target_chars is None
    assert lay.margins_cm == {"top": 2.5, "bottom": 2.5, "left": 2.5, "right": 2.5}


def test_text_too_wide():
    rules = Rules(font_size_pt=12, chars_per_line=Range(100, 100))
    with pytest.raises(LayoutError):
        compute_layout(rules, "Courier")


def test_json_roundtrip(tmp_path):
    lay = compute_layout(load_rules(UNIBO), "Courier")
    path = tmp_path / "layout.json"
    path.write_text(json.dumps(lay.__dict__ | {"paper_cm": list(lay.paper_cm)}), encoding="utf-8")
    assert load_layout(path) == lay
    assert isinstance(load_layout(path), Layout)


def test_layout_command(tmp_path, capsys):
    out = tmp_path / "layout.json"
    code = cli.main(["layout", "--rules", str(UNIBO), "--font", "Courier", "-o", str(out)])
    assert code == 0
    assert load_layout(out).target_chars == 65


def test_layout_command_error(capsys):
    code = cli.main(["layout", "--rules", str(UNIBO), "--font", "Calibri"])
    assert code == 2
    assert "error" in capsys.readouterr().err


def test_layout_command_bad_rules(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text("pages: 3\n", encoding="utf-8")
    assert cli.main(["layout", "--rules", str(bad), "--font", "Courier"]) == 2
