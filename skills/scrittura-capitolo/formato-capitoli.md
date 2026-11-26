# Chapter source format (Word documents)

In the Word branch every chapter is written as a small Markdown file in
`<work>/.help-me-write/capitoli/`, one file per chapter, and the whole document is built
from these files with:

```
hmw assemble "<work>/.help-me-write/manifest.yaml" -o "<work>/<name>.docx"
```

`assemble` adds the title page, the table of contents, the numbers of figures, tables and
citations, the bibliography and the page layout. Write only what is listed here: anything
else is either shown literally or refused with an error that names the file and the line.

## Blocks

Separate blocks with a blank line.

- **Headings:** `# Chapter`, `## Section`, `### Subsection` (three levels, no deeper). A
  `#` heading starts a new page. Do not number headings by hand.
- **Paragraphs:** plain text; lines of one paragraph may be wrapped, they are joined.
- **Lists:** items starting with `- ` (bullets) or `1. `, `2. `, ... (numbered). One level
  only: no nested lists. A longer item may continue on an indented line.
- **Figures:** alone on their line, with a blank line before and after:
  `![Caption](path/to/image.png){#fig:label width=12cm}`
  - the path is relative to the chapter file (PNG or JPEG);
  - `width` is optional (`cm`, `mm`, `in`, `pt` or `%` of the text width); without it the
    image keeps its natural width, reduced to the text width when wider;
  - the figure is centred and kept on the same page as its caption, which becomes
    "Figura N: Caption" ("Figure N" in English).
- **Tables:** a pipe table with the caption line above it:

  ```
  Tabella: Caption {#tab:label}

  | Column | Value |
  |--------|------:|
  | a      | 1     |
  ```

  Write `Table:` in English documents. The separator row may set the alignment of each
  column (`:--` left, `:-:` centre, `--:` right). Every row has the header's number of
  cells. The caption becomes "Tabella N: Caption" above the table.

## Inside the text

- `**bold**`, `*italic*`, `` `code` ``. A `\` before `*`, `` ` ``, `[`, `]` or `@` shows
  the character itself.
- **References:** `@fig:label` and `@tab:label` become "Figura N" and "Tabella N"
  ("Figure N", "Table N" in English). Refer to every figure and table in the text.
- **Citations:** `[@key]` or `[@key1; @key2]`, with keys of the `.bib` file named in the
  manifest. They become `[1]` and `[1, 2]`, numbered in order of first citation, and the
  cited entries are listed at the end under "Bibliografia" ("References"). No page numbers
  or other text inside the brackets.
- **Placeholders:** `[DA VERIFICARE: what is missing]`, the same words in every language,
  for every fact or number without a source. They stay in the text, highlighted in
  yellow, and `assemble` reports how many there are.
- **Formulas:** there is no formula syntax. Write them as Unicode text (`E = σ / ε`,
  `x² + y²`, `≤ 10 %`). Typeset equations are a known limitation of the Word branch.

Not supported: code blocks (```` ``` ````), footnotes, links (write a URL as plain text),
images inside a paragraph, headings deeper than `###`.

## Manifest

`<work>/.help-me-write/manifest.yaml`; paths are relative to its folder.

| Key | Required | Meaning |
|---|---|---|
| `layout` | yes | the JSON written by `hmw layout` (fonts, margins, line pitch) |
| `chapters` | yes | the chapter files, in order |
| `title_page` | no | a `.docx` with the filled title page (`hmw titlepage`) |
| `bibliography` | no | a `.bib` file, needed when the text cites |
| `language` | no | `it` (default) or `en`: words of captions, references and titles |
| `toc` | no | `true` (default): a table of contents after the title page |
| `toc_title` | no | default "Indice" ("Contents" in English) |
| `bibliography_title` | no | default "Bibliografia" ("References" in English) |

Every problem (a missing file or image, a label defined twice or never defined, a cited
key missing from the `.bib`, an unknown key in the manifest, a line in an unsupported
form) is reported at once with exit code 2, and no document is written. The page numbers
of the table of contents are computed with LibreOffice; without it they stay `00` and
Word updates them when the document is opened (or with F9).

## Example

`capitoli/02-attivita.md`:

```
# Attività svolte

Nelle prime due settimane ho studiato il processo di rilascio in uso, descritto nella
documentazione interna [@manuale-rilascio]. Il flusso che ne è risultato è nella
@fig:flusso.

![Flusso di rilascio prima del tirocinio](../figure/flusso.png){#fig:flusso width=10cm}

## Automazione della compilazione

Ho preparato tre immagini dei contenitori:

- applicazione web;
- servizi di supporto;
- base di dati di prova.

I tempi misurati sono nella @tab:tempi.

Tabella: Durata delle fasi della pipeline {#tab:tempi}

| Fase | Minuti |
|------|-------:|
| Compilazione | 4 |
| Test | [DA VERIFICARE: durata dei test dopo l'ottimizzazione] |
```

`manifest.yaml`:

```
title_page: frontespizio.docx
layout: layout.json
bibliography: ../bibliografia.bib
chapters:
  - capitoli/01-introduzione.md
  - capitoli/02-attivita.md
  - capitoli/03-risultati.md
  - capitoli/04-conclusioni.md
```
