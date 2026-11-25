"""Static checks on skills (skills/*/SKILL.md) and document profiles (profili/*.md)."""
import re

import pytest
import yaml

from conftest import ROOT
from helpmewrite.rules import parse_rules

SKILLS = sorted((ROOT / "skills").glob("*/SKILL.md"))
PROFILES = sorted((ROOT / "profili").glob("*.md"))

PROFILE_HEADINGS = [
    "## Recognize", "## Typical structure", "## Default guidelines", "## Interview prompts",
    "## Tone", "## Content checklist", "## Citation needs",
]
SKILL_DIR_PLACEHOLDER = "<this skill's directory>/"

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)
_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_CODE_SPAN = re.compile(r"`([^`\n]+)`")
_FENCE = re.compile(r"^```.*?^```", re.S | re.M)
_REL_TOKEN = re.compile(r"(?:^|\s)(\.\.?/\S+)")


def _split(skill_md):
    m = _FRONTMATTER.match(skill_md.read_text(encoding="utf-8"))
    assert m, f"{skill_md}: no YAML frontmatter between --- lines"
    return yaml.safe_load(m.group(1)), m.group(2)


def relative_paths(body: str) -> list[str]:
    """Files the body cites by a path relative to the skill folder.

    Markdown link targets that are not URLs or anchors, and code spans that start with
    ./, ../ or <this skill's directory>/ (the placeholder is dropped). Paths in fenced
    blocks are examples, not citations.
    """
    body = _FENCE.sub("", body)
    paths = []
    for target in _MD_LINK.findall(body):
        if not re.match(r"[a-z][a-z0-9+.-]*:|#", target):
            paths.append(target.split("#")[0])
    for span in _CODE_SPAN.findall(body):
        span = span.replace(SKILL_DIR_PLACEHOLDER, " ")
        paths += [t for t in _REL_TOKEN.findall(span) if "<" not in t]
    return paths


def test_expected_skills_and_profiles_exist():
    for name in ["linee-guida", "revisione", "revisione-bibliografia", "help-me-write",
                 "analisi-materiale"]:
        assert (ROOT / "skills" / name / "SKILL.md") in SKILLS
    assert {p.stem for p in PROFILES} >= {"relazione-tirocinio", "generico"}


@pytest.mark.parametrize("skill_md", SKILLS, ids=lambda p: p.parent.name)
def test_skill_frontmatter(skill_md):
    meta, _ = _split(skill_md)
    assert meta["name"] == skill_md.parent.name
    description = meta["description"]
    assert isinstance(description, str) and description.startswith("Use when")
    assert len(description) <= 500  # Codex truncates longer descriptions


@pytest.mark.parametrize("skill_md", SKILLS, ids=lambda p: p.parent.name)
def test_skill_relative_paths_exist(skill_md):
    _, body = _split(skill_md)
    missing = [p for p in relative_paths(body) if not (skill_md.parent / p).exists()]
    assert not missing, f"{skill_md}: cited files not found: {missing}"


def test_relative_paths_parser():
    body = ("See [schema](schema.md) and [web](https://x.org), [top](#a).\n"
            "Run `python <this skill's directory>/../../scripts/hmw.py extract` and "
            "`../../profili/generico.md`; not `.help-me-write/linee-guida.yaml` "
            "nor `../../profili/<name>.md`.\n"
            "```\n[x](inside-fence.md)\n```\n")
    assert relative_paths(body) == ["schema.md", "../../scripts/hmw.py",
                                    "../../profili/generico.md"]


def test_linee_guida_description_keywords():
    meta, _ = _split(ROOT / "skills" / "linee-guida" / "SKILL.md")
    for word in ["guidelines", "regolamento", "template", "facsimile", "page limits", "font",
                 "formatting rules"]:
        assert word in meta["description"], word


def test_revisione_description_triggers():
    meta, _ = _split(ROOT / "skills" / "revisione" / "SKILL.md")
    for word in ["finished draft", "rivedi", "revisione", "correggi la bozza", "review my draft",
                 "proofread", "Not for writing"]:
        assert word in meta["description"], word


def test_revisore_prompt_contract():
    text = (ROOT / "skills" / "revisione" / "prompt-revisore.md").read_text(encoding="utf-8")
    placeholders = set(re.findall(r"\{([A-Z_]+)\}", text))
    assert placeholders == {"EXTRACT", "MEASURE", "GUIDELINES", "PROFILE", "ANSWERS",
                            "EDITS_OUT", "NOTES_OUT", "DOCUMENT_LANGUAGE", "USER_LANGUAGE"}
    for needed in ["## Form", "## Content", "## Questions for the author", '"by": "revisore"',
                   "## Content checklist", "Never invent", "[DA VERIFICARE"]:
        assert needed in text, needed


def test_revisione_bibliografia_description_triggers():
    meta, _ = _split(ROOT / "skills" / "revisione-bibliografia" / "SKILL.md")
    for word in ["bibliografia", "citazioni", "fonti", "controlla le citazioni",
                 "check my references", "check my citations", "revisione skill"]:
        assert word in meta["description"], word


def test_revisore_bibliografia_prompt_contract():
    folder = ROOT / "skills" / "revisione-bibliografia"
    text = (folder / "prompt-revisore-bibliografia.md").read_text(encoding="utf-8")
    placeholders = set(re.findall(r"\{([A-Z_]+)\}", text))
    assert placeholders == {"EXTRACT", "BIB", "PROFILE", "GUIDELINES", "BIBFILE", "SOURCES",
                            "SOURCE_TEXTS", "HMW", "EDITS_OUT", "NOTES_OUT",
                            "DOCUMENT_LANGUAGE", "USER_LANGUAGE"}
    for needed in ["## Citations", "## Missing citations", "## Bibliography consistency",
                   '"by": "bibliografia"', "## Citation needs", "pdftext",
                   "title, authors, year and DOI", "not verifiable", "possible invented or wrong",
                   "page", "author's own work"]:
        assert needed in text, needed
    # pdftext output goes to a file, never judged when cut off (final review, finding 6)
    flat = " ".join(text.split())
    for needed in ['pdftext "<file>.pdf" -o "{SOURCE_TEXTS}/', "--pages A-B",
                   "Never judge a citation from text that was cut off",
                   "Never print a whole PDF in the shell"]:
        assert needed in flat, needed
    # the document's own PDFs are never sources (finding 7)
    for needed in ["`*-differenze.pdf`", "`*-revisionato*` folder", "excluded_sources",
                   "named like the document"]:
        assert needed in flat, needed
    # a reference-data replace only from a value read on the source itself (ruling R15)
    rule = re.search(r"^   - A correction of reference data.*?(?=^   - )", text, re.S | re.M)
    assert rule, "the reference-data correction rule"
    rule = " ".join(rule.group(0).split())
    for needed in ["first page of a local PDF", "record you opened", "search-result snippet",
                   "becomes a comment", "where you saw it"]:
        assert needed in rule, needed
    _, body = _split(folder / "SKILL.md")
    assert "./prompt-revisore-bibliografia.md" in body
    for output in ["bib.json", "edits-bibliografia.json", "note-bibliografia.md"]:
        assert output in body, output


def test_revisione_runs_the_bibliography_reviewer():
    _, body = _split(ROOT / "skills" / "revisione" / "SKILL.md")
    assert "](../revisione-bibliografia/SKILL.md)" in body
    for output in ["<rev>/bib.json", "<rev>/edits-bibliografia.json",
                   "<rev>/note-bibliografia.md", '--edits "<rev>/edits-bibliografia.json"']:
        assert output in body, output


def test_rapporto_template_sections_in_order():
    text = (ROOT / "skills" / "revisione" / "modello-rapporto.md").read_text(encoding="utf-8")
    template = re.search(r"^```markdown\n(.*?)^```", text, re.S | re.M).group(1)
    headings = [line[3:] for line in template.splitlines() if line.startswith("## ")]
    assert headings == ["Riepilogo", "Forma", "Lingua", "Contenuto", "Bibliografia",
                        "Da sistemare a mano", "Domande per te"]


def _profile_sections(profile):
    text = profile.read_text(encoding="utf-8")
    lines = text.splitlines()
    return text, [line.rstrip() for line in lines if line.startswith("## ")]


@pytest.mark.parametrize("profile", PROFILES, ids=lambda p: p.stem)
def test_profile_headings(profile):
    _, headings = _profile_sections(profile)
    for heading in PROFILE_HEADINGS:
        assert headings.count(heading) == 1, f"{profile.name}: {heading!r} must appear once"


@pytest.mark.parametrize("profile", PROFILES, ids=lambda p: p.stem)
def test_profile_default_guidelines_are_valid_rules(profile):
    text, _ = _profile_sections(profile)
    section = text.split("\n## Default guidelines\n", 1)[1].split("\n## ", 1)[0]
    block = re.search(r"^```yaml\n(.*?)^```", section, re.S | re.M)
    assert block, f"{profile.name}: no ```yaml block under ## Default guidelines"
    rules = parse_rules(yaml.safe_load(block.group(1)))
    assert rules.document_type == profile.stem


# --- command lines in skills and prompts (final review, recommendation 3) ---------------

PROMPTS = [ROOT / "skills" / "revisione" / "prompt-revisore.md",
           ROOT / "skills" / "revisione-bibliografia" / "prompt-revisore-bibliografia.md"]
_HMW_TOKEN = re.compile(r"(?:^|\s)(?:hmw|\{HMW\}|\S*scripts/hmw\.py)\s+(?!<command>)\S")
_PATH_OPTIONS = {"-o", "--output", "--rules", "--workdir", "--layout", "--edits", "--sources",
                 "--bib"}


def command_lines(text: str) -> list[str]:
    """`hmw <cmd> …`, `{HMW} <cmd> …` and `…/scripts/hmw.py <cmd> …` in code spans and in
    fenced blocks (one per line); the generic `hmw.py <command>` is left out."""
    candidates = [line for block in _FENCE.findall(text) for line in block.splitlines()]
    candidates += _CODE_SPAN.findall(_FENCE.sub("", text))
    return [c.strip() for c in candidates if _HMW_TOKEN.search(c)]


def hmw_arguments(line: str) -> list[str]:
    """The arguments after hmw, placeholders replaced by dummy values."""
    import shlex

    line = line.replace("{HMW}", "hmw")
    line = re.sub(r"<[^<>]*>", "x", line)
    line = re.sub(r"\{[A-Z_]+\}", "x", line)
    tokens = shlex.split(line)
    start = next(i for i, t in enumerate(tokens) if t == "hmw" or t.endswith("hmw.py"))
    return tokens[start + 1:]


def _documents():
    return SKILLS + PROMPTS


@pytest.mark.parametrize("document", _documents(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_skill_command_lines_parse(document):
    from helpmewrite import cli

    parser = cli._build_parser()
    lines = command_lines(document.read_text(encoding="utf-8"))
    if document.name == "SKILL.md" or "bibliografia" in document.name:
        assert lines, f"{document}: no hmw command found"
    for line in lines:
        try:
            parser.parse_args(hmw_arguments(line))
        except SystemExit:
            pytest.fail(f"{document.name}: the CLI rejects `{line}`")


def test_command_line_helpers():
    text = ("Run `hmw doctor` and `python <this skill's directory>/../../scripts/hmw.py "
            "<command>`.\n```\nhmw track \"<doc>\" --edits \"<rev>/e.json\" -o \"<copy>\"\n```\n"
            "Read with `{HMW} pdftext \"<file>.pdf\" -o \"{SOURCE_TEXTS}/<file name>.json\"`.")
    lines = command_lines(text)
    assert lines == ['hmw track "<doc>" --edits "<rev>/e.json" -o "<copy>"', "hmw doctor",
                     '{HMW} pdftext "<file>.pdf" -o "{SOURCE_TEXTS}/<file name>.json"']
    assert hmw_arguments(lines[2]) == ["pdftext", "x.pdf", "-o", "x/x.json"]


@pytest.mark.parametrize("skill_md", SKILLS, ids=lambda p: p.parent.name)
def test_skill_paths_are_anchored(skill_md):
    """Paths in commands are absolute placeholders: the shell's folder may not be <work>."""
    _, body = _split(skill_md)
    spans = _CODE_SPAN.findall(_FENCE.sub("", body))
    for span in spans:
        for m in re.finditer(r"\.help-me-write/", span):
            assert span[:m.start()].endswith("<work>/"), f"{skill_md.parent.name}: `{span}`"
        for m in re.finditer(r"(?<![\w>/])\.\./\.\./profili/", span):
            assert span[:m.start()].endswith("<this skill's directory>/"), span
    for line in command_lines(body):
        tokens = line.split()
        for option, value in zip(tokens, tokens[1:]):
            if option in _PATH_OPTIONS:
                assert re.match(r'"(<work>|<rev>|<parent>|<copy>|<sources>|<bibfile>)', value), \
                    f"{skill_md.parent.name}: {option} {value} in `{line}`"


@pytest.mark.parametrize("skill_md", [ROOT / "skills" / "revisione" / "SKILL.md",
                                      ROOT / "skills" / "revisione-bibliografia" / "SKILL.md"],
                         ids=lambda p: p.parent.name)
def test_review_folder_has_seconds_and_latex_outputs_beside_the_project(skill_md):
    _, body = _split(skill_md)
    assert "<YYYY-MM-DD-HHMMSS>" in body and "%Y-%m-%d-%H%M%S" in body
    assert "HHMM>" not in body and "%H%M'" not in body
    assert '-o "<parent>/<name>-differenze.pdf"' in body
    assert "`<parent>/<name>-revisionato`" in body
    flat = " ".join(body.split())
    assert "output that already exists (use the next free name the message gives)" in flat


def test_bib_prompt_unique_source_names():
    text = (ROOT / "skills" / "revisione-bibliografia"
            / "prompt-revisore-bibliografia.md").read_text(encoding="utf-8")
    assert "replaced by __" in text


# --- entry skill and material analysis (Part 2, Task 11) --------------------------------

def test_skills_use_known_commands():
    """Every `hmw <command>` cited in a SKILL.md or a prompt exists in cli._COMMANDS."""
    from helpmewrite import cli

    for document in SKILLS + PROMPTS:
        for line in command_lines(document.read_text(encoding="utf-8")):
            command = hmw_arguments(line)[0]
            assert command in cli._COMMANDS, f"{document.parent.name}: `{line}`"


def test_entry_skill_rules():
    _, body = _split(ROOT / "skills" / "help-me-write" / "SKILL.md")
    flat = " ".join(body.split())
    for needed in ["LaTeX or Word", "never ask again", "state modified", "[DA VERIFICARE",
                   "give them this `<work>` (absolute) as their work folder",
                   "the working copy's main `.tex`"]:
        assert needed in flat, needed


def test_material_skill_and_template():
    folder = ROOT / "skills" / "analisi-materiale"
    _, body = _split(folder / "SKILL.md")
    assert "](modello-materiale.md)" in body
    template = (folder / "modello-materiale.md").read_text(encoding="utf-8")
    block = re.search(r"^```markdown\n(.*?)^```", template, re.S | re.M).group(1)
    headings = [line[3:] for line in block.splitlines() if line.startswith("## ")]
    assert headings == ["Sintesi del lavoro", "Mappa del materiale", "Cronologia",
                        "Dati e numeri", "Note dell'autore", "Non letto", "Lacune e domande"]
