"""Environment check: Python version, packages and optional external tools.

Standard library only: it must run before the packages it checks are installed.
"""
import importlib
import shutil
import sys

from . import cli, render

MIN_PYTHON = (3, 10)
PACKAGES = tuple(cli.PACKAGES)


def _version(module_name):
    """Return the module version string, or None if it cannot be imported."""
    try:
        module = importlib.import_module(module_name)
    except Exception:  # ImportError, or a broken installation
        return None
    return str(getattr(module, "__version__", "unknown"))


def check_environment() -> dict:
    version = ".".join(str(p) for p in sys.version_info[:3])
    python_ok = sys.version_info[:2] >= MIN_PYTHON
    packages = {name: _version(name) for name in PACKAGES}
    soffice = render.find_soffice()
    latexmk = shutil.which("latexmk")
    latexdiff = shutil.which("latexdiff")

    missing = []
    if not python_ok:
        missing.append({
            "what": "Python >= 3.10",
            "needed_for": "everything",
            "how_to_install": "https://www.python.org/downloads/",
        })
    for name, ver in packages.items():
        if ver is None:
            missing.append({
                "what": f"Python package '{cli.PACKAGES[name]}' (import name '{name}')",
                "needed_for": "Word/PDF/LaTeX/bibliography processing",
                "how_to_install": cli.install_hint() + " (in a virtual environment if pip "
                                  "reports \"externally-managed-environment\")",
            })
    if soffice is None:
        missing.append({
            "what": "LibreOffice",
            "needed_for": "rendering .docx to PDF and measuring the layout",
            "how_to_install": "Download from https://www.libreoffice.org/download/",
        })
    if latexmk is None:
        missing.append({
            "what": "latexmk",
            "needed_for": "compiling LaTeX documents",
            "how_to_install": "Install TeX Live (https://tug.org/texlive/) or MiKTeX",
        })
    if latexdiff is None:
        missing.append({
            "what": "latexdiff",
            "needed_for": "showing LaTeX corrections as tracked changes",
            "how_to_install": "Install TeX Live (https://tug.org/texlive/), which includes latexdiff",
        })
    return {
        "python": version,
        "python_ok": python_ok,
        "packages": packages,
        "soffice": soffice,
        "latexmk": latexmk,
        "latexdiff": latexdiff,
        "missing": missing,
    }


def summary(env: dict) -> str:
    lines = [f"Python {env['python']}: {'ok' if env['python_ok'] else 'too old (need >= 3.10)'}"]
    for name, ver in env["packages"].items():
        lines.append(f"  package {name}: {ver or 'MISSING'}")
    for key in ("soffice", "latexmk", "latexdiff"):
        lines.append(f"  {key}: {env[key] or 'not found (optional)'}")
    if env["missing"]:
        lines.append("")
        lines.append("Missing:")
        for item in env["missing"]:
            lines.append(f"  - {item['what']} (needed for {item['needed_for']}): {item['how_to_install']}")
    else:
        lines.append("")
        lines.append("Everything is installed.")
    return "\n".join(lines)


def add_arguments(parser):
    pass


def run(args) -> int:
    env = check_environment()
    cli.emit(env, args, text=summary(env))
    return 0
