# Scenario: partial LaTeX draft, real case (spec §9 case 3, the only `claude -p` run of Part 2)

Checks that an agent with the plugin, asked to continue a real partial internship report,
reads the material, builds the working copy with the corrected layout, fills the title
page with the values it is given, writes the missing conclusions from the author's
answers without inventing numbers, keeps the author's own distinctions, and proposes
(does not apply) the cuts that bring the document within 30 pages. The user is replaced
by `risposte.md`.

The draft is the public repository https://github.com/madashi14/relazione_tirocinio: the
LaTeX project `relazione_tirocinio/Relazione_Tirocinio/` (chapters 1–5 written, chapter 6
empty, title page with placeholders), three archives `relazione_tirocinio/{script,rf,
ml_physics_rf_v2}.zip` and `travi.ipynb` at the root. It is never copied into this
repository: `--setup` clones it into a temporary folder.

## Requirements

- Network (the clone), `git`, `latexmk` and XeLaTeX with the fonts of the draft:
  "Times New Roman" must be known to `fc-list`. On Linux it is not: create the test copy
  with `python tests/strumenti/font_times_prova.py --dest <dir>` and run `fc-cache -f`
  (setup warns when the font is missing).
- `texlive-lang-italian`, `texlive-latex-extra`, `texlive-science` (Debian names).

## Setup

`<repo>` is the absolute path of this repository, `<tmp>` a new, empty folder:

```
python <repo>/tests/scenari/check_bozza_parziale.py --setup <tmp>
```

- `<tmp>/lavoro`: the clone (`GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1`) without `.git`,
  `main.pdf` and the LaTeX artefacts (`*.aux`, `*.toc`, `*.out`, `*.log`,
  `*.synctex.gz`), plus `.help-me-write/linee-guida.yaml` (a copy of
  `tests/fixtures/linee-guida-unibo.yaml`: Part 1 already proved the guidelines phase).
- `<tmp>/risposte.md`: the answers of the user, all fictional values declared as such:
  - the guideline says "tra 10 e 30 pagine circa" and the user wants the 30 pages (the
    `source` of the fixture does not exist in the work folder, so the agent cannot read
    the sentence anywhere else);
  - timeline: May–October 2026 as in chapter 1 of the draft (the archive dates, 2 October–24 November 2026, are those of the outputs and of the upload);
  - title page: "Studente Prova", matricola "0000000000", code "0000", and so on;
  - the interview of the conclusions: objectives reached, what was learned, limits,
    consistent with chapters 1–5 and without new numbers;
  - the approvals: outline and working copy with the corrected layout, title page
    values, the conclusions as written, "approvo l'elenco dei tagli proposti ma non
    applicarli".
- `<tmp>/plugin`: a copy of the plugin without `tests/` and `docs/` (as in Part 1).
- `<tmp>-verifica/`: sha256 of every file of `lavoro` and the untouched clone, as
  reference. It is outside `<tmp>`, so the agent is not given it.

## Run

From `<tmp>/lavoro`:

```
claude -p --plugin-dir <tmp>/plugin --add-dir <tmp>/plugin --add-dir <tmp> --allowedTools "Bash(python:*) Bash(python3:*)" --permission-mode acceptEdits --output-format stream-json --verbose "<prompt>" > <tmp>/transcript.jsonl
```

- `--add-dir <tmp>` lets the agent read `risposte.md` (and the plugin copy, and `lavoro`);
  `--allowedTools` lets it run `hmw.py`; interactively the user approves these instead.
- Restrictive allow-lists reject chained commands: the prompt says "one command per
  call".
- Not run in the tests of the repository: it takes a real session (about the cost of
  runs 1–4 of `revisione.md`, a few dollars), so it runs once, after the review of the
  task, and again only for the fixes of the final review.

The prompt (in Italian, one line in the real command):

```
Usa help-me-write sulla cartella di lavoro <tmp>/lavoro: la bozza LaTeX della relazione
è in relazione_tirocinio/Relazione_Tirocinio e devo completarla (mancano le conclusioni e il
frontespizio). Le linee guida in .help-me-write/linee-guida.yaml sono già valide, non
rifarle. Non posso rispondere alle tue domande: tutte le mie risposte e le mie
approvazioni sono in <tmp>/risposte.md, leggile da lì invece di attendere me e dai per
approvato ciò che il file approva (valori del frontespizio, indice, copia di lavoro
con impaginazione corretta, conclusioni). Procedi con il flusso della bozza parziale
fino a quando le conclusioni sono scritte e hai proposto i tagli per rientrare nelle 30
pagine: l'elenco dei tagli va solo proposto, non applicarlo, e fermati prima della
revisione finale. Esegui un solo comando per volta, senza concatenarli con && o ;, e non
modificare mai i file originali: lavora sulla copia di lavoro e in .help-me-write/.
```

- The prompt follows the order of the `struttura` skill (controller ruling R12-2): the
  cuts are proposed before the missing parts are written, because the cut budget
  reserves their length. So the run is expected to end with both the conclusions written
  and the cuts proposed.
- The skill may dispatch subagents: that is the product under test.
- If `claude -p` is not usable, give a fresh subagent only the text of
  `skills/help-me-write/SKILL.md` (with its folder path) and the same request.

## Expected

Pass/fail, all checked by `check_bozza_parziale.py` (the work folder is `<tmp>/lavoro`;
the state is read with `helpmewrite.state`):

1. **Originals unchanged:** every file of `lavoro` (outside `.help-me-write/`) has the
   sha256 recorded at setup.
2. **State:** `.help-me-write/progetto.md` is valid, `mode: bozza-parziale`,
   `format: latex`.
3. **Material:** `materiale.md` cites `script.zip`, `rf.zip`, `ml_physics_rf_v2.zip` and
   `travi.ipynb`, has a section "Cronologia" and a section "Note dell'autore" that reports
   the batch MAPDL (subprocess and APDL files) versus PyMAPDL distinction of the author's
   `LEGGIMI.txt`.
4. **Layout:** the working copy (the `output` of the state, `<project>-help-me-write`)
   has the layout block (`% help-me-write: impaginazione (inizio)`), and `hmw measure`
   on its `main.tex` gives `chars_per_line`, `lines_per_page` and `page_numbers` OK.
5. **Conclusions:** `06_conclusioni.tex` of the copy has at least 1500 characters of
   text, and every number in it (regex `\d+(?:[.,]\d+)?`, after dropping comments,
   `\label`/`\ref`/`\cite`/`\includegraphics`, other commands and optional arguments)
   occurs in chapters 1–5 of the copy, in `materiale.md` or in `risposte.md`.
6. **Title page:** the `\newcommand` lines of the copy's `main.tex` hold the values of
   `risposte.md` (`\NomeStudente`, `\MatricolaStudente`, `\CorsoDiStudio`, `\CodiceCorso`,
   `\StrutturaOspitante`, `\TutorOspitante`, `\AnnoAccademico`).
7. **Author's distinction:** chapter 3 of the copy still contains "batch".
8. **Cut proposal:** if the pages of the copy exceed 30 (expected: the corrected layout
   adds pages), a table with chapter and lines is in the body of `progetto.md` or in
   `.help-me-write/revisioni/*/tagli*.md`, and no version copy (`*-v<N>-help-me-write`)
   exists: the cuts were proposed, not applied. A copy within 30 pages passes without a
   table.

Also expected (read the transcript, the files and the final answer):

- No question is left to the user for what `risposte.md` answers; nothing in the
  conclusions that is not in a listed file (a gap is `[DA VERIFICARE: …]`).
- The conclusions are in Italian, in the first person like chapters 1–5, and read as the
  chapter 6 of that report.
- The agent does not touch `main.pdf` of the reference clone or run the author's scripts,
  notebook or archives (they are only listed and read as text).
- Every `hmw` command used absolute, quoted paths; refused chained commands are noted.

## Check

```
python <repo>/tests/scenari/check_bozza_parziale.py --check <tmp>
```

Prints PASS or FAIL with the reason per check and exits 1 if any fails. It compiles the
copy with `hmw measure` (a temporary folder for the PDF).

## Results

Not run yet: the controller runs it once after the review of Task 14 and records the
outcome and cost here ("Esecuzione 1").
