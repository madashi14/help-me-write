# Scenario: guidelines from the Unibo facsimile (skill `linee-guida`)

Checks that an agent with the plugin turns the Unibo facsimile into a valid
`.help-me-write/linee-guida.yaml` in the work folder, with the values of
`tests/fixtures/linee-guida-unibo.yaml`.

## Setup

A new temporary folder containing only a copy of
`docs/riferimenti/Facsimile_relazione_di_fine_tirocinio.docx`. Run everything from that
folder. `<repo>` is the absolute path of this repository.

## Run

```
claude -p "Estrai le linee guida dal facsimile in questa cartella e salvale. Confermo il profilo e la scheda che estrai: salva il file senza chiedere." --plugin-dir <repo> --add-dir <repo> --allowedTools "Bash(python:*) Bash(python3:*)" --permission-mode acceptEdits
```

- A headless run cannot answer the skill's confirmation questions, so the prompt
  confirms in advance.
- A headless run cannot answer permission prompts either. Without `--add-dir <repo>`
  (read the skill's schema and the profiles) and `--allowedTools` for `python` (run
  `hmw.py`), the agent can read nothing and saves nothing: interactively, the user
  approves these two prompts instead.
- Add `--output-format stream-json --verbose > <file outside the folder>` to keep the
  transcript.
- If `claude -p` is not usable, give a fresh subagent only the text of
  `skills/linee-guida/SKILL.md` (with its folder path) and the same request.

## Expected

Pass/fail:

1. `.help-me-write/linee-guida.yaml` exists in the temporary folder and
   `python <repo>/scripts/hmw.py rules validate .help-me-write/linee-guida.yaml` exits 0.
2. It equals the fixture on `pages` (10–30), `font_size_pt` (12), `lines_per_page`
   (30–35), `chars_per_line` (60–70), `page_numbers` (true) and on the names of the
   required sections, in order: frontespizio, indice, introduzione, corpo, conclusione.

Also expected (read the file and the final answer):

- `document_type: relazione-tirocinio`, `format: null`, `fonts` Times New Roman, Courier,
  Helvetica; `allegati` present with `required: false`; introduzione and conclusione
  with `pages` 1–2; `title_page_template` and `source` naming the facsimile.
- Values not taken from the facsimile carry `# profile default` (or `# user`).
- The scheda is shown in Italian, follows the block of spec §9 and marks profile
  defaults; the draft `.help-me-write/linee-guida.bozza.yaml` no longer exists.
- Nothing is written outside the temporary folder; the facsimile is unchanged.

## Check

From the temporary folder:

```
python <repo>/scripts/hmw.py rules validate .help-me-write/linee-guida.yaml
python - <repo> <<'EOF'
import sys
from pathlib import Path
import yaml

repo = Path(sys.argv[1])
got = yaml.safe_load(Path(".help-me-write/linee-guida.yaml").read_text(encoding="utf-8"))
exp = yaml.safe_load((repo / "tests/fixtures/linee-guida-unibo.yaml").read_text(encoding="utf-8"))

def required(d):
    return [s["name"] for s in d.get("sections") or [] if s.get("required", True)]

bad = [k for k in ("pages", "font_size_pt", "lines_per_page", "chars_per_line", "page_numbers")
       if got.get(k) != exp.get(k)]
if required(got) != required(exp):
    bad.append(f"required sections {required(got)}")
print("OK" if not bad else f"MISMATCH: {bad}")
EOF
```
