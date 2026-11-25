# Scenario: review of a bibliography (skill `revisione-bibliografia`, spec §9 case 5)

Checks that an agent with the plugin, asked to check the bibliography of a draft, finds
every bibliographic defect inserted on purpose, quotes the source for the wrong claim,
asks for no citation on the student's own activities, and delivers comments and the
corrected year in a copy, leaving the original and the sources untouched. The combined run
checks the same through the `revisione` skill, which runs the bibliography reviewer next
to the main reviewer.

## Setup

`<repo>` is the absolute path of this repository. Create a new, empty temporary folder
`<tmp>` and run:

```
python <repo>/tests/scenari/check_bibliografia.py --setup <tmp>/lavoro <tmp>/expected.json <tmp>/plugin
```

- `<tmp>/lavoro` then holds `bozza-bib.docx` (built by `build_bib_draft` in
  `tests/fixtures/builders.py`), `fonti/rossi2021.pdf`, `fonti/bianchi2020.pdf` and
  `.help-me-write/linee-guida.yaml` (a copy of `tests/fixtures/linee-guida-unibo.yaml`:
  profile `relazione-tirocinio`, whose `## Citation needs` is the reviewer's criterion).
- `<tmp>/plugin` is a copy of the plugin without `tests/`, `docs/` and the repository's
  history, as in the review scenario: the agent under test cannot read the defects.
- `expected.json` stays outside the folder too.

`bozza-bib.docx` is a short internship report with numeric citations. The two PDFs are
fictional sources, with title, author and year on page 1. The defects (ids as in
`expected.json`):

| Id | Defect |
|---|---|
| `wrong_claim` | "Secondo [1] la cache delle dipendenze riduce i tempi di build del 60%"; `rossi2021.pdf` says 30% (page 2) |
| `invented_entry` | entry [3] "Neri, P. (2018). Quantum CI. doi:10.9999/fake.2018" does not exist |
| `wrong_year` | entry [2] has 2018; `bianchi2020.pdf` says 2020 |
| `missing_citation` | "il 70% delle aziende italiane usa pipeline CI" has no citation |
| `missing_entry` | [4] is cited and has no entry |

Three sentences describe the student's own activities ("Ho configurato…", "Ho scritto…",
"Ho misurato…", the last one with numbers): they need no citation.

## Run: the skill alone

From `<tmp>/lavoro`:

```
claude -p --plugin-dir <tmp>/plugin --add-dir <tmp>/plugin --allowedTools "Bash(python:*) Bash(python3:*) WebSearch WebFetch" --permission-mode acceptEdits --output-format stream-json --verbose "Controlla la bibliografia di bozza-bib.docx. Ora non rispondo a domande: lasciale nel rapporto." > <tmp>/transcript.jsonl
```

- The prompt answers in advance the only thing a headless run cannot: no answers now.
- `WebSearch WebFetch` let the reviewer look entries up online, if this machine has the
  network for it. Without them, or without network, the reviewer must say so in its notes
  and mark [3] "non verificabile"; with them, [3] is not found ("possibile citazione
  inventata o errata"). Both pass.
- The skill may dispatch its reviewer as a subagent: that is the product under test.

## Combined run: through the review skill

A new `<tmp>` and setup as above, then from `<tmp>/lavoro`:

```
claude -p --plugin-dir <tmp>/plugin --add-dir <tmp>/plugin --allowedTools "Bash(python:*) Bash(python3:*) WebSearch WebFetch" --permission-mode acceptEdits --output-format stream-json --verbose "Rivedi bozza-bib.docx. Le linee guida in .help-me-write/linee-guida.yaml sono ancora valide, non serve rifarle. Per la copia formattata usa Times New Roman. Ora non rispondo alle domande sul contenuto: lasciale nel rapporto." > <tmp>/transcript.jsonl
```

## Expected

Pass/fail, all checked by `check_bibliografia.py`:

1. `bozza-bib.docx` and the two PDFs are unchanged (sha256 from setup).
2. The newest folder `.help-me-write/revisioni/<YYYY-MM-DD-HHMM>/` with
   `note-bibliografia.md` also has `bib.json`, `edits-bibliografia.json` and
   `rapporto.md`; with `--combined`, also the files of the `revisione` skill
   (`extract.json`, `measure.json`, `edits-revisore.json`, `note-revisore.md`, `edits.json`,
   the last one with the bibliography edits).
3. `note-bibliografia.md`: a first line on the online search; the sections `## Citations`
   (the table), `## Missing citations` and `## Bibliography consistency`, in this order.
4. `edits-bibliografia.json` is a valid EditSet, every edit `"by": "bibliografia"`.
5. Every defect, with evidence specific to it (a word any note contains does not count,
   nor a keyword right after a negation such as "non inventata"):
   - `wrong_claim`: the table row of [1] has the verdict "non supportata" or "parzialmente
     supportata", quotes the source verbatim (at least "tempi di build del 30%") and gives
     page 2;
   - `invented_entry`: what the note says about [3] (its row, or the text after "[3]" up to
     another key) says not found, possibly invented, or not verifiable;
   - `wrong_year`: what the note says about [2] has 2018 and 2020 (not inside a file name
     such as `bianchi2020.pdf`), the edits replace 2018 with 2020 in the entry, and the
     copy's visible text of the entry has 2020 and not 2018;
   - `missing_citation`: an item of `## Missing citations` has "70%";
   - `missing_entry`: a clause of `## Bibliography consistency` names [4] (not as the end
     of a range "[1]–[4]") as missing from the bibliography.
6. No edit of `edits-bibliografia.json` has its `find` in one of the three personal
   sentences.
7. `bozza-bib-revisionato.docx` exists next to the original with at least 3 comments.
8. The Bibliography section of `rapporto.md` is populated: it has "30%", [3] with one of
   its keywords, 2018 and 2020, "70%" and [4].

Also expected (read the notes, the report and the transcript):

- The reviewer reads the PDFs with `hmw pdftext` and does not look online for an entry it
  found locally.
- Online queries, if any, hold only titles, authors and DOIs, never text of the draft.
- No source is proposed for the 70% statement: neither PDF supports it.
- The report is in Italian and, alone, has only the title lines, a summary and the
  Bibliography section.

## Check

```
python <repo>/tests/scenari/check_bibliografia.py <tmp>/lavoro <tmp>/expected.json [--combined]
```

Prints one line per check and exits 1 if any fails. `tests/test_check_bibliografia.py`
runs it on a hand-made correct review and on notes that name the defects only with
generic words, which it must reject.

## Results

Claude Code 2.1.332, headless, each run in a new folder made by `--setup`. ✓ = pass.
Runs 1–3 are runs of the skill alone; "Combined" is the combined run, checked with
`--combined`.

| Check of `check_bibliografia.py` | Run 1 | Run 2 | Combined | Run 3 |
|---|---|---|---|---|
| original unchanged | ✓ | ✓ | ✓ | ✓ |
| sources unchanged | ✓ | ✓ | ✓ | ✓ |
| review folder with `note-bibliografia.md` | ✓ | ✓ | ✓ | ✓ |
| review files | ✓ | ✓ | ✓ (9 files) | ✓ |
| note sections in order | ✓ | ✓ | ✓ | ✓ |
| note says whether online search was used | ✓ | ✓ | ✓ | ✓ |
| `edits-bibliografia.json` valid, by bibliografia | ✓ 7 | ✓ 7 | ✓ 7 | ✓ 7 |
| `edits.json` has the bibliography edits | – | – | ✓ 7 | – |
| `wrong_claim`: [1] non supportata, 30% quoted, p. 2 | ✓ | ✓ | ✓ | ✓ |
| `invented_entry`: [3] | ✓ | ✓ | ✓ | ✓ |
| `wrong_year`: both years for [2] in the notes | ✓ | ✓ | ✓ | ✓ |
| `wrong_year`: tracked change in the entry | ✓ | ✓ | ✓ | ✓ |
| `missing_citation`: 70% under Missing citations | ✓ | ✓ | ✓ | ✓ |
| `missing_entry`: [4] missing from the bibliography | ✓ | ✓ | ✓ | ✓ |
| no edit in the personal sentences | ✓ | ✓ | ✓ | ✓ |
| revised copy exists | ✓ | ✓ | ✓ | ✓ |
| comments in the revised copy | ✓ 6 | ✓ 6 | ✓ 17 | ✓ 6 |
| `wrong_year`: 2020 in the copy's visible text | ✓ | ✓ | ✓ | ✓ |
| report: Bibliography section populated | ✓ | ✓ | ✓ | ✓ |
| **Total** | **18/18** | **18/18** | **19/19** | **18/18** |

Online lookup on this machine: `WebSearch` works (it runs on the provider's side);
`WebFetch` and any direct request (doi.org, api.crossref.org) are refused by the network
proxy. Every run therefore searched [3] by title, author and DOI, found nothing, and
wrote "possibile citazione inventata o errata" for the entry (the table row of its
citation says "non verificabile", "non accessibile"); the notes' first line says that
pages could not be fetched.

- **Run 1** (2026-11-25): first text. 2 min 33 s, $1.14, 17 turns.
  - The skill triggered (`help-me-write:revisione-bibliografia`), read the profile from
    `linee-guida.yaml`, ran `extract` and `bib`, and dispatched the reviewer as a
    subagent, which read both PDFs with `pdftext`.
  - 7 edits: the year as a tracked change and 6 comments ([1] 60% vs 30% with the quoted
    passage, [2] partially supported since the source covers eight companies only, [3]
    in the text and in the entry, [4], the 70% statement). All applied. No edit and no
    missing citation in the personal sentences.
  - The report: title lines, summary, Bibliography section, 4 questions.
  - One web query added topic words of the citing sentence ("continuous integration
    test selection quantum computing") to the title and author.
- **Between runs 1 and 2:** the prompt now says that a query holds only an entry's title,
  authors, year and DOI, no words or topic of the citing sentence. Skill wording: a PDF
  draft ends the Bibliography section with the proposals; a search for new sources, only
  on request, uses a few topic keywords, never sentences.
- **Run 2:** 2 min 38 s, $1.12, 17 turns. The same outcome; the queries held only title,
  author, year and DOI. A chained `mkdir … && extract` was refused by the headless
  allow-list; the agent then ran `extract -o` before creating the folder and got a
  traceback (`cli.emit` does not create the parent folder of `-o`), then recovered.
- **Combined run** (text of run 2): the `revisione` skill on `bozza-bib.docx`. 3 min 46 s,
  $2.04.
  - Both reviewers were dispatched in parallel as background subagents. 18 edits (11
    comments of the main reviewer, 7 of the bibliography reviewer) went into one `track`:
    all applied, no conflicts; then the formatted copy and its measure.
  - `rapporto.md` has the seven sections; "Revisori: principale (subagente), bibliografia
    (subagente)"; the Bibliografia section has the notes' table, the year correction,
    the missing citation and the consistency list; "Domande per te" ends with the 5
    bibliography questions.
  - The background bibliography subagent's first shell command (a chained `cat`/`find`)
    was denied, and it read the PDFs with its file-reading tool instead of `pdftext`,
    saying so in its notes; the pages it quoted are right.
  - The main reviewer commented on two personal sentences (contribution, a figure the
    host may consider confidential): its own remit, not a citation request.
- **Between the combined run and run 3:** the prompt says to read files with a
  file-reading tool, to use the shell only for `pdftext` (one PDF per command), and, if
  that is refused, to read the PDF with a tool that keeps its pages and say so.
- **Run 3** (final text): 2 min 28 s, $0.99, 14 turns. 18/18. `pdftext` for both PDFs,
  no refused read; queries only title, author, year and DOI.
