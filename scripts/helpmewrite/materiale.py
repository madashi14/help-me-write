"""Read the user's material: folder inventory, safe zip extraction, notebook to Markdown.

The material is untrusted: nothing here is executed, imported or deserialized. Files are only
listed, zip members are copied as text or images, notebooks are read as plain JSON.
"""
import base64
import binascii
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
import zlib
from datetime import date, datetime, timezone
from pathlib import Path

from . import detect

MAX_FILES = 2000
MAX_MEMBER_BYTES = 20 * 1024 * 1024
MAX_EXTRACT_BYTES = 200 * 1024 * 1024
MAX_OUTPUT_LINES = 30
EXTRA_SKIP_DIRS = {".mypy_cache", ".pytest_cache", "env"}

_EXT = {
    "code": ".py .m .c .cpp .h .java .js .ts .r .jl .sh .bat .ps1 .apdl .mac .inp",
    "notebook": ".ipynb",
    "data": ".csv .tsv .json .xlsx .xls .dat .parquet .mat .h5 .hdf5",
    "document": ".md .txt .docx .pdf .tex .bib .odt .rtf",
    "image": ".png .jpg .jpeg .svg .gif .tif .tiff .bmp",
    "archive": ".zip .tar .gz .tgz .7z .rar",
    "model": ".joblib .pkl .pickle .pt .pth .onnx .ckpt .npy .npz",
}
_KIND = {ext: kind for kind, exts in _EXT.items() for ext in exts.split()}
_TEXT_DATA = {".csv", ".tsv", ".json", ".dat", ".txt"}
_TEXT_DOC = {".md", ".txt", ".tex", ".bib"}
_EXTRACT_KINDS = {"code", "notebook", "image"}
_DATE_NOTE = ("File dates are probably those of a copy or an upload, not of the work: "
              "do not use them to date the work; ask the user.")


class MaterialError(Exception):
    """Invalid or unreadable material (reported as a usage error, exit 2)."""


def kind_of(name: str) -> str:
    return _KIND.get(os.path.splitext(name.replace("\\", "/").rsplit("/", 1)[-1])[1].lower(),
                     "other")


def _ext(name: str) -> str:
    return os.path.splitext(name.replace("\\", "/").rsplit("/", 1)[-1])[1].lower()


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


MAX_REPOS = 20


def _skip(name: str) -> bool:
    return detect.skip_dir(name) or name in EXTRA_SKIP_DIRS


# --- zip ----------------------------------------------------------------------------------

def _unsafe_name(name: str) -> str | None:
    if "\x00" in name:
        return "unsafe path: NUL in name"
    norm = name.replace("\\", "/")
    if norm.startswith("/") or re.match(r"^[A-Za-z]:", norm):
        return "unsafe path: absolute or drive letter"
    if ".." in norm.split("/"):
        return "unsafe path: parent folder reference"
    return None


def _extractable(name: str) -> bool:
    kind, ext = kind_of(name), _ext(name)
    return (kind in _EXTRACT_KINDS or (kind == "data" and ext in _TEXT_DATA)
            or (kind == "document" and ext in _TEXT_DOC))


def _zip_date(info) -> str | None:
    try:
        return date(*info.date_time[:3]).isoformat()
    except ValueError:
        return None


def _copy_member(zf, info, target: Path, limit: int) -> int | None:
    """Copy info to target reading at most limit bytes; None (nothing left) if exceeded."""
    target.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    try:
        with zf.open(info) as src, open(target, "wb") as dst:
            while chunk := src.read(65536):
                total += len(chunk)
                if total > limit:
                    break
                dst.write(chunk)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    if total > limit:
        target.unlink(missing_ok=True)
        return None
    return total


def _read_zip(path: Path, rel: str, extract_dir: Path | None) -> dict:
    entry = {"path": rel, "opened": False}
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError, EOFError, zlib.error) as exc:
        entry["error"] = f"cannot open: {exc}"
        return entry
    with zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        entry["opened"] = True
        entry["members"] = [{"name": i.filename, "kind": kind_of(i.filename),
                             "size": i.file_size, "date": _zip_date(i)} for i in infos]
        dates = sorted(m["date"] for m in entry["members"] if m["date"])
        entry["first"], entry["last"] = (dates[0], dates[-1]) if dates else (None, None)
        if extract_dir is None:
            return entry
        dest = extract_dir / rel.replace("/", "__")
        if dest.suffix.lower() == ".zip":
            dest = dest.with_suffix("")
        entry["extracted_to"] = str(dest)
        entry["extracted"], entry["skipped"] = [], []
        if dest.exists():
            entry["note"] = "already extracted"
            return entry
        skipped, used = entry["skipped"], 0
        for info in infos:
            name = info.filename
            mode = (info.external_attr >> 16) & 0o170000
            kind = kind_of(name)
            reason = _unsafe_name(name)
            if reason is None and mode == 0o120000:
                reason = "symbolic link"
            elif reason is None and mode not in (0, 0o100000):
                reason = "special file"
            elif reason is None and kind == "model":
                reason = "model file: listed, never loaded"
            elif reason is None and kind == "archive":
                reason = "nested archive: not opened"
            elif reason is None and not _extractable(name):
                reason = f"type not extracted: {_ext(name) or 'no extension'}"
            elif reason is None and info.file_size > MAX_MEMBER_BYTES:
                reason = f"larger than {MAX_MEMBER_BYTES} bytes"
            elif reason is None and used + info.file_size > MAX_EXTRACT_BYTES:
                reason = f"total extraction limit of {MAX_EXTRACT_BYTES} bytes reached"
            if reason:
                skipped.append({"name": name, "reason": reason})
                continue
            target = dest.joinpath(*name.replace("\\", "/").split("/"))
            if dest.resolve() not in target.resolve().parents or target.exists():
                skipped.append({"name": name, "reason": "unsafe or duplicate destination"})
                continue
            try:
                size = _copy_member(zf, info, target,
                                    min(MAX_MEMBER_BYTES, MAX_EXTRACT_BYTES - used))
            except (zipfile.BadZipFile, EOFError, zlib.error) as exc:
                skipped.append({"name": name, "reason": f"corrupt member: {exc}"})
                continue
            except (OSError, RuntimeError, NotImplementedError) as exc:
                skipped.append({"name": name, "reason": f"cannot extract: {exc}"})
                continue
            if size is None:
                skipped.append({"name": name, "reason": "larger than the extraction limit"})
                continue
            used += size
            entry["extracted"].append({"name": name, "size": size,
                                       "path": target.relative_to(extract_dir).as_posix()})
    return entry


# --- git ----------------------------------------------------------------------------------

def _git_history(work: Path) -> dict | None:
    if not (work / ".git").exists() or shutil.which("git") is None:
        return None
    try:
        done = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-C", str(work), "log",
             "--format=%ad", "--date=short"],
            capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    days = sorted(d for d in done.stdout.split() if d)
    if done.returncode != 0 or not days:
        return None
    return {"commits": len(days), "first": days[0], "last": days[-1]}


# --- inventory ----------------------------------------------------------------------------

def inventory(work: Path, extract_dir: Path | None = None) -> dict:
    work = Path(work)
    skip_extract = extract_dir.resolve() if extract_dir is not None else None
    files, archives, skipped_dirs, counts = [], [], [], {}
    truncated = False
    repo_dirs = []
    for root, dirs, names in os.walk(work):
        if (Path(root) / ".git").exists():  # a directory, or a file for worktrees/submodules
            repo_dirs.append(Path(root))
        keep = []
        for d in sorted(dirs):
            full = Path(root) / d
            if _skip(d) or (skip_extract is not None and full.resolve() == skip_extract):
                skipped_dirs.append(full.relative_to(work).as_posix())
            else:
                keep.append(d)
        dirs[:] = keep
        folder = Path(root).relative_to(work).as_posix()
        for name in sorted(names):
            full = Path(root) / name
            try:
                st = full.stat()
            except OSError:
                continue
            counts[folder] = counts.get(folder, 0) + 1
            if len(files) >= MAX_FILES:
                truncated = True
                continue
            rel = full.relative_to(work).as_posix()
            files.append({"path": rel, "kind": kind_of(name), "size": st.st_size,
                          "modified": _day(st.st_mtime)})
            if _ext(name) == ".zip":
                archives.append(_read_zip(full, rel, extract_dir))
            elif kind_of(name) == "archive":
                archives.append({"path": rel, "opened": False})
    git = _git_history(work)
    git_repos, more_repos = [], max(0, len(repo_dirs) - MAX_REPOS)
    for repo in repo_dirs[:MAX_REPOS]:
        history = _git_history(repo)
        if history:
            git_repos.append({"path": repo.relative_to(work).as_posix(), **history})
    days = sorted(f["modified"] for f in files)
    arc_days = sorted(d for a in archives for d in (a.get("first"), a.get("last")) if d)
    span = (date.fromisoformat(days[-1]) - date.fromisoformat(days[0])).days if days else 0
    many_commits = any(r["commits"] > 1 for r in git_repos) or (git and git["commits"] > 1)
    reliable = bool(days) and not (span <= 1 and not many_commits)
    return {"root": str(work), "files": files, "archives": archives, "git": git,
            "git_repos": git_repos,
            **({"git_repos_note": f"{more_repos} more repositories not listed (limit {MAX_REPOS})"}
               if more_repos else {}),
            "dates": {"files": {"first": days[0] if days else None,
                                "last": days[-1] if days else None},
                      "archives": {"first": arc_days[0] if arc_days else None,
                                   "last": arc_days[-1] if arc_days else None},
                      "reliable": reliable,
                      "note": ("File dates come from the file system; compare them with the "
                               "git history and the archive dates." if reliable
                               else _DATE_NOTE)},
            "skipped_dirs": skipped_dirs, "truncated": truncated,
            "counts_by_dir": dict(sorted(counts.items())) if truncated else {}}


# --- notebook -----------------------------------------------------------------------------

def _text(value) -> str:
    return "".join(value) if isinstance(value, list) else str(value or "")


def _clip(text: str) -> str:
    lines = text.rstrip("\n").split("\n")
    if len(lines) <= MAX_OUTPUT_LINES:
        return "\n".join(lines)
    more = len(lines) - MAX_OUTPUT_LINES
    return "\n".join(lines[:MAX_OUTPUT_LINES] + [f"[... {more} more lines]"])


def notebook_markdown(ipynb: Path, images_dir: Path | None) -> tuple[str, list[Path]]:
    ipynb = Path(ipynb)
    try:
        nb = json.loads(ipynb.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MaterialError(f"{ipynb} is not a valid notebook: {exc}") from None
    cells = nb.get("cells") if isinstance(nb, dict) else None
    if not isinstance(cells, list):
        raise MaterialError(f"{ipynb} is not a valid notebook: no cells")
    out, images = [f"# {ipynb.stem}", ""], []
    for n, cell in enumerate(cells, 1):
        if not isinstance(cell, dict):
            continue
        ctype = str(cell.get("cell_type", "raw"))
        out += [f"## Cell {n} ({ctype})", ""]
        source = _text(cell.get("source")).rstrip("\n")
        if ctype == "code":
            out += ["```python", source, "```", ""]
        elif source:
            out += [source, ""]
        k = 0
        for res in cell.get("outputs") or []:
            if not isinstance(res, dict):
                continue
            kind = res.get("output_type")
            data = res.get("data") if isinstance(res.get("data"), dict) else {}
            if kind == "error":
                out += ["```", f"{res.get('ename', 'Error')}: {res.get('evalue', '')}",
                        "```", ""]
                continue
            text = _text(res.get("text") if kind == "stream" else data.get("text/plain"))
            if "image/png" in data:
                k += 1
                png = _save_png(data["image/png"], images_dir,
                                f"{ipynb.stem}-cell{n}-{k}.png")
                if png is not None:
                    images.append(png)
                    out += [f"![{png.name}]({png.as_posix()})", ""]
                elif text:
                    text = _clip(text)
                    out += ["```", text, "```", ""]
                continue
            if text.strip():
                out += ["```", _clip(text), "```", ""]
    return "\n".join(out).rstrip("\n") + "\n", images


def _save_png(b64, images_dir: Path | None, name: str) -> Path | None:
    if images_dir is None:
        return None
    try:
        raw = base64.b64decode(_text(b64), validate=False)
    except (binascii.Error, ValueError):
        return None
    if not raw.startswith(b"\x89PNG\r\n\x1a\n") or len(raw) > MAX_MEMBER_BYTES:
        return None
    target = Path(images_dir) / name
    if target.exists():
        raise MaterialError(f"image already exists: {target} (it is never overwritten); "
                            f"pass a new --images folder")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return target


# --- command line -------------------------------------------------------------------------

def add_material_arguments(parser):
    parser.add_argument("work", help="work folder to read")
    parser.add_argument("--extract", help="folder where text members of zip files are copied")


def run_material(args) -> int:
    from . import cli

    work = Path(args.work)
    if not work.is_dir():
        raise cli.CliError(f"not a folder: {work}")
    inv = inventory(work, Path(args.extract) if args.extract else None)
    counts = {}
    for f in inv["files"]:
        counts[f["kind"]] = counts.get(f["kind"], 0) + 1
    lines = [f"files: {len(inv['files'])}" + (" (truncated)" if inv["truncated"] else "")]
    lines += [f"  {k}: {v}" for k, v in sorted(counts.items())]
    for a in inv["archives"]:
        if a["opened"]:
            lines.append(f"archive {a['path']}: {len(a['members'])} members, "
                         f"{a['first']} to {a['last']}"
                         + (f", extracted {len(a['extracted'])} to {a['extracted_to']}"
                            if "extracted" in a else ""))
            lines += [f"  skipped {s['name']}: {s['reason']}" for s in a.get("skipped", [])]
        else:
            lines.append(f"archive {a['path']}: not opened")
    g = inv["git"]
    lines.append(f"git: {g['commits']} commits, {g['first']} to {g['last']}" if g
                 else "git: none")
    for r in inv["git_repos"]:
        lines.append(f"git repository {r['path']}: {r['commits']} commits, "
                     f"{r['first']} to {r['last']}")
    if inv.get("git_repos_note"):
        lines.append(inv["git_repos_note"])
    d = inv["dates"]
    lines.append(f"dates: files {d['files']['first']} to {d['files']['last']}, "
                 f"reliable: {str(d['reliable']).lower()}. {d['note']}")
    if inv["skipped_dirs"]:
        lines.append("skipped folders: " + ", ".join(inv["skipped_dirs"]))
    cli.emit(inv, args, text="\n".join(lines))
    return 0


def add_notebook_arguments(parser):
    parser.add_argument("input", help="the .ipynb to read (never modified or run)")
    parser.add_argument("-o", "--output", required=True, help="Markdown file to write")
    parser.add_argument("--images", help="folder where PNG outputs are saved")


def run_notebook(args) -> int:
    from . import cli

    if cli.refuses_existing_output(args.output, sources=[args.input]):
        return 2
    try:
        md, images = notebook_markdown(Path(args.input),
                                       Path(args.images) if args.images else None)
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
    except (MaterialError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {out} ({len(images)} images)")
    return 0
