"""Entry point: python scripts/hmw.py <command>.

The Python version is checked before anything else is imported, with syntax every Python
can parse, so an old interpreter gets a clear message instead of a traceback.
"""
import sys

MIN_PYTHON = (3, 10)


def python_too_old():
    """True (after printing why) if this Python is older than MIN_PYTHON."""
    if tuple(sys.version_info[:2]) >= MIN_PYTHON:
        return False
    sys.stderr.write(
        "error: help-me-write needs Python %d.%d or newer; this is Python %s (%s). "
        "Install a newer Python from https://www.python.org/downloads/ and run the "
        "command with it (python3 or py -3 may name it).\n"
        % (MIN_PYTHON[0], MIN_PYTHON[1],
           ".".join(str(part) for part in sys.version_info[:3]), sys.executable))
    return True


if __name__ == "__main__":
    if python_too_old():
        sys.exit(3)
    import os

    sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
    from helpmewrite.cli import main

    sys.exit(main())
