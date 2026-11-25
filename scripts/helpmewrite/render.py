"""Rendering to PDF: .docx through LibreOffice, .tex through latexmk, .pdf as is.

Standard library only (doctor imports it).

- A .docx is converted from a temporary copy set to show the text with every tracked
  change accepted (w:revisionView): LibreOffice would otherwise lay out deleted text struck
  through, and the pages, lines and sections measured would not be those of the document.
- A .tex is compiled with the engine it asks for: a `% !TEX program = ...` magic comment,
  else XeLaTeX (LuaLaTeX if only that is installed) for fontspec, polyglossia or
  unicode-math, else pdfLaTeX; a latexmkrc in the project folder that sets $pdf_mode
  chooses by itself. A failed compilation reports the first errors (`!` lines) of the log.
"""
import re
import shutil
import subprocess
import tempfile
import unicodedata
import zipfile
from pathlib import Path

TIMEOUT_S = 180

_FALLBACK_PATHS = (
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
)

_INSTALL_HINT = {
    "soffice": "LibreOffice is needed to render .docx files to PDF: "
               "download it from https://www.libreoffice.org/download/",
    "latexmk": "latexmk is needed to compile LaTeX to PDF: install TeX Live "
               "(https://tug.org/texlive/) or MiKTeX (https://miktex.org/)",
}


class RenderError(Exception):
    """Rendering failed; missing_tool names the external tool to install, if that is why."""

    def __init__(self, message: str, missing_tool: str | None = None):
        super().__init__(message)
        self.missing_tool = missing_tool


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


def soffice_command(src, outdir, profile_dir, soffice=None) -> list[str]:
    """LibreOffice command converting src to PDF in outdir.

    A private profile (-env:UserInstallation) lets the conversion run even while the user
    has LibreOffice open: with the shared profile headless conversion fails silently.
    """
    profile_uri = Path(profile_dir).absolute().as_uri()
    return [str(soffice or find_soffice() or "soffice"),
            f"-env:UserInstallation={profile_uri}", "--headless",
            "--convert-to", "pdf", "--outdir", str(outdir), str(src)]


def _excerpt(proc, limit=600) -> str:
    text = (proc.stderr or b"").decode("utf-8", "replace").strip()
    if not text:
        text = (proc.stdout or b"").decode("utf-8", "replace").strip()
    text = " ".join(text.split())
    return text[-limit:] if text else "no output"


def _find_output(outdir: Path, stem: str) -> Path | None:
    """The PDF named after stem; tolerant to Unicode normalization (NFC/NFD) of accents."""
    expected = outdir / f"{stem}.pdf"
    if expected.is_file():
        return expected
    key = unicodedata.normalize("NFC", stem)
    for candidate in outdir.glob("*.pdf"):
        if unicodedata.normalize("NFC", candidate.stem) == key:
            return candidate
    return None


def _run(cmd, cwd=None):
    try:
        return subprocess.run(cmd, cwd=cwd, timeout=TIMEOUT_S, capture_output=True)
    except subprocess.TimeoutExpired:
        raise RenderError(f"{Path(cmd[0]).name} did not finish within {TIMEOUT_S} s")


def _fresh_outdir(workdir: Path) -> Path:
    """A new, empty subfolder: files already in workdir are never overwritten or mistaken."""
    return Path(tempfile.mkdtemp(prefix="pdf-", dir=workdir))


_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
# settings that follow w:revisionView in CT_Settings: it goes before the first of them
_AFTER_REVISION_VIEW = ("trackRevisions", "doNotTrackMoves", "doNotTrackFormatting",
                        "documentProtection", "autoFormatOverride", "styleLockTheme",
                        "styleLockQFSet", "defaultTabStop")


def accepted_view_settings(xml: bytes):
    """word/settings.xml showing the final text (changes accepted, no markup); None if the
    part cannot be read."""
    try:
        text = xml.decode("utf-8")
    except UnicodeDecodeError:
        return None
    m = re.search(r'xmlns:([\w.-]+)="' + re.escape(_W_NS) + '"', text)
    if m is None:
        return None
    w = m.group(1)
    text = re.sub(rf"<{w}:revisionView\b[^>]*?(?:/>|>.*?</{w}:revisionView>)", "", text,
                  flags=re.S)
    element = (f'<{w}:revisionView {w}:markup="false" {w}:insDel="false" '
               f'{w}:formatting="false"/>')
    anchors = [hit.start() for a in _AFTER_REVISION_VIEW
               if (hit := re.search(rf"<{w}:{a}\b", text))]
    at = min(anchors) if anchors else text.rfind(f"</{w}:settings>")
    if at < 0:
        return None
    return (text[:at] + element + text[at:]).encode("utf-8")


def _accepted_copy(src: Path, folder: Path) -> Path:
    """A copy of src in folder that shows the final text; src itself if that cannot be made
    (LibreOffice then reports the problem with the file)."""
    dst = folder / src.name
    try:
        with zipfile.ZipFile(src) as zin:
            settings = accepted_view_settings(zin.read("word/settings.xml"))
            if settings is None:
                return src
            with zipfile.ZipFile(dst, "w") as zout:
                for item in zin.infolist():
                    data = settings if item.filename == "word/settings.xml" else zin.read(item)
                    zout.writestr(item, data)
    except (zipfile.BadZipFile, KeyError, OSError, RuntimeError, ValueError):
        return src
    return dst


def _render_docx(src: Path, workdir: Path, soffice: str) -> Path:
    outdir = _fresh_outdir(workdir)
    profile = Path(tempfile.mkdtemp(prefix="lo-profile-", dir=workdir))
    view = Path(tempfile.mkdtemp(prefix="docx-", dir=workdir))
    try:
        copy = _accepted_copy(src, view)
        proc = _run(soffice_command(copy.absolute(), outdir.absolute(), profile, soffice))
    except OSError as exc:
        raise RenderError(f"cannot start LibreOffice ({exc}). {_INSTALL_HINT['soffice']}",
                          missing_tool="soffice")
    finally:
        shutil.rmtree(profile, ignore_errors=True)
        shutil.rmtree(view, ignore_errors=True)
    pdf = _find_output(outdir, src.stem)
    if proc.returncode != 0 or pdf is None:
        raise RenderError(f"LibreOffice could not convert {src.name} to PDF "
                          f"(exit code {proc.returncode}): {_excerpt(proc)}")
    return pdf


# --- LaTeX engine -----------------------------------------------------------------------

_MAGIC = re.compile(r"^\s*%\s*!\s*TeX\s+(?:TS-)?program\s*=\s*([\w-]+)", re.I | re.M)
_ENGINES = {"pdflatex": "-pdf", "pdftex": "-pdf", "xelatex": "-xelatex", "xetex": "-xelatex",
            "lualatex": "-lualatex", "luatex": "-lualatex", "latex": "-pdfdvi"}
_PACKAGE = re.compile(r"\\(?:usepackage|RequirePackage)\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")
_INCLUDE = re.compile(r"\\(?:input|include|subfile)\s*\{([^}]*)\}")
_UNICODE_PACKAGES = {"fontspec", "polyglossia", "unicode-math"}
_LUA_PACKAGES = {"luacode", "luatexbase", "luaotfload", "lua-visual-debug"}
_MAGIC_LINES = 50


def _read_tex(path: Path) -> str:
    try:
        return path.read_bytes().decode("utf-8", "replace")
    except OSError:
        return ""


def _uncommented(text: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", text)


def _project_packages(main: Path) -> set:
    """Packages loaded by main and the files it includes (\\input, \\include, \\subfile)."""
    packages, seen, todo = set(), set(), [main]
    while todo and len(seen) < 200:
        path = todo.pop()
        key = path.resolve()
        if key in seen or not path.is_file():
            continue
        seen.add(key)
        text = _uncommented(_read_tex(path))
        for m in _PACKAGE.finditer(text):
            packages.update(n.strip() for n in m.group(1).split(",") if n.strip())
        for m in _INCLUDE.finditer(text):
            name = m.group(1).strip()
            if name:
                child = main.parent / name
                todo.append(child if child.suffix == ".tex" else child.with_name(child.name + ".tex"))
    return packages


def _latexmkrc_chooses(folder: Path) -> bool:
    """True if a latexmkrc in folder sets $pdf_mode: latexmk then picks the engine itself."""
    for name in ("latexmkrc", ".latexmkrc"):
        rc = folder / name
        if rc.is_file() and re.search(r"^[^#]*\$pdf_mode\s*=", _read_tex(rc), re.M):
            return True
    return False


def tex_engine(main) -> list:
    """latexmk's engine option for the project of main ([] : the latexmkrc decides)."""
    main = Path(main)
    if _latexmkrc_chooses(main.parent):
        return []
    head = "\n".join(_read_tex(main).splitlines()[:_MAGIC_LINES])
    m = _MAGIC.search(head)
    if m and m.group(1).lower() in _ENGINES:
        return [_ENGINES[m.group(1).lower()]]
    packages = _project_packages(main)
    if packages & _LUA_PACKAGES:
        return ["-lualatex"]
    if packages & _UNICODE_PACKAGES:
        if shutil.which("xelatex") is None and shutil.which("lualatex") is not None:
            return ["-lualatex"]
        return ["-xelatex"]
    return ["-pdf"]


_MAX_PRINT_LINE = 79  # TeX wraps log lines at this length
_NOT_THE_CAUSE = ("! Emergency stop.", "!  ==> Fatal error occurred")


def _log_errors(log: Path, limit=3) -> str:
    """The first TeX errors of a log: each `!` line (unwrapped), with its `l.<n>` line."""
    try:
        lines = log.read_bytes().decode("utf-8", "replace").splitlines()
    except OSError:
        return ""
    errors = []
    for i, line in enumerate(lines):
        if not line.startswith("!") or line.startswith(_NOT_THE_CAUSE):
            continue
        text, j = line, i
        while j + 1 < len(lines):
            more = re.match(r"\([\w.-]+\)\s+(\S.*)$", lines[j + 1])  # "(fontspec)  LuaTeX."
            if len(lines[j]) >= _MAX_PRINT_LINE:
                text += lines[j + 1]
            elif more:
                text += " " + more.group(1)
            else:
                break
            j += 1
        where = next((l.strip() for l in lines[j + 1:j + 12] if re.match(r"l\.\d+", l)), "")
        errors.append(" ".join(text.split()) + (f" ({where[:80]})" if where else ""))
        if len(errors) == limit:
            break
    return "; ".join(errors)


def _render_tex(src: Path, workdir: Path, latexmk: str, engine=None) -> Path:
    outdir = _fresh_outdir(workdir)
    engine = tex_engine(src) if engine is None else list(engine)
    cmd = [latexmk, *engine, "-interaction=nonstopmode", f"-outdir={outdir.absolute()}", src.name]
    try:
        proc = _run(cmd, cwd=src.parent)
    except OSError as exc:
        raise RenderError(f"cannot start latexmk ({exc}). {_INSTALL_HINT['latexmk']}",
                          missing_tool="latexmk")
    pdf = _find_output(outdir, src.stem)
    if proc.returncode != 0 or pdf is None:
        errors = _log_errors(outdir / f"{src.stem}.log")
        how = " ".join(engine) or "the project's latexmkrc"
        detail = errors or _excerpt(proc)
        raise RenderError(f"latexmk ({how}) could not compile {src.name} "
                          f"(exit code {proc.returncode}): {detail}")
    return pdf


def render_pdf(src, workdir, engine=None) -> Path:
    """Return a PDF of src: a .pdf as is, a .docx via LibreOffice, a .tex via latexmk.

    The PDF (with latexmk's auxiliary files) goes into a new subfolder of workdir (created if
    needed), so files already in workdir are never touched; the temporary LibreOffice
    profile and .docx copy are created in workdir and removed afterwards. engine is
    latexmk's engine option for a .tex, as a list (default: tex_engine(src)).
    Raises RenderError; its missing_tool is set when an external tool is not installed.
    """
    src, workdir = Path(src), Path(workdir)
    suffix = src.suffix.lower()
    if suffix not in (".pdf", ".docx", ".tex"):
        raise RenderError(f"unsupported format '{src.suffix}' (use .docx, .tex or .pdf)")
    if suffix == ".docx":
        tool, exe, renderer = "soffice", find_soffice(), _render_docx
    elif suffix == ".tex":
        tool, exe, renderer = "latexmk", shutil.which("latexmk"), _render_tex
    if suffix != ".pdf" and exe is None:
        raise RenderError(_INSTALL_HINT[tool], missing_tool=tool)
    if not src.is_file():
        raise RenderError(f"file not found: {src}")
    if suffix == ".pdf":
        return src
    workdir.mkdir(parents=True, exist_ok=True)
    if suffix == ".tex":
        return renderer(src, workdir, exe, engine)
    return renderer(src, workdir, exe)
