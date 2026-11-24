---
name: linee-guida
description: Use when the rules a document must follow have to be read or confirmed before writing or reviewing it - guidelines, linee guida, regolamento, template, facsimile, call or author instructions with page limits, font, lines per page, characters per line, required sections or other formatting rules - or when .help-me-write/linee-guida.yaml is missing or may be out of date.
---

# Guidelines (linee-guida)

## Overview

Turn the document's guidelines into `.help-me-write/linee-guida.yaml`, the rules every
other help-me-write skill checks against. Each value comes from the guidelines document;
a profile default only fills what the guidelines leave unsaid and is labelled as such;
the user fills the rest. Never invent a rule or a number.

- Talk to the user in their language. Ask questions as plain questions to the user.
- A confirmation the user already gave in their request ("save without asking") counts:
  do not ask for it again.
- Helper: `python <this skill's directory>/../../scripts/hmw.py <command>` (`python3`
  where `python` is not Python 3), written `hmw` below.
- Work folder: the folder of the document being reviewed or written, otherwise the
  user's current project folder; never the plugin's folder. Create `.help-me-write/`
  there if missing.
- Do not ask LaTeX or Word: leave `format: null`.

## If `.help-me-write/linee-guida.yaml` exists

Run `hmw rules validate .help-me-write/linee-guida.yaml`, show its scheda (below) and
ask the user whether it is still valid. Yes: stop here, without extracting again. No: ask
what changed. A new guidelines document: start from step 1. Otherwise: change only those
values (comment `# user`) in a draft copy and continue from step 5. If the file is
invalid, show the problems and fix them the same way.

## Steps

1. **Find and read the guidelines.** Look in the work folder for the guidelines (name or
   text about linee guida, regolamento, norme, facsimile, modello, template, bando,
   guidelines, author instructions; .docx, .pdf, .tex, .md, .txt). One: use it. Several:
   ask which. None: ask the user for the file, or for the rules if there is no file.
   Read it with `hmw extract <file>`; read .md and .txt directly. If `extract` reports a
   missing package, run `hmw doctor`, show the user its install hint and stop.
2. **Choose the profile.** Read `## Recognize` in each file of `../../profili/`
   ([relazione-tirocinio](../../profili/relazione-tirocinio.md),
   [generico](../../profili/generico.md)), propose the one that matches (`generico` if
   none does) and ask the user to confirm it.
3. **Fill the YAML** following [schema-linee-guida.md](schema-linee-guida.md): every rule
   the guidelines state, with their numbers; then, only where the guidelines are silent,
   the values of the profile's `## Default guidelines` block, commented
   `# profile default`.
4. **Ask for the missing rules that matter.** Of length in pages, fonts and size, lines
   per page, characters per line, page numbering and required sections, ask the user in
   one grouped question for those still unset. Answers get `# user`. Unknown: leave the
   key out (not checked).
5. **Validate.** Write the draft to `.help-me-write/linee-guida.bozza.yaml` and run
   `hmw rules validate .help-me-write/linee-guida.bozza.yaml --json`. Fix every problem
   listed and run it again until it exits 0.
6. **Show the scheda and ask the user to confirm it.** Changes: edit the draft and go
   back to step 5.
7. **Save.** Rename the draft to `.help-me-write/linee-guida.yaml` (replacing an old file
   only now) and tell the user the path.

## Scheda

The summary the user confirms, in the user's language, one line per topic:

```
Type:       <document type as the guidelines call it> (<institution>) - profile <profile>
Length:     <min>–<max> pages
Structure:  <section> (<length, notes>) · <section> · … · <section> (optional)
Format:     <font> / <font> <size>
            <min>–<max> lines per page, <min>–<max> characters per line, numbered pages
Content:    <content rules, in a few words>
Images:     <what the guidelines say about figures>
Not checked: <rules with no place in the YAML, e.g. binding, signatures>
Source:     <guidelines file>
```

- Mark each value that is not from the guidelines: "(profile default)" or "(from you)",
  translated. Write "not specified, not checked" for a rule nobody gave.
- After a font that is often missing (Helvetica on Windows), name the equivalent the
  scripts accept (Arial).

## Common mistakes

- A number from memory or "the usual standard" when the guidelines are silent: ask the
  user or leave it out.
- Profile defaults written without `# profile default`, or not marked in the scheda.
- Keys outside the schema (`margins`, `line_spacing`): `rules validate` rejects them;
  write such rules as sentences in `content_rules`.
- Extracting again when a confirmed `linee-guida.yaml` already exists.
