"""Fill the title-page model of the guidelines (a .docx whose page is built from text boxes).

The model is edited, not recreated: everything before `start_at` is dropped and placeholder
texts are replaced everywhere, in the body and in text boxes, in both copies Word stores
(mc:Choice and mc:Fallback).
"""
import json
import re
import sys
import zipfile
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
_P, _R, _T, _BR = (f"{{{W}}}{n}" for n in ("p", "r", "t", "br"))
_SECT = f"{{{W}}}sectPr"
_RUN_PARENTS = {f"{{{W}}}{n}" for n in ("ins", "hyperlink", "smartTag", "sdtContent")}


class TitlePageError(Exception):
    """Unusable template or values."""


def _own_texts(p) -> list:
    """The w:t elements of the runs of p itself (not those of nested text-box paragraphs)."""
    out = []

    def walk(node):
        for child in node:
            if child.tag == _R:
                out.extend(t for t in child if t.tag == _T)
            elif child.tag in _RUN_PARENTS:
                walk(child)

    walk(p)
    return out


def _find_spans(text: str, find: str):
    """(start, end) of every non-overlapping occurrence; exact first, then spaces collapsed."""
    spans, pos = [], 0
    while find and (i := text.find(find, pos)) >= 0:
        spans.append((i, i + len(find)))
        pos = i + len(find)
    if spans:
        return spans
    needle = re.sub(r"\s+", " ", find).strip()
    if not needle:
        return []
    norm, index, prev_space = [], [], False
    for i, ch in enumerate(text):
        if ch.isspace():
            if prev_space:
                continue
            ch, prev_space = " ", True
        else:
            prev_space = False
        norm.append(ch)
        index.append(i)
    norm = "".join(norm)
    pos = 0
    while (i := norm.find(needle, pos)) >= 0:
        j = i + len(needle)
        spans.append((index[i], index[j - 1] + 1))
        pos = j
    return spans


def _replace_in_paragraph(p, find: str, new: str) -> int:
    ts = _own_texts(p)
    texts = [t.text or "" for t in ts]
    spans = _find_spans("".join(texts), find)
    if not spans:
        return 0
    starts, acc = [], 0
    for s in texts:
        starts.append(acc)
        acc += len(s)
    for a, b in reversed(spans):  # from the end, so earlier offsets stay valid
        first = True
        for k, s in enumerate(texts):
            lo, hi = starts[k], starts[k] + len(s)
            if hi <= a or lo >= b:
                continue
            ca, cb = max(a, lo) - lo, min(b, hi) - lo
            texts[k] = s[:ca] + (new if first else "") + s[cb:]
            first = False
    for t, s in zip(ts, texts):
        if s != (t.text or ""):
            t.text = s
            t.set(f"{{{XML_NS}}}space", "preserve")
    return len(spans)


def _drop_page_break(element) -> None:
    """Remove a page break at the very start of element (before any text)."""
    for ppr in element.iter(f"{{{W}}}pageBreakBefore"):
        ppr.getparent().remove(ppr)
        break
    for node in element.iter():
        if node.tag == _T and (node.text or ""):
            return
        if node.tag == _BR and node.get(f"{{{W}}}type") == "page":
            r = node.getparent()
            r.remove(node)
            if not len(r):
                r.getparent().remove(r)
            return


def fill_title_page(template: Path, replacements: list, out: Path,
                    start_at: str | None = None) -> dict:
    """Write a copy of the template with the title page filled in; see the module docstring."""
    template, out = Path(template), Path(out)
    with zipfile.ZipFile(template) as zin:
        try:
            root = etree.fromstring(zin.read("word/document.xml"))
        except KeyError:
            raise TitlePageError(f"{template} is not a .docx (no word/document.xml)") from None
        body = root.find(f"{{{W}}}body")
        removed = 0
        if start_at:
            target = next((c for c in body if c.tag != _SECT
                           and start_at in "".join(c.itertext())), None)
            if target is None:
                raise TitlePageError(f"start_at text not found: {start_at!r}")
            for child in list(body):
                if child is target:
                    break
                if child.tag != _SECT:
                    body.remove(child)
                    removed += 1
            _drop_page_break(target)
        replaced = {}
        for find, new in replacements:
            replaced[find] = sum(_replace_in_paragraph(p, find, new) for p in list(body.iter(_P)))
        data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                zout.writestr(item, data if item.filename == "word/document.xml"
                              else zin.read(item.filename))
    return {"replaced": replaced,
            "not_found": [f for f, n in replaced.items() if n == 0],
            "removed_elements": removed}


def _load_values(path) -> tuple:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise TitlePageError(f"cannot read {path}: {exc}") from None
    items = data.get("replace") if isinstance(data, dict) else None
    start_at = data.get("start_at") if isinstance(data, dict) else None
    if not isinstance(items, list) or not (start_at is None or isinstance(start_at, str)):
        raise TitlePageError('values must be {"start_at": "...", "replace": '
                             '[{"find": "...", "with": "..."}]}')
    pairs = []
    for i, item in enumerate(items):
        if not (isinstance(item, dict) and isinstance(item.get("find"), str)
                and item["find"] and isinstance(item.get("with"), str)):
            raise TitlePageError(f'replace[{i}] needs string "find" (not empty) and "with"')
        pairs.append((item["find"], item["with"]))
    return pairs, start_at


def add_arguments(parser):
    parser.add_argument("template", help="the title-page model .docx (never modified)")
    parser.add_argument("--values", required=True,
                        help='JSON: {"start_at": "...", "replace": [{"find": "...", "with": "..."}]}')
    parser.add_argument("-o", "--output", required=True, help="new .docx to write")


def run(args) -> int:
    from . import cli

    if cli.refuses_existing_output(args.output, sources=[args.template]):
        return 2
    try:
        pairs, start_at = _load_values(args.values)
        result = fill_title_page(Path(args.template), pairs, Path(args.output), start_at)
    except TitlePageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (OSError, zipfile.BadZipFile) as exc:
        print(f"error: cannot fill {args.template}: {exc}", file=sys.stderr)
        return 2
    result = {"output": str(args.output), **result}
    lines = [f"wrote {args.output} ({result['removed_elements']} elements removed)"]
    lines += [f"- {n}x {f}" for f, n in result["replaced"].items() if n]
    lines += [f"not found: {f}" for f in result["not_found"]]

    class _View:  # -o is the document here, never a JSON path
        json = getattr(args, "json", False)
        output = None

    cli.emit(result, _View, text="\n".join(lines))
    return 1 if result["not_found"] else 0
