"""Set up and check the acceptance scenarios da-zero-word.md and ripresa.md. Needs no pytest.

    python tests/scenari/check_accettazione.py --setup da-zero|ripresa <folder> <expected-dir> <plugin>
        builds the example work folder (tests/fixtures/builders.py: build_example_work) in
        <folder>; the chapters the report should resemble (`attesi/`) and the expected
        results go to <expected-dir>, outside <folder>; <plugin> gets a copy of the plugin
        without tests/ and docs/. For `ripresa` the folder also holds the state after two
        approved chapters and the interview of the third.

    python tests/scenari/check_accettazione.py --check da-zero|ripresa <folder> <expected-dir>
        checks <folder> after the run; prints one line per check, exits 1 if any fails.
        For `ripresa`, <expected-dir>/sessione2.jsonl is the stream-json transcript of the
        second session.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "tests"), str(REPO / "scripts")]
PLUGIN_PARTS = [".claude-plugin", ".codex-plugin", ".agents", "skills", "profili", "scripts",
                "requirements.txt", "README.md"]
UNIBO = REPO / "tests" / "fixtures" / "linee-guida-unibo.yaml"
HMW = REPO / "scripts" / "hmw.py"

# Answers to the interview of the example, given in advance to a headless run (da-zero).
ANSWERS = """# Risposte all'intervista (tirocinio presso Acme S.r.l.)

Usa queste risposte per ogni capitolo; sono le sole informazioni oltre ai file.

- Contributo personale: ho scritto io il pacchetto `analisi` e ho lanciato le tre campagne
  di prova (base, ottimizzata, finale); il tutor ha scelto le metriche.
- Difficolta: la prima campagna aveva dati incompleti; li ho ripuliti in una settimana.
- Risultati: l'accuratezza e salita da 0,808 a 0,912 (file dati/metriche.csv).
- Immagini: un grafico a barre dell'accuratezza per campagna dai dati del CSV.
- Da non pubblicare: i nomi dei clienti di Acme.
- Introduzione: obiettivo concordato con il tutor all'inizio, raggiunto.
- Conclusioni: ho imparato a confrontare campagne di prova; resta aperto il test su dati reali.
- Frontespizio: anno accademico 2025/2026, Mario Rossi (matricola 0000123456), struttura
  Acme S.r.l., argomento "Diagnostica FEM con ML".
- Struttura: approvata cosi come la proponi; formato Word; font Times New Roman.
"""
# Facts of the interview already given in session 1 of `ripresa`; session 2 must not ask again.
NOTES = """# Intervista: Confronto (confronto)

## Giro 1, 2026-11-20

1. **Qual e stato il tuo contributo personale nel confronto delle campagne?**
   Risposta: "Ho scritto io il pacchetto analisi e confrontato le tre campagne di prova."
2. **Quali risultati contano, con i numeri?**
   Risposta: "L'accuratezza e salita da 0,808 a 0,912 (dati/metriche.csv)."
3. **Quali difficolta hai incontrato?**
   Risposta: "I dati della prima campagna erano incompleti, ci ho messo una settimana."

## Immagini
- non necessarie: il grafico e gia nel capitolo Attivita svolte

## Da non pubblicare
- i nomi dei clienti di Acme
"""
RESUME_KEYWORDS = ["contributo personale", "difficolt", "risultati contano", "numeri"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args) -> None:
    subprocess.run([sys.executable, str(HMW), *map(str, args)], check=True,
                   capture_output=True, text=True)


def prepare(folder: Path, expected: Path, plugin: Path) -> bool:
    for other in (expected, plugin):
        if folder in (other, *other.parents) or other in folder.parents:
            print(f"error: {other} and {folder} must not contain each other", file=sys.stderr)
            return False
    if plugin.exists() and any(plugin.iterdir()):
        print(f"error: {plugin} exists and is not empty", file=sys.stderr)
        return False
    for part in PLUGIN_PARTS:
        source = REPO / part
        if source.is_dir():
            shutil.copytree(source, plugin / part,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        elif source.is_file():
            plugin.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, plugin / part)
    expected.mkdir(parents=True, exist_ok=True)
    return True


def setup_resume(ex: dict) -> dict:
    """The state of case 3: five chapters, two approved, the third interviewed."""
    from fixtures.builders import EXAMPLE_TITLE_VALUES

    work = ex["folder"]
    state = work / ".help-me-write"
    capitoli = state / "capitoli"
    capitoli.mkdir(parents=True)
    run("state", "init", work, "--mode", "da-zero", "--format", "word")
    (state / "materiale.md").write_text(
        "# Materiale\n\n## Mappa\n| File | Contenuto | Capitolo |\n|---|---|---|\n"
        "| progetto/ | pacchetto Python `analisi`, 3 commit (2026-09-15 .. 2026-11-05) | attivita |\n"
        "| dati/metriche.csv | accuratezza e F1 di tre campagne | risultati, confronto |\n"
        "| diario.md | date del tirocinio | attivita |\n", encoding="utf-8")
    shutil.copyfile(UNIBO, state / "linee-guida.yaml")
    outline = [{"id": i, "title": t, "kind": k} for i, t, k in [
        ("attivita", "Attività svolte", "corpo"), ("risultati", "Risultati", "corpo"),
        ("confronto", "Confronto", "corpo"), ("introduzione", "Introduzione", "introduzione"),
        ("conclusioni", "Conclusioni", "conclusione")]]
    (state / "indice.json").write_text(json.dumps(outline, ensure_ascii=False), encoding="utf-8")
    run("state", "outline", work, "--from", state / "indice.json")
    (state / "frontespizio.json").write_text(json.dumps(EXAMPLE_TITLE_VALUES, ensure_ascii=False),
                                             encoding="utf-8")
    run("titlepage", ex["facsimile"], "--values", state / "frontespizio.json",
        "-o", state / "frontespizio.docx")
    run("state", "set", work, "outline_approved=true", "title_page_approved=true")
    names = {"attivita": "02-attivita.md", "risultati": "03-risultati.md"}
    run("chart", _spec(work), "-o", capitoli / "metriche.png")
    for cid, name in names.items():
        shutil.copyfile(ex["sources"] / name, capitoli / f"{cid}.md")
        run("state", "chapter", work, cid, "--status", "approvato",
            "--source", capitoli / f"{cid}.md")
    (capitoli / "confronto-intervista.md").write_text(NOTES, encoding="utf-8")
    run("state", "chapter", work, "confronto", "--status", "intervista-fatta",
        "--notes", capitoli / "confronto-intervista.md")
    return {"approved": {cid: sha(capitoli / f"{cid}.md") for cid in names},
            "next": {"phase": "scrittura", "chapter": "confronto"},
            "answered_keywords": RESUME_KEYWORDS}


def _spec(work: Path) -> Path:
    spec = work / ".help-me-write" / "capitoli" / "metriche.json"
    spec.write_text(json.dumps({
        "type": "bar", "language": "it", "annotate": True, "xlabel": "Campagna",
        "ylabel": "Accuratezza",
        "csv": {"file": "../../dati/metriche.csv", "x": "campagna", "y": ["accuracy"],
                "labels": {"accuracy": "Accuratezza"}}}), encoding="utf-8")
    return spec


def setup(kind: str, folder: Path, expected_dir: Path, plugin: Path) -> int:
    from fixtures.builders import build_example_work

    folder, expected_dir, plugin = folder.resolve(), expected_dir.resolve(), plugin.resolve()
    if not prepare(folder, expected_dir, plugin):
        return 2
    ex = build_example_work(folder)
    expected = {"scenario": kind, "git_dates": ["2026-09-15", "2026-10-10", "2026-11-05"]}
    if kind == "ripresa":
        expected.update(setup_resume(ex))
    else:
        (expected_dir / "risposte.md").write_text(ANSWERS, encoding="utf-8")
        expected["answers"] = str(expected_dir / "risposte.md")
    # the expected chapters never stay where the agent can read them
    shutil.move(str(folder / "attesi"), str(expected_dir / "attesi"))
    (expected_dir / "expected.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"example work folder in {folder}; expected results in {expected_dir}; "
          f"plugin copy {plugin}")
    return 0


def _assistant_text(transcript: Path) -> str:
    out = []
    for line in transcript.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") != "assistant":
            continue
        for part in event.get("message", {}).get("content", []):
            if part.get("type") == "text":
                out.append(part["text"])
            elif part.get("type") == "tool_use" and "question" in json.dumps(part).lower():
                out.append(json.dumps(part.get("input", {}), ensure_ascii=False))
    return "\n".join(out)


def check(kind: str, folder: Path, expected_dir: Path) -> int:
    from helpmewrite.measure import measure
    from helpmewrite.rules import load_rules
    from helpmewrite.state import load_state, next_step
    import docx

    folder, expected_dir = folder.resolve(), expected_dir.resolve()
    expected = json.loads((expected_dir / "expected.json").read_text(encoding="utf-8"))
    results = []

    def add(ok, name, detail=""):
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))

    state_dir = folder / ".help-me-write"
    try:
        state = load_state(folder)
    except Exception as exc:  # no state file: the run did nothing
        print(f"FAIL  state file readable  ({exc})")
        return 1
    if kind == "da-zero":
        add(state.mode == "da-zero" and state.format == "word", "state: da-zero, word",
            f"{state.mode}, {state.format}")
        add(len(state.chapters) >= 3 and all(c.status in ("approvato", "revisionato")
                                             for c in state.chapters),
            "every chapter approved", ", ".join(f"{c.id}={c.status}" for c in state.chapters))
        add((state_dir / "materiale.md").is_file(), ".help-me-write/materiale.md exists")
        outputs = sorted(p for p in folder.glob("*.docx")
                         if p.name != "Facsimile_relazione_di_fine_tirocinio.docx")
        add(bool(outputs), "a .docx was produced", ", ".join(p.name for p in outputs))
        if outputs:
            out = outputs[0]
            m = measure(out, load_rules(UNIBO), folder / ".help-me-write" / "misura")
            for c in m.checks:
                add(c.ok, f"measure {c.rule}", c.detail[:90])
            xml = zipfile.ZipFile(out).read("word/document.xml").decode("utf-8")
            text = re.sub(r"<[^>]+>", "", xml)  # title page values may sit in tables or boxes
            add("Mario Rossi" in text and "Acme" in text, "title page values present")
            add(len(docx.Document(str(out)).inline_shapes) >= 1, "a figure is in the document")
            add(all(w in text for w in ("Introduzione", "Conclusioni")),
                "introduction and conclusion present")
        add(bool(state.fingerprints), "state recorded the output (fingerprints)")
    else:
        for cid, digest in expected["approved"].items():
            add(sha(state_dir / "capitoli" / f"{cid}.md") == digest,
                f"approved chapter {cid} unchanged")
        chapters = {c.id: c for c in state.chapters}
        add(chapters["confronto"].status in ("scritto", "approvato"),
            "third chapter written in session 2", chapters["confronto"].status)
        source = chapters["confronto"].source
        text = (folder / source).read_text(encoding="utf-8") if source else ""
        add(bool(source) and "0,912" in text and "0,808" in text,
            "chapter uses the numbers of the notes")
        transcript = expected_dir / "sessione2.jsonl"
        add(transcript.is_file(), "transcript of session 2 present")
        if transcript.is_file():
            said = _assistant_text(transcript).lower()
            asked = [k for k in expected["answered_keywords"]
                     if any(k in s for s in said.split("?")[:-1])]
            add(not asked, "session 2 does not ask again what the notes answer", ", ".join(asked))
        step = next_step(folder, load_state(folder))
        add(step["phase"] != "scrittura" or step["chapter"] != "confronto",
            "next step moved past the third chapter", f"{step['phase']} {step['chapter']}")
    return 0 if all(results) else 1


def main(argv) -> int:
    if len(argv) == 5 and argv[0] == "--setup" and argv[1] in ("da-zero", "ripresa"):
        return setup(argv[1], Path(argv[2]), Path(argv[3]), Path(argv[4]))
    if len(argv) == 4 and argv[0] == "--check" and argv[1] in ("da-zero", "ripresa"):
        return check(argv[1], Path(argv[2]), Path(argv[3]))
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
