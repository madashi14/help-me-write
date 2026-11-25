# Scenario: review of a flawed draft (skill `revisione`, spec §9 case 2)

Checks that an agent with the plugin, asked to review a finished draft, finds every
defect inserted on purpose, delivers the corrections as tracked changes in a copy, and
leaves the original untouched.

## Setup

`<repo>` is the absolute path of this repository. Create a new, empty temporary folder
`<tmp>` and run:

```
python <repo>/tests/scenari/check_revisione.py --setup <tmp>/lavoro <tmp>/expected.json <tmp>/plugin
```

- `<tmp>/lavoro` then holds `bozza.docx` (built by `build_flawed_draft` in
  `tests/fixtures/builders.py`) and `.help-me-write/linee-guida.yaml` (a copy of
  `tests/fixtures/linee-guida-unibo.yaml`).
- `<tmp>/plugin` is a copy of the plugin (manifests, `skills/`, `profili/`, `scripts/`,
  README) without `tests/`, `docs/` and the repository's history. The agent under test
  gets only this copy, so it cannot read the list of defects (in the tests, the plan and
  this file).
- `expected.json` stays outside the folder too.

The defects of `bozza.docx` (ids as in `expected.json`):

| Id | Defect |
|---|---|
| `font` | Calibri 11 instead of Times New Roman, Courier or Helvetica 12 |
| `chars_per_line` | about 85 characters per line instead of 60–70 |
| `no_index` | no table of contents |
| `intro_length` | introduction of 4 pages instead of 1–2 |
| `typo_installaizone`, `typo_e_stato`, `typo_perche`, `typo_qual_e`, `typo_un_altro` | the typos "installaizone", "e stato", "perchè", "qual'è", "un'altro" |
| `acronym_ci_cd` | the acronym CI/CD never defined |
| `figure_not_cited` | Figura 2 never cited in the text |
| `personal_contribution` | chapter "Attività svolte" all impersonal and passive: no personal contribution |
| `credential` | "password: Alfa2024!" in a paragraph |

## Run

From `<tmp>/lavoro`:

```
claude -p --plugin-dir <tmp>/plugin --add-dir <tmp>/plugin --allowedTools "Bash(python:*) Bash(python3:*)" --permission-mode acceptEdits --output-format stream-json --verbose "Rivedi bozza.docx. Le linee guida in .help-me-write/linee-guida.yaml sono ancora valide, non serve rifarle. Per la copia formattata usa Times New Roman. Ora non rispondo alle domande sul contenuto: lasciale nel rapporto." > <tmp>/transcript.jsonl
```

- A headless run cannot answer the skill's questions, so the prompt answers them in
  advance: guidelines still valid, font of the formatted copy, no answers to the content
  questions (no second cycle).
- `--add-dir <tmp>/plugin` lets the agent read the skill's files and the profiles;
  `--allowedTools` lets it run `hmw.py`. Interactively the user approves these instead.
  Without permission for any other folder, a headless run reads nothing outside
  `<tmp>/lavoro` and the plugin copy.
- The skill may dispatch its reviewer as a subagent: that is the product under test.
- If `claude -p` is not usable, give a fresh subagent only the text of
  `skills/revisione/SKILL.md` (with its folder path) and the same request.

## Expected

Pass/fail, all checked by `check_revisione.py`:

1. `bozza.docx` is unchanged (sha256 from setup).
2. The newest folder `.help-me-write/revisioni/<YYYY-MM-DD-HHMM>/` has `extract.json`,
   `measure.json`, `edits-revisore.json`, `note-revisore.md` (sections `## Form`,
   `## Content`, `## Questions for the author`), `edits.json` and `rapporto.md`.
3. `rapporto.md` reports every defect:
   - form defects (`font`, `chars_per_line`, `no_index`, `intro_length`): a row of the
     table in the Form section names the measure check (`font_family`, `chars_per_line`,
     `section:indice:present`, `section:introduzione:pages`) and marks it ✗ in the next
     cell;
   - every other defect: one of its keywords from `expected.json` starts a word of the
     report, case-insensitively ("e stato" does not match "essere stato");
     `personal_contribution` counts only with passiv…, impersonal…, "prima persona" or
     "first person" in the Content section. Words that every report following the
     template contains (the checklist item "contributo personale", the measured font
     name) do not count.
   - The report does not repeat the password.
4. `bozza-revisionato.docx` exists next to the original, has at least 5 tracked
   insertions (`w:ins`), its visible text contains "installazione", and in the
   paragraph of the password the secret is deleted or a comment is anchored.

Also expected (read the report, the copies and the final answer):

- `bozza-revisionato-formattato.docx` exists (Times New Roman layout) and the report shows
  the form after formatting.
- The report is in Italian, follows `skills/revisione/modello-rapporto.md` and lists
  questions for the author: personal contribution in "Attività svolte", expansion of
  CI/CD, where to cite Figura 2. Its bibliography section comes from the bibliography
  reviewer (the draft has no citations: at most missing citations); in runs 1–3, made
  before `revisione-bibliografia` existed, it said "not run".
- No edit adds facts; no edit replaces a whole sentence or paragraph.
- The credential has a comment and the secret is not repeated in the report or the
  answer.

## Check

```
python <repo>/tests/scenari/check_revisione.py <tmp>/lavoro <tmp>/expected.json
```

Prints one line per check and exits 1 if any fails.

## Results

Claude Code 2.1.331, headless, each run in a new folder made by `--setup`. ✓ = pass.

- Runs 1–2 used the first version of this scenario: `--plugin-dir` and `--add-dir` on
  the repository itself, and a plain keyword search in the report. Review fix round 1
  made the checks stricter (✗ in the Form table, word-start keywords, the Content
  section for `personal_contribution`, the credential in the copy) and isolated the
  plugin copy.
- The outputs of runs 1–2, checked again with the new `check_revisione.py`, also pass
  22/22.
- Run 3 is the first run with the isolated setup above.

| Check of `check_revisione.py` (current) | Run 1 (2026-11-24) | Run 2 (2026-11-24) | Run 3 (2026-11-25) |
|---|---|---|---|
| original unchanged | ✓ | ✓ | ✓ |
| review folder with `rapporto.md` | ✓ | ✓ | ✓ |
| review files | ✓ | ✓ | ✓ |
| `note-revisore.md` sections | ✓ | ✓ | ✓ |
| `font`: `font_family` ✗ in the Form table | ✓ | ✓ | ✓ |
| `chars_per_line`: `chars_per_line` ✗ | ✓ | ✓ | ✓ |
| `no_index`: `section:indice:present` ✗ | ✓ | ✓ | ✓ |
| `intro_length`: `section:introduzione:pages` ✗ | ✓ | ✓ | ✓ |
| `typo_installaizone` | ✓ | ✓ | ✓ |
| `typo_e_stato` | ✓ | ✓ | ✓ |
| `typo_perche` | ✓ | ✓ | ✓ |
| `typo_qual_e` | ✓ | ✓ | ✓ |
| `typo_un_altro` | ✓ | ✓ | ✓ |
| `acronym_ci_cd` | ✓ | ✓ | ✓ |
| `figure_not_cited` | ✓ | ✓ | ✓ |
| `personal_contribution` (Content section) | ✓ "impersonal" | ✓ "impersonal" | ✓ "impersonal" |
| `credential` (report) | ✓ "password" | ✓ "password" | ✓ "password" |
| report does not repeat the secret | ✓ | ✓ | ✓ |
| revised copy exists | ✓ | ✓ | ✓ |
| tracked insertions | ✓ 5 | ✓ 5 | ✓ 5 |
| visible text has "installazione" | ✓ | ✓ | ✓ |
| credential deleted or commented in the copy | ✓ both | ✓ both | ✓ both |
| **Total** | **22/22** | **22/22** | **22/22** |

- **Run 1:** first text of the skill. 3 min 15 s, $1.38.
  - The skill triggered (`help-me-write:revisione`), dispatched the reviewer as a
    subagent, and skipped the bibliography reviewer as not installed.
  - 17 edits: 6 replacements (the 5 typos and the deletion of the password) and 12
    comments. All were applied; 12 questions.
  - The formatted copy passes font, size, lines, characters and page numbers. The index
    and the introduction (now 7 pages) remain, as the report says.
  - Two chained shell commands were refused by the headless allow-list; the agent ran
    them one by one.
- **Between runs 1 and 2:** no defect was missed, so nothing changed for a defect.
  Wording fixes from self-review:
  - run each command on its own;
  - `--edits` only for the reviewers that ran;
  - a PDF draft keeps `layout` for the recommended settings.
- **Run 2:** 3 min 16 s, $1.31. The same outcome.
  - 15 edits: 6 replacements and 10 comments, at most 2 per paragraph, longest `find`
    7 words. All were applied.
  - Two chained commands were refused, and the agent recovered.
- **Between runs 2 and 3 (review fix round 1):** skill changes:
  - the answers cycle now extracts and measures the newest `-revisionato` copy and
    reuses `layout.json`;
  - the bibliography reviewer gets `<work>` for its sources and `<rev>` for its outputs;
  - the report template asks for the exact check id and ✗/✓ from `ok`.

  Also the stricter checks and the isolated plugin copy described above.
- **Run 3:** isolated setup, 3 min 39 s, $1.49.
  - No tool call reached the repository, `tests/` or `docs/`.
  - 20 edits: 6 replacements and 15 comments, at most 3 per paragraph, longest `find`
    7 words. All were applied.
  - The report marks the four form checks ✗ in its Form table and gives the form after
    formatting (17 pages; font, lines, characters and page numbers pass; index and the
    7-page introduction remain). The bibliography is "non eseguita".
  - Two chained commands were refused, and the agent recovered.
