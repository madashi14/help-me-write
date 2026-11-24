# Profile: relazione-tirocinio

Internship report ("relazione di fine tirocinio", curricular or not) written by a
university student at the end of an internship in a company, public body or lab.
Italian document type: section names and headings below are Italian; for a report in
another language translate them into the document's language.

## Recognize

Choose this profile when one or more of these appear in the request, the guidelines or
the work folder:

- the words "tirocinio", "stage", "internship", "relazione di fine tirocinio",
  "relazione finale di tirocinio", "progetto formativo";
- a host organization ("azienda ospitante", "struttura ospitante", "ente ospitante"),
  a company tutor or an academic tutor ("tutor aziendale", "tutor accademico",
  "referente");
- university guidelines or a facsimile for the end-of-internship report (CFU, "Corso di
  Studio", signatures of student and host);
- material of an internship: activity diary, timesheets, the host's project repository,
  weekly reports to the tutor.

Not this profile: a degree thesis ("tesi di laurea"), a paper or a project report for an
exam — use `generico` until a dedicated profile exists.

## Typical structure

1. **Frontespizio** — title page; universities often impose a fixed model (fill it in,
   do not redesign it).
2. **Indice** — table of contents.
3. **Introduzione** — objectives of the internship, main activities, results achieved
   in terms of knowledge, experience and methods learned; short.
4. **Corpo** — the internship in chronological or development order: context (host,
   team, project, the student's role), then the activities phase by phase, each with
   what the student did, problems met, decisions and results. Usually several
   chapters, no heading called "Corpo".
5. **Conclusione** — salient aspects and results of the internship, what was learned,
   what remains open.
6. **Bibliografia / Sitografia** — only if sources are cited.
7. **Allegati** — optional annexes (diagrams, extra tables, code excerpts the host
   allows to publish).

## Default guidelines

Structure only. Numbers (pages, font, lines, characters) differ between universities and
departments: they come from the guidelines document or from the user, never from here.

```yaml
document_type: relazione-tirocinio
sections:
  - name: frontespizio
    required: true
    headings: []
  - name: indice
    required: true
    headings: [indice, sommario]
  - name: introduzione
    required: true
    headings: [introduzione]
  - name: corpo
    required: true
    headings: []
  - name: conclusione
    required: true
    headings: [conclusione, conclusioni]
  - name: allegati
    required: false
    headings: [allegati, appendice]
```

## Interview prompts

Start each question from the material map; never ask a generic question the material
already answers.

- Context: host organization, team, project, your role, company and academic tutors,
  dates and length of the internship.
- Objectives agreed at the start (training project): which were reached, changed or
  dropped, and why.
- Timeline: the phases or weeks of the internship and what happened in each.
- For each phase or chapter:
  - the salient points;
  - what you did personally, as distinct from the team or the tutor;
  - difficulties, how you solved them, decisions you took;
  - results, with numbers (times, sizes, performance, defects, users);
  - images: which exist already (file path), which to generate (which diagram or
    chart), which are not needed.
- Tools, technologies and methods you used or learned, and where they come from
  (documentation, courses, colleagues).
- What you learned (knowledge, experience, methods) and what you would do differently.
- What must stay confidential: names, client data, figures, code the host does not
  allow to publish.

## Tone

- A diary of the internship experience in chronological or development order, not a
  presentation of the company, the product or a technology.
- First person singular for the student's own activities ("ho progettato", "ho
  misurato"); first person plural or impersonal only for team work, saying who did what.
- Past tense for the activities; present tense for facts that still hold.
- Formal, precise and technical; concrete facts and numbers from the material instead
  of adjectives; no promotional language about the host, no generic filler.

## Content checklist

- The personal contribution stands out: for every activity it is clear what the student
  did personally, decided or proposed, and any originality is made explicit.
- The text is a chronological or development diary, not a presentation: the body
  follows the phases of the internship and stays on the student's experience.
- Objectives, activities and results are consistent between introduction, body and
  conclusion: the introduction announces what the body describes, the conclusion
  reports the results of those same activities, and the numbers match everywhere.
- No confidential information of the host: no credentials (passwords, keys, tokens),
  client or personal data, internal figures not cleared for publication, proprietary
  code copied in full.
- No `[DA VERIFICARE]` placeholders left: each one is reported as a question to the
  author.

## Citation needs

- No citation: the activities the student carried out — what they did, configured,
  wrote, measured, decided or observed during the internship — and common knowledge of
  the field. Most of the report is of this kind: never ask for a citation there.
- Citation needed: technologies, tools, frameworks, standards and methods made by
  others, where the text introduces, defines or describes them (official
  documentation, paper or book); data and numbers taken from third parties
  (literature, vendors, reports); claims of third parties, state of the art, results of
  others, non-obvious statements.
- Internal documents of the host may be cited only if the host allows it; otherwise
  describe them without details.
