# help-me-write

Plugin per Claude Code e OpenAI Codex che rivede e aiuta a scrivere documenti formali
(relazioni di tirocinio, articoli): controlla linee guida, impaginazione e bibliografia e
propone le correzioni come revisioni tracciate, senza mai modificare l'originale.

## Requisiti

- Python 3.10 o superiore
- Dipendenze Python: `pip install -r requirements.txt`
  (su Python di sistema Debian/Ubuntu, `bibtexparser` può richiedere `pip install --use-pep517 bibtexparser`)
- Opzionali: LibreOffice (conversione in PDF e misura dell'impaginazione), `latexmk` e
  `latexdiff` (documenti LaTeX). Si installano da https://www.libreoffice.org/download/ e
  https://tug.org/texlive/.

## Installazione

### Claude Code

```
/plugin marketplace add madashi14/help-me-write
/plugin install help-me-write@help-me-write
```

### Codex

```
codex plugin marketplace add madashi14/help-me-write
codex plugin add help-me-write@help-me-write
```

In alternativa, dentro Codex, il comando `/plugins` apre il browser dei plugin, raggruppati
per marketplace. Comandi secondo la documentazione di Codex
(https://developers.openai.com/codex/cli/reference e
https://developers.openai.com/codex/plugins); se la tua versione di Codex li chiama in
modo diverso, controlla `codex plugin --help`.

Il supporto Codex non è ancora verificato su un'installazione reale: la procedura di
prova è in `tests/scenari/codex.md`.

## Verificare l'ambiente

```
python scripts/hmw.py doctor
python scripts/hmw.py doctor --json
```

`doctor` elenca versione di Python, pacchetti e strumenti esterni, e per ciò che manca
indica a cosa serve e come installarlo.

Per Word serve LibreOffice (misura dell'impaginazione e copia formattata); per LaTeX
servono `latexmk` e `latexdiff`.

## Permessi

Le skill eseguono comandi `python .../scripts/hmw.py ...`. In Claude Code ti viene chiesto di
consentirli: puoi consentire i comandi `python` per la sessione. Nelle esecuzioni
automatiche (headless) servono `--allowedTools "Bash(python:*) Bash(python3:*)"`. Ogni
comando viene eseguito da solo, non concatenato con `&&` o `;`, perché le liste di
permessi restrittive rifiutano i comandi concatenati.

## Cosa fa la Parte 1

Si usa chiedendo all'assistente, in italiano o nella tua lingua, ad esempio "Rivedi
bozza.docx".

- `linee-guida`: legge le linee guida del documento (facsimile, regolamento, istruzioni
  agli autori) e le salva in `.help-me-write/linee-guida.yaml`.
- `revisione`: rivede una bozza finita (`.docx`, `.tex` o `.pdf`). Produce
  `<nome>-revisionato.docx` con correzioni tracciate e commenti, la copia
  `<nome>-revisionato-formattato.docx` con l'impaginazione corretta, per LaTeX la cartella
  `<nome>-revisionato/` e `<nome>-differenze.pdf`, e il rapporto in
  `.help-me-write/revisioni/<data-ora>/rapporto.md`. L'originale non viene mai modificato.
- `revisione-bibliografia`: controlla citazioni, fonti e bibliografia (citazioni non
  supportate dalla fonte, voci inventate o errate, affermazioni senza citazione), con
  commenti in Word. Parte anche dentro `revisione`. Online invia solo titoli, autori e
  DOI, mai il testo; non inserisce mai fonti non verificate.

Guida d'uso e limiti noti: `docs/uso.md`.

## Cosa arriverà con la Parte 2

Il flusso di scrittura a partire da una cartella di lavoro: analisi del materiale, scelta
tra LaTeX e Word, scaletta e frontespizio, interviste capitolo per capitolo, stesura e
figure. Non è ancora disponibile.

## Comandi

`python scripts/hmw.py <comando>`: `doctor`, `extract`, `rules`, `layout`, `format`,
`measure`, `track`, `texdiff`, `bib`, `pdftext`. Con `--json` l'output è JSON.
