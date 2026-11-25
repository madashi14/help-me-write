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
- wrong_claim: in the table row whose first cell names [1], the Verdict cell says not (or
  partially) supported, and the Source passage cell quotes, word for word from the
  source PDF's page, a passage with the expected words, and names that page;
- invented_entry: the text about [3] in "## Bibliography consistency" says not found or
  possibly invented; "not verifiable" counts only when the notes' first line says that
  online search was not available;
- wrong_year: what the note says about [2] has both years (not inside a file name), and
  the entry gets a tracked change from one to the other;
- missing_citation: an item of "## Missing citations" has the statement's number and does
  not say that no citation is needed, and a comment is anchored in the statement;
- missing_entry: a clause of "## Bibliography consistency" names [4] (not as the end of a
  range "[1]–[4]") as missing.
No edit and no "## Missing citations" item may fall on the student's own activities.
A keyword does not count after a negation in its clause ("non inventata", "non risulta
inventata", "nessuna mancante", "not, as far as I can tell, invented").
"""
import hashlib
import json
import re
import sys
import unicodedata
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
    """Casefolded, one space between words, no space before %, plain apostrophes,
    ligatures split (NFKC: a PDF's "ﬁ" is "fi")."""
    text = unicodedata.normalize("NFKC", text).replace("’", "'").casefold()
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


# negations: right before a keyword ("nessuna mancante"), or anywhere earlier in its
# clause ("la voce non risulta inventata", "it is not, as far as I can tell, invented")
_NEGATED_RIGHT_BEFORE = re.compile(r"(?:\bnon|\bnot|\bno|\bnessun\w*|\bnone|\bnever|\bmai)\s+"
                                   r"(?:(?:è|e|is|was|be|stat[ao]|been)\s+)*$")
_NEGATION = re.compile(r"\b(?:non|not|never|mai|né|nor)\b|n't\b")
_CLAUSE_END = re.compile(r"[;:!?]|\.\s|\s[—–]\s|\|")
# keywords that are themselves negative ("non trovata", "not found") are not negated by
# the clause: "nessun PDF locale, non trovata online" still says not found
_NEGATIVE_KEYWORD = re.compile(r"(?:non|not|no|nessun\w*|does not|cannot)\b")


def negated(low: str, start: int, keyword_text: str) -> bool:
    if _NEGATED_RIGHT_BEFORE.search(low[max(0, start - 24):start]):
        return True
    if _NEGATIVE_KEYWORD.match(keyword_text):
        return False
    ends = [m.end() for m in _CLAUSE_END.finditer(low, 0, start)]
    return _NEGATION.search(low[ends[-1] if ends else 0:start]) is not None


def keyword(text: str, keywords):
    """The first keyword found in text, not negated."""
    low = norm(text)
    for k in keywords:
        for m in re.finditer(re.escape(k), low):
            if not negated(low, m.start(), k):
                return k
    return None


def any_hit(texts, keywords):
    for text in texts:
        hit = keyword(text, keywords)
        if hit:
            return hit, text
    return None, None


def names_alone(text: str, key: str) -> bool:
    """text names key on its own, not as the end of a range such as [1]–[4]."""
    return any(not re.search(r"\]\s*[–—-]\s*$", text[:m.start()])
               for m in re.finditer(re.escape(key), text))


def clauses_naming(text: str, key: str) -> list[str]:
    """Clauses (split at ; and at the end of sentences) that name key on its own."""
    return [c for line in text.splitlines() for c in re.split(r";|\.\s", line)
            if names_alone(c, key)]


def segments_about(text: str, key: str) -> list[str]:
    """On each line naming key on its own, the text from key up to the next other key."""
    out = []
    for line in text.splitlines():
        if not names_alone(line, key):
            continue
        for m in re.finditer(re.escape(key), line):
            rest = line[m.end():]
            other = next((k for k in KEY.finditer(rest) if k.group(0) != key), None)
            out.append(key + (rest[:other.start()] if other else rest))
    return out


def table_columns(text: str) -> dict:
    """Column index of the verdict and of the source passage, from the table's header."""
    for line in text.splitlines():
        cells = _cells(line)
        if not cells:
            continue
        found = {}
        for i, cell in enumerate(cells):
            low = cell.casefold()
            if re.search(r"verdict|esito", low):
                found.setdefault("verdict", i)
            elif re.search(r"passage|passaggio", low):
                found.setdefault("passage", i)
        return {"verdict": found.get("verdict", 2), "passage": found.get("passage", 4)}
    return {"verdict": 2, "passage": 4}


_QUOTED = re.compile(r"«([^»]+)»|“([^”]+)”|\"([^\"]+)\"")


def verbatim_quotes(cell: str, page_text: str) -> list[str]:
    """Quotations in cell whose every fragment (split at ellipses) is in page_text."""
    page = norm(page_text)
    out = []
    for m in _QUOTED.finditer(cell):
        quoted = next(g for g in m.groups() if g is not None)
        fragments = [norm(f).strip(" .,;:") for f in re.split(r"…|\.\.\.|\[…\]", quoted)]
        fragments = [f for f in fragments if f]
        if fragments and all(f in page for f in fragments):
            out.append(quoted)
    return out


_NO_CITATION_NEEDED = re.compile(
    r"non serv|non è necessari|non necessari|non richied|non va citat|non occorr|"
    r"nessuna citazione|not needed|no citation needed|does not need|doesn't need|"
    r"not required|needs no citation|no need")


def windows(text: str, n: int = 4) -> set:
    words = re.findall(r"[\w%]+", norm(text))
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def mentions_personal(line: str, paragraphs, sentences) -> str | None:
    """The personal sentence a line quotes (4 words in a row found nowhere else in the
    document), if any."""
    rest = " ".join(p["text"] for p in paragraphs)
    for s in sentences:
        rest = rest.replace(s, " ")
    elsewhere = windows(rest)
    seen = windows(line)
    for s in sentences:
        if (windows(s) - elsewhere) & seen:
            return s
    return None


def overlapping_edits(edits, paragraphs, sentence, comment_only=False):
    """Edits whose find falls (even partly) in sentence."""
    spans = personal_spans(paragraphs, [sentence])
    texts = {p["id"]: p["text"] for p in paragraphs}
    out = []
    for e in edits:
        if comment_only and not e.get("comment"):
            continue
        find, para = e.get("find") or "", e.get("paragraph")
        starts = [m.start() for m in re.finditer(re.escape(find), texts.get(para, ""))] if find else []
        if any(a < s + len(find) and s < b for s in starts for a, b in spans.get(para, [])):
            out.append(e)
    return out


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
    offline = False
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
        offline = re.search(r"non disponibil|not available|unavailable|non usat|not used|"
                            r"nessuno strumento|no web|senza rete|no network|nessuna rete",
                            first, re.I) is not None
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
    citations = section(note, ["citations"])
    columns = table_columns(citations)
    page = re.compile(PAGE.format(n=spec["page"]), re.I)
    try:
        from helpmewrite.bib import pdf_pages_text

        page_text = pdf_pages_text(folder / spec["source"])[spec["page"] - 1]
    except Exception:  # missing or unreadable source: nothing can be quoted from it
        page_text = ""
    good = []
    for row in rows_of(citations, spec["key"]):
        cells = _cells(row)
        verdict = cells[columns["verdict"]] if len(cells) > columns["verdict"] else ""
        passage = cells[columns["passage"]] if len(cells) > columns["passage"] else ""
        quotes = [q for q in verbatim_quotes(passage, page_text) if norm(spec["quote"]) in norm(q)]
        if keyword(verdict, spec["verdicts"]) and quotes and page.search(passage):
            good.append(f"{verdict} | {passage}")
    add(good, "wrong_claim: [1] not supported, source quoted verbatim with page",
        good[0][:160] if good else
        f"need, in the row of {spec['key']}, a verdict of {spec['verdicts'][:2]} and a "
        f"passage quoted verbatim from {spec['source']} p. {spec['page']} with "
        f"«{spec['quote']}» and the page")

    spec = defects["invented_entry"]
    consistency = section(note, ["bibliography consistency"])
    accepted = spec["keywords"] + (spec["offline_keywords"] if offline else [])
    hit, text = any_hit(segments_about(consistency, spec["key"]), accepted)
    add(hit, "invented_entry: [3] not found or possibly invented",
        f"{hit!r} in {text[:120]!r}" if hit else
        f"no line of ## Bibliography consistency says {spec['key']} was not found"
        + ("" if offline else " (online search was available: 'not verifiable' is not enough)"))

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
             if any(k in norm(line) for k in spec["keywords"])
             and not _NO_CITATION_NEEDED.search(norm(line))]
    anchored = overlapping_edits(edits, paragraphs, spec["sentence"], comment_only=True)
    add(items and anchored, "missing_citation: listed under ## Missing citations and commented",
        (items[0][:120] if items else f"no item with {spec['keywords']} that asks for a citation")
        + ("; comment on " + repr(anchored[0]["find"]) if anchored
           else "; no comment anchored in the statement"))

    spec = defects["missing_entry"]
    lines = [c for c in clauses_naming(consistency, spec["key"]) if keyword(c, spec["keywords"])]
    add(lines, "missing_entry: [4] missing from the bibliography",
        lines[0][:160] if lines else f"no line of ## Bibliography consistency names {spec['key']}"
                                     " as missing")

    # -- personal activities
    bad = edits_in_personal(edits, paragraphs, expected["personal_sentences"])
    add(not bad, "no edit in the personal sentences",
        "; ".join(f"¶ {e.get('paragraph')} {e.get('find')!r}" for e in bad))
    asked = [line for line in missing_section.splitlines()
             if mentions_personal(line, paragraphs, expected["personal_sentences"])]
    add(not asked, "no missing citation on the personal sentences",
        "; ".join(line[:100] for line in asked))

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
            [bib], defects["invented_entry"]["keywords"]
            + defects["invented_entry"]["offline_keywords"])[0] is not None,
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
