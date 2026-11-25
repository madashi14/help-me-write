---
name: struttura
description: Use when the outline and the title page of a document must be proposed and approved, or a partial draft must be compared with its guidelines, reorganized and brought within the page limit by proposed cuts - indice, frontespizio, piano di riorganizzazione, rientro nelle pagine, troppe pagine. Phases struttura and frontespizio of help-me-write.
---

# Structure and title page (struttura)

## Overview

Phase 5 of help-me-write. In `da-zero` it proposes the outline, fills the title page and
prepares the chapter files. In `bozza-parziale` it measures and reads the draft, compares
it with the guidelines, plans the reorganization, makes the working copy, fills the title
page and brings the draft within the page limit by cuts the user approves. Nothing is
invented, and every change to text the user wrote is delivered as a reviewable revision.

- Talk to the user in their language. Ask questions as plain questions to the user. A
  confirmation the user already gave in their request counts.
- Helper: `python <this skill's directory>/../../scripts/hmw.py <command>` (`python3`
  where `python` is not Python 3), written `hmw` below. Quote every path. Run each command
  on its own, not chained with `&&` or `;`.
- `<work>`: the work folder the entry skill [help-me-write](../help-me-write/SKILL.md)
  gives you (it holds the material and, for a LaTeX draft, the project folder), as an
  absolute path in every command. The fixed rules of that skill apply here.
- From `hmw state show "<work>" --json`: `<output>` is the output folder (`output`),
  `<draft>` the draft (`draft`), both relative to `<work>`. For a LaTeX draft,
  `<project>` is the draft's project folder and `<main>` its main file name
  (`<draft>` = `<project>/<main>`); `<output>` is then the working copy
  `<project>-help-me-write`. In a new LaTeX project `<main>` is `main.tex`. `<name>` is
  the document name: `<output>` without `-help-me-write`.
- If a command exits 3, run `hmw doctor` and show its install hint. Exit 2: show the
  message, it names the field or file at fault.

## Before you start

1. Read the state, `<work>/.help-me-write/linee-guida.yaml`,
   `<work>/.help-me-write/materiale.md`, the body of `<work>/.help-me-write/progetto.md`
   (`## Decisioni`) and the profile
   `<this skill's directory>/../../profili/<profile>.md` (`## Typical structure`,
   `## Writing budget`).
2. **Layout** (before D1; for a draft, right after the measure of P1). If
   `<work>/.help-me-write/layout.json` is missing, choose the font: the draft's own font
   (the `font_family` check of the measure names it) when the guidelines allow it,
   otherwise ask the user, proposing the first of `fonts`. Then run
   `hmw layout --rules "<work>/.help-me-write/linee-guida.yaml" --font "<font>" -o "<work>/.help-me-write/layout.json"`.
   It holds margins, line pitch, `target_lines` (lines per page) and `target_chars`
   (characters per line). If it refuses (a font of no known family, no `font_size_pt`),
   tell the user why and get the missing value into the guidelines with the
   [linee-guida](../linee-guida/SKILL.md) skill (marked `# user`), then run it again.
3. **Where to start.** `da-zero`: `outline_approved` false → D1; otherwise D3 (a title
   page already made, `<work>/<output>/main.tex` or
   `<work>/.help-me-write/frontespizio.docx`, is shown again, not made again).
   `bozza-parziale`: `outline_approved` false → P1; no "copia di lavoro" line in
   `## Decisioni` → P4; no "frontespizio approvato" line → P5; otherwise P6 (a `tagli.md`
   under `<work>/.help-me-write/revisioni/` not yet marked applied or declined in
   `## Decisioni` is shown again, not recomputed). Write those two marker lines with
   these words, whatever the user's language.

## Mode `da-zero`

**D1. Propose the outline.** Start from the profile's `## Typical structure` and from
`materiale.md` (Sintesi, Mappa del materiale, Cronologia):
- introduction; body chapters in chronological or development order, one per phase or
  activity the material documents; conclusion; annexes only for material that calls for
  them;
- for each chapter: an id (lowercase letters, digits and hyphens, no number: the order
  is the list's), the title in the document's language, the kind (`introduzione`,
  `corpo`, `conclusione`, `allegato`), the material that supports it (paths from the
  Mappa del materiale) and its page budget from `## Writing budget`;
- a chapter with no material behind it is not proposed: the gap becomes a question.

Show it as a table and ask the user to approve or change it.

**D2. Record it.** Write `<work>/.help-me-write/indice.md` (the approved table: id,
title, kind, material, pages) and `<work>/.help-me-write/indice.json`, the list in
document order:

```json
[{"id": "introduzione", "title": "Introduzione", "kind": "introduzione"},
 {"id": "contesto", "title": "Il contesto aziendale", "kind": "corpo"},
 {"id": "conclusioni", "title": "Conclusioni", "kind": "conclusione"}]
```

Run `hmw state outline "<work>" --from "<work>/.help-me-write/indice.json"`, then
`hmw state set "<work>" outline_approved=true`. A later change: edit both files and run
`state outline` again (it keeps the progress of the ids that remain).

**D3. Title page.** The values: if `linee-guida.yaml` has `title_page_template`, read
the model with `hmw extract "<work>/<template>"` and list every value it asks for (each
placeholder or blank: name, student number, course and its code, host, tutor, academic
year, title); without a model, the keys of the LaTeX `generico` page below. Ask the user
for all of them in one grouped question. Never deduce a name, a student number or a
code, even from the material; propose only the title, from the outline, for the user to
confirm. A value not given stays `[DA VERIFICARE: <what>]`.
- **Word:** write `<work>/.help-me-write/frontespizio-valori.json` as
  `{"start_at": "<first text of the title page in the model>", "replace": [{"find": "<placeholder, copied exactly from the extract>", "with": "<value>"}]}`
  (`start_at` drops the pages before the title page, such as instructions; leave it out
  when the model starts with it). Run
  `hmw titlepage "<work>/<template>" --values "<work>/.help-me-write/frontespizio-valori.json" -o "<work>/.help-me-write/frontespizio.docx"`.
  Exit 1: the texts under `not found` differ from the model; copy them exactly from the
  extract and run again with a new output name (`frontespizio-2.docx`). Then run
  `hmw extract "<work>/.help-me-write/frontespizio.docx"` and show the user the text for
  approval. No model: ask the user whether they have a title page as `.docx` (fill it the
  same way) or go without one (no `title_page` in the manifest).
- **LaTeX:** write `<work>/.help-me-write/frontespizio-valori.json`, a JSON object with
  the values given: for the Unibo facsimile (it starts with "ALMA MATER STUDIORUM")
  `--title-page unibo`, keys `anno_accademico`, `studente`, `matricola`, `corso`,
  `codice_corso`, `struttura`, `argomento`, `referente`; for any other model or none
  `--title-page generico`, keys `titolo`, `autore`, `istituzione`, `data`, and tell the
  user that only the Unibo model is reproduced exactly. A key left out becomes
  `[DA VERIFICARE: <key>]` in the page. Then run
  `hmw latex-init "<work>/<output>" --layout "<work>/.help-me-write/layout.json" --chapters "<work>/.help-me-write/indice.json" --values "<work>/.help-me-write/frontespizio-valori.json" --title-page unibo --language it`
  (`--language en` for an English document; add `--bibliography` when the user has
  sources to cite, and copy the entries of their `.bib` into the new
  `<work>/<output>/bibliografia.bib`). It writes `main.tex`, `frontespizio.tex`, one
  `capitoli/NN-<id>.tex` per chapter and `immagini/`. Compile and show:
  `hmw measure "<work>/<output>/main.tex" --rules "<work>/.help-me-write/linee-guida.yaml" --workdir "<work>/.help-me-write/pdf" -o "<work>/.help-me-write/misure/progetto.json"`;
  the `pdf` of the JSON has the title page on page 1: give the user its path. Failed
  checks are expected here, the chapters are empty. To change a value, edit its
  `\newcommand` line in `<work>/<output>/main.tex` and compile again. On approval run
  `hmw state record "<work>" "<work>/<output>"`.

**D4. Word: chapter files.** Create `<work>/.help-me-write/capitoli/` with one file
`<id>.md` per chapter holding only its heading (`# <title>`), and
`<work>/.help-me-write/manifest.yaml` in the format of
[formato-capitoli.md](../scrittura-capitolo/formato-capitoli.md):

```yaml
layout: layout.json
title_page: frontespizio.docx
language: it
chapters:
  - capitoli/introduzione.md
  - capitoli/contesto.md
  - capitoli/conclusioni.md
```

Add `bibliography:` (path relative to `<work>/.help-me-write/`) when the user has a `.bib`.

**D5. Done.** Run `hmw state set "<work>" title_page_approved=true` and add the outline
and the title page to `## Decisioni`, one line each.

## Mode `bozza-parziale`

**P1. Measure and read.** Run
`hmw measure "<work>/<draft>" --rules "<work>/.help-me-write/linee-guida.yaml" --workdir "<work>/.help-me-write/pdf" -o "<work>/.help-me-write/misure/bozza.json"`
(exit 1 only means that some check failed; exit 2 or 3: show the error and stop) and
`hmw extract "<work>/<draft>" -o "<work>/.help-me-write/misure/bozza-testo.json"`.
Then read the chapters one at a time and note for each: what it covers, its pages
(`sections` of the measure: `start_page`–`end_page`), the numbers it states and whether
"Dati e numeri" of `materiale.md` has them, whether the personal contribution is
visible, what is missing.

**P2. Comparison table.** One row per rule of `linee-guida.yaml` (length, fonts, size,
lines per page, characters per line, page numbers, each section and its length, each
content rule, title page) and per item of the profile's `## Content checklist`: rule →
state in the draft → action, the action being keep, fix, write or cut (in Italian
tenere, correggere, scrivere, tagliare). States come from the measure checks and from
your reading. Show it to the user. Shape only:

```
| Regola                   | Nella bozza            | Azione                              |
|--------------------------|------------------------|-------------------------------------|
| 10–30 pagine circa       | 36 pagine              | tagliare                            |
| 60–70 caratteri per riga | 73–78                  | correggere: impaginazione nella copia |
| Conclusione 1–2 pagine   | capitolo vuoto         | scrivere                            |
```

**P3. Reorganization plan.** The outline of the finished document: the draft's chapters
in their order, each with its file and status `scritto`; each empty or missing part
(`empty_parts` of `detect`, a required section that is absent) with status `da-fare`.
Ids come from the file names (`06_conclusioni.tex` → `06-conclusioni`; Word: from the
headings). Add each chapter's actions from P2 and its page budget
(`## Writing budget`). Every change to the draft's own text (cuts, a title, the order of
the `\include` lines) is applied later as a revision (see "Revision of existing text"),
never by rewriting the files. Ask the user to approve the plan, then:
1. write `indice.md` and `indice.json` as in D2 and run
   `hmw state outline "<work>" --from "<work>/.help-me-write/indice.json"`;
2. for each chapter with text,
   `hmw state chapter "<work>" <id> --status scritto --source "<work>/<output>/<file inside the project>"`,
   and for an empty file the same without `--status` (LaTeX: the chapter's path inside
   the working copy of P4, the same as in the project; Word: the working `.docx`,
   `<work>/<output>/<name>.docx`);
3. `hmw state set "<work>" outline_approved=true`.

**P4. Working copy.** If P2 found lines per page or characters per line out of the
rules, propose to fix the layout in the copy (the user's files stay as they are) and ask.
- **LaTeX**, accepted: `hmw format "<work>/<draft>" --layout "<work>/.help-me-write/layout.json" -o "<work>/<output>"`;
  declined: `hmw format "<work>/<draft>" -o "<work>/<output>"` (a plain copy).
- **Word**, accepted: `hmw format "<work>/<draft>" --layout "<work>/.help-me-write/layout.json" -o "<work>/<output>/<name>.docx"`;
  declined: no copy yet, the draft is the base of the first revision.

If `changes` says "font not changed", tell the user that the draft's font is not an
allowed one; changing it is their decision (a `\setmainfont` edit in P6). Record the copy:
LaTeX `hmw state record "<work>" "<work>/<output>"`, Word
`hmw state record "<work>" "<work>/<output>/<name>.docx"` (nothing to record when there
is no copy). Add "copia di lavoro: <path> (impaginazione corretta, or invariata)" to
`## Decisioni` and measure the copy (P6.1): the correct layout usually adds pages; tell
the user how many.

**P5. Title page values.** In LaTeX the values live in `\newcommand` lines (usually in
the preamble of `<main>`, such as `\NomeStudente` or `\MatricolaStudente`). List each
with its value in the copy and ask the user, in one grouped question, for every
placeholder and to confirm the values already filled. Never deduce name, student number
or codes. Write the answers into those lines of `<work>/<output>/<main>` (the copy, never
the draft), escaping `& % $ # _ { } ~ ^ \`; compile with the measure command of P6.1
and give the user the PDF path (`pdf` in the JSON, title page on page 1). Word: write the
values file as in D3 without `start_at` and fill the placeholders of the copy's title
page with
`hmw titlepage "<work>/<output>/<name>.docx" --values "<work>/.help-me-write/frontespizio-valori.json" -o "<work>/<output>/<name>-v2.docx"`
(the whole document is kept). Check `replaced`: a placeholder in a text box counts 2,
because Word stores two copies of it; a higher count means the text also occurs in the
body: use a longer `find`. On approval record the copy (LaTeX
`hmw state record "<work>" "<work>/<output>"`; Word
`hmw state record "<work>" "<work>/<output>/<name>-v2.docx"`) and add "frontespizio
approvato" to `## Decisioni`.

**P6. Fit into the pages.**
1. Measure the working copy:
   `hmw measure "<work>/<output>/<main>" --rules "<work>/.help-me-write/linee-guida.yaml" --workdir "<work>/.help-me-write/pdf" -o "<work>/.help-me-write/misure/copia.json"`
   (Word: the working `.docx`). If `pages` and every `section:<name>:pages` check pass,
   with room for the parts still to write, there is nothing to cut: go to P6.7.
2. **Target.** The maximum of `pages`. Read the sentence that sets it in the guidelines
   (`hmw extract "<guidelines file>"`, the file named by `source` in `linee-guida.yaml`,
   or a comment there): if it qualifies the
   limit as approximate ("circa", "indicativamente", "about"), say so and let the user
   choose the target (the maximum itself or a little more). If the file is not at hand,
   ask whether the limit is strict. Record the target in `## Decisioni`.
3. **Lines to remove** = (pages − target) × lines per page of the layout
   (`target_lines` of `layout.json`; without it the typical `body_lines` of full pages in
   the measure). Pages = the measured pages plus what the `da-fare` parts will add (their
   budget minus what they take now: an empty chapter already takes its heading page).
   A part over its own limit (a failed `section:<name>:pages`) must lose its excess
   whatever the total. Example: 41 pages, an empty conclusion budgeted at 2 pages that
   takes 1 now, target 30, 33 lines per page: (41 + 1 − 30) × 33 = 396 lines.
4. **Proposed cuts**, as a table: chapter | what (section, paragraph or figure, with file
   and line) | lines saved, about | why. Look for: repetitions; general explanations of
   tools or theory, to replace with a citation of a source already in the `.bib` or the
   user's folder; long lists; figures that duplicate a table; parts that could move to
   the annexes, only if the user confirms that annexes do not count. Lines saved = the
   characters removed divided by `target_chars`, plus the partial last line of each
   removed paragraph; a figure saves its height. Add the total against the lines to
   remove. Never cut the personal contribution, the results with their numbers, or what
   the author's notes ask to keep (a distinction they want explicit stays).
5. **Rules.** To gain pages, never reduce the font size, the margins or the line
   spacing beyond the limits of the guidelines, and do not change the layout. Never
   write new text that adds facts: condensing reuses only sentences and facts already
   in the draft.
6. Create `<rev>` = `<work>/.help-me-write/revisioni/<YYYY-MM-DD-HHMMSS>/` (local time,
   e.g. from `python -c "import datetime; print(datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S'))"`),
   write the table, the target and the totals to `<rev>/tagli.md`, add "tagli proposti:
   <rev>/tagli.md" to `## Domande aperte`, show the table and ask which cuts to apply.
   Apply the approved ones as in "Revision of existing text": an EditSet
   `<rev>/tagli.json`, applied by track into a new copy, and in LaTeX texdiff for the PDF
   of the differences. Measure the new copy; still over the target: propose another round from
   P6.4, or let the user decide. Record the outcome in `## Decisioni` (applied, partly,
   or declined).
7. Run `hmw state set "<work>" title_page_approved=true`. For a partial draft it is set
   only now, so that a resumed session does not skip the fit into the pages.

**P7. What follows.** Tell the user: the `da-fare` parts (the conclusions, for example)
get their interview and writing, the draft's chapters come one by one to approval, then
the review. The entry skill routes them from `next.phase`.

**P8. Word draft: what differs.** Comparison, formatted copy and cuts work as above, the
cuts as tracked changes in a new `.docx`. The track command replaces text inside
paragraphs; it does not insert chapters: say so to the user. New or missing chapters are
written as sources (`<work>/.help-me-write/capitoli/<id>.md`) and assembled with the same
layout,
from `<work>/.help-me-write/manifest-capitoli-nuovi.yaml` (only those chapters,
`toc: false`, plus `title_page` when the draft lacks one and the guidelines have a
model), by
`hmw assemble "<work>/.help-me-write/manifest-capitoli-nuovi.yaml" -o "<work>/<output>/<name>-capitoli-nuovi.docx"`,
for the user to paste into the document.

## Revision of existing text

Every change to text the user wrote (cuts, a fix they asked for in a draft chapter, a
title) and every change to an output they edited by hand goes this way, never by
rewriting a file.
1. `<rev>` as in P6.6. Run `hmw extract "<work>/<output>/<main>" -o "<rev>/testo.json"`
   (Word: the working `.docx`): each LaTeX line with `file` and `line`, each Word
   paragraph with its `id`, and its text.
2. Write the EditSet (format: the docstring of
   [edits.py](../../scripts/helpmewrite/edits.py)), e.g. `<rev>/tagli.json`:

   ```json
   {"author": "help-me-write", "edits": [
     {"file": "capitoli/02_studio.tex", "line": 41, "find": "<the exact text of that line>",
      "replace": "", "reason": "repeats section 2.1 (approved cut 3)", "by": "revisore"},
     {"file": "capitoli/02_studio.tex", "line": 57, "find": "<a sentence of the line>",
      "replace": "<a shorter sentence made only of words already there>",
      "reason": "condensed (approved cut 4)", "by": "revisore"}]}
   ```

   `find` is copied from the extract and occurs once at that line. A LaTeX edit covers
   one source line: `find` and `replace` hold no newline, so deleting a five-line
   paragraph takes five edits. Word edits use `"paragraph": <id>` instead of `file` and
   `line`. `by` is `revisore` (the format accepts only `revisore` and `bibliografia`).
3. Apply it to a new version:
   - LaTeX:
     `hmw track "<work>/<output>/<main>" --edits "<rev>/tagli.json" -o "<work>/<base>-v2-help-me-write" --json`,
     then
     `hmw texdiff "<work>/<output>/<main>" "<work>/<base>-v2-help-me-write/<main>" -o "<work>/<base>-v2-differenze.pdf"`.
     `<base>` is the first working copy's name without `-help-me-write` (`<project>`, or
     `<name>` in `da-zero`); use the first free `-v<N>-`. The name keeps ending in
     `-help-me-write`, so `detect` and `material` skip it.
   - Word:
     `hmw track "<work>/<output>/<name>.docx" --edits "<rev>/tagli.json" -o "<work>/<output>/<name>-v2.docx" --json`
     (the newest version as input, the first free `-v<N>` as output).
   - Exit 0: all applied. Exit 1: the copy is written, the edits under `failed` and
     `conflicts` were not applied: fix their `find` from the extract in another round, or
     list them for the user. Exit 2: nothing written; read the message (an invalid
     EditSet, or an output that exists: take the next free name).
4. Measure the new version and show the user the pages and the PDF of the differences
   (LaTeX) or the tracked changes, which they accept or reject in Word or LibreOffice.
5. When the user accepts it, it becomes the working copy. LaTeX:
   `hmw state set "<work>" output="<work>/<base>-v2-help-me-write"`, then for each
   chapter `hmw state chapter "<work>" <id> --source "<work>/<base>-v2-help-me-write/<file>"`,
   then `hmw state record "<work>" "<work>/<base>-v2-help-me-write"`. Word: record the
   new `.docx` and point the chapters' `--source` to it. Add a line to `## Decisioni`.

## Common mistakes

- Cutting by shrinking the font, the margins or the line spacing, or by tuning the
  layout: the layout is the one the guidelines ask for.
- Condensing with new sentences that add or round facts.
- Rewriting a file of the draft, or of a copy the user edited, instead of a revision.
- Deducing name, student number or codes for the title page.
- Treating "30 pagine circa" as a hard limit without telling the user, or leaving out
  the pages the empty parts will need.
- A path in a command without `<work>/` or `<rev>/` in front, or a state path outside
  `<work>`.
- Setting `title_page_approved=true` for a partial draft before the fit into the pages.
