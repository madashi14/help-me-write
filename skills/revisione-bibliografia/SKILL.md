---
name: revisione-bibliografia
description: Use when the citations, sources or bibliography of a draft (docx, tex or pdf) must be checked - bibliografia, citazioni, fonti, controlla le citazioni, controlla la bibliografia, verifica le fonti, check my references, check my citations, verify my sources - to find claims their source does not support, invented or wrong references and statements missing a citation. Also run by the revisione skill.
---

# Bibliography review (revisione-bibliografia)

## Overview

An independent reviewer reads the sources of a draft. For every citation it checks that
the source says what the text says, and quotes the passage with its page. It checks that
every entry of the bibliography exists and that its data are right, and it finds the
statements that need a citation and have none. Problems become comments in a copy,
corrections of reference data (a wrong year) tracked changes, and the report gets a
Bibliography section. The original is never modified. Nothing is invented: no source is
added that nobody read, and no citation is called verified that was not.

- Talk to the user in their language. Corrections are in the document's language.
- A confirmation the user already gave in their request counts: do not ask for it again.
- Helper: `python <this skill's directory>/../../scripts/hmw.py <command>` (`python3`
  where `python` is not Python 3), written `hmw` below. Quote every path: names with
  spaces and accents are common. Run each command on its own, not chained with `&&` or
  `;`: permission rules match single commands.
- `<doc>`, `<work>`, `<parent>`, `<rev>` and the names of the copies are those of the
  [revisione](../revisione/SKILL.md) skill: the document; its folder (for LaTeX, the
  project folder: the folder of the main `.tex`), where `<work>/.help-me-write/` lives;
  the folder that holds a LaTeX project folder; and a new folder
  `<work>/.help-me-write/revisioni/<YYYY-MM-DD-HHMMSS>/` for this review's files (local
  time, e.g. from
  `python -c "import datetime; print(datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S'))"`).
  Write them as absolute paths in every command: the current folder of your shell may
  differ.
- `<sources>` is where the sources are: `<work>` (all its subfolders are searched), or the
  folder the user names for them. The document's own PDFs there (its PDF export, the
  copies, `*-differenze.pdf`) are never sources: `bib` lists them in `excluded_sources`.
- Alone, run every step. The [revisione](../revisione/SKILL.md) skill runs only steps 3
  and 4, with its own `<doc>`, `<work>`, `<rev>`, guidelines and profile, and applies the
  edits and writes the report itself.

## Steps

1. **Find the document and check the tools.** Use the file the user names; otherwise
   look for it as step 1 of the revisione skill does. Run `hmw doctor`: every Python
   package is needed. If one is missing, tell the user how to install it (the `doctor`
   output says) and stop. `latexmk` and `latexdiff` are needed only for the PDF of
   differences of a `.tex`: without them, skip that PDF and say why.
2. **Profile and guidelines.** If `<work>/.help-me-write/linee-guida.yaml` exists, it is
   the guidelines, and its `document_type` names the profile
   `<this skill's directory>/../../profili/<document_type>.md` (`generico.md` if that file
   does not exist). Otherwise read `## Recognize` in each file of
   `<this skill's directory>/../../profili/`, propose the profile that matches
   (`generico` if none does) and ask the user to confirm it; the guidelines are then
   `none`. Do not build the guidelines only for this check.
   The profile's `## Citation needs` is the reviewer's criterion for what needs a
   citation.
3. **Extract and list the citations.** Create the folder `<rev>` if it does not exist.
   `<bibfile>` is the work's BibTeX file: the one the main `.tex` names, or the only
   `.bib` in `<work>` (several: ask the user which), or `none`. Then run:
   - `hmw extract "<doc>" -o "<rev>/extract.json"`, unless that file exists already;
   - `hmw bib "<doc>" --sources "<sources>" -o "<rev>/bib.json"`, for LaTeX with
     `--bib "<bibfile>"` when the main file names no `.bib` (`\bibliography{…}`,
     `\addbibresource{…}`; `bib` reads a named one by itself).

   On exit 2 show the error and stop.
4. **Reviewer.** Take `./prompt-revisore-bibliografia.md` and fill its placeholders:
   absolute paths of `<rev>/extract.json`, `<rev>/bib.json`, the guidelines (or `none`),
   the profile, `<bibfile>` (or `none`), `<sources>`, the folder `<rev>/fonti` for the
   texts of the sources (`{SOURCE_TEXTS}`), and the two outputs
   `<rev>/edits-bibliografia.json` and `<rev>/note-bibliografia.md`; `{HMW}` = `python`
   (or `python3`) followed by the quoted absolute path of `hmw.py`; the document's
   language and the user's language. Dispatch a fresh subagent with the filled prompt as
   its whole task: no conversation, no summary of how the document was written, no
   opinion of yours. It reads the PDFs with the `pdftext` command (into `<rev>/fonti`),
   and uses web search and fetch tools if it has them. If you cannot dispatch subagents,
   do the review yourself, reading only the files and sources the prompt lists.
5. **Apply the edits** (alone). When the reviewer has finished:

   `hmw track "<doc>" --edits "<rev>/edits-bibliografia.json" -o "<copy>" --json`

   - `<copy>` is `<work>/<name>-revisionato.docx`, or the next free name (`-2`, `-3`, …);
     for LaTeX the folder `<parent>/<name>-revisionato`, beside the project folder, then
     `hmw texdiff "<doc>" "<copy>/<main file name>" -o "<parent>/<name>-differenze.pdf"`
     (exit 2: read the error message; exit 3: `latexmk` or `latexdiff` is missing).
     LaTeX sources get no comments: the report lists them with file and line.
   - Exit 0: all applied. Exit 1: the copy is written; some edits failed or conflicted.
     Exit 2: nothing was written; read the error message: an invalid edits file (fix
     only what the listed problems name, a missing `reason` or an unknown key, never
     what an edit says, and run it again), a missing document, an output that already
     exists (use the next free name the message gives), an unwritable folder.
6. **Report** (alone). Write `<rev>/rapporto.md` in the user's language with the title
   lines of [modello-rapporto](../revisione/modello-rapporto.md) (reviewers:
   bibliography only), a summary of a few lines (files produced; corrections, comments,
   edits to fix by hand) and only the template's Bibliography section, filled as it
   says. End that section with the edits `track` did not apply (every `failed` and
   `conflicts` entry: where, the text, the intended change or comment, and why, in plain
   words) and the questions only the author can answer, numbered.
7. **Tell the user.** Show the summary: the citations not supported or not verifiable,
   the missing citations, the entries not found or with wrong data, and the paths of the
   copy and of `rapporto.md`. Changes in the copy are accepted or rejected in Word or
   LibreOffice.

## PDF drafts

A PDF cannot carry tracked changes: run steps 1–4, 6 and 7, no `track`. The report ends
its Bibliography section with the reviewer's edits as proposals (page, text, proposed
change or comment) and says that a `.docx` or `.tex` source would get them in a copy.

## New sources

The reviewer proposes only sources already in `<sources>` or in `<bibfile>`, and only
after reading them. Look for new sources online only when the user asks: search with a
few keywords of the topic, never sentences of the document; read each source you
propose, give its passage and page, and let the user add it. Never insert a source into
the document yourself.

## Common mistakes

- Giving the reviewer the conversation, a summary of the draft or your own findings: it
  judges from the listed files and the sources only.
- Taking `bib.json` as complete: it misses citations glued to a word ("results[3]") and
  entries after a subheading inside the bibliography; the reviewer also reads the
  extract.
- Calling a citation verified, or an entry invented, without having read the source or
  searched for it. Without web tools or network an entry with no local PDF is "not
  verifiable".
- Asking for citations on the author's own activities.
- Sending the document's text online: only titles, authors and DOIs of the entries (and,
  when the user asks for new sources, a few keywords) leave the computer.
- Writing, improving or dropping the reviewer's edits yourself. The only change allowed
  is a format fix that `track` asks for.
