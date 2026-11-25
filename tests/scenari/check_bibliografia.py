"""Set up and check the bibliography scenario (tests/scenari/bibliografia.md). Needs no pytest.

    python tests/scenari/check_bibliografia.py --setup <folder> <expected.json> <plugin>
        writes bozza-bib.docx and fonti/ (tests/fixtures/builders.py: build_bib_draft) and
        .help-me-write/linee-guida.yaml (the Unibo fixture) in <folder>, the expected
        results to <expected.json>, and a copy of the plugin without tests/, docs/ and the
        repository's history to <plugin> (as check_revisione.py does). <expected.json> and
        <plugin> must be outside <folder>.

    python tests/scenari/check_bibliografia.py <folder> <expected.json> [--combined]
        checks <folder> after the review; prints one line per check and exits 1 if any
        check fails. --combined: the review was run by the `revisione` skill, so its own
        files must be there too.

Every defect needs evidence specific to it in note-bibliografia.md, never a word that any
note contains:
- wrong_claim: a row of the table whose first cell names [1], with the verdict not (or
  partially) supported, the source's words quoted verbatim and the page;
- invented_entry: what the note says about [3] (its table row, or the text after "[3]" on
  a line, up to another key) says not found, possibly invented or not verifiable;
- wrong_year: what the note says about [2] has both years (not inside a file name), and
  the entry gets a tracked change from one to the other;
- missing_citation: an item of "## Missing citations" has the statement's number;
- missing_entry: a clause of "## Bibliography consistency" names [4] as missing.
A keyword right after a negation ("non inventata", "nessuna mancante") does not count.
"""
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

from check_revisione import REPO, prepare, section  # also puts tests/ and scripts/ on sys.path

BIB_FILES = ["bib.json", "edits-bibliografia.json", "note-bibliografia.md", "rapporto.md"]
REVISIONE_FILES = ["extract.json", "measure.json", "edits-revisore.json", "note-revisore.md",
                   "edits.json"]
NOTE_HEADINGS = ["## Citations", "## Missing citations", "## Bibliography consistency"]
REPORT_SECTION = ["bibliografia", "bibliography"]
KEY = re.compile(r"\[\d+\]")
PAGE = r"(?:\bp|\bpp|\bpag|\bpagina|\bpage|\bpg)\.?\s*{n}(?!\d)"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def setup(folder: Path, expected_path: Path, plugin: Path) -> int:
    import shutil

    from fixtures.builders import build_bib_draft

    folder, expected_path, plugin = folder.resolve(), expected_path.resolve(), plugin.resolve()
    if not prepare(folder, expected_path, plugin):
        return 2
    expected = build_bib_draft(folder)
    state = folder / ".help-me-write"
    state.mkdir(exist_ok=True)
    shutil.copyfile(REPO / "tests" / "fixtures" / "linee-guida-unibo.yaml",
                    state / "linee-guida.yaml")
    expected_path.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    print(f"wrote {folder / expected['document']}, {folder / 'fonti'}, "
          f"{state / 'linee-guida.yaml'}, {expected_path}, plugin copy {plugin}")
    return 0


def norm(text: str) -> str:
    """Casefolded, one space between words, no space before %, plain quotes."""
    text = text.replace(" ", " ").replace("’", "'").casefold()
    text = " ".join(text.split())
    return re.sub(r"\s+%", "%", text)


def word(text: str, token: str) -> bool:
    """token occurs not glued to letters, digits, dots or underscores (not in 'x2020.pdf')."""
    return re.search(rf"(?<![\w.]){re.escape(token)}(?![\w])(?!\.\w)", text) is not None


def _cells(line: str):
    if not line.lstrip().startswith("|"):
        return None
    return [c.strip() for c in line.strip().strip("|").split("|")]


def rows_of(note: str, key: str) -> list[str]:
    """Table rows whose first cell names key."""
    return [line for line in note.splitlines()
            if (cells := _cells(line)) and key in cells[0]]


def about(note: str, key: str) -> list[str]:
    """What the note says about key: its table rows, and on other lines the text from key
    up to the next other key."""
    out = rows_of(note, key)
    for line in note.splitlines():
        if _cells(line) is not None:
            continue
        for m in re.finditer(re.escape(key), line):
            rest = line[m.end():]
            other = next((k for k in KEY.finditer(rest) if k.group(0) != key), None)
            out.append(key + (rest[:other.start()] if other else rest))
    return out


# a keyword right after a negation does not count: "non inventata", "nessuna mancante"
_NEGATED = re.compile(r"(?:\bnon|\bnot|\bno|\bnessun\w*|\bnone|\bnever|\bmai)\s+"
                      r"(?:(?:è|e|is|was|be|stat[ao]|been)\s+)*$")


def keyword(text: str, keywords):
    """The first keyword found in text, not negated."""
    low = norm(text)
    for k in keywords:
        for m in re.finditer(re.escape(k), low):
            if not _NEGATED.search(low[max(0, m.start() - 24):m.start()]):
                return k
    return None


def any_hit(texts, keywords):
    for text in texts:
        hit = keyword(text, keywords)
        if hit:
            return hit, text
    return None, None


def clauses_naming(text: str, key: str) -> list[str]:
    """Clauses (split at ; and at the end of sentences) that name key on its own, not as
    the end of a range such as [1]–[4]."""
    alone = re.compile(rf"(?<![–\-])(?<![–\-]\s){re.escape(key)}")
    return [c for line in text.splitlines() for c in re.split(r";|\.\s", line)
            if alone.search(c)]


def personal_spans(paragraphs, sentences):
    """{paragraph id: [(start, end)]} of the personal sentences in the original."""
    spans = {}
    for p in paragraphs:
        for s in sentences:
            start = p["text"].find(s)
            if start >= 0:
                spans.setdefault(p["id"], []).append((start, start + len(s)))
    return spans


def edits_in_personal(edits, paragraphs, sentences):
    """Edits whose find falls (even partly) in a personal sentence."""
    spans = personal_spans(paragraphs, sentences)
    texts = {p["id"]: p["text"] for p in paragraphs}
    bad = []
    for e in edits:
        find = e.get("find") or ""
        if not find:
            continue
        text = texts.get(e.get("paragraph"), "")
        starts = [m.start() for m in re.finditer(re.escape(find), text)]
        if starts:
            if any(a < s + len(find) and s < b for s in starts
                   for a, b in spans.get(e.get("paragraph"), [])):
                bad.append(e)
        elif any(find in s for s in sentences):
            bad.append(e)
    return bad


def count_comments(docx_path: Path) -> int:
    with zipfile.ZipFile(docx_path) as z:
        if "word/comments.xml" not in z.namelist():
            return 0
        xml = z.read("word/comments.xml").decode("utf-8")
    return len(re.findall(r"<w:comment\b", xml))


def _latest_review(folder: Path):
    reviews = sorted(p for p in (folder / ".help-me-write" / "revisioni").glob("*")
                     if (p / "note-bibliografia.md").is_file())
    return reviews[-1] if reviews else None


def evaluate(folder: Path, expected_path: Path, combined: bool = False) -> list:
    """Every check as (ok, name, detail)."""
    from helpmewrite.edits import EditsError, parse_edits
    from helpmewrite.extract import extract_docx

    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    defects = expected["defects"]
    results = []  # (ok, name, detail)

    def add(ok, name, detail=""):
        results.append((bool(ok), name, detail))

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

    original = folder / expected["document"]
    add(sha(original) == expected["sha256"], "original unchanged", f"{original.name} sha256")
    changed = [n for n, digest in expected["sources"].items() if sha(folder / n) != digest]
    add(not changed, "sources unchanged", f"changed or missing: {changed}" if changed else "")
    paragraphs = extract_docx(original) if original.is_file() else []

    review = _latest_review(folder)
    add(review is not None, "review folder with note-bibliografia.md",
        str(review) if review else "none in .help-me-write/revisioni/")
    note = report = ""
    edits = []
    if review is not None:
        needed = BIB_FILES + (REVISIONE_FILES if combined else [])
        missing = [n for n in needed if not (review / n).is_file()]
        add(not missing, "review files", f"missing: {missing}" if missing else ", ".join(needed))
        note = (review / "note-bibliografia.md").read_text(encoding="utf-8")
        if (review / "rapporto.md").is_file():
            report = (review / "rapporto.md").read_text(encoding="utf-8")
        positions = [re.search(rf"^{re.escape(h)}\s*$", note, re.M) for h in NOTE_HEADINGS]
        absent = [h for h, m in zip(NOTE_HEADINGS, positions) if m is None]
        in_order = not absent and [m.start() for m in positions] == sorted(
            m.start() for m in positions)
        add(in_order, "note-bibliografia.md sections in order",
            f"missing: {absent}" if absent else "" if in_order else "out of order")
        first = next((line for line in note.splitlines() if line.strip()), "")
        add(re.search(r"online|web|rete|internet", first, re.I),
            "note says whether online search was used", first[:120])
        edits_path = review / "edits-bibliografia.json"
        try:
            data = json.loads(edits_path.read_text(encoding="utf-8"))
            parse_edits(data)
            edits = data["edits"]
            others = [e.get("by") for e in edits if e.get("by") != "bibliografia"]
            add(not others, "edits-bibliografia.json valid, by bibliografia",
                f"{len(edits)} edits" + (f"; other by: {others}" if others else ""))
        except (OSError, ValueError, EditsError) as exc:
            add(False, "edits-bibliografia.json valid, by bibliografia", str(exc)[:200])
        if combined:
            try:
                union = json.loads((review / "edits.json").read_text(encoding="utf-8"))
                n_bib = sum(1 for e in union.get("edits", []) if e.get("by") == "bibliografia")
            except (OSError, ValueError):
                n_bib = 0
            add(n_bib == len(edits) and n_bib > 0, "edits.json has the bibliography edits",
                f"{n_bib} by bibliografia, {len(edits)} in edits-bibliografia.json")

    # -- the five defects in the notes
    spec = defects["wrong_claim"]
    rows = rows_of(note, spec["key"])
    page = re.compile(PAGE.format(n=spec["page"]), re.I)
    good = [r for r in rows if keyword(r, spec["verdicts"])
            and norm(spec["quote"]) in norm(r) and page.search(r)]
    add(good, "wrong_claim: [1] not supported, source quoted with page",
        f"{len(rows)} row(s) for {spec['key']}; need verdict, «{spec['quote']}», "
        f"page {spec['page']}" if not good else good[0][:160])

    spec = defects["invented_entry"]
    hit, text = any_hit(about(note, spec["key"]), spec["keywords"])
    add(hit, "invented_entry: [3] not found / invented / not verifiable",
        f"{hit!r} in {text[:120]!r}" if hit else f"nothing about {spec['key']} says so")

    spec = defects["wrong_year"]
    lines = [t for t in about(note, spec["key"]) if word(t, spec["wrong"]) and word(t, spec["right"])]
    add(lines, "wrong_year: [2] with both years in the notes",
        lines[0][:160] if lines else f"no statement about {spec['key']} with "
                                     f"{spec['wrong']} and {spec['right']}")
    entry = next((p for p in paragraphs if p["text"].startswith(spec["key"] + " ")), None)
    fixes = [e for e in edits if entry and e.get("paragraph") == entry["id"]
             and spec["wrong"] in e.get("find", "") and spec["right"] in (e.get("replace") or "")]
    add(fixes, "wrong_year: tracked change in the entry",
        f"{fixes[0]['find']!r} -> {fixes[0]['replace']!r}" if fixes else
        f"no replace {spec['wrong']} -> {spec['right']} in ¶ {entry and entry['id']}")

    spec = defects["missing_citation"]
    missing_section = section(note, ["missing citations"])
    items = [line for line in missing_section.splitlines()
             if any(k in norm(line) for k in spec["keywords"])]
    add(items, "missing_citation: the statement under ## Missing citations",
        items[0][:160] if items else f"none of {spec['keywords']}")

    spec = defects["missing_entry"]
    consistency = section(note, ["bibliography consistency"])
    lines = [c for c in clauses_naming(consistency, spec["key"]) if keyword(c, spec["keywords"])]
    add(lines, "missing_entry: [4] missing from the bibliography",
        lines[0][:160] if lines else f"no line of ## Bibliography consistency names {spec['key']}"
                                     " as missing")

    # -- personal activities
    bad = edits_in_personal(edits, paragraphs, expected["personal_sentences"])
    add(not bad, "no edit in the personal sentences",
        "; ".join(f"¶ {e.get('paragraph')} {e.get('find')!r}" for e in bad))

    # -- the revised copy
    revised = folder / expected["revised"]
    add(revised.is_file(), "revised copy exists", revised.name)
    if revised.is_file():
        n = count_comments(revised)
        add(n >= expected["min_comments"], "comments in the revised copy",
            f"{n} (need {expected['min_comments']})")
        spec = defects["wrong_year"]
        if entry is not None:
            text = next((p["text"] for p in extract_docx(revised) if p["id"] == entry["id"]), "")
            ok = word(text, spec["right"]) and not word(text, spec["wrong"])
            add(ok, "wrong_year: corrected in the copy's visible text", text[:100])

    # -- the report
    bib = section(report, REPORT_SECTION)
    evidence = {
        "wrong_claim": "30%" in norm(bib),
        "invented_entry": defects["invented_entry"]["key"] in bib and any_hit(
            [bib], defects["invented_entry"]["keywords"])[0] is not None,
        "wrong_year": word(bib, defects["wrong_year"]["wrong"]) and word(
            bib, defects["wrong_year"]["right"]),
        "missing_citation": "70%" in norm(bib),
        "missing_entry": defects["missing_entry"]["key"] in bib,
    }
    lacking = [d for d, ok in evidence.items() if not ok]
    add(bib.strip() and not lacking, "rapporto.md: Bibliography section populated",
        f"lacking: {lacking}" if lacking else f"{len(bib.splitlines())} lines")

    return results


def check(folder: Path, expected_path: Path, combined: bool = False) -> int:
    results = evaluate(folder, expected_path, combined)
    failed = [r for r in results if not r[0]]
    for ok, name, detail in results:
        print(f"{'OK  ' if ok else 'FAIL'} {name}" + (f": {detail}" if detail else ""))
    print(f"{len(results) - len(failed)} of {len(results)} checks passed")
    return 1 if failed else 0


def main(argv) -> int:
    if len(argv) == 4 and argv[0] == "--setup":
        return setup(Path(argv[1]), Path(argv[2]), Path(argv[3]))
    combined = "--combined" in argv
    argv = [a for a in argv if a != "--combined"]
    if len(argv) == 2:
        folder, expected = Path(argv[0]), Path(argv[1])
        if not expected.is_file() or not folder.is_dir():
            print("error: need an existing folder and expected.json", file=sys.stderr)
            return 2
        return check(folder, expected, combined)
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
