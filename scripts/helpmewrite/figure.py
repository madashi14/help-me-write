"""Charts from the user's data files (with provenance) and simple block diagrams.

Every plotted number is read from a file and recorded in the provenance, so none is invented.
matplotlib is imported only when something is drawn (Agg backend, no display).
"""
import csv
import io
import json
import re
import textwrap
from pathlib import Path

CHART_TYPES = ("bar", "barh", "line", "scatter")
SUFFIXES = {".png": "png", ".pdf": "pdf", ".svg": "svg"}


class FigureError(Exception):
    """Bad spec or data; the message says what and where."""


def _pyplot():
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot

    return pyplot


# --- reading data ------------------------------------------------------------------------

def to_number(text) -> float:
    """Parse '0,808', '1.234,5' or '0.808' (also plain numbers) into a float."""
    if isinstance(text, bool):
        raise FigureError(f"not a number: {text!r}")
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text).strip().replace(" ", "").replace(" ", "")
    if "," in s and "." in s:
        # the rightmost separator is the decimal one
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        raise FigureError(f"not a number: {str(text).strip()!r}") from None


def load_table(path: Path) -> list[dict[str, str]]:
    """Rows of a CSV as dicts; BOM removed, separator among , ; and tab detected."""
    return _read_table(path)[1]


def _read_table(path: Path):
    """(header, rows) of a CSV."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise FigureError(f"cannot read {path.name}: {exc}") from None
    lines = text.splitlines()
    head = lines[0] if lines else ""
    sep = max((",", ";", "\t"), key=head.count)
    if head.count(sep) == 0:
        sep = ","
    reader = csv.DictReader(io.StringIO(text), delimiter=sep)
    rows = []
    for n, row in enumerate(reader, 1):
        if None in row:
            raise FigureError(f"{path.name}, row {n}: more cells than the header has columns")
        rows.append({k.strip(): (v or "").strip() for k, v in row.items()})
    return [k.strip() for k in (reader.fieldnames or [])], rows


def json_value(path: Path, key: str) -> float:
    """The number at a dotted key (list indices allowed: `per_class.0.f1`) of a JSON file."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise FigureError(f"cannot read {path.name}: {exc}") from None
    node = data
    for part in key.split("."):
        try:
            node = node[int(part)] if isinstance(node, list) else node[part]
        except (KeyError, IndexError, ValueError, TypeError):
            raise FigureError(f"key {key!r} not found in {path.name}") from None
    try:
        return to_number(node)
    except FigureError:
        raise FigureError(f"key {key!r} in {path.name} is not a number: {node!r}") from None


# --- chart -------------------------------------------------------------------------------

def _points_from_csv(spec: dict, base: Path):
    """-> (categories, {series: [value]}, provenance rows)."""
    file, xcol, ycols = spec.get("file"), spec.get("x"), spec.get("y")
    if not file or not xcol or not isinstance(ycols, list) or not ycols:
        raise FigureError('"csv" needs "file", "x" and a non-empty "y" list')
    header, rows = _read_table(base / file)
    for col in [xcol, *ycols]:
        if col not in header:
            raise FigureError(f"column {col!r} not found in {file}")
    if not rows:
        raise FigureError(f"{file} has no data rows")
    labels = spec.get("labels") or {}
    cats, series, prov = [], {}, []
    for n, row in enumerate(rows, 1):
        if xcol not in row:
            raise FigureError(f"column {xcol!r} not found in {file}")
        cats.append(row[xcol])
        for col in ycols:
            if col not in row:
                raise FigureError(f"column {col!r} not found in {file}")
            try:
                value = to_number(row[col])
            except FigureError as exc:
                raise FigureError(f"{file}, column {col!r}, row {n}: {exc}") from None
            name = labels.get(col, col)
            series.setdefault(name, []).append(value)
            prov.append({"series": name, "x": row[xcol], "value": value, "file": file,
                         "where": f"{col}, row {n}"})
    return cats, series, prov


def _points_from_values(items, base: Path):
    if not isinstance(items, list) or not items:
        raise FigureError('"values" must be a non-empty list')
    cats, series, prov = [], {}, []
    for item in items:
        try:
            label, file, key = item["label"], item["file"], item["key"]
        except (KeyError, TypeError):
            raise FigureError('each "values" entry needs "label", "file" and "key"') from None
        name = item.get("series") or ""
        if label in series.get(name, {}):
            raise FigureError(f'"values": label {label!r} appears twice in series {name!r}: '
                              "only one value per label and series can be plotted")
        value = json_value(base / file, key)
        if label not in cats:
            cats.append(label)
        series.setdefault(name, {})[label] = value
        prov.append({"series": name, "x": label, "value": value, "file": file, "where": key})
    # align every series to the categories (missing -> None, left blank)
    return cats, {s: [m.get(c) for c in cats] for s, m in series.items()}, prov


def _fmt(value: float, language) -> str:
    text = f"{value:.2f}"
    return text.replace(".", ",") if language == "it" else text


def render_chart(spec: dict, base: Path, out: Path) -> dict:
    """Draw the chart to `out` (.png, .pdf or .svg); returns the provenance of every value."""
    base, out = Path(base), Path(out)
    kind = spec.get("type")
    if kind not in CHART_TYPES:
        raise FigureError(f'"type" must be one of {", ".join(CHART_TYPES)}, not {kind!r}')
    if out.suffix.lower() not in SUFFIXES:
        raise FigureError(f"unsupported output type {out.suffix!r}: use .png, .pdf or .svg")
    if ("csv" in spec) == ("values" in spec):
        raise FigureError('give exactly one data source: "csv" or "values"')
    cats, series, prov = (_points_from_csv(spec["csv"], base) if "csv" in spec
                          else _points_from_values(spec["values"], base))

    plt = _pyplot()
    from matplotlib.ticker import FuncFormatter

    language = spec.get("language")
    fig, ax = plt.subplots(figsize=(7, 4.2))
    try:
        n = len(series)
        width = 0.8 / n
        numeric_x = None
        if kind in ("line", "scatter"):
            try:
                numeric_x = [to_number(c) for c in cats]
            except FigureError:
                numeric_x = None
        for i, (name, values) in enumerate(series.items()):
            pos = list(range(len(cats)))
            if kind in ("bar", "barh"):
                pos = [p - 0.4 + width * (i + 0.5) for p in pos]
                pairs = [(p, v) for p, v in zip(pos, values) if v is not None]
                draw = ax.bar if kind == "bar" else ax.barh
                bars = draw([p for p, _ in pairs], [v for _, v in pairs],
                            width, label=name or None)
                if spec.get("annotate"):
                    ax.bar_label(bars, labels=[_fmt(v, language) for _, v in pairs],
                                 padding=2, fontsize=8)
            else:
                xs = numeric_x if numeric_x is not None else pos
                pts = [(x, v) for x, v in zip(xs, values) if v is not None]
                plot = ax.plot if kind == "line" else ax.scatter
                kw = {"marker": "o"} if kind == "line" else {}
                plot([x for x, _ in pts], [v for _, v in pts], label=name or None, **kw)
                if spec.get("annotate"):
                    for x, v in pts:
                        ax.annotate(_fmt(v, language), (x, v), textcoords="offset points",
                                    xytext=(0, 5), ha="center", fontsize=8)
        index = list(range(len(cats)))
        if kind == "barh":
            ax.set_yticks(index, cats)
            ax.invert_yaxis()
        elif numeric_x is None:
            crowded = len(cats) > 4 or max(len(c) for c in cats) > 12
            ax.set_xticks(index, cats, rotation=20 if crowded else 0,
                          ha="right" if crowded else "center")
        value_axis = ax.xaxis if kind == "barh" else ax.yaxis
        if language == "it":
            value_axis.set_major_formatter(
                FuncFormatter(lambda v, _: f"{v:g}".replace(".", ",")))
        if spec.get("title"):
            ax.set_title(spec["title"])
        if spec.get("xlabel"):
            ax.set_xlabel(spec["xlabel"])
        if spec.get("ylabel"):
            ax.set_ylabel(spec["ylabel"])
        if spec.get("ylim"):
            try:
                lo, hi = spec["ylim"]
                (ax.set_xlim if kind == "barh" else ax.set_ylim)(float(lo), float(hi))
            except (TypeError, ValueError):
                raise FigureError('"ylim" must be [min, max]') from None
        if n > 1 or (n == 1 and next(iter(series)) and kind in ("line", "scatter")):
            ax.legend(loc="best")
        fig.tight_layout()
        fig.savefig(out, format=SUFFIXES[out.suffix.lower()], dpi=200)
    finally:
        plt.close(fig)
    return {"values": prov}


# --- diagram -----------------------------------------------------------------------------

def _graph(spec: dict):
    nodes = spec.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise FigureError('"nodes" must be a non-empty list')
    ids = []
    for node in nodes:
        if not isinstance(node, dict) or "id" not in node:
            raise FigureError('each node needs an "id"')
        if node["id"] in ids:
            raise FigureError(f"duplicate node id {node['id']!r}")
        ids.append(node["id"])
    edges = []
    for edge in spec.get("edges") or []:
        try:
            a, b = edge["from"], edge["to"]
        except (KeyError, TypeError):
            raise FigureError('each edge needs "from" and "to"') from None
        for end in (a, b):
            if end not in ids:
                raise FigureError(f"edge refers to unknown node {end!r}")
        edges.append((a, b))
    return ids, edges


def _find_cycle(ids, edges):
    out = {i: [b for a, b in edges if a == i] for i in ids}
    state, stack = {}, []

    def visit(n):
        state[n] = 1
        stack.append(n)
        for m in out[n]:
            if state.get(m) == 1:
                return stack[stack.index(m):] + [m]
            if m not in state:
                found = visit(m)
                if found:
                    return found
        stack.pop()
        state[n] = 2
        return None

    for i in ids:
        if i not in state:
            found = visit(i)
            if found:
                return found
    return []


def diagram_ranks(spec: dict) -> dict[str, int]:
    """Rank of each node: the length of the longest path reaching it from a source."""
    ids, edges = _graph(spec)
    rank = {i: 0 for i in ids}
    indeg = {i: sum(1 for _, b in edges if b == i) for i in ids}
    queue = [i for i in ids if indeg[i] == 0]
    done = 0
    while queue:
        n = queue.pop(0)
        done += 1
        for a, b in edges:
            if a == n:
                rank[b] = max(rank[b], rank[n] + 1)
                indeg[b] -= 1
                if indeg[b] == 0:
                    queue.append(b)
    if done < len(ids):
        cycle = _find_cycle(ids, edges)
        raise FigureError("the diagram has a cycle: " + " -> ".join(map(str, cycle)))
    return rank


def render_diagram(spec: dict, out: Path) -> None:
    """Draw boxes and arrows (LR or TB) to `out` (.png, .pdf or .svg)."""
    out = Path(out)
    if out.suffix.lower() not in SUFFIXES:
        raise FigureError(f"unsupported output type {out.suffix!r}: use .png, .pdf or .svg")
    direction = spec.get("direction", "LR")
    if direction not in ("LR", "TB"):
        raise FigureError(f'"direction" must be LR or TB, not {direction!r}')
    ranks = diagram_ranks(spec)
    labels = {n["id"]: n.get("label", str(n["id"])) for n in spec["nodes"]}
    slot, pos = {}, {}
    box_w, box_h, gap_x, gap_y = 2.4, 1.0, 1.4, 0.9
    for nid in labels:
        r = ranks[nid]
        k = slot.get(r, 0)
        slot[r] = k + 1
        if direction == "LR":
            pos[nid] = (r * (box_w + gap_x), -k * (box_h + gap_y))
        else:
            pos[nid] = (k * (box_w + gap_x), -r * (box_h + gap_y))

    plt = _pyplot()
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    fig, ax = plt.subplots(figsize=(max(3, (max(xs) - min(xs) + box_w + 1) * 0.7),
                                    max(2, (max(ys) - min(ys) + box_h + 1) * 0.7)))
    try:
        patches = {}
        for nid, (cx, cy) in pos.items():
            patch = FancyBboxPatch((cx - box_w / 2, cy - box_h / 2), box_w, box_h,
                                   boxstyle="round,pad=0.05,rounding_size=0.2",
                                   facecolor="#eef3fa", edgecolor="#33475b", linewidth=1.2)
            ax.add_patch(patch)
            patches[nid] = patch
            ax.text(cx, cy, textwrap.fill(str(labels[nid]), 18), ha="center", va="center",
                    fontsize=9)
        for edge in spec.get("edges") or []:
            a, b = edge["from"], edge["to"]
            ax.add_patch(FancyArrowPatch(pos[a], pos[b], arrowstyle="-|>", mutation_scale=14,
                                         patchA=patches[a], patchB=patches[b],
                                         shrinkA=2, shrinkB=2, color="#33475b"))
            if edge.get("label"):
                ax.text((pos[a][0] + pos[b][0]) / 2, (pos[a][1] + pos[b][1]) / 2,
                        str(edge["label"]), ha="center", va="bottom", fontsize=8,
                        bbox={"facecolor": "white", "edgecolor": "none", "pad": 1})
        ax.set_xlim(min(xs) - box_w / 2 - 0.4, max(xs) + box_w / 2 + 0.4)
        ax.set_ylim(min(ys) - box_h / 2 - 0.4, max(ys) + box_h / 2 + 0.4)
        ax.set_aspect("equal")
        ax.axis("off")
        fig.tight_layout()
        fig.savefig(out, format=SUFFIXES[out.suffix.lower()], dpi=200)
    finally:
        plt.close(fig)


# --- command line ------------------------------------------------------------------------

def _add_arguments(parser, what):
    parser.add_argument("spec", help=f"the {what} description (JSON)")
    parser.add_argument("-o", "--output", required=True,
                        help="image to write (.png, .pdf or .svg); never overwritten")


def add_chart_arguments(parser):
    _add_arguments(parser, "chart")


def add_diagram_arguments(parser):
    _add_arguments(parser, "diagram")


def _load_spec(path) -> dict:
    try:
        spec = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise FigureError(f"cannot read the spec {path}: {exc}") from None
    if not isinstance(spec, dict):
        raise FigureError(f"the spec {path} must be a JSON object")
    return spec


def _free_pair(out: Path) -> Path:
    """First image name (out, -2, -3, ...) whose image and provenance file are both free."""
    n = 1
    while True:
        cand = out if n == 1 else out.with_name(f"{out.stem}-{n}{out.suffix}")
        if not cand.exists() and not cand.with_name(cand.name + ".fonte.json").exists():
            return cand
        n += 1


def _run(args, chart: bool) -> int:
    import sys

    from . import cli

    out = Path(args.output)
    prov_path = out.with_name(out.name + ".fonte.json")
    if cli.refuses_existing_output(out, sources=[args.spec]):
        return 2
    if chart and prov_path.exists():
        print(f"error: provenance file already exists: {prov_path} (it is never overwritten); "
              f"use a new image name, e.g. {_free_pair(out)}", file=sys.stderr)
        return 2
    try:
        spec = _load_spec(args.spec)
        out.parent.mkdir(parents=True, exist_ok=True)
        if chart:
            prov = render_chart(spec, Path(args.spec).resolve().parent, out)
            try:
                prov_path.write_text(json.dumps(prov, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")
            except OSError:
                out.unlink(missing_ok=True)
                raise
        else:
            render_diagram(spec, out)
    except FigureError as exc:
        out.unlink(missing_ok=True)
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: cannot write {out}: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {out}" + (f" and {prov_path}" if chart else ""))
    return 0


def run_chart(args) -> int:
    return _run(args, True)


def run_diagram(args) -> int:
    return _run(args, False)
