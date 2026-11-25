# Scenario: a report from scratch in Word (skill `help-me-write`, spec §9 case 1)

To be run later with an agent (Task 14: a single `claude -p` run). Not run in the
deterministic plan: `tests/test_acceptance.py` proves that the script pipeline alone
delivers this case; this scenario checks that the skills drive it.

An agent with the plugin, given a work folder of an invented internship (a Python
project with git history, an Italian CSV, a diary, the Unibo facsimile) and the answers
to the interviews in a file, writes the whole report in Word, passing every form check.

## Setup

`<repo>` is the absolute path of this repository. Create a new, empty temporary folder
`<tmp>` and run:

```
python <repo>/tests/scenari/check_accettazione.py --setup da-zero <tmp>/lavoro <tmp>/atteso <tmp>/plugin
```

- `<tmp>/lavoro` holds what `build_example_work` (`tests/fixtures/builders.py`) builds:
  `progetto/` (git, 3 commits dated 2026-09-15, 2026-10-10, 2026-11-05), `dati/metriche.csv`
  (BOM, `;`, decimal comma), `diario.md`, the facsimile `.docx`. No state.
- `<tmp>/plugin` is a copy of the plugin without `tests/` and `docs/`.
- `<tmp>/atteso` (outside the work folder) holds `expected.json`, `risposte.md` (the
  answers to the interviews) and `attesi/capitoli/` (chapters written by hand: the agent
  must not see them).

## Run

From `<tmp>/lavoro`:

```
claude -p --plugin-dir <tmp>/plugin --add-dir <tmp>/plugin --add-dir <tmp>/atteso/risposte.md --allowedTools "Bash(python:*) Bash(python3:*)" --permission-mode acceptEdits --output-format stream-json --verbose "Aiutami a scrivere la relazione di fine tirocinio da questa cartella, in Word, con le linee guida del facsimile (font Times New Roman). Non posso rispondere ora: leggi le mie risposte in <tmp>/atteso/risposte.md e considera approvati la struttura, il frontespizio e ogni capitolo appena scritto." > <tmp>/transcript.jsonl
```

- A headless run cannot answer questions, so the prompt gives the answers and the
  approvals in advance. If the agent still stops to ask, give a second `claude -p
  --continue` run with the answer; count it as a run of the scenario.
- If `claude -p` is not usable, give a fresh subagent only the text of
  `skills/help-me-write/SKILL.md` (with its folder path) and the same request.

## Expected

Check:

```
python <repo>/tests/scenari/check_accettazione.py --check da-zero <tmp>/lavoro <tmp>/atteso
```

It prints one line per check and exits 1 if any fails:

1. the state says `da-zero` and `word`, and every chapter is `approvato` or `revisionato`;
2. `.help-me-write/materiale.md` exists;
3. a `.docx` of the report exists in the work folder and the state has recorded it;
4. every `measure` check with the Unibo rules is OK (10-30 pages, 30-35 lines, 60-70
   characters, numbered pages, index, introduction 1-2 pages, conclusion 1-2 pages);
5. the title page has the student and the host company; the document has at least one
   figure, an introduction and a conclusion.

Also read the transcript and the document:

- no figure or number without a source in the files or in `risposte.md`; what is missing
  is `[DA VERIFICARE: ...]`;
- the chronology uses the git dates (September to November 2026), not the file dates;
- the figure comes from `dati/metriche.csv` through `chart` (a `.fonte.json` beside it);
- the facsimile and the CSV are unchanged; nothing from `progetto/` was executed;
- the agent never read `<tmp>/atteso/attesi`.

## Results

Not run yet.
