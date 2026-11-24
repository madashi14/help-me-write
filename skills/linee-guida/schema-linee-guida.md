# Schema of `.help-me-write/linee-guida.yaml`

The file is one YAML mapping. `rules validate` (scripts/helpmewrite/rules.py) accepts
exactly the keys below: **any other key, at the top level, in a section or in a range, is
an error.** Always write `document_type`, `language` and `format`; every other key is
optional, and an omitted key takes the default shown and its rule is not checked. Values
in the YAML are in the document's language (section names, headings, content rules);
keys are in English.

## Top-level keys

| Key | Type | Default | Meaning |
|---|---|---|---|
| `document_type` | string | `""` | Name of the profile used: the file name in `profili/` without `.md` (`relazione-tirocinio`, `generico`). Later skills open `profili/<document_type>.md`. |
| `language` | string | `it` | ISO 639-1 code of the document's language (`it`, `en`, …). |
| `format` | `docx`, `latex` or `null` | `null` | Leave `null`. In review the format is the file's; the writing flow sets it. |
| `source` | string or `null` | `null` | Path of the guidelines document, relative to the work folder (absolute if outside it). `null` when the rules come only from the user. |
| `pages` | range | `null` | Allowed number of pages of the whole document, title page included. |
| `fonts` | list of strings | `[]` | Every allowed font, as written in the guidelines, in their order. Any one of them is accepted. |
| `font_size_pt` | number | `null` | Body text size in points. |
| `lines_per_page` | range | `null` | Lines of text per full page. |
| `chars_per_line` | range | `null` | Characters per full line, **spaces included**. |
| `page_numbers` | `true` / `false` | `false` | `true` when pages must be numbered. `false` means "not required" and is not checked. |
| `sections` | list of sections | `[]` | The parts of the document, in the order the document must follow (see below). |
| `content_rules` | list of strings | `[]` | Every other rule a reviewer can check by reading the document: one sentence each, quoted or closely paraphrased from the guidelines (diary form, personal contribution, citation style, line spacing, margins…). |
| `title_page_template` | string or `null` | `null` | Path of the file holding the title-page model, relative to the work folder. When the guidelines document contains the model itself ("frontespizio: vedi pagina a seguire"), its own path. |

## Range

A mapping with `min` and/or `max`, both non-negative numbers; omit a bound that is open.
`min` must not exceed `max`.

```yaml
pages: {min: 10, max: 30}      # "between 10 and 30 pages" (also "circa 10-30")
pages: {max: 20}               # "at most 20 pages"
lines_per_page: {min: 30, max: 35}
```

A slash between two numbers usually means a range ("1/2 pagine" = 1–2 pages); if the
meaning is unclear, ask the user.

## Section

| Key | Type | Default | Meaning |
|---|---|---|---|
| `name` | non-empty string | — (required) | Short lowercase name of the part, as the guidelines call it, without descriptions: "introduzione che sintetizza gli obiettivi…" → `introduzione`. |
| `required` | `true` / `false` | `true` | `false` for optional parts ("eventuali …", "facoltativo", "optional", "if any"). |
| `headings` | list of strings | `[]` | Lowercase heading texts that identify the part in the document. A heading matches when, ignoring case and leading numbering ("1.", "Capitolo 2 -", "IV."), it starts with one of them as whole words (`conclusione` does not match "Conclusioni": list both). `[]` for parts with no heading of their own (title page, a body made of several chapters): those are checked by the reviewer, not by `measure`. |
| `pages` | range | `null` | Allowed length of the part in pages. |

When the guidelines list the parts, `sections` is exactly their list, in their order,
with their names and optional marks. `headings` may add the profile's synonyms for the
same part (mark them as profile defaults). When the guidelines list no parts, use the
profile's sections.

## What reads each value

- `measure` checks `pages`, `fonts` (95% of body text in an allowed family),
  `font_size_pt` (±0.5 pt), `lines_per_page`, `chars_per_line`, `page_numbers` (every
  page except the first) and, for `.docx` only, presence and `pages` of each section with
  `headings`.
- `layout --font <name>` needs `font_size_pt` and a font listed in `fonts`, and uses the
  middle of `lines_per_page` and `chars_per_line`.
- Fonts are recognized by family: times (Times New Roman, Times, Liberation Serif, TeX
  Gyre Termes, Nimbus Roman), helvetica (Helvetica, Arial, Liberation Sans, TeX Gyre
  Heros, Nimbus Sans), courier (Courier, Courier New, Liberation Mono, TeX Gyre Cursor,
  Nimbus Mono). Write any other font exactly as the guidelines name it, and tell the user
  that the automatic font check and layout cannot handle it.
- The reviewer reads `sections`, `content_rules` and `title_page_template`.

## Provenance comments

A value with no comment comes from the guidelines document. Mark every other value with
a trailing comment: `# profile default` or `# user`. Rules that nobody gave are omitted,
with a comment line saying so. YAML ignores comments; they keep the origin of each value
visible to the user and to later skills.

## Example

Fictional guidelines document `linee-guida-tirocinio.pdf` (Dipartimento di Informatica,
Università di Esempio), profile `relazione-tirocinio`, one answer from the user:

```yaml
# Relazione di tirocinio, Dipartimento di Informatica, Università di Esempio
document_type: relazione-tirocinio
language: it
format: null
source: linee-guida-tirocinio.pdf
pages: {min: 15, max: 25}
fonts: [Times New Roman]
font_size_pt: 12
# lines_per_page, chars_per_line: not stated in the guidelines; the user does not know
page_numbers: true                                   # user
sections:
  - name: frontespizio
    required: true
    headings: []
  - name: indice
    required: true
    headings: [indice, sommario]                     # sommario: profile default
  - name: introduzione
    required: true
    headings: [introduzione]
    pages: {max: 2}
  - name: attività svolte
    required: true
    headings: []
  - name: conclusioni
    required: true
    headings: [conclusioni, conclusione]             # conclusione: profile default
  - name: bibliografia
    required: false
    headings: [bibliografia, riferimenti bibliografici]
content_rules:
  - Interlinea 1,5 e margini di 2,5 cm su tutti i lati.
  - "Citazioni: stile APA, con l'elenco completo delle fonti in bibliografia."
  - La relazione descrive in prima persona le attività svolte dallo studente.
title_page_template: modello-frontespizio.docx
```

## Validation errors

`rules validate <file> --json` exits 0 when valid, 2 with every problem listed. Fix all of
them, then run it again.

| Error | Fix |
|---|---|
| `unknown key 'margins'` (or `font`, `line_spacing`, …) | No such field: write the rule as a sentence in `content_rules`, or drop it. |
| `sections[2]: unknown keys ['optional']` | Use `required: false`. |
| `pages: expected a mapping with min/max, got '10-30'` | Write `{min: 10, max: 30}`. |
| `font_size_pt: expected a number, got '12pt'` | Write the bare number `12`. |
| `pages: min (30) is greater than max (10)` | Swap the bounds. |
| `invalid YAML: …` | Usually an unquoted `: ` or ` #` inside a string: wrap that string in double quotes. |
