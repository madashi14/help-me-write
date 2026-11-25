# Scenario: resume after two chapters (skill `help-me-write`, spec §9 case 3)

To be run later with an agent (Task 14). `tests/test_acceptance.py`
(`test_case3_resume_after_two_chapters`) proves the state side without an LLM; this
scenario checks that a second session resumes from the state and does not ask again what
the notes already answer.

## Setup

```
python <repo>/tests/scenari/check_accettazione.py --setup ripresa <tmp>/lavoro <tmp>/atteso <tmp>/plugin
```

`<tmp>/lavoro` holds the example work folder and the state of a report in Word:

- five chapters: `attivita` and `risultati` are `approvato` (sources in
  `.help-me-write/capitoli/`), `confronto` is `intervista-fatta` with its notes
  `.help-me-write/capitoli/confronto-intervista.md`, then `introduzione` and
  `conclusioni` are `da-fare`;
- `materiale.md`, `linee-guida.yaml` (Unibo), the approved outline and title page;
- `hmw state show --json` gives `next = {"phase": "scrittura", "chapter": "confronto"}`.

`<tmp>/atteso` holds `expected.json` (SHA-256 of the two approved chapters and the
keywords of the questions the notes already answer).

## Run

Two sessions in `<tmp>/lavoro`. The first only proves that the folder is resumable (it
makes no change); the second is the run under test.

```
claude -p --plugin-dir <tmp>/plugin --add-dir <tmp>/plugin --allowedTools "Bash(python:*) Bash(python3:*)" --permission-mode acceptEdits "Dove eravamo rimasti con la relazione? Dimmi solo il prossimo passo, senza modificare nulla."
```

```
claude -p --plugin-dir <tmp>/plugin --add-dir <tmp>/plugin --allowedTools "Bash(python:*) Bash(python3:*)" --permission-mode acceptEdits --output-format stream-json --verbose "Riprendi la relazione da dove l'avevamo lasciata. Considera approvato il capitolo che scrivi e fermati dopo di esso: non fare ora l'introduzione." > <tmp>/atteso/sessione2.jsonl
```

If `claude -p` is not usable, give a fresh subagent only the text of
`skills/help-me-write/SKILL.md` (with its folder path) and each request.

## Expected

```
python <repo>/tests/scenari/check_accettazione.py --check ripresa <tmp>/lavoro <tmp>/atteso
```

1. Session 1 names the phase `scrittura` and the chapter `confronto`, and changes nothing.
2. Session 2 does not redo the title page, the outline or the interviews of the first
   two chapters: their files are byte-identical (SHA-256 from setup).
3. It writes `confronto` from the notes: the state moves to `scritto` or `approvato`, the
   source exists and uses the numbers of the notes (0,808 and 0,912).
4. It does not ask again what the notes answer (personal contribution, difficulties,
   which results count, the numbers): the checker looks for these in the questions of the
   assistant in `sessione2.jsonl`. At most it asks something new (e.g. the figure).
5. The next step in the state is no longer `scrittura` of `confronto`.

Read also: `[DA VERIFICARE: ...]` for what the notes do not say; no client name (the notes
say not to publish them).

## Results

Not run yet.
