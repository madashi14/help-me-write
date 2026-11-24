"""Builders for test documents."""
from pathlib import Path

import docx
from docx.shared import Cm, Pt

HERE = Path(__file__).resolve().parent


def italian_paragraphs(n: int) -> list[str]:
    """n paragraphs of Italian prose, cycling through testo_italiano.txt."""
    text = (HERE / "testo_italiano.txt").read_text(encoding="utf-8")
    base = [p.strip() for p in text.split("\n\n") if p.strip()]
    return [base[i % len(base)] for i in range(n)]


def write_docx(path, paragraphs, font="Calibri", size_pt=11, margins_cm=1.5,
               line_spacing=None) -> Path:
    """Write a .docx. Items are text or (style, text) tuples."""
    path = Path(path)
    document = docx.Document()
    normal = document.styles["Normal"]
    normal.font.name = font
    normal.font.size = Pt(size_pt)
    if line_spacing is not None:
        normal.paragraph_format.line_spacing = line_spacing
    for section in document.sections:
        section.left_margin = section.right_margin = Cm(margins_cm)
        section.top_margin = section.bottom_margin = Cm(margins_cm)
    for item in paragraphs:
        if isinstance(item, tuple):
            style, text = item
            document.add_paragraph(text, style=style)
        else:
            document.add_paragraph(item)
    document.save(str(path))
    return path
