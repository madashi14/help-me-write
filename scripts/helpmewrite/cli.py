"""Command-line entry: subcommand registry and output helpers.

Exit codes: 0 ok; 1 checks failed (measure) or some edits failed (track); 2 usage error or
bad input; 3 missing external tool or Python package.

Command modules are imported only when their command runs, so `doctor` works with the
standard library alone; a missing package is reported with the command that installs it.
"""
import argparse
import importlib
import json
import os
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
HMW_SCRIPT = PLUGIN_ROOT / "scripts" / "hmw.py"
REQUIREMENTS = PLUGIN_ROOT / "requirements.txt"
# import name -> name on PyPI
PACKAGES = {"docx": "python-docx", "lxml": "lxml", "pdfplumber": "pdfplumber",
            "yaml": "PyYAML", "bibtexparser": "bibtexparser",
            "matplotlib": "matplotlib"}

# name -> (module, add_arguments, handler, json_output, packages needed)
# json_output=False: -o belongs to the command (the document it produces), not to JSON.
_COMMANDS = {
    "bib": ("bib", "add_bib_arguments", "run_bib", True,
            ("lxml", "docx", "pdfplumber", "bibtexparser")),
    "chart": ("figure", "add_chart_arguments", "run_chart", False, ("matplotlib",)),
    "detect": ("detect", "add_arguments", "run", True, ("lxml", "docx")),
    "diagram": ("figure", "add_diagram_arguments", "run_diagram", False, ("matplotlib",)),
    "doctor": ("doctor", "add_arguments", "run", True, ()),
    "extract": ("extract", "add_arguments", "run", True, ("lxml", "docx", "pdfplumber")),
    "format": ("layout", "add_format_arguments", "run_format", False, ("lxml", "docx")),
    "layout": ("layout", "add_arguments", "run", True, ("yaml",)),
    "material": ("materiale", "add_material_arguments", "run_material", True, ()),
    "measure": ("measure", "add_arguments", "run", True,
                ("lxml", "docx", "pdfplumber", "yaml")),
    "notebook": ("materiale", "add_notebook_arguments", "run_notebook", False, ()),
    "pdftext": ("bib", "add_pdftext_arguments", "run_pdftext", True,
                ("lxml", "pdfplumber")),
    "rules": ("rules", "add_arguments", "run", True, ("yaml",)),
    "state": ("state", "add_arguments", "run", False, ("yaml",)),
    "texdiff": ("track_tex", "add_texdiff_arguments", "run_texdiff", False, ("lxml",)),
    "titlepage": ("titlepage", "add_arguments", "run", False, ("lxml", "docx")),
    "track": ("edits", "add_track_arguments", "run_track", False, ("lxml", "docx")),
}


class CliError(Exception):
    """A clean error for the user: printed as `error: <message>`, exit code 2."""


def install_hint() -> str:
    """The command that installs every Python package the plugin needs."""
    if REQUIREMENTS.is_file():
        return f'"{sys.executable}" -m pip install -r "{REQUIREMENTS}"'
    return f'"{sys.executable}" -m pip install ' + " ".join(
        f'"{name}"' if any(c in name for c in "<>=") else name
        for name in ("python-docx>=1.2", "lxml", "pdfplumber", "PyYAML", "bibtexparser>=1.4,<2",
                     "matplotlib>=3.7"))


def doctor_command() -> str:
    return f'"{sys.executable}" "{HMW_SCRIPT}" doctor'


def missing_packages_message(names) -> str:
    listed = ", ".join(PACKAGES.get(n, n) for n in names)
    return (f"missing Python package(s): {listed}. Install them with: {install_hint()} "
            f"(in a virtual environment if pip reports \"externally-managed-environment\"); "
            f"to check everything run: {doctor_command()}")


def emit(data: dict, args, text=None) -> None:
    """Print JSON if --json, write JSON to -o file if given, else a readable summary.

    The folder of the -o file is created if needed; a file that cannot be written raises
    CliError.
    """
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    output = getattr(args, "output", None)
    if output:
        path = Path(output)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload + "\n", encoding="utf-8")
        except OSError as exc:
            blocker = next((f for f in path.parents if f.is_file()), None)
            reason = f"{blocker} is a file, not a folder" if blocker else exc.strerror or exc
            raise CliError(f"cannot write {path}: {reason}") from None
        return
    if getattr(args, "json", False):
        print(payload)
    else:
        print(text if text is not None else payload)


def same_file(a, b) -> bool:
    """True if a and b are the same file (os.path.samefile when both exist)."""
    a, b = Path(a), Path(b)
    if a.exists() and b.exists():
        try:
            return os.path.samefile(a, b)
        except OSError:
            pass
    return a.resolve() == b.resolve()


def refuses_overwrite(source, args) -> bool:
    """True (after printing an error) if -o points at the source file itself."""
    output = getattr(args, "output", None)
    if output and same_file(output, source):
        print(f"error: output would overwrite the original: {source}", file=sys.stderr)
        return True
    return False


def next_free_name(path) -> Path:
    """path itself if free, else the first free `<stem>-2<suffix>`, `<stem>-3<suffix>`, …"""
    path = Path(path)
    if not path.exists():
        return path
    stem, suffix = (path.stem, path.suffix) if path.suffix and not path.is_dir() \
        else (path.name, "")
    n = 2
    while (path.parent / f"{stem}-{n}{suffix}").exists():
        n += 1
    return path.parent / f"{stem}-{n}{suffix}"


def refuses_existing_output(output, sources=(), folder_ok_if_empty=False) -> bool:
    """True (after printing an error) if output is one of sources or already exists.

    A document is never overwritten: the error names the next free name to use instead.
    With folder_ok_if_empty, an existing empty folder is accepted.
    """
    output = Path(output)
    for source in sources:
        if same_file(output, source):
            print(f"error: output would overwrite the original: {source}", file=sys.stderr)
            return True
    if not output.exists():
        return False
    if folder_ok_if_empty and output.is_dir() and not any(output.iterdir()):
        return False
    print(f"error: output already exists: {output} (it is never overwritten); "
          f"use a new name, e.g. {next_free_name(output)}", file=sys.stderr)
    return True


def _command_module(name):
    return importlib.import_module(f"{__package__}.{_COMMANDS[name][0]}")


def _build_parser(only=None):
    """The argument parser; with only=<command>, only that command's module is imported."""
    parser = argparse.ArgumentParser(prog="hmw", description="help-me-write helper")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, (_, add_arguments, handler, json_output, _) in _COMMANDS.items():
        p = sub.add_parser(name)
        if only is not None and name != only:
            continue
        module = _command_module(name)
        getattr(module, add_arguments)(p)
        p.add_argument("--json", action="store_true", help="print JSON")
        if json_output:
            p.add_argument("-o", "--output", help="write JSON to this file")
        p.set_defaults(handler=getattr(module, handler))
    return parser


def _missing(packages) -> list[str]:
    missing = []
    for name in packages:
        try:
            importlib.import_module(name)
        except Exception:  # ImportError, or a broken installation
            missing.append(name)
    return missing


def _error(message, code) -> int:
    print(f"error: {message}", file=sys.stderr)
    return code


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    argv = sys.argv[1:] if argv is None else list(argv)
    command = next((a for a in argv if not a.startswith("-")), None)
    only = command if command in _COMMANDS else ""
    if only:
        missing = _missing(_COMMANDS[only][4])
        if missing:
            return _error(missing_packages_message(missing), 3)
    try:
        parser = _build_parser(only=only)
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    except ImportError as exc:
        return _error(missing_packages_message([exc.name or str(exc)]), 3)
    try:
        return args.handler(args)
    except CliError as exc:
        return _error(str(exc), 2)
    except ModuleNotFoundError as exc:
        return _error(missing_packages_message([exc.name or str(exc)]), 3)
    except KeyboardInterrupt:
        return _error("interrupted", 2)
    except Exception as exc:  # never a traceback: exit 1 would read as "checks failed"
        return _error(f"{type(exc).__name__}: {exc}", 2)
