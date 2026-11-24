# Scriba — documento di progetto

*Data: 24 novembre 2026 · Nome provvisorio: "scriba"*

Legenda: le decisioni prese dall'utente sono indicate come **[deciso]**. Le scelte
proposte da Claude e non ancora confermate esplicitamente sono indicate come
**[proposta]**. Sono correggibili in fase di revisione del documento.

---

## 1. Intento e perché

Un plugin per **Claude Code** e **OpenAI Codex** che, partendo da una cartella con il
lavoro di una persona (sviluppo software, studio di ricerca, pratica legale…),
accompagna fino al **documento formale finito**: relazione, report, paper, atto.
Rispetta le linee guida richieste (struttura, lunghezza, formato, frontespizio).

Il bisogno concreto da cui nasce: l'utente deve scrivere la **relazione di fine
tirocinio curriculare** (Scuola di Ingegneria, Università di Bologna). Quella relazione
è il **primo caso reale e il banco di prova** del plugin. Il plugin però resta generale:
la relazione di tirocinio è il primo tipo di documento supportato bene, non l'unico.

Alcuni amici dell'utente usano Codex: per questo il plugin deve funzionare anche lì
**[deciso]**.

Risultato atteso:
- per l'utente, la propria relazione completa, nel formato richiesto e rivista;
- in più, uno strumento riusabile e condivisibile.

## 2. Obiettivi

### 2.1 Tre modalità d'uso [deciso]

1. **Da zero.** Il plugin legge la cartella del lavoro e guida tutto il flusso (§4),
   dalla comprensione del materiale al documento rivisto.
2. **Bozza parziale.** Nella cartella c'è già del testo. Il plugin lo confronta con le
   linee guida, propone una riorganizzazione, conserva ciò che va bene e completa il
   resto riprendendo il flusso dalla struttura (§4, fase 5).
3. **Solo revisione.** Il documento è già scritto per intero. Il plugin lo rivede e
   consegna le correzioni (§6).

### 2.2 Altri obiettivi

- **Formato:** chiedere sempre all'utente se procedere in **LaTeX o Word** **[deciso]**.
  Fa eccezione la modalità "solo revisione", in cui il formato si ricava dal file della
  bozza **[proposta]**.
- **Ripresa del lavoro:** interrompere e riprendere il lavoro tra sessioni diverse,
  anche passando da Codex a Claude e viceversa, grazie a un file di stato nella
  cartella **[proposta]**.
- **Lingua:** interagire nella lingua dell'utente e scrivere il documento nella lingua
  del documento. Il primo caso di test è in italiano **[proposta]**.

## 3. Non-obiettivi e anti-obiettivi

### 3.1 Non-obiettivi della prima versione [proposta]

- **Illustrazioni generate con l'AI** (immagini fotografiche o artistiche): servirebbe
  un servizio esterno a pagamento con chiave API. Le figure generate dal plugin sono
  solo schemi, diagrammi e grafici prodotti con codice. L'utente non ha obiettato.
- **Formati diversi da Word (.docx) e LaTeX:** niente Google Docs, Markdown come
  output finale, Typst.
- **Profili dedicati a paper scientifico e atto giudiziario.** Nella prima versione
  questi tipi funzionano tramite il **profilo generico** (§5.3), con le regole prese dal
  bando, dal regolamento o dalle risposte dell'utente. Il profilo dedicato per
  l'atto giudiziario arriva in seguito (ad es. con i limiti del DM 110/2023 per gli
  atti civili).
- **Antiplagio**, firme e rilegatura (aspetti fisici o burocratici).
- **Gestione bibliografica avanzata.** Basta una bibliografia corretta: BibTeX/biblatex
  in LaTeX, elenco formattato in Word.

### 3.2 Anti-obiettivi

Sono fallimenti anche se il plugin "funziona".

- **Inventare.** Il plugin non inventa fatti, numeri, risultati, citazioni o il
  contributo personale dell'utente. Ogni affermazione deve venire dal materiale della
  cartella o dalle risposte dell'utente. Ciò che manca si **chiede**. Se resta un
  buco, nel testo va un segnaposto visibile (es. `[DA VERIFICARE: …]`), che il
  revisore segnala.
- **Saltare il dialogo.** Il plugin non scrive capitoli senza aver fatto l'intervista e
  non procede senza l'approvazione di indice e frontespizio.
- **Violare le linee guida in silenzio.** Esempio concreto: Times 12 con margini
  standard dà circa 85 caratteri per riga, contro i 60–70 richiesti.
- **Perdere testo dell'utente.** Il plugin non sovrascrive mai i file originali né le
  modifiche fatte a mano dall'utente (§7.3).
- **Prosa generica "da AI".** Tono e forma devono essere quelli del tipo di documento:
  per la relazione Unibo un "diario" cronologico che metta in evidenza il contributo
  personale, non una presentazione.
- **Far trapelare informazioni riservate dell'azienda ospitante.** Il revisore segnala
  credenziali, dati di clienti e codice proprietario copiato per intero **[proposta]**.

## 4. Il flusso (modalità "da zero")

Le fasi sono quelle indicate dall'utente **[deciso]**; i dettagli sotto ogni fase sono
**[proposta]** salvo dove indicato.

1. **Lettura della cartella.** Il plugin capisce di che lavoro si tratta e produce una
   "mappa del materiale": cosa c'è, cosa è stato fatto, quali fonti esistono per cosa.
   Ricostruisce anche la **cronologia** dalle date disponibili: storia git, date dei
   file, diari, verbali. Se non ci sono date, chiede la linea del tempo all'utente.
   Le cartelle grandi (es. un repository con migliaia di file) vanno esplorate a
   campione e riassunte nel file di stato, senza caricarle tutte nel contesto.
2. **Tipo di documento.** Il plugin propone il tipo (relazione di tirocinio, report
   tecnico, paper, atto…) e l'utente lo conferma.
3. **Linee guida.** Il plugin estrae le regole da un regolamento o da un modello
   presente nella cartella o fornito dall'utente (es. il facsimile Unibo), oppure le
   chiede. Poi le riassume in una scheda che l'utente conferma (esempio in §9). Le
   regole misurabili vengono **tradotte in impostazioni concrete**: righe per pagina
   e caratteri per riga diventano margini, interlinea e larghezza del testo, in base
   al font (§7.2).
4. **LaTeX o Word:** il plugin lo chiede sempre **[deciso]**.
5. **Indice e frontespizio.** Il plugin propone l'indice e lo fa approvare **[deciso]**.
   Il frontespizio va approvato anch'esso. Se le linee guida includono un **modello di
   frontespizio**, il plugin compila quello invece di ricrearlo. In LaTeX lo riproduce
   fedelmente.
6. **Intervista per capitolo** **[deciso]**: un capitolo alla volta, il plugin chiede:
   - i punti salienti;
   - cosa ha fatto personalmente l'utente;
   - difficoltà e risultati, con i numeri;
   - le **immagini**: quali esistono già (percorso del file), quali generare (che
     schema o grafico), quali non servono.

   Le domande partono dalla mappa del materiale e sono specifiche, mai generiche.
7. **Scrittura del capitolo**, subito dopo la sua intervista **[deciso]**.
   - Il capitolo viene mostrato all'utente, che può chiedere modifiche prima di
     passare al successivo.
   - *Ordine* **[proposta]**: prima il corpo, poi introduzione e conclusione, che lo
     riassumono.
8. **Revisione finale** con un revisore indipendente **[deciso]** (§6). Le domande
   aperte tornano all'utente, si correggono e si rimisura.

**Formati di bozza accettati** **[proposta]**: `.docx` e `.tex`, con revisioni sul
file; `.md` e `.txt`, convertiti nel formato scelto. Una bozza solo in PDF riceve
soltanto il rapporto, senza modifiche tracciate.

La modalità **bozza parziale** esegue le fasi 1–4 (il formato è quello della bozza),
confronta la bozza con le linee guida, propone indice e riorganizzazione, poi segue
le fasi 5–8 solo dove serve. La modalità **solo revisione** salta direttamente alla §6,
previa acquisizione delle linee guida (fase 3).

## 5. Approcci e architettura

### 5.1 Approcci considerati

| Approccio | Pro | Contro |
|---|---|---|
| **A. Un'unica skill** con tutto il flusso e file di supporto | Installazione minima; portabile ovunque, anche su claude.ai | Le istruzioni lunghe vengono seguite peggio (fasi saltate); "solo revisione" e ripresa diventano casi particolari; revisore non indipendente; servono comunque script per revisioni e misure |
| **B. Una skill per fase, più file di stato e script di controllo** | Ogni fase si invoca da sola; ripresa affidabile; misure esatte; revisore indipendente; estendibile con nuovi profili | Più file da costruire e testare; dipendenze locali (Python, LibreOffice, LaTeX) |
| *Scartato:* app autonoma su API | — | Non è un plugin dentro Claude e Codex |
| *Scartato:* B senza script | Nessuna dipendenza | Revisioni Word accettabili/rifiutabili e conteggio di righe e caratteri non affidabili con le sole istruzioni |

**Scelto: B** **[deciso]**. È l'unico approccio che regge tutti i requisiti: tre modalità,
revisioni sul file, misure esatte, due piattaforme.

### 5.2 Struttura del plugin [proposta]

Il riferimento è la struttura multi-piattaforma del plugin Superpowers: una cartella
`skills/` condivisa e un manifest per ogni piattaforma.

```
scriba/
  .claude-plugin/plugin.json        # manifest Claude Code
  .claude-plugin/marketplace.json   # per installare da GitHub in Claude Code
  .codex-plugin/plugin.json         # manifest Codex (verificare il formato corrente)
  agents/revisore.md                # sub-agente revisore (Claude Code)
  skills/
    scriba/                 # ingresso: rileva modalità e stato, orchestra le fasi
    analisi-materiale/      # fase 1
    linee-guida/            # fasi 2–4 (tipo, regole, formato)
    struttura/              # fase 5 (indice + frontespizio)
    intervista-capitolo/    # fase 6
    scrittura-capitolo/     # fase 7
    figure/                 # schemi/grafici generati + inserimento immagini esistenti
    revisione/              # §6, invocabile anche da sola
  profili/                  # un file per tipo di documento (§5.3)
  scripts/                  # Python, multipiattaforma (§7)
  tests/
```

- Ogni `SKILL.md` ha `name` e `description` (formato comune a Claude e Codex).
- Le skill di base non devono dipendere da strumenti presenti su una sola piattaforma,
  come la skill docx di Claude o lo strumento di domande strutturate di Claude Code.
  Le istruzioni dicono "chiedi all'utente" e lasciano l'ospite libero di usare lo
  strumento migliore che ha.
- Gli script devono essere raggiungibili dalle skill su entrambe le piattaforme; il
  modo di risolvere i percorsi è lasciato al costruttore.

### 5.3 Profili dei tipi di documento [proposta]

Un profilo è un file che descrive un tipo di documento:
- come riconoscerlo;
- la struttura tipica;
- le linee guida predefinite (quando non ne vengono fornite);
- le domande guida per l'intervista;
- il tono;
- la **checklist di contenuto** per il revisore.

Prima versione:
- `relazione-tirocinio`: completo e collaudato sul caso Unibo;
- `generico`: tutte le regole arrivano dalle linee guida o dall'utente; copre paper,
  report e atti finché non avranno un profilo dedicato.

Il formato del profilo va documentato, così aggiungerne uno significa scrivere un
solo file.

## 6. Revisione

### 6.1 Cosa controlla [proposta, salvo dove indicato]

**Forma, con misure automatiche (§7.2):**
- numero di pagine;
- righe per pagina e caratteri per riga;
- font e dimensione;
- numerazione delle pagine;
- presenza e ordine delle sezioni obbligatorie (es. frontespizio, indice,
  introduzione, corpo, conclusione);
- lunghezza delle sezioni vincolate (es. introduzione e conclusione di 1–2 pagine).

**Lingua:**
- ortografia e grammatica;
- coerenza dei termini;
- acronimi definiti al primo uso;
- numerazione di figure e tabelle, didascalie, riferimenti nel testo;
- citazioni e bibliografia.

**Contenuto**, con la checklist del profilo. Per la relazione di tirocinio:
- il contributo personale emerge chiaramente;
- il testo è un diario cronologico o di sviluppo, non una presentazione;
- obiettivi, attività e risultati sono coerenti tra introduzione, corpo e conclusione;
- non ci sono informazioni riservate;
- non restano segnaposto `[DA VERIFICARE]`.

### 6.2 Come consegna le correzioni [deciso: opzione B]

- **Word:** una **copia** del documento con le correzioni come **revisioni**
  (inserimenti e cancellazioni tracciati, autore "Scriba"), che l'utente accetta o
  rifiuta in Word o LibreOffice. Il file originale non viene mai toccato.
- **LaTeX:** una copia corretta dei sorgenti più un **PDF delle differenze** (tipo
  `latexdiff`) che evidenzia in colore cosa è cambiato.
- In entrambi i casi un **breve rapporto** che riporta:
  - cosa è stato corretto;
  - cosa non rispetta le regole misurabili, con le impostazioni esatte per
    sistemarlo;
  - le **domande sul contenuto** che il revisore non può risolvere da solo (es. "nel
    cap. 3 non emerge il tuo contributo: cosa hai fatto tu?").
- *Correzioni di formattazione* (margini, font, interlinea) **[proposta]**: vanno
  tracciate come revisioni se fattibile in modo affidabile; altrimenti applicate in
  una copia separata ed elencate nel rapporto. Ogni modifica al testo invece deve
  essere sempre visibile e rifiutabile.

### 6.3 Indipendenza [proposta]

Il revisore lavora solo su documento, linee guida e checklist, **senza** la
conversazione in cui il testo è stato scritto.
- **Claude Code:** sub-agente `agents/revisore.md`.
- **Codex:** sub-agente se gli agenti multipli sono attivi; altrimenti passata di
  revisione nella stessa sessione, rileggendo tutto dai file e seguendo la checklist
  alla lettera.

Ciclo dopo la revisione:
1. l'utente risponde alle domande;
2. il plugin applica le correzioni;
3. il plugin rimisura.

Al massimo due cicli automatici, poi la decisione passa all'utente.

## 7. Componenti tecnici [proposta]

### 7.1 File di stato

Cartella `.scriba/` dentro la cartella del lavoro, leggibile e modificabile da
entrambe le piattaforme (Markdown, con eventuale intestazione YAML):

- `progetto.md`:
  - modalità e tipo di documento;
  - formato;
  - linee guida estratte, con la fonte;
  - impostazioni di impaginazione calcolate;
  - indice approvato;
  - stato di ogni capitolo (da fare → intervista fatta → scritto → approvato →
    revisionato);
  - decisioni prese e domande aperte.
- `materiale.md`: mappa del materiale e cronologia.
- `capitoli/`: note delle interviste e, per Word, il testo sorgente dei capitoli.
- `revisioni/`: i rapporti di revisione.

Il documento finale va in una cartella di output proposta all'inizio e confermata
dall'utente.

### 7.2 Script (Python, Windows/macOS/Linux)

- **`doctor`:** verifica le dipendenze e dice esattamente cosa manca e come
  installarlo:
  - Python;
  - LibreOffice, per impaginare e misurare i file Word;
  - una distribuzione LaTeX con `latexmk` e `latexdiff`, solo per chi sceglie LaTeX;
  - gli strumenti per i diagrammi.

  Il plugin lo lancia all'avvio.
- **Calcolo impaginazione:** dato font, dimensione, righe per pagina e caratteri per
  riga richiesti, calcola margini, interlinea e larghezza del testo.
- **Misura:** impagina il documento in PDF (Word tramite LibreOffice, LaTeX tramite
  `latexmk`) e misura:
  - pagine;
  - righe per pagina (solo pagine di testo pieno, escluse quelle iniziali);
  - caratteri per riga;
  - font;
  - numerazione.

  Restituisce esito per ogni regola e scostamento.
- **Frontespizio:** compila il modello `.docx` fornito con i dati dell'utente. Per
  LaTeX ne produce l'equivalente.
- **Assemblaggio Word:** dai sorgenti dei capitoli al `.docx`, con:
  - stili coerenti con le impostazioni calcolate;
  - indice automatico e numeri di pagina;
  - didascalie, note, figure;
  - frontespizio in testa.
- **Revisioni Word:** applica le correzioni come modifiche tracciate.
- **Differenze LaTeX:** produce il PDF delle differenze.

### 7.3 Protezione delle modifiche manuali

Se l'utente ha modificato a mano il `.docx` o i `.tex` dopo l'ultima generazione
(rilevabile ad esempio con un'impronta salvata nel file di stato), il plugin **non
rigenera** il file. Passa invece alle correzioni tracciate (§6.2).

### 7.4 Figure

- **Grafici:** generati con matplotlib.
- **Schemi e diagrammi:** strumento a scelta del costruttore (es. Graphviz, Mermaid,
  TikZ solo in LaTeX), con preferenza per ciò che funziona su entrambe le
  piattaforme e con meno dipendenze.
- **Immagini dell'utente** (screenshot, foto): inserite dal percorso indicato.
- Ogni figura ha numero, didascalia e un riferimento nel testo.

## 8. Vincoli

- **Piattaforme:** Claude Code (terminale e app desktop) e OpenAI Codex (CLI, app,
  estensione IDE). Il costruttore deve verificare sulla documentazione corrente il
  formato del manifest Codex e il meccanismo di installazione. Il formato `SKILL.md`
  è condiviso; i sub-agenti di Codex richiedono la funzione "multi-agent" attivata
  dall'utente.
- **Dipendenze locali:** Python, LibreOffice (gratuito) e, solo per LaTeX, una
  distribuzione TeX. Il sistema operativo di utente e amici è ignoto, quindi tutto
  deve essere multipiattaforma.
- **Font equivalenti:** dove un font richiesto non esiste (es. Helvetica su Windows), si
  usa l'equivalente metrico (Arial / TeX Gyre Heros) e lo si dichiara nella scheda
  delle linee guida **[proposta]**.
- **Distribuzione:** un repository GitHub da cui installare il plugin in Claude Code e
  in Codex. Account e visibilità (pubblico o privato) si decidono nel piano.
- **Privacy:** il materiale resta sul computer dell'utente. Il plugin non invia nulla a
  servizi esterni oltre a quanto fa già l'agente stesso.
- **Contesto limitato del modello:** materiale e documento vanno gestiti a pezzi
  (mappa del materiale, un capitolo alla volta), con lo stato su file.

## 9. Caso di prova e criteri di accettazione

**Linee guida di riferimento:** il facsimile Unibo, salvato in
`docs/riferimenti/Facsimile_relazione_di_fine_tirocinio.docx`. Scheda attesa:

```
Tipo:        Relazione di fine tirocinio curriculare (Ingegneria, Unibo)
Lunghezza:   10–30 pagine
Struttura:   frontespizio (modello fisso, pag. 2 del facsimile) · indice
             · introduzione (1–2 pp) · corpo (ordine cronologico o di sviluppo)
             · conclusione (1–2 pp) · allegati (facoltativi)
Formato:     Times New Roman / Courier / Helvetica 12
             30–35 righe per pagina, 60–70 caratteri per riga, pagine numerate
Contenuto:   forma di diario; evidenziare contributo personale e originalità
Immagini:    schemi, schizzi e disegni ammessi
```

**Criteri di accettazione:**

1. **Da zero, sulla cartella reale del tirocinio dell'utente.** Fino a quando l'utente
   non la fornisce, si usa una cartella d'esempio sintetica. Il risultato deve:
   - produrre la relazione in **Word e in LaTeX** (due esecuzioni);
   - superare tutte le misure di forma;
   - avere il frontespizio corrispondente al modello;
   - non contenere fatti non tracciabili alla cartella o alle risposte;
   - superare la checklist di contenuto del revisore.
2. **Solo revisione.** Si prepara una bozza con difetti inseriti apposta:
   - font sbagliato, circa 85 caratteri per riga, indice mancante;
   - introduzione di 4 pagine, refusi;
   - acronimo non definito, figura non citata;
   - contributo personale assente, una credenziale nel testo.

   Il revisore deve trovarli tutti. Le revisioni Word devono aprirsi correttamente
   in Word e LibreOffice ed essere accettabili e rifiutabili; il PDF delle differenze
   LaTeX deve compilare.
3. **Ripresa:** interrompere a metà (dopo 2 capitoli) e riprendere in una nuova
   sessione senza perdere decisioni né rifare domande già fatte.
4. **Codex:** il caso 1 o il caso 2 eseguito con Codex.
5. **Script:** test automatici per calcolo impaginazione, misura (su documenti di
   esempio con valori noti), validità dei `.docx` con revisioni.

## 10. Lasciato al costruttore

- Librerie specifiche (es. per leggere e scrivere `.docx`, estrarre testo dal PDF,
  generare diagrammi), purché multipiattaforma e coerenti con §8.
- Formato esatto del file di stato e dei profili, nomi definitivi delle skill.
- Come gli script si trovano dalle skill su entrambe le piattaforme.
- Come si scelgono le domande dell'intervista (numero, raggruppamento), nel rispetto
  di §4.6.
- **Lingua delle istruzioni interne delle skill** **[proposta]**: inglese, per la
  massima riusabilità. Le interazioni con l'utente e i documenti restano nella sua
  lingua.
- Nome definitivo del plugin.
