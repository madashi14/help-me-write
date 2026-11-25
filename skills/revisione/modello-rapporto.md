# Template of the review report (`rapporto.md`)

The `revisione` skill writes `<rev>/rapporto.md` with these seven sections, in this order,
in the user's language. Headings are given here in English with their Italian wording;
use the wording of the user's language. Never drop a section: an empty one says so in one
line ("Nessuna", "None"). The `revisione-bibliografia` skill, run alone, writes only the
title lines, a short summary and the Bibliography section.

Sources, all in `<rev>`: `measure.json` and `measure-formattato.json`, `layout.json`, the
edits files and the result of `track`, `note-revisore.md`, `note-bibliografia.md`.

Never copy a password or other secret from the document: write where it is ("the password
in ¶ 33") instead.

---

```markdown
# Revisione di <document file name> (<date>)

Documento: <path> · Linee guida: <path of linee-guida.yaml> · Profilo: <profile>
Revisori: principale (<subagent | same session>), bibliografia (<subagent | same session | not run>)

## Riepilogo

- File prodotti: <corrected copy>, <formatted copy>, <PDF of differences>, questo
  rapporto (<rev>). Only the files that exist.
- <N> correzioni applicate, <C> commenti nel documento, <M> da sistemare a mano,
  <Q> domande per te.
- I problemi principali, uno per riga, al massimo cinque.

## Forma

| Regola | Esito | Dettaglio | Impostazioni consigliate |
|---|---|---|---|
| Caratteri per riga (`chars_per_line`) | ✗ | <measured> caratteri per riga (ammessi <min>–<max>) | <font> <size> pt, margini sinistro e destro <cm> cm |

Dopo la formattazione (<formatted copy>): <the checks whose outcome changed>.

<Form findings of note-revisore.md: section order, title page.>

## Lingua

| ¶ | Prima | Dopo | Motivo |
|---|---|---|---|
| 12 | progetazione | progettazione | refuso |

<Language findings of note-revisore.md, with the comments placed: acronyms, figures and
tables, terms.>

## Contenuto

- <checklist item>: ✓ | <problem, where, and the comment placed in the copy>

## Bibliografia

Ricerca online: <usata | non disponibile: perché>. Fonti locali: <PDF letti>.

| Citazione | Frase (¶) | Esito | Verificata su | Passaggio della fonte (pagina) | Nota |
|---|---|---|---|---|---|
| [5] | «… del 25% …» (¶ 40) | non supportata | testo completo | «… del 15% …» (p. 4) | <nota> |

| ¶ | Prima | Dopo | Motivo |
|---|---|---|---|
| 88 | (2015) | (2016) | anno errato: 2016 nella fonte (p. 1) |

### Citazioni mancanti

- ¶ 52: «…» — <perché serve una fonte>; <fonte proposta | nessuna fonte nella cartella>

### Coerenza della bibliografia

- <one line per entry, then cited but missing, never cited, style>

<Or: Non eseguita: <reason>.>

## Da sistemare a mano

| ¶ | Testo | Modifica prevista | Perché non è stata applicata |
|---|---|---|---|

## Domande per te

1. <question> (¶ 40)
```

## How to fill each section

- **Summary.** Paths relative to the work folder. The main problems come first from
  content and the rules of the guidelines, then form, then language.
- **Form.** One row per check of `measure.json`, in its order. Rule: a readable name and
  the check id exactly as `measure.json` writes it, in backticks (`section:indice:present`).
  Outcome: ✓ when `ok` is true, ✗ when it is false (with "not checked" and the reason
  when the detail says it could not be evaluated). Detail: the measured value against the allowed one, in the
  user's language. Recommended settings, for a failed check:
  - font, size, lines per page, characters per line: from `layout.json` (font and size,
    margins in cm, exact line spacing = the line pitch in pt, paragraph spacing 0);
  - page numbers: a centred number in the footer;
  - a missing section: what to add and where (a table of contents after the title page);
  - a section too long: how many pages to cut.

  Then the line "after formatting" from `measure-formattato.json`, when it exists.
- **Language.** Every applied edit of the main reviewer (`"by": "revisore"`) with a
  `replace`: paragraph, `find` (Before),
  `replace` (After, "(eliminato)" when empty), `reason`. A deleted secret is written
  "(credenziale rimossa)", never its text. Then the language findings of the notes.
- **Content.** One line per item of `## Content` in the notes, with the comments placed
  in the copy (paragraph and gist).
- **Bibliography.** From `note-bibliografia.md`, translated: its first line (online
  search used or not, local sources), the table of `## Citations` (one row per citation,
  every quoted passage and page kept word for word), then the applied edits by
  `bibliografia` with a `replace` (Before/After table), then `## Missing citations` and
  `## Bibliography consistency`. Or "not run" with the reason (the skill is not
  installed, the user excluded it). Never write "verified" or "supported" where the
  notes do not.
- **To fix by hand.** Every `failed` and `conflicts` entry of `track`, with the reason in
  plain words. For LaTeX also every comment (file:line), since sources get none. For a
  PDF draft every proposed correction (page, text, proposal).
- **Questions for you.** The questions of `note-revisore.md`, then one for each problem
  of `note-bibliografia.md` only the author can solve: a missing citation (which source?),
  an entry not found (where does it come from?), a claim its source does not support
  (correct the claim or the source?). Numbered, each with where it applies. Answering
  them starts a new review cycle.
