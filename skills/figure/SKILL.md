---
name: figure
description: Use when a document being written needs a figure - a chart from the user's data files (CSV, JSON metrics), a block diagram of a process the user described, or an image the user already has - with number, caption and a reference in the text; grafico, schema, diagramma, figura, immagine. Values only from files, never photographic or AI-generated images.
---

# Figures (figure)

## Overview

Three kinds of figure, no others: charts drawn from a data file with hmw chart, every
value traced in a `.fonte.json` file; block diagrams drawn with hmw diagram from what
the user described; images the user already has. The plugin never makes photographic or
artistic images and never uses an AI image service (spec §3.1). Every figure has a
number, a caption and a reference in the text.

- Talk to the user in their language; captions and labels are in the document's
  language.
- Helper: `python <this skill's directory>/../../scripts/hmw.py <command>` (`python3`
  where `python` is not Python 3), written `hmw` below. Quote every path. Exit 3:
  matplotlib or another package is missing; run `hmw doctor` and show its install hint.
- `<work>`, `<output>` as in [struttura](../struttura/SKILL.md): for LaTeX `<output>` is
  the project or working copy. `<fig>` is a short name for the figure (`campagne-accuratezza`).
  The fixed rules of [help-me-write](../help-me-write/SKILL.md) apply here.

| | Description (spec) | Image |
|---|---|---|
| LaTeX | `<work>/.help-me-write/figure/<fig>.json` | `<work>/<output>/immagini/<fig>.png` |
| Word | `<work>/.help-me-write/figure/<fig>.json` | `<work>/.help-me-write/figure/<fig>.png` |

## Charts

1. **Only from a data file** listed in `materiale.md`: a CSV or JSON under `<work>`, or
   extracted from an archive under `<work>/.help-me-write/materiale/estratti/`. Never
   values typed by you. Numbers found only in a text or in an answer of the user make a
   table with its source, not a chart; or ask the user for the data file.
2. **Write the spec** in `<work>/.help-me-write/figure/<fig>.json`. Data paths are
   relative to the spec's folder: a file `<work>/<path>` is written `../../<path>`.
   Column names exactly as in the file's header. A CSV (BOM, `;` and decimal commas are
   read correctly):

   ```json
   {"type": "bar", "language": "it", "annotate": true,
    "xlabel": "Campagna", "ylabel": "Accuratezza",
    "csv": {"file": "../../dati/metriche.csv", "x": "campagna", "y": ["accuracy"],
            "labels": {"accuracy": "Accuratezza"}}}
   ```

   or values at dotted keys of JSON files (list indices allowed, `per_class.0.f1`):

   ```json
   {"type": "barh", "language": "it",
    "values": [{"label": "Prima campagna", "series": "test", "file": "../../risultati/run1.json", "key": "test.accuracy"},
               {"label": "Seconda campagna", "series": "test", "file": "../../risultati/run2.json", "key": "test.accuracy"}]}
   ```

   `type` is `bar`, `barh`, `line` or `scatter`; `ylim` `[min, max]` is optional. Leave
   `title` out: the caption is the title.
3. **Draw it:**
   `hmw chart "<work>/.help-me-write/figure/<fig>.json" -o "<work>/<output>/immagini/<fig>.png"`
   (Word: `-o "<work>/.help-me-write/figure/<fig>.png"`). Beside the image it writes
   `<fig>.png.fonte.json`: every plotted value with its file and position (column and
   row, or key; "row N" is the N-th data row, the header not counted, so row 1 is the
   line after the header). Keep it there, never edit or delete it. Exit 2: the message names the
   file, column or row: fix the spec, never the data. An image that exists is never
   overwritten: use the free name the message gives.
4. **Numbers must match the provenance.** A value in the caption or in the text about the
   chart is a value of its `.fonte.json`, with the same rounding (two decimals with
   `annotate`), and agrees with "Dati e numeri" of `materiale.md`. A number that is in
   neither does not appear.

## Diagrams

1. **Only what the user described** (interview notes) or what the material documents (a
   pipeline whose steps a README names). One box per step that is there; never add steps
   to make it look complete.
2. **Write the spec** in `<work>/.help-me-write/figure/<fig>.json`, labels short (they
   wrap at 18 characters), in the document's language:

   ```json
   {"direction": "LR",
    "nodes": [{"id": "dati", "label": "Raccolta dei log"},
              {"id": "feature", "label": "Estrazione delle feature"},
              {"id": "modello", "label": "Random Forest"}],
    "edges": [{"from": "dati", "to": "feature"},
              {"from": "feature", "to": "modello", "label": "CSV"}]}
   ```

   `direction` is `LR` or `TB`. A cycle is refused (the message names it): describe the
   loop in the caption or the text.
3. **Draw it:**
   `hmw diagram "<work>/.help-me-write/figure/<fig>.json" -o "<work>/<output>/immagini/<fig>.png"`
   (Word: `-o "<work>/.help-me-write/figure/<fig>.png"`), and show it to the user with the
   chapter.

## The user's images

- Screenshots, photos the user took, plots saved by their notebooks (the notebook command
  of the material analysis extracts them under
  `<work>/.help-me-write/materiale/estratti/`). Check against the
  interview's "Da non pubblicare": no client data, credentials or internal figures.
- **LaTeX:** copy the image into the project's `immagini/` folder, leaving the original
  where it is: `python -c "import shutil, sys; shutil.copy2(sys.argv[1], sys.argv[2])" "<work>/<image path>" "<work>/<output>/immagini/<file name>"`.
  Never copy over an existing file: choose a free name. Images already in the project
  (a partial draft) are used where they are.
- **Word:** cite it by its path, relative to the chapter file in
  `<work>/.help-me-write/capitoli/` (`../../<path inside the work folder>`). PNG or JPEG
  only: for another format ask the user for an export.

## Number, caption, reference

Numbering is automatic in both formats. Every figure has a caption that says what it
shows (for a chart, also which data: "Accuratezza delle tre campagne, dal file
experiment_comparison.csv") and is referred to in the text at least once, near it.
Labels are unique: `fig:<chapter id>-<fig>`.

LaTeX, with the reference `Figura~\ref{fig:<label>}` (`Figure~\ref` in English):

```latex
\begin{figure}[htbp]
  \centering
  \includegraphics[width=0.8\textwidth]{<fig>.png}
  \caption{<caption>}
  \label{fig:<label>}
\end{figure}
```

Word (format of [formato-capitoli.md](../scrittura-capitolo/formato-capitoli.md)), with
the reference `@fig:<label>` in the text:

```
![<caption>](../figure/<fig>.png){#fig:<label> width=12cm}
```

A figure that repeats a table, or a table that repeats a figure: keep one.

## Common mistakes

- A chart from numbers typed into the spec or copied from a text, instead of a data
  file.
- A caption or a sentence with a value that is not in the `.fonte.json` beside the
  image.
- Deleting or moving the `.fonte.json` away from its image.
- A diagram with steps nobody described.
- A photographic or AI-generated image.
- A figure with no caption or never referred to in the text.
