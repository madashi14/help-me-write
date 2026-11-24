# Scenario: review of a flawed draft (skill `revisione`, spec §9 case 2)

Checks that an agent with the plugin, asked to review a finished draft, finds every
defect inserted on purpose, delivers the corrections as tracked changes in a copy, and
leaves the original untouched.

## Setup

`<repo>` is the absolute path of this repository. Create a new, empty temporary folder
`<tmp>` and run:

```
python <repo>/tests/scenari/check_revisione.py --setup <tmp>/lavoro <tmp>/expected.json
```

`<tmp>/lavoro` then holds `bozza.docx` (built by `build_flawed_draft` in
`tests/fixtures/builders.py`) and `.help-me-write/linee-guida.yaml` (a copy of
`tests/fixtures/linee-guida-unibo.yaml`). `expected.json` stays outside the folder: the
agent must not see the list of defects.

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
claude -p --plugin-dir <repo> --add-dir <repo> --allowedTools "Bash(python:*) Bash(python3:*)" --permission-mode acceptEdits --output-format stream-json --verbose "Rivedi bozza.docx. Le linee guida in .help-me-write/linee-guida.yaml sono ancora valide, non serve rifarle. Per la copia formattata usa Times New Roman. Ora non rispondo alle domande sul contenuto: lasciale nel rapporto." > <tmp>/transcript.jsonl
```

- A headless run cannot answer the skill's questions, so the prompt answers them in
  advance: guidelines still valid, font of the formatted copy, no answers to the content
  questions (no second cycle).
- `--add-dir <repo>` lets the agent read the skill's files and the profiles;
  `--allowedTools` lets it run `hmw.py`. Interactively the user approves these instead.
- The skill may dispatch its reviewer as a subagent: that is the product under test.
- If `claude -p` is not usable, give a fresh subagent only the text of
  `skills/revisione/SKILL.md` (with its folder path) and the same request.

## Expected

Pass/fail, all checked by `check_revisione.py`:

1. `bozza.docx` is unchanged (sha256 from setup).
2. The newest folder `.help-me-write/revisioni/<YYYY-MM-DD-HHMM>/` has `extract.json`,
   `measure.json`, `edits-revisore.json`, `note-revisore.md` (sections `## Form`,
   `## Content`, `## Questions for the author`), `edits.json` and `rapporto.md`.
3. `measure.json` fails `font_family`, `chars_per_line`, `section:indice:present` and
   `section:introduzione:pages`.
4. `rapporto.md` mentions every defect: for each id at least one of its keywords
   (case-insensitive) from `expected.json`; it does not repeat the password.
5. `bozza-revisionato.docx` exists next to the original, has at least 5 tracked
   insertions (`w:ins`), and its visible text contains "installazione".

Also expected (read the report, the copies and the final answer):

- `bozza-revisionato-formattato.docx` exists (Times New Roman layout) and the report shows
  the form after formatting.
- The report is in Italian, follows `skills/revisione/modello-rapporto.md`, says that the
  bibliography reviewer was not run (until `revisione-bibliografia` exists) and lists
  questions for the author: personal contribution in "Attività svolte", expansion of
  CI/CD, where to cite Figura 2.
- No edit adds facts; no edit replaces a whole sentence or paragraph.
- The credential has a comment and the secret is not repeated in the report or the
  answer.

## Check

```
python <repo>/tests/scenari/check_revisione.py <tmp>/lavoro <tmp>/expected.json
```

Prints one line per check and exits 1 if any fails.

## Results

Runs with the command above (Claude Code 2.1.331, headless), each in a new folder made by
`--setup`. ✓ = pass.

| Check of `check_revisione.py` | Run 1 (2026-11-24) | Run 2 (2026-11-24) |
|---|---|---|
| original unchanged | ✓ | ✓ |
| review folder with `rapporto.md` | ✓ | ✓ |
| review files | ✓ | ✓ |
| `note-revisore.md` sections | ✓ | ✓ |
| `measure.json` flags the form defects | ✓ | ✓ |
| `font` | ✓ "calibri" | ✓ "calibri" |
| `chars_per_line` | ✓ | ✓ |
| `no_index` | ✓ | ✓ |
| `intro_length` | ✓ | ✓ |
| `typo_installaizone` | ✓ | ✓ |
| `typo_e_stato` | ✓ | ✓ |
| `typo_perche` | ✓ | ✓ |
| `typo_qual_e` | ✓ | ✓ |
| `typo_un_altro` | ✓ | ✓ |
| `acronym_ci_cd` | ✓ | ✓ |
| `figure_not_cited` | ✓ | ✓ |
| `personal_contribution` | ✓ "impersonal" | ✓ "impersonal" |
| `credential` | ✓ "password" | ✓ "password" |
| password not repeated in the report | ✓ | ✓ |
| revised copy exists | ✓ | ✓ |
| tracked insertions | ✓ 5 | ✓ 5 |
| visible text has "installazione" | ✓ | ✓ |
| **Total** | **22/22** | **22/22** |

- **Run 1:** first text of the skill. 3 min 15 s, $1.38. The skill triggered
  (`help-me-write:revisione`), dispatched the reviewer as a subagent, skipped the
  bibliography reviewer as not installed. 17 edits (6 replacements: the 5 typos and the
  deletion of the password; 12 comments), all applied; 12 questions. The formatted copy
  passes font, size, lines, characters and page numbers; index and introduction (now 7
  pages) remain, as the report says. Two chained shell commands were refused by the
  headless allow-list; the agent ran them one by one.
- **Between the runs:** no defect was missed, so no change for a defect. Wording fixes
  from self-review: run each command on its own; `--edits` only for the reviewers that
  ran; a PDF draft keeps `layout` for the recommended settings.
- **Run 2:** final text. 3 min 16 s, $1.31. Same outcome: 15 edits (6 replacements,
  10 comments, at most 2 per paragraph, longest `find` 7 words), all applied; the report
  says the bibliography was not run. Two chained commands refused again (an `echo` and a
  heredoc of the subagent), recovered.
