"""Set up and check the review scenario (tests/scenari/revisione.md). Needs no pytest.

    python tests/scenari/check_revisione.py --setup <folder> <expected.json> <plugin>
        writes bozza.docx (tests/fixtures/builders.py: build_flawed_draft) and
        .help-me-write/linee-guida.yaml (the Unibo fixture) in <folder>, the expected
        results to <expected.json>, and a copy of the plugin without tests/, docs/ and
        the repository's history to <plugin>, the folder the agent under test gets: it
        must not be able to read the list of defects. <expected.json> and <plugin> must be
        outside <folder>.

    python tests/scenari/check_revisione.py <folder> <expected.json>
        checks <folder> after the review; prints one line per check and exits 1 if any
        check fails.

Report checks (rapporto.md of the newest review folder):
- a form defect counts when a row of the table in the Form section names its measure
  check id and marks it failed (✗) in the next cell;
- any other defect counts when one of its keywords starts a word of the report (or of
  the named section), case-insensitively: "e stato" does not match "essere stato".
"""
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "tests"), str(REPO / "scripts")]

REVIEW_FILES = ["extract.json", "measure.json", "edits-revisore.json", "note-revisore.md",
                "edits.json", "rapporto.md"]
NOTE_HEADINGS = ["## Form", "## Content", "## Questions for the author"]
FORM_SECTION = ["forma", "form"]
FAILED_MARKS = ("✗", "❌", "✘")
# what the plugin needs at run time; everything else (tests, docs, .git, .superpowers)
# stays out of the agent's reach
PLUGIN_PARTS = [".claude-plugin", ".codex-plugin", ".agents", "skills", "profili", "scripts",
                "requirements.txt", "README.md"]
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _inside(path: Path, folder: Path) -> bool:
    return path == folder or folder in path.parents


def prepare(folder: Path, expected_path: Path, plugin: Path) -> bool:
    """Check that the three setup paths are apart, then copy the plugin to `plugin`."""
    for other in (expected_path, plugin):
        if _inside(other, folder) or _inside(folder, other):
            print(f"error: {other} and {folder} must not contain each other", file=sys.stderr)
            return False
    if plugin.exists() and any(plugin.iterdir()):
        print(f"error: {plugin} exists and is not empty", file=sys.stderr)
        return False
    for part in PLUGIN_PARTS:
        source = REPO / part
        if source.is_dir():
            shutil.copytree(source, plugin / part,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        elif source.is_file():
            plugin.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, plugin / part)
    folder.mkdir(parents=True, exist_ok=True)
    return True


def setup(folder: Path, expected_path: Path, plugin: Path) -> int:
    from fixtures.builders import build_flawed_draft

    folder, expected_path, plugin = folder.resolve(), expected_path.resolve(), plugin.resolve()
    if not prepare(folder, expected_path, plugin):
        return 2
    expected = build_flawed_draft(folder)
    state = folder / ".help-me-write"
    state.mkdir(exist_ok=True)
    shutil.copyfile(REPO / "tests" / "fixtures" / "linee-guida-unibo.yaml",
                    state / "linee-guida.yaml")
    expected_path.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    print(f"wrote {folder / expected['document']}, {state / 'linee-guida.yaml'}, "
          f"{expected_path}, plugin copy {plugin}")
    return 0


def _latest_review(folder: Path):
    reviews = sorted(p for p in (folder / ".help-me-write" / "revisioni").glob("*")
                     if (p / "rapporto.md").is_file())
    return reviews[-1] if reviews else None


def section(report: str, names) -> str:
    """Text under the first `## <name>` heading (any of names, case-insensitive)."""
    out, inside = [], False
    for line in report.splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            if inside:
                break
            inside = heading.group(1).casefold() in names
        elif inside:
            out.append(line)
    return "\n".join(out)


def marked_failed(form: str, rule: str) -> bool:
    """A table row names `rule` in a cell and marks the next cell failed."""
    for line in form.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        for i, cell in enumerate(cells[:-1]):
            if re.search(rf"(?<![\w:]){re.escape(rule)}(?![\w:])", cell) and \
                    any(mark in cells[i + 1] for mark in FAILED_MARKS):
                return True
    return False


def keyword_hit(text: str, keywords):
    for keyword in keywords:
        if re.search(rf"(?<!\w){re.escape(keyword)}", text, re.IGNORECASE):
            return keyword
    return None


def secret_handled(original: Path, revised: Path, secret: str):
    """(ok, detail): the secret is no longer visible in its paragraph, or a comment is there."""
    import docx

    from helpmewrite.extract import extract_docx, iter_body_paragraphs, visible_text

    index = next((p["id"] for p in extract_docx(original) if secret in p["text"]), None)
    if index is None:
        return False, "the original has no paragraph with the secret"
    paragraph = iter_body_paragraphs(docx.Document(str(revised)))[index]
    deleted = secret not in visible_text(paragraph)
    commented = any(True for _ in paragraph.iter(f"{W}commentRangeStart", f"{W}commentReference"))
    detail = f"¶ {index}: " + ", ".join(
        [w for w, ok in (("deleted", deleted), ("commented", commented)) if ok] or ["neither"])
    return deleted or commented, detail


def check(folder: Path, expected_path: Path) -> int:
    from helpmewrite.extract import extract_docx

    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    results = []  # (ok, name, detail)

    def add(ok, name, detail=""):
        results.append((bool(ok), name, detail))

    original = folder / expected["document"]
    digest = hashlib.sha256(original.read_bytes()).hexdigest() if original.is_file() else None
    add(digest == expected["sha256"], "original unchanged", f"{original.name} sha256")

    review = _latest_review(folder)
    add(review is not None, "review folder with rapporto.md",
        str(review) if review else "none in .help-me-write/revisioni/")
    report = ""
    if review is not None:
        missing = [name for name in REVIEW_FILES if not (review / name).is_file()]
        add(not missing, "review files", f"missing: {missing}" if missing else ", ".join(REVIEW_FILES))
        notes_path = review / "note-revisore.md"
        notes = notes_path.read_text(encoding="utf-8") if notes_path.is_file() else ""
        absent = [h for h in NOTE_HEADINGS if not re.search(rf"^{re.escape(h)}\s*$", notes, re.M)]
        add(not absent, "note-revisore.md sections", f"missing: {absent}" if absent else "")
        report = (review / "rapporto.md").read_text(encoding="utf-8")

    form = section(report, FORM_SECTION)
    for defect, rule in expected["form_defects"].items():
        add(marked_failed(form, rule), f"report: {defect}",
            f"`{rule}` marked ✗ in the Form table")
    for defect, spec in expected["defects"].items():
        text = section(report, spec["section"]) if spec.get("section") else report
        hit = keyword_hit(text, spec["keywords"])
        where = f" in section {spec['section'][0]}" if spec.get("section") else ""
        add(hit is not None, f"report: {defect}",
            f"found {hit!r}{where}" if hit else f"none of {spec['keywords']}{where}")
    secret = expected["secret"]
    add(secret not in report, "report does not repeat the secret")

    revised = folder / expected["revised"]
    add(revised.is_file(), "revised copy exists", revised.name)
    if revised.is_file():
        with zipfile.ZipFile(revised) as z:
            xml = z.read("word/document.xml").decode("utf-8")
        insertions = len(re.findall(r"<w:ins\b", xml))
        add(insertions >= expected["min_insertions"], "tracked insertions",
            f"{insertions} w:ins (need {expected['min_insertions']})")
        text = "\n".join(p["text"] for p in extract_docx(revised))
        for word in expected["visible_text"]:
            add(word in text, f"visible text has {word!r}")
        if original.is_file():
            ok, detail = secret_handled(original, revised, secret)
            add(ok, "credential deleted or commented in the copy", detail)
    failed = [r for r in results if not r[0]]
    for ok, name, detail in results:
        print(f"{'OK  ' if ok else 'FAIL'} {name}" + (f": {detail}" if detail else ""))
    print(f"{len(results) - len(failed)} of {len(results)} checks passed")
    return 1 if failed else 0


def main(argv) -> int:
    if len(argv) == 4 and argv[0] == "--setup":
        return setup(Path(argv[1]), Path(argv[2]), Path(argv[3]))
    if len(argv) == 2:
        folder, expected = Path(argv[0]), Path(argv[1])
        if not expected.is_file() or not folder.is_dir():
            print("error: need an existing folder and expected.json", file=sys.stderr)
            return 2
        return check(folder, expected)
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
