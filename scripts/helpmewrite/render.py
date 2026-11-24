"""Rendering helpers (LibreOffice detection; more added in later tasks)."""
import shutil
from pathlib import Path

_FALLBACK_PATHS = (
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
)


def find_soffice():
    """Return the path of the LibreOffice executable, or None if not found."""
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in _FALLBACK_PATHS:
        if Path(candidate).exists():
            return candidate
    return None
