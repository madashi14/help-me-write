"""The flawed draft of spec §9 case 2 (tests/scenari/revisione.md) really has its defects."""
import hashlib
import re
import statistics

import pytest

from conftest import FIX
from fixtures.builders import build_flawed_draft
from helpmewrite.extract import extract_docx
from helpmewrite.measure import measure
from helpmewrite.rules import load_rules

FORM_DEFECTS = {"font": "font_family", "chars_per_line": "chars_per_line",
                "no_index": "section:indice:present",
                "intro_length": "section:introduzione:pages"}
DEFECTS = {
    "typo_installaizone", "typo_e_stato", "typo_perche", "typo_qual_e", "typo_un_altro",
    "acronym_ci_cd", "figure_not_cited", "personal_contribution", "credential",
}
TYPOS = ["installaizone", "e stato", "perchè", "qual'è", "un'altro"]
FIRST_PERSON = re.compile(r"\b(io|ho|mi|me|mio|mia|miei|mie|abbiamo|noi|ci siamo|nostr\w*)\b",
                          re.IGNORECASE)


@pytest.fixture(scope="module")
def draft(tmp_path_factory):
    folder = tmp_path_factory.mktemp("bozza")
    expected = build_flawed_draft(folder)
    return folder / "bozza.docx", expected


@pytest.fixture(scope="module")
def paragraphs(draft):
    return extract_docx(draft[0])


def _chapter(paragraphs, title):
    """Paragraphs between the heading `title` and the next heading."""
    start = next(i for i, p in enumerate(paragraphs) if p["heading_level"] and p["text"] == title)
    end = next((i for i in range(start + 1, len(paragraphs)) if paragraphs[i]["heading_level"]),
               len(paragraphs))
    return paragraphs[start + 1:end]


def test_expected_names_every_defect(draft):
    path, expected = draft
    assert expected["form_defects"] == FORM_DEFECTS   # id -> measure check marked failed
    assert set(expected["defects"]) == DEFECTS
    for defect, spec in expected["defects"].items():
        keywords = spec["keywords"]
        assert keywords and all(k and k == k.lower() for k in keywords), defect
        assert set(spec) <= {"keywords", "section"}
    # keywords that a report following the template contains anyway do not count
    assert expected["defects"]["personal_contribution"] == {
        "keywords": ["passiv", "impersonal", "prima persona", "first person"],
        "section": ["contenuto", "content"]}
    assert expected["document"] == "bozza.docx" and expected["revised"] == "bozza-revisionato.docx"
    assert expected["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert expected["min_insertions"] >= 5 and "installazione" in expected["visible_text"]
    assert expected["secret"] == "Alfa2024!"


def test_typos_occur_once_each(paragraphs):
    text = "\n".join(p["text"] for p in paragraphs)
    for typo in TYPOS:
        assert len(re.findall(rf"(?<!\w){re.escape(typo)}(?!\w)", text)) == 1, typo
    assert "installaizone" in text


def test_structure_without_table_of_contents(paragraphs):
    headings = [p["text"] for p in paragraphs if p["heading_level"]]
    assert headings == ["Introduzione", "Il contesto aziendale", "Attività svolte", "Risultati",
                        "Conclusione"]
    assert not any(p["text"].strip().lower() in ("indice", "sommario") for p in paragraphs)


def test_acronym_never_defined(paragraphs):
    text = "\n".join(p["text"] for p in paragraphs)
    assert text.count("CI/CD") >= 3
    assert "(CI/CD)" not in text and "CI/CD (" not in text
    assert not re.search(r"continuous|delivery|deployment", text, re.IGNORECASE)


def test_figure_2_only_in_its_caption(paragraphs):
    with_2 = [p for p in paragraphs if "Figura 2" in p["text"]]
    assert len(with_2) == 1 and with_2[0]["style"] == "Caption"
    with_1 = [p for p in paragraphs if "Figura 1" in p["text"]]
    assert {p["style"] for p in with_1} == {"Caption", "Normal"}  # figure 1 is cited


def test_activities_chapter_is_impersonal(paragraphs):
    chapter = _chapter(paragraphs, "Attività svolte")
    prose = [p["text"] for p in chapter if p["style"] == "Normal" and p["text"]]
    assert len(prose) >= 8
    for text in prose:
        assert not FIRST_PERSON.search(text), text


def test_credential_in_a_paragraph(paragraphs):
    hits = [p for p in paragraphs if "password: Alfa2024!" in p["text"]]
    assert len(hits) == 1 and len(hits[0]["text"]) > len("password: Alfa2024!") + 40


@pytest.mark.needs_soffice
def test_measure_flags_the_form_defects(draft, tmp_path):
    path, expected = draft
    m = measure(path, load_rules(FIX / "linee-guida-unibo.yaml"), tmp_path / "w")
    by = {c.rule: c for c in m.checks}
    for rule in expected["form_defects"].values():
        assert not by[rule].ok, (rule, by[rule].detail)
    # about 12 pages, 4 of introduction, 85 characters per line (12, 4 and 85 with Carlito,
    # the metric clone of Calibri; a machine without it renders with another font)
    assert by["pages"].ok and 10 <= m.page_count <= 14, m.page_count
    assert by["section:conclusione:pages"].ok, by["section:conclusione:pages"].detail
    intro = next(s for s in m.sections if s.title == "Introduzione")
    assert 3 <= intro.end_page - intro.start_page + 1 <= 5
    full = [p.chars_per_full_line for p in m.pages if p.number != 1 and p.is_full]
    assert 75 <= statistics.median(full) <= 95
