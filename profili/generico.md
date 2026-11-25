# Profile: generico

Fallback profile for every document type without a dedicated profile: papers, technical
reports, theses, project reports, legal acts. It assumes nothing: every rule comes from
the guidelines (call, regulation, template, author instructions) or from the user.

This file is also the template for a new profile: copy it to
`profili/<document-type>.md`, keep the eight `##` headings exactly as they are (skills
read the sections by these names) and write the `## Default guidelines` YAML block in the
schema of `skills/linee-guida/schema-linee-guida.md`, with `document_type` equal to the
file name without `.md`.

## Recognize

Choose this profile when no other profile matches the request, the guidelines or the
work folder, or when the user names a document type that has no profile.

## Typical structure

None by default. Use the structure the guidelines prescribe. When they prescribe none,
propose the usual structure of the document type the user named (for example, a paper:
abstract, introduction, related work, method, results, discussion, conclusion,
references) and ask the user to confirm it before using it.

## Default guidelines

No defaults: every rule comes from the guidelines or from the user.

```yaml
document_type: generico
```

## Interview prompts

Start each question from the material map; never ask a generic question the material
already answers.

- Purpose of the document and its audience (examiners, reviewers, a judge, a client).
- The main message or claim, in one or two sentences.
- For each section or chapter:
  - the salient points;
  - what the author did personally;
  - difficulties and results, with numbers;
  - images: which exist already (file path), which to generate (which diagram or
    chart), which are not needed.
- Sources the text relies on (files in the folder, `.bib` file, references the user
  names).
- Anything that must stay confidential.

## Tone

As the guidelines or the user prescribe; otherwise the formal register usual for the
document type and its audience. Consistent person and tense throughout; precise terms,
defined at first use; no filler or generic prose.

## Content checklist

- Clarity: each paragraph makes one clear point; sentences are not overloaded; terms and
  acronyms are defined at first use.
- Repetitions: no content repeated across sections, no word or phrase repeated without
  reason in nearby sentences.
- Coherence: what the introduction announces is developed in the body and taken up by
  the conclusion; claims, names and numbers are the same everywhere.
- Tone suited to the audience and to the document type.
- No `[DA VERIFICARE]` placeholders left: each one is reported as a question to the
  author.

## Citation needs

- Citation needed: data and numbers from the literature, definitions, results, state of
  the art, methods and tools of others, non-obvious claims.
- No citation: the author's own work and common knowledge of the field.
- Use the citation style the guidelines require, the same throughout.

## Writing budget

No fixed shares. A length the guidelines give for a part (`sections[].pages` in
`linee-guida.yaml`) is that part's budget. The rest of the maximum of `pages` is shared
among the other parts in proportion to the material that supports each (`materiale.md`);
opening and closing parts (abstract, introduction, conclusion) stay short. Propose the
shares with the outline and ask the user to confirm them.
