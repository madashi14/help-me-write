"""Write test copies of "Times New Roman": Liberation Serif (its metric clone) renamed.

For the tests and the real-draft bench on Linux, where Times New Roman is not installed.
XeLaTeX finds a font by the names in the file's `name` table, so a fontconfig alias is not
enough: this rewrites names 1, 3, 4, 6 and 16 of the four Liberation Serif styles. Never
used by the plugin.

    python tests/strumenti/font_times_prova.py --dest ~/.local/share/fonts/hmw-prova
    fc-cache -f

Exit codes: 0 written; 2 Liberation Serif not found; 3 fontTools not installed.
"""
import argparse
import os
import sys
from pathlib import Path

FAMILY = "Times New Roman"
# Liberation Serif style -> (full name, PostScript name) of the copy
STYLES = {
    "Regular": (FAMILY, "TimesNewRomanPSMT"),
    "Bold": (f"{FAMILY} Bold", "TimesNewRomanPS-BoldMT"),
    "Italic": (f"{FAMILY} Italic", "TimesNewRomanPS-ItalicMT"),
    "BoldItalic": (f"{FAMILY} Bold Italic", "TimesNewRomanPS-BoldItalicMT"),
}
FONT_DIRS = [
    Path("/usr/share/fonts"), Path("/usr/local/share/fonts"),
    Path.home() / ".local" / "share" / "fonts", Path.home() / ".fonts",
    Path("/Library/Fonts"), Path.home() / "Library" / "Fonts",
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
]


def find_liberation(dirs=FONT_DIRS) -> dict[str, Path]:
    """Style -> LiberationSerif-<style>.ttf, for the styles found in dirs (searched deep)."""
    found = {}
    for folder in dirs:
        if not folder.is_dir():
            continue
        for style in STYLES:
            if style not in found:
                hit = next(folder.rglob(f"LiberationSerif-{style}.ttf"), None)
                if hit is not None:
                    found[style] = hit
    return found


def renamed(source: Path, style: str):
    """The font of source with the names of the Times New Roman copy, as a TTFont."""
    from fontTools.ttLib import TTFont

    full, postscript = STYLES[style]
    font = TTFont(str(source))
    name = font["name"]
    for name_id, value in {1: FAMILY, 3: f"hmw-prova {full}", 4: full, 6: postscript,
                           16: FAMILY}.items():
        name.removeNames(nameID=name_id)
        name.setName(value, name_id, 3, 1, 0x409)  # Windows, English (US)
        name.setName(value, name_id, 1, 0, 0)      # Macintosh, Roman
    return font


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dest", required=True, help="folder for the four .ttf files")
    args = parser.parse_args(argv)
    try:
        import fontTools  # noqa: F401
    except ImportError:
        print("error: fontTools is needed (pip install fonttools)", file=sys.stderr)
        return 3
    sources = find_liberation()
    missing = [style for style in STYLES if style not in sources]
    if missing:
        names = ", ".join(f"LiberationSerif-{style}.ttf" for style in missing)
        print(f"error: Liberation Serif not found ({names}); install it (Debian/Ubuntu: "
              "apt install fonts-liberation) and try again", file=sys.stderr)
        return 2
    dest = Path(args.dest).expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    for style, source in sources.items():
        target = dest / f"TimesNewRoman-{style}.ttf"
        renamed(source, style).save(str(target))
        print(f"wrote {target} (from {source})")
    print("now run: fc-cache -f")
    return 0


if __name__ == "__main__":
    sys.exit(main())
