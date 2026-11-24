"""Guidelines as data: schema, loading and validation of linee-guida.yaml."""
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

FORMATS = ("docx", "latex")
TOP_LEVEL_KEYS = {
    "document_type", "language", "format", "source", "pages", "fonts",
    "font_size_pt", "lines_per_page", "chars_per_line", "page_numbers",
    "sections", "content_rules", "title_page_template",
}
SECTION_KEYS = {"name", "required", "headings", "pages"}


class RulesError(Exception):
    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


@dataclass
class Range:
    min: float | None = None
    max: float | None = None

    def mid(self):
        if self.min is None or self.max is None:
            return None
        return (self.min + self.max) / 2


@dataclass
class SectionRule:
    name: str
    required: bool = True
    headings: list = field(default_factory=list)
    pages: Range | None = None


@dataclass
class Rules:
    document_type: str = ""
    language: str = "it"
    format: str | None = None
    source: str | None = None
    pages: Range | None = None
    fonts: list = field(default_factory=list)
    font_size_pt: float | None = None
    lines_per_page: Range | None = None
    chars_per_line: Range | None = None
    page_numbers: bool = False
    sections: list = field(default_factory=list)
    content_rules: list = field(default_factory=list)
    title_page_template: str | None = None


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _number(value, where, problems, allow_none=True):
    if value is None and allow_none:
        return None
    if not _is_number(value):
        problems.append(f"{where}: expected a number, got {value!r}")
        return None
    if value < 0:
        problems.append(f"{where}: must not be negative, got {value!r}")
        return None
    return value


def _range(value, where, problems):
    if value is None:
        return None
    if not isinstance(value, dict):
        problems.append(f"{where}: expected a mapping with min/max, got {value!r}")
        return None
    extra = set(value) - {"min", "max"}
    if extra:
        problems.append(f"{where}: unknown keys {sorted(map(str, extra))}")
    lo = _number(value.get("min"), f"{where}.min", problems)
    hi = _number(value.get("max"), f"{where}.max", problems)
    if lo is not None and hi is not None and lo > hi:
        problems.append(f"{where}: min ({lo}) is greater than max ({hi})")
        return None
    return Range(lo, hi)


def _string(value, where, problems):
    if value is None:
        return None
    if not isinstance(value, str):
        problems.append(f"{where}: expected a string, got {value!r}")
        return None
    return value


def _string_list(value, where, problems):
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        problems.append(f"{where}: expected a list of strings, got {value!r}")
        return []
    return list(value)


def _bool(value, where, problems, default):
    if value is None:
        return default
    if not isinstance(value, bool):
        problems.append(f"{where}: expected true or false, got {value!r}")
        return default
    return value


def _section(raw, i, problems):
    where = f"sections[{i}]"
    if not isinstance(raw, dict):
        problems.append(f"{where}: expected a mapping, got {raw!r}")
        return None
    extra = set(raw) - SECTION_KEYS
    if extra:
        problems.append(f"{where}: unknown keys {sorted(map(str, extra))}")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        problems.append(f"{where}: missing 'name'")
        name = None
    return SectionRule(
        name=name or "",
        required=_bool(raw.get("required"), f"{where}.required", problems, True),
        headings=_string_list(raw.get("headings"), f"{where}.headings", problems),
        pages=_range(raw.get("pages"), f"{where}.pages", problems),
    ) if name else None


def parse_rules(data) -> Rules:
    problems = []
    if not isinstance(data, dict):
        raise RulesError(["top level: expected a mapping of guideline fields"])
    for key in sorted(set(data) - TOP_LEVEL_KEYS, key=str):
        problems.append(f"unknown key '{key}'")

    fmt = data.get("format")
    if fmt is not None and fmt not in FORMATS:
        problems.append(f"format: must be one of {list(FORMATS)} or null, got {fmt!r}")
        fmt = None
    sections = []
    raw_sections = data.get("sections")
    if raw_sections is None:
        raw_sections = []
    if not isinstance(raw_sections, list):
        problems.append(f"sections: expected a list, got {raw_sections!r}")
        raw_sections = []
    for i, raw in enumerate(raw_sections):
        s = _section(raw, i, problems)
        if s is not None:
            sections.append(s)

    rules = Rules(
        document_type=_string(data.get("document_type"), "document_type", problems) or "",
        language=_string(data.get("language"), "language", problems) or "it",
        format=fmt,
        source=_string(data.get("source"), "source", problems),
        pages=_range(data.get("pages"), "pages", problems),
        fonts=_string_list(data.get("fonts"), "fonts", problems),
        font_size_pt=_number(data.get("font_size_pt"), "font_size_pt", problems),
        lines_per_page=_range(data.get("lines_per_page"), "lines_per_page", problems),
        chars_per_line=_range(data.get("chars_per_line"), "chars_per_line", problems),
        page_numbers=_bool(data.get("page_numbers"), "page_numbers", problems, False),
        sections=sections,
        content_rules=_string_list(data.get("content_rules"), "content_rules", problems),
        title_page_template=_string(
            data.get("title_page_template"), "title_page_template", problems),
    )
    if problems:
        raise RulesError(problems)
    return rules


def load_rules(path) -> Rules:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RulesError([f"cannot read {path}: {exc.strerror or exc}"])
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RulesError([f"invalid YAML: {exc}"])
    return parse_rules(data)


def add_arguments(parser):
    parser.add_argument("action", choices=["validate"], help="action to perform")
    parser.add_argument("file", help="linee-guida.yaml to check")


def run(args) -> int:
    from . import cli

    if cli.refuses_overwrite(args.file, args):
        return 2
    try:
        rules = load_rules(args.file)
    except RulesError as exc:
        for problem in exc.problems:
            print(f"error: {problem}", file=sys.stderr)
        cli.emit({"valid": False, "problems": exc.problems}, args,
                 text=f"{len(exc.problems)} problem(s) found")
        return 2
    cli.emit({"valid": True, "problems": []}, args,
             text=f"valid: {rules.document_type} ({len(rules.sections)} sections)")
    return 0
