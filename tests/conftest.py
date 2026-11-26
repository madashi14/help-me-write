import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"

SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


@pytest.fixture
def root():
    return ROOT


@pytest.fixture
def fix():
    return FIX


def pytest_collection_modifyitems(config, items):
    from helpmewrite import render

    if render.find_soffice() is None:
        skip = pytest.mark.skip(reason="LibreOffice (soffice) not installed")
        for item in items:
            if "needs_soffice" in item.keywords:
                item.add_marker(skip)
    if not (shutil.which("latexmk") and shutil.which("latexdiff")):
        skip = pytest.mark.skip(reason="latexmk/latexdiff not installed")
        for item in items:
            if "needs_latex" in item.keywords:
                item.add_marker(skip)
    if not (shutil.which("xelatex") and shutil.which("latexmk")):
        skip = pytest.mark.skip(reason="xelatex/latexmk not installed")
        for item in items:
            if "needs_xelatex" in item.keywords:
                item.add_marker(skip)
