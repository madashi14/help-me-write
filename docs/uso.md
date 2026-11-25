# Guida d'uso (Parte 1: revisione)

## Prima di cominciare

1. Installa il plugin e le dipendenze come nel `README.md`.
2. Controlla l'ambiente: `python scripts/hmw.py doctor` dice cosa manca (LibreOffice per
   Word, `latexmk` e `latexdiff` per LaTeX).
3. Metti la bozza in una cartella di lavoro. Le fonti della bibliografia (PDF) possono
   stare nella stessa cartella o in sue sottocartelle. Aggiungi le linee guida
   (facsimile, regolamento) se le hai.

## Come chiedere una revisione

Apri l'assistente nella cartella del lavoro e scrivi, ad esempio:

- "Rivedi bozza.docx"
- "Controlla la bibliografia di bozza.docx"
- "Review my draft"

Cosa ti viene chiesto:

- se esiste già `.help-me-write/linee-guida.yaml`, se è ancora valido; altrimenti
  quale documento contiene le linee guida e la conferma delle regole lette;
- il font da usare per la copia formattata, se l'impaginazione non è a norma;
- il file da rivedere, se nella cartella ce n'è più d'uno.

Le conferme date già nella richiesta ("le linee guida sono ancora valide", "usa Times New
Roman") non vengono richieste di nuovo. In Claude Code ti viene chiesto di consentire i
comandi `python`: puoi consentirli per la sessione.

## Dove trovare i file prodotti

I file vengono creati accanto all'originale, che non viene mai modificato. Se un nome è
già usato si aggiunge `-2`, `-3`, ...

| Bozza | Prodotti |
|---|---|
| `bozza.docx` | `bozza-revisionato.docx` (revisioni tracciate e commenti); `bozza-revisionato-formattato.docx` (impaginazione corretta) |
| `.tex` nella cartella `bozza` | cartella `bozza-revisionato/`; `bozza-differenze.pdf` (differenze evidenziate) |
| `.pdf` | solo il rapporto |

Il rapporto è `.help-me-write/revisioni/<AAAA-MM-GG-HHMM>/rapporto.md`: riepilogo, modifiche
fatte, controlli di forma prima e dopo, sezione bibliografia, correzioni da fare a mano e
domande per te. Nella stessa cartella ci sono i file di lavoro (`extract.json`,
`measure.json`, le note dei revisori).

## Accettare o rifiutare le revisioni

- **Word**: scheda Revisione, "Accetta" o "Rifiuta" su ogni modifica, oppure "Accetta
  tutte le modifiche". I commenti si leggono nel pannello Revisioni e si eliminano con
  "Elimina".
- **LibreOffice Writer**: menu Modifica, Modifiche, "Gestisci...": seleziona una modifica
  e scegli Accetta o Rifiuta, oppure "Accetta tutto". I commenti sono nel margine.
- **LaTeX**: le modifiche sono già nei sorgenti della cartella `-revisionato`; il PDF
  delle differenze mostra cosa è cambiato. I commenti non vengono scritti nei sorgenti:
  stanno nel rapporto, con file e riga.

Autore delle revisioni e dei commenti: `help-me-write` (iniziali `HMW`).

## Le domande e il secondo giro

Ciò che l'assistente non può correggere da solo, senza inventare, diventa una domanda nel
rapporto (ad esempio il tuo contributo personale, il significato di una sigla, dove citare
una figura). Se rispondi, l'assistente applica le risposte alla copia più recente e
misura di nuovo. Il ciclo di risposte è al massimo di 2 giri; poi decidi tu.

## Bibliografia e rete

Il revisore della bibliografia legge le tue fonti in locale. Online usa la ricerca e la
lettura di pagine solo se l'ambiente le offre, e invia solo titoli, autori e DOI, mai il
testo della bozza. Senza rete le citazioni che non può controllare sono segnate "non
verificabile". Non inserisce mai fonti che non ha verificato.

## Limiti noti

- Le correzioni di formattazione (font, corpo, margini, interlinea) sono applicate nella
  copia separata `-formattato`, non come revisioni tracciate.
- Una bozza solo in PDF riceve solo il rapporto, con le correzioni proposte da fare a mano.
- Una modifica a un testo dentro una casella di testo (ad esempio il frontespizio)
  cambia solo la versione moderna della casella.
- Una correzione che cade su un collegamento o su un campo (ad esempio una citazione
  Zotero) non viene applicata: compare tra le correzioni da fare a mano.
- Il ciclo di risposte è al massimo di 2 giri.
- Il supporto Codex non è ancora verificato su un'installazione reale
  (`tests/scenari/codex.md`).
- Word non è stato provato direttamente: sono stati verificati il passaggio da
  LibreOffice e la validità OOXML dei file.
- La Parte 2 (scrittura guidata da una cartella di lavoro) non è ancora disponibile.
