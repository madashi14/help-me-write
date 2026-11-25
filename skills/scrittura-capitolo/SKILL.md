---
name: scrittura-capitolo
description: Use when one chapter of a document must be written from its interview notes and the material, shown to the user, changed as asked and approved - scrivi il capitolo, approva il capitolo, modifica il capitolo. Phases scrittura and approvazione of help-me-write; every fact from the material or the user, [DA VERIFICARE] otherwise.
---

# Writing a chapter (scrittura-capitolo)

## Overview

Write one chapter, the one in `next.chapter`, in the user's voice and the document's
language, using only the interview notes and the material; show it; apply the changes
asked; record the approval. Phase `scrittura` (status `intervista-fatta`) writes and then
goes on to the approval; phase `approvazione` (status `scritto`) starts at step 5, also
for the chapters of a partial draft.

- Talk to the user in their language; write the chapter in the document's language.
- Helper: `python <this skill's directory>/../../scripts/hmw.py <command>` (`python3`
  where `python` is not Python 3), written `hmw` below. Quote every path. Run each command
  on its own.
- `<work>`, `<output>`, `<main>`, `<name>` as in [struttura](../struttura/SKILL.md);
  `<id>` is the chapter's id and `<notes>` its interview notes,
  `<work>/.help-me-write/capitoli/<id>-intervista.md`. The fixed rules of
  [help-me-write](../help-me-write/SKILL.md) apply here.

## Inputs

Read before writing:
- `<notes>`: the user's answers, in their words. Missing: follow
  [intervista-capitolo](../intervista-capitolo/SKILL.md) first.
- `<work>/.help-me-write/materiale.md`: "Dati e numeri" is the only reservoir of
  numbers; "Note dell'autore" are constraints; the Mappa names the files.
- The files the notes and `<work>/.help-me-write/indice.md` name for this chapter
  (read-only), and the chapter's current text when it exists.
- The profile `<this skill's directory>/../../profili/<profile>.md`: `## Tone`,
  `## Content checklist`, `## Citation needs` and `## Writing budget`.
- `<work>/.help-me-write/linee-guida.yaml`: `content_rules`, the section's `pages`.
- `## Decisioni` of `<work>/.help-me-write/progetto.md`.
- For an introduction or a conclusion: the approved body chapters.

**Length.** The chapter's budget in pages (from `indice.md`, set from `## Writing budget`)
times `target_lines` times `target_chars` of `<work>/.help-me-write/layout.json` is its
length in characters: 2 pages × 33 lines × 65 characters ≈ 4300 characters, figures
included at their height.

## Rules

- **Every number and every fact has a source**: a file listed in `materiale.md` (with
  its position) or an answer recorded in `<work>/.help-me-write/`. List them at the end of
  `<notes>` in a section `## Fonti del capitolo`, one line each: what the text says →
  file and position, or "risposta dell'utente, <date>".
- **No source, no fact.** Write `[DA VERIFICARE: <what is missing>]`, literally, in any
  language, and list it in "Fonti del capitolo" as without source. Never a plausible
  value, date, name or result.
- **Diary.** When the profile asks for it (relazione-tirocinio does): first person
  singular for the user's own work, chronological or development order, past tense for
  the activities.
- **Personal contribution explicit**: for every activity, what the user did, decided or
  proposed, as distinct from the team or the tutor, as the notes say.
- **Citations** only to sources in the project's or the user's `.bib`, or files in the
  user's folder: `\cite{<key>}` in LaTeX, `[@<key>]` in Word. A statement that needs a
  citation (`## Citation needs`) and has no source gets
  `[DA VERIFICARE: fonte per <what>]`. Never a reference from memory.
- **The author's notes and the interview are constraints**: what to stress, what to
  leave out, how to name things. What must not be published stays out.
- **Introduction and conclusion summarize the chapters and bring no new facts**: every
  result or number they mention is already in a body chapter, with the same value;
  objectives, what was learned and what remains open come from the interview notes.
- Numbers keep the value and rounding of "Dati e numeri", the same in every chapter.

## Prose to avoid

Rewrite any sentence of these kinds with the specific fact from the notes, or drop it:
- empty formulas: "riveste un ruolo fondamentale", "nel panorama attuale", "in
  conclusione possiamo affermare", "è importante sottolineare", "al giorno d'oggi",
  "gioca un ruolo chiave" (in English: "plays a crucial role", "in today's landscape");
- rhetorical triplets: three adjectives or nouns in a row for rhythm ("efficiente,
  robusto e scalabile") that the material does not back one by one;
- intensifiers without a number: "molto", "estremamente", "fortemente",
  "significativamente", "notevole";
- sentences that would fit any internship or any project: "è stata un'esperienza
  formativa", "ho messo in pratica le conoscenze acquisite", "ho imparato a lavorare in
  team", unless the notes give the episode;
- promotional words about the host, a product or a technology.

A paragraph with no fact from the notes or the material is cut.

## Steps

1. **Plan the chapter.** Sections in chronological or development order; under each, the
   facts with their sources and the figures. For each image of the notes (existing, or a
   chart or diagram to generate) follow the [figure](../figure/SKILL.md) skill.
2. **Before writing into a LaTeX project**, run `hmw state modified "<work>"`. If the
   working copy is `modified`, the user edited it by hand: never write into it. Make a
   plain copy, `hmw format "<work>/<output>/<main>" -o "<work>/<base>-v2-help-me-write"`
   (the first free `-v<N>-`, `<base>` as in struttura; their edits come along), make it the
   working copy as in step 5 of struttura's "Revision of existing text", and write there.
   If the chapter's file already holds text besides its heading and comments, it is the
   user's: show it and ask whether to build on it, keeping their sentences.
3. **Write.**
   - **LaTeX:** the chapter's file, its `source` in the state; in a new project
     `<work>/<output>/capitoli/NN-<id>.tex`. Keep its `\chapter{…}` and `\label` lines
     and write the text after them. A new project's line
     `% help-me-write: testo da scrivere` is replaced; a comment the user left in an
     empty file says what they expect there: follow it and keep it. Use `\section`,
     `\cite`, figures as the figure skill says, and escape `% & _ # $` in the text.
   - **Word:** `<work>/.help-me-write/capitoli/<id>.md` in the format of
     [formato-capitoli.md](formato-capitoli.md) (headings, lists, figures, tables,
     `@fig:` references, `[@key]` citations, placeholders); nothing outside that format.
   - Append `## Fonti del capitolo` to `<notes>`.
   - Run
     `hmw state chapter "<work>" <id> --status scritto --source "<work>/<output>/capitoli/<file>"`
     (Word: `--source "<work>/.help-me-write/capitoli/<id>.md"`).
4. **Check before showing.** Every number of the chapter is in "Dati e numeri" or in
   the notes, with the same value; every `[DA VERIFICARE: …]` is listed; no prose to
   avoid; the length is within the budget; the tone and the profile's
   `## Content checklist` hold; the author's notes are respected; nothing confidential.
5. **Show the chapter.**
   - **LaTeX:** compile it with
     `hmw measure "<work>/<output>/<main>" --rules "<work>/.help-me-write/linee-guida.yaml" --workdir "<work>/.help-me-write/pdf" -o "<work>/.help-me-write/misure/<id>.json"`;
     give the user the PDF (`pdf` in the JSON) and the chapter's pages (its heading in
     `sections`: `start_page`–`end_page`) against its budget.
   - **Word:** show the text of the source and its length in pages, about.
   - List each `[DA VERIFICARE: …]` as a question to the user.
6. **Changes.** In a chapter written by this skill, edit its file, check again (step 4)
   and show it again. In a chapter of the user's draft never rewrite the file: deliver
   the change as a revision ("Revision of existing text" in struttura). An answer to a
   `[DA VERIFICARE]` question is first recorded in `<notes>` with its date, then replaces
   the placeholder.
7. **Approval.** When the user approves, run
   `hmw state chapter "<work>" <id> --status approvato`, then record the output:
   LaTeX `hmw state record "<work>" "<work>/<output>"`; Word after step 8. In a partial
   draft the user may approve several of the draft's own chapters in one answer: set each
   to `approvato`. Add a line to `## Decisioni`.
8. **Word: the document.** After each approval run `hmw state modified "<work>"`.
   - The last assembled `.docx` is `unchanged`, or there is none yet: build a new version
     with `hmw assemble "<work>/.help-me-write/manifest.yaml" -o "<work>/<output>/<name>.docx"`
     (when the file exists, use the first free `<name>-v<N>.docx`), tell the user how many
     placeholders it reports, and run `hmw state record "<work>" "<work>/<output>/<name>.docx"`
     with the name used.
   - It is `modified`: the user edited it by hand, never assemble over it. Changes to
     text already in it are tracked changes, as in struttura's "Revision of existing
     text"; new chapters are assembled alone into `<name>-capitoli-nuovi.docx` for the
     user to paste (struttura, P8).
   - A partial Word draft: never assemble the whole document; new chapters go to
     `<name>-capitoli-nuovi.docx` (struttura, P8).

## Common mistakes

- A number that is in no file of `materiale.md` and in no recorded answer, or a value
  rounded differently from "Dati e numeri".
- Filling a gap with something plausible instead of `[DA VERIFICARE: …]`.
- The team's work written as the user's, or the user's contribution hidden in "abbiamo".
- An introduction or conclusion with results the body does not have.
- Generic prose that would fit any internship.
- Rewriting a chapter of the user's draft, or writing into a copy or `.docx` they edited
  by hand, instead of a revision.
- Moving on before the user approved the chapter.
