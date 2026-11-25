"""The bibliography draft of spec §9 case 5 (tests/scenari/bibliografia.md) really has its
defects, and `bib` sees the citations, entries and local sources the scenario relies on."""
import hashlib
import re

import pytest

from fixtures.builders import build_bib_draft
from helpmewrite.bib import extract_bibliography, find_local_sources, pdf_pages_text
from helpmewrite.extract import extract_docx

pytestmark = pytest.mark.needs_soffice  # the source PDFs are rendered with LibreOffice

DEFECTS = {"wrong_claim", "invented_entry", "wrong_year", "missing_citation", "missing_entry"}


def _norm(text: str) -> str:
    return " ".join(text.split())


@pytest.fixture(scope="module")
def draft(tmp_path_factory):
    folder = tmp_path_factory.mktemp("bib")
    return folder, build_bib_draft(folder)


@pytest.fixture(scope="module")
def paragraphs(draft):
    folder, expected = draft
    return extract_docx(folder / expected["document"])


@pytest.fixture(scope="module")
def text(paragraphs):
    return "\n".join(p["text"] for p in paragraphs)


def _paragraph_with(paragraphs, needle):
    hits = [p for p in paragraphs if needle in p["text"]]
    assert len(hits) == 1, (needle, hits)
    return hits[0]


def test_expected_describes_every_defect(draft):
    folder, expected = draft
    assert expected["document"] == "bozza-bib.docx"
    assert expected["revised"] == "bozza-bib-revisionato.docx"
    doc = folder / expected["document"]
    assert expected["sha256"] == hashlib.sha256(doc.read_bytes()).hexdigest()
    assert set(expected["sources"]) == {"fonti/rossi2021.pdf", "fonti/bianchi2020.pdf"}
    for name, digest in expected["sources"].items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest
    assert expected["min_comments"] >= 3
    assert set(expected["defects"]) == DEFECTS
    d = expected["defects"]
    assert d["wrong_claim"]["key"] == "[1]" and "30%" in d["wrong_claim"]["quote"]
    assert d["wrong_claim"]["page"] == 2 and d["wrong_claim"]["source"] == "fonti/rossi2021.pdf"
    assert d["invented_entry"]["key"] == "[3]" and "inventat" in d["invented_entry"]["keywords"]
    assert "non verificabil" in d["invented_entry"]["offline_keywords"]
    assert "non verificabil" not in d["invented_entry"]["keywords"]
    assert d["wrong_year"] == {"key": "[2]", "wrong": "2018", "right": "2020"}
    assert d["missing_citation"]["keywords"] == ["70%"]
    assert "il 70% delle aziende italiane usa pipeline CI" in d["missing_citation"]["sentence"]
    assert d["missing_entry"]["key"] == "[4]"
    for spec in d.values():
        for k in spec.get("keywords", []) + spec.get("offline_keywords", []):
            assert k == k.lower(), k


def test_personal_sentences(draft, text):
    _, expected = draft
    sentences = expected["personal_sentences"]
    assert len(sentences) == 3
    assert [s.split()[:2] for s in sentences][:2] == [["Ho", "configurato"], ["Ho", "scritto"]]
    for sentence in sentences:
        assert sentence.startswith("Ho ") and text.count(sentence) == 1
        assert not re.search(r"\[\d+\]|\(\w+,? \d{4}\)", sentence)  # no citation


def test_wrong_claim_cites_rossi_with_60_percent(paragraphs):
    p = _paragraph_with(paragraphs, "60%")
    assert "Secondo [1]" in p["text"] and "la cache delle dipendenze" in p["text"]
    assert "30%" not in "\n".join(q["text"] for q in paragraphs)


def test_bibliography_entries(paragraphs):
    headings = [p["text"] for p in paragraphs if p["heading_level"]]
    assert headings[-1] == "Bibliografia"
    entries = [p["text"] for p in paragraphs[[p["text"] for p in paragraphs].index("Bibliografia") + 1:]]
    assert [e[:3] for e in entries] == ["[1]", "[2]", "[3]"]
    assert entries[0].startswith("[1] Rossi, M. (2021). Tempi di build nelle pipeline di "
                                 "integrazione continua.")
    assert entries[1].startswith("[2] Bianchi, L. (2018). Test automatici in contesti industriali.")
    assert entries[2] == "[3] Neri, P. (2018). Quantum CI. doi:10.9999/fake.2018"


def test_missing_citation_and_missing_entry(draft, paragraphs):
    p = _paragraph_with(paragraphs, "il 70% delle aziende italiane usa pipeline CI")
    assert draft[1]["defects"]["missing_citation"]["sentence"] in p["text"]
    sentence = next(s for s in re.split(r"(?<=\.)\s+", p["text"]) if "70%" in s)
    assert not re.search(r"\[\d+\]", sentence)
    assert "[4]" in _paragraph_with(paragraphs, "[4]")["text"]
    assert not any(q["text"].startswith("[4]") for q in paragraphs)


def test_bib_sees_citations_entries_and_local_sources(draft):
    folder, expected = draft
    report = extract_bibliography(folder / expected["document"])
    assert report.style == "numeric"
    assert [e.key for e in report.entries] == ["[1]", "[2]", "[3]"]
    assert sorted({c.key for c in report.citations}) == ["[1]", "[2]", "[3]", "[4]"]
    assert report.missing_entries == ["[4]"] and report.uncited_entries == []
    assert report.entries[1].year == "2018" and report.entries[2].doi == "10.9999/fake.2018"
    found = find_local_sources(folder, report.entries)
    assert {k: v.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] for k, v in found.items()} == {
        "[1]": "rossi2021.pdf", "[2]": "bianchi2020.pdf"}


def test_source_pdfs(draft):
    folder, expected = draft
    rossi = [_norm(t) for t in pdf_pages_text(folder / "fonti" / "rossi2021.pdf")]
    bianchi = [_norm(t) for t in pdf_pages_text(folder / "fonti" / "bianchi2020.pdf")]
    assert len(rossi) == 2
    for needed in ("Tempi di build nelle pipeline di integrazione continua", "Rossi M.", "2021"):
        assert needed in rossi[0], needed
    quote = "la cache delle dipendenze riduce i tempi di build del 30%"
    assert quote not in rossi[0] and quote in rossi[1]
    assert expected["defects"]["wrong_claim"]["quote"] in rossi[1]
    for needed in ("Test automatici in contesti industriali", "Bianchi L.", "2020"):
        assert needed in bianchi[0], needed
    everything = " ".join(rossi + bianchi).lower()
    for absent in ("2018", "60%", "70%", "quantum", "neri", "10.9999"):
        assert not re.search(rf"(?<!\w){re.escape(absent)}(?!\w)", everything), absent
