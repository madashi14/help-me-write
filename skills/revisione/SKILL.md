---
name: revisione
description: Use when the user wants a finished draft (docx, tex or pdf) reviewed or corrected against guidelines - rivedi, revisiona, revisione, correggi la bozza, controlla la relazione, review my draft, proofread, check my report against the rules - to get tracked corrections, a report and questions for the author. Not for writing, completing or restructuring a document from notes.
---

# Review (revisione)

## Overview

Review a finished draft against its guidelines: `hmw` measures the form, an independent
reviewer checks language and content, its corrections go into a copy as tracked changes,
and a report lists what changed, what still breaks the rules and the questions only the
author can answer. The original is never modified. Nothing is invented: what a reviewer
cannot correct from the document itself becomes a question.

- Talk to the user in their language. Corrections are in the document's language.
- A confirmation the user already gave in their request ("the guidelines are still
  valid", "use Times New Roman") counts: do not ask for it again.
- Helper: `python <this skill's directory>/../../scripts/hmw.py <command>` (`python3`
  where `python` is not Python 3), written `hmw` below. Quote every path: names with
  spaces and accents are common. Run each command on its own, not chained with `&&` or
  `;`: permission rules match single commands.
- `<doc>` is the reviewed document; `<work>` its folder (for LaTeX, the folder of the main
  `.tex`), where `.help-me-write/` lives. Each review writes its files in a new folder
  `<work>/.help-me-write/revisioni/<YYYY-MM-DD-HHMM>/` (local time, e.g. from
  `python -c "import datetime; print(datetime.datetime.now().strftime('%Y-%m-%d-%H%M'))"`),
  written `<rev>` below.
- Copies go next to the original and never replace a file: when a name is taken, add
  `-2`, `-3`, … before the extension (`bozza-revisionato-2.docx`).

| Draft | Corrected copy | Also |
|---|---|---|
| `<name>.docx` | `<name>-revisionato.docx`: tracked changes and comments | `<name>-revisionato-formattato.docx` (step 8) |
| main `.tex` in folder `<name>` | folder `<name>-revisionato` beside folder `<name>` | `<name>-differenze.pdf` beside it |
| `.pdf` | none: report only (see below) | |

## Steps

1. **Find the document and check the tools.** Use the file the user names. Otherwise
   look in the current folder for `.docx`, `.tex` and `.pdf` drafts, leaving out the
   guidelines, files ending in `-revisionato`, `-formattato` or `-differenze`, and
   `.help-me-write/`. One: use it. Several: ask the user which. For LaTeX use the main
   file (the one with `\documentclass`). Run `hmw doctor`. Needed: every Python package;
   `soffice` for `.docx`; `latexmk` and `latexdiff` for `.tex`. If one is missing, tell the
   user how to install it (the `doctor` output says) and stop.
2. **Guidelines.** Follow the [linee-guida](../linee-guida/SKILL.md) skill with `<work>` as
   its work folder: it asks whether an existing `.help-me-write/linee-guida.yaml` is still
   valid, or builds it. Its `document_type` names the profile
   `<this skill's directory>/../../profili/<document_type>.md` (`generico.md` if that file
   does not exist) and `language` the document's language.
3. **Extract and measure.** Create the folder `<rev>`, then run:
   - `hmw extract "<doc>" -o "<rev>/extract.json"`
   - `hmw measure "<doc>" --rules "<work>/.help-me-write/linee-guida.yaml" --workdir "<rev>/pdf" -o "<rev>/measure.json"`:
     exit 1 only means that some check failed; on exit 2 or 3 show the error and stop.

   If `font_family`, `font_size`, `chars_per_line` or `lines_per_page` failed, ask the user
   which allowed font the formatted copy should use, proposing the first of `fonts` in the
   guidelines, then run
   `hmw layout --rules "<work>/.help-me-write/linee-guida.yaml" --font "<font>" -o "<rev>/layout.json"`.
   Its font, size, margins and line pitch are the settings the report recommends. If
   `layout` refuses (a font of no known family, no `font_size_pt`), tell the user why:
   there will be no formatted copy.
4. **Bibliography reviewer, in parallel.** When the profile has a `## Citation needs`
   section, or the document has citations or a bibliography section, also run steps 3
   and 4 of the [revisione-bibliografia](../revisione-bibliografia/SKILL.md) skill, with
   `<work>` as its work folder (its sources are the PDFs there), this `<rev>` for its
   outputs, and the guidelines and profile of step 2. Its step 3 writes `<rev>/bib.json`
   (`extract.json` exists already); its reviewer, dispatched with its own prompt, writes
   `<rev>/edits-bibliografia.json` and `<rev>/note-bibliografia.md`. Its own track and
   report steps are not run: steps 6 and 9 here do them. Dispatch its reviewer at the
   same time as the one of step 5, not after it. If that skill is not installed, skip it:
   the report's bibliography section then says "not run".
5. **Main reviewer.** Take `./prompt-revisore.md`, fill its placeholders with absolute
   paths (extract, measure, guidelines, profile, the two outputs in `<rev>`), the
   document's language, the user's language and `{ANSWERS}` = none. Dispatch a fresh
   subagent with the filled prompt as its whole task: no conversation, no summary of how
   the document was written, no opinion of yours. If you cannot dispatch subagents, do
   the review yourself, reading only the files the prompt lists. It writes
   `<rev>/edits-revisore.json` and `<rev>/note-revisore.md`.
6. **Apply the edits.** When every reviewer has finished, write `<rev>/edits.json`, the
   union for the record: one EditSet (`"author": "help-me-write"`) with the edits of
   `edits-revisore.json` followed by those of `edits-bibliografia.json` (when step 4
   ran), unchanged. Then apply them with one command, one `--edits` per reviewer that
   ran:

   `hmw track "<doc>" --edits "<rev>/edits-revisore.json" --edits "<rev>/edits-bibliografia.json" -o "<copy>" --json`

   - Exit 0: all applied. Exit 1: the copy is written; some edits failed or conflicted.
     Exit 2: an edits file is invalid: fix only what the listed problems name (a missing
     `reason`, an unknown key), never what an edit says, and run it again.
   - LaTeX: `<copy>` is the folder `<name>-revisionato`; then run
     `hmw texdiff "<doc>" "<copy>/<main file name>" -o "<name>-differenze.pdf"`. Comments
     are not written into LaTeX sources: the report lists them with file and line.
7. **Edits not applied.** Every entry of `failed` and `conflicts` carries its edit. Each
   goes in the report's "To fix by hand": where, the text, the intended change or
   comment, and why it was not applied in plain words ("not found": the text differs;
   "ambiguous": the text occurs twice; a link, field or earlier revision is in the way).
8. **Formatted copy.** For a `.docx` with a `layout.json` from step 3, run
   `hmw format "<copy>" --layout "<rev>/layout.json" -o "<copy name>-formattato.docx" --json`,
   then measure the result into `<rev>/measure-formattato.json` (as in step 3, `--workdir
   "<rev>/pdf-formattato"`), so the report shows the form before and after.
9. **Report.** Write `<rev>/rapporto.md` following `./modello-rapporto.md`, in the user's
   language. What changed comes from the edits files themselves (their `find`, `replace`,
   `comment` and `reason`) minus the edits in `failed` and `conflicts`; never reconstruct
   it from the `applied` indices.
10. **Tell the user.** Show the report's summary and its questions, with the paths of the
    copies and of `rapporto.md`. Changes in the copy are accepted or rejected in Word or
    LibreOffice.
11. **Answers: at most two cycles.** When the user answers the questions, run a cycle
    (spec §6.3: apply the corrections, measure again):
    1. Start a new `<rev>` and write the answers, verbatim, to `<rev>/risposte.md`.
    2. `<last>` is the newest corrected copy, `<name>-revisionato.docx` or
       `<name>-revisionato-<N>.docx` with the highest N (for LaTeX the main `.tex` in
       the newest `-revisionato` folder), never a `-formattato` copy.
    3. Run step 3 on `<last>` into the new `<rev>` (`extract.json`, `measure.json`), and
       copy the previous `<rev>/layout.json` there if there is one, without asking for
       the font again.
    4. Step 5 with these `extract.json` and `measure.json` and `{ANSWERS}` = the path of
       `risposte.md`: the reviewer writes only the edits that bring the answers into the
       text.
    5. Step 6 with `track` on `<last>`, output under the next free name; then step 7;
       step 8 on the new copy with the copied `layout.json`, so the formatted copy has
       this cycle's edits too.
    6. Steps 9–10, reporting the new changes and the new measures.

    After two cycles, stop and let the user decide what to do next.

## PDF drafts

A PDF cannot carry tracked changes: run steps 1–5 and 9–10, no `track`, no `format`
(in step 3, `layout` only gives the recommended settings). The report lists the reviewer's edits as proposed corrections, with
page, text and proposed change, in "To fix by hand", and says that a `.docx` or `.tex`
source would get them as tracked changes.

## Common mistakes

- Giving the reviewer the conversation, a summary of the draft or your own findings: it
  judges from the listed files only.
- Writing, improving or dropping the reviewers' edits yourself. The only change allowed
  is a format fix that `track` asks for.
- One `track` per reviewer, or an output name that already exists: one command with
  every `--edits`, and a new file name.
- Listing what changed from the `applied` indices instead of the edits files.
- Copying a password or other secret from the document into the report or the chat:
  name where it is instead.
- Reporting "everything is fine" for a check that `measure` could not evaluate: say it
  was not checked and why.
