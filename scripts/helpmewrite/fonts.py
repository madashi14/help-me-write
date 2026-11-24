"""Font families (times / helvetica / courier) and their metrics."""
import re

# Prefixes of equivalent font names, compared after lowercasing and dropping
# spaces, hyphens, underscores and commas. "nimbusrom"/"nimbussan"/"nimbusmon"
# also cover the PDF names NimbusRomNo9L, NimbusSanL, NimbusMonL.
_ALIASES = {
    "times": ("timesnewroman", "times", "liberationserif", "texgyretermes",
              "nimbusroman", "nimbusrom"),
    "helvetica": ("helvetica", "arial", "liberationsans", "texgyreheros",
                  "nimbussans", "nimbussan"),
    "courier": ("courier", "couriernew", "liberationmono", "texgyrecursor",
                "nimbusmono", "nimbusmon"),
}

DOCX_FONT = {"times": "Times New Roman", "helvetica": "Arial", "courier": "Courier New"}

# Effective width per character (spaces included) of a full line of Italian prose.
# times/helvetica were calibrated on PDFs rendered by LibreOffice (Liberation fonts) and
# measured by measure.py, so that a 65-character layout measures a median of ~65 characters
# per full line (word wrapping included). Courier is monospace: 0.60 em is exact.
AVG_CHAR_WIDTH_EM = {"times": 0.41, "helvetica": 0.45, "courier": 0.60}

_SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")


def normalize_font(name: str) -> str | None:
    """Map a font name (docx or PDF, incl. subset prefix and style suffixes) to a family."""
    if not name:
        return None
    key = _SUBSET_PREFIX.sub("", name.strip())
    key = re.sub(r"[\s_,\-]+", "", key).lower()
    for family, aliases in _ALIASES.items():
        if any(key.startswith(alias) for alias in aliases):
            return family
    return None
