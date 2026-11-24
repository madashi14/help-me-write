"""LaTeX: edits applied to a copy of the project, and a PDF of the differences (latexdiff)."""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .edits import EditsError, EditSet
from .render import RenderError, render_pdf
from .track_docx import ApplyResult

WINDOW = 2
_IGNORED_DIRS = (".help-me-write",)
_IGNORED_FILES = ("*.aux", "*.log", "*.fls", "*.fdb_latexmk", "*.synctex.gz", "*.out", "*.toc")
_LINE = re.compile(r"[^\r\n]*(?:\r\n|\n|\r)|[^\r\n]+")
_TIMEOUT_S = 180
_LATEXDIFF_HINT = ("latexdiff is needed to show the differences: install TeX Live "
                   "(https://tug.org/texlive/) or MiKTeX (https://miktex.org/)")


def _inside(path: Path, folder: Path) -> bool:
    return path == folder or folder in path.parents


def _prepare_out_dir(src_dir: Path, out_dir: Path) -> Path:
    src_dir, out_dir = src_dir.resolve(), out_dir.resolve()
    if _inside(out_dir, src_dir):
        raise EditsError([f"output folder {out_dir} is inside the source folder {src_dir}"])
    if _inside(src_dir, out_dir):
        raise EditsError([f"source folder {src_dir} is inside the output folder {out_dir}"])
    if out_dir.exists() and (not out_dir.is_dir() or any(out_dir.iterdir())):
        raise EditsError([f"output folder {out_dir} already exists and is not empty"])
    return out_dir


def _read(path: Path):
    data = path.read_bytes()
    try:
        return data.decode("utf-8"), False
    except UnicodeDecodeError:
        return data.decode("latin-1"), True


def _fix_in_window(lines, line, find):
    """(index, start) of the only occurrence of find at that line, else a reason string."""
    n = len(lines)

    def occurrences(indexes):
        text = "".join(lines[i] for i in indexes)
        starts, pos = [], text.find(find)
        while pos >= 0:
            starts.append(pos)
            pos = text.find(find, pos + 1)
        return starts

    exact = [line - 1] if 1 <= line <= n else []
    for indexes in (exact, list(range(max(0, line - 1 - WINDOW), min(n, line + WINDOW)))):
        if not indexes:
            continue
        found = []
        for i in indexes:  # per line, so positions map back to a line
            pos = lines[i].find(find)
            while pos >= 0:
                found.append((i, pos))
                pos = lines[i].find(find, pos + 1)
        if len(found) == 1:
            return found[0]
        if len(found) > 1:
            return "ambiguous"
    return "not found"


def _target(out_dir: Path, name: str):
    path = (out_dir / name).resolve()
    if not _inside(path, out_dir) or path == out_dir:
        return None
    return path


def apply_edits_tex(main: Path, edits: EditSet, out_dir: Path) -> ApplyResult:
    """Copy the project of main into out_dir and apply the edits there.

    An edit with `replace` is applied at its line, else within +-2 lines (find must occur
    exactly once); comment-only edits touch nothing and count as applied. The originals
    are never modified. Raises EditsError if out_dir is unusable.
    """
    main = Path(main)
    out_dir = _prepare_out_dir(main.parent, Path(out_dir))
    shutil.copytree(main.parent, out_dir, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(*_IGNORED_DIRS, *_IGNORED_FILES))
    result = ApplyResult()
    cache = {}  # path -> (lines, latin1)
    for index, edit in enumerate(edits.edits):
        def fail(reason):
            result.failed.append({"index": index, "reason": reason})

        if edit.replace is None:
            result.applied.append(index)
            continue
        if "\n" in edit.find or "\r" in edit.find or "\n" in edit.replace or "\r" in edit.replace:
            fail("multi-line")
            continue
        path = _target(out_dir, edit.file) if edit.file else None
        if path is None or not path.is_file():
            fail(f"file not found: {edit.file}")
            continue
        if path not in cache:
            text, latin1 = _read(path)
            cache[path] = ([m for m in _LINE.findall(text)], latin1)
            if latin1:
                result.notes.append(f"{edit.file} is not UTF-8: read and written as latin-1")
        lines = cache[path][0]
        hit = _fix_in_window(lines, edit.line, edit.find)
        if isinstance(hit, str):
            fail(hit)
            continue
        i, pos = hit
        lines[i] = lines[i][:pos] + edit.replace + lines[i][pos + len(edit.find):]
        result.applied.append(index)
    for path, (lines, latin1) in cache.items():
        path.write_bytes("".join(lines).encode("latin-1" if latin1 else "utf-8"))
    return result


def _excerpt(text: str, limit=600) -> str:
    text = (text or "").strip()
    return text[-limit:] if len(text) > limit else text


def texdiff(old_main: Path, new_main: Path, out_pdf: Path) -> Path:
    """PDF of the differences between two LaTeX projects (latexdiff, then latexmk)."""
    old_main, new_main, out_pdf = Path(old_main), Path(new_main), Path(out_pdf)
    for main in (old_main, new_main):
        if not main.is_file():
            raise RenderError(f"file not found: {main}")
    if out_pdf.resolve() in (old_main.resolve(), new_main.resolve()):
        raise RenderError(f"output would overwrite the original: {out_pdf}")
    latexdiff = shutil.which("latexdiff")
    if latexdiff is None:
        raise RenderError(_LATEXDIFF_HINT, missing_tool="latexdiff")
    if shutil.which("latexmk") is None:
        render_pdf(new_main, Path(tempfile.gettempdir()))  # raises the latexmk hint
    # inside the new project's folder, so relative \includegraphics paths still resolve
    work = Path(tempfile.mkdtemp(prefix=".hmw-texdiff-", dir=new_main.parent))
    try:
        try:
            proc = subprocess.run([latexdiff, "--flatten", str(old_main.resolve()),
                                   str(new_main.resolve())], capture_output=True,
                                  timeout=_TIMEOUT_S, cwd=new_main.parent)
        except OSError as exc:
            raise RenderError(f"cannot start latexdiff ({exc}). {_LATEXDIFF_HINT}",
                              missing_tool="latexdiff")
        except subprocess.TimeoutExpired:
            raise RenderError(f"latexdiff did not finish within {_TIMEOUT_S} s")
        if proc.returncode != 0 or not proc.stdout.strip():
            raise RenderError(f"latexdiff failed (exit code {proc.returncode}): "
                              f"{_excerpt(proc.stderr.decode('utf-8', 'replace'))}")
        diff = work / "diff.tex"
        diff.write_bytes(proc.stdout)
        pdf = render_pdf(diff, work)
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pdf, out_pdf)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return out_pdf


# --- the `texdiff` command --------------------------------------------------------------


def add_texdiff_arguments(parser):
    parser.add_argument("old_main", help="original main .tex")
    parser.add_argument("new_main", help="corrected main .tex")
    parser.add_argument("-o", "--output", required=True, help="PDF of the differences to write")


def run_texdiff(args) -> int:
    import sys

    try:
        pdf = texdiff(Path(args.old_main), Path(args.new_main), Path(args.output))
    except RenderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3 if exc.missing_tool else 2
    print(f"wrote {pdf}")
    return 0
