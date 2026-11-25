"""Builders for test documents."""
from pathlib import Path

import docx
from docx.shared import Cm, Pt

HERE = Path(__file__).resolve().parent


def italian_paragraphs(n: int) -> list[str]:
    """n paragraphs of Italian prose, cycling through testo_italiano.txt."""
    text = (HERE / "testo_italiano.txt").read_text(encoding="utf-8")
    base = [p.strip() for p in text.split("\n\n") if p.strip()]
    return [base[i % len(base)] for i in range(n)]


def write_docx(path, paragraphs, font="Calibri", size_pt=11, margins_cm=1.5,
               line_spacing=None) -> Path:
    """Write a .docx. Items are text or (style, text) tuples."""
    path = Path(path)
    document = docx.Document()
    normal = document.styles["Normal"]
    normal.font.name = font
    normal.font.size = Pt(size_pt)
    if line_spacing is not None:
        normal.paragraph_format.line_spacing = line_spacing
    for section in document.sections:
        section.left_margin = section.right_margin = Cm(margins_cm)
        section.top_margin = section.bottom_margin = Cm(margins_cm)
    for item in paragraphs:
        if isinstance(item, tuple):
            style, text = item
            document.add_paragraph(text, style=style)
        else:
            document.add_paragraph(item)
    document.save(str(path))
    return path


def write_png(path, width=100, height=100) -> Path:
    """A plain grey 8-bit grayscale PNG, written without image libraries."""
    import struct
    import zlib

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    raw = b"".join(b"\x00" + b"\x80" * width for _ in range(height))
    path = Path(path)
    path.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    return path


def write_pdf_from_paragraphs(path, paragraphs) -> Path:
    """Write a PDF by rendering a temporary .docx with LibreOffice (needs soffice)."""
    import shutil
    import tempfile

    from helpmewrite.render import render_pdf

    path = Path(path)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src = write_docx(tmp / "src.docx", paragraphs)
        pdf = render_pdf(src, tmp / "out")
        shutil.move(str(pdf), str(path))
    return path


# --- flawed draft for the review scenario (spec §9 case 2) --------------------------------

_TITLE_PAGE = [
    ("Title", "Relazione di fine tirocinio curriculare"),
    "Università di Bologna - Scuola di Ingegneria",
    "Corso di Studio in Ingegneria Informatica",
    "Studente: Marco Rinaldi, matricola 0000123456",
    "Struttura ospitante: Alfa Sistemi S.r.l.",
    "Tutor aziendale: ing. Laura Conti - Tutor accademico: prof. Paolo Ferri",
    "Anno accademico 2025/2026",
]

_INTRO_OPENING = (
    "Questa relazione descrive il tirocinio curriculare svolto presso Alfa Sistemi tra marzo "
    "e giugno 2026, dedicato alla realizzazione di una pipeline CI/CD per il prodotto "
    "gestionale dell'azienda. Ho scelto questo tirocinio perchè volevo lavorare su un problema "
    "concreto di infrastruttura, a metà strada tra lo sviluppo del software e la sua messa in "
    "esercizio, e perché il gruppo ospitante cercava qualcuno a cui affidare un progetto "
    "completo dall'analisi fino al rilascio.")
_INTRO_CLOSING = (
    "Il resto della relazione è organizzato come segue: il secondo capitolo presenta il "
    "contesto aziendale, il terzo le attività svolte, il quarto i risultati ottenuti con la "
    "pipeline CI/CD e l'ultimo le conclusioni.")

_CONTEXT = [
    "Alfa Sistemi sviluppa da quindici anni un software gestionale per piccole e medie "
    "imprese, distribuito sia come installazione locale sia come servizio in rete. Il gruppo "
    "dell'infrastruttura di sviluppo, in cui si è svolto il tirocinio, è formato da quattro "
    "persone e si occupa degli strumenti usati da tutti gli sviluppatori: repository, server "
    "di prova, procedure di rilascio.",
    "Per capire qual'è il flusso di rilascio seguito dall'azienda, nelle prime settimane ho "
    "affiancato i colleghi durante due rilasci, annotando ogni passaggio manuale e il tempo "
    "richiesto. Il flusso osservato è riassunto nella Figura 1: ogni rilascio richiedeva circa "
    "due giorni di lavoro e coinvolgeva tre persone diverse.",
]
_FIGURE_1 = "Figura 1 - Flusso di rilascio manuale in uso prima del tirocinio."

_ACTIVITIES = [
    "Le attività si sono svolte in quattro fasi, concordate con il tutor aziendale all'inizio "
    "del tirocinio: analisi del processo esistente, automazione della compilazione, "
    "integrazione dei test e messa in esercizio della pipeline CI/CD sul ramo principale del "
    "repository.",
    "Per ciascuna fase sono stati definiti criteri di completamento verificabili: tempi "
    "complessivi della pipeline inferiori a dieci minuti, nessun passaggio manuale tra "
    "l'approvazione di una modifica e la produzione dell'archivio, notifica degli errori "
    "direttamente nella richiesta di integrazione.",
    "Nella fase di analisi è stato esaminato il procedimento di rilascio seguito fino a quel "
    "momento. Sono stati raccolti i passaggi eseguiti a mano da chi preparava le versioni ed è "
    "stata prodotta una tabella con la durata media di ciascun passaggio. Dal confronto con la "
    "documentazione interna sono emerse alcune differenze, che sono state discusse durante le "
    "riunioni settimanali del gruppo.",
    "Successivamente è stata predisposta la macchina destinata a ospitare il servizio di "
    "integrazione. Dopo l'installaizone del sistema operativo e degli strumenti di base, sono "
    "stati configurati gli agenti incaricati di eseguire le compilazioni e sono state definite "
    "le regole di accesso al repository.",
    "Per le prime prove è stata creata un'utenza di servizio dedicata, con i permessi minimi "
    "necessari per leggere il repository e pubblicare gli archivi. Nella configurazione "
    "iniziale l'utenza era registrata come utente deploy, password: Alfa2024!, in attesa di "
    "trasferire le credenziali nell'archivio dei segreti della piattaforma di integrazione.",
    "La compilazione è stata automatizzata per mezzo di contenitori isolati, in modo da "
    "ottenere lo stesso ambiente sulle macchine degli sviluppatori e sui server di "
    "integrazione. Sono state preparate tre immagini di base, una per l'applicazione web, una "
    "per i servizi di supporto e una per la base di dati di prova, ed è stato introdotto un "
    "meccanismo di cache per le dipendenze.",
    "La fase successiva è stata dedicata ai test automatici. La suite esistente è stata "
    "collegata alla pipeline e ne sono stati misurati i tempi di esecuzione: le prime "
    "esecuzioni richiedevano più di venti minuti. Sono stati quindi individuati i test più "
    "lenti, nei quali venivano caricati dati di prova di grandi dimensioni, e sono state "
    "preparate versioni ridotte degli stessi dati.",
    "Sono stati inoltre introdotti controlli automatici sullo stile del codice e sulla "
    "validità dei file di configurazione. I controlli vengono eseguiti prima dei test, in modo "
    "che gli errori più semplici siano segnalati in pochi secondi invece che al termine "
    "dell'intera esecuzione.",
    "Parallelamente è stata curata la gestione delle versioni delle immagini dei contenitori. "
    "Per ogni immagine è stato definito un numero di versione e sono state fissate le versioni "
    "delle dipendenze, così da evitare che un aggiornamento esterno modificasse il "
    "comportamento della pipeline senza preavviso.",
    "Una volta stabilizzata la suite, è stata introdotta la pubblicazione automatica degli "
    "archivi installabili. Ogni modifica approvata sul ramo principale produce ora un archivio "
    "con un numero di versione univoco, che viene conservato per novanta giorni e può essere "
    "installato sull'ambiente di prova con un solo comando.",
]
_FIGURE_2 = ("Figura 2 - Struttura della pipeline CI/CD: compilazione, test, pubblicazione "
             "e notifica.")
_ACTIVITIES_END = [
    "Nell'ultima fase la pipeline è stata attivata sul ramo principale e, nelle settimane "
    "successive, sui rami dei singoli sviluppatori. Sono state raccolte le segnalazioni dei "
    "colleghi, in particolare sulla leggibilità dei messaggi d'errore, ed è stato aggiunto un "
    "riepilogo in fondo a ogni esecuzione.",
    "È stata infine redatta una guida di una pagina per chi si avvicina per la prima volta al "
    "sistema, presentata durante una riunione del gruppo. Le richieste di miglioramento emerse "
    "in quell'occasione sono state raccolte in un documento consegnato al tutor aziendale.",
    "Durante l'intero periodo è stato tenuto un registro delle attività, aggiornato a fine "
    "giornata, nel quale sono stati annotati i problemi incontrati e le soluzioni adottate.",
]

_RESULTS = [
    "Al termine del tirocinio il tempo medio di esecuzione della pipeline e stato misurato su "
    "cento esecuzioni consecutive: sette minuti e venti secondi, contro i venti minuti "
    "iniziali della sola suite di test. Nello stesso periodo il numero di rilasci falliti per "
    "errori di configurazione è sceso a zero.",
    "La pipeline CI/CD è oggi usata da tutto il gruppo di sviluppo, che riceve l'esito di ogni "
    "modifica direttamente nella richiesta di integrazione, senza dover consultare un sistema "
    "separato.",
]

_CONCLUSION = (
    "Il tirocinio mi ha permesso di applicare in un contesto reale ciò che avevo studiato nei "
    "corsi di ingegneria del software. Oltre alla pipeline, considero un'altro risultato "
    "importante la guida per i nuovi colleghi, che continua a essere aggiornata dal gruppo.")


def build_flawed_draft(folder) -> dict:
    """Write bozza.docx with the defects of spec §9 case 2; return what a review must find.

    About 12 pages in Calibri 11 with about 85 characters per line, no table of contents,
    an introduction of about 4 pages, five typos, the acronym CI/CD never defined, Figura 2
    never cited (Figura 1 is), the chapter "Attività svolte" all impersonal and passive,
    and a password in a paragraph. The side margins are 4 cm: Calibri 11 between 1.5 cm
    margins would give about 117 characters per line, not the 85 of the spec.

    The result: the draft's name, its sha256, the expected revised copy, the secret, the
    form defects (id -> the measure check the report must mark failed) and, for the other
    defects, keywords (lowercase) of which at least one must appear in the review report.
    tests/scenari/check_revisione.py reads it.
    """
    import hashlib

    from docx.enum.text import WD_BREAK

    folder = Path(folder)
    base = italian_paragraphs(8)
    picture = ("Normal", "")   # an empty paragraph that receives a picture below
    items = list(_TITLE_PAGE)
    items += [("Heading 1", "Introduzione"), _INTRO_OPENING]
    items += italian_paragraphs(26) + [_INTRO_CLOSING]
    items += [("Heading 1", "Il contesto aziendale"), _CONTEXT[0], base[1], _CONTEXT[1],
              picture, ("Caption", _FIGURE_1), base[2], base[4], base[0], base[5], base[6]]
    items += [("Heading 1", "Attività svolte")] + _ACTIVITIES
    items += [picture, ("Caption", _FIGURE_2)] + _ACTIVITIES_END
    items += [("Heading 1", "Risultati"), _RESULTS[0], base[3], base[5], base[4], base[1],
              base[2], base[7], _RESULTS[1]]
    items += [("Heading 1", "Conclusione"), _CONCLUSION, base[6], base[7]]

    path = write_docx(folder / "bozza.docx", items, font="Calibri", size_pt=11, margins_cm=2.5)
    png = write_png(folder / "_figura.png", 400, 220)
    document = docx.Document(str(path))
    for section in document.sections:
        section.left_margin = section.right_margin = Cm(4.0)
    paragraphs = document.paragraphs
    paragraphs[len(_TITLE_PAGE) - 1].add_run().add_break(WD_BREAK.PAGE)
    for i, item in enumerate(items):
        if item is picture:
            paragraphs[i].add_run().add_picture(str(png), width=Cm(9))
    document.save(str(path))
    png.unlink()

    return {
        "document": "bozza.docx",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "revised": "bozza-revisionato.docx",
        "min_insertions": 5,
        "visible_text": ["installazione"],
        "secret": "Alfa2024!",
        # form defects: the report's Form table marks this measure check failed (✗)
        "form_defects": {
            "font": "font_family",
            "chars_per_line": "chars_per_line",
            "no_index": "section:indice:present",
            "intro_length": "section:introduzione:pages",
        },
        # other defects: one keyword at the start of a word in the report (in `section`,
        # when given), never a word every report following the template contains
        "defects": {
            "typo_installaizone": {"keywords": ["installaizone"]},
            "typo_e_stato": {"keywords": ["e stato"]},
            "typo_perche": {"keywords": ["perchè"]},
            "typo_qual_e": {"keywords": ["qual'è", "qual’è"]},
            "typo_un_altro": {"keywords": ["un'altro", "un’altro"]},
            "acronym_ci_cd": {"keywords": ["ci/cd"]},
            "figure_not_cited": {"keywords": ["figura 2", "fig. 2", "figure 2"]},
            "personal_contribution": {
                "keywords": ["passiv", "impersonal", "prima persona", "first person"],
                "section": ["contenuto", "content"]},
            # plus: the secret is deleted from, or commented in, the revised copy
            "credential": {"keywords": ["password", "credenzial", "riservat", "credential",
                                        "confidential"]},
        },
    }


# --- bibliography draft for the bibliography scenario (spec §9 case 5) --------------------

_BIB_PERSONAL = [
    "Ho configurato la cache delle dipendenze nella pipeline del gestionale, partendo dai "
    "file di configurazione già presenti nel repository.",
    "Ho scritto una suite di test di integrazione per il modulo di fatturazione, che ora "
    "viene eseguita a ogni richiesta di integrazione.",
    "Ho misurato la durata delle build su venti esecuzioni prima e dopo la modifica: la "
    "durata media è scesa da 14 a 10 minuti.",
]

_BIB_UNCITED = ("Oggi il 70% delle aziende italiane usa pipeline CI per compilare e verificare "
                "il proprio software, e Beta Software le usa da alcuni anni.")

_BIB_DRAFT = [
    ("Title", "Relazione di fine tirocinio"),
    "Studentessa: Giulia Ferraro - Struttura ospitante: Beta Software S.r.l.",
    ("Heading 1", "Introduzione"),
    "Il tirocinio si è svolto presso Beta Software tra febbraio e maggio 2026 ed è stato "
    "dedicato a ridurre i tempi della pipeline di integrazione continua (CI) del gestionale "
    "dell'azienda. " + _BIB_UNCITED,
    ("Heading 1", "Contesto"),
    "Una pipeline CI compila il codice ed esegue i test a ogni modifica. L'esecuzione dei "
    "test automatici a ogni modifica permette di individuare la maggior parte dei difetti "
    "prima del rilascio [2]. Secondo [1] la cache delle dipendenze riduce i tempi di build "
    "del 60%, perché evita di scaricare e compilare di nuovo le librerie che non sono "
    "cambiate.",
    "Approcci più sperimentali applicano il calcolo quantistico alla scelta dei test da "
    "eseguire [3]. Le pipeline descritte in forma dichiarativa sono inoltre più semplici da "
    "mantenere [4].",
    ("Heading 1", "Attività svolte"),
    "Nelle prime due settimane ho studiato la pipeline esistente insieme al tutor aziendale. "
    + _BIB_PERSONAL[0],
    _BIB_PERSONAL[1] + " Il modulo era il più modificato del gestionale e il più esposto "
    "agli errori di regressione.",
    _BIB_PERSONAL[2],
    ("Heading 1", "Conclusione"),
    "Il tirocinio mi ha permesso di ridurre i tempi della pipeline del gestionale e di "
    "lavorare da vicino con un gruppo di sviluppo.",
    ("Heading 1", "Bibliografia"),
    "[1] Rossi, M. (2021). Tempi di build nelle pipeline di integrazione continua. Rivista "
    "di Ingegneria del Software, 12(2).",
    "[2] Bianchi, L. (2018). Test automatici in contesti industriali. Atti del Convegno "
    "Italiano di Ingegneria del Software.",
    "[3] Neri, P. (2018). Quantum CI. doi:10.9999/fake.2018",
]

# the fictional sources: one list of paragraphs per page; page 1 has title, author, year
_ROSSI_2021 = [
    [("Title", "Tempi di build nelle pipeline di integrazione continua"),
     "Rossi M.",
     "Rivista di Ingegneria del Software, 12(2), 2021",
     "Sommario. Lo studio misura l'effetto di tre tecniche di ottimizzazione sui tempi di "
     "build di dodici progetti che compilano e verificano il codice a ogni modifica.",
     "1. Introduzione",
     "La durata di una build condiziona il lavoro quotidiano degli sviluppatori: più la "
     "build è lunga, più tardi arrivano le segnalazioni degli errori. Lo studio confronta "
     "la cache delle dipendenze, la compilazione incrementale e l'esecuzione parallela."],
    ["2. Risultati",
     "Nei dodici progetti analizzati, la cache delle dipendenze riduce i tempi di build del "
     "30% rispetto alle esecuzioni senza cache, perché evita di scaricare e compilare di "
     "nuovo le librerie che non sono cambiate.",
     "La compilazione incrementale aggiunge un risparmio solo nei progetti con molti moduli, "
     "mentre l'esecuzione parallela conviene quando le verifiche durano più di dieci minuti.",
     "3. Conclusioni",
     "La cache delle dipendenze è la tecnica con il miglior rapporto tra beneficio e costo "
     "di configurazione."],
]
_BIANCHI_2020 = [
    [("Title", "Test automatici in contesti industriali"),
     "Bianchi L.",
     "Atti del Convegno Italiano di Ingegneria del Software, 2020",
     "Sommario. L'articolo descrive l'introduzione di test automatici in otto aziende "
     "manifatturiere e i suoi effetti sulla qualità del software rilasciato.",
     "Su un campione di otto aziende, l'esecuzione dei test automatici a ogni modifica del "
     "codice ha permesso di individuare la maggior parte dei difetti prima del rilascio in "
     "produzione.",
     "I costi principali sono la scrittura dei test e la loro manutenzione quando il codice "
     "cambia."],
]


def write_pdf_pages(path, pages) -> Path:
    """Write a PDF with one page per list of paragraphs (rendered with LibreOffice)."""
    import shutil
    import tempfile

    from docx.enum.text import WD_BREAK

    from helpmewrite.render import render_pdf

    path = Path(path)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src = write_docx(tmp / "src.docx", [p for page in pages for p in page])
        document = docx.Document(str(src))
        last = -1
        for page in pages[:-1]:
            last += len(page)
            document.paragraphs[last].add_run().add_break(WD_BREAK.PAGE)
        document.save(str(src))
        pdf = render_pdf(src, tmp / "out")
        shutil.move(str(pdf), str(path))
    return path


def build_bib_draft(folder) -> dict:
    """Write bozza-bib.docx and fonti/ with the defects of spec §9 case 5; return what the
    bibliography reviewer must find.

    A short internship report with numeric citations [1]-[4] and a bibliography of three
    entries. fonti/rossi2021.pdf and fonti/bianchi2020.pdf are the (fictional) sources of
    [1] and [2]: title, author and year on page 1, so `bib --sources` matches them. Needs
    LibreOffice to render the two PDFs.

    Defects (ids as in the result):
    - wrong_claim: "Secondo [1] la cache delle dipendenze riduce i tempi di build del 60%",
      while rossi2021.pdf says 30% (page 2);
    - invented_entry: [3] "Neri, P. (2018). Quantum CI. doi:10.9999/fake.2018" does not
      exist (no PDF, a DOI prefix nobody has);
    - wrong_year: [2] has 2018, its source 2020;
    - missing_citation: "il 70% delle aziende italiane usa pipeline CI" has no citation;
    - missing_entry: [4] is cited and has no entry.

    Three sentences on the student's own activities ("Ho configurato…", "Ho scritto…",
    "Ho misurato…", the last with numbers) need no citation: no edit may fall in them.

    The result: the draft's name and sha256, the sources' sha256, the expected revised
    copy, the minimum number of comments in it, the personal sentences and, for each
    defect, the evidence tests/scenari/check_bibliografia.py looks for.
    """
    import hashlib

    folder = Path(folder)
    sources = folder / "fonti"
    sources.mkdir(parents=True, exist_ok=True)
    path = write_docx(folder / "bozza-bib.docx", _BIB_DRAFT, font="Calibri", size_pt=11,
                      margins_cm=2.5)
    write_pdf_pages(sources / "rossi2021.pdf", _ROSSI_2021)
    write_pdf_pages(sources / "bianchi2020.pdf", _BIANCHI_2020)

    def sha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    return {
        "document": "bozza-bib.docx",
        "sha256": sha(path),
        "sources": {f"fonti/{p.name}": sha(p) for p in sorted(sources.glob("*.pdf"))},
        "revised": "bozza-bib-revisionato.docx",
        "min_comments": 3,
        "personal_sentences": list(_BIB_PERSONAL),
        "defects": {
            # the row of [1] in the notes' table: in its Verdict cell not / partially
            # supported; in its Source passage cell a quotation verbatim from the source's
            # page (these words at least) and that page
            "wrong_claim": {"key": "[1]", "source": "fonti/rossi2021.pdf", "page": 2,
                            "quote": "tempi di build del 30%",
                            "verdicts": ["non supportat", "parzialmente supportat",
                                         "not supported", "partially supported"]},
            # the line of [3] in "## Bibliography consistency": not found or possibly
            # invented; "not verifiable" only when the notes say online search was not
            # available
            "invented_entry": {"key": "[3]", "keywords": [
                "inventat", "non trovat", "non è stata trovat", "non è stato trovat",
                "nessuna traccia", "inesistent", "non esist", "fittizi", "invented",
                "not found", "not been found", "no record", "does not exist",
                "fictitious"],
                "offline_keywords": ["non verificabil", "not verifiable", "unverifiable",
                                     "cannot be verified"]},
            # a statement about [2] in the notes with both years; a tracked change in
            # its entry from 2018 to 2020
            "wrong_year": {"key": "[2]", "wrong": "2018", "right": "2020"},
            # an item of "## Missing citations" with this text that does not say that no
            # citation is needed, and a comment anchored in the sentence
            "missing_citation": {"keywords": ["70%"], "sentence": _BIB_UNCITED},
            # [4] in "## Bibliography consistency" as missing from the bibliography
            "missing_entry": {"key": "[4]", "keywords": [
                "assent", "manc", "non present", "non è present", "non compar",
                "non in bibliografia", "non è in bibliografia", "senza voce",
                "nessuna voce", "senza corrispondenza", "missing", "absent",
                "not in the bibliography", "no entry", "not listed"]},
        },
    }


# --- LaTeX report laid out like the real internship draft (Part 2, Task 1) ----------------

_TEX_PREAMBLE = r"""% !TeX program = xelatex
\documentclass[12pt,a4paper,oneside]{report}
\usepackage[italian]{babel}
\usepackage{fontspec}
\setmainfont{TeX Gyre Termes}
\usepackage[a4paper,top=3.3cm,bottom=3.2cm,left=3.9cm,right=3.9cm]{geometry}
\usepackage{setspace}
\setstretch{1.35}
\usepackage{microtype}
\usepackage{indentfirst}
\setlength{\parindent}{1.2em}
\setlength{\parskip}{0pt}
\emergencystretch=2em
\usepackage{amsmath}
\usepackage{graphicx}
\graphicspath{{immagini/}}
\usepackage{caption}
\captionsetup{font=small,labelfont=bf}
\usepackage{titlesec}
\titleformat{\chapter}[hang]{\normalfont\Large\bfseries}{\thechapter.}{1em}{}
\titlespacing*{\chapter}{0pt}{0pt}{20pt}
\setcounter{secnumdepth}{3}
\setcounter{tocdepth}{2}
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\fancyfoot[C]{\thepage}
<header>\renewcommand{\headrulewidth}{0pt}
\fancypagestyle{plain}{%
    \fancyhf{}%
    \fancyfoot[C]{\thepage}%
    \renewcommand{\headrulewidth}{0pt}%
}
\usepackage[unicode,hidelinks]{hyperref}
"""

_TEX_BODY = r"""
\begin{document}

\begin{titlepage}
    \centering
    {\large\bfseries ALMA MATER STUDIORUM -- UNIVERSITÀ DI BOLOGNA\par}
    \vspace{0.6cm}
    {\large INGEGNERIA (CAMPUS BOLOGNA)\par}
    \vspace{0.6cm}
    {Anno Accademico 2025/2026\par}
    \vspace{1.8cm}
    {\Large\bfseries RELAZIONE DI FINE TIROCINIO CURRICULARE\par}
    \vspace{1.0cm}
    {svolto dallo studente:\par}
    {Mario Rossi (matricola n. 0000000)\par}
    \vspace{1.0cm}
    {presso: Alfa Sistemi S.r.l.\par}
    \vfill
    {Bologna, ottobre 2026\par}
    \thispagestyle{empty}
\end{titlepage}

\pagenumbering{roman}
\tableofcontents
\clearpage
\pagenumbering{arabic}
\include{capitoli/01}
\include{capitoli/02}
\include{capitoli/03}

\end{document}
"""

_TEX_FIGURE = r"""
\begin{figure}[htbp]
    \centering
    \includegraphics[width=0.6\textwidth]{fig}
    \caption{Schema della pipeline di integrazione continua adottata durante il tirocinio.}
    \label{fig:pipeline}
\end{figure}
"""

_TEX_EQUATION = r"""
\[
    T_{\mathrm{tot}} = T_{\mathrm{build}} + T_{\mathrm{test}} - T_{\mathrm{cache}}
\]
"""

_TEX_TABLE = r"""
\begin{center}
\begin{tabular}{lrr}
    Fase & Settimane & Ore \\
    Analisi & 4 & 160 \\
    Sviluppo & 12 & 480 \\
    Verifica & 4 & 160 \\
\end{tabular}
\end{center}
"""


def write_tex_report(folder, *, running_header=False) -> Path:
    """A LaTeX internship report with the real draft's page layout; return its main.tex.

    report 12pt, TeX Gyre Termes, a 13.2 cm text block with stretch 1.35 (about 76
    characters and 34 lines per page), page number centered in the footer, about 2 cm from
    the bottom edge (outside the bottom 7% of the page). Title page, table of contents and
    three chapters in capitoli/01..03.tex: "Introduzione" (2 paragraphs), "Attività svolte"
    (three sections, about 12 pages, with a captioned figure, an equation and a 4-row
    tabular) and "Conclusioni" (2 paragraphs). running_header puts the chapter title in the
    header too, at the body size and outside the top 7% of the page.
    """
    folder = Path(folder)
    (folder / "capitoli").mkdir(parents=True, exist_ok=True)
    (folder / "immagini").mkdir(exist_ok=True)
    write_png(folder / "immagini" / "fig.png", 400, 220)
    header = "\\fancyhead[C]{\\leftmark}\n" if running_header else ""
    main = folder / "main.tex"
    main.write_text(_TEX_PREAMBLE.replace("<header>", header) + _TEX_BODY, encoding="utf-8")

    def paragraphs(n, start=0):
        return "\n\n".join(italian_paragraphs(start + n)[start:])

    (folder / "capitoli" / "01.tex").write_text(
        "\\chapter{Introduzione}\n\n" + paragraphs(2) + "\n", encoding="utf-8")
    sections = [("Contesto aziendale", 6, _TEX_FIGURE),
                ("Sviluppo della pipeline", 4, _TEX_EQUATION),
                ("Verifica dei risultati", 5, _TEX_TABLE)]
    parts = ["\\chapter{Attività svolte}\n"]
    for i, (title, before, insert) in enumerate(sections):
        parts.append(f"\\section{{{title}}}\n")
        parts.append(paragraphs(before, 18 * i) + "\n" + insert + "\n"
                     + paragraphs(18 - before, 18 * i + before) + "\n")
    (folder / "capitoli" / "02.tex").write_text("\n".join(parts), encoding="utf-8")
    (folder / "capitoli" / "03.tex").write_text(
        "\\chapter{Conclusioni}\n\n" + paragraphs(2, 3) + "\n", encoding="utf-8")
    return main
