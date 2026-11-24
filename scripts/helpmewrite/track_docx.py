"""Apply an EditSet to a copy of a .docx as Word revisions (w:del + w:ins) and comments.

Every edit is checked before its paragraph is touched: one that cannot be applied safely
(text not found or ambiguous, inside a hyperlink or field, on someone else's revision, or
spanning content that is not plain text) goes to `failed` and changes nothing. After the
edits of a paragraph, the paragraph is verified: its visible text must be the corrected
text and rejecting our revisions must give back the original text. If not, the paragraph
is restored and its edits are reported as failed.
"""
import copy
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from lxml import etree

from .edits import EditSet, locate
from .extract import W, iter_body_paragraphs, visible_text

INITIALS = "HMW"
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def _w(tag):
    return f"{{{W}}}{tag}"


_P, _R, _T, _TAB, _BR, _RPR = _w("p"), _w("r"), _w("t"), _w("tab"), _w("br"), _w("rPr")
_INS, _DEL, _DELTEXT = _w("ins"), _w("del"), _w("delText")
_ID, _AUTHOR, _DATE = _w("id"), _w("author"), _w("date")
_FLDCHAR = _w("fldChar")
_INSTR = (_w("instrText"), _w("delInstrText"))

# containers whose runs extract.visible_text reads
_TEXT_CONTAINERS = {_INS, _w("hyperlink"), _w("smartTag"), _w("sdt"), _w("sdtContent")}
# run children a matched run may have: anything else is content the text does not show
_PLAIN_RUN = {_RPR, _T, _TAB, _BR, _w("lastRenderedPageBreak")}
# children of a textless run that may sit inside a match without being displaced
_NEUTRAL_RUN = {_RPR, _w("lastRenderedPageBreak"), _w("commentReference")}
_DYNAMIC = {_w("hyperlink"), _w("fldSimple"), _w("sdt")}
_REVISIONS = {_INS, _DEL, _w("moveTo"), _w("moveFrom")}
_DELETED = {_DEL, _w("moveFrom")}
# elements that may lie between the matched runs: left in place (their runs are checked)
_LEAVE = _DELETED | {_w(t) for t in (
    "ins", "moveTo", "smartTag", "smartTagPr", "bookmarkStart", "bookmarkEnd", "proofErr",
    "commentRangeStart", "commentRangeEnd", "permStart", "permEnd", "moveFromRangeStart",
    "moveFromRangeEnd", "moveToRangeStart", "moveToRangeEnd")}
_SKIP_INSIDE = {_R, _w("smartTagPr")} | _DELETED
_ALL_IDS = etree.XPath("//@w:id", namespaces={"w": W})


@dataclass
class ApplyResult:
    applied: list[int] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)  # {"index", "reason"}


class _Refused(Exception):
    """The edit cannot be applied safely; the message is the reason reported."""


@dataclass
class _Anchor:
    """Where a comment goes: around outer_first..outer_last, the runs given to python-docx."""
    paragraph: object
    outer_first: object
    outer_last: object
    first_run: object
    last_run: object


class _Context:
    def __init__(self, document, author, date):
        self.document = document
        self.author = author
        self.when = _utc(date)
        self.stamp = self.when.strftime("%Y-%m-%dT%H:%M:%SZ")
        self._next_id = _max_id(document) + 1
        self.field_depth = _field_depths(document.element.body)

    def revision(self, tag, ours):
        el = etree.Element(tag)
        el.set(_ID, str(self._next_id))
        el.set(_AUTHOR, self.author)
        el.set(_DATE, self.stamp)
        ours.add(str(self._next_id))
        self._next_id += 1
        return el


def apply_edits_docx(src: Path, edits: EditSet, dst: Path,
                     date: datetime | None = None) -> ApplyResult:
    """Write dst, a copy of src with the edits as revisions by edits.author.

    date (default now) is used for every revision and comment; naive means UTC.
    """
    import docx

    src, dst = Path(src), Path(dst)
    if dst.resolve() == src.resolve():
        raise ValueError(f"output would overwrite the original: {src}")
    document = docx.Document(str(src))
    paragraphs = iter_body_paragraphs(document)
    ctx = _Context(document, edits.author, date)
    result = ApplyResult()
    located = {}
    for index, edit in enumerate(edits.edits):
        if edit.paragraph is None:
            result.failed.append({"index": index, "reason": "edit has no paragraph id"})
        elif not 0 <= edit.paragraph < len(paragraphs):
            result.failed.append({"index": index, "reason": "no such paragraph"})
        else:
            span = locate(visible_text(paragraphs[edit.paragraph]), edit.find)
            if isinstance(span, str):
                result.failed.append({"index": index, "reason": span})
            else:
                located.setdefault(edit.paragraph, []).append((index, edit, span))
    for pid, items in located.items():
        _apply_paragraph(paragraphs[pid], items, ctx, result)
    document.save(str(dst))
    result.applied.sort()
    result.failed.sort(key=lambda f: f["index"])
    return result


def _apply_paragraph(p, items, ctx, result):
    original = visible_text(p)
    chosen = []
    for index, edit, span in items:  # first edit wins, as in merge_edits
        if any(span[0] < s[1] and s[0] < span[1] for _, _, s in chosen):
            result.failed.append({"index": index, "reason": "overlaps another edit"})
        else:
            chosen.append((index, edit, span))
    snapshot = copy.deepcopy(p)
    ours, done, expected = set(), [], original
    # right to left: the offsets of the edits still to apply stay valid
    for index, edit, span in sorted(chosen, key=lambda c: c[2][0], reverse=True):
        try:
            anchor = _apply_edit(p, span, edit, ctx, ours)
        except _Refused as exc:
            result.failed.append({"index": index, "reason": str(exc)})
            continue
        done.append((index, edit, anchor))
        if edit.replace is not None:
            expected = expected[:span[0]] + edit.replace + expected[span[1]:]
    if done and (visible_text(p) != expected or _rejected_text(p, ours) != original):
        p.getparent().replace(p, snapshot)
        for index, _, _ in done:
            result.failed.append({"index": index,
                                  "reason": "internal check failed; paragraph left unchanged"})
        return
    for index, edit, anchor in sorted(done, key=lambda d: d[0]):
        if edit.comment is not None:
            _add_comment(ctx, anchor, edit.comment)
        result.applied.append(index)


def _apply_edit(p, span, edit, ctx, ours) -> _Anchor:
    start, end = span
    runs = _text_runs(p)
    if "".join(text for _, _, text in runs) != visible_text(p):
        raise _Refused("unsupported content")
    touched = [(r, off, text) for r, off, text in runs if off < end and off + len(text) > start]
    in_field = _field_runs(p, ctx.field_depth.get(p, 0))
    for r, _, _ in touched:
        _check_matched_run(r, p, in_field)
    _check_span(p, touched[0][0], touched[-1][0], {r for r, _, _ in touched}, in_field)

    pieces = [r for r, _, _ in touched]
    last_offset = touched[-1][1]
    cut = start - touched[0][1]
    if cut > 0:
        pieces[0] = _split(pieces[0], cut)
        if len(pieces) == 1:
            last_offset = start
    cut = end - last_offset
    if cut < _run_length(pieces[-1]):
        _split(pieces[-1], cut)

    if edit.replace is None:
        return _Anchor(p, pieces[0], pieces[-1], pieces[0], pieces[-1])
    groups = []
    for r in pieces:
        for t in r.findall(_T):
            t.tag = _DELTEXT
            t.set(_XML_SPACE, "preserve")
        if groups and r.getprevious() is groups[-1]:
            groups[-1].append(r)
        else:
            deletion = ctx.revision(_DEL, ours)
            r.addprevious(deletion)
            deletion.append(r)
            groups.append(deletion)
    outer_last, last_run = groups[-1], pieces[-1]
    if edit.replace:
        insertion = ctx.revision(_INS, ours)
        last_run = _text_run(edit.replace, pieces[0].find(_RPR))
        insertion.append(last_run)
        groups[-1].addnext(insertion)
        outer_last = insertion
    return _Anchor(p, groups[0], outer_last, pieces[0], last_run)


# --- reading the paragraph -------------------------------------------------------------


def _child_text(el) -> str:
    if el.tag == _T:
        return el.text or ""
    return {_TAB: "\t", _BR: "\n"}.get(el.tag, "")


def _run_length(run) -> int:
    return sum(len(_child_text(el)) for el in run)


def _text_runs(p) -> list:
    """(run, offset, text) for every run, read exactly as extract.visible_text reads them."""
    out, pos = [], 0

    def walk(node):
        nonlocal pos
        for child in node:
            if child.tag == _R:
                text = "".join(_child_text(el) for el in child)
                out.append((child, pos, text))
                pos += len(text)
            elif child.tag in _TEXT_CONTAINERS:
                walk(child)

    walk(p)
    return out


def _field_depths(body) -> dict:
    """Number of complex fields open where each paragraph starts (fields can span them)."""
    depths, depth = {}, 0
    for el in body.iter(_P, _FLDCHAR):
        if el.tag == _P:
            depths[el] = depth
        else:
            depth = _next_depth(el, depth)
    return depths


def _next_depth(fld_char, depth) -> int:
    kind = fld_char.get(_w("fldCharType"))
    if kind == "begin":
        return depth + 1
    if kind == "end":
        return max(depth - 1, 0)
    return depth


def _field_runs(p, depth) -> set:
    """Runs of p belonging to a complex field: its instruction, result and markers."""
    inside = set()
    for el in p.iter(_R, _FLDCHAR, *_INSTR):
        if el.tag == _R:
            if depth > 0:
                inside.add(el)
        else:
            inside.add(el.getparent())
            if el.tag == _FLDCHAR:
                depth = _next_depth(el, depth)
    return inside


def _inside(el, p, tags) -> str | None:
    """Tag of the nearest ancestor of el (below p) whose tag is in tags."""
    for ancestor in el.iterancestors():
        if ancestor is p:
            return None
        if ancestor.tag in tags:
            return ancestor.tag
    return None


def _check_matched_run(r, p, in_field):
    if _inside(r, p, _DYNAMIC) or r in in_field:
        raise _Refused("hyperlink/field")
    if _inside(r, p, _REVISIONS):
        raise _Refused("existing revision")
    if any(child.tag not in _PLAIN_RUN for child in r):
        raise _Refused("unsupported content")
    rpr = r.find(_RPR)
    if rpr is not None and rpr.find(_w("rPrChange")) is not None:
        raise _Refused("existing revision")


def _check_span(p, first, last, matched, in_field):
    """Everything between the first and last matched run must be safe to leave in place."""
    active = False
    for el in p.iter():
        if el is first:
            active = True
        if not active or _inside(el, p, _SKIP_INSIDE):
            continue
        if el.tag == _R:
            if el in matched:
                pass
            elif el in in_field:
                raise _Refused("hyperlink/field")
            elif not all(c.tag in _NEUTRAL_RUN or (c.tag == _T and not c.text) for c in el):
                if _inside(el, p, _REVISIONS):
                    raise _Refused("existing revision")
                raise _Refused("unsupported content")
        elif el.tag in _DYNAMIC:
            raise _Refused("hyperlink/field")
        elif el.tag not in _LEAVE:
            raise _Refused("unsupported content")
        if el is last:
            return


def _rejected_text(p, ours) -> str:
    """Visible text of p with our revisions rejected: our w:ins dropped, our w:del read."""
    out = []

    def walk(node, deleted):
        for child in node:
            if child.tag == _R:
                for el in child:
                    out.append((el.text or "") if deleted and el.tag == _DELTEXT
                               else _child_text(el))
            elif child.tag in (_INS, _DEL) and child.get(_ID) in ours:
                if child.tag == _DEL:
                    walk(child, True)
            elif child.tag in _TEXT_CONTAINERS:
                walk(child, deleted)

    walk(p, False)
    return "".join(out)


# --- changing the paragraph ------------------------------------------------------------


def _split(run, k):
    """Cut run at visible offset k: run keeps [0, k); the rest becomes a new run after it."""
    right = copy.deepcopy(run)
    _trim(run, 0, k)
    _trim(right, k, None)
    run.addnext(right)
    return right


def _trim(run, a, b):
    """Keep only the text of run in [a, b) (b None: to the end); rPr is always kept."""
    pos = 0
    for child in list(run):
        if child.tag == _RPR:
            continue
        n = len(_child_text(child))
        lo, hi = max(pos, a), pos + n if b is None else min(pos + n, b)
        keep = (a <= pos and (b is None or pos < b)) if n == 0 else lo < hi
        if not keep:
            run.remove(child)
        elif child.tag == _T and (lo, hi) != (pos, pos + n):
            child.text = child.text[lo - pos:hi - pos]
            child.set(_XML_SPACE, "preserve")
        pos += n


def _text_run(text, rpr):
    """A new run with rpr (copied) and text; tabs and line breaks become w:tab and w:br."""
    from docx.oxml.parser import OxmlElement

    run = OxmlElement("w:r")
    if rpr is not None:
        run.append(copy.deepcopy(rpr))
    for part in re.split(r"(\t|\n)", text):
        if part == "\t":
            etree.SubElement(run, _TAB)
        elif part == "\n":
            etree.SubElement(run, _BR)
        elif part:
            t = etree.SubElement(run, _T)
            t.text = part
            t.set(_XML_SPACE, "preserve")
    return run


def _add_comment(ctx, anchor, text):
    """Comment through python-docx, then move its markers to the paragraph level."""
    from docx.text.run import Run

    comment = ctx.document.add_comment(
        [Run(anchor.first_run, ctx.document), Run(anchor.last_run, ctx.document)],
        text=text, author=ctx.author, initials=INITIALS)
    comment._comment_elm.date = ctx.when  # python-docx 1.2 has no public date setter
    cid = str(comment.comment_id)

    def marker(tag):
        return next(el for el in anchor.paragraph.iter(_w(tag)) if el.get(_ID) == cid)

    start, end = marker("commentRangeStart"), marker("commentRangeEnd")
    reference_run = marker("commentReference").getparent()
    # python-docx puts them next to the runs, i.e. inside our w:del / w:ins
    anchor.outer_first.addprevious(start)
    anchor.outer_last.addnext(reference_run)
    anchor.outer_last.addnext(end)


# --- document-wide values --------------------------------------------------------------


def _utc(date) -> datetime:
    if date is None:
        date = datetime.now(timezone.utc)
    elif date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return date.astimezone(timezone.utc).replace(microsecond=0)


def _max_id(document) -> int:
    """Highest w:id in any WordprocessingML part (revisions, comments, bookmarks...)."""
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    highest = 0
    for part in document.part.package.iter_parts():
        if "wordprocessingml" not in part.content_type:
            continue
        root = getattr(part, "element", None)
        if root is None:
            root = etree.fromstring(part.blob, parser)
        for value in _ALL_IDS(root):
            if value.lstrip("-").isdigit():
                highest = max(highest, int(value))
    return highest
