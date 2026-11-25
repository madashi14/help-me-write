"""Turn guideline numbers (lines/page, chars/line, font) into margins and line spacing."""
import json
import math
import re
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
    try:
        return Layout.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise LayoutError(f"cannot read layout file {path}: {exc!r}") from exc


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


# --- applying a layout to a .docx copy -------------------------------------------------

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_HEADING_RE = re.compile(r"^(?:heading|titolo)\s*([1-3])$", re.IGNORECASE)
_PAGE_RE = re.compile(r"\bPAGE\b")


def _q(tag):
    return f"{{{_W}}}{tag}"


def _is_heading(style) -> bool:
    return bool(_HEADING_RE.match(style.name or "") or _HEADING_RE.match(style.style_id or ""))


def _set_style_font(style, font_name):
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(_q("rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(_q("rFonts"), {})
        rpr.insert(0, rfonts)
    for attr in list(rfonts.attrib):
        rfonts.attrib.pop(attr)
    for attr in ("ascii", "hAnsi", "cs", "eastAsia"):
        rfonts.set(_q(attr), font_name)


def _set_exact_spacing(style, pitch_pt):
    ppr = style.element.get_or_add_pPr()
    spacing = ppr.find(_q("spacing"))
    if spacing is None:
        spacing = ppr.get_or_add_spacing()
    spacing.set(_q("line"), str(round(pitch_pt * 20)))
    spacing.set(_q("lineRule"), "exact")


TITLE_PAGE_MAX_PARAGRAPHS = 15  # a title page has a few lines (ruling R3)
_PROTECTED_STYLE_RE = re.compile(r"^(title|subtitle|titolo|sottotitolo)$", re.IGNORECASE)


def _in_textbox(el) -> bool:
    return any(a.tag == _q("txbxContent") for a in el.iterancestors())


def _has_page_break(p) -> bool:
    return any(br.get(_q("type")) == "page" and not _in_textbox(br) for br in p.iter(_q("br"))) \
        or p.find(f"{_q('pPr')}/{_q('sectPr')}") is not None


def _title_page_paragraphs(body) -> set:
    """Paragraphs treated as title page (direct formatting kept).

    Paragraphs in text boxes (w:txbxContent, and the paragraphs hosting them), plus every
    body paragraph before the first explicit page break (w:br type=page, pageBreakBefore) or
    section break (pPr/sectPr), if that break occurs within the first
    TITLE_PAGE_MAX_PARAGRAPHS (15) paragraphs.
    """
    paragraphs = [p for p in body.iter(_q("p")) if not _in_textbox(p)]
    protected = {p for p in body.iter(_q("p")) if _in_textbox(p) or p.find(".//" + _q("txbxContent")) is not None}
    for i, p in enumerate(paragraphs[:TITLE_PAGE_MAX_PARAGRAPHS]):
        if p.find(f"{_q('pPr')}/{_q('pageBreakBefore')}") is not None:
            protected.update(paragraphs[:i])
            break
        if _has_page_break(p):
            protected.update(paragraphs[:i + 1])
            break
    return protected


def _strip_direct_overrides(body, protected) -> int:
    """Remove direct font/size/line-spacing overrides from body paragraphs (not title page)."""
    count = 0
    for p in body.iter(_q("p")):
        if p in protected:
            continue
        for rpr in p.iter(_q("rPr")):
            if rpr.getparent().tag != _q("r"):
                continue  # leave paragraph-mark properties alone
            for tag in ("rFonts", "sz", "szCs"):
                for child in rpr.findall(_q(tag)):
                    rpr.remove(child)
                    count += 1
        spacing = p.find(f"{_q('pPr')}/{_q('spacing')}")
        if spacing is not None:
            removed = False
            for attr in ("line", "lineRule"):
                if _q(attr) in spacing.attrib:
                    del spacing.attrib[_q(attr)]
                    removed = True
            count += removed
            if not spacing.attrib:
                spacing.getparent().remove(spacing)
    return count


FIRST_LINE_INDENT_CM = 1.0


def _auto_spacing_for_pictures(body) -> int:
    """Single line spacing on paragraphs holding a picture or object (w:drawing, w:pict,
    w:object): with the style's exact spacing they would be clipped to one line."""
    count = 0
    for p in body.iter(_q("p")):
        if next(p.iter(_q("drawing"), _q("pict"), _q("object")), None) is None:
            continue
        spacing = p.get_or_add_pPr().get_or_add_spacing()
        if spacing.get(_q("line")) is not None:
            continue  # the paragraph's own line spacing (kept on the title page)
        spacing.set(_q("line"), "240")
        spacing.set(_q("lineRule"), "auto")
        count += 1
    return count


def _zero_paragraph_spacing(ppr):
    """Spacing before/after 0 on a pPr (style or document defaults); line spacing untouched."""
    spacing = ppr.get_or_add_spacing()
    for attr in ("beforeAutospacing", "afterAutospacing", "beforeLines", "afterLines"):
        spacing.attrib.pop(_q(attr), None)
    spacing.set(_q("before"), "0")
    spacing.set(_q("after"), "0")


def _inherited_first_line(style):
    """First-line indent (negative = hanging) a style gets from itself or its base styles."""
    for _ in range(20):  # basedOn chains are short; guards against cycles
        if style is None:
            break
        if style.paragraph_format.first_line_indent is not None:
            return style.paragraph_format.first_line_indent
        style = style.base_style
    return 0


def _keep_unindented(body, normal_id, protected) -> int:
    """Give Normal paragraphs that must not get the new first-line indent an explicit 0.

    Title page paragraphs, table cells and centered or right-aligned paragraphs (figures)
    keep their previous look. Paragraphs with their own indent are left alone.
    """
    count = 0
    for p in body.iter(_q("p")):
        ppr = p.find(_q("pPr"))
        style = None if ppr is None else ppr.find(_q("pStyle"))
        if style is not None and style.get(_q("val")) != normal_id:
            continue
        ind = None if ppr is None else ppr.find(_q("ind"))
        if ind is not None and (_q("firstLine") in ind.attrib or _q("hanging") in ind.attrib):
            continue
        jc = None if ppr is None else ppr.find(_q("jc"))
        centered = jc is not None and jc.get(_q("val")) in ("center", "right", "end")
        in_table = any(a.tag == _q("tc") for a in p.iterancestors())
        if p in protected or in_table or centered:
            p.get_or_add_pPr().get_or_add_ind().set(_q("firstLine"), "0")
            count += 1
    return count


def _has_page_field(footer) -> bool:
    for el in footer._element.iter(_q("fldSimple"), _q("instrText")):
        if _PAGE_RE.search(el.get(_q("instr"), "") + (el.text or "")):
            return True
    return False


def _chain_reaches_first(document, index, attr) -> bool:
    """True if section index's footer of this kind is linked all the way back to section 0.

    Only used for first_page_footer: the first section's one is the title page's and stays
    unnumbered, so a later section must not inherit it.
    """
    sections = document.sections
    for k in range(index, 0, -1):
        if not getattr(sections[k], attr).is_linked_to_previous:
            return False
    return True


def _number_footers(document) -> int:
    """Give each page kind of each section a PAGE field; return how many footers changed.

    Linked footers stay linked (they inherit, text included). The first-page footer of the
    first section (the title page) is left unnumbered, so a later section's first-page
    footer linked back to it gets its own; even-page footers stay linked like the others.
    """
    sections = document.sections
    even_odd = document.settings.odd_and_even_pages_header_footer
    added = 0
    for i, section in enumerate(sections):
        kinds = ["footer"]
        if section.different_first_page_header_footer:
            kinds.append("first_page_footer")
        if even_odd:
            kinds.append("even_page_footer")
        for attr in kinds:
            if attr == "first_page_footer" and i == 0:
                continue
            footer = getattr(section, attr)
            if footer.is_linked_to_previous:
                if i > 0 and not (attr == "first_page_footer"
                                  and _chain_reaches_first(document, i, attr)):
                    continue
                footer.is_linked_to_previous = False
            if _has_page_field(footer):
                continue
            _add_page_field(footer)
            added += 1
    return added


def _add_page_field(footer):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import parse_xml

    paragraphs = footer.paragraphs
    if len(paragraphs) == 1 and not paragraphs[0].text.strip():
        paragraph = paragraphs[0]
    else:
        paragraph = footer.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph._p.append(parse_xml(
        f'<w:fldSimple xmlns:w="{_W}" w:instr=" PAGE "><w:r><w:t>1</w:t></w:r></w:fldSimple>'))


def apply_layout(src, layout: Layout, dst) -> list[str]:
    """Write a copy of src formatted per layout to dst; return readable list of changes."""
    import docx
    from docx.shared import Cm, Pt

    from .cli import same_file

    src, dst = Path(src), Path(dst)
    if same_file(src, dst):
        raise ValueError(f"destination would overwrite the original: {src}")
    document = docx.Document(str(src))
    changes = []

    m = layout.margins_cm
    for section in document.sections:
        section.page_width, section.page_height = Cm(layout.paper_cm[0]), Cm(layout.paper_cm[1])
        section.top_margin, section.bottom_margin = Cm(m["top"]), Cm(m["bottom"])
        section.left_margin, section.right_margin = Cm(m["left"]), Cm(m["right"])
    changes.append(
        f"page {layout.paper_cm[0]:g}x{layout.paper_cm[1]:g} cm, margins cm: top {m['top']}, "
        f"bottom {m['bottom']}, left {m['left']}, right {m['right']} "
        f"({len(document.sections)} section(s))")

    def is_normal(style):
        return style.style_id == "Normal" or (style.name or "").lower() == "normal"

    paragraph_styles = [s for s in document.styles
                        if s.type == docx.enum.style.WD_STYLE_TYPE.PARAGRAPH]
    normal = next((s for s in paragraph_styles if is_normal(s)), None)
    # Only Normal paragraphs get the new first-line indent: other styles keep the one they had.
    kept_indent = [(s, _inherited_first_line(s)) for s in paragraph_styles
                   if not is_normal(s) and s.paragraph_format.first_line_indent is None]

    styled = []
    for style in paragraph_styles:
        if _PROTECTED_STYLE_RE.match(style.name or ""):
            continue
        if is_normal(style):
            _set_style_font(style, layout.docx_font)
            style.font.size = Pt(layout.font_size_pt)
            styled.append(style.name)
        elif _is_heading(style):
            _set_style_font(style, layout.docx_font)
            styled.append(style.name)
        else:  # inherit font and size from Normal
            if style.base_style is None:
                style.base_style = document.styles["Normal"]
            rpr = style.element.rPr
            if rpr is not None:
                for tag in ("rFonts", "sz", "szCs"):
                    for child in rpr.findall(_q(tag)):
                        rpr.remove(child)
        if layout.line_pitch_pt is not None:
            _set_exact_spacing(style, layout.line_pitch_pt)
    changes.append(f"font {layout.docx_font} on styles: {', '.join(styled)}; "
                   f"Normal size {layout.font_size_pt:g} pt")
    if layout.line_pitch_pt is not None:
        changes.append(f"exact line spacing {layout.line_pitch_pt} pt on all paragraph styles except Title/Subtitle")

    body = document.element.body
    protected = _title_page_paragraphs(body)
    if normal is not None:
        defaults = document.styles.element.find(
            f"{_q('docDefaults')}/{_q('pPrDefault')}/{_q('pPr')}")
        _zero_paragraph_spacing(normal.element.get_or_add_pPr())
        if defaults is not None:
            _zero_paragraph_spacing(defaults)
        changes.append("paragraph spacing before/after 0 pt on Normal"
                       + (" and the document defaults" if defaults is not None else ""))
        normal.paragraph_format.first_line_indent = Cm(FIRST_LINE_INDENT_CM)
        for style, indent in kept_indent:
            style.paragraph_format.first_line_indent = indent
        unindented = _keep_unindented(body, normal.style_id, protected)
        changes.append(f"first-line indent {FIRST_LINE_INDENT_CM:g} cm on Normal (other styles keep "
                       f"their indent; {unindented} title-page, table or centered paragraph(s) "
                       "kept unindented)")

    removed = _strip_direct_overrides(body, protected)
    if removed:
        changes.append(f"removed {removed} direct font/size/line-spacing override(s) from the body")
    pictures = _auto_spacing_for_pictures(body)
    if pictures:
        changes.append(f"single line spacing on {pictures} paragraph(s) holding a picture or "
                       "object (exact spacing would clip them)")

    added = _number_footers(document)
    if added:
        changes.append(f"added a centered page number to {added} footer(s)")

    document.save(str(dst))
    return changes


def add_format_arguments(parser):
    parser.add_argument("input", help="the .docx to format (never modified)")
    parser.add_argument("--layout", required=True, help="layout.json from the layout command")
    parser.add_argument("-o", "--output", required=True, help="formatted .docx to write")


def run_format(args) -> int:
    from . import cli

    if cli.refuses_overwrite(args.input, args):
        return 2
    if cli.refuses_existing_output(args.output):
        return 2
    try:
        layout = load_layout(args.layout)
        changes = apply_layout(args.input, layout, args.output)
    except LayoutError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # unreadable/not a docx, unwritable destination
        print(f"error: cannot format {args.input}: {exc!r}", file=sys.stderr)
        return 2
    cli.emit({"output": str(args.output), "changes": changes}, _no_json_file(args),
             text="\n".join([f"wrote {args.output}"] + [f"- {c}" for c in changes]))
    return 0


class _no_json_file:
    """View of args for emit(): -o is the document here, so never treat it as a JSON path."""

    def __init__(self, args):
        self.json = getattr(args, "json", False)
        self.output = None
