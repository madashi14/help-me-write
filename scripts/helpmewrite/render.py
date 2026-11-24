"""Rendering to PDF: .docx through LibreOffice, .tex through latexmk, .pdf as is."""
import shutil
import subprocess
import tempfile
import unicodedata
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


def _render_docx(src: Path, workdir: Path, soffice: str) -> Path:
    stale = _find_output(workdir, src.stem)
    if stale is not None:
        stale.unlink()  # never mistake a previous run's PDF for this one
    profile = Path(tempfile.mkdtemp(prefix="lo-profile-", dir=workdir))
    try:
        proc = _run(soffice_command(src.absolute(), workdir.absolute(), profile, soffice))
    except OSError as exc:
        raise RenderError(f"cannot start LibreOffice ({exc}). {_INSTALL_HINT['soffice']}",
                          missing_tool="soffice")
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    pdf = _find_output(workdir, src.stem)
    if proc.returncode != 0 or pdf is None:
        raise RenderError(f"LibreOffice could not convert {src.name} to PDF "
                          f"(exit code {proc.returncode}): {_excerpt(proc)}")
    return pdf


def _render_tex(src: Path, workdir: Path, latexmk: str) -> Path:
    cmd = [latexmk, "-pdf", "-interaction=nonstopmode", f"-outdir={workdir.absolute()}", src.name]
    try:
        proc = _run(cmd, cwd=src.parent)
    except OSError as exc:
        raise RenderError(f"cannot start latexmk ({exc}). {_INSTALL_HINT['latexmk']}",
                          missing_tool="latexmk")
    pdf = _find_output(workdir, src.stem)
    if proc.returncode != 0 or pdf is None:
        raise RenderError(f"latexmk could not compile {src.name} "
                          f"(exit code {proc.returncode}): {_excerpt(proc)}")
    return pdf


def render_pdf(src, workdir) -> Path:
    """Return a PDF of src: a .pdf as is, a .docx via LibreOffice, a .tex via latexmk.

    Output and the temporary LibreOffice profile go into workdir (created if needed).
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
    return renderer(src, workdir, exe)
