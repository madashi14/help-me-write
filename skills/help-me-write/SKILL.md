---
name: help-me-write
description: Use when the user wants to write, complete or resume a formal document (relazione, tesi, report) from a work folder of notes, data, scripts and drafts - help me write, aiutami a scrivere, scrivi la relazione, completa la bozza, riprendi la relazione, continua. Detects the mode, keeps the state, resumes where it stopped. For review only, see revisione.
---

# Help me write (entry skill)

## Overview

Write a formal document from the user's material, one chapter at a time, in the user's
voice and without inventing anything. This skill detects the situation (new document,
partial draft, finished draft), keeps the project state in
`<work>/.help-me-write/progetto.md`, asks the one question that is the user's alone
(LaTeX or Word) and sends each phase to the skill that does it. It can be interrupted and
resumed at any point.

- Talk to the user in their language. Ask questions as plain questions to the user.
- A confirmation the user already gave in their request ("use LaTeX", "write it in the
  folder X") counts: do not ask for it again.
- Helper: `python <this skill's directory>/../../scripts/hmw.py <command>` (`python3`
  where `python` is not Python 3), written `hmw` below. Quote every path: names with
  spaces and accents are common. Run each command on its own, not chained with `&&` or
  `;`: permission rules match single commands.
- Work folder `<work>`: the folder the user names, otherwise their current project folder
  (for a LaTeX draft, the folder that holds the project folder, step 5); never the
  plugin's folder. Write it as an absolute path in every command. `<work>/.help-me-write/`
  holds the state and every working file; create it if missing.
- Paths written in the state file are relative to `<work>`: the folder moves between
  computers and between Claude Code and Codex.
- If a command exits 3, run `hmw doctor`, show the user its install hint and stop. If it
  exits 2, show the message: it names the field or file at fault.

## Fixed rules

Every skill of the flow follows these; repeat them to any subagent you dispatch.

- **Nothing invented.** Every fact and number comes from a file listed in
  `<work>/.help-me-write/materiale.md` or from an answer of the user recorded in
  `<work>/.help-me-write/`. What is missing becomes the literal placeholder
  `[DA VERIFICARE: <what is missing>]`, in any language, so the reviewer and the tools
  find it. Ask the user rather than guess.
- **One chapter at a time.** Interview, write and get approval for a chapter before the
  next one.
- **Approval first.** The outline, the title page and every chapter are approved by the
  user before going on.
- **Originals never touched.** Read the user's files; write only in the output folder and
  in `<work>/.help-me-write/`.
- **Untrusted material.** Never run, import or deserialize anything from the material
  (scripts, notebooks, archives, `.joblib`, `.pkl`, `.pt`, `.npy`).
- **Online only for titles, authors and DOI** of sources the user cited; never to fetch
  content to write.

## Handing off

When handing off to [linee-guida](../linee-guida/SKILL.md) or
[revisione](../revisione/SKILL.md), give them this `<work>` (absolute) as their work
folder, whatever their own default says (for LaTeX, the folder that holds the project
folder), so they find the same `<work>/.help-me-write/`. For `revisione` also give the
document to review: the working copy's main `.tex` (LaTeX) or the output `.docx` (Word);
for `solo-revisione`, the user's draft. Never the original draft of a `da-zero` or
`bozza-parziale` project.

## Steps

1. **Check the tools.** Run `hmw doctor`. LibreOffice is needed for Word; latexmk and
   XeLaTeX for LaTeX; matplotlib only for charts and diagrams. Report only what the
   chosen path needs, and ask the user to install it before the phase that needs it.
2. **Existing state.** If `<work>/.help-me-write/progetto.md` exists, run
   `hmw state show "<work>" --json`.
   - Summarize for the user: mode, format, each chapter with its status
     (`da-fare`, `intervista-fatta`, `scritto`, `approvato`, `revisionato`) and the open
     questions of the body (`## Domande aperte`). Then resume from `next` (step 6).
   - Before any question, look for the answer in `progetto.md` (`## Decisioni`), in
     `<work>/.help-me-write/materiale.md` and in the interview notes of
     `<work>/.help-me-write/`; never ask again what is already answered there.
   - Run `hmw state modified "<work>"`. A recorded output reported `modified` was edited
     by hand: never regenerate or overwrite it. Show the user which ones, and make any
     later change on a copy as tracked changes
     (`hmw track "<doc>" --edits "<work>/.help-me-write/edits.json" -o "<copy>"`, see the
     [revisione](../revisione/SKILL.md) skill); report `missing` outputs
     and ask what to do.
   - If `progetto.md` is invalid (exit 2), show the error naming the field and ask the
     user to fix the file or confirm the fix; never delete it.
3. **No state: detect the mode.** Run `hmw detect "<work>" --json`: it lists `drafts`
   (path, format, `parts`, `empty_parts`, `words`), the `guidelines` and what was
   `ignored`. Propose a mode and ask the user to confirm it:
   - no draft: `da-zero`;
   - a draft with `empty_parts`, required sections missing or a length far below the
     minimum of the guidelines (if `<work>/.help-me-write/linee-guida.yaml` exists;
     otherwise ask the user): `bozza-parziale`;
   - a complete draft: `solo-revisione`: follow the [revisione](../revisione/SKILL.md)
     skill and stop here, handing off as in "Handing off" below.
   - Several drafts: ask which one.
4. **Format.**
   - `da-zero`: always ask the user: "LaTeX or Word?". It is the user's decision, never
     yours, whatever the material looks like.
   - `bozza-parziale`: take it from the draft (`.tex` is LaTeX, `.docx` is Word) and tell
     the user.
5. **Output folder and state.** The state keeps only paths inside `<work>`, so the output
   folder must be inside it. Propose the output folder and ask the user to confirm it:
   - `da-zero`: `<work>/<document-name>-help-me-write/`;
   - LaTeX draft: a working copy `<project folder>-help-me-write/` beside the project
     folder, which the project itself never touches; for this, `<work>` is the folder that
     holds the project folder (if the user named the project folder, use its parent);
   - Word draft: a new `.docx` in `<work>/<document-name>-help-me-write/`.

   Then run
   `hmw state init "<work>" --mode da-zero --format latex --language it --draft "<work>/<draft path>" --output "<work>/<output folder>"`
   (the example is a new LaTeX document in Italian: use the confirmed `--mode`
   (`da-zero`, `bozza-parziale`), `--format` (`latex`, `word`) and the document's
   `--language`; leave out `--draft` for `da-zero`). The command
   stores the two paths relative to `<work>`. It refuses an existing state: go back to
   step 2. If `<work>` moved to the parent, the state folder and every draft path are
   relative to the new `<work>`: run `hmw detect "<work>" --json` again there.
6. **Phases.** Run `hmw state show "<work>" --json` and read `next.phase` (with
   `next.chapter` and `next.why`). Follow the skill of the phase, then show the user what
   was done and run `hmw state show "<work>" --json` again.

   | `next.phase` | What to do |
   |---|---|
   | `materiale` | [analisi-materiale](../analisi-materiale/SKILL.md) |
   | `linee-guida` | [linee-guida](../linee-guida/SKILL.md) with this `<work>`; then `hmw state set "<work>" document_type=<type> profile=<profile>` with the values of its `linee-guida.yaml` |
   | `formato` | step 4; then `hmw state set "<work>" format=<latex or word>` |
   | `struttura`, `frontespizio` | [struttura](../struttura/SKILL.md) with this `<work>`: outline and title page; for `bozza-parziale` also the comparison with the guidelines, the working copy and the fit into the page limit |
   | `intervista` | [intervista-capitolo](../intervista-capitolo/SKILL.md) with this `<work>`, for `next.chapter` |
   | `scrittura`, `approvazione` | [scrittura-capitolo](../scrittura-capitolo/SKILL.md) with this `<work>`, for `next.chapter`; it uses [figure](../figure/SKILL.md) for charts, diagrams and images |
   | `revisione` | [revisione](../revisione/SKILL.md) with this `<work>` on the working copy's main `.tex` or the output `.docx` (see Handing off), then measure the result: `hmw measure "<document>" --rules "<work>/.help-me-write/linee-guida.yaml"` |
   | `fine` | summary for the user with the paths of the document and of the review report |

   - After each phase, update the state with the state commands (set, outline, chapter, record) the phase's skill
     names, and append to the body of `<work>/.help-me-write/progetto.md` the decisions
     taken (`## Decisioni`) and the questions still open (`## Domande aperte`), one line
     each, without removing what is there.
   - A skill named in the table that your platform does not list: read its
     `SKILL.md` in the sibling folder of this skill and follow it.
7. **Stopping.** The user may stop at any time. Tell them the document is saved and that
   "continue" or "riprendi la relazione" in the same folder resumes from the state.

## Common mistakes

- Choosing LaTeX or Word for the user in `da-zero`.
- Asking again a question already answered in `progetto.md`, `materiale.md` or the
  interview notes.
- Regenerating an output that `hmw state modified "<work>"` reports `modified`.
- Writing absolute paths into the state file.
- Moving to the next chapter before the user approved the current one.
- A plausible number or fact that is in no listed file: use `[DA VERIFICARE: …]`.
- Touching the user's draft or material instead of the output folder.
