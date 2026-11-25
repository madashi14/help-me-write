# Scenario: verifica su Codex (spec §9 caso 4)

Codex non era disponibile dove è stato costruito il plugin: il supporto Codex **non è
verificato** finché questa procedura non viene eseguita da chi ha Codex. Esegue gli
stessi scenari `revisione` e `bibliografia` con `codex exec`, e gli stessi script
`check_*.py`. Servono Python >= 3.10 con `pip install -r requirements.txt`, LibreOffice,
e questo repository clonato (`<repo>` = percorso assoluto).

## 1. Installazione del plugin

Comandi secondo https://developers.openai.com/codex/cli/reference e
https://developers.openai.com/codex/plugins. Per l'ultima versione:

```
codex plugin marketplace add madashi14/help-me-write
codex plugin add help-me-write@help-me-write
```

Se un comando non esiste nella tua versione, guarda `codex plugin --help` o usa `/plugins`
dentro Codex. Per provare invece la copia isolata degli scenari (punto 3), aggiungi come
marketplace la cartella locale `<tmp>/plugin`:
`codex plugin marketplace add <tmp>/plugin` e poi `codex plugin add help-me-write@help-me-write`.

## 2. Sub-agenti (`multi_agent`)

Le skill chiedono di avviare un revisore indipendente come sub-agente. Secondo la
documentazione (https://developers.openai.com/codex/multi-agent/ e
https://developers.openai.com/codex/config-basic) la funzione è attiva di default; se
l'hai disattivata, in `~/.codex/config.toml`:

```toml
[features]
multi_agent = true

[agents]
enabled = true
```

Annota nei risultati se i sub-agenti hanno funzionato. Se non possono essere avviati, le
skill dicono di fare la revisione da soli: anche questo va annotato.

## 3. Scenario `revisione`

Crea una cartella temporanea nuova e vuota `<tmp>`, poi:

```
python <repo>/tests/scenari/check_revisione.py --setup <tmp>/lavoro <tmp>/expected.json <tmp>/plugin
```

Da `<tmp>/lavoro`, con il plugin installato (punto 1):

```
codex exec --sandbox workspace-write -C <tmp>/lavoro --json "Rivedi bozza.docx. Le linee guida in .help-me-write/linee-guida.yaml sono ancora valide, non serve rifarle. Per la copia formattata usa Times New Roman. Ora non rispondo alle domande sul contenuto: lasciale nel rapporto." > <tmp>/transcript.jsonl
```

Se Codex rifiuta i comandi `python` o le scritture, controlla la sandbox e le regole di
approvazione (`codex exec --help`); l'agente non deve poter leggere `<repo>/tests`.
Poi:

```
python <repo>/tests/scenari/check_revisione.py <tmp>/lavoro <tmp>/expected.json
```

Atteso: 22/22 (vedi `revisione.md`).

## 4. Scenario `bibliografia`

Una nuova `<tmp>`:

```
python <repo>/tests/scenari/check_bibliografia.py --setup <tmp>/lavoro <tmp>/expected.json <tmp>/plugin
```

Da `<tmp>/lavoro`, la skill da sola:

```
codex exec --sandbox workspace-write -C <tmp>/lavoro --json "Controlla la bibliografia di bozza-bib.docx. Ora non rispondo a domande: lasciale nel rapporto." > <tmp>/transcript.jsonl
```

```
python <repo>/tests/scenari/check_bibliografia.py <tmp>/lavoro <tmp>/expected.json
```

Atteso: 19/19. Per la prova combinata, una nuova `<tmp>` con lo stesso setup, il prompt
"Rivedi bozza-bib.docx. Le linee guida in .help-me-write/linee-guida.yaml sono ancora
valide, non serve rifarle. Per la copia formattata usa Times New Roman. Ora non rispondo
alle domande sul contenuto: lasciale nel rapporto." e il check con `--combined`
(atteso 20/20). Senza ricerca web, [3] deve risultare "non verificabile" e la prima riga
delle note deve dirlo.

## 5. Cosa riportare

Per ogni scenario: versione di Codex, esito di ogni controllo, se i sub-agenti sono stati
usati, comandi rifiutati dalla sandbox, e le differenze rispetto a Claude Code. Finché non
c'è un esito, il supporto Codex resta "non verificato".
