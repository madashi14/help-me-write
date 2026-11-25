"""Set up and check the real-draft scenario (tests/scenari/bozza-parziale.md). Needs no pytest.

    python tests/scenari/check_bozza_parziale.py --setup <tmp>
        <tmp> must be new or empty. Clones https://github.com/madashi14/relazione_tirocinio
        (public, `git clone --depth 1`, git-lfs smudge off) and writes:
        - <tmp>/lavoro: the clone without .git, without main.pdf and without LaTeX
          artefacts (*.aux, *.toc, *.out, *.log, *.synctex.gz), plus
          .help-me-write/linee-guida.yaml (the Unibo fixture);
        - <tmp>/risposte.md: the answers the agent reads instead of the user;
        - <tmp>/plugin: a copy of the plugin without tests/ and docs/ (as in Part 1);
        - <tmp>-verifica/: the sha256 of every file of lavoro (hash-originali.json) and the
          untouched clone, kept as reference outside the folders the agent is given.
        Prints a warning if fontconfig does not know "Times New Roman".

    python tests/scenari/check_bozza_parziale.py --check <tmp>
        checks <tmp>/lavoro after the run: one line PASS or FAIL with the reason per check,
        exit 1 if any fails.

Number check (5): the text of 06_conclusioni.tex of the working copy is stripped of
comments, `\\label`, `\\ref`, `\\cite`, `\\includegraphics`, `\\vspace`-like commands with
their arguments, optional `[...]` arguments, other `\\command` names and math delimiters;
every number left (`\\d+(?:[.,]\\d+)?`) must occur, as a whole number and with `.` or `,`
as decimal separator, in chapters 1-5 of the copy (files 01..05_*.tex), in materiale.md
or in risposte.md. Section numbers do not appear: LaTeX numbers sections itself.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "scripts"), str(Path(__file__).resolve().parent)]

from check_revisione import PLUGIN_PARTS  # noqa: E402  (what the plugin needs at run time)

SOURCE_URL = "https://github.com/madashi14/relazione_tirocinio"
PROJECT = "relazione_tirocinio/Relazione_Tirocinio"  # the LaTeX project inside the clone
ARCHIVES = ["script.zip", "rf.zip", "ml_physics_rf_v2.zip"]  # in relazione_tirocinio/
NOTEBOOK = "travi.ipynb"
ARTEFACTS = ["main.pdf", "*.aux", "*.toc", "*.out", "*.log", "*.synctex.gz"]
STATE = ".help-me-write"
MIN_CONCLUSION_CHARS = 1500
TARGET_PAGES = 30
BLOCK_BEGIN = "% help-me-write: impaginazione (inizio)"
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")

# title page values of the scenario: fictional, written to risposte.md and checked in main.tex
TITLE_VALUES = {
    "NomeStudente": "Studente Prova",
    "MatricolaStudente": "0000000000",
    "CorsoDiStudio": "Laurea Magistrale in Ingegneria Meccanica",
    "CodiceCorso": "0000",
    "StrutturaOspitante": "Struttura Ospitante di Prova",
    "TutorOspitante": "Tutor Prova, responsabile di prova",
    "AnnoAccademico": "2026/2027",
}

RISPOSTE = """# Risposte dell'utente (scenario di prova)

Tutti i valori di questo file sono fittizi, scritti per la prova: non sono dati reali.

## Linee guida

Le linee guida in `.help-me-write/linee-guida.yaml` sono ancora valide. Il file del
facsimile a cui rimandano non è in questa cartella. Il regolamento dice: "tra 10 e 30
pagine circa". Voglio rispettare le 30 pagine: il limite per me è quello, non uno di più.
Per la copia di lavoro usa il Times New Roman, come nella bozza.

## Cronologia del tirocinio (indicativa, per la sezione Cronologia)

- Prima e seconda settimana di ottobre 2026: familiarizzazione con ANSYS Workbench e studio
  preliminare.
- Terza e quarta settimana di ottobre 2026: automazione delle simulazioni con Python e
  MAPDL (script batch).
- Prima e seconda settimana di novembre 2026: Random Forest sulle campagne di simulazione.
- Terza e quarta settimana di novembre 2026: reti neurali per travi e telai
  (`travi.ipynb`).

## Valori del frontespizio (FITTIZI, solo per la prova)

- Nome dello studente: Studente Prova
- Matricola: 0000000000
- Corso di studio: Laurea Magistrale in Ingegneria Meccanica (confermo il valore già nel
  file)
- Codice del corso: 0000
- Struttura ospitante: Struttura Ospitante di Prova
- Referente della struttura ospitante: Tutor Prova, responsabile di prova
- Anno accademico: 2026/2027
- Titolo: confermo quello già nel file.

## Conclusioni (risposte all'intervista)

- Obiettivi raggiunti: ho costruito un percorso che parte dall'uso di ANSYS, passa
  all'automazione delle simulazioni con Python e raggiunge un primo strumento di
  diagnostica degli errori FEM con la Random Forest e con una rete neurale a grafo sui
  telai piani, come descritto nei capitoli da 1 a 5.
- Cosa ho imparato: a impostare e ripetere campagne di simulazione senza passare dalla
  interfaccia grafica, a distinguere l'esecuzione batch di MAPDL (sottoprocesso e file
  APDL) dalla libreria PyMAPDL, a leggere i log e a organizzare i dati, a confrontare
  modelli di Machine Learning e a interpretare i loro risultati.
- Limiti: i risultati vanno letti come una prima verifica, non come un sistema pronto
  per l'uso; la capacità di generalizzare a casi diversi da quelli generati resta da
  dimostrare, come dicono i capitoli 4 e 5; i conteggi delle simulazioni sono quelli
  programmati dagli script.
- Sviluppi: quelli già indicati alla fine del capitolo 5. Non aggiungere altri numeri: usa
  solo quelli già presenti nei capitoli.

## Approvazioni

- Approvo l'indice (il piano di riorganizzazione) e la copia di lavoro con l'impaginazione
  corretta.
- Approvo i valori del frontespizio sopra elencati.
- Approvo le conclusioni come scritte.
- Approvo l'elenco dei tagli proposti ma non applicarli: la prova si ferma lì.
"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _verifica(tmp: Path) -> Path:
    return tmp.with_name(tmp.name + "-verifica")


def _hashes(lavoro: Path) -> dict:
    return {p.relative_to(lavoro).as_posix(): _sha256(p)
            for p in sorted(lavoro.rglob("*"))
            if p.is_file() and STATE not in p.relative_to(lavoro).parts}


def _times_new_roman_known() -> bool:
    try:
        out = subprocess.run(["fc-list", ":family"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    return "times new roman" in out.stdout.casefold()


def setup(tmp: Path) -> int:
    tmp = tmp.resolve()
    verifica = _verifica(tmp)
    for folder in (tmp, verifica):
        if folder.exists() and any(folder.iterdir()):
            print(f"error: {folder} exists and is not empty", file=sys.stderr)
            return 2
    tmp.mkdir(parents=True, exist_ok=True)
    verifica.mkdir(parents=True, exist_ok=True)
    clone = verifica / "clone"
    env = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1")
    try:
        subprocess.run(["git", "clone", "--depth", "1", SOURCE_URL, str(clone)],
                       env=env, check=True, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"error: cannot clone {SOURCE_URL}: {getattr(exc, 'stderr', exc)}", file=sys.stderr)
        return 3
    lavoro = tmp / "lavoro"
    shutil.copytree(clone, lavoro, ignore=shutil.ignore_patterns(".git", *ARTEFACTS))
    state = lavoro / STATE
    state.mkdir()
    shutil.copyfile(REPO / "tests" / "fixtures" / "linee-guida-unibo.yaml",
                    state / "linee-guida.yaml")
    (tmp / "risposte.md").write_text(RISPOSTE, encoding="utf-8")
    plugin = tmp / "plugin"
    for part in PLUGIN_PARTS:
        source = REPO / part
        if source.is_dir():
            shutil.copytree(source, plugin / part,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        elif source.is_file():
            plugin.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, plugin / part)
    hashes = _hashes(lavoro)
    (verifica / "hash-originali.json").write_text(
        json.dumps(hashes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    missing = [n for n in [f"relazione_tirocinio/{a}" for a in ARCHIVES] + [NOTEBOOK]
               if n not in hashes]
    print(f"wrote {lavoro} ({len(hashes)} files), {tmp / 'risposte.md'}, plugin copy {plugin}, "
          f"reference {verifica}")
    if missing:
        print(f"warning: expected files missing from the clone: {missing}", file=sys.stderr)
    if not _times_new_roman_known():
        print('warning: fontconfig does not know "Times New Roman": XeLaTeX cannot compile the '
              "draft. Run python tests/strumenti/font_times_prova.py --dest <dir> (see its "
              "docstring), then fc-cache -f", file=sys.stderr)
    return 0


# --- checks -------------------------------------------------------------------------------

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _section(text: str, names) -> str:
    """Text under the first `## <name>` heading whose name is one of `names` (casefolded)."""
    out, inside = [], False
    for line in text.splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            if inside:
                break
            inside = heading.group(1).replace("’", "'").casefold() in names
        elif inside:
            out.append(line)
    return "\n".join(out)


def conclusion_text(tex: str) -> str:
    """Plain text of a LaTeX chapter: what is left after dropping what is not prose."""
    tex = re.sub(r"(?<!\\)%.*", "", tex)
    tex = re.sub(r"\\(?:label|ref|eqref|autoref|cref|Cref|pageref|cite[a-z]*|includegraphics"
                 r"|vspace|hspace|setlength|input|include)\*?(?:\[[^\]]*\])*\{[^{}]*\}", " ", tex)
    tex = re.sub(r"\\(?:chapter|section|subsection)\*?(?:\[[^\]]*\])?\{", "{", tex)
    tex = re.sub(r"\[[^\]\n]*\]", " ", tex)
    tex = re.sub(r"\\[A-Za-z]+\*?", " ", tex)
    tex = re.sub(r"[\\${}~^_&#]", " ", tex)
    return re.sub(r"\s+", " ", tex).strip()


def numbers_of(text: str) -> list:
    return sorted(set(NUMBER.findall(text)))


def number_in(number: str, corpus: str) -> bool:
    """The number occurs as a whole number, with `.` or `,` as the decimal separator."""
    for form in {number, number.replace(",", "."), number.replace(".", ",")}:
        if re.search(rf"(?<![\d.,]){re.escape(form)}(?![\d]|[.,]\d)", corpus):
            return True
    return False


def _find_work(lavoro: Path):
    from helpmewrite import state as st

    for work in (lavoro, *sorted(p.parent.parent for p in lavoro.rglob("progetto.md")
                                 if p.parent.name == STATE)):
        if st.state_path(work).is_file():
            return work
    return None


def check(tmp: Path) -> int:
    from helpmewrite import state as st

    tmp = tmp.resolve()
    lavoro = tmp / "lavoro"
    verifica = _verifica(tmp)
    results = []  # (ok, name, detail)

    def add(ok, name, detail=""):
        results.append((bool(ok), name, detail))

    # 1. originals
    try:
        recorded = json.loads((verifica / "hash-originali.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        recorded = None
    if recorded is None:
        add(False, "1 originals unchanged", f"{verifica / 'hash-originali.json'} not readable")
    else:
        now = _hashes(lavoro)
        changed = sorted(n for n in recorded if n in now and now[n] != recorded[n])
        gone = sorted(n for n in recorded if n not in now)
        add(not changed and not gone, "1 originals unchanged",
            f"{len(recorded)} files; changed: {changed}; missing: {gone}" if changed or gone
            else f"{len(recorded)} files with the same sha256")

    # 2. state
    work = _find_work(lavoro)
    state = None
    copy = None
    if work is None:
        add(False, "2 progetto.md valid, bozza-parziale, latex", "no .help-me-write/progetto.md")
    else:
        try:
            state = st.load_state(work)
        except st.StateError as exc:
            add(False, "2 progetto.md valid, bozza-parziale, latex", str(exc))
        else:
            ok = state.mode == "bozza-parziale" and state.format == "latex"
            add(ok, "2 progetto.md valid, bozza-parziale, latex",
                f"mode={state.mode} format={state.format} output={state.output} "
                f"chapters={[c.id for c in state.chapters]}")
            if state.output:
                copy = work / state.output
    state_dir = (work or lavoro) / STATE
    body = _read(state_dir / "progetto.md")

    # 3. materiale.md
    materiale = _read(state_dir / "materiale.md")
    lower = materiale.casefold()
    missing = [n for n in ARCHIVES + [NOTEBOOK] if n.casefold() not in lower]
    cronologia = _section(materiale, ["cronologia"])
    note = _section(materiale, ["note dell'autore"])
    problems = []
    if not materiale:
        problems.append("materiale.md missing")
    if missing:
        problems.append(f"not mentioned: {missing}")
    if not cronologia.strip():
        problems.append("no section Cronologia")
    if not note.strip():
        problems.append("no section Note dell'autore")
    elif not (re.search(r"batch", note, re.I) and re.search(r"pymapdl", note, re.I)):
        problems.append("Note dell'autore lacks the batch/PyMAPDL distinction")
    add(not problems, "3 materiale.md: archives, Cronologia, Note dell'autore",
        "; ".join(problems) if problems else "three zips, travi.ipynb, both sections, batch/PyMAPDL")

    # 4. working copy and layout
    copy_ok = copy is not None and copy.is_dir() and (copy / "main.tex").is_file()
    layout_block = copy_ok and any(BLOCK_BEGIN in _read(p) for p in copy.rglob("*.tex"))
    measure_detail, measured = "", {}
    if copy_ok:
        rules = state_dir / "linee-guida.yaml"
        workdir = Path(tempfile.mkdtemp(prefix="hmw-scenario-pdf-"))
        done = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "hmw.py"), "measure", str(copy / "main.tex"),
             "--rules", str(rules), "--workdir", str(workdir), "--json"],
            capture_output=True, text=True, timeout=900)
        try:
            measured = json.loads(done.stdout)
        except ValueError:
            measure_detail = f"measure exit {done.returncode}: {done.stderr.strip()[:200]}"
    wanted = ("chars_per_line", "lines_per_page", "page_numbers")
    by_rule = {c["rule"]: c for c in measured.get("checks", [])}
    bad = [f"{r}: {by_rule[r]['detail']}" if r in by_rule else f"{r}: not evaluated"
           for r in wanted if r not in by_rule or not by_rule[r]["ok"]]
    problems = []
    if not copy_ok:
        problems.append(f"no working copy with main.tex (state output: {state.output if state else None})")
    elif not layout_block:
        problems.append(f"no layout block ({BLOCK_BEGIN}) in the copy")
    if measure_detail:
        problems.append(measure_detail)
    elif copy_ok:
        problems += bad
    add(not problems, "4 layout block; measure chars_per_line, lines_per_page, page_numbers",
        "; ".join(problems) if problems
        else f"{measured.get('page_count')} pages; " + "; ".join(
            f"{r} ok" for r in wanted))

    # 5. conclusions
    corpus = ""
    conclusion_file = None
    if copy_ok:
        found = sorted((copy / "capitoli").glob("06_conclusioni.tex")) or \
            sorted(copy.rglob("06_conclusioni.tex"))
        conclusion_file = found[0] if found else None
        for p in sorted((copy / "capitoli").glob("0[1-5]_*.tex")):
            corpus += _read(p) + "\n"
    corpus += _read(state_dir / "materiale.md") + "\n" + _read(tmp / "risposte.md")
    if conclusion_file is None:
        add(False, "5 conclusions written, numbers traceable", "no 06_conclusioni.tex in the copy")
    else:
        text = conclusion_text(_read(conclusion_file))
        nums = numbers_of(text)
        untraced = [n for n in nums if not number_in(n, corpus)]
        problems = []
        if len(text) < MIN_CONCLUSION_CHARS:
            problems.append(f"{len(text)} characters of text (need {MIN_CONCLUSION_CHARS})")
        if untraced:
            problems.append(f"numbers not in chapters 1-5, materiale.md or risposte.md: {untraced}")
        add(not problems, "5 conclusions written, numbers traceable",
            "; ".join(problems) if problems
            else f"{len(text)} characters; {len(nums)} numbers, all traceable ({nums})")

    # 6. title page values
    main = _read(copy / "main.tex") if copy_ok else ""
    wrong = []
    for name, value in TITLE_VALUES.items():
        found = re.search(rf"\\newcommand\{{\\{name}\}}\{{([^}}]*)\}}", main)
        if not found:
            wrong.append(f"{name}: not found")
        elif found.group(1).strip() != value:
            wrong.append(f"{name}: {found.group(1).strip()!r}")
    add(not wrong, "6 title page \\newcommand values", "; ".join(wrong) if wrong
        else f"{len(TITLE_VALUES)} values as in risposte.md")

    # 7. chapter 3 keeps the batch distinction
    ch3 = sorted((copy / "capitoli").glob("03_*.tex")) if copy_ok else []
    add(bool(ch3) and re.search(r"batch", _read(ch3[0]), re.I),
        "7 chapter 3 of the copy still says batch",
        ch3[0].name if ch3 else "no 03_*.tex in the copy")

    # 8. cut proposal, not applied
    pages = measured.get("page_count")
    proposals = [p for p in sorted((state_dir / "revisioni").glob("*/tagli*.md"))] \
        if (state_dir / "revisioni").is_dir() else []
    sources = {p.relative_to(state_dir).as_posix(): _read(p) for p in proposals}
    sources["progetto.md"] = body
    tables = {}
    for name, text in sources.items():
        lines = [ln for ln in text.splitlines()
                 if ln.lstrip().startswith("|") and not re.match(r"^\s*\|[\s:|-]+\|?\s*$", ln)]
        rows = [ln for ln in lines if re.search(r"\d", ln)]  # a row with a number of lines
        if len(rows) >= 2 and re.search(r"cap|0[1-5][_-]|\.tex", "\n".join(lines), re.I):
            tables[name] = len(rows)
    applied = sorted(p.name for p in (copy.parent.glob(f"*-v[0-9]*-help-me-write")
                                      if copy else []) if p.is_dir())
    if pages is None:
        add(False, "8 cut proposal", "pages of the copy not measured")
    elif pages <= TARGET_PAGES:
        add(not applied, "8 cut proposal (not needed: copy within the limit)",
            f"{pages} pages" + (f"; unexpected version copies {applied}" if applied else ""))
    else:
        problems = []
        if not tables:
            problems.append(f"{pages} pages (> {TARGET_PAGES}) and no table of cuts with chapter "
                            "and lines in revisioni/*/tagli*.md or in progetto.md")
        if applied:
            problems.append(f"cuts were applied: {applied}")
        add(not problems, "8 cut proposal, not applied",
            "; ".join(problems) if problems
            else f"{pages} pages; table in {', '.join(f'{k} ({v} rows)' for k, v in tables.items())}")

    for ok, name, detail in results:
        print(f"{'PASS' if ok else 'FAIL'} {name}" + (f": {detail}" if detail else ""))
    failed = [r for r in results if not r[0]]
    print(f"{len(results) - len(failed)} of {len(results)} checks passed")
    return 1 if failed else 0


def main(argv) -> int:
    if len(argv) == 2 and argv[0] == "--setup":
        return setup(Path(argv[1]))
    if len(argv) == 2 and argv[0] == "--check":
        if not Path(argv[1], "lavoro").is_dir():
            print(f"error: {argv[1]}/lavoro not found: run --setup first", file=sys.stderr)
            return 2
        return check(Path(argv[1]))
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
