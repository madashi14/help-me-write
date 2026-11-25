# help-me-write — Parte 2: scrittura guidata e bozza parziale — Piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** dal materiale di una cartella di lavoro alla relazione finita, in LaTeX o in Word,
con intervista per capitolo, stato ripristinabile tra sessioni e completamento di una bozza
parziale (il caso reale: `madashi14/relazione_tirocinio`), dopo aver corretto le misure
della Parte 1 che falliscono su un PDF LaTeX vero.

**Architecture:** come nella Parte 1, le parti deterministiche sono comandi di
`scripts/hmw.py` (output JSON) e il giudizio sta nelle skill.
- **Nuovi comandi:**
  - `state` e `detect`: stato e modalità;
  - `material` e `notebook`: lettura del materiale;
  - `chart` e `diagram`: figure;
  - `titlepage`: frontespizio Word;
  - `assemble`: documento Word dai sorgenti dei capitoli;
  - `latex-init`: progetto LaTeX nuovo;
  - `format` esteso ai progetti `.tex`.
- **Nuove skill:** `help-me-write` (ingresso), `analisi-materiale`, `struttura`,
  `intervista-capitolo`, `scrittura-capitolo`, `figure`.
- Revisione e bibliografia restano le skill della Parte 1.

**Tech Stack:**
- Python ≥ 3.10 con python-docx ≥ 1.2, lxml, pdfplumber, PyYAML, bibtexparser 1.4.x e,
  nuovo, matplotlib ≥ 3.7;
- LibreOffice; latexmk, latexdiff e XeLaTeX (solo per LaTeX);
- pytest.

**Spec:** `docs/superpowers/specs/2026-11-24-scriba-design.md`. Questo piano implementa:
- §2.1 modalità 1 e 2;
- §4 fasi 1, 2 e 4–7;
- §7.1, §7.3 e §7.4;
- §9 casi 1 e 3.

**Ingresso:** `docs/superpowers/handoff/2026-11-25-parte-2.md` (decisioni, caso reale,
priorità). Le correzioni del suo §4 sono i Task 1–3.

**Esecuzione (decisione dell'utente, modalità B):**
- subagent-driven-development;
- ogni task indica il **Modello** del costruttore: *medio* di norma, *capace* solo per i
  task delicati;
- i revisori dei task usano il modello medio;
- la revisione finale dell'intero ramo usa il modello capace, con una sola ondata di
  correzioni;
- **una sola** prova `claude -p`, alla fine (Task 14).

## Banco di prova reale (fuori dal repository)

Il repository pubblico `madashi14/relazione_tirocinio` contiene la bozza LaTeX in
`relazione_tirocinio/Relazione_Tirocinio/`, tre archivi zip e `travi.ipynb` (alla radice,
ora presente). Non va mai copiato nel repository del plugin.

1. Clonare il repository in una cartella esterna (sola lettura).
2. Copiare `Relazione_Tirocinio/` in una cartella di lavoro e togliere `*.aux`, `*.toc`,
   `*.out`, `*.log` e `*.synctex.gz`.
3. Creare i font di prova:
   `python tests/strumenti/font_times_prova.py --dest ~/.local/share/fonts/hmw-prova`
   (Task 1), poi `fc-cache -f`.
   - XeLaTeX legge il nome dalla tabella `name` del file, quindi un alias fontconfig
     non basta.
4. Compilare con `latexmk -xelatex main.tex`. Pacchetti Debian necessari:
   `texlive-lang-italian`, `texlive-latex-extra`, `texlive-science`.

Valori di riferimento misurati il 25/11/2026 sul `main.pdf` caricato dall'autore:
- 33 pagine; la compilazione locale ne dà 36;
- **l'indice del PDF caricato è di una compilazione precedente:** i titoli dei capitoli 4
  e 5 non sono quelli dei sorgenti;
- numero di pagina a 12 pt, top ≈ 771,7 pt su una pagina alta 841,9 pt: fuori dalla
  fascia del 7%;
- passo delle righe 19,5 pt; blocco di testo da 96,1 a ≈ 742,7 pt, cioè 34 righe;
- con le correzioni del Task 1:
  - 21 pagine piene, da 33 a 35 righe;
  - caratteri per riga da 73 a 78: **fuori dal 60–70**, un difetto vero;
- la mediana di un progetto LaTeX con i margini di `layout` per 65 caratteri è 67.

## Global Constraints

- **Identificatori:**
  - plugin `help-me-write`;
  - cartella di stato `.help-me-write/` nella cartella del lavoro;
  - autore delle revisioni `help-me-write`, iniziali `HMW`.
- **Dipendenze:** Python ≥ 3.10; solo `requirements.txt`, cioè `python-docx>=1.2`,
  `lxml`, `pdfplumber`, `PyYAML`, `bibtexparser>=1.4,<2` e, nuovo, `matplotlib>=3.7`,
  richiesto solo da `chart` e `diagram`.
  - Test: `pytest`.
- **Multipiattaforma:**
  - solo `pathlib`, mai `shell=True`;
  - nomi con spazi e accenti supportati.
- **Strumenti esterni:** LibreOffice, latexmk, latexdiff, XeLaTeX e git sono opzionali e
  vengono rilevati.
  - Quando mancano, il comando fallisce con il messaggio di installazione (exit 3), mai
    con un traceback.
  - Fa eccezione `material`, che senza git omette la storia.
- **Originali mai modificati:**
  - ogni comando scrive in un file o in una cartella nuovi;
  - destinazione uguale alla sorgente: exit 2;
  - un output esistente non si sovrascrive: il comando rifiuta e suggerisce il nome
    libero successivo (regola R2, `cli.refuses_existing_output`).
- **Riga di comando:** `python scripts/hmw.py <comando>`; `--json` (o `-o file.json` per i
  comandi con output JSON) stampa JSON.
  - Exit code:
    - 0 ok;
    - 1 controlli non superati (`measure`), correzioni non applicate (`track`) o
      sostituzioni non trovate (`titlepage`);
    - 2 errore d'uso o dati non validi;
    - 3 strumento o pacchetto mancante.
- **Lingua:**
  - istruzioni di skill e prompt in inglese;
  - messaggi all'utente nella sua lingua;
  - documento nella lingua del documento;
  - i valori del file di stato (modalità, stati dei capitoli) sono parole italiane
    fisse, elencate nel Task 4.
- **Indipendenza dalla piattaforma:**
  - le domande sono "ask the user";
  - i sub-agenti sono "dispatch a fresh subagent; if you cannot, do it yourself reading
    only the files listed";
  - script dalle skill: `<this skill's directory>/../../scripts/hmw.py`.
- **Nessuna invenzione (spec §3.2):**
  - ogni fatto e ogni numero del testo viene da un file elencato in
    `.help-me-write/materiale.md` o da una risposta dell'utente registrata in
    `.help-me-write/`;
  - ciò che manca diventa `[DA VERIFICARE: <cosa manca>]`, letterale in ogni lingua, così
    revisore e strumenti lo trovano.
- **Materiale non fidato:**
  - archivi, notebook e script dell'utente non si eseguono, non si importano e non si
    deserializzano mai (`.joblib`, `.pkl`, `.pickle`, `.pt`, `.npy` sono solo elencati);
  - dagli zip si estraggono solo tipi testuali e immagini, dentro la cartella di
    estrazione, con limiti di dimensione.
- **Percorsi nel file di stato:** relativi alla cartella del lavoro, perché la cartella
  passa tra computer e tra Claude Code e Codex.
- **Caratteri per riga:** spazi inclusi.
- **Famiglie di font:** quelle della Parte 1 (`fonts.py`).
- **Ambiente di test:** "Times New Roman" in Linux esiste solo come copia rinominata di
  Liberation Serif, creata da `tests/strumenti/font_times_prova.py`, mai dal plugin.

## Review Focus

1. **Intestazione corrente con testo** (fancyhdr con `\leftmark`, al corpo del testo, a
   ~2 cm dal bordo). Non è una riga di corpo e non impedisce di trovare il numero di
   pagina. Test nel Task 1: `test_running_header_text_is_margin`.
2. **Zip ostile o sporco:** `../`, percorsi assoluti o con lettera di unità, link
   simbolici, un membro enorme, nomi cp437. Nulla va scritto fuori dalla cartella di
   estrazione e ogni membro saltato ha un motivo. Test nel Task 5:
   `test_material_zip_hostile_members`.
3. **CSV esportato all'italiana**, come `experiment_comparison.csv` del caso reale: BOM,
   separatore `;`, eventuale virgola decimale. I valori devono essere letti giusti e
   tracciati. Test nel Task 7: `test_chart_italian_csv`.
4. **`progetto.md` modificato a mano:** YAML rotto, stato sconosciuto, testo libero
   aggiunto. Errore chiaro (exit 2) che nomina il campo; il file non viene mai riscritto
   in modo da perdere il corpo. Test nel Task 4: `test_state_hand_edited_invalid`,
   `test_state_set_preserves_body`.
5. **Varianti di `\input`/`\include`:** senza estensione, in una sottocartella con spazi,
   commentate, con file mancante. Test nel Task 2: `test_tex_headings_input_variants`.

---

## Struttura dei file

```
scripts/helpmewrite/
  measure.py      (mod.) margini adattivi, righe come "spazi riga", caratteri su ogni pagina
  checks.py       (mod.) nuove regole di valutazione e messaggi per sorgente dei titoli
  headings.py     (nuovo) titoli da .tex (\input/\include) e dai segnalibri del PDF
  render.py       (mod.) copia "modifiche accettate" anche senza settings.xml
  bib.py          (mod.) .PDF maiuscolo, esclusione -differenze legata al documento
  cli.py          (mod.) suggerimento con sys.executable, nuovi comandi, matplotlib
  state.py        (nuovo) .help-me-write/progetto.md: lettura, scrittura, prossimo passo, impronte
  detect.py       (nuovo) bozze, linee guida candidate e parti vuote nella cartella
  materiale.py    (nuovo) inventario di cartelle e zip, estrazione sicura, notebook → Markdown
  layout.py       (mod.) `format` su progetti .tex
  figure.py       (nuovo) grafici matplotlib da CSV/JSON con provenienza; schemi a blocchi
  titlepage.py    (nuovo) frontespizio .docx dal modello (caselle di testo comprese)
  assemble.py     (nuovo) capitoli Markdown → .docx con indice, didascalie, bibliografia
  latexproj.py    (nuovo) progetto LaTeX nuovo
  extract.py      (mod.) lo stile "TOC Heading" è un titolo di livello 1
modelli/latex/frontespizio-unibo.tex   modello LaTeX fedele al facsimile Unibo
skills/help-me-write/SKILL.md          ingresso: modalità, stato, ripresa, formato, fasi
skills/analisi-materiale/SKILL.md      + modello-materiale.md
skills/struttura/SKILL.md              indice, frontespizio, confronto bozza, rientro nelle pagine
skills/intervista-capitolo/SKILL.md
skills/scrittura-capitolo/SKILL.md     + formato-capitoli.md (sorgenti Word)
skills/figure/SKILL.md
tests/strumenti/font_times_prova.py    font di prova (solo test)
tests/fixtures/builders.py             (mod.) write_tex_report, build_example_work
tests/test_headings.py, test_state.py, test_detect.py, test_materiale.py, test_figure.py,
tests/test_titlepage.py, test_assemble.py, test_latexproj.py, test_acceptance.py
tests/scenari/bozza-parziale.md + check_bozza_parziale.py   (l'unica prova claude -p)
tests/scenari/da-zero-word.md, ripresa.md                   (da eseguire più avanti)
```

---

### Task 1: Misura su un PDF LaTeX vero — **Modello:** capace

Il numero di pagina a ~2 cm dal bordo finisce tra le righe di corpo. Il blocco di testo
sembra allora più lungo, ogni pagina "perde" righe e nessuna risulta piena. Inoltre
l'indice e le formule falsano il conteggio dei caratteri per riga.

**Files:**
- Modify: `scripts/helpmewrite/measure.py`, `scripts/helpmewrite/checks.py`, `docs/uso.md`
  ("Limiti noti")
- Modify: `tests/fixtures/builders.py` (`write_tex_report`), `tests/conftest.py` (marcatore
  `needs_xelatex`: salta se mancano `xelatex` o `latexmk`)
- Create: `tests/strumenti/font_times_prova.py`
- Test: `tests/test_measure.py`

**Interfaces:**
- Produces:
  - `PageStats.line_slots: int | None`: righe di corpo più spazi riga occupati da righe
    non di corpo (titoli, didascalie, note); `None` se la pagina non è piena;
  - `PageStats.chars_per_full_line`: ora `None` se la pagina ha meno di
    `MIN_FULL_LINES = 5` righe piene di prosa;
  - `slot_counts(body, others, typical_top, typical_bottom, pitch, paragraph_step) ->
    tuple[float, float]`, che restituisce (vuoti, occupati), in frazioni di spazio riga;
  - `margin_positions(pages: list[list[_Line]], pitch: float) -> tuple[list[float],
    list[float]]`, cioè le posizioni (top) di intestazioni e piè di pagina;
  - builder `write_tex_report(folder: Path, *, running_header: bool = False) -> Path`, che
    restituisce il `main.tex`.
- Consumes: `checks.check_rules` (Parte 1), `render.render_pdf`.

**Algoritmo** (da scrivere nel docstring di `measure.py`, al posto dei punti 4–5):
1. **Parole e righe:**
   - parole con `extract_words(x_tolerance=WORD_GAP_PT)`, con `WORD_GAP_PT = 1.5`: con 3
     pt gli spazi stretti del testo giustificato di TeX si perdono;
   - due righe consecutive i cui ingombri verticali si sovrappongono per più di metà
     dell'altezza minore sono una riga sola (il segno "−" rialzato di una formula).
2. **Passo:** è la mediana dei salti tra righe consecutive del corpo del testo, escluse
   quelle nelle fasce fisse del 7%.
3. **Posizioni di margine:**
   - per ogni pagina, l'ultima riga è candidata piè di pagina se è sola sulla pagina o se
     dista dalla precedente più di `MARGIN_GAP_PITCHES = 1.5` passi; la prima riga è
     candidata intestazione allo stesso modo;
   - una posizione (top a ±`2.0` pt) condivisa da candidati su almeno
     `MARGIN_SHARE = 0.3` delle pagine con testo è una posizione di margine.
4. **Righe di margine:** sono quelle nelle fasce fisse del 7%, più la prima o l'ultima
   riga di una pagina che sta a ±2 pt da una posizione di margine.
   - Le righe di margine non sono mai di corpo.
   - `has_page_number` cerca `_PAGE_NUMBER` solo tra le righe di margine.
5. **Pagina piena** (sostituisce il rapporto 0,90 e `missing_slots`):
   - si sommano, in frazioni di passo e prima di arrotondare, i salti sopra la prima riga
     di corpo (dal top tipico), dentro la pagina (solo quelli più larghi di
     `paragraph_step + 0.5·passo`) e sotto l'ultima (fino al fondo tipico);
   - un salto che contiene una riga non di corpo e non di margine è **occupato**;
     altrimenti è **vuoto**, per esempio quello di una figura senza didascalia o di un
     testo che finisce prima;
   - la pagina è piena se `round(vuoti) <= MISSING_SLOTS (1)` e non è l'ultima;
   - `line_slots = righe di corpo + round(occupati)`;
   - top e fondo tipici sono le mediane delle pagine senza la prima e l'ultima.
6. **Righe di prosa piene:**
   - una riga è piena se è larga tra il 90 e il 110% della larghezza di riferimento;
   - una riga piena non è di prosa se due parole consecutive distano più di
     `2 × corpo` (voce d'indice col numero a destra, riga di tabella), o se contiene
     puntini di guida `(?:\.\s?){4,}`.

**Regole in `checks.py`:**
- `lines_per_page` usa `line_slots` sulle pagine piene; il dettaglio aggiunge "a heading
  or caption counts for the lines it takes".
- `chars_per_line` valuta ogni pagina tranne la 1 con `chars_per_full_line` non `None`,
  ultima pagina compresa.
  - Motivo di esclusione: `"fewer than 5 full-width lines of text"`.
- `page_numbers`: il dettaglio dice "in the header or footer (the lines above the text or
  below it)".

- [ ] **Step 1: font di prova e fixture.**
  - `tests/strumenti/font_times_prova.py --dest <dir>` scrive quattro TTF ("Times New
    Roman" Regular, Bold, Italic, Bold Italic) copiando Liberation Serif e riscrivendo con
    fontTools i nomi 1, 3, 4, 6 e 16:
    - PostScript `TimesNewRomanPSMT`, `TimesNewRomanPS-BoldMT`, `-ItalicMT`,
      `-BoldItalicMT`;
    - Liberation mancante: messaggio ed exit 2.
  - `write_tex_report` crea `main.tex`, `capitoli/01..03.tex` e `immagini/fig.png`
    (`write_png`).
    - Preambolo identico per impaginazione alla bozza reale:
      - `report` 12pt a4 oneside, `babel` italian;
      - `fontspec` `\setmainfont{TeX Gyre Termes}`;
      - `geometry` top 3.3, bottom 3.2, left e right 3.9 cm;
      - `\setstretch{1.35}`, `parindent 1.2em`, `parskip 0`, `indentfirst`;
      - `fancyhdr` con `\thepage` al centro del piè di pagina, stile `plain` ridefinito;
      - `titlesec` hang `\Large\bfseries` con spazio dopo di 20pt, `hyperref`.
    - `running_header=True` aggiunge `\fancyhead[C]{\leftmark}`.
    - Corpo:
      - `titlepage` di 8 righe;
      - `\pagenumbering{roman}\tableofcontents\clearpage\pagenumbering{arabic}`;
      - "Introduzione" (2 paragrafi);
      - "Attività svolte" con tre `\section`, i paragrafi di `testo_italiano.txt` ripetuti
        fino a ~12 pagine, una figura con didascalia, un'equazione `\[ \]` e una
        `tabular` di 4 righe;
      - "Conclusioni" (2 paragrafi).

- [ ] **Step 2: test che falliscono** (in `tests/test_measure.py`; `_line` riceve un
  parametro `size=12.0`):

```python
def test_overlapping_fragments_are_one_line():  # "−" rialzato di 2,3 pt + resto della formula
    lines = _merge_overlapping([_line(100.0), _line(102.3)])
    assert len(lines) == 1 and len(_merge_overlapping([_line(100.0), _line(119.5)])) == 2

def test_slot_counts_heading_inside_is_occupied():
    pitch, top = 19.5, 96.0
    bottom = top + 33 * pitch + 12.0
    body = [_line(top + i * pitch) for i in range(15)] + [_line(top + (i + 18) * pitch) for i in range(16)]
    empty, occupied = slot_counts(body, [_line(top + 16 * pitch, size=14.4)], top, bottom, pitch, pitch)
    assert round(empty) == 0 and round(occupied) == 3     # line_slots = 31 + 3 = 34

def test_slot_counts_figure_and_early_end_are_empty():
    pitch, top = 19.5, 96.0
    bottom = top + 33 * pitch + 12.0
    figure_at_top = [_line(top + (i + 7) * pitch) for i in range(27)]
    early_end = [_line(top + i * pitch) for i in range(28)]
    assert round(slot_counts(figure_at_top, [], top, bottom, pitch, pitch)[0]) == 7
    assert round(slot_counts(early_end, [], top, bottom, pitch, pitch)[0]) == 6

def test_slot_counts_sum_fractions_before_rounding():
    # 0.4 above + 0.6 inside + 0.4 below = 1.4 -> 1 (full); 0.6 + 0.6 + 0.6 = 1.8 -> 2
    ...  # build both pages from the same pitch/top/bottom; assert round(empty) == 1 and == 2

def test_margin_positions_find_footer_not_last_body_line():
    # 10 pages: 30 body lines from 96.0 at pitch 19.5, footer "N" at 771.7;
    # page 11: body lines down to 783.0 and no footer
    headers, footers = margin_positions(pages, 19.5)
    assert headers == [] and len(footers) == 1 and abs(footers[0] - 771.7) <= 2.0

@needs_xelatex
def test_latex_report_like_real_draft(tmp_path):
    main = write_tex_report(tmp_path / "rel")
    m = measure(main, load_rules(UNIBO), tmp_path / "w")
    checks = {c.rule: c for c in m.checks}
    assert checks["page_numbers"].ok
    assert checks["lines_per_page"].ok and "could not evaluate" not in checks["lines_per_page"].detail
    full = [p for p in m.pages if p.is_full]
    assert len(full) >= 4 and all(33 <= p.line_slots <= 35 for p in full)
    cpl = checks["chars_per_line"]
    assert not cpl.ok and "could not evaluate" not in cpl.detail       # 13.2 cm: ~76 characters
    evaluated = [p for p in m.pages if p.number != 1 and p.chars_per_full_line is not None]
    assert 2 not in [p.number for p in evaluated]                       # table of contents
    assert all(71 <= p.chars_per_full_line <= 80 for p in evaluated)

@needs_xelatex
def test_running_header_text_is_margin(tmp_path):
    main = write_tex_report(tmp_path / "rel", running_header=True)
    m = measure(main, load_rules(UNIBO), tmp_path / "w")
    checks = {c.rule: c for c in m.checks}
    assert checks["page_numbers"].ok and checks["lines_per_page"].ok
    assert all(p.line_slots <= 35 for p in m.pages if p.is_full)
```

  - Sostituire `test_missing_slots_figure_at_top_and_heading_inside` con i test sopra.
  - Il test docx "finding 8" (`test_figure_at_top_and_heading_with_early_end_are_not_full`)
    resta invariato e deve continuare a passare.

- [ ] **Step 3: verificare che falliscano.**
  Run: `python -m pytest tests/test_measure.py -q`. Expected: FAIL (`_merge_overlapping`,
  `slot_counts` e `margin_positions` non esistono; la misura LaTeX dà "could not
  evaluate").

- [ ] **Step 4: implementare** l'algoritmo sopra in `measure.py` e le regole in
  `checks.py`.
  - Aggiornare i test esistenti il cui motivo di esclusione atteso cambia (pagina
    piena → spazi riga; caratteri per riga sull'ultima pagina).
  - Nessuna asserzione su un FAIL che deve restare FAIL va tolta.
  - Riscrivere il docstring di `measure.py`: punti 1–6 sopra, più le deroghe della Parte 1
    ancora valide.
  - In `docs/uso.md`, "Limiti noti", la voce sulle pagine piene diventa: righe per pagina
    sulle pagine piene, dove un titolo o una didascalia contano per le righe che
    occupano; caratteri per riga su ogni pagina con almeno 5 righe piene di prosa.

- [ ] **Step 5: verificare.**
  Run: `python -m pytest -q`. Expected: tutto PASS.

- [ ] **Step 6: banco di prova reale** (registrare i numeri nel rapporto del task).
  Run: `python scripts/hmw.py measure "<bozza>/main.pdf" --rules
  tests/fixtures/linee-guida-unibo.yaml`, sia sul PDF caricato sia su quello compilato.
  Expected:
  - `page_numbers` OK;
  - `lines_per_page` OK, con valori tra 33 e 35;
  - `chars_per_line` FAIL, con valori tra 72 e 79 e nessun "could not evaluate".

- [ ] **Step 7: commit**

```bash
git add scripts/helpmewrite/measure.py scripts/helpmewrite/checks.py docs/uso.md tests/
git commit -m "fix: measure real LaTeX PDFs (adaptive header/footer, line slots, prose lines)"
```

---

### Task 2: Titoli da LaTeX e dai segnalibri del PDF — **Modello:** medio

**Files:**
- Create: `scripts/helpmewrite/headings.py`
- Modify: `scripts/helpmewrite/measure.py` (`measure()`, `Measurement.headings_source`),
  `scripts/helpmewrite/checks.py` (`_section_checks`), `docs/uso.md`
- Test: `tests/test_headings.py`, `tests/test_measure.py`

**Interfaces:**
- Produces:
  - `tex_headings(main: Path) -> list[dict]`, con elementi `{"text", "heading_level",
    "file", "line"}` e `file` relativo alla cartella di `main`;
  - `tex_parts(main: Path) -> list[Path]`: i file inclusi esistenti, in ordine, senza
    `main` (lo usa `detect`, Task 4);
  - `pdf_headings(pdf: Path) -> list[dict] | None`, che restituisce `None` se il PDF non
    ha segnalibri;
  - `document_headings(doc: Path, pdf: Path) -> tuple[list[dict] | None, str]`, con
    sorgente `"docx"`, `"tex"`, `"pdf-bookmarks"` o `"none"`;
  - `Measurement.headings_source: str`.
- Consumes: `extract.extract` per `.docx` (come oggi), `measure.section_spans`.

**Regole di `tex_headings`:**
- **Lettura dei file:**
  - testo dopo `%` non preceduto da `\` ignorato;
  - nulla dopo `\end{document}`;
  - `\input{x}` e `\include{x}` risolti dalla cartella di `main`, con `.tex` aggiunto se
    manca;
  - un file mancante o già visitato si salta senza errore.
- **Comandi riconosciuti:** `\chapter`, `\section` e `\subsection`, anche `*` e con
  `[breve]`; il titolo è l'argomento tra graffe, anche annidate.
  - Livelli: con almeno un `\chapter`, chapter 1, section 2 e subsection 3; altrimenti
    section 1 e subsection 2.
- **Voci generate**, tutte di livello 1, con la lingua da `babel`/`polyglossia` (italian
  o english; senza pacchetto, english):
  - `\tableofcontents` → "Indice" / "Contents";
  - `\listoffigures` → "Elenco delle figure" / "List of Figures";
  - `\bibliography{…}` o `\printbibliography` → con `report`/`book` "Bibliografia" /
    "Bibliography", con `article` "Riferimenti bibliografici" / "References".
- **Testo del titolo:**
  - `\emph`, `\textbf`, `\textit`, `\texttt` e `\textsc` tengono l'argomento;
  - `\label` e `\footnote` si tolgono;
  - `~` diventa spazio, `\&` diventa &, `--` diventa –;
  - accenti `\'e`, `\`a` e simili diventano lettere accentate;
  - gli altri comandi si tolgono e gli spazi si comprimono.

**Messaggi in `_section_checks`, secondo `headings_source`:**
- titolo trovato solo come riga di testo:
  - `"tex"`: `"'<riga>' found on page N as plain text, not as \chapter or \section"`;
  - `"pdf-bookmarks"`: `"… not among the PDF bookmarks"`;
  - `"docx"`: invariato;
- `"none"`: `"cannot determine sections: this PDF has no bookmarks (headings are read from
  .docx, from .tex sources or from PDF bookmarks); check by hand for a heading …"`.

- [ ] **Step 1: test che falliscono**

```python
def test_tex_headings_follow_include_and_input(tmp_path):
    # main.tex: babel italian, \tableofcontents, \include{capitoli/01_intro}
    #   (\chapter{Introduzione} + \section{Obiettivi \emph{del} tirocinio\label{s:o}}),
    #   %\include{capitoli/03} (contains \chapter{Non incluso}),
    #   \input{capitoli/02.tex} (\chapter*{Conclusioni}), \bibliography{bib}
    assert [(h["text"], h["heading_level"]) for h in tex_headings(main)] == [
        ("Indice", 1), ("Introduzione", 1), ("Obiettivi del tirocinio", 2),
        ("Conclusioni", 1), ("Bibliografia", 1)]

def test_tex_headings_input_variants(tmp_path):
    # \input{sotto cartella/parte} (no extension, folder with a space), \input{./parte2.tex},
    # \include{manca} (missing: skipped), "% \input{commentato}", a file \input twice (cycle)
    ...  # assert the titles of parte and parte2 appear once each, in order, nothing else

def test_tex_headings_article_english():
    # article, no babel: \section -> 1, \subsection -> 2, \tableofcontents -> "Contents",
    # \bibliography -> "References"

@needs_xelatex
def test_pdf_headings_from_bookmarks(tmp_path):
    pdf = render_pdf(write_tex_report(tmp_path / "r"), tmp_path / "w")
    titles = [(h["text"], h["heading_level"]) for h in pdf_headings(pdf)]
    assert ("Introduzione", 1) in titles and ("Conclusioni", 1) in titles
    assert pdf_headings(write_pdf_from_paragraphs(tmp_path / "x.pdf", ["a"])) is None

@needs_xelatex
def test_measure_latex_sections(tmp_path):
    m = measure(write_tex_report(tmp_path / "r"), load_rules(UNIBO), tmp_path / "w")
    checks = {c.rule: c for c in m.checks}
    assert m.headings_source == "tex"
    for rid in ("section:indice:present", "section:introduzione:present",
                "section:conclusione:present", "section:introduzione:pages"):
        assert rid in checks and "cannot determine" not in checks[rid].detail
    assert checks["section:indice:present"].ok
```

  Più `test_measure_pdf_without_bookmarks_message`: `write_pdf_from_paragraphs` misurato
  produce il messaggio `"none"` sopra.

- [ ] **Step 2: verificare che falliscano**: `python -m pytest tests/test_headings.py -q`
  (modulo inesistente).
- [ ] **Step 3: implementare** `headings.py`.
  - Per i segnalibri: `pdfplumber.open(pdf).doc.get_outlines()` (pdfminer), con
    eccezione `PDFNoOutlines` o qualunque errore → `None`.
  - `measure()` chiama `document_headings`; `check_rules` riceve `headings_source`.
  - In `docs/uso.md` togliere il limite "per LaTeX le sezioni non vengono controllate" e
    scrivere da dove si leggono i titoli.
- [ ] **Step 4: verificare**: `python -m pytest -q`, tutto PASS.
- [ ] **Step 5: banco di prova reale.**
  - `measure` sul `main.tex` compilato: `section:indice`, `introduzione` e `conclusione`
    presenti; `section:conclusione:pages` FAIL o OK secondo il capitolo vuoto, ma mai
    "cannot determine".
  - Sul PDF caricato: titoli dai segnalibri.
- [ ] **Step 6: commit**: `feat: read section headings from LaTeX sources and PDF bookmarks`.

---

### Task 3: Punti minori della Parte 1 — **Modello:** medio

**Files:**
- Modify: `scripts/helpmewrite/cli.py` (`install_hint`, `doctor_command`), `bib.py`
  (`find_local_sources`, `_own_pdf`), `render.py` (`_accepted_copy`),
  `skills/revisione-bibliografia/prompt-revisore-bibliografia.md` (riga di `pdftext`),
  `docs/uso.md` e `README.md` dove descrivono l'exit code 1
- Test: `tests/test_cli.py`, `tests/test_bib.py`, `tests/test_render.py`,
  `tests/test_skills_static.py`

**Comportamenti:**
1. `install_hint()` e `doctor_command()` usano `sys.executable` tra virgolette
   (`"<sys.executable>" -m pip install -r "<requirements>"`).
2. `find_local_sources` trova i PDF con estensione in qualunque maiuscola (`.PDF`,
   `.Pdf`).
3. `_own_pdf`:
   - con `document` noto, un `*-differenze.pdf` è escluso solo se il nome senza il
     suffisso è il nome del documento;
   - una cartella `*-revisionato*` è esclusa solo se il suo nome comincia con il nome
     del documento o della sua cartella di progetto;
   - con `document=None` resta la regola attuale.
4. `_accepted_copy`: se `word/settings.xml` manca, la copia ne riceve uno.
   - Contenuto: radice `w:settings` con il solo `w:revisionView` di
     `accepted_view_settings`.
   - Servono anche l'Override del content type
     `application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml` e la
     relazione `…/relationships/settings` in `word/_rels/document.xml.rels`.
   - Ricade sull'originale solo se il file non è uno zip valido.
5. Nel prompt del revisore bibliografico l'output di `pdftext` diventa
   `{SOURCE_TEXTS}/<path of the PDF relative to the work folder, every / or \ replaced by
   __, without .pdf>.json`. Due PDF omonimi in cartelle diverse non si sovrascrivono più.
6. Ovunque `docs/uso.md` o `README.md` descrivono l'exit code 1, la dicitura diventa quella
   delle Global Constraints.

- [ ] **Step 1: test che falliscono.**
  - `test_install_hint_uses_running_python`: `sys.executable in install_hint()` e in
    `doctor_command()`.
  - `test_find_local_sources_uppercase_suffix`: una fonte `Articolo.PDF` viene trovata.
  - `test_unrelated_differenze_pdf_is_a_source`: con il documento `bozza.docx`,
    `Confronto-differenze.pdf`, che contiene il titolo della voce, è una fonte; mentre
    `bozza-differenze.pdf` resta escluso.
  - `test_render_accepts_changes_without_settings_part` (soffice): un `.docx` con una
    cancellazione tracciata "TESTOCANCELLATO" e un inserimento "TESTOINSERITO", senza
    `word/settings.xml`. Il PDF contiene "TESTOINSERITO" e non "TESTOCANCELLATO".
  - `test_bib_prompt_unique_source_names`: il prompt contiene `replaced by __`.
- [ ] **Step 2: verificare che falliscano**:
  `python -m pytest tests/test_cli.py tests/test_bib.py tests/test_render.py tests/test_skills_static.py -q`.
- [ ] **Step 3: implementare** i sei punti.
- [ ] **Step 4: verificare**: `python -m pytest -q`, tutto PASS.
- [ ] **Step 5: commit**: `fix: part 1 leftovers (python hint, .PDF, own-PDF rule, settings part, source names)`.

---

### Task 4: File di stato e rilevamento della modalità — **Modello:** medio

**Files:**
- Create: `scripts/helpmewrite/state.py`, `scripts/helpmewrite/detect.py`
- Modify: `scripts/helpmewrite/cli.py` (comandi `state`, con pacchetto `yaml`, e `detect`,
  con `lxml` e `docx`)
- Test: `tests/test_state.py`, `tests/test_detect.py`

**Formato di `.help-me-write/progetto.md`** (spec §7.1): intestazione YAML fra righe
`---`, poi il corpo Markdown libero ("## Decisioni", "## Domande aperte", note).

```yaml
version: 1
mode: bozza-parziale            # da-zero | bozza-parziale | solo-revisione
document_type: relazione-tirocinio
profile: relazione-tirocinio
format: latex                   # latex | word | null
language: it
draft: Relazione_Tirocinio/main.tex          # relativo alla cartella del lavoro
output: Relazione_Tirocinio-help-me-write    # cartella di output confermata
outline_approved: false
title_page_approved: false
chapters:
  - {id: 06-conclusioni, title: Conclusioni, kind: conclusione, status: da-fare,
     source: Relazione_Tirocinio-help-me-write/capitoli/06_conclusioni.tex,
     notes: .help-me-write/capitoli/06-conclusioni-intervista.md}
fingerprints: {Relazione_Tirocinio-help-me-write: <sha256>}
```

- **Valori ammessi:**
  - `kind`: `introduzione`, `corpo`, `conclusione`, `allegato`;
  - `status`: `da-fare` → `intervista-fatta` → `scritto` → `approvato` → `revisionato`;
    ogni transizione è ammessa;
  - `id`: `[a-z0-9][a-z0-9-]*`, unico.

**Interfaces:**
- Produces (`state.py`):
  - `Chapter(id, title, kind, status="da-fare", source=None, notes=None)`;
  - `ProjectState(mode, document_type, profile, format, language, draft, output,
    outline_approved, title_page_approved, chapters: list[Chapter],
    fingerprints: dict[str, str], body: str)`;
  - `StateError(problems: list[str])`;
  - `load_state(work: Path) -> ProjectState` e `save_state(work: Path, state) -> None`;
    il salvataggio è atomico (file temporaneo + `replace`) e il corpo resta intatto;
  - `next_step(work: Path, state) -> dict`, che restituisce
    `{"phase": str, "chapter": str | None, "why": str}`;
  - `fingerprint(path: Path) -> str`, cioè sha256 di un file; per una cartella, dei
    percorsi relativi ordinati più il contenuto dei suoi `.tex`, `.bib` e `.docx`;
  - `modified(work: Path, state) -> dict[str, str]`, con valori `unchanged`, `modified`
    o `missing`.
- Produces (`detect.py`): `detect(work: Path) -> dict`, con
  `{"state": str | None, "drafts": [...], "guidelines": [...], "ignored": [...]}`. Ogni
  bozza è `{"path", "format", "parts", "empty_parts", "words"}`, con `format` in latex,
  word, markdown, text o pdf.
- CLI:
  - `hmw state init <work> --mode M [--format F] [--type T] [--profile P] [--language L]
    [--draft D] [--output O]`: rifiuta se esiste;
  - `hmw state show <work>`: stato più `next`;
  - `hmw state set <work> key=value…`: chiavi scalari dell'intestazione; `true`/`false`;
    `null` per svuotare;
  - `hmw state outline <work> --from outline.json`: lista di `{id, title, kind}`; tiene
    `status`, `source` e `notes` degli id già presenti; i nuovi sono `da-fare`; quelli
    tolti sono elencati in `removed`;
  - `hmw state chapter <work> <id> [--status S] [--source P] [--notes P]`;
  - `hmw state record <work> <path>…`;
  - `hmw state modified <work>`.
  - Exit 0 o 2.

**`next_step`** (fasi in quest'ordine; la prima che manca vince):
- **`solo-revisione`:** `linee-guida` se manca `.help-me-write/linee-guida.yaml`,
  altrimenti `revisione`.
- **Altre modalità:**
  1. `materiale` se manca `.help-me-write/materiale.md`;
  2. `linee-guida`;
  3. `formato` se `format` è null;
  4. `struttura` se l'indice non è approvato;
  5. `frontespizio` se il frontespizio non è approvato;
  6. poi i capitoli in ordine di scrittura: prima `corpo` nell'ordine della lista, poi
     `introduzione`, `conclusione` e `allegato`. Il primo non `approvato`/`revisionato`
     decide:
     - `da-fare` → `intervista`;
     - `intervista-fatta` → `scrittura`;
     - `scritto` → `approvazione`;
  7. tutti approvati → `revisione`; tutti `revisionato` → `fine`.

**`detect`:**
- **Cartelle saltate:** `.git`, `.help-me-write`, `__pycache__`, `node_modules`, `.venv`,
  `venv`, `.ipynb_checkpoints`, e quelle che finiscono in `-revisionato` o
  `-help-me-write`.
- **Bozze:**
  - LaTeX: un `.tex` con `\documentclass`; le sue parti sono `headings.tex_parts(main)`
    (Task 2);
  - `empty_parts`: parti con meno di 200 caratteri, tolti commenti, `\chapter{…}`,
    `\section{…}` e spazi;
  - `.docx`: esclusi `~$*`, le copie `-revisionato`, `-formattato` e `-differenze` e i
    nomi da linee guida;
  - `.md`/`.txt`: solo con nome che contiene relazione, report, bozza, draft, tesi o
    capitolo;
  - `.pdf`: solo se non esiste una bozza sorgente con lo stesso nome.
- **Linee guida candidate:** i nomi con linee guida, regolamento, norme, facsimile,
  modello, template, bando o guidelines.

- [ ] **Step 1: test che falliscono**

```python
def test_state_round_trip_and_next_step(tmp_path):
    assert main(["state", "init", str(tmp_path), "--mode", "da-zero"]) == 0
    s = load_state(tmp_path); assert s.mode == "da-zero" and s.format is None
    assert next_step(tmp_path, s)["phase"] == "materiale"

ALL = ["materiale.md", "linee-guida.yaml"]          # files in .help-me-write/
DONE = {"format": "word", "outline_approved": True, "title_page_approved": True}

@pytest.mark.parametrize("files,fields,chapters,phase,chapter", [
    (["materiale.md"], {}, [], "linee-guida", None),
    (["materiale.md", "linee-guida.yaml"], {"format": None}, [], "formato", None),
    (ALL, {"format": "word", "outline_approved": True, "title_page_approved": True},
     [("01-a", "corpo", "approvato"), ("02-b", "corpo", "intervista-fatta"),
      ("00-intro", "introduzione", "da-fare")], "scrittura", "02-b"),
    (ALL, DONE, [("01-a", "corpo", "approvato"), ("00-intro", "introduzione", "da-fare")],
     "intervista", "00-intro"),
])
def test_next_step_phases(tmp_path, files, fields, chapters, phase, chapter): ...

def test_state_set_preserves_body(tmp_path):   # body "## Decisioni\n- Word\n" survives set/chapter/outline
def test_state_hand_edited_invalid(tmp_path):
    # broken YAML; status "fatto"; unknown key "formato": exit 2, stderr names the line/field,
    # file bytes unchanged
def test_state_paths_are_relative(tmp_path):
    # record <abs path inside work> stores the relative path; a path outside work: exit 2
def test_state_modified_reports_hand_edits(tmp_path):
    # record a .docx and a LaTeX folder; edit one .tex -> {"<folder>": "modified", "<docx>": "unchanged"}
def test_outline_keeps_progress(tmp_path):
    # chapters 01 (approvato), 02; new outline 02, 03 -> 02 keeps status, 03 da-fare, removed == ["01"]
def test_detect_partial_latex_draft(tmp_path):
    # Relazione/main.tex + capitoli/01..06 (06 = "\chapter{Conclusioni}\n% da scrivere\n"),
    # Facsimile.docx, bozza-revisionato.docx, script.zip
    d = detect(tmp_path)
    assert d["drafts"][0]["format"] == "latex" and d["drafts"][0]["empty_parts"] == ["Relazione/capitoli/06.tex"]
    assert d["guidelines"] == ["Facsimile.docx"] and all("revisionato" not in x["path"] for x in d["drafts"])
```

- [ ] **Step 2: verificare che falliscano**:
  `python -m pytest tests/test_state.py tests/test_detect.py -q`.
- [ ] **Step 3: implementare** `state.py` e `detect.py`, poi registrarli in
  `cli._COMMANDS`.
  - L'intestazione si scrive con `yaml.safe_dump(sort_keys=False, allow_unicode=True)`.
  - Errori: `StateError` → exit 2, con un problema per riga.
- [ ] **Step 4: verificare**: `python -m pytest -q`, tutto PASS.
- [ ] **Step 5: commit**: `feat: project state file and draft detection`.

---

### Task 5: Lettura del materiale: cartelle, zip, notebook — **Modello:** medio

**Files:**
- Create: `scripts/helpmewrite/materiale.py`
- Modify: `scripts/helpmewrite/cli.py` (`material` e `notebook`, nessun pacchetto)
- Test: `tests/test_materiale.py`

**Interfaces:**
- Produces:
  - `kind_of(name: str) -> str`, uno tra code, notebook, data, document, image, archive,
    model, other.
    - code: `.py .m .c .cpp .h .java .js .ts .r .jl .sh .bat .ps1 .apdl .mac .inp`;
    - notebook: `.ipynb`;
    - data: `.csv .tsv .json .xlsx .xls .dat .parquet .mat .h5 .hdf5`;
    - document: `.md .txt .docx .pdf .tex .bib .odt .rtf`;
    - image: `.png .jpg .jpeg .svg .gif .tif .tiff .bmp`;
    - archive: `.zip .tar .gz .tgz .7z .rar`;
    - model: `.joblib .pkl .pickle .pt .pth .onnx .ckpt .npy .npz`.
  - `inventory(work: Path, extract_dir: Path | None = None) -> dict` (struttura sotto);
  - `notebook_markdown(ipynb: Path, images_dir: Path | None) -> tuple[str, list[Path]]`;
  - `MaterialError`.
- CLI:
  - `hmw material <work> [--extract DIR] [-o inventario.json]`;
  - `hmw notebook <file.ipynb> -o <out.md> [--images DIR]`: rifiuta un `out.md` già
    esistente, regola R2.

**`inventory`** restituisce
`{"root", "files": [{"path", "kind", "size", "modified"}], "archives": [...], "git", "dates", "skipped_dirs", "truncated", "counts_by_dir"}`.
- **Cartelle saltate:** come `detect`, più `.mypy_cache`, `.pytest_cache`, `env` e la
  cartella `extract_dir`.
- **Cartelle grandi:** al massimo `MAX_FILES = 2000` file elencati; oltre,
  `truncated: true` e `counts_by_dir` con il numero di file per cartella.
- **Archivi:** si apre solo `.zip`. Gli altri archivi sono elencati con
  `"opened": false`.
  - Ogni membro è `{"name", "kind", "size", "date"}`, con la data da
    `ZipInfo.date_time`.
  - Con `extract_dir` si estraggono solo i membri code, notebook, data testuali (`.csv
    .tsv .json .dat .txt`), document testuali (`.md .txt .tex .bib`) e image.
    - Limiti: al massimo `MAX_MEMBER_BYTES = 20 MB` ciascuno e `MAX_EXTRACT_BYTES =
      200 MB` in tutto.
    - Destinazione: `<extract_dir>/<percorso dell'archivio con / → __, senza .zip>/`.
    - Rifiutati con motivo in `skipped`:
      - percorsi assoluti, con lettera di unità o con `..`;
      - link simbolici, riconosciuti dal tipo in `external_attr >> 16`;
      - membri oltre i limiti;
      - modelli: `"model file: listed, never loaded"`;
      - zip annidati: `"nested archive: not opened"`.
    - Una destinazione già presente per quell'archivio non si riscrive
      (`"extracted_to"` più `"already extracted"`).
- **`git`:** solo se `<work>/.git` esiste e git è nel PATH:
  `git -C <work> log --format=%ad --date=short`, da cui
  `{"commits", "first", "last"}`; altrimenti `null`.
- **`dates`:** `{"files": {"first", "last"}, "archives": {"first", "last"}, "reliable":
  bool, "note": str}`.
  - `reliable` è falso se le date dei file stanno in 2 giorni e git manca o ha un solo
    commit.
  - La nota (in inglese) dice che sono probabilmente le date di una copia o di un upload.

**`notebook_markdown`:**
- celle in ordine, con `## Cell N (markdown|code)`;
- codice in blocchi ```` ```python ````;
- output testuali troncati a `MAX_OUTPUT_LINES = 30`, con `[... N more lines]`;
- immagini `image/png` salvate come `<stem>-cell<N>-<k>.png`, solo se la firma PNG è
  valida, e citate nel Markdown;
- errori come `ename: evalue`;
- JSON non valido → `MaterialError`, exit 2.

- [ ] **Step 1: test che falliscono**

```python
def test_material_inventory_kinds_and_skips(tmp_path):
    # files: a.py, d/metrics.csv, n.ipynb, m.joblib, .git/x, node_modules/y.js, .help-me-write/z.md
    inv = inventory(tmp_path)
    assert {f["path"]: f["kind"] for f in inv["files"]} == {
        "a.py": "code", "d/metrics.csv": "data", "n.ipynb": "notebook", "m.joblib": "model"}

def test_material_zip_extracts_text_members_only(tmp_path):
    # rf.zip: rf/train.py, rf/metrics (2).json, rf/model.joblib, rf/fig.png, rf/inner.zip
    inv = inventory(work, tmp_path / "estratti")
    # extracted: train.py, metrics (2).json, fig.png; skipped with reasons: model.joblib, inner.zip

def test_material_zip_hostile_members(tmp_path):
    # members "../evil.py", "/abs.py", "C:/x.py", a symlink (external_attr 0o120777 << 16),
    # one bigger than MAX_MEMBER_BYTES (monkeypatched to 10), a cp437-flagged name "caf\x82.py"
    # -> nothing written outside estratti/<archive>/ (walk tmp_path), each listed in skipped
    #    with a reason; the cp437 file extracted inside

def test_material_dates_unreliable_and_archive_dates(tmp_path):
    # all files mtime 2026-11-24; zip members dated 2026-10-02 -> reliable False,
    # archives.first == "2026-10-02"

def test_material_git_history(tmp_path):   # skip if git missing; 2 commits dated 2026-10-01 and 2026-11-20
def test_material_truncates_large_folder(tmp_path, monkeypatch):   # MAX_FILES=50, 120 files
def test_notebook_markdown_images_and_truncation(tmp_path):        # 40-line stream output, one PNG output
def test_material_module_never_loads_user_code():
    src = (ROOT / "scripts/helpmewrite/materiale.py").read_text(encoding="utf-8")
    assert not re.search(r"\b(pickle|joblib|runpy|importlib|exec\(|eval\()", src)
```

- [ ] **Step 2: verificare che falliscano**: `python -m pytest tests/test_materiale.py -q`.
- [ ] **Step 3: implementare** `materiale.py` e i comandi. L'output testuale di `material`
  è un riepilogo: conteggi per tipo, archivi con date, git, nota sulle date, file saltati.
- [ ] **Step 4: verificare**: `python -m pytest -q`, tutto PASS.
- [ ] **Step 5: banco di prova reale.** Sul clone di `relazione_tirocinio`, con
  `--extract` in una cartella temporanea:
  - tre archivi;
  - i `.joblib` saltati come modelli;
  - date degli archivi dal 2026-10-02 al 2026-11-24;
  - `reliable` falso.

  Poi `hmw notebook travi.ipynb` scrive Markdown e immagini.
- [ ] **Step 6: commit**: `feat: material inventory with safe zip extraction and notebook reader`.

---

### Task 6: `format` per i progetti LaTeX — **Modello:** medio

`format` oggi lavora solo su `.docx`. Per la bozza reale (caratteri per riga 73–78 contro
60–70) serve una copia del progetto con l'impaginazione corretta, e la stessa copia è la
"copia di lavoro" della modalità 2.

**Files:**
- Modify: `scripts/helpmewrite/layout.py` (`add_format_arguments`, `run_format`, nuova
  `apply_layout_tex`)
- Test: `tests/test_format.py`

**Interfaces:**
- Produces: `apply_layout_tex(main: Path, layout: Layout | None, out_dir: Path) ->
  list[str]`, con le modifiche fatte e gli avvisi. CLI: `hmw format <main.tex> -o <cartella>
  [--layout L]`. Per `.tex`, `--layout` è facoltativo (senza: copia semplice); per
  `.docx` resta obbligatorio (exit 2 se manca).
- Consumes: `track_tex._prepare_out_dir`, che fissa le regole su cartelle annidate o già
  piene.

**Regole:**
- **Copia:** si copia la cartella di `main` senza `*.aux`, `*.log`, `*.toc`, `*.out`,
  `*.lof`, `*.lot`, `*.synctex.gz`, `*.fdb_latexmk`, `*.fls`, `*.bbl`, `*.blg`, `*.xdv` e
  `<main>.pdf`. Gli altri PDF restano: possono essere figure.
- **Blocco d'impaginazione:** si inserisce subito prima di `\begin{document}` nel
  `main.tex` copiato.

```
% help-me-write: impaginazione (inizio)
\usepackage{geometry}          % solo se il preambolo non carica già geometry
\usepackage{setspace}          % solo se non carica già setspace
\geometry{a4paper,top=2.5cm,bottom=2.5cm,left=4.83cm,right=4.83cm}
\setstretch{1.4552}
% help-me-write: impaginazione (fine)
```

- **Valori del blocco:**
  - `\setstretch` = `line_pitch_pt / baselineskip normale`, con baselineskip 12.0 a
    10pt, 13.6 a 11pt e 14.5 a 12pt; la dimensione viene da `\documentclass[..pt]`
    (default 10) e il valore ha 4 decimali;
  - la carta è `a4paper` per (21, 29.7), altrimenti `paperwidth`/`paperheight`;
  - un blocco già presente si sostituisce.
- **Font:** non si cambiano mai. Se il font principale (`\setmainfont{X}`, oppure Computer
  Modern senza fontspec) non è della famiglia del layout, `changes` riporta
  `"font not changed: the document uses X, the layout asks for <family>"`.

- [ ] **Step 1: test che falliscono.**
  - `test_format_tex_copies_project_and_sets_layout`: progetto con
    `\usepackage[margin=2cm]{geometry}`, setspace, `capitoli/`, `immagini/a.png`, `.aux` e
    `main.pdf`.
    - La copia ha i file meno gli artefatti.
    - Il blocco sta prima di `\begin{document}`, senza `\usepackage` doppi.
    - L'originale ha lo stesso hash.
  - `test_format_tex_adds_packages_when_missing`.
  - `test_format_tex_twice_keeps_one_block`: formattare la copia in una terza cartella.
  - `test_format_tex_without_layout_is_plain_copy`.
  - `test_format_tex_refuses_output_inside_project` (exit 2).
  - `test_format_tex_brings_report_within_limits` (`needs_xelatex`):
    `write_tex_report` → `compute_layout(Unibo, "Times New Roman")` → format → measure.
    `chars_per_line` e `lines_per_page` OK.
- [ ] **Step 2: verificare che falliscano**: `python -m pytest tests/test_format.py -q`.
- [ ] **Step 3: implementare.**
- [ ] **Step 4: verificare**: `python -m pytest -q`, tutto PASS.
- [ ] **Step 5: banco di prova reale.** `hmw layout --rules <unibo> --font "Times New
  Roman"`, poi `format` sulla bozza compilata, poi `measure` sulla copia.
  - `chars_per_line` e `lines_per_page` OK.
  - Registrare il numero di pagine: atteso oltre 30, ~40. È il dato da cui parte la
    proposta di rientro (Task 12).
- [ ] **Step 6: commit**: `feat: format LaTeX projects into a copy with the computed layout`.

---

### Task 7: Figure: grafici e schemi — **Modello:** medio

**Files:**
- Create: `scripts/helpmewrite/figure.py`
- Modify: `scripts/helpmewrite/cli.py` (`chart` e `diagram`, con pacchetto `matplotlib`;
  `PACKAGES["matplotlib"] = "matplotlib"`), `scripts/helpmewrite/doctor.py`,
  `requirements.txt` (`matplotlib>=3.7`), `README.md` (requisiti)
- Test: `tests/test_figure.py`, `tests/test_doctor.py`

**Interfaces:**
- Produces:
  - `load_table(path: Path) -> list[dict[str, str]]`;
  - `to_number(text: str) -> float`;
  - `json_value(path: Path, key: str) -> float`;
  - `render_chart(spec: dict, base: Path, out: Path) -> dict`, che restituisce la
    provenienza `{"values": [{"series", "x", "value", "file", "where"}]}`;
  - `diagram_ranks(spec: dict) -> dict[str, int]`;
  - `render_diagram(spec: dict, out: Path) -> None`;
  - `FigureError`.
- CLI:
  - `hmw chart <spec.json> -o <out.png|.pdf|.svg>`: scrive anche
    `<out>.fonte.json` con la provenienza;
  - `hmw diagram <spec.json> -o <out>`;
  - un output già esistente è rifiutato (R2);
  - i percorsi dei dati sono relativi alla cartella della spec.

**Specifica del grafico** (JSON):
- **Campi comuni:**
  - `type`: `bar`, `barh`, `line` o `scatter`;
  - `title`, `xlabel`, `ylabel` e `ylim`, facoltativi;
  - `annotate: bool`, che scrive i valori sulle barre con 2 decimali;
  - `language`, che con `it` usa la virgola decimale nelle etichette.
- **Fonte dei dati**, esattamente una delle due:
  - `"csv": {"file", "x": colonna, "y": [colonne], "labels": {colonna: etichetta}}`;
  - `"values": [{"label", "series", "file", "key"}]`, con chiavi puntate e indici di
    lista (`test.accuracy`, `per_class.0.f1`).
- **Lettura del CSV:**
  - BOM tolto (`utf-8-sig`);
  - separatore riconosciuto tra `,`, `;` e tabulazione;
  - `to_number`: `0,808` → 0.808, `1.234,5` → 1234.5, `0.808` → 0.808.

**Schema** (`diagram`):
`{"direction": "LR"|"TB", "nodes": [{"id", "label"}], "edges": [{"from", "to", "label"?}]}`.
- Ranghi per cammino più lungo dalle sorgenti. Un ciclo → `FigureError` che nomina i
  nodi del ciclo.
- Riquadri arrotondati (`FancyBboxPatch`), etichette a capo a 18 caratteri, frecce
  `-|>`.
- Backend `Agg`.

- [ ] **Step 1: test che falliscono**

```python
def test_chart_italian_csv(tmp_path):
    (tmp_path / "c.csv").write_bytes("\ufeffexperiment;acc\n01_raw;0,808\n03_eta;0,88\n".encode("utf-8"))
    spec = {"type": "bar", "csv": {"file": "c.csv", "x": "experiment", "y": ["acc"]}}
    prov = render_chart(spec, tmp_path, tmp_path / "g.png")
    assert [v["value"] for v in prov["values"]] == [0.808, 0.88]
    assert prov["values"][0]["file"] == "c.csv" and prov["values"][0]["where"] == "acc, row 1"
    assert (tmp_path / "g.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

def test_chart_values_from_json_keys(tmp_path):  # {"test": {"accuracy": 0.82}, "per_class": [{"f1": 0.6}]}
def test_chart_missing_key_names_file_and_key(tmp_path):  # exit 2, stderr has file name and key
def test_chart_refuses_existing_output(tmp_path):          # exit 2 with next free name
def test_diagram_ranks_and_cycle_error():
    assert diagram_ranks({"nodes": N("a", "b", "c"), "edges": E("ab", "bc", "ac")}) == {"a": 0, "b": 1, "c": 2}
    with pytest.raises(FigureError, match="a.*b"): diagram_ranks({"nodes": N("a", "b"), "edges": E("ab", "ba")})
def test_diagram_renders_png(tmp_path):
def test_doctor_reports_matplotlib(monkeypatch):           # missing matplotlib is listed with its install hint
```

- [ ] **Step 2: verificare che falliscano**: `python -m pytest tests/test_figure.py -q`.
- [ ] **Step 3: implementare.**
- [ ] **Step 4: verificare**: `python -m pytest -q`, tutto PASS.
- [ ] **Step 5: banco di prova reale.** Grafico a barre da
  `ml_physics_rf_v2/experiment_comparison.csv` estratto (Task 5), con colonne
  `holdout_accuracy` e `holdout_macro_f1`. I valori 0.808, 0.82 e 0.88 sono nella
  provenienza.
- [ ] **Step 6: commit**: `feat: charts from data files with provenance, and block diagrams`.

---

### Task 8: Frontespizio Word dal modello — **Modello:** medio

**Files:**
- Create: `scripts/helpmewrite/titlepage.py`
- Modify: `scripts/helpmewrite/cli.py` (`titlepage`, con `lxml` e `docx`; `-o` è il
  documento)
- Test: `tests/test_titlepage.py`

**Interfaces:**
- Produces: `fill_title_page(template: Path, replacements: list[tuple[str, str]], out:
  Path, start_at: str | None = None) -> dict`, che restituisce
  `{"replaced": {find: count}, "not_found": [find], "removed_elements": int}`.
- CLI: `hmw titlepage <modello.docx> --values valori.json -o <out.docx>`, con
  `valori.json = {"start_at": "...", "replace": [{"find": "...", "with": "..."}]}`.
  - Exit 1 se qualche `find` non è trovato (il file è comunque scritto); exit 2 per gli
    errori.

**Regole:**
- **`start_at`:** si tolgono tutti gli elementi del corpo prima dell'elemento di primo
  livello che contiene il testo, anche dentro una sua casella di testo.
  - Si tiene l'ultimo `w:sectPr` del corpo.
  - Si toglie un'interruzione di pagina all'inizio dell'elemento trovato
    (`w:br w:type="page"` o `pageBreakBefore`).
- **Sostituzione:**
  - su ogni paragrafo, nel corpo e nelle caselle di testo, sia in `mc:Choice` sia in
    `mc:Fallback`, `w:txbxContent` compreso;
  - corrispondenza sul testo concatenato dei run; se fallisce, una seconda prova con gli
    spazi compressi;
  - il nuovo testo va nel primo run toccato, con la sua formattazione, e il testo
    trovato si toglie dai run successivi;
  - si sostituiscono tutte le occorrenze.

- [ ] **Step 1: test che falliscono**, sul facsimile reale
  `docs/riferimenti/Facsimile_relazione_di_fine_tirocinio.docx`:

```python
VALUES = {"start_at": "ALMA MATER STUDIORUM", "replace": [
    {"find": "Anno Accademico 20…./20….", "with": "Anno Accademico 2025/2026"},
    {"find": "indicare nome e cognome  (matricola nr.              )", "with": "Mario Rossi (matricola nr. 0000123456)"},
    {"find": "indicare la denominazione della Struttura Ospitante", "with": "Acme S.r.l."},
    {"find": "inserire titolo o argomento delle attività di tirocinio", "with": "Diagnostica FEM con ML"}]}

def test_titlepage_fills_facsimile(tmp_path):     # write_json: test helper, dumps VALUES to a file
    out = tmp_path / "f.docx"
    assert main(["titlepage", str(FACSIMILE), "--values", str(write_json(tmp_path, VALUES)), "-o", str(out)]) == 0
    texts = [p["text"] for p in extract(out)["paragraphs"] if p["text"].strip()]
    assert texts[0].startswith("ALMA MATER") and not any(t.startswith("Finalità") for t in texts)
    for v in ("Anno Accademico 2025/2026", "Mario Rossi", "Acme S.r.l.", "Diagnostica FEM con ML"):
        assert sum(v in t for t in texts) == 1
    xml = zipfile.ZipFile(out).read("word/document.xml").decode()
    assert "indicare nome e cognome" not in xml and xml.count("Mario Rossi") == ORIGINAL.count("indicare nome e cognome")

def test_titlepage_reports_not_found(tmp_path):   # one bogus find -> exit 1, JSON not_found == [it]
@needs_soffice
def test_titlepage_renders_one_page(tmp_path):    # render -> 1 page; text has "ALMA MATER" and "Mario Rossi"
```

  `ORIGINAL` è il `document.xml` del facsimile.

- [ ] **Step 2: verificare che falliscano**: `python -m pytest tests/test_titlepage.py -q`.
- [ ] **Step 3: implementare.**
- [ ] **Step 4: verificare**: `python -m pytest -q`, tutto PASS.
- [ ] **Step 5: commit**: `feat: fill a .docx title page template (text boxes included)`.

---

### Task 9: Assemblaggio Word dai sorgenti dei capitoli — **Modello:** capace

**Files:**
- Create: `scripts/helpmewrite/assemble.py`,
  `skills/scrittura-capitolo/formato-capitoli.md` (il formato sotto, in inglese, con un
  esempio)
- Modify: `scripts/helpmewrite/cli.py` (`assemble`, con `lxml`, `docx`, `yaml` e
  `bibtexparser`; `-o` è il documento), `scripts/helpmewrite/extract.py` (stile "TOC
  Heading" o "Titolo sommario" → `heading_level` 1), `scripts/helpmewrite/bib.py` (alias
  pubblico `bibtex_entries = _bibtex_entries`)
- Test: `tests/test_assemble.py`, `tests/test_extract.py`

**Formato dei capitoli** (Markdown ridotto, un file per capitolo):
- **Blocchi:**
  - `#`, `##`, `###`: titoli di livello 1–3;
  - paragrafi separati da una riga vuota;
  - elenchi `- ` e `1. `.
- **Testo in linea:** `**grassetto**`, `*corsivo*` e `` `codice` ``.
- **Figura:** `![Didascalia](percorso.png){#fig:etichetta width=12cm}`, da sola su una
  riga; `width` è facoltativo e di default vale il minimo tra la larghezza naturale e
  quella del testo.
- **Tabella:** tabella a barre preceduta da `Tabella: Didascalia {#tab:etichetta}`
  (`Table:` in inglese).
- **Riferimenti:** `@fig:x` e `@tab:x` diventano "Figura N" e "Tabella N" ("Figure",
  "Table" con `language: en`).
- **Citazioni:** `[@chiave]` e `[@a; @b]` diventano numeri `[1]` e `[1, 2]`, in ordine di
  prima citazione.
- **Segnaposto:** `[DA VERIFICARE: …]` resta testo, evidenziato in giallo
  (`w:highlight w:val="yellow"`).
- **Formule:** niente sintassi propria; si scrivono come testo Unicode. Limite noto, da
  dichiarare in `docs/uso.md`.

**Manifest** (YAML; percorsi relativi alla sua cartella):
- `title_page`: `.docx`, facoltativo;
- `layout`: JSON di `hmw layout`, obbligatorio;
- `chapters`: lista, obbligatoria;
- `bibliography`: `.bib`, facoltativo;
- `language`: `it` di default;
- `toc`: `true` di default;
- `toc_title`: "Indice" / "Contents";
- `bibliography_title`: "Bibliografia" / "References".

**Interfaces:**
- Produces:
  - `parse_chapter(text: str) -> list[Block]`, con dataclass `Heading`, `Paragraph`,
    `ListBlock`, `Figure` e `Table`;
  - `validate_manifest(path: Path) -> list[str]`, che restituisce i problemi;
  - `assemble(manifest: Path, out: Path) -> dict`, cioè
    `{"chapters", "figures", "tables", "citations", "warnings"}`.
- CLI: `hmw assemble <manifest.yaml> -o <out.docx>`. Exit 2 se `validate_manifest`
  restituisce problemi, che vengono elencati tutti, e nessun file viene scritto.
- Consumes:
  - `layout.load_layout` e `layout.apply_layout` (Parte 1, frontespizio protetto, R3/R4);
  - `render.render_pdf`, `measure.measure_pdf` e `measure.section_spans`;
  - `bib.bibtex_entries`.

**Costruzione** (l'ordine conta: l'impaginazione si fissa prima dei numeri dell'indice):
1. **Validazione:**
   - file e immagini esistenti;
   - etichette uniche e tutte definite;
   - chiavi citate presenti nel `.bib`;
   - chiavi del manifest note.
2. **Base:** una copia del frontespizio, se c'è, altrimenti un documento vuoto. Dopo il
   frontespizio un'interruzione di sezione (pagina successiva).
   - Il frontespizio resta senza numero; le pagine seguenti sono numerate dal piè di
     pagina di `apply_layout`.
3. **Indice:** paragrafo stile "TOC Heading" (creato se manca, grassetto, senza livello
   di struttura), poi un campo `TOC \o "1-3" \h \z \u` con una voce per titolo
   (stile `TOC 1`–`TOC 3`, tabulazione destra con puntini) e numero provvisorio `00`.
   `w:updateFields` vale true in `settings.xml`.
4. **Contenuto:**
   - capitoli, con titoli in stile `Heading 1`–`3`;
   - figure centrate con `keep_with_next`, poi didascalia `Caption`
     "Figura N: Didascalia" con campo `SEQ Figura` e risultato memorizzato N;
   - tabelle (stile `Table Grid`) con la didascalia sopra;
   - alla fine "Bibliografia" (`Heading 1`), con voci
     `[n] Autori. Titolo. Sede, Anno. DOI: x.` (le parti mancanti si omettono).
5. **Impaginazione:** `apply_layout`, poi il salvataggio.
6. **Numeri dell'indice:**
   - `render_pdf` e pagine dei titoli con `section_spans`;
   - numero stampato = pagina fisica − pagine prima della prima pagina numerata + 1;
   - i `00` si sostituiscono senza cambiare il numero delle voci;
   - senza soffice: avviso `"table of contents without page numbers: update it in Word
     (F9)"` ed exit 0.

- [ ] **Step 1: test che falliscono**

```python
def test_parse_chapter_blocks():
    blocks = parse_chapter("# Attività\n\nTesto *a* [@k1].\n\n![Schema](s.png){#fig:s width=10cm}\n\n- uno\n- due\n")
    assert [type(b).__name__ for b in blocks] == ["Heading", "Paragraph", "Figure", "ListBlock"]
    assert blocks[2].label == "fig:s" and blocks[2].width_cm == 10.0

def test_assemble_minimal_document(tmp_path):   # 2 chapters, figure, table, @fig/@tab refs, [@k1], list, [DA VERIFICARE: x]
    stats = assemble(manifest, out)
    paras = extract(out)["paragraphs"]
    assert [(p["text"], p["heading_level"]) for p in paras if p["heading_level"]][:3] == [
        ("Indice", 1), ("Introduzione", 1), ("Contesto", 2)]
    texts = [p["text"] for p in paras]
    assert "Figura 1: Schema" in texts and "Tabella 1: Risultati" in texts
    assert any("come mostra la Figura 1" in t for t in texts) and any("[1]" in t for t in texts)
    assert any(t.startswith("[1] Rossi") for t in texts)
    assert 'w:val="yellow"' in zipfile.ZipFile(out).read("word/document.xml").decode()

def test_assemble_reports_missing_figure_and_label(tmp_path):
    # chapter cites ![x](manca.png) and @fig:assente and [@nessuna]
    assert main(["assemble", str(manifest), "-o", str(out)]) == 2 and not out.exists()
    # stderr names manca.png, fig:assente and nessuna

def test_extract_toc_heading_is_level_1(tmp_path):   # in tests/test_extract.py

@needs_soffice
def test_assemble_with_facsimile_title_page(tmp_path):   # titlepage (Task 8) + 4 chapters ~12 pages
    m = measure(out, load_rules(UNIBO), tmp_path / "w")
    checks = {c.rule: c for c in m.checks}
    for rule in ("pages", "font_family", "font_size", "lines_per_page", "chars_per_line",
                 "page_numbers", "section:indice:present", "section:introduzione:present",
                 "section:conclusione:present"):
        assert checks[rule].ok, checks[rule].detail
    assert "ALMA MATER" in m.pages[0].text and not m.pages[0].has_page_number
    toc = m.pages[1].text            # the TOC entry of Introduzione carries its printed page number
```

  Asserire che la voce "Introduzione" dell'indice termina con il numero stampato della
  sua pagina.

- [ ] **Step 2: verificare che falliscano**: `python -m pytest tests/test_assemble.py -q`.
- [ ] **Step 3: implementare** `assemble.py`, le modifiche a `extract.py` e a `bib.py` e
  `formato-capitoli.md`.
- [ ] **Step 4: verificare**: `python -m pytest -q`, tutto PASS.
- [ ] **Step 5: commit**: `feat: assemble a .docx from chapter sources (TOC, captions, bibliography)`.

---

### Task 10: Progetto LaTeX nuovo — **Modello:** medio

**Files:**
- Create: `scripts/helpmewrite/latexproj.py`, `modelli/latex/frontespizio-unibo.tex`
- Modify: `scripts/helpmewrite/cli.py` (`latex-init`, senza pacchetti; `-o` non c'è: la
  cartella è un argomento)
- Test: `tests/test_latexproj.py`

**Interfaces:**
- Produces:
  - `tex_escape(text: str) -> str`, che protegge `& % $ # _ { } ~ ^ \`;
  - `new_latex_project(out_dir: Path, layout: Layout, chapters: list[dict], language:
    str = "it", title_page: str = "unibo", values: dict[str, str] | None = None,
    bibliography: bool = False) -> list[Path]`.
- CLI: `hmw latex-init <out_dir> --layout L --chapters capitoli.json [--values v.json]
  [--title-page unibo|generico] [--language it|en] [--bibliography]`. `capitoli.json` ha
  il formato di `state outline`. Una cartella non vuota → exit 2; chiavi di `values`
  sconosciute → exit 2.
- Consumes: `layout.load_layout`, `fonts.DOCX_FONT`.

**Progetto generato:**
- **`main.tex`:**
  - prima riga `% !TeX program = xelatex`;
  - `report` con la dimensione del layout (10, 11 o 12 pt; altrimenti exit 2), a4 e
    oneside;
  - `babel` italian o english;
  - fontspec con
    `\IfFontExistsTF{<DOCX_FONT>}{\setmainfont{<DOCX_FONT>}}{\setmainfont{<equivalente>}}`;
    equivalenti TeX Gyre Termes, Heros e Cursor;
  - geometry dai margini e `\setstretch` come nel Task 6;
  - `\parindent 1cm`, `\parskip 0pt`, `indentfirst`;
  - `graphicx` con `\graphicspath{{immagini/}}`, `caption`, `booktabs`;
  - `fancyhdr` con piè di pagina centrato `\thepage`, anche nello stile plain;
  - `titlesec` hang `\Large\bfseries` con 1.5 righe dopo;
  - `hyperref` hidelinks;
  - blocco "DATI DEL FRONTESPIZIO" con un `\newcommand` per valore;
  - corpo: `\input{frontespizio}`,
    `\pagenumbering{roman}\tableofcontents\clearpage\pagenumbering{arabic}`, un `\include`
    per capitolo e, se richiesta, `\bibliographystyle{unsrt}\bibliography{bibliografia}`.
- **`frontespizio.tex`:** dal modello. `unibo` riproduce riga per riga la pagina 2 del
  facsimile:
  - "ALMA MATER STUDIORUM - UNIVERSITÀ DI BOLOGNA", "INGEGNERIA (CAMPUS BOLOGNA)",
    "Anno Accademico …", un filetto, "RELAZIONE DI FINE TIROCINIO CURRICULARE";
  - "svolto dallo studente:", "<studente> (matricola nr. <matricola>)";
  - "iscritto al Corso di Studio in", "<corso> (codice <codice_corso>)";
  - "presso:", "<struttura>", "sul seguente argomento:", "<argomento>";
  - "Studente:" con riga e "(firma)";
  - "Referente Struttura Ospitante:", "<referente>", con riga e "(firma per approvazione
    della relazione finale)".
  - Chiavi: `anno_accademico`, `studente`, `matricola`, `corso`, `codice_corso`,
    `struttura`, `argomento`, `referente`.
  - `generico` ha le chiavi `titolo`, `autore`, `istituzione`, `data`.
  - Un valore mancante diventa `[DA VERIFICARE: <chiave>]`.
- **Capitoli:** `capitoli/NN-<id>.tex` con `\chapter{<titolo>}\label{cap:<id>}` e una riga
  `% help-me-write: testo da scrivere`.
- **Altri file:** `immagini/` vuota, `bibliografia.bib` vuoto se richiesto, `.latexmkrc`
  con `$pdf_mode = 5;`.

- [ ] **Step 1: test che falliscono.**
  - `test_latex_init_files_and_escaping`: un titolo "R&D al 100%" diventa `R\&D al
    100\%`; i file attesi esistono; una cartella non vuota dà exit 2.
  - `test_latex_init_missing_value_is_placeholder`.
  - `test_latex_project_compiles_and_measures` (`needs_xelatex`):
    - progetto Unibo con 3 capitoli riempiti con i paragrafi di `testo_italiano.txt`
      fino a 11 pagine;
    - `measure` con le regole Unibo: `pages`, `font_family`, `font_size`,
      `lines_per_page`, `chars_per_line`, `page_numbers` e `section:indice:present` OK;
    - pagina 1 con "ALMA MATER" e senza numero.
- [ ] **Step 2: verificare che falliscano**: `python -m pytest tests/test_latexproj.py -q`.
- [ ] **Step 3: implementare.**
- [ ] **Step 4: verificare**: `python -m pytest -q`, tutto PASS.
- [ ] **Step 5: commit**: `feat: new LaTeX project with a faithful Unibo title page`.

---

### Task 11: Skill di ingresso e di lettura del materiale — **Modello:** medio

**Files:**
- Create: `skills/help-me-write/SKILL.md`, `skills/analisi-materiale/SKILL.md`,
  `skills/analisi-materiale/modello-materiale.md`
- Modify: `tests/test_skills_static.py`
- Test: `tests/test_skills_static.py`

Le convenzioni di intestazione sono quelle di `skills/linee-guida/SKILL.md`: `<work>`,
`hmw`, lingua, "ask the user", percorsi tra virgolette.

**`help-me-write`.** La `description` copre: scrivere, completare o riprendere un
documento formale da una cartella di lavoro ("help me write", "aiutami a scrivere",
"scrivi la relazione", "completa la bozza", "riprendi la relazione", "continua").
Passi:
1. `hmw doctor`: serve LibreOffice per Word e latexmk/XeLaTeX per LaTeX; matplotlib
   solo per i grafici.
2. **Stato esistente:** `hmw state show "<work>" --json`.
   - Riassumere all'utente modalità, formato, capitoli con stato e domande aperte, poi
     riprendere da `next`.
   - Prima di ogni domanda, cercare la risposta in `progetto.md`, in `materiale.md` e
     nelle note d'intervista; **mai rifare una domanda già fatta** (caso 3).
   - `hmw state modified "<work>"`: un output modificato a mano non si rigenera mai (§7.3)
     e le modifiche successive passano per `hmw track` (revisioni) su una copia.
3. **Nessuno stato:** `hmw detect "<work>" --json`, poi proposta della modalità da
   confermare:
   - nessuna bozza → `da-zero`;
   - bozza con `empty_parts`, sezioni obbligatorie mancanti o lunghezza molto sotto il
     minimo → `bozza-parziale`;
   - bozza completa → `solo-revisione`, che passa alla skill `revisione`.
4. **Formato:**
   - `da-zero`: chiedere **sempre** "LaTeX o Word?" (decisione dell'utente);
   - altrimenti si ricava dalla bozza e lo si dice.
5. **Cartella di output:** proporla e farla confermare.
   - `da-zero`: `<work>/<nome-documento>-help-me-write/`;
   - bozza LaTeX: la copia di lavoro `<cartella del progetto>-help-me-write/`, accanto al
     progetto.

   Poi `hmw state init`.
6. **Fasi:** tabella `next.phase` → skill da seguire:
   - `materiale` → analisi-materiale;
   - `linee-guida` → linee-guida (poi `state set document_type=… profile=…`);
   - `formato` → passo 4;
   - `struttura`, `frontespizio` → struttura;
   - `intervista` → intervista-capitolo;
   - `scrittura`, `approvazione` → scrittura-capitolo;
   - `revisione` → revisione, sul documento di output, poi `measure`;
   - `fine` → riepilogo con percorsi.
   - Dopo ogni fase si aggiorna lo stato con i comandi di `state` e si aggiungono
     decisioni e domande aperte al corpo di `progetto.md`.
7. **Regole fisse:**
   - nessuna invenzione e segnaposto `[DA VERIFICARE: …]`;
   - un capitolo alla volta;
   - approvazione di indice, frontespizio e ogni capitolo prima di proseguire;
   - originali mai toccati;
   - online solo titoli, autori e DOI.

**`analisi-materiale`:**
1. `hmw material "<work>" --extract "<work>/.help-me-write/materiale/estratti" -o
   "<work>/.help-me-write/materiale/inventario.json"`.
2. **Leggere prima le note dell'autore** (README, LEGGIMI, NOTE, diari): sono vincoli da
   rispettare, da copiare nella sezione "Note dell'autore".
3. **Leggere in modo selettivo:**
   - metriche CSV/JSON;
   - degli script, le intestazioni, i docstring, gli argomenti e le costanti di
     configurazione;
   - dei notebook, `hmw notebook`.
   - Mai eseguire, importare o deserializzare nulla; i modelli si elencano soltanto.
   - Nelle cartelle grandi, un campione per sottocartella (README, punti d'ingresso, 2–3
     file), dichiarando cosa non è stato letto.
4. **Cronologia:** dalle date di git, degli archivi, dei diari e dei nomi dei file. Se
   `dates.reliable` è falso o restano buchi, una domanda raggruppata all'utente sulla
   linea del tempo; le risposte hanno fonte "utente".
5. **Scrivere `<work>/.help-me-write/materiale.md`** dal modello, con le sezioni:
   - Sintesi del lavoro;
   - Mappa del materiale (percorso | cosa contiene | per quale parte del documento);
   - Cronologia (data | evento | fonte);
   - **Dati e numeri** (valore | significato | file e posizione, o "risposta
     dell'utente, <data>"): l'unico serbatoio di numeri per la scrittura;
   - Note dell'autore;
   - Non letto;
   - Lacune e domande.

**Test statici nuovi:**
- `test_expected_skills_and_profiles_exist` elenca le nuove skill (quelle del Task 12
  si aggiungono lì);
- `test_skills_use_known_commands`: ogni `hmw <comando>` citato in una SKILL.md o in un
  prompt esiste in `cli._COMMANDS`;
- `test_entry_skill_rules`: la SKILL.md di ingresso contiene "LaTeX or Word", "never ask
  again", `state modified` e `[DA VERIFICARE`.

- [ ] **Step 1: scrivere i test statici**: `python -m pytest tests/test_skills_static.py -q`
  → FAIL (skill mancanti).
- [ ] **Step 2: scrivere le due skill e il modello.**
- [ ] **Step 3: verificare**: `python -m pytest -q`, tutto PASS.
- [ ] **Step 4: commit**: `feat: entry skill (modes, state, resume) and material analysis skill`.

---

### Task 12: Skill di struttura, intervista, scrittura e figure — **Modello:** capace

**Files:**
- Create: `skills/struttura/SKILL.md`, `skills/intervista-capitolo/SKILL.md`,
  `skills/scrittura-capitolo/SKILL.md`, `skills/figure/SKILL.md`
- Modify: `profili/relazione-tirocinio.md` (sezione `## Writing budget`: introduzione e
  conclusione 1–2 pagine, il resto ai capitoli del corpo in proporzione al materiale),
  `tests/test_skills_static.py`
- Test: `tests/test_skills_static.py`

**`struttura` (fase 5 e confronto della bozza):**
- **`da-zero`:**
  - indice proposto dalla struttura tipica del profilo e da `materiale.md`: capitoli del
    corpo in ordine cronologico o di sviluppo, ciascuno con il materiale che lo sostiene;
  - approvazione, poi `hmw state outline`;
  - frontespizio: se le linee guida hanno `title_page_template`, chiedere in una domanda
    raggruppata ogni valore che il modello richiede, senza mai dedurre nome, matricola o
    codici;
    - Word: `hmw titlepage` e testo estratto mostrato per l'approvazione;
    - LaTeX: `hmw latex-init` con `--values`, compilato e mostrato;
  - poi `state set title_page_approved=true`;
  - Word: cartella `.help-me-write/capitoli/` e `manifest.yaml` (formato del Task 9).
- **`bozza-parziale`:**
  1. **Misura e lettura:** `hmw measure` e `extract` della bozza, poi lettura dei
     capitoli.
  2. **Tabella di confronto** regola → stato nella bozza → azione (tenere, correggere,
     scrivere, tagliare).
  3. **Piano di riorganizzazione:** i capitoli esistenti entrano nell'indice con `source`
     e stato `scritto`; le parti vuote sono `da-fare`.
  4. **Copia di lavoro:** `hmw format "<main.tex>" -o "<copia>" [--layout …]`, con il
     layout solo se l'utente accetta la correzione dell'impaginazione; poi
     `hmw state record` della copia.
  5. **Frontespizio:** i valori `\newcommand` della copia, chiesti all'utente.
  6. **Rientro nelle pagine:**
     - `hmw measure` sulla copia; con pagine oltre il massimo, righe da togliere =
       (pagine − massimo) × righe per pagina del layout;
     - una tabella di tagli proposti: capitolo | cosa | righe risparmiate circa |
       perché (ripetizioni, spiegazioni generali di strumenti o teoria da sostituire con
       una citazione, elenchi lunghi, figure che duplicano tabelle, parti spostabili negli
       allegati se l'utente conferma che non contano);
     - **mai** ridurre corpo, margini o interlinea oltre i limiti, **mai** testo nuovo che
       aggiunge fatti; condensare usa solo frasi e fatti già presenti;
     - se le linee guida qualificano il limite come approssimato ("circa"), dirlo e far
       scegliere il bersaglio all'utente;
     - dopo l'approvazione, i tagli vanno in un EditSet (`edits.py`) applicato con
       `hmw track` in una nuova copia, più `hmw texdiff` per il PDF delle differenze.
  7. **Seguito:** intervista e scrittura per le parti `da-fare` (per esempio le
     conclusioni), poi la revisione.
  8. **Bozza Word:** confronto, copia formattata (`hmw format` con il layout) e tagli
     come revisioni tracciate (`hmw track`) funzionano come sopra. I capitoli nuovi o
     mancanti si scrivono come sorgenti e si assemblano con `hmw assemble` in
     `<nome>-capitoli-nuovi.docx`, con lo stesso layout, da incollare nella bozza.
     Dirlo all'utente: `track` sostituisce testo dentro i paragrafi, non inserisce
     capitoli.

**`intervista-capitolo`:**
- un capitolo alla volta;
- domande specifiche costruite da `materiale.md`, che citano file, date e numeri: punti
  salienti, cosa ha fatto personalmente l'utente rispetto al gruppo o al tutor,
  difficoltà, risultati con i numeri, immagini (esistenti con percorso, da generare e da
  quali dati, non necessarie), cosa non si può pubblicare;
- al massimo 8 domande per giro, raggruppate; prima di chiedere, controllare che la
  risposta non sia già in `.help-me-write/`;
- risposte in `.help-me-write/capitoli/<id>-intervista.md`, con data e parole
  dell'utente;
- poi `hmw state chapter <id> --status intervista-fatta --notes …`;
- introduzione e conclusione si intervistano dopo il corpo: obiettivi raggiunti, cosa si
  è imparato, cosa resta aperto.

**`scrittura-capitolo`:**
- **Ingressi:** note d'intervista, `materiale.md`, tono e checklist del profilo, budget di
  pagine dal `## Writing budget` del profilo, linee guida.
- **Uscita:**
  - LaTeX: il file del capitolo nel progetto o nella copia di lavoro;
  - Word: `.help-me-write/capitoli/<id>.md` secondo `formato-capitoli.md`.
- **Regole:**
  - ogni numero e ogni fatto ha una fonte (file di `materiale.md` o risposta registrata),
    elencata in una sezione "Fonti del capitolo" del file d'intervista;
  - senza fonte → `[DA VERIFICARE: …]`;
  - prima persona e ordine cronologico se il profilo chiede un diario;
  - contributo personale esplicito;
  - si citano solo fonti del `.bib` o della cartella dell'utente;
  - le note dell'autore sono vincoli;
  - introduzione e conclusioni riassumono i capitoli e non portano fatti nuovi.
- **Prosa da evitare** (elenco nella skill): formule vuote ("riveste un ruolo
  fondamentale", "nel panorama attuale", "in conclusione possiamo affermare"), terne
  retoriche, intensificatori, frasi che valgono per qualunque tirocinio.
- **Approvazione:**
  - mostrare il capitolo (LaTeX: compilarlo con `hmw measure` sulla copia e indicare le
    pagine);
  - applicare le modifiche chieste;
  - all'approvazione, `state chapter --status approvato` e `state record`.
- **Word:** dopo ogni approvazione, `hmw assemble` del documento in una nuova versione,
  ma solo se `state modified` non segnala modifiche a mano; altrimenti correzioni con
  `hmw track`.

**`figure`:**
- grafici solo da file di dati con `hmw chart`; il file `.fonte.json` resta accanto alla
  figura, e i numeri di didascalia e testo devono coincidere con la provenienza;
- schemi con `hmw diagram` dalla descrizione dell'utente;
- immagini dell'utente copiate in `immagini/` (LaTeX) o citate per percorso (Word);
- ogni figura ha numero, didascalia e riferimento nel testo (`\ref` o `@fig:`);
- niente immagini fotografiche o generate con l'AI (spec §3.1).

**Test statici:** `test_writing_skills_rules`.
- `scrittura-capitolo` contiene `[DA VERIFICARE`, "Fonti del capitolo" e l'elenco della
  prosa da evitare.
- `struttura` contiene "never reduce" e `texdiff`.
- `intervista-capitolo` contiene "at most 8 questions".
- `figure` contiene `.fonte.json`.
- Le skill citano solo comandi esistenti: test del Task 11.

- [ ] **Step 1: test statici** → FAIL.
- [ ] **Step 2: scrivere le quattro skill e la sezione del profilo.**
- [ ] **Step 3: verificare**: `python -m pytest -q`, tutto PASS.
- [ ] **Step 4: commit**: `feat: structure, interview, writing and figure skills`.

---

### Task 13: Accettazione deterministica (casi 1 e 3) e scenari futuri — **Modello:** medio

**Files:**
- Modify: `tests/fixtures/builders.py` (`build_example_work(folder) -> dict`)
- Create: `tests/test_acceptance.py`, `tests/scenari/da-zero-word.md`,
  `tests/scenari/ripresa.md`

**`build_example_work`** crea una cartella d'esempio di tirocinio fittizio:
- `progetto/` con un piccolo pacchetto Python e un repository git con 3 commit datati
  2026-09-15, 2026-10-10 e 2026-11-05;
- `dati/metriche.csv` all'italiana (BOM e `;`);
- `diario.md` con date;
- una copia del facsimile;
- quattro sorgenti di capitolo già scritti, in `attesi/capitoli/*.md`, per ~12 pagine,
  con una figura dal grafico.

Restituisce i percorsi.

- [ ] **Step 1: test** (soffice; i passi LaTeX con `needs_xelatex`):
  - **`test_case1_word_pipeline`:**
    1. `detect` non trova bozze; `state init --mode da-zero --format word`;
    2. `material`: git con 3 commit, date affidabili;
    3. `chart` dal CSV e `titlepage` dal facsimile;
    4. `assemble` con i capitoli attesi;
    5. `measure` con le regole Unibo: **tutti** i controlli OK;
    6. `state record`; una modifica a mano con python-docx (un paragrafo aggiunto) →
       `state modified` dice `modified`.
  - **`test_case1_latex_pipeline`:** `latex-init`, capitoli convertiti a mano nel test
    (stessi paragrafi), figura dal grafico, compilazione, `measure`: tutti i controlli OK.
  - **`test_case3_resume_after_two_chapters`:**
    - stato con 5 capitoli, 2 `approvato` e il terzo `intervista-fatta` con le note;
    - `state show --json` → `next == {"phase": "scrittura", "chapter": <terzo>}`;
    - nessun campo perso dopo `state set` e `state chapter` (confronto dell'intestazione
      prima e dopo).
- [ ] **Step 2: scenari da eseguire più avanti** (formato di
  `tests/scenari/revisione.md`; non si eseguono in questo piano, per la regola di una sola
  prova `claude -p`):
  - `da-zero-word.md`: cartella di `build_example_work`, risposte all'intervista in un
    file, controlli sul `.docx` e sullo stato;
  - `ripresa.md`: due sessioni `claude -p`; la seconda non deve rifare domande presenti
    nelle note.
- [ ] **Step 3: verificare**: `python -m pytest -q`, tutto PASS.
- [ ] **Step 4: commit**: `test: deterministic acceptance for cases 1 and 3, scenarios for later`.

---

### Task 14: Scenario reale (l'unica prova `claude -p`) e documentazione — **Modello:** medio

**Files:**
- Create: `tests/scenari/bozza-parziale.md`, `tests/scenari/check_bozza_parziale.py`
- Modify: `docs/uso.md`, `README.md`, `.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json` (versione `0.2.0`;
  `description` che dice anche "write")

**Scenario** (sul modello di `tests/scenari/revisione.md`):
- **`--setup <tmp>`:**
  - clona `madashi14/relazione_tirocinio` in `<tmp>/lavoro`, senza `.git` e senza
    `main.pdf` e artefatti, che restano come riferimento fuori dalla cartella;
  - scrive `<tmp>/lavoro/.help-me-write/linee-guida.yaml` (copia della fixture Unibo):
    la Parte 1 è già provata e così si risparmia la fase;
  - scrive `<tmp>/risposte.md` con:
    - linea del tempo: ottobre–novembre 2026, settimane indicative;
    - valori del frontespizio, fittizi e dichiarati tali: "Studente Prova", ecc.;
    - risposte per le conclusioni: obiettivi raggiunti, cosa ha imparato, limiti;
    - "approvo indice e copia di lavoro con impaginazione corretta";
  - prepara una copia isolata del plugin, senza `tests/` e `docs/`;
  - registra gli hash degli originali.
- **Prompt:** in italiano. Chiede di usare help-me-write sulla cartella, di leggere le
  risposte da `<tmp>/risposte.md` invece di attendere l'utente e di fermarsi dopo aver
  proposto i tagli per rientrare nelle 30 pagine (senza applicarli e senza revisione
  finale). Il comando è quello del §6 del documento di passaggio.
- **`--check <tmp>`**, con esito per punto:
  1. originali con gli hash invariati;
  2. `.help-me-write/progetto.md` valido, `mode: bozza-parziale`, `format: latex`;
  3. `materiale.md` cita i tre zip e `travi.ipynb`, con una sezione "Cronologia" e una
     "Note dell'autore" che riporta la distinzione batch/PyMAPDL del LEGGIMI;
  4. copia di lavoro con il blocco d'impaginazione; `measure` sulla copia dà
     `chars_per_line`, `lines_per_page` e `page_numbers` OK;
  5. `06_conclusioni.tex` della copia con almeno 1500 caratteri di testo; **ogni numero**
     (regex `\d+(?:[.,]\d+)?`) compare nei capitoli 1–5, in `materiale.md` o in
     `risposte.md`;
  6. i `\newcommand` del frontespizio con i valori di `risposte.md`;
  7. il capitolo 3 della copia contiene ancora "batch";
  8. una proposta di tagli (tabella con capitolo e righe) nel corpo di `progetto.md` o in
     `.help-me-write/revisioni/`, se le pagine della copia superano 30.

**Documentazione:**
- `docs/uso.md`:
  - le tre modalità e la ripresa;
  - Word o LaTeX;
  - figure;
  - cartella `.help-me-write/`;
  - limiti nuovi:
    - formule in Word come testo;
    - in una bozza Word parziale i capitoli nuovi arrivano in un documento a parte, da
      incollare;
    - scenari `da-zero-word` e `ripresa` non ancora eseguiti;
    - Codex ancora da verificare.
- `README.md`: cosa fa ora il plugin e requisiti con matplotlib.

- [ ] **Step 1: scrivere scenario e controllore**; `python
  tests/scenari/check_bozza_parziale.py --setup <tmp>` funziona (prova a secco).
- [ ] **Step 2: documentazione e versione**; `claude plugin validate .` passa.
- [ ] **Step 3: verificare**: `python -m pytest -q`, tutto PASS.
- [ ] **Step 4: commit**: `docs: part 2 usage, real-draft scenario, version 0.2.0`.
- [ ] **Step 5 (controllore, dopo la revisione del task):**
  - eseguire **una volta** lo scenario con `claude -p` e poi `--check`;
  - registrare esito e costo in fondo a `tests/scenari/bozza-parziale.md` ("Esecuzione
    1");
  - i difetti trovati vanno nell'unica ondata di correzioni dopo la revisione finale.
