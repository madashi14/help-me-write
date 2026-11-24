# help-me-write — Parte 1: fondamenta e modalità "solo revisione" — Piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** un plugin installabile in Claude Code e Codex che, dato un documento già scritto
(.docx, .tex o .pdf) e le sue linee guida, produce una copia con correzioni tracciate,
commenti bibliografici e un rapporto di revisione.

**Architecture:** skill condivise (`skills/*/SKILL.md`) con un manifest per piattaforma. Le
parti deterministiche sono in un pacchetto Python invocato da riga di comando
(`python scripts/hmw.py <comando>`, output JSON):
- estrazione del testo;
- calcolo e applicazione dell'impaginazione;
- misura sul PDF;
- revisioni Word e LaTeX;
- estrazione della bibliografia.

Le parti di giudizio le svolgono due revisori. Ciascuno è un file di prompt dentro la
propria skill, passato a un sub-agente generico (con esecuzione nella stessa sessione se
la piattaforma non ha sub-agenti).

**Tech Stack:**
- Python ≥ 3.10, con python-docx ≥ 1.2 (API commenti), lxml, pdfplumber, PyYAML,
  bibtexparser 1.4.x e pytest;
- LibreOffice (`soffice`), per impaginare i .docx;
- latexmk e latexdiff, solo per LaTeX.

**Spec:** `docs/superpowers/specs/2026-11-24-scriba-design.md`. Questo piano implementa:
- §2.1 modalità 3 (solo revisione);
- §4 fase 3 (linee guida);
- §5.3 (profili);
- §6 (revisione e revisore della bibliografia);
- §7.2 (script, eccetto frontespizio e assemblaggio Word);
- §9 casi 2, 5 e 6, più la procedura per il caso 4 (Codex), da eseguire fuori da
  questo ambiente.

Il flusso di scrittura (§4 fasi 1, 2, 4–7, modalità 1 e 2, §7.1 completo, §7.3, §7.4,
§9 casi 1 e 3) è la **Parte 2**, con un piano separato.

## Global Constraints

- **Nome e identificatori:**
  - nome del plugin: `help-me-write`;
  - cartella di stato nella cartella del lavoro: `.help-me-write/`;
  - autore delle revisioni e dei commenti Word: `help-me-write`, iniziali `HMW`.
- **Ambiente:**
  - Python ≥ 3.10;
  - dipendenze solo da `requirements.txt`: `python-docx>=1.2`, `lxml`, `pdfplumber`,
    `PyYAML`, `bibtexparser>=1.4,<2`;
  - test: `pytest`, in `requirements-dev.txt`.
- **Multipiattaforma (Windows/macOS/Linux):**
  - solo `pathlib`, mai `shell=True`;
  - nomi file con spazi e lettere accentate supportati.
- **Strumenti esterni:** LibreOffice, latexmk e latexdiff sono opzionali. Vengono
  rilevati da `doctor`; quando mancano, i comandi che li richiedono falliscono con un
  messaggio che spiega cosa installare, mai con un traceback.
- **Originali mai modificati:**
  - ogni comando scrive in un file o in una cartella nuovi;
  - se la destinazione coincide con la sorgente, il comando rifiuta (exit code 2).
- **Interfaccia di riga di comando:** `python scripts/hmw.py <comando>`.
  - Con `--json` (o `-o file.json`) l'output è JSON, altrimenti un riepilogo leggibile.
  - Exit code: 0 ok; 1 controlli non superati (solo `measure`); 2 errore d'uso; 3
    strumento esterno mancante.
- **Lingua (spec §10):**
  - istruzioni delle skill e dei prompt in inglese;
  - ogni messaggio all'utente nella lingua dell'utente;
  - le correzioni nella lingua del documento.
- **Indipendenza dalla piattaforma:** nessuna skill dipende da strumenti di una sola
  piattaforma. Le domande all'utente sono formulate come "ask the user"; i sub-agenti
  come "dispatch a fresh subagent; if you cannot, do it yourself reading only the files
  listed".
- **Nessuna invenzione (spec §3.2):** i revisori non aggiungono fatti, numeri o fonti.
  Ciò che non possono correggere da soli diventa una domanda all'utente.
- **Caratteri per riga:** si contano **spazi inclusi**.
- **Famiglie di font equivalenti (spec §8):**
  - times = Times New Roman, Times, Liberation Serif, TeX Gyre Termes, Nimbus Roman,
    NimbusRomNo9L;
  - helvetica = Helvetica, Arial, Liberation Sans, TeX Gyre Heros, Nimbus Sans;
  - courier = Courier, Courier New, Liberation Mono, TeX Gyre Cursor, Nimbus Mono.
- **Script dalle skill:** le skill trovano gli script con il percorso
  `<cartella della skill>/../../scripts/hmw.py`, che vale su entrambe le piattaforme.

## Review Focus

1. **Testo dentro caselle di testo.** Il frontespizio del facsimile Unibo è fatto di
   caselle di testo (`w:txbxContent`, duplicate in `mc:Choice`/`mc:Fallback`).
   L'estrazione deve leggerle **una sola volta**. Test in Task 2:
   `test_extract_facsimile_textboxes_once`.
2. **Documento che contiene già revisioni o commenti** (es. del tutor). Il testo
   "visibile" esclude `w:del`; le nuove revisioni non devono rompere quelle esistenti.
   Test in Task 7: `test_track_on_doc_with_existing_revisions`.
3. **Percorsi con spazi e accenti** (`Relazione finale Università.docx`). La conversione
   con soffice e la ricerca del PDF prodotto devono funzionare. Test in Task 6:
   `test_render_path_with_spaces_and_accents`.
4. **LibreOffice già aperto dall'utente.** Senza un profilo privato la conversione
   headless fallisce in silenzio, quindi il comando deve sempre usare
   `-env:UserInstallation` con una cartella temporanea. Test in Task 6:
   `test_soffice_command_uses_private_profile`.
5. **Correzione che cade su un collegamento ipertestuale o su un campo** (es.
   citazione Zotero). La correzione va nella lista `failed` con un motivo, senza
   corrompere il file. Test in Task 7: `test_track_refuses_hyperlink_and_field`.

---

## Struttura dei file

```
.claude-plugin/plugin.json          manifest Claude Code
.claude-plugin/marketplace.json     marketplace Claude Code (installazione da GitHub)
.codex-plugin/plugin.json           manifest Codex
.agents/plugins/marketplace.json    marketplace Codex
requirements.txt, requirements-dev.txt, pytest.ini, .gitignore, README.md
scripts/hmw.py                      entry point: aggiunge scripts/ a sys.path, chiama cli.main()
scripts/helpmewrite/
  __init__.py   cli.py   doctor.py   fonts.py   rules.py   extract.py
  layout.py     render.py   measure.py   edits.py   track_docx.py   track_tex.py   bib.py
profili/relazione-tirocinio.md      profilo completo (spec §5.3)
profili/generico.md                 profilo generico
skills/linee-guida/SKILL.md         + schema-linee-guida.md
skills/revisione/SKILL.md           + prompt-revisore.md + modello-rapporto.md
skills/revisione-bibliografia/SKILL.md  + prompt-revisore-bibliografia.md
tests/conftest.py                   sys.path, cartella fixture, marker per strumenti mancanti
tests/fixtures/builders.py          costruttori di documenti di prova
tests/fixtures/testo_italiano.txt   ~700 parole di prosa italiana (tirocinio fittizio)
tests/fixtures/linee-guida-unibo.yaml   estrazione attesa dal facsimile
tests/test_*.py                     un file per modulo
tests/scenari/                      scenari eseguiti da un agente (Task 11–12)
```

---

### Task 1: Scheletro del plugin, manifest e `doctor`

**Files:**
- Create: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json`
- Create: `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `.gitignore` (`__pycache__/`, `.pytest_cache/`, `*.pyc`, `tests/_out/`)
- Create: `scripts/hmw.py`, `scripts/helpmewrite/__init__.py`, `scripts/helpmewrite/cli.py`, `scripts/helpmewrite/doctor.py`, `scripts/helpmewrite/render.py` (solo `find_soffice`)
- Create: `README.md` (italiano: cos'è, requisiti, installazione Claude Code e Codex, `doctor`)
- Test: `tests/conftest.py`, `tests/test_manifests.py`, `tests/test_doctor.py`

**Interfaces:**
- Produces:
  - `doctor.check_environment() -> dict`. Chiavi: `python` (str versione),
    `python_ok` (bool), `packages` (dict nome→versione o None), `soffice` (str
    percorso o None), `latexmk` (str o None), `latexdiff` (str o None), `missing`
    (lista di `{"what", "needed_for", "how_to_install"}`).
  - `render.find_soffice()`: lo usa `doctor`. Va definito qui in `render.py` con solo
    questa funzione; Task 6 aggiunge il resto del modulo.
  - `cli.main(argv: list[str] | None = None) -> int`. Sottocomandi registrati da ogni
    task con `cli.register(name, add_arguments, handler)`.
  - `cli.emit(data: dict, args) -> None`: stampa JSON se `--json`, scrive su file se
    `-o`, altrimenti un riepilogo.

- [ ] **Step 1: Scrivi i test dei manifest**

```python
def test_claude_manifest():
    m = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    assert m["name"] == "help-me-write" and m["version"] == "0.1.0"

def test_claude_marketplace_points_to_repo_root():
    m = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    assert m["plugins"][0]["name"] == "help-me-write" and m["plugins"][0]["source"] == "./"

def test_codex_manifest():
    m = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
    assert m["name"] == "help-me-write" and m["skills"] == "./skills/"
    assert m["interface"]["displayName"] == "Help Me Write"

def test_codex_marketplace():
    m = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
    assert m["plugins"][0]["source"] == {"source": "url", "url": "./"}
```

- [ ] **Step 2: Esegui e verifica che falliscano.** `pytest tests/test_manifests.py -v` → FAIL (file assenti).
- [ ] **Step 3: Crea i manifest.** Ricalca la struttura di Superpowers (vedi spec §5.2).
  - Codex `interface`: `displayName` "Help Me Write", `category` "Productivity",
    `capabilities` ["Interactive","Read","Write"];
  - `defaultPrompt`: ["Rivedi la mia relazione", "Review my paper draft"];
  - descrizione in inglese.
  - Prima di scrivere il manifest Codex, verifica i campi su
    https://developers.openai.com/codex/plugins/build/ e annota nel commit eventuali
    differenze.
- [ ] **Step 4: Esegui.** `pytest tests/test_manifests.py -v` → PASS.
- [ ] **Step 5: Scrivi i test di `doctor`**

```python
def test_doctor_reports_python_and_packages():
    env = check_environment()
    assert env["python_ok"] is True
    assert set(env["packages"]) == {"docx", "lxml", "pdfplumber", "yaml", "bibtexparser"}

def test_doctor_lists_missing_tool_with_install_hint(monkeypatch):
    monkeypatch.setattr(render, "find_soffice", lambda: None)
    env = check_environment()
    item = next(m for m in env["missing"] if m["what"] == "LibreOffice")
    assert "libreoffice.org" in item["how_to_install"]

def test_cli_doctor_json(capsys):
    assert main(["doctor", "--json"]) == 0
    assert "python_ok" in json.loads(capsys.readouterr().out)
```

- [ ] **Step 6: Esegui.** `pytest tests/test_doctor.py -v` → FAIL.
- [ ] **Step 7: Implementa `cli.py`, `doctor.py`, `render.find_soffice()`, `hmw.py`.**
  - `find_soffice()` cerca, nell'ordine:
    1. `shutil.which("soffice")` e `shutil.which("libreoffice")`;
    2. `C:\Program Files\LibreOffice\program\soffice.exe`;
    3. `/Applications/LibreOffice.app/Contents/MacOS/soffice`.
  - I suggerimenti di installazione indicano il sito ufficiale (libreoffice.org,
    tug.org/texlive) e `pip install -r requirements.txt`.
- [ ] **Step 8: Esegui.** `pytest -v` → PASS. Poi `python scripts/hmw.py doctor` stampa il riepilogo.
- [ ] **Step 9: Commit.** `git add -A && git commit -m "feat: plugin skeleton, manifests, doctor"`

---

### Task 2: Estrazione dei paragrafi (`extract`)

**Files:**
- Create: `scripts/helpmewrite/extract.py`, `tests/fixtures/builders.py`, `tests/fixtures/testo_italiano.txt`
- Test: `tests/test_extract.py`

**Interfaces:**
- Produces:
  - `iter_body_paragraphs(doc: docx.document.Document) -> list[lxml element w:p]`.
    - Contiene tutti i `w:p` del corpo in ordine di documento: celle di tabella e
      caselle di testo incluse; header, footer e note escluse.
    - Delle caselle di testo prende solo il ramo `mc:Choice` (salta `mc:Fallback`).
    - **L'indice in questa lista è l'id del paragrafo** usato da `track_docx`, `bib` e
      dai revisori.
  - `visible_text(p) -> str`: testo di `w:t` nei run diretti, in `w:ins` e in
    `w:hyperlink`; esclude `w:del`/`w:delText`; `w:tab`→"\t", `w:br`→"\n".
  - `extract_docx(path) -> list[dict]` con `{"id": int, "style": str,
    "heading_level": int | None, "text": str}`. `heading_level` deriva da stili
    "Heading N"/"Titolo N" o da `w:outlineLvl`.
  - `extract_tex(main: Path) -> list[dict]` con `{"id", "file" (relativo a main),
    "line": int, "text": str}`.
    - Una voce per riga non vuota e non commento.
    - Segue `\input{}` e `\include{}`, aggiungendo `.tex` se manca.
  - `extract_pdf(path) -> list[dict]` con `{"id", "page": int, "text": str}`: un
    paragrafo per blocco separato da riga vuota (`pdfplumber`).
  - `extract(path) -> dict` con `{"format": "docx"|"latex"|"pdf", "source": str,
    "paragraphs": [...]}`. È il comando `extract <doc> [-o]`.
  - `builders.write_docx(path, paragraphs: list[str | tuple[str, str]], font="Calibri",
    size_pt=11, margins_cm=1.5, line_spacing=None) -> Path`. Una tupla `(style, text)`
    imposta lo stile (es. `("Heading 1", "Introduzione")`).
  - `builders.italian_paragraphs(n: int) -> list[str]`: ripete ciclicamente i paragrafi
    di `testo_italiano.txt`.

- [ ] **Step 1: Scrivi `testo_italiano.txt`.** Circa 700 parole in 6–8 paragrafi, prosa
  italiana realistica su un tirocinio fittizio (sviluppo di una pipeline CI in
  un'azienda fittizia "Alfa Sistemi"). Nessun dato reale.
- [ ] **Step 2: Scrivi i test**

```python
def test_extract_docx_ids_and_headings(tmp_path):
    p = write_docx(tmp_path / "a.docx", [("Heading 1", "Introduzione"), "Primo.", "Secondo."])
    paras = extract_docx(p)
    assert [x["id"] for x in paras] == [0, 1, 2]
    assert paras[0]["heading_level"] == 1 and paras[2]["text"] == "Secondo."

def test_extract_facsimile_textboxes_once():
    paras = extract_docx(ROOT / "docs/riferimenti/Facsimile_relazione_di_fine_tirocinio.docx")
    texts = [x["text"] for x in paras]
    assert sum("indicare nome e cognome" in t for t in texts) == 1
    assert any("RELAZIONE DI FINE TIROCINIO CURRICULARE" in t for t in texts)

def test_visible_text_skips_deleted_runs():
    # paragrafo costruito a mano con <w:del><w:r><w:delText>vecchio</w:delText></w:r></w:del>
    # e <w:ins><w:r><w:t>nuovo</w:t></w:r></w:ins>
    assert visible_text(p) == "testo nuovo"

def test_extract_tex_follows_input(tmp_path):
    # main.tex contiene \input{cap1} ; cap1.tex riga 3 = "Testo del capitolo."
    paras = extract_tex(tmp_path / "main.tex")
    assert {"file": "cap1.tex", "line": 3} == {k: paras[-1][k] for k in ("file", "line")}
```

- [ ] **Step 3: Esegui.** `pytest tests/test_extract.py -v` → FAIL.
- [ ] **Step 4: Implementa `extract.py`, `builders.py` e il comando `extract`.**
- [ ] **Step 5: Esegui.** `pytest tests/test_extract.py -v` → PASS.
- [ ] **Step 6: Commit.** `git commit -m "feat: paragraph extraction for docx, tex, pdf"`

---

### Task 3: Linee guida come dati (`rules`)

**Files:**
- Create: `scripts/helpmewrite/rules.py`, `tests/fixtures/linee-guida-unibo.yaml`
- Test: `tests/test_rules.py`

**Interfaces:**
- Produces (dataclass):
  - `Range(min: float | None, max: float | None)` con `mid() -> float | None`.
  - `SectionRule(name: str, required: bool, headings: list[str], pages: Range | None)`.
    Se `headings` è vuoto, la sezione non viene verificata dallo script ma solo dal
    revisore.
  - `Rules` con i campi:
    - `document_type: str`, `language: str`, `format: str | None` ("docx"|"latex"),
      `source: str | None`;
    - `pages: Range | None`, `fonts: list[str]`, `font_size_pt: float | None`;
    - `lines_per_page: Range | None`, `chars_per_line: Range | None`,
      `page_numbers: bool`;
    - `sections: list[SectionRule]`, `content_rules: list[str]`,
      `title_page_template: str | None`.
  - `load_rules(path: Path) -> Rules`. Solleva `RulesError(problems: list[str])`
    elencando **tutti** i problemi, non solo il primo.
  - Comando `rules validate <file>`.

- [ ] **Step 1: Scrivi `linee-guida-unibo.yaml`.** Riporta la scheda della spec §9 nel
  formato `Rules`:
  - `pages {min 10, max 30}`;
  - `fonts [Times New Roman, Courier, Helvetica]`, `font_size_pt 12`;
  - `lines_per_page {30, 35}`, `chars_per_line {60, 70}`, `page_numbers true`;
  - sezioni:
    - frontespizio (required, headings []);
    - indice (headings [indice, sommario]);
    - introduzione (headings [introduzione], pages {1, 2});
    - corpo (headings []);
    - conclusione (headings [conclusione, conclusioni], pages {1, 2});
    - allegati (required false, headings [allegati, appendice]);
  - `content_rules`: le 3 frasi del facsimile su diario, contributo personale e
    originalità;
  - `title_page_template` = percorso del facsimile.
- [ ] **Step 2: Scrivi i test**

```python
def test_load_unibo_rules():
    r = load_rules(FIX / "linee-guida-unibo.yaml")
    assert r.chars_per_line == Range(60, 70) and r.lines_per_page.mid() == 32.5
    assert [s.name for s in r.sections if s.required] == ["frontespizio", "indice", "introduzione", "corpo", "conclusione"]

def test_rules_errors_are_all_reported(tmp_path):
    (tmp_path / "x.yaml").write_text("document_type: x\nfont_size_pt: dodici\npages: {min: 30, max: 10}\n")
    with pytest.raises(RulesError) as e:
        load_rules(tmp_path / "x.yaml")
    assert len(e.value.problems) == 2   # font_size_pt non numerico, pages min > max
```

- [ ] **Step 3: Esegui.** FAIL. **Step 4: Implementa.** **Step 5: Esegui.** PASS.
- [ ] **Step 6: Commit.** `git commit -m "feat: guidelines schema and validation"`

---

### Task 4: Font e calcolo dell'impaginazione (`layout`)

**Files:**
- Create: `scripts/helpmewrite/fonts.py`, `scripts/helpmewrite/layout.py` (solo `compute_layout`; `apply_layout` arriva in Task 5)
- Test: `tests/test_layout.py`

**Interfaces:**
- Produces:
  - `normalize_font(name: str) -> str | None`.
    - Restituisce "times", "helvetica", "courier" o None.
    - Toglie il prefisso di sottoinsieme PDF (`ABCDEF+`), i suffissi
      `-Bold`/`,Italic`/`MT`/`PSMT`, ignora maiuscole e spazi.
    - Alias: quelli dei Global Constraints.
  - `DOCX_FONT = {"times": "Times New Roman", "helvetica": "Arial", "courier": "Courier New"}`.
  - `AVG_CHAR_WIDTH_EM = {"times": 0.44, "helvetica": 0.50, "courier": 0.60}`. Sono
    valori iniziali: Task 6 li calibra.
  - `Layout` (dataclass), con i campi:
    - `family: str`, `docx_font: str`, `font_size_pt: float`;
    - `paper_cm: tuple[float, float]`, `margins_cm: dict[str, float]` (top, bottom,
      left, right);
    - `line_pitch_pt: float | None`, `target_chars: int | None`,
      `target_lines: int | None`.
  - `compute_layout(rules: Rules, font: str, paper_cm=(21.0, 29.7),
    vertical_margin_cm=2.5) -> Layout`.
    - Arrotondamenti sempre "half-up" (32.5 → 33), mai il `round()` bancario di Python.
    - `target_chars = round(chars_per_line.mid())`.
    - Larghezza del testo = `target_chars × AVG_CHAR_WIDTH_EM[family] × font_size_pt`.
      Margini sinistro e destro uguali, `(larghezza foglio − larghezza testo) / 2`.
    - `target_lines = round(lines_per_page.mid())`.
    - `line_pitch_pt = (altezza foglio − 2×vertical_margin) in pt / target_lines × 0.995`.
    - Se mancano `chars_per_line` o `lines_per_page`: margini 2.5 cm e `line_pitch_pt=None`.
    - Errore `LayoutError` se `font` non appartiene a una famiglia nota o non è tra
      `rules.fonts` (quando la lista non è vuota).
  - Comando `layout --rules <yaml> --font <nome> [-o layout.json]`.

- [ ] **Step 1: Scrivi i test**

```python
@pytest.mark.parametrize("raw,fam", [("ABCDEF+LiberationSerif-Bold", "times"), ("ArialMT", "helvetica"),
    ("TeXGyreCursor-Regular", "courier"), ("Calibri", None)])
def test_normalize_font(raw, fam):
    assert normalize_font(raw) == fam

def test_courier_layout_unibo():
    lay = compute_layout(load_rules(FIX / "linee-guida-unibo.yaml"), "Courier")
    assert lay.target_chars == 65 and lay.target_lines == 33          # arrotondamento half-up: 32.5 → 33
    assert lay.margins_cm["left"] == pytest.approx(2.25, abs=0.05)    # 65 × 0.6 × 12 pt = 16.51 cm di testo
    assert lay.line_pitch_pt == pytest.approx(21.1, abs=0.1)          # 24.7 cm / 33 × 0.995

def test_font_not_allowed():
    with pytest.raises(LayoutError):
        compute_layout(load_rules(FIX / "linee-guida-unibo.yaml"), "Calibri")
```

- [ ] **Step 2: Esegui.** FAIL. **Step 3: Implementa.** **Step 4: Esegui.** PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat: font families and layout computation"`

---

### Task 5: Applicare l'impaginazione a una copia (`format`)

**Files:**
- Modify: `scripts/helpmewrite/layout.py` (aggiungi `apply_layout`)
- Test: `tests/test_format.py`

**Interfaces:**
- Consumes: `Layout` (Task 4).
- Produces:
  - `apply_layout(src: Path, layout: Layout, dst: Path) -> list[str]`. Restituisce
    l'elenco leggibile delle modifiche fatte.
    - Imposta tutte le sezioni: formato carta e margini.
    - Imposta gli stili `Normal` e `Heading 1–3` (o i loro equivalenti localizzati,
      trovati per `w:styleId`): font `layout.docx_font` (ascii, hAnsi, cs, eastAsia) e
      dimensione `font_size_pt` per Normal.
    - Applica l'interlinea esatta (`w:spacing w:line=<pitch×20> w:lineRule="exact"`) a
      Normal e agli stili di paragrafo basati su Normal.
    - Rimuove le sovrascritture dirette di font, dimensione e interlinea dai paragrafi
      del corpo.
    - Aggiunge un campo PAGE centrato nel footer se nessun footer contiene un campo PAGE.
    - Rifiuta `dst == src`.
  - Comando `format <in.docx> --layout <layout.json> -o <out.docx>`.

- [ ] **Step 1: Scrivi i test**

```python
def test_apply_layout_sets_margins_fonts_spacing(tmp_path):
    src = write_docx(tmp_path / "in.docx", italian_paragraphs(10))
    lay = compute_layout(load_rules(FIX / "linee-guida-unibo.yaml"), "Times New Roman")
    changes = apply_layout(src, lay, tmp_path / "out.docx")
    d = Document(tmp_path / "out.docx")
    assert d.sections[0].left_margin.cm == pytest.approx(lay.margins_cm["left"], abs=0.01)
    assert d.styles["Normal"].font.name == "Times New Roman" and d.styles["Normal"].font.size.pt == 12
    assert 'w:lineRule="exact"' in d.styles["Normal"].element.xml
    assert "PAGE" in "".join(s.footer._element.xml for s in d.sections)
    assert changes

def test_apply_layout_refuses_same_path(tmp_path):
    src = write_docx(tmp_path / "in.docx", ["x"])
    with pytest.raises(ValueError):
        apply_layout(src, compute_layout(load_rules(FIX / "linee-guida-unibo.yaml"), "Courier"), src)
```

- [ ] **Step 2: Esegui.** FAIL. **Step 3: Implementa.** **Step 4: Esegui.** PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat: apply computed layout to a docx copy"`

---

### Task 6: Impaginare e misurare (`render`, `measure`)

**Files:**
- Modify: `scripts/helpmewrite/render.py`
- Create: `scripts/helpmewrite/measure.py`
- Modify: `scripts/helpmewrite/fonts.py` (calibrazione `AVG_CHAR_WIDTH_EM`)
- Test: `tests/test_render.py`, `tests/test_measure.py` (marker `needs_soffice`: skip se `find_soffice()` è None)

**Interfaces:**
- Produces:
  - **`render.py`:**
    - `soffice_command(src, outdir, profile_dir) -> list[str]`. Include
      `-env:UserInstallation=<profile_dir.as_uri()>`, `--headless`,
      `--convert-to pdf`, `--outdir <outdir>`.
    - `render_pdf(src: Path, workdir: Path) -> Path`:
      - `.pdf` lo restituisce così com'è;
      - `.docx` passa da soffice, con un profilo temporaneo dentro `workdir` e timeout
        180 s;
      - `.tex` passa da `latexmk -pdf -interaction=nonstopmode -outdir=<workdir>`;
      - errori come `RenderError(message, missing_tool: str | None)`.
  - **`measure.py`**, dataclass:
    - `PageStats(number, body_lines, chars_per_full_line: float | None,
      font_chars: dict[str, int], body_size_pt: float | None, has_page_number: bool,
      is_full: bool, text: str)`;
    - `SectionSpan(title, level, start_page, end_page)`;
    - `Check(rule: str, ok: bool, detail: str, pages: list[int])`;
    - `Measurement(source, pdf, page_count, pages, sections, checks)`.
  - **Funzioni di `measure.py`:**
    - `measure_pdf(pdf: Path, body_size_pt: float | None = None) -> list[PageStats]`;
    - `section_spans(pages: list[PageStats], headings: list[dict]) -> list[SectionSpan]`.
      `headings` sono i paragrafi di `extract` con `heading_level`; la pagina di
      inizio è la prima pagina, dopo la 1, il cui testo contiene il titolo
      normalizzato (spazi compressi, case-insensitive).
    - `check_rules(m_pages, sections, rules: Rules) -> list[Check]`. Id delle regole:
      `pages`, `font_family`, `font_size`, `lines_per_page`, `chars_per_line`,
      `page_numbers`, `section:<nome>:present`, `section:<nome>:pages`.
    - `measure(doc: Path, rules: Rules, workdir: Path) -> Measurement`.
    - Comando `measure <doc> --rules <yaml> [--workdir] [-o]`. Exit 1 se qualche
      check è `ok=False`.

Algoritmo di misura (le decisioni che i test non fissano da soli):
- **Parole e righe.** Le parole si leggono con
  `page.extract_words(extra_attrs=["fontname", "size"])`. Le righe sono gruppi di
  parole con `top` entro 2 pt; il testo della riga sono le parole unite da uno spazio.
- **Corpo del testo.** La dimensione del corpo è la dimensione più frequente nel
  documento, pesata per numero di caratteri (se non è passata). Le righe del corpo
  sono quelle con dimensione entro ±0.6 pt da quella del corpo, fuori dalle fasce
  header e footer (7% superiore e inferiore della pagina).
- **Numero di pagina.** Una riga nelle fasce header o footer che corrisponde a
  `^\W*\d+\W*$` o `^(pag\.?|pagina|page)\s*\d+`.
- **Riga piena.** Larghezza ≥ 90% della riga di corpo più larga del documento.
  `chars_per_full_line` è la mediana sulla pagina.
- **Pagina piena.** Le righe di corpo coprono verticalmente ≥ 75% dell'altezza media
  dell'area di testo delle pagine. I controlli `lines_per_page` e `chars_per_line`
  valutano solo le pagine piene e mai la pagina 1 (frontespizio). Il controllo
  `page_numbers` esclude la pagina 1.
- **Font.** `font_family` è ok se ≥ 95% dei caratteri del corpo appartiene a una
  famiglia ammessa da `rules.fonts` (tramite `normalize_font`). `font_size` è ok se la
  dimensione del corpo è entro ±0.5 pt da `rules.font_size_pt`.
- **Sezioni.** `section:<nome>:pages` conta le pagine come
  `end_page − start_page + 1`. La sezione finisce alla pagina prima del titolo
  successivo di livello uguale o superiore.

- [ ] **Step 1: Scrivi i test di `render`**

```python
def test_soffice_command_uses_private_profile(tmp_path):
    cmd = soffice_command(Path("a.docx"), tmp_path, tmp_path / "prof")
    assert any(c.startswith("-env:UserInstallation=file:") for c in cmd) and "--headless" in cmd

@needs_soffice
def test_render_path_with_spaces_and_accents(tmp_path):
    src = write_docx(tmp_path / "Relazione finale Università.docx", italian_paragraphs(3))
    pdf = render_pdf(src, tmp_path / "work")
    assert pdf.exists() and pdf.suffix == ".pdf"

def test_render_tex_without_latexmk_reports_missing_tool(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(RenderError) as e:
        render_pdf(tmp_path / "main.tex", tmp_path)
    assert e.value.missing_tool == "latexmk"
```

- [ ] **Step 2: Esegui.** FAIL. **Step 3: Implementa `render.py`.** **Step 4: Esegui.** PASS.
- [ ] **Step 5: Scrivi i test di calibrazione e misura.** Sono questi che fissano
  `AVG_CHAR_WIDTH_EM`.

```python
@needs_soffice
@pytest.mark.parametrize("font", ["Times New Roman", "Courier", "Helvetica"])
def test_layout_meets_unibo_rules_after_measure(tmp_path, font):
    rules = load_rules(FIX / "linee-guida-unibo.yaml")
    src = write_docx(tmp_path / "in.docx", [("Heading 1", "Introduzione")] + italian_paragraphs(40))
    apply_layout(src, compute_layout(rules, font), tmp_path / "out.docx")
    m = measure(tmp_path / "out.docx", rules, tmp_path / "w")
    by = {c.rule: c for c in m.checks}
    assert by["chars_per_line"].ok, by["chars_per_line"].detail
    assert by["lines_per_page"].ok, by["lines_per_page"].detail
    assert by["font_family"].ok and by["page_numbers"].ok

@needs_soffice
def test_bad_layout_is_flagged(tmp_path):
    src = write_docx(tmp_path / "bad.docx", italian_paragraphs(30), font="Calibri", size_pt=11, margins_cm=1.5)
    by = {c.rule: c for c in measure(src, load_rules(FIX / "linee-guida-unibo.yaml"), tmp_path / "w").checks}
    assert not by["font_family"].ok and not by["font_size"].ok and not by["chars_per_line"].ok
    assert "7" in by["chars_per_line"].detail or "8" in by["chars_per_line"].detail   # ~80+ caratteri

@needs_soffice
def test_section_pages_for_introduction(tmp_path):
    # Heading "Introduzione" + 4 pagine di testo + Heading "Conclusione" + 1 pagina
    by = {c.rule: c for c in m.checks}
    assert not by["section:introduzione:pages"].ok and by["section:conclusione:pages"].ok
```

- [ ] **Step 6: Esegui.** FAIL. **Step 7: Implementa `measure.py`.**
- [ ] **Step 8: Esegui e calibra.** Se `test_layout_meets_unibo_rules_after_measure`
  fallisce su una famiglia, correggi solo `AVG_CHAR_WIDTH_EM[famiglia]` con il valore
  misurato: caratteri medi osservati → larghezza in em. Poi riesegui fino a PASS. Nel
  messaggio di commit annota i valori finali.
- [ ] **Step 9: Esegui.** `pytest -v` → PASS (i test `needs_soffice` passano in questo ambiente, dove LibreOffice c'è).
- [ ] **Step 10: Commit.** `git commit -m "feat: render to PDF and measure layout rules (calibrated)"`

---

### Task 7: Correzioni tracciate e commenti in Word (`track` per .docx)

**Files:**
- Create: `scripts/helpmewrite/edits.py`, `scripts/helpmewrite/track_docx.py`
- Test: `tests/test_edits.py`, `tests/test_track_docx.py`

**Interfaces:**
- Consumes: `iter_body_paragraphs`, `visible_text` (Task 2).
- Produces:
  - **`edits.py`:**
    - `Edit(paragraph: int | None, file: str | None, line: int | None, find: str,
      replace: str | None, comment: str | None, reason: str, by: str)`.
      - Per .docx/.pdf serve `paragraph`; per .tex servono `file` e `line`.
      - `replace=""` significa cancellazione.
      - Serve almeno uno tra `replace` e `comment`.
      - `by` vale "revisore" o "bibliografia".
    - `EditSet(author: str, edits: list[Edit])`, `load_edits(path) -> EditSet`,
      `dump_edits(EditSet, path)`.
    - `merge_edits(*sets) -> tuple[EditSet, list[dict]]`. Unisce più insiemi; due
      `find` sovrapposti nello stesso paragrafo sono un conflitto: si tiene il primo e
      il secondo va nella lista dei conflitti, con il motivo.
    - Formato JSON: `{"author": "help-me-write", "edits": [{"paragraph": 12, "find":
      "...", "replace": "...", "comment": "...", "reason": "...", "by": "revisore"}]}`.
  - **`track_docx.py`:**
    - `ApplyResult(applied: list[int], failed: list[dict])`, dove `failed` contiene
      `{"index", "reason"}`.
    - `apply_edits_docx(src: Path, edits: EditSet, dst: Path,
      date: datetime | None = None) -> ApplyResult`.
  - Comando `track <doc> --edits <json> [--edits <json> ...] -o <out>`.
    - Con più `--edits` li unisce con `merge_edits`.
    - Restituisce JSON `{"applied", "failed", "conflicts"}`.
    - Sceglie tra docx e tex in base all'estensione; il caso tex arriva in Task 8.

Algoritmo (le decisioni non ovvie):
- **Ricerca.** `find` va cercato nel `visible_text` del paragrafo e deve comparire
  esattamente una volta. Altrimenti l'edit va in `failed` con motivo "not found" o
  "ambiguous".
- **Rifiuti.** Se la corrispondenza tocca un run dentro `w:hyperlink`, `w:fldSimple`,
  oppure tra `w:fldChar begin` e `end`, l'edit va in `failed` con motivo
  "hyperlink/field".
- **Divisione dei run.** I run vanno divisi ai confini della corrispondenza: copia
  profonda del run, testo spezzato, `w:rPr` conservato, `xml:space="preserve"`.
- **Sostituzione.**
  1. I run della corrispondenza vanno avvolti in `w:del` (con `w:t` trasformato in
     `w:delText`).
  2. Subito dopo va un `w:ins` con un run nuovo che porta l'`rPr` del primo run della
     corrispondenza e il testo di `replace`.
  3. `w:id` sono interi unici: il massimo esistente nel documento + 1, crescente.
     `w:author` = `edits.author`; `w:date` in ISO 8601 UTC.
- **Commento.** Si usa l'API commenti di python-docx 1.2 (`document.add_comment`),
  ancorata ai run della corrispondenza; per una sostituzione, ancorata alla coppia
  `w:del` + `w:ins`, con i marcatori di intervallo come fratelli a livello di
  paragrafo. Autore `edits.author`, iniziali "HMW".
- **Ordine di applicazione.** Edit di paragrafi diversi in ordine qualsiasi; nello
  stesso paragrafo, in ordine di offset decrescente.

- [ ] **Step 1: Scrivi i test di `edits`.** Caricamento e validazione: un edit senza `replace` né `comment` è un errore; `merge_edits` segnala la sovrapposizione.
- [ ] **Step 2: Scrivi i test di `track_docx`**

```python
def test_replace_inside_single_run(tmp_path):
    src = write_docx(tmp_path / "a.docx", ["Il sistema e stato installato."])
    r = apply_edits_docx(src, EditSet("help-me-write", [Edit(0, None, None, "e stato", "è stato", None, "accento", "revisore")]), tmp_path / "b.docx")
    assert r.applied == [0] and r.failed == []
    p = iter_body_paragraphs(Document(tmp_path / "b.docx"))[0]
    assert visible_text(p) == "Il sistema è stato installato."
    assert 'w:author="help-me-write"' in etree.tostring(p).decode()

def test_replace_across_runs_keeps_formatting(tmp_path):
    # paragrafo con run "Il " + run grassetto "framework" + run " React"; find "framework React"
    # → il testo inserito eredita il grassetto del primo run della corrispondenza; il testo visibile finale è corretto

def test_comment_only(tmp_path):
    ...
    assert len(list(Document(out).comments)) == 1 and "fonte" in next(iter(Document(out).comments)).text

def test_not_found_and_ambiguous(tmp_path):
    ...
    assert {f["reason"] for f in r.failed} == {"not found", "ambiguous"}

def test_track_on_doc_with_existing_revisions(tmp_path):
    # sorgente con un w:ins/w:del preesistente di autore "Tutor" nello stesso paragrafo
    # → l'edit nuovo si applica sul testo visibile; le revisioni di "Tutor" restano intatte

def test_track_refuses_hyperlink_and_field(tmp_path):
    # find dentro un w:hyperlink e dentro un campo ADDIN ZOTERO → entrambi in failed con reason "hyperlink/field"

@needs_soffice
def test_tracked_output_opens_in_libreoffice(tmp_path):
    # il file risultante viene convertito in PDF da render_pdf senza errori
```

- [ ] **Step 3: Esegui.** FAIL. **Step 4: Implementa `edits.py` e `track_docx.py`.** **Step 5: Esegui.** PASS.
- [ ] **Step 6: Verifica manuale una tantum.** Converti un output con soffice, poi apri `word/document.xml`: `w:del`, `w:ins` e `commentRangeStart` devono essere ben annidati.
- [ ] **Step 7: Commit.** `git commit -m "feat: tracked changes and comments for docx"`

---

### Task 8: Correzioni LaTeX e PDF delle differenze (`track` per .tex, `texdiff`)

**Files:**
- Create: `scripts/helpmewrite/track_tex.py`
- Test: `tests/test_track_tex.py` (marker `needs_latex`: skip senza latexmk o latexdiff)

**Interfaces:**
- Consumes: `EditSet`, `ApplyResult`, `RenderError`.
- Produces:
  - `apply_edits_tex(main: Path, edits: EditSet, out_dir: Path) -> ApplyResult`.
    - Copia l'intera cartella di `main` in `out_dir`, che deve essere vuota o
      inesistente e fuori dalla cartella sorgente.
    - Applica gli edit con `replace` alla riga `line` di `file`: `find` deve comparire
      una sola volta in quella riga; se non c'è, si cerca nelle righe ±2 e deve
      comparire una sola volta.
    - Gli edit con solo `comment` non toccano i file e finiscono in `applied` (diventano
      voci del rapporto).
  - `texdiff(old_main: Path, new_main: Path, out_pdf: Path) -> Path`.
    1. `latexdiff --flatten old new` → `diff.tex` nella cartella del nuovo;
    2. `latexmk -pdf` di `diff.tex`;
    3. copia del PDF in `out_pdf`.
    - Strumento mancante → `RenderError(missing_tool=...)`.
  - Comando `texdiff <old_main> <new_main> -o <pdf>`.

- [ ] **Step 1: Scrivi i test.**
  - Edit applicato alla riga giusta.
  - Edit su riga spostata di 1, trovato nella finestra ±2.
  - Edit ambiguo → `failed`.
  - Originali invariati: confronto degli hash prima e dopo.
  - `texdiff` produce un PDF (`needs_latex`).
- [ ] **Step 2: Esegui.** FAIL. **Step 3: Implementa.** **Step 4: Esegui.** PASS.
- [ ] **Step 5: Prova LaTeX in questo ambiente.** Prova `apt-get install -y latexmk
  latexdiff texlive-latex-recommended texlive-fonts-recommended` ed esegui i test
  `needs_latex`. Se l'installazione non riesce, annota nel commit che quei test sono
  rimasti da verificare.
- [ ] **Step 6: Commit.** `git commit -m "feat: LaTeX edits on a copy and latexdiff PDF"`

---

### Task 9: Estrazione della bibliografia (`bib`, `pdftext`)

**Files:**
- Create: `scripts/helpmewrite/bib.py`
- Modify: `tests/fixtures/builders.py` (aggiungi `write_pdf_from_paragraphs(path, paragraphs)` via `write_docx` + `render_pdf`)
- Test: `tests/test_bib.py`

**Interfaces:**
- Consumes: `extract`, `render_pdf`.
- Produces (dataclass):
  - `BibEntry(key: str, raw: str, title: str | None, authors: list[str],
    year: str | None, doi: str | None, venue: str | None, paragraph: int | None)`.
  - `Citation(key: str, paragraph: int | None, file: str | None, line: int | None,
    sentence: str)`.
  - `BibReport(style: str, entries, citations, uncited_entries: list[str],
    missing_entries: list[str], local_sources: dict[str, str])`. `style` vale
    "numeric", "author-year", "latex" o "unknown".
- Produces (funzioni):
  - `extract_bibliography(doc: Path, bib: Path | None = None) -> BibReport`.
  - `find_local_sources(folder: Path, entries: list[BibEntry]) -> dict[str, str]`.
  - `pdf_pages_text(pdf: Path) -> list[str]`.
  - Comandi `bib <doc> [--bib refs.bib] [--sources <cartella>] [-o]` e
    `pdftext <pdf> [-o]`.

Regole di estrazione:
- **Sezione bibliografia in .docx/.pdf.** Sono i paragrafi dopo l'ultimo titolo che
  corrisponde a `bibliografia|riferimenti( bibliografici)?|references|bibliography`
  (case-insensitive). Ogni paragrafo non vuoto è una voce.
- **Chiavi delle voci:**
  - stile numerico: "[n]" se la voce inizia con `[n]`, altrimenti la posizione n;
  - stile autore-anno: cognome del primo autore (minuscolo, senza accenti) + anno,
    es. `rossi2021`.
- **Citazioni nel testo:**
  - numeriche `[3]`, `[2, 5]`, `[2–4]` (espanse);
  - autore-anno `(Rossi, 2021)`, `(Rossi et al., 2021; Bianchi 2019)`,
    `Rossi (2021)`;
  - LaTeX `\cite`, `\citep`, `\citet`, `\parencite`, `\textcite`, `\autocite`, con più
    chiavi separate da virgola.
- **Frase della citazione.** È la frase (divisione su `. `, `? `, `! `) che contiene la
  citazione.
- **Dati delle voci in .bib.** Si leggono con bibtexparser. Nelle voci testuali sono
  best-effort: anno `\b(19|20)\d{2}\b`, DOI `10\.\d{4,9}/\S+`, titolo tra virgolette
  o dopo "(anno)." fino al punto successivo. Se non si trova, il campo resta `None`: ci
  pensa l'agente.
- **Fonti locali.** Una voce ha una fonte locale se, nel testo delle prime 2 pagine di
  un PDF nella cartella (ricorsiva), si trova il suo DOI oppure ≥ 80% delle parole del
  titolo normalizzate.

- [ ] **Step 1: Scrivi i test.**

```python
def test_numeric_citations_and_missing(tmp_path):
    doc = write_docx(tmp_path / "d.docx", ["La build dura 12 minuti [1].", "Come mostrato in [2, 4].",
        ("Heading 1", "Bibliografia"), "[1] Rossi, M. (2021). Tempi di build. Rivista X.", "[2] Bianchi, L. (2019). Pipeline. Conf Y.",
        "[3] Verdi, A. (2020). Test. Z."])
    r = extract_bibliography(doc)
    assert r.style == "numeric" and r.missing_entries == ["[4]"] and r.uncited_entries == ["[3]"]
    assert r.citations[0].sentence == "La build dura 12 minuti [1]." and r.entries[0].year == "2021"

def test_author_year_keys(tmp_path):
    # "(Rossi et al., 2021; Bianchi 2019)" → chiavi ["rossi2021", "bianchi2019"]

def test_latex_cites_with_bibfile(tmp_path):
    # main.tex con \parencite{rossi21,bianchi19} e refs.bib con la sola voce rossi21 → missing ["bianchi19"]

@needs_soffice
def test_find_local_sources_by_title(tmp_path):
    # PDF in fonti/ con titolo "Tempi di build nelle pipeline di integrazione continua" → voce [1] trovata
```

- [ ] **Step 2: Esegui.** FAIL. **Step 3: Implementa.** **Step 4: Esegui.** PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat: bibliography and citation extraction, local source matching"`

---

### Task 10: Profili e skill delle linee guida

**Files:**
- Create: `profili/relazione-tirocinio.md`, `profili/generico.md`
- Create: `skills/linee-guida/SKILL.md`, `skills/linee-guida/schema-linee-guida.md`
- Test: `tests/test_skills_static.py`, `tests/scenari/linee-guida.md`

**Interfaces:**
- Consumes: comandi `rules validate`, `extract`, `doctor`.
- Produces:
  - La skill scrive `.help-me-write/linee-guida.yaml` nella cartella del lavoro.
    Quel file è il formato `Rules` (Task 3), valido per `rules validate`.
  - La "scheda" mostrata all'utente segue il blocco della spec §9.
  - Ogni profilo ha queste sezioni, con questi titoli esatti (le skill delle parti 1 e
    2 le leggono per nome): `## Recognize`, `## Typical structure`,
    `## Default guidelines`, `## Interview prompts`, `## Tone`,
    `## Content checklist`, `## Citation needs`.

Contenuti richiesti:
- **`relazione-tirocinio.md`:**
  - checklist di contenuto della spec §6.1: contributo personale, diario cronologico o
    di sviluppo, coerenza obiettivi/attività/risultati tra introduzione e conclusione,
    informazioni riservate, segnaposto `[DA VERIFICARE]`;
  - `## Citation needs`: le attività svolte dallo studente non richiedono citazioni;
    tecnologie, dati e affermazioni di terzi sì (spec §6.4).
- **`generico.md`:** ogni regola viene dalle linee guida o dall'utente; checklist di
  contenuto generale (chiarezza, ripetizioni, coerenza, tono adatto al pubblico).
- **`linee-guida/SKILL.md`:**
  - frontmatter con `name: linee-guida` e una `description` in inglese che inizi con
    "Use when", con le parole chiave: guidelines, regolamento, template, facsimile,
    page limits, font, formatting rules;
  - passi:
    1. cercare il documento delle linee guida (nella cartella o chiesto all'utente) e
       leggerlo con `extract`;
    2. scegliere il profilo e farlo confermare;
    3. compilare il YAML, usando i default del profilo solo dove le linee guida
       tacciono, e segnandoli come tali nella scheda;
    4. chiedere all'utente le regole mancanti che contano;
    5. `rules validate`;
    6. mostrare la scheda e farla confermare;
    7. salvare.
  - Se `.help-me-write/linee-guida.yaml` esiste già: la skill lo mostra e chiede se è
    ancora valido, senza rifare l'estrazione.
  - La skill **non** chiede LaTeX/Word: in revisione il formato si ricava dal file (la
    domanda appartiene al flusso di scrittura, Parte 2).

- [ ] **Step 1: Scrivi `tests/test_skills_static.py`.** Per ogni `skills/*/SKILL.md` verifica:
  - frontmatter YAML con `name` uguale al nome della cartella;
  - `description` lunga meno di 1024 caratteri, che inizia con "Use when";
  - ogni file citato nel corpo con un percorso relativo esiste.

  Per ogni `profili/*.md` verifica che le 7 intestazioni ci siano.
- [ ] **Step 2: Esegui.** FAIL. **Step 3: Scrivi profili e skill.** **Step 4: Esegui.** PASS.
- [ ] **Step 5: Scenario con agente** (`tests/scenari/linee-guida.md` descrive prompt ed esito atteso).
  1. Copia il facsimile in una cartella temporanea.
  2. Esegui
     `claude -p --plugin-dir <repo> "Estrai le linee guida dal facsimile in questa cartella e salvale" --permission-mode acceptEdits`
     nella cartella; se `claude -p` non è utilizzabile, usa un sub-agente nuovo a cui
     dai solo il testo della skill.
  3. Atteso:
     - `.help-me-write/linee-guida.yaml` supera `rules validate`;
     - coincide con `tests/fixtures/linee-guida-unibo.yaml` su `pages`,
       `font_size_pt`, `lines_per_page`, `chars_per_line`, `page_numbers` e sui nomi
       delle sezioni obbligatorie.
- [ ] **Step 6: Commit.** `git commit -m "feat: document profiles and guidelines skill"`

---

### Task 11: Skill di revisione e prompt del revisore

**Files:**
- Create: `skills/revisione/SKILL.md`, `skills/revisione/prompt-revisore.md`, `skills/revisione/modello-rapporto.md`
- Modify: `tests/fixtures/builders.py` (aggiungi `build_flawed_draft(dir) -> dict`)
- Create: `tests/scenari/revisione.md`, `tests/scenari/check_revisione.py`
- Test: `tests/test_flawed_fixture.py`

**Interfaces:**
- Consumes: tutti i comandi delle Task 1–9; la skill `linee-guida`; i profili.
- Produces:
  - **Cartella di lavoro** di ogni revisione:
    `.help-me-write/revisioni/<AAAA-MM-GG-HHMM>/`, con dentro `extract.json`,
    `measure.json`, `edits-revisore.json`, `note-revisore.md`, `edits.json` (unione) e
    `rapporto.md`.
  - **Copie accanto all'originale:**
    - `<nome>-revisionato.docx`: correzioni tracciate e commenti;
    - `<nome>-revisionato-formattato.docx`: solo se ci sono controlli di forma falliti
      e correggibili con `format`;
    - per LaTeX, la cartella `<nome>-revisionato/` e `<nome>-differenze.pdf`;
    - se il nome esiste già, si aggiunge `-2`, `-3`, …
  - **Contratto del sub-agente revisore** (`prompt-revisore.md`):
    - Riceve i percorsi di `extract.json`, `measure.json`, `linee-guida.yaml` e del
      profilo, più la lingua del documento.
    - Scrive `edits-revisore.json` (formato `EditSet`, `by: "revisore"`) e
      `note-revisore.md`, con tre sezioni: `## Form`, `## Content`, `## Questions for
      the author`.
    - Non legge né riceve la conversazione di scrittura.

Contenuti richiesti:
- **`revisione/SKILL.md`**, `name: revisione`, `description` "Use when the user wants a
  finished draft (docx, tex or pdf) reviewed or corrected against guidelines…".
  1. Trova il documento (chiedi se ce n'è più d'uno) e lancia `doctor`. Se manca uno
     strumento necessario, spiega all'utente come installarlo e fermati.
  2. Ottieni le linee guida con la skill `linee-guida`.
  3. Lancia `extract`, `measure` e, se `measure` restituisce `font_family`, `font_size`,
     `chars_per_line` o `lines_per_page` falliti, `layout` (con il primo font ammesso
     che l'utente conferma).
  4. Se il documento contiene citazioni o una sezione bibliografia, oppure il profilo
     ha `## Citation needs`, avvia **in parallelo** il revisore della bibliografia
     (skill `revisione-bibliografia`, Task 12).
  5. Avvia un sub-agente nuovo con `prompt-revisore.md` riempito. Se la piattaforma
     non lo consente, esegui tu il prompt leggendo solo i file elencati.
  6. Applica tutti gli edit con un solo comando `track`, con un `--edits` per ogni
     revisore. Il comando li unisce e restituisce `applied`, `failed` e `conflicts`.
  7. Riporta gli edit `failed` e i conflitti nel rapporto come "da sistemare a mano".
  8. Se i controlli di forma sono falliti, produci con `format` la copia `-formattato`.
  9. Scrivi `rapporto.md` secondo `modello-rapporto.md`.
  10. Mostra all'utente il riepilogo e le domande.
  11. Con le risposte, ripeti i passi 5–9 solo sugli edit nuovi, per **al massimo 2
      cicli**; poi lascia decidere all'utente.
  - Bozza solo PDF: si fanno solo il rapporto e il passo 4, senza `track` (spec §4).
- **`prompt-revisore.md`:**
  - checklist di forma e lingua della spec §6.1;
  - checklist di contenuto presa dal profilo;
  - regole sugli edit:
    - `find` copiato **esatto** dal testo di `extract.json`, minimo e univoco nel
      paragrafo;
    - mai sostituire interi paragrafi;
    - mai inventare contenuti: le lacune diventano domande, i segnaposto
      `[DA VERIFICARE]` vanno segnalati;
    - informazioni riservate (credenziali, dati di clienti) sempre segnalate con un
      commento.
- **`modello-rapporto.md`:**
  - sezioni: Riepilogo (file prodotti), Forma (tabella con regola, esito, dettaglio e
    impostazioni consigliate), Lingua, Contenuto, Bibliografia (dalla Task 12), Da
    sistemare a mano, Domande per te;
  - il rapporto è scritto nella lingua dell'utente.

- [ ] **Step 1: Scrivi `build_flawed_draft(dir)`.** Crea `bozza.docx` (circa 12 pagine, testo da `italian_paragraphs` più testo specifico) con i difetti della spec §9 caso 2:
  - Calibri 11, margini 1.5 cm (circa 85 caratteri per riga);
  - nessun indice;
  - introduzione di circa 4 pagine;
  - 5 refusi noti ("installaizone", "e stato", "perchè", "qual'è", "un'altro");
  - acronimo "CI/CD" mai definito;
  - "Figura 2" presente ma mai citata;
  - il capitolo "Attività svolte" scritto tutto al passivo impersonale, senza contributo
    personale;
  - la riga "password: Alfa2024!" in un paragrafo.

  Restituisce il dizionario `expected` con, per ogni difetto, un id e le parole chiave
  accettabili nel rapporto (es. `"credential": ["password", "credenzial", "riservat"]`).
- [ ] **Step 2: Scrivi `test_flawed_fixture.py`.** La bozza contiene davvero i difetti: `measure` fallisce `font_family`, `chars_per_line` e `section:introduzione:pages`; `extract` trova "installaizone".
- [ ] **Step 3: Esegui.** FAIL, poi implementa il builder e riesegui. PASS.
- [ ] **Step 4: Scrivi `SKILL.md`, `prompt-revisore.md`, `modello-rapporto.md`.** Poi esegui `pytest tests/test_skills_static.py` → PASS.
- [ ] **Step 5: Scrivi `check_revisione.py <workdir> <expected.json>`.** Verifica:
  - `rapporto.md` esiste e menziona ogni difetto (almeno una parola chiave per id);
  - `bozza-revisionato.docx` esiste, ha ≥ 5 `w:ins`, e "installazione" compare nel
    testo visibile;
  - `bozza.docx` è identico all'originale (hash).
- [ ] **Step 6: Scenario con agente** (`tests/scenari/revisione.md`). Costruisci la bozza in una cartella temporanea con un `linee-guida.yaml` già presente (copia del fixture Unibo) ed esegui `claude -p --plugin-dir <repo> "Rivedi bozza.docx"` (oppure un sub-agente nuovo con il testo della skill). Poi esegui `check_revisione.py` → tutti i controlli OK. Se un difetto non viene trovato, correggi il prompt o la skill (non il test) e ripeti.
- [ ] **Step 7: Commit.** `git commit -m "feat: review skill, reviewer prompt, report template, scenario"`

---

### Task 12: Revisore della bibliografia

**Files:**
- Create: `skills/revisione-bibliografia/SKILL.md`, `skills/revisione-bibliografia/prompt-revisore-bibliografia.md`
- Modify: `tests/fixtures/builders.py` (aggiungi `build_bib_draft(dir) -> dict`)
- Create: `tests/scenari/bibliografia.md`, `tests/scenari/check_bibliografia.py`

**Interfaces:**
- Consumes: `bib`, `pdftext`, `extract`, `merge_edits`, la cartella di lavoro della Task 11.
- Produces:
  - Il sub-agente scrive `bib.json` (output di `bib`), `edits-bibliografia.json`
    (`by: "bibliografia"`; i problemi come `comment`, le correzioni dei dati
    bibliografici come `replace`) e `note-bibliografia.md`.
  - `note-bibliografia.md` contiene una tabella per citazione con le colonne: chiave,
    frase, esito (supportata, parzialmente supportata, non supportata, non
    verificabile), livello di verifica (testo completo, abstract, non accessibile),
    passaggio della fonte con pagina, nota.
  - Poi due sezioni: `## Missing citations` e `## Bibliography consistency`.

Contenuti richiesti (spec §6.4):
- **`revisione-bibliografia/SKILL.md`** (`name: revisione-bibliografia`): invocabile da
  sola oppure dalla skill `revisione`.
  1. Lancia `bib`, con `--sources` sulla cartella del lavoro e `--bib` se c'è un
     `.bib`.
  2. Avvia un sub-agente nuovo con il prompt, oppure eseguilo tu leggendo solo i file
     elencati.
  3. Quando chiamata da sola, applica gli edit con `track` e scrivi un rapporto con la
     sola sezione Bibliografia.
- **`prompt-revisore-bibliografia.md`:**
  - ordine delle fonti: PDF locali (`pdftext`), poi accesso aperto online, poi
    abstract;
  - online si inviano solo titolo, autori e DOI;
  - non dichiarare mai "verificata" una citazione che non lo è;
  - per ogni giudizio, riportare il passaggio testuale della fonte con la pagina;
  - criterio "cosa richiede una citazione", preso da `## Citation needs` del profilo;
  - una voce che non si trova né in locale né online è "possibile citazione inventata
    o errata"; senza rete è "non verificabile" e va detto;
  - fonti mancanti: proporre solo fonti già presenti nella cartella o nel `.bib`,
    mai fonti non verificate;
  - senza strumenti web, dichiararlo nella nota e lavorare solo in locale.

- [ ] **Step 1: Scrivi `build_bib_draft(dir)`.** Crea `bozza-bib.docx` e `fonti/` con 2 PDF fittizi, generati con `write_pdf_from_paragraphs`:
  - `rossi2021.pdf`: "Tempi di build nelle pipeline di integrazione continua", Rossi
    M., 2021. Contiene la frase "la cache delle dipendenze riduce i tempi di build del
    30%".
  - `bianchi2020.pdf`: "Test automatici in contesti industriali", Bianchi L., 2020.

  I difetti inseriti (spec §9 caso 5):
  1. "secondo [1] la cache riduce i tempi del 60%", mentre la fonte dice 30%;
  2. la voce [3], "Neri, P. (2018). Quantum CI. doi:10.9999/fake.2018", inesistente;
  3. la voce [2] con anno 2018 invece di 2020;
  4. la frase "il 70% delle aziende italiane usa pipeline CI" senza citazione;
  5. la citazione [4] nel testo, assente in bibliografia.

  Il testo contiene anche 3 frasi sulle attività personali ("Ho configurato…",
  "Ho scritto…"), che **non** devono essere segnalate. Restituisce `expected` con le
  parole chiave per ciascuno dei 5 difetti e la lista delle 3 frasi personali.
- [ ] **Step 2: Scrivi `SKILL.md` e il prompt.** Poi esegui `pytest tests/test_skills_static.py` → PASS.
- [ ] **Step 3: Scrivi `check_bibliografia.py <workdir> <expected.json>`.** Verifica:
  - `note-bibliografia.md` menziona i 5 difetti;
  - per il difetto 1 riporta la frase della fonte con "30%";
  - nessun edit di `edits-bibliografia.json` ha un `find` contenuto in una delle 3
    frasi personali;
  - la copia revisionata contiene almeno 3 commenti.
- [ ] **Step 4: Scenario con agente** (`tests/scenari/bibliografia.md`). Lo stesso schema della Task 11 con `"Controlla la bibliografia di bozza-bib.docx"` → `check_bibliografia.py` OK. Se la rete non c'è, il difetto 2 deve risultare "non verificabile/non trovata". Correggi il prompt finché lo scenario passa.
- [ ] **Step 5: Scenario combinato.** Esegui la skill `revisione` su `bozza-bib.docx` e verifica che il rapporto unico abbia la sezione Bibliografia popolata.
- [ ] **Step 6: Commit.** `git commit -m "feat: bibliography reviewer skill and scenario"`

---

### Task 13: Documentazione e verifica finale

**Files:**
- Modify: `README.md`
- Create: `docs/uso.md`, una guida d'uso breve in italiano con:
  - come chiedere una revisione;
  - dove trovare i file prodotti;
  - come accettare o rifiutare le revisioni in Word e LibreOffice;
  - limiti noti (formattazione non tracciata, bozza solo PDF, rete).

- [ ] **Step 1: Aggiorna il README.**
  - Installazione su Claude Code:
    ```
    /plugin marketplace add madashi14/help-me-write
    /plugin install help-me-write@help-me-write
    ```
  - Installazione su Codex: secondo la documentazione verificata in Task 1.
  - Requisiti e `doctor`.
  - Cosa fa la Parte 1 e cosa arriva con la Parte 2.
- [ ] **Step 2: Verifica completa.** `pytest -v`: tutto PASS, con i test saltati elencati e motivati.
- [ ] **Step 3: Verifica del manifest.** Se disponibile, esegui `claude plugin validate .`. Altrimenti installa il plugin in locale con `--plugin-dir` e verifica che le 3 skill compaiano.
- [ ] **Step 4: Procedura per Codex (spec §9 caso 4).** Codex non è disponibile in
  questo ambiente. Scrivi `tests/scenari/codex.md` con:
  - installazione;
  - attivazione di `multi_agent` in `~/.codex/config.toml`;
  - esecuzione degli scenari `revisione` e `bibliografia` con `codex exec`;
  - uso degli stessi script `check_*.py`.

  Nel messaggio finale all'utente indica che questa verifica va fatta da lui o da un
  amico con Codex, e che fino ad allora il supporto Codex non è verificato.
- [ ] **Step 5: Commit e push.** `git commit -m "docs: usage guide and install instructions"`, poi `git push`.
