"""Set up and check the review scenario (tests/scenari/revisione.md). Needs no pytest.

    python tests/scenari/check_revisione.py --setup <folder> <expected.json>
        writes bozza.docx (tests/fixtures/builders.py: build_flawed_draft) and
        .help-me-write/linee-guida.yaml (the Unibo fixture) in <folder>, and the expected
        results to <expected.json>, which must be outside <folder>: the agent under test
        must not read it.

    python tests/scenari/check_revisione.py <folder> <expected.json>
        checks <folder> after the review; prints one line per check and exits 1 if any
        check fails.
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
SECRET = "Alfa2024!"


def setup(folder: Path, expected_path: Path) -> int:
    from fixtures.builders import build_flawed_draft

    folder, expected_path = folder.resolve(), expected_path.resolve()
    if folder in expected_path.parents:
        print(f"error: {expected_path} must be outside {folder}", file=sys.stderr)
        return 2
    folder.mkdir(parents=True, exist_ok=True)
    expected = build_flawed_draft(folder)
    state = folder / ".help-me-write"
    state.mkdir(exist_ok=True)
    shutil.copyfile(REPO / "tests" / "fixtures" / "linee-guida-unibo.yaml",
                    state / "linee-guida.yaml")
    expected_path.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    print(f"wrote {folder / expected['document']}, {state / 'linee-guida.yaml'}, {expected_path}")
    return 0


def _latest_review(folder: Path):
    reviews = sorted(p for p in (folder / ".help-me-write" / "revisioni").glob("*")
                     if (p / "rapporto.md").is_file())
    return reviews[-1] if reviews else None


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
        measure_path = review / "measure.json"
        if measure_path.is_file():
            checks = {c["rule"]: c["ok"] for c in json.loads(measure_path.read_text(encoding="utf-8"))["checks"]}
            not_failed = [r for r in expected["failed_checks"] if checks.get(r, True)]
            add(not not_failed, "measure.json flags the form defects",
                f"not failed: {not_failed}" if not_failed else ", ".join(expected["failed_checks"]))
        report = (review / "rapporto.md").read_text(encoding="utf-8")

    lowered = report.casefold()
    for defect, keywords in expected["defects"].items():
        hit = next((k for k in keywords if k.casefold() in lowered), None)
        add(hit is not None, f"report mentions {defect}",
            f"found {hit!r}" if hit else f"none of {keywords}")
    add(SECRET not in report, "report does not repeat the password")

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
    failed = [r for r in results if not r[0]]
    for ok, name, detail in results:
        print(f"{'OK  ' if ok else 'FAIL'} {name}" + (f": {detail}" if detail else ""))
    print(f"{len(results) - len(failed)} of {len(results)} checks passed")
    return 1 if failed else 0


def main(argv) -> int:
    if len(argv) == 3 and argv[0] == "--setup":
        return setup(Path(argv[1]), Path(argv[2]))
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
