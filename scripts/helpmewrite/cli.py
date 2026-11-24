"""Command-line entry: subcommand registry and output helpers.

Exit codes: 0 ok; 1 checks failed (measure only); 2 usage error; 3 missing external tool.
"""
import argparse
import json
import sys

_COMMANDS = {}


def register(name, add_arguments, handler):
    """Register a subcommand.

    add_arguments(parser) adds its arguments; handler(args) -> int is the exit code.
    Every subcommand automatically gets --json and -o/--output.
    """
    _COMMANDS[name] = (add_arguments, handler)


def emit(data: dict, args, text=None) -> None:
    """Print JSON if --json, write JSON to -o file if given, else a readable summary."""
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    output = getattr(args, "output", None)
    if output:
        from pathlib import Path

        Path(output).write_text(payload + "\n", encoding="utf-8")
        return
    if getattr(args, "json", False):
        print(payload)
    else:
        print(text if text is not None else payload)


def refuses_overwrite(source, args) -> bool:
    """True (after printing an error) if -o points at the source file itself."""
    from pathlib import Path

    output = getattr(args, "output", None)
    if output and Path(output).resolve() == Path(source).resolve():
        print(f"error: output would overwrite the original: {source}", file=sys.stderr)
        return True
    return False


def _build_parser():
    parser = argparse.ArgumentParser(prog="hmw", description="help-me-write helper")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, (add_arguments, handler) in _COMMANDS.items():
        p = sub.add_parser(name)
        add_arguments(p)
        p.add_argument("--json", action="store_true", help="print JSON")
        p.add_argument("-o", "--output", help="write JSON to this file")
        p.set_defaults(handler=handler)
    return parser


def _load_commands():
    # Command modules register themselves here; later tasks add their import.
    from . import doctor, extract, layout, rules

    register("doctor", doctor.add_arguments, doctor.run)
    register("extract", extract.add_arguments, extract.run)
    register("layout", layout.add_arguments, layout.run)
    register("rules", rules.add_arguments, rules.run)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    _load_commands()
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    return args.handler(args)
