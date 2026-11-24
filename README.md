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
```

Poi installa `help-me-write` dal marketplace aggiunto.

## Verificare l'ambiente

```
python scripts/hmw.py doctor
python scripts/hmw.py doctor --json
```

`doctor` elenca versione di Python, pacchetti e strumenti esterni, e per ciò che manca
indica a cosa serve e come installarlo.
