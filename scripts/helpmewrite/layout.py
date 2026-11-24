"""Turn guideline numbers (lines/page, chars/line, font) into margins and line spacing."""
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from .fonts import AVG_CHAR_WIDTH_EM, DOCX_FONT, normalize_font

PT_PER_CM = 72 / 2.54
MIN_SIDE_MARGIN_CM = 1.0
DEFAULT_MARGIN_CM = 2.5


class LayoutError(Exception):
    pass


@dataclass
class Layout:
    family: str
    docx_font: str
    font_size_pt: float
    paper_cm: tuple
    margins_cm: dict
    line_pitch_pt: float | None = None
    target_chars: int | None = None
    target_lines: int | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Layout":
        data = dict(data)
        data["paper_cm"] = tuple(data["paper_cm"])
        return cls(**data)


def _round_half_up(value: float, digits: int = 0) -> float:
    factor = 10 ** digits
    result = math.floor(value * factor + 0.5 + 1e-9) / factor
    return int(result) if digits == 0 else result


def _mid(rng):
    return rng.mid() if rng is not None else None


def compute_layout(rules, font: str, paper_cm=(21.0, 29.7), vertical_margin_cm=2.5) -> Layout:
    family = normalize_font(font)
    if family is None:
        raise LayoutError(f"unknown font family: {font!r} (use Times, Helvetica/Arial or Courier)")
    if rules.fonts:
        allowed = {normalize_font(f) for f in rules.fonts}
        if family not in allowed:
            raise LayoutError(f"font {font!r} is not allowed by the guidelines: {', '.join(rules.fonts)}")
    if rules.font_size_pt is None:
        raise LayoutError("the guidelines do not specify font_size_pt; cannot compute a layout")
    size = rules.font_size_pt

    side = DEFAULT_MARGIN_CM
    target_chars = None
    chars_mid = _mid(rules.chars_per_line)
    if chars_mid is not None:
        target_chars = _round_half_up(chars_mid)
        text_cm = target_chars * AVG_CHAR_WIDTH_EM[family] * size / PT_PER_CM
        side = _round_half_up((paper_cm[0] - text_cm) / 2, 2)
        if side < MIN_SIDE_MARGIN_CM:
            raise LayoutError(
                f"{target_chars} characters per line in {font} {size:g} pt need {text_cm:.1f} cm, "
                f"leaving margins of {side:.2f} cm on a {paper_cm[0]:g} cm wide page (minimum "
                f"{MIN_SIDE_MARGIN_CM:g} cm)")

    target_lines = pitch = None
    lines_mid = _mid(rules.lines_per_page)
    if lines_mid is not None:
        target_lines = _round_half_up(lines_mid)
        if target_lines < 1:
            raise LayoutError("lines_per_page must be at least 1")
        height_pt = (paper_cm[1] - 2 * vertical_margin_cm) * PT_PER_CM
        pitch = _round_half_up(height_pt / target_lines * 0.995, 1)

    return Layout(
        family=family, docx_font=DOCX_FONT[family], font_size_pt=size,
        paper_cm=tuple(paper_cm),
        margins_cm={"top": vertical_margin_cm, "bottom": vertical_margin_cm,
                    "left": side, "right": side},
        line_pitch_pt=pitch, target_chars=target_chars, target_lines=target_lines)


def load_layout(path) -> Layout:
    return Layout.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def add_arguments(parser):
    parser.add_argument("--rules", required=True, help="linee-guida.yaml")
    parser.add_argument("--font", required=True, help="font name, e.g. Courier")


def run(args) -> int:
    from . import cli
    from .rules import RulesError, load_rules

    try:
        rules = load_rules(args.rules)
        layout = compute_layout(rules, args.font)
    except RulesError as exc:
        for problem in exc.problems:
            print(f"error: {problem}", file=sys.stderr)
        return 2
    except LayoutError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    m = layout.margins_cm
    pitch = f"{layout.line_pitch_pt} pt" if layout.line_pitch_pt is not None else "unchanged"
    text = (f"{layout.docx_font} {layout.font_size_pt:g} pt; margins cm: top {m['top']}, "
            f"bottom {m['bottom']}, left {m['left']}, right {m['right']}; line pitch {pitch}")
    cli.emit(asdict(layout), args, text=text)
    return 0
