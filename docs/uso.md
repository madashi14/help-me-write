# Guida d'uso

Il plugin ha due usi: **scrivere** un documento a partire da una cartella di lavoro (Parte 2,
sotto) e **rivedere** una bozza finita (Parte 1, dopo "Prima di cominciare").

## Scrivere un documento (help-me-write)

Apri l'assistente nella cartella del lavoro e scrivi, ad esempio, "Aiutami a scrivere la
relazione", "Completa la bozza" o "Riprendi la relazione". Nella cartella possono stare
appunti, dati, script, progetti git, notebook, archivi e una bozza: il plugin li legge
senza mai eseguirli, e non modifica mai i tuoi file.

### Le tre modalità

| Modalità | Quando | Cosa fa |
|---|---|---|
| `da-zero` | non c'è una bozza | propone la scaletta, il frontespizio, poi un capitolo alla volta |
| `bozza-parziale` | c'è una bozza con parti vuote, sezioni mancanti o troppo breve | confronta la bozza con le linee guida, propone il piano di riorganizzazione, fa una **copia di lavoro** con l'impaginazione corretta, compila il frontespizio, propone i tagli per rientrare nelle pagine, poi scrive le parti mancanti |
| `solo-revisione` | la bozza è completa | passa alla revisione (Parte 1) |

L'assistente propone la modalità e la conferma è tua. In `da-zero` ti chiede sempre
"LaTeX o Word?": è una scelta tua, qualunque sia il materiale.

### Un capitolo alla volta

Per ogni capitolo: intervista (ciò che solo tu sai: cosa è importante, il tuo contributo,
le difficoltà, i risultati con i numeri, cosa non si può pubblicare), stesura, tua
approvazione, poi il successivo. Scaletta e frontespizio vanno approvati prima. Alla fine
c'è la revisione del documento completo. Nulla è inventato: ogni fatto e ogni numero viene
da un file del materiale o da una tua risposta; ciò che manca resta
`[DA VERIFICARE: ...]` nel testo, da completare.

### Riprendere

Puoi fermarti quando vuoi. "Continua" o "riprendi la relazione" nella stessa cartella
riparte dallo stato salvato: l'assistente riassume modalità, formato e stato di ogni
capitolo, poi continua dal passo successivo senza richiederti ciò che ha già in
`.help-me-write/`. Se hai modificato a mano un file prodotto, l'assistente se ne accorge e
non lo rigenera: ogni cambiamento successivo passa da una copia con revisioni tracciate.
La cartella può passare da un computer all'altro e tra Claude Code e Codex, perché lo
stato contiene solo percorsi relativi.

### Word o LaTeX

| | Word | LaTeX |
|---|---|---|
| Uscita | `<nome>-help-me-write/<nome>.docx` | progetto in `<nome>-help-me-write/` (`main.tex`, `capitoli/`, `immagini/`) |
| Serve | LibreOffice (misura e conversione) | `latexmk` e XeLaTeX (o LuaLaTeX); `latexdiff` per le differenze |
| Bozza parziale | i tagli sono revisioni tracciate in un nuovo `.docx` | la copia di lavoro `<progetto>-help-me-write/` accanto al progetto (dentro la cartella del progetto, al primo livello, se la cartella che indichi è il progetto stesso); i tagli sono modifiche con un PDF delle differenze in `.help-me-write/revisioni/` |

Il formato di una bozza parziale si ricava dalla bozza (`.docx` o `.tex`).

### Figure

Tre tipi di figura, nessun altro: grafici disegnati dai tuoi file di dati (CSV, JSON; i
valori sono tracciati in un file `.fonte.json`), schemi a blocchi disegnati da ciò che
descrivi, immagini che hai già. Ogni figura ha numero, didascalia e un riferimento nel
testo. Il plugin non crea mai immagini fotografiche o artistiche e non usa servizi di
immagini generate. Grafici e schemi richiedono `matplotlib` (vedi `README.md`); senza
`matplotlib` il resto funziona, revisione compresa.

### La cartella `.help-me-write/`

Dentro la cartella del lavoro, contiene lo stato e i file di lavoro; puoi leggerla, e
cancellarla per ricominciare:

| File | Contenuto |
|---|---|
| `progetto.md` | stato: modalità, formato, uscita, capitoli con il loro stato (`da-fare`, `intervista-fatta`, `scritto`, `approvato`, `revisionato`); nel testo `## Decisioni` e `## Domande aperte` |
| `linee-guida.yaml` | regole lette dalle linee guida |
| `materiale.md` | sintesi, mappa del materiale, cronologia, dati e numeri, note dell'autore, cosa non è stato letto, lacune |
| `layout.json` | margini, interlinea e righe/caratteri per pagina calcolati dalle regole |
| `indice.md`, `indice.json` | scaletta approvata |
| `capitoli/`, `manifest.yaml` | sorgenti dei capitoli e manifesto (Word) |
| `revisioni/<data-ora>/` | rapporti di revisione e proposte di tagli (`tagli.md`) |
| `misure/`, `pdf/` | misure e PDF di prova |

I percorsi scritti nello stato sono relativi alla cartella del lavoro.

## Prima di cominciare

1. Installa il plugin e le dipendenze Python come nel `README.md`:
   `python -m pip install "python-docx>=1.2" lxml pdfplumber PyYAML "bibtexparser>=1.4,<2" "matplotlib>=3.7"`
   (con l'errore `externally-managed-environment`, in un ambiente virtuale creato con
   `python -m venv`).
2. Controlla l'ambiente: chiedi all'assistente "Esegui il controllo dell'ambiente di
   help-me-write (doctor)". Dice cosa manca (pacchetti Python, LibreOffice per Word,
   `latexmk` e `latexdiff` per LaTeX) e il comando per installarlo; `matplotlib` è
   elencato a parte, come facoltativo (solo grafici e schemi). Le skill lo eseguono
   comunque all'inizio di ogni revisione.
3. Metti la bozza in una cartella di lavoro. Le fonti della bibliografia (PDF) possono
   stare nella stessa cartella o in sue sottocartelle. Aggiungi le linee guida
   (facsimile, regolamento) se le hai.

## Come chiedere una revisione (Parte 1)

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

I file vengono creati accanto all'originale, che non viene mai modificato. Un file già
esistente non viene mai sovrascritto: se un nome è già usato (ad esempio la copia di una
revisione precedente, su cui magari hai già accettato o rifiutato delle modifiche) si
aggiunge `-2`, `-3`, ...

| Bozza | Prodotti |
|---|---|
| `bozza.docx` | `bozza-revisionato.docx` (revisioni tracciate e commenti); `bozza-revisionato-formattato.docx` (impaginazione corretta) |
| `.tex` nella cartella `bozza` | accanto alla cartella `bozza`: la cartella `bozza-revisionato/` e `bozza-differenze.pdf` (differenze evidenziate) |
| `.pdf` | solo il rapporto |

Il rapporto è `.help-me-write/revisioni/<AAAA-MM-GG-HHMMSS>/rapporto.md`: riepilogo, modifiche
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

Il revisore della bibliografia legge le tue fonti in locale: i PDF nella cartella di
lavoro e nelle sue sottocartelle. Non usa mai come fonte la bozza stessa: il PDF esportato
della bozza (`bozza.pdf`), le copie `-revisionato` e `-formattato`, i PDF `-differenze` e
le cartelle `-revisionato`, né ciò che help-me-write ha scritto (le cartelle
`-help-me-write` e i loro PDF). Online usa la ricerca e la lettura di pagine solo se
l'ambiente le offre, e invia solo titoli, autori e DOI, mai il testo della bozza. Senza
rete le citazioni che non può controllare sono segnate "non verificabile". Non inserisce
mai fonti che non ha verificato.

## Limiti noti

- Le correzioni di formattazione (font, corpo, margini, interlinea) sono applicate nella
  copia separata `-formattato`, non come revisioni tracciate.
- Una bozza solo in PDF riceve solo il rapporto, con le correzioni proposte da fare a mano.
- Una modifica a un testo dentro una casella di testo (ad esempio il frontespizio)
  cambia solo la versione moderna della casella.
- Una correzione che cade su un collegamento o su un campo (ad esempio una citazione
  Zotero) non viene applicata: compare tra le correzioni da fare a mano.
- Il ciclo di risposte è al massimo di 2 giri, e non è ancora stato provato da uno
  scenario automatico (gli scenari provano la prima revisione).
- I titoli delle sezioni si leggono da dove sono più affidabili: dagli stili Titolo di un
  .docx, da `\chapter`, `\section` e `\subsection` dei sorgenti .tex (seguendo `\input`
  e `\include`, con indice, elenchi delle figure e delle tabelle e bibliografia generati
  da LaTeX, anche una `thebibliography` scritta a mano) o dai
  segnalibri di un PDF. Un PDF senza segnalibri non ha titoli leggibili: il rapporto segna
  le sezioni "non determinabile", da verificare a mano.
- Un titolo scritto come testo normale (ad esempio in grassetto) invece che con uno stile
  Titolo (o in LaTeX come testo normale invece che con `\chapter` o `\section`, o in un
  PDF fuori dai segnalibri) viene trovato, ma la lunghezza della sua sezione non si può
  misurare: il rapporto suggerisce di applicare lo stile.
- Le righe per pagina si misurano sulle pagine piene, dove un titolo o una didascalia
  contano per le righe che occupano: sono escluse le pagine che finiscono prima o hanno
  una figura senza didascalia, e l'ultima. I caratteri per riga si misurano su ogni pagina
  con almeno 5 righe piene di prosa, se non sono meno delle altre sue righe piene (voci
  dell'indice, righe di una tabella); l'indice e la bibliografia sono saltati.
  Il frontespizio è sempre escluso, e il rapporto dice quali pagine non ha valutato e
  perché.
- Il supporto Codex non è ancora verificato su un'installazione reale
  (`tests/scenari/codex.md`): resta da verificare, anche per la Parte 2.
- Word non è stato provato direttamente: sono stati verificati il passaggio da
  LibreOffice e la validità OOXML dei file.
- Nei documenti Word le formule sono scritte come testo semplice, non come equazioni di Word.
- Il frontespizio di un modello Word ha la sua intestazione, che non compare nelle pagine di
  testo (`titlePg`): l'intestazione del facsimile porta un numero di pagina, quindi le
  pagine di testo hanno l'intestazione vuota.
- In una bozza Word parziale il comando di revisione sostituisce testo dentro i paragrafi
  ma non inserisce capitoli: i capitoli nuovi arrivano in un documento a parte,
  `<nome>-capitoli-nuovi.docx`, da incollare nel tuo.
- Gli scenari `da-zero-word` e `ripresa` sono scritti ma non ancora eseguiti. Della Parte
  2 la prova su una bozza LaTeX reale, `tests/scenari/bozza-parziale.md`, è stata
  eseguita una volta: "Esecuzione 1" in fondo al file (8 controlli su 8 dal lato
  dell'assistente).
- `material` legge anche i repository git annidati nella cartella (`git_repos`) e ne
  riassume la storia; senza `git` la storia viene omessa.
