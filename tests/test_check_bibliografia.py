"""tests/scenari/check_bibliografia.py accepts a correct bibliography review and rejects
notes that mention the defects only with generic words."""
import json
import shutil
import sys

import pytest

from conftest import ROOT
from fixtures.builders import build_bib_draft
from helpmewrite import cli

sys.path.insert(0, str(ROOT / "tests" / "scenari"))
import check_bibliografia  # noqa: E402

pytestmark = pytest.mark.needs_soffice  # build_bib_draft renders the source PDFs

ROW_1 = ("| [1] | «Secondo [1] la cache delle dipendenze riduce i tempi di build del 60%, …» "
         "(¶ 5) | non supportata | testo completo | «la cache delle dipendenze riduce i tempi "
         "di build del 30% rispetto alle esecuzioni senza cache» (p. 2) | Il testo dice 60%, "
         "la fonte 30%. |")
ROW_3 = ("| [3] | «Approcci più sperimentali … [3].» (¶ 6) | non verificabile | non accessibile "
         "| — | Nessun PDF locale, nessuno strumento web. |")
LINE_2 = ("- [2] Bianchi, 2018: trovata, PDF locale fonti/bianchi2020.pdf; anno: 2018 nella "
          "voce, 2020 nella fonte (p. 1).")
LINE_3 = "- [3] Neri, 2018: non verificabile: nessun PDF locale e nessuno strumento web."
LINE_4 = "- Citate ma assenti dalla bibliografia: [4] (¶ 6)."
MISSING = ("- ¶ 3: «Oggi il 70% delle aziende italiane usa pipeline CI …» — dato preso da "
           "terzi; nessuna fonte della cartella lo riporta.")

GOOD_NOTE = f"""Ricerca online: non disponibile (nessuno strumento web). Fonti locali: fonti/rossi2021.pdf ([1]), fonti/bianchi2020.pdf ([2]).

## Citations
| Key | Sentence | Verdict | Verified on | Source passage (page) | Note |
|---|---|---|---|---|---|
| [2] | «L'esecuzione dei test automatici … prima del rilascio [2].» (¶ 5) | supportata | testo completo | «ha permesso di individuare la maggior parte dei difetti prima del rilascio in produzione» (p. 1) | |
{ROW_1}
{ROW_3}
| [4] | «Le pipeline descritte … [4].» (¶ 6) | non verificabile | non accessibile | — | Nessuna voce [4]. |

## Missing citations
{MISSING}

## Bibliography consistency
- [1] Rossi, 2021: trovata, PDF locale fonti/rossi2021.pdf; dati come nella fonte.
{LINE_2}
{LINE_3}
{LINE_4}
- In bibliografia ma mai citate: nessuna.
- Stile di citazione: numerico, uniforme.
"""

GOOD_EDITS = [
    {"paragraph": 5, "find": "del 60%", "comment": "La fonte [1] riporta il 30% (p. 2).",
     "reason": "dato non supportato", "by": "bibliografia"},
    {"paragraph": 3, "find": "il 70% delle aziende italiane", "comment": "Quale fonte?",
     "reason": "citazione mancante", "by": "bibliografia"},
    {"paragraph": 6, "find": "[4]", "comment": "[4] non è in bibliografia.",
     "reason": "voce mancante", "by": "bibliografia"},
    {"paragraph": 16, "find": "Quantum CI", "comment": "Voce non verificabile.",
     "reason": "voce non verificabile", "by": "bibliografia"},
    {"paragraph": 15, "find": "(2018)", "replace": "(2020)",
     "reason": "anno errato: 2020 nella fonte (p. 1)", "by": "bibliografia"},
]

GOOD_REPORT = """# Revisione di bozza-bib.docx (2026-11-25)

## Bibliografia

| Citazione | Frase (¶) | Esito | Verificata su | Passaggio della fonte (pagina) | Nota |
|---|---|---|---|---|---|
| [1] | «… del 60% …» (¶ 5) | non supportata | testo completo | «… del 30% …» (p. 2) | |
| [3] | «…» (¶ 6) | non verificabile | non accessibile | — | |

| ¶ | Prima | Dopo | Motivo |
|---|---|---|---|
| 15 | (2018) | (2020) | anno errato |

### Citazioni mancanti
- ¶ 3: il 70% delle aziende italiane — nessuna fonte.

### Coerenza della bibliografia
- [4] citata ma assente dalla bibliografia.
"""

# a note that names every defect only with words any note has
GENERIC_NOTE = """Ricerca online: non disponibile.

## Citations
| Key | Sentence | Verdict | Verified on | Source passage (page) | Note |
|---|---|---|---|---|---|
| [1] | «… del 60% …» (¶ 5) | supportata | testo completo | «la cache delle dipendenze riduce i tempi di build del 30%» (p. 2) | |
| [2] | «…» (¶ 5) | supportata | testo completo | «…» (p. 1) | fonti/bianchi2020.pdf |
| [3] | «…» (¶ 6) | supportata | solo abstract | «…» | trovata online, non inventata |

## Missing citations
- ¶ 8: «Ho configurato la cache delle dipendenze» — serve una fonte.

## Bibliography consistency
- [2] Bianchi (2018): trovata, fonti/bianchi2020.pdf; dati corretti.
- [3] Neri (2018): trovata online, non è inventata.
- Citazioni: [1]–[4] tutte presenti, nessuna mancante.
"""

DEFECT_CHECKS = {
    "wrong_claim": "wrong_claim: [1] not supported, source quoted with page",
    "invented_entry": "invented_entry: [3] not found / invented / not verifiable",
    "wrong_year_note": "wrong_year: [2] with both years in the notes",
    "wrong_year_edit": "wrong_year: tracked change in the entry",
    "wrong_year_copy": "wrong_year: corrected in the copy's visible text",
    "missing_citation": "missing_citation: the statement under ## Missing citations",
    "missing_entry": "missing_entry: [4] missing from the bibliography",
    "personal": "no edit in the personal sentences",
    "comments": "comments in the revised copy",
    "report": "rapporto.md: Bibliography section populated",
}


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    root = tmp_path_factory.mktemp("bibcheck")
    folder = root / "lavoro"
    expected = build_bib_draft(folder)
    path = root / "expected.json"
    path.write_text(json.dumps(expected, ensure_ascii=False), encoding="utf-8")
    return folder, path


def failed_checks(base, tmp_path, capsys, note=GOOD_NOTE, edits=GOOD_EDITS, report=GOOD_REPORT):
    source, expected = base
    folder = tmp_path / "lavoro"
    shutil.copytree(source, folder)
    rev = folder / ".help-me-write" / "revisioni" / "2026-11-25-1200"
    rev.mkdir(parents=True)
    (rev / "bib.json").write_text("{}", encoding="utf-8")
    (rev / "note-bibliografia.md").write_text(note, encoding="utf-8")
    (rev / "edits-bibliografia.json").write_text(
        json.dumps({"author": "help-me-write", "edits": edits}, ensure_ascii=False),
        encoding="utf-8")
    (rev / "rapporto.md").write_text(report, encoding="utf-8")
    cli.main(["track", str(folder / "bozza-bib.docx"), "--edits",
              str(rev / "edits-bibliografia.json"), "-o",
              str(folder / "bozza-bib-revisionato.docx")])
    capsys.readouterr()
    return {name for ok, name, _ in check_bibliografia.evaluate(folder, expected) if not ok}


def test_a_correct_review_passes(base, tmp_path, capsys):
    assert failed_checks(base, tmp_path, capsys) == set()


def test_a_generic_note_fails_every_defect(base, tmp_path, capsys):
    edits = [e for e in GOOD_EDITS if "replace" not in e] + [
        {"paragraph": 8, "find": "Ho configurato la cache", "comment": "Serve una fonte.",
         "reason": "citazione mancante", "by": "bibliografia"}]
    failed = failed_checks(base, tmp_path, capsys, note=GENERIC_NOTE, edits=edits,
                           report="# Revisione\n\n## Bibliografia\n\nNon eseguita.\n")
    assert failed == set(DEFECT_CHECKS.values()) - {DEFECT_CHECKS["comments"]}


@pytest.mark.parametrize("old, new, check", [
    # the verdict of [1], the verbatim passage, its page
    ("| non supportata | testo completo | «la cache", "| supportata | testo completo | «la cache",
     "wrong_claim"),
    ("riduce i tempi di build del 30% rispetto", "riduce del 30% i tempi di build rispetto",
     "wrong_claim"),
    ("senza cache» (p. 2)", "senza cache»", "wrong_claim"),
    (LINE_3, "- [3] Neri, 2018: trovata online, non inventata.", "invented_entry"),
    (LINE_2, "- [2] Bianchi, 2018: trovata, PDF locale fonti/bianchi2020.pdf; dati corretti.",
     "wrong_year_note"),
    (MISSING, "- ¶ 8: «Ho configurato la cache» — serve una fonte.", "missing_citation"),
    (LINE_4, "- Citazioni: [1]–[4] tutte presenti, nessuna mancante.", "missing_entry"),
])
def test_each_defect_needs_its_own_evidence(base, tmp_path, capsys, old, new, check):
    note = GOOD_NOTE.replace(ROW_3, ROW_3.replace("non verificabile", "supportata")) \
        if check == "invented_entry" else GOOD_NOTE
    assert old in note
    assert failed_checks(base, tmp_path, capsys, note=note.replace(old, new)) == {
        DEFECT_CHECKS[check]}


def test_edits_and_copy(base, tmp_path, capsys):
    personal = GOOD_EDITS + [{"paragraph": 10, "find": "da 14 a 10 minuti",
                              "comment": "Fonte?", "reason": "dato", "by": "bibliografia"}]
    assert failed_checks(base, tmp_path, capsys, edits=personal) == {DEFECT_CHECKS["personal"]}
    no_year = [e for e in GOOD_EDITS if "replace" not in e]
    assert failed_checks(base, tmp_path / "y", capsys, edits=no_year) == {
        DEFECT_CHECKS["wrong_year_edit"], DEFECT_CHECKS["wrong_year_copy"]}
    two_comments = [e for e in GOOD_EDITS if "replace" in e or e["paragraph"] in (5, 3)]
    assert failed_checks(base, tmp_path / "c", capsys, edits=two_comments) == {
        DEFECT_CHECKS["comments"]}
