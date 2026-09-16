#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sci-drawio CLI — deterministic builder / validator / deliverer for scientific
figures in draw.io (科研绘图).

Pipeline:  JSON 图规格(spec) -> draw.io XML(.drawio) -> 校验 -> 打开/导出/URL

Stdlib-only, cross-platform (Windows / macOS / Linux), zero pip dependencies.
The agent (LLM) is the designer: it produces a structured JSON spec (see
references/diagram-spec-schema.md). This script turns the spec into
well-formed draw.io XML and hands it to the locally installed draw.io.

Subcommands:
  build     spec.json -o out.drawio           生成 .drawio 文件
  validate  file.drawio                        校验 XML 结构与引用完整性
  open      file.drawio [--layout NAME]        用本机 draw.io 打开(可编辑)
  export    file.drawio -f png -o out.png      导出 PNG/SVG/PDF 预览
  url       file.drawio                        生成可在浏览器打开的 draw.io 链接
  inspect   file.drawio                        打印节点/连线/容器统计
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import zlib
from html import escape

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
THEMES_PATH = os.path.join(SKILL_DIR, "assets", "themes.json")

DEFAULT_W = 150
DEFAULT_H = 60
PAD = 20              # container inner padding
TITLE_H = 60
GAP = 30              # gap between packed items (auto layout)
GRID_MIN_W = 200      # minimum top-level slot width
GRID_MIN_H = 120      # minimum top-level slot height

SHAPE_STYLES = {
    "rect":            "whiteSpace=wrap;html=1;",
    "rounded":         "rounded=1;whiteSpace=wrap;html=1;",
    "ellipse":         "ellipse;whiteSpace=wrap;html=1;",
    "double_ellipse":  "ellipse;whiteSpace=wrap;html=1;shape=doubleEllipse;",
    "rhombus":         "rhombus;whiteSpace=wrap;html=1;",
    "cylinder":        "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;",
    "parallelogram":   "shape=parallelogram;whiteSpace=wrap;html=1;perimeter=parallelogramPerimeter;",
    "hexagon":         "shape=hexagon;whiteSpace=wrap;html=1;perimeter=hexagonPerimeter2;",
    "process":         "shape=process;whiteSpace=wrap;html=1;",
    "document":        "shape=document;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=12;",
    "cloud":           "shape=cloud;whiteSpace=wrap;html=1;",
    "actor":           "shape=actor;whiteSpace=wrap;html=1;",
    "note":            "shape=note;whiteSpace=wrap;html=1;size=14;",
    "text":            "text;html=1;align=center;",
    "swimlane":        "swimlane;horizontal=0;startSize=110;html=1;",
}

FONT_STYLE = {"normal": 0, "bold": 1, "italic": 2, "bold-italic": 3}

# arrow semantics -> draw.io style fragments
# verified against draw.io 31.4.5 via SVG path analysis:
#   classic/block -> filled triangle; open -> hollow V; oval -> filled circle
#   ERone -> perpendicular T-bar (inhibition); diamond -> filled diamond
#   sharp/tech/techThin -> render NOTHING in 31.4.5 (avoid)
ARROW_STYLES = {
    "activation":    "endArrow=classic;endFill=1;",
    "inhibition":    "endArrow=ERone;endFill=0;",
    "translocation": "endArrow=open;endFill=0;",
    "association":   "endArrow=oval;endFill=1;",
    "production":    "endArrow=classic;endFill=1;",
    "none":          "endArrow=none;",
}

DEFAULT_THEMES = {
    "nature": {
        "bg": "#FFFFFF",
        "default": {"fill": "#4C72B0", "stroke": "#2B4A7A", "font": "#FFFFFF"},
        "alt":     {"fill": "#DD8452", "stroke": "#8A5220", "font": "#FFFFFF"},
        "alt2":    {"fill": "#55A868", "stroke": "#2E6B3C", "font": "#FFFFFF"},
        "alt3":    {"fill": "#C44E52", "stroke": "#7E2A2E", "font": "#FFFFFF"},
        "alt4":    {"fill": "#8172B3", "stroke": "#4E4280", "font": "#FFFFFF"},
        "alt5":    {"fill": "#937860", "stroke": "#5E4A38", "font": "#FFFFFF"},
        "muted":   {"fill": "#EAF0F6", "stroke": "#8FA3B8", "font": "#22303E"},
        "container": {"fill": "#F7F9FB", "stroke": "#C5D0DA", "font": "#22303E"},
        "edge": "#4C72B0", "edge_alt": "#8C98A8",
    },
    "minimal": {
        "bg": "#FFFFFF",
        "default": {"fill": "#F2F2F2", "stroke": "#333333", "font": "#111111"},
        "alt":     {"fill": "#FFFFFF", "stroke": "#555555", "font": "#111111"},
        "alt2":    {"fill": "#E8E8E8", "stroke": "#333333", "font": "#111111"},
        "alt3":    {"fill": "#D9D9D9", "stroke": "#333333", "font": "#111111"},
        "alt4":    {"fill": "#F5F5F5", "stroke": "#555555", "font": "#111111"},
        "alt5":    {"fill": "#E0E0E0", "stroke": "#444444", "font": "#111111"},
        "muted":   {"fill": "#FAFAFA", "stroke": "#AAAAAA", "font": "#333333"},
        "container": {"fill": "#FFFFFF", "stroke": "#999999", "font": "#111111"},
        "edge": "#333333", "edge_alt": "#888888",
    },
    "cell": {
        "bg": "#FFFFFF",
        "default": {"fill": "#F4B183", "stroke": "#C55A11", "font": "#FFFFFF"},
        "alt":     {"fill": "#9DC3E6", "stroke": "#2E75B6", "font": "#FFFFFF"},
        "alt2":    {"fill": "#A9D18E", "stroke": "#538135", "font": "#FFFFFF"},
        "alt3":    {"fill": "#FFD966", "stroke": "#BF8F00", "font": "#5A4A00"},
        "alt4":    {"fill": "#B4A7D6", "stroke": "#7030A0", "font": "#FFFFFF"},
        "alt5":    {"fill": "#F8CBAD", "stroke": "#C55A11", "font": "#5A2A00"},
        "muted":   {"fill": "#FDF2E9", "stroke": "#C9A892", "font": "#4A3A2E"},
        "container": {"fill": "#FBF6EF", "stroke": "#D9C4AD", "font": "#3A2E22"},
        "edge": "#7F5A3A", "edge_alt": "#A99B8C",
    },
}

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def eprint(*a):
    print(*a, file=sys.stderr)


def die(msg, code=1):
    eprint("Error: " + msg)
    sys.exit(code)


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception as ex:
        die("cannot read %s: %s" % (path, ex))


def esc_attr(s):
    """Escape a string for use inside an XML attribute value.

    Labels may contain HTML markup (<b>, <br>, <font color=...>, <sub>...).
    We escape for the attribute context; draw.io renders it when html=1.
    """
    if s is None:
        return ""
    s = str(s).replace("\n", "&#xa;").replace("\r", "")
    return escape(s, quote=True)


def load_themes():
    themes = dict(DEFAULT_THEMES)
    if os.path.exists(THEMES_PATH):
        try:
            with open(THEMES_PATH, "r", encoding="utf-8-sig") as f:
                extra = json.load(f)
            themes.update(extra)
        except Exception as ex:
            eprint("warning: cannot load themes.json (%s); using built-ins" % ex)
    return themes


def find_drawio():
    """Locate the draw.io desktop executable."""
    env = os.environ.get("DRAWIO_PATH")
    candidates = []
    if env:
        candidates.append(env)
    candidates += [
        "drawio", "draw.io", "drawio.exe",
        r"C:\Program Files\draw.io\draw.io.exe",
        r"C:\Program Files (x86)\draw.io\draw.io.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "draw.io", "draw.io.exe"),
        r"E:\安装包\draw.io-31.4.5-windows\draw.io.exe",   # common portable location
        "/Applications/draw.io.app/Contents/MacOS/draw.io",
        "/usr/bin/drawio", "/usr/local/bin/drawio", "/opt/homebrew/bin/drawio",
        "/snap/bin/drawio",
    ]
    for c in candidates:
        if not c:
            continue
        if os.path.sep in c or "/" in c:
            if os.path.exists(c):
                return c
        else:
            hit = shutil.which(c)
            if hit:
                return hit
    return None


# ---------------------------------------------------------------------------
# layout
# ---------------------------------------------------------------------------


def _ids(nodes):
    ids = [n["id"] for n in nodes]
    if len(set(ids)) != len(ids):
        dup = [i for i in ids if ids.count(i) > 1]
        die("duplicate node ids: %s" % sorted(set(dup)))
    return ids


def assign_ranks(nodes, edges):
    """Longest-path layering; explicit 'rank' acts as a floor.
    Cycles (feedback loops) are tolerated: DFS back-edges are skipped
    for ranking and render as upward/curved edges."""
    ids = _ids(nodes)
    node_map = {n["id"]: n for n in nodes}
    adj = {i: [] for i in ids}
    for e in edges:
        if e.get("from") in adj and e.get("to") in adj:
            adj[e["from"]].append(e["to"])

    state = {i: 0 for i in ids}   # 0=unvisited 1=on stack 2=done
    memo = {}
    back = set()

    def lp(i):
        if i in memo:
            return memo[i]
        r = node_map[i].get("rank")
        if r is not None:
            memo[i] = int(r)
            state[i] = 2
            return memo[i]
        state[i] = 1
        best = 0
        for j in adj[i]:
            if state[j] == 1:          # back edge -> cycle, skip for ranking
                back.add((i, j))
                continue
            best = max(best, lp(j) + 1)
        state[i] = 2
        memo[i] = best
        return best

    for i in ids:
        if state[i] == 0:
            lp(i)

    # enforce order on acyclic edges only (respects explicit-rank floors)
    changed = True
    guard = 0
    while changed and guard < len(ids) + 1:
        changed = False
        guard += 1
        for e in edges:
            f, t = e.get("from"), e.get("to")
            if (f, t) in back or f not in memo or t not in memo:
                continue
            if memo[t] <= memo[f]:
                memo[t] = memo[f] + 1
                changed = True
    return memo


def pack_row(items, start_x, start_y, gap):
    """Place items left-to-right; return (positions, row_width, row_height)."""
    x = start_x
    max_h = 0
    out = {}
    for it in items:
        w = it.get("_w", DEFAULT_W)
        h = it.get("_h", DEFAULT_H)
        out[it["id"]] = (x, start_y)
        x += w + gap
        max_h = max(max_h, h)
    return out, x - gap - start_x + (gap if items else 0), max_h


def build_layout(spec, themes):
    """Compute x/y/w/h for every node & container. Returns
    (node_geo, container_geo) dicts keyed by id."""
    nodes = spec.get("nodes", [])
    edges = spec.get("edges", [])
    containers = spec.get("containers", [])
    title = spec.get("title")
    theme = themes.get(spec.get("theme", "nature"), themes["nature"])

    node_map = {n["id"]: n for n in nodes}
    cont_map = {c["id"]: c for c in containers}

    auto = spec.get("layout", "auto") == "auto"
    if auto:
        # auto mode: everything placed by rank/order; explicit x/y ignored
        any_missing = True
    else:
        any_missing = any(n.get("x") is None for n in nodes) or \
                      any(c.get("x") is None for c in containers)
        if any_missing:
            auto = True

    # ---- node sizes -------------------------------------------------------
    for n in nodes:
        n["_w"] = int(n.get("w", DEFAULT_W))
        n["_h"] = int(n.get("h", DEFAULT_H))
    for c in containers:
        c["_w"] = int(c.get("w", 0) or 0)
        c["_h"] = int(c.get("h", 0) or 0)

    # ---- node colors ------------------------------------------------------
    tone = theme.get("default")
    for n in nodes:
        t = theme.get(n.get("tone", "default"), theme["default"])
        n.setdefault("fill", t["fill"])
        n.setdefault("stroke", t["stroke"])
        n.setdefault("fontColor", t["font"])

    node_geo = {}
    cont_geo = {}

    if not auto:
        # ---------------- manual mode -------------------------------------
        for n in nodes:
            node_geo[n["id"]] = {
                "x": float(n["x"]), "y": float(n["y"]),
                "w": n["_w"], "h": n["_h"],
                "container": n.get("container"),
                "layer": n.get("layer", "1"),
            }
        for c in containers:
            cx, cy = float(c["x"]), float(c["y"])
            cw, ch = c["_w"], c["_h"]
            if not cw or not ch:  # auto-size from children
                cw, ch = GRID_MIN_W, GRID_MIN_H
            cont_geo[c["id"]] = {"x": cx, "y": cy, "w": cw, "h": ch,
                                 "layer": c.get("layer", "1")}
        _size_containers_to_children(containers, node_geo, cont_geo)
        return node_geo, cont_geo

    # ---------------- auto mode -------------------------------------------
    origin_x = 40
    origin_y = (TITLE_H + 40) if title else 40

    # 1) children inside containers: pack locally
    for c in containers:
        kids = [n for n in nodes if n.get("container") == c["id"]]
        if not kids:
            continue
        ranks = assign_ranks(kids, [e for e in edges if e.get("from") in node_map and e.get("to") in node_map])
        # group by rank, pack
        rank_items = {}
        for k in kids:
            rank_items.setdefault(ranks[k["id"]], []).append(k)
        y = c.get("startSize", 30) + PAD
        max_w = 0
        for r in sorted(rank_items):
            items = sorted(rank_items[r], key=lambda k: (k.get("order", 10 ** 9), k["id"]))
            pos, rw, rh = pack_row(items, PAD, y, GAP)
            for kid_id, (kx, ky) in pos.items():
                kid = node_map[kid_id]
                node_geo[kid_id] = {"x": kx, "y": ky, "w": kid["_w"], "h": kid["_h"],
                                    "container": c["id"], "layer": kid.get("layer", c.get("layer", "1"))}
            max_w = max(max_w, rw)
            y += rh + GAP
        c["_child_extent"] = (max_w + 2 * PAD, y - GAP + PAD)

    # 2) free nodes (no container) + containers: top-level grid by rank/order
    top_nodes = [n for n in nodes if not n.get("container")]
    top_ids = [n["id"] for n in top_nodes]
    cont_ids = [c["id"] for c in containers]

    # ranks for free nodes
    rank_map = {}
    if top_nodes:
        r = assign_ranks(top_nodes, [e for e in edges if e.get("from") in node_map and e.get("to") in node_map])
        rank_map.update(r)
    for c in containers:
        rank_map[c["id"]] = int(c.get("rank", 0))

    rank_items = {}
    for n in top_nodes:
        rank_items.setdefault(rank_map[n["id"]], []).append(n)
    for c in containers:
        rank_items.setdefault(rank_map[c["id"]], []).append(c)

    y = origin_y
    for r in sorted(rank_items):
        items = sorted(rank_items[r], key=lambda it: (it.get("order", 10 ** 9), it["id"]))
        x = origin_x
        max_h = 0
        for it in items:
            if it["id"] in cont_map:
                c = cont_map[it["id"]]
                cw = c["_w"] or GRID_MIN_W
                if c.get("_child_extent"):
                    cw = max(GRID_MIN_W, c["_child_extent"][0])
                ch = c["_h"] or GRID_MIN_H
                if c.get("_child_extent"):
                    ch = max(GRID_MIN_H, c["_child_extent"][1])
                cont_geo[c["id"]] = {"x": x, "y": y, "w": cw, "h": ch,
                                     "layer": c.get("layer", "1")}
                c["_w"], c["_h"] = cw, ch
                x += cw + GAP
                max_h = max(max_h, ch)
            else:
                node_geo[it["id"]] = {"x": x, "y": y, "w": it["_w"], "h": it["_h"],
                                      "container": None, "layer": it.get("layer", "1")}
                x += it["_w"] + GAP
                max_h = max(max_h, it["_h"])
        y += max_h + GAP

    # 3) children placed before containers: offset by container origin
    for c in containers:
        if c["id"] in cont_geo:
            ox, oy = cont_geo[c["id"]]["x"], cont_geo[c["id"]]["y"]
            for kid in nodes:
                if kid.get("container") == c["id"] and kid["id"] in node_geo:
                    # already local; keep local (children coords are relative)
                    pass
    _size_containers_to_children(containers, node_geo, cont_geo, auto=auto)
    return node_geo, cont_geo


def _size_containers_to_children(containers, node_geo, cont_geo, auto=False):
    """Grow containers that have no explicit size to fit their children."""
    for c in containers:
        kids = [n for n in node_geo.values() if n.get("container") == c["id"]]
        if not kids:
            continue
        cw = max(k["x"] + k["w"] for k in kids) + PAD
        ch = max(k["y"] + k["h"] for k in kids) + PAD
        g = cont_geo[c["id"]]
        if auto or not c.get("w"):
            g["w"] = max(g.get("w", 0), cw)
        if auto or not c.get("h"):
            g["h"] = max(g.get("h", 0), ch)


# ---------------------------------------------------------------------------
# XML emission
# ---------------------------------------------------------------------------


def node_style(n, theme):
    shape = n.get("shape", "rounded")
    base = SHAPE_STYLES.get(shape, SHAPE_STYLES["rounded"])
    parts = [base]
    fill = n.get("fill")
    stroke = n.get("stroke")
    font = n.get("fontColor")
    if fill:
        parts.append("fillColor=%s;" % fill)
    if stroke:
        parts.append("strokeColor=%s;" % stroke)
    if font:
        parts.append("fontColor=%s;" % font)
    fs = n.get("fontStyle", "normal")
    if fs in FONT_STYLE and FONT_STYLE[fs]:
        parts.append("fontStyle=%d;" % FONT_STYLE[fs])
    if n.get("dashed"):
        parts.append("dashed=1;")
    if n.get("fontSize"):
        parts.append("fontSize=%s;" % n["fontSize"])
    if n.get("align"):
        parts.append("align=%s;" % n["align"])
    if n.get("verticalAlign"):
        parts.append("verticalAlign=%s;" % n["verticalAlign"])
    if n.get("opacity"):
        parts.append("opacity=%s;" % n["opacity"])
    if n.get("whiteSpace") == "nowrap":
        parts.append("whiteSpace=nowrap;")
    return "".join(parts)


def edge_style(e, theme):
    style = e.get("style", "orthogonal")
    parts = []
    if style == "raw":
        # passthrough: caller provides the full style string, no defaults added
        return e.get("rawStyle", "")
    if style == "orthogonal":
        parts.append("edgeStyle=orthogonalEdgeStyle;rounded=1;")
    elif style == "curved":
        parts.append("curved=1;")
    # straight: nothing
    parts.append("html=1;")
    arrow = ARROW_STYLES.get(e.get("arrow", "activation"), ARROW_STYLES["activation"])
    parts.append(arrow)
    if e.get("dashed"):
        parts.append("dashed=1;")
    parts.append("strokeColor=%s;" % e.get("color", theme["edge"]))
    parts.append("strokeWidth=%s;" % int(e.get("width", 2)))
    if e.get("startArrow"):
        sa = ARROW_STYLES.get(e["startArrow"], "")
        if sa:
            parts.append(sa.replace("endArrow", "startArrow").replace("endFill", "startFill"))
    return "".join(parts)


def build_xml(spec, node_geo, cont_geo, themes):
    nodes = spec.get("nodes", [])
    edges = spec.get("edges", [])
    containers = spec.get("containers", [])
    layers = spec.get("layers", [])
    legend = spec.get("legend", [])
    notes = spec.get("notes", [])
    title = spec.get("title")
    theme = themes.get(spec.get("theme", "nature"), themes["nature"])

    name = esc_attr(spec.get("name", "sci-figure"))

    # ---- collect geometry & bbox -----------------------------------------
    cells = []  # list of (kind, dict)

    layer_ids = ["1"]
    for i, ly in enumerate(layers):
        layer_ids.append(ly["id"])

    for c in containers:
        g = cont_geo[c["id"]]
        cells.append(("container", c, g))
    for n in nodes:
        g = node_geo[n["id"]]
        cells.append(("node", n, g))
    for e in edges:
        cells.append(("edge", e, None))

    xs = []
    ys = []
    xe = []
    ye = []
    for kind, obj, g in cells:
        if kind == "edge":
            continue
        xs.append(g["x"]); ys.append(g["y"])
        xe.append(g["x"] + g["w"]); ye.append(g["y"] + g["h"])
    if xs:
        min_x, min_y = min(xs), min(ys)
        max_x, max_y = max(xe), max(ye)
    else:
        min_x = min_y = 0
        max_x, max_y = 800, 600
    bbox_w = max_x - min_x
    bbox_h = max_y - min_y

    # title (skip auto title when nodes already define a node with id="title")
    has_title_node = any(n.get("id") == "title" for n in nodes)
    if title and not has_title_node:
        tw = max(400, bbox_w)
        cells.insert(0, ("title", title, {"x": min_x, "y": 10, "w": tw, "h": 40}))

    # legend
    legend_h = 0
    if legend:
        lh = len(legend) * 26 + 40
        legend_h = lh
        cells.append(("legend", legend, {"x": min_x, "y": max_y + 80, "w": 260, "h": lh}))

    # notes
    for i, nt in enumerate(notes):
        nx = nt.get("x", min_x)
        ny = nt.get("y", max_y + (100 + legend_h) if legend_h else max_y + 40)
        cells.append(("note", nt, {"x": nx, "y": ny, "w": nt.get("w", 360), "h": nt.get("h", 30)}))

    # ---- emit -------------------------------------------------------------
    out = []
    out.append('<mxfile host="app.diagrams.net" agent="sci-drawio" version="31.4.5" type="device">')
    out.append('<diagram id="%s" name="%s">' % (esc_attr(spec.get("diagramId", "sci-drawio-1")), name))
    pw = max(1169, int(max_x + 120))
    ph = max(827, int(max_y + 120 + legend_h))
    out.append('<mxGraphModel dx="1100" dy="750" grid="1" gridSize="10" guides="1" '
               'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
               'pageWidth="%d" pageHeight="%d" math="0" shadow="0" adaptiveColors="auto">' % (pw, ph))
    out.append("<root>")
    out.append('<mxCell id="0"/>')
    out.append('<mxCell id="1" parent="0"/>')
    for i, ly in enumerate(layers):
        out.append('<mxCell id="%s" value="%s" parent="0"/>' % (esc_attr(ly["id"]), esc_attr(ly.get("name", ""))))

    id_counter = [1000]

    def nid(prefix):
        id_counter[0] += 1
        return "%s%d" % (prefix, id_counter[0])

    # containers
    for kind, obj, g in cells:
        if kind != "container":
            continue
        c = obj
        style = c.get("style") or (
            "swimlane;startSize=%d;fillColor=%s;strokeColor=%s;fontColor=%s;html=1;"
            % (int(c.get("startSize", 30)),
               c.get("fill", theme["container"]["fill"]),
               c.get("stroke", theme["container"]["stroke"]),
               c.get("fontColor", theme["container"]["font"])))
        cid = c["id"]
        out.append('<mxCell id="%s" value="%s" style="%s" vertex="1" parent="%s">'
                   % (esc_attr(cid), esc_attr(c.get("label", "")), style,
                      esc_attr(c.get("layer", "1"))))
        out.append('<mxGeometry x="%s" y="%s" width="%s" height="%s" as="geometry"/>'
                   % (_n(g["x"]), _n(g["y"]), _n(g["w"]), _n(g["h"])))
        out.append("</mxCell>")

    # nodes
    for kind, obj, g in cells:
        if kind != "node":
            continue
        n = obj
        st = node_style(n, theme)
        pid = n.get("layer", "1")
        if g.get("container"):
            pid = g["container"]
        out.append('<mxCell id="%s" value="%s" style="%s" vertex="1" parent="%s">'
                   % (esc_attr(n["id"]), esc_attr(n.get("label", "")), st, esc_attr(pid)))
        out.append('<mxGeometry x="%s" y="%s" width="%s" height="%s" as="geometry"/>'
                   % (_n(g["x"]), _n(g["y"]), _n(g["w"]), _n(g["h"])))
        out.append("</mxCell>")

    # edges
    for kind, obj, g in cells:
        if kind != "edge":
            continue
        e = obj
        st = edge_style(e, theme)
        out.append('<mxCell id="%s" value="%s" style="%s" edge="1" parent="%s" '
                   'source="%s" target="%s">'
                   % (esc_attr(e["id"]), esc_attr(e.get("label", "")), st,
                      esc_attr(e.get("layer", "1")), esc_attr(e["from"]), esc_attr(e["to"])))
        out.append('<mxGeometry relative="1" as="geometry"/>')
        out.append("</mxCell>")

    # title
    for kind, obj, g in cells:
        if kind != "title":
            continue
        out.append('<mxCell id="%s" value="%s" style="text;html=1;align=center;fontSize=16;fontStyle=1;fontColor=%s;" vertex="1" parent="1">'
                   % (nid("t_"), esc_attr(obj), theme["default"]["font"] if False else "#111111"))
        out.append('<mxGeometry x="%s" y="%s" width="%s" height="%s" as="geometry"/>'
                   % (_n(g["x"]), _n(g["y"]), _n(g["w"]), _n(g["h"])))
        out.append("</mxCell>")

    # legend
    for kind, obj, g in cells:
        if kind != "legend":
            continue
        cid = nid("leg_")
        out.append('<mxCell id="%s" value="图例 Legend" style="swimlane;startSize=24;fillColor=%s;strokeColor=%s;html=1;" vertex="1" parent="1">'
                   % (cid, theme["container"]["fill"], theme["container"]["stroke"]))
        out.append('<mxGeometry x="%s" y="%s" width="%s" height="%s" as="geometry"/>'
                   % (_n(g["x"]), _n(g["y"]), _n(g["w"]), _n(g["h"])))
        out.append("</mxCell>")
        yy = g["y"] + 34
        for item in obj:
            glyph = legend_glyph(item.get("arrow", "activation"), item.get("dashed"))
            color = item.get("color", theme["edge"])
            lid = nid("legi_")
            html = '<font color="%s">%s</font> %s' % (color, glyph, item.get("label", ""))
            out.append('<mxCell id="%s" value="%s" style="text;html=1;align=left;fontSize=11;" vertex="1" parent="1">'
                       % (lid, esc_attr(html)))
            out.append('<mxGeometry x="%s" y="%s" width="%s" height="22" as="geometry"/>'
                       % (_n(g["x"] + 12), _n(yy), 236, ))
            out.append("</mxCell>")
            yy += 26

    # notes
    for kind, obj, g in cells:
        if kind != "note":
            continue
        nid_ = nid("note_")
        out.append('<mxCell id="%s" value="%s" style="text;html=1;align=left;fontSize=11;fontStyle=2;fontColor=#666666;" vertex="1" parent="1">'
                   % (nid_, esc_attr(obj.get("text", ""))))
        out.append('<mxGeometry x="%s" y="%s" width="%s" height="%s" as="geometry"/>'
                   % (_n(g["x"]), _n(g["y"]), _n(g["w"]), _n(g["h"])))
        out.append("</mxCell>")

    out.append("</root>")
    out.append("</mxGraphModel>")
    out.append("</diagram>")
    out.append("</mxfile>")

    stats = {
        "nodes": len(nodes), "edges": len(edges),
        "containers": len(containers), "layers": len(layers) + 1,
        "bbox": "%d x %d" % (int(max_x - min_x), int(max_y - min_y)),
    }
    return "\n".join(out) + "\n", stats


def legend_glyph(arrow, dashed):
    dash = "┄" if dashed else "─"
    tail = dash * 2
    heads = {
        "activation": "►", "inhibition": "⊣", "translocation": "▷",
        "association": "●", "production": "■", "none": "",
    }
    return tail + heads.get(arrow, "►")


def _n(v):
    v = float(v)
    return ("%d" % v) if v == int(v) else ("%g" % v)


# ---------------------------------------------------------------------------
# build / validate / inspect
# ---------------------------------------------------------------------------


def cmd_build(args):
    spec = load_json(args.spec)
    for key in ("nodes", "edges"):
        if key not in spec:
            die("spec must contain '%s' (see references/diagram-spec-schema.md)" % key)
    themes = load_themes()
    node_geo, cont_geo = build_layout(spec, themes)
    xml, stats = build_xml(spec, node_geo, cont_geo, themes)
    out = args.output or (os.path.splitext(args.spec)[0] + ".drawio")
    with open(out, "w", encoding="utf-8") as f:
        f.write(xml)
    print("built %s" % out)
    print("  nodes=%d edges=%d containers=%d layers=%d bbox=%s"
          % (stats["nodes"], stats["edges"], stats["containers"],
             stats["layers"], stats["bbox"]))
    errs = validate_xml(xml, quiet=True)
    if errs:
        die("generated XML failed validation: %s" % "; ".join(errs))
    return out


def parse_xml(content):
    import xml.etree.ElementTree as ET
    return ET.fromstring(content)


def validate_xml(content, quiet=False):
    """Return list of problems (empty == valid)."""
    errs = []
    try:
        root = parse_xml(content)
    except Exception as ex:
        return ["XML not well-formed: %s" % ex]
    cells = root.iter("mxCell")
    ids = {}
    edges = []
    vertices = []
    for cell in cells:
        cid = cell.get("id")
        if cid is not None:
            if cid in ids:
                errs.append("duplicate cell id '%s'" % cid)
            ids[cid] = cell
        if cell.get("edge") == "1":
            edges.append(cell)
            geo = cell.find("mxGeometry")
            if geo is None or geo.get("relative") != "1":
                errs.append("edge '%s' missing <mxGeometry relative='1'/>" % cid)
        if cell.get("vertex") == "1":
            vertices.append(cell)
    for e in edges:
        for attr in ("source", "target"):
            ref = e.get(attr)
            if ref and ref not in ids:
                errs.append("edge '%s' references missing cell '%s'" % (e.get("id"), ref))
    for v in vertices:
        pid = v.get("parent")
        if pid and pid not in ids:
            errs.append("cell '%s' references missing parent '%s'" % (v.get("id"), pid))
    if not quiet:
        print("XML valid. cells=%d vertices=%d edges=%d"
              % (len(ids), len(vertices), len(edges)))
    return errs


def cmd_validate(args):
    content = open(args.file, "r", encoding="utf-8-sig").read()
    errs = validate_xml(content, quiet=False)
    if errs:
        eprint("validation failed:")
        for e in errs:
            eprint("  - " + e)
        sys.exit(1)
    print("OK: %s" % args.file)


def cmd_inspect(args):
    content = open(args.file, "r", encoding="utf-8-sig").read()
    root = parse_xml(content)
    cells = list(root.iter("mxCell"))
    verts = [c for c in cells if c.get("vertex") == "1"]
    edges = [c for c in cells if c.get("edge") == "1"]
    parents = {}
    for c in verts:
        p = c.get("parent", "?")
        parents.setdefault(p, 0)
        parents[p] += 1
    print("file: %s" % args.file)
    print("cells=%d vertices=%d edges=%d" % (len(cells), len(verts), len(edges)))
    if parents:
        print("nodes per parent: %s" % ", ".join("%s:%d" % (k, v) for k, v in parents.items()))


# ---------------------------------------------------------------------------
# draw.io delivery
# ---------------------------------------------------------------------------


def _require_drawio():
    exe = find_drawio()
    if not exe:
        die("draw.io executable not found. Install draw.io Desktop, or set DRAWIO_PATH.")
    return exe


def cmd_open(args):
    exe = _require_drawio()
    cmd = [exe, os.path.abspath(args.file)]
    if args.layout:
        cmd += ["--layout", args.layout]
    print("opening %s with %s" % (args.file, exe))
    subprocess.Popen(cmd)


def cmd_export(args):
    exe = _require_drawio()
    fmt = args.format.lower()
    out = args.output
    if not out:
        out = os.path.splitext(args.file)[0] + "." + fmt
    cmd = [exe, "--export", "--format", fmt, "--border", str(args.border),
           "--scale", str(args.scale)]
    if args.embed:
        cmd.append("--embed-diagram")
    if args.layout:
        cmd += ["--layout", args.layout]
    if args.transparent:
        cmd.append("--transparent")
    if args.page:
        cmd += ["--page-index", str(args.page)]
    cmd += ["-o", os.path.abspath(out), os.path.abspath(args.file)]
    print("exporting... %s" % " ".join(cmd))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout)
    except subprocess.TimeoutExpired:
        die("export timed out after %ds" % args.timeout)
    if r.returncode != 0:
        die("export failed:\n" + (r.stderr or r.stdout or "unknown error"))
    if os.path.exists(out):
        print("exported %s" % out)
    else:
        die("export finished but output file missing")


def cmd_url(args):
    content = open(args.file, "r", encoding="utf-8-sig").read()
    # extract the inner <mxGraphModel>...</mxGraphModel> for #create=xml
    m = re.search(r"<mxGraphModel.*?</mxGraphModel>", content, re.S)
    xml = m.group(0) if m else content
    url = generate_drawio_url(xml, base_url=args.base_url)
    print(url)
    if args.write:
        with open(args.write, "w", encoding="utf-8") as f:
            f.write(url)
        print("written to %s" % args.write)


def generate_drawio_url(xml, base_url="https://app.diagrams.net/"):
    """Reproduce drawio-mcp's generateDrawioUrl (compressed #create format)."""
    encoded = urllib_quote(xml)
    co = zlib.compressobj(9, zlib.DEFLATED, -15)  # raw deflate (== pako.deflateRaw)
    compressed = co.compress(encoded.encode("ascii")) + co.flush()
    data = base64.b64encode(compressed).decode("ascii")
    create_obj = {"type": "xml", "compressed": True, "data": data}
    fragment = "#create=" + urllib_quote(json.dumps(create_obj, separators=(",", ":")))
    params = "grid=0&pv=0&border=10&edit=_blank"
    return base_url + "?" + params + fragment


def urllib_quote(s):
    """JS encodeURIComponent semantics: leaves A-Z a-z 0-9 - _ . ! ~ * ' ( )."""
    import urllib.parse
    return urllib.parse.quote(s, safe="-_.!~*'()")


def cmd_url_verify(args):
    """Round-trip check: url -> decode -> inflate -> unquote == original xml."""
    from urllib.parse import unquote
    url = open(args.url_file, "r", encoding="utf-8-sig").read().strip()
    frag = url.split("#create=", 1)[1]
    obj = json.loads(unquote(frag))
    if not obj.get("compressed"):
        die("not a compressed #create URL")
    raw = base64.b64decode(obj["data"])
    inflated = zlib.decompress(raw, -15)
    xml = unquote(inflated.decode("ascii"))
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(xml)
    print("decoded ok -> %s (%d bytes)" % (args.output, len(xml)))


# ---------------------------------------------------------------------------
# MCP integration — official @drawio/mcp tool server (browser draw.io)
# ---------------------------------------------------------------------------


def _npm_root_global():
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        return None
    try:
        if os.name == "nt":
            r = subprocess.run(["cmd", "/c", npm, "root", "-g"],
                               capture_output=True, text=True, timeout=30)
        else:
            r = subprocess.run([npm, "root", "-g"],
                               capture_output=True, text=True, timeout=30)
        root = r.stdout.strip()
        return root if root and os.path.isdir(root) else None
    except Exception:
        return None


def find_mcp_server():
    """Locate the official draw.io MCP tool server (@drawio/mcp).

    Resolution order: DRAWIO_MCP_PATH env -> global npm install -> npx.
    Returns the argv list to spawn, or dies with install instructions.
    """
    node = shutil.which("node") or shutil.which("node.exe")
    env_js = os.environ.get("DRAWIO_MCP_PATH")
    if env_js:
        if os.path.isdir(env_js):
            env_js = os.path.join(env_js, "src", "index.js")
        if os.path.exists(env_js) and node:
            return [node, env_js]
        die("DRAWIO_MCP_PATH does not point to a valid @drawio/mcp index.js")
    if node:
        root = _npm_root_global()
        if root:
            js = os.path.join(root, "@drawio", "mcp", "src", "index.js")
            if os.path.exists(js):
                return [node, js]
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if npx:
        if npx.lower().endswith((".cmd", ".bat")):
            return ["cmd", "/c", npx, "-y", "@drawio/mcp"]
        return [npx, "-y", "@drawio/mcp"]
    die("draw.io MCP server (@drawio/mcp) not found.\n"
        "Install it with:  npm install -g @drawio/mcp\n"
        "or set DRAWIO_MCP_PATH to its src/index.js")


class McpClient:
    """Minimal stdio MCP client (JSON-RPC 2.0, newline-delimited)."""

    def __init__(self, argv, env=None):
        self.proc = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1,
            encoding="utf-8", errors="replace", env=env)
        self._id = 0
        import threading
        self._err_drain = threading.Thread(
            target=self._drain, daemon=True).start()

    def _drain(self):
        try:
            for line in self.proc.stderr:
                pass
        except Exception:
            pass

    def _next_id(self):
        self._id += 1
        return self._id

    def send(self, obj):
        self.proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def read(self):
        while True:
            line = self.proc.stdout.readline()
            if not line:
                die("MCP server exited unexpectedly (is @drawio/mcp installed?)")
            try:
                msg = json.loads(line)
            except Exception:
                continue
            if "id" in msg:
                return msg

    def call(self, method, params=None):
        rid = self._next_id()
        self.send({"jsonrpc": "2.0", "id": rid, "method": method,
                   "params": params or {}})
        while True:
            msg = self.read()
            if msg.get("id") == rid:
                return msg

    def close(self):
        try:
            self.proc.terminate()
        except Exception:
            pass

    def initialize(self):
        self.call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "sci-drawio", "version": "1.0"},
        })
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def tools(self):
        msg = self.call("tools/list")
        result = msg.get("result") or {}
        return [t.get("name") for t in result.get("tools", [])]

    def call_tool(self, name, args):
        msg = self.call("tools/call", {"name": name, "arguments": args})
        result = msg.get("result") or {}
        if result.get("isError"):
            texts = [c.get("text", "") for c in result.get("content", [])
                     if c.get("type") == "text"]
            die("MCP tool %s failed: %s" % (name, " ".join(texts)))
        texts = [c.get("text", "") for c in result.get("content", [])
                 if c.get("type") == "text"]
        return "\n".join(texts)


def _graph_model_xml(path):
    content = open(path, "r", encoding="utf-8-sig").read()
    m = re.search(r"<mxGraphModel.*?</mxGraphModel>", content, re.S)
    if not m:
        die("no <mxGraphModel> found in %s" % path)
    return m.group(0)


def cmd_mcp(args):
    client = McpClient(find_mcp_server())
    try:
        client.initialize()
        if args.action == "list":
            names = client.tools()
            print("draw.io MCP tools (%d):" % len(names))
            for n in names:
                print("  - " + n)
            return
        if args.action == "shapes":
            text = client.call_tool("search_shapes", {
                "query": args.query, "limit": args.limit})
            print(text)
            return
        if args.action == "open":
            xml = _graph_model_xml(args.file)
            tool_args = {"content": xml}
            if args.lightbox:
                tool_args["lightbox"] = True
            if args.dark:
                tool_args["dark"] = args.dark
            if args.routing:
                tool_args["routing"] = args.routing
            text = client.call_tool("open_drawio_xml", tool_args)
            m = re.search(r"https?://\S+", text)
            if not m:
                die("MCP open_drawio_xml returned no URL:\n%s" % text[:400])
            url = m.group(0)
            print("MCP open_drawio_xml -> draw.io URL")
            print(url)
            if args.write:
                with open(args.write, "w", encoding="utf-8") as f:
                    f.write(url)
                print("written to %s" % args.write)
            return
        die("unknown mcp action: %s" % args.action)
    finally:
        client.close()


# ---------------------------------------------------------------------------
# live drawing: step-by-step drawing on the visible draw.io canvas.
# Uses the bundled drawio-live MCP server (scripts/live/live-server.mjs),
# MIT (c) icebird1998 scientific-illustrator. Zero npm dependencies.
# ---------------------------------------------------------------------------

LIVE_SHAPE_MAP = {
    "rect": "rectangle", "rounded": "rounded", "ellipse": "ellipse",
    "double_ellipse": "ellipse", "rhombus": "diamond", "cylinder": "cylinder",
    "parallelogram": "parallelogram", "hexagon": "hexagon", "process": "rectangle",
    "document": "document", "cloud": "cloud", "actor": "rectangle",
    "note": "note", "text": "text", "swimlane": "swimlane",
}
LIVE_ARROW_MAP = {
    "activation": "classic", "inhibition": "ERone", "translocation": "open",
    "association": "oval", "production": "classic", "none": "none",
}


def _live_server_argv():
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        die("node.js not found: live drawing requires Node.js 22+")
    candidates = []
    env_js = os.environ.get("SCI_DRAWIO_LIVE_SERVER")
    if env_js:
        candidates.append(env_js)
    candidates.append(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "live", "live-server.mjs"))
    for cand in candidates:
        if cand and os.path.exists(cand):
            return [node, cand]
    die("drawio-live server not found: expected scripts/live/live-server.mjs "
        "inside this skill, or set SCI_DRAWIO_LIVE_SERVER.")


def _live_result(client, name, args=None):
    msg = client.call("tools/call", {"name": name, "arguments": args or {}})
    result = msg.get("result") or {}
    if result.get("isError"):
        texts = [c.get("text", "") for c in result.get("content", [])
                 if c.get("type") == "text"]
        die("live tool %s failed: %s" % (name, " ".join(texts)))
    return result


def _live_text(result):
    return "\n".join(c.get("text", "") for c in result.get("content", [])
                     if c.get("type") == "text")


def _live_save_image(result, path):
    if not path:
        return False
    for c in result.get("content", []):
        if c.get("type") == "image" and c.get("data"):
            try:
                import base64
                with open(path, "wb") as f:
                    f.write(base64.b64decode(c["data"]))
                return True
            except Exception as e:
                print("warning: could not save screenshot: %s" % e)
    return False


def _container_style(c, theme):
    """Live-mode container style, matching build_xml (swimlane with title bar)."""
    return (c.get("style") or
            "swimlane;startSize=%d;fillColor=%s;strokeColor=%s;fontColor=%s;html=1;"
            % (int(c.get("startSize", 30)),
               c.get("fill", theme["container"]["fill"]),
               c.get("stroke", theme["container"]["stroke"]),
               c.get("fontColor", theme["container"]["font"])))


def _spec_ops(spec, themes, node_geo, cont_geo):
    """Convert a spec into drawio-live draw_sequence operations.

    Containers are drawn first as swimlanes (parents); child nodes are then
    inserted with parent=<container-id> using container-relative coordinates,
    so they stay nested and move together with the container. Title, legend
    and notes are drawn as editable text/swimlane cells so live output stays
    self-explanatory like the build path."""
    theme = themes.get(spec.get("theme", "nature"), themes["nature"])
    nodes = spec.get("nodes", [])
    edges = spec.get("edges", [])
    containers = spec.get("containers", [])
    ops = []

    # bounding box over top-level nodes + containers (child coords are local)
    top_gs = [g for g in node_geo.values() if not g.get("container")]
    all_gs = list(top_gs) + list(cont_geo.values())
    gx0 = min([g["x"] for g in all_gs] or [40])
    gy0 = min([g["y"] for g in all_gs] or [40])
    gx1 = max([g["x"] + g["w"] for g in all_gs] or [800])
    gy1 = max([g["y"] + g["h"] for g in all_gs] or [600])

    title = spec.get("title")
    has_title_node = any(n.get("id") == "title" for n in nodes)
    if title and not has_title_node:
        ops.append({
            "type": "shape", "id": "title", "shape": "text", "label": title,
            "x": gx0, "y": max(10, gy0 - 55), "width": max(400, gx1 - gx0), "height": 40,
            "style": "text;html=1;align=center;fontSize=16;fontStyle=1;fontColor=#22303E;",
        })

    for c in sorted(containers, key=lambda k: (k.get("order", 10 ** 9), k["id"])):
        g = cont_geo[c["id"]]
        ops.append({
            "type": "shape",
            "id": c["id"],
            "shape": "swimlane",
            "label": c.get("label", ""),
            "x": g["x"], "y": g["y"], "width": g["w"], "height": g["h"],
            "style": _container_style(c, theme),
        })
    for n in sorted(nodes, key=lambda k: (k.get("order", 10 ** 9), k["id"])):
        g = node_geo[n["id"]]
        op = {
            "type": "shape",
            "id": n["id"],
            "shape": LIVE_SHAPE_MAP.get(n.get("shape", "rounded"), "rounded"),
            "label": n.get("label", ""),
            "x": g["x"], "y": g["y"], "width": g["w"], "height": g["h"],
            "style": node_style(n, theme),
        }
        if g.get("container"):  # child: keep local coords, nest under container
            op["parent"] = g["container"]
        if n.get("fontSize"):
            op["font_size"] = n["fontSize"]
        ops.append(op)
    for e in edges:
        op = {
            "type": "edge",
            "id": e.get("id", "%s-%s" % (e["from"], e["to"])),
            "source": e["from"], "target": e["to"],
            "label": e.get("label", ""),
            "end_arrow": LIVE_ARROW_MAP.get(e.get("arrow", "activation"), "classic"),
            "color": e.get("color", theme["edge"]),
            "width": int(e.get("width", 2)),
        }
        if e.get("dashed"):
            op["dashed"] = True
        if e.get("style") == "curved":
            op["curved"] = True
        ops.append(op)

    # legend: swimlane box + one text row per entry (symbol + label)
    legend = spec.get("legend", [])
    if legend:
        lx = gx1 + 50
        ly = gy0
        ops.append({
            "type": "shape", "id": "legend-box", "shape": "swimlane",
            "label": "图例 Legend",
            "x": lx, "y": ly, "width": 250, "height": 28 + 24 * len(legend),
            "style": "swimlane;startSize=24;fillColor=#FFFFFF;strokeColor=#999999;fontColor=#22303E;html=1;",
        })
        for i, item in enumerate(legend):
            sym = {"activation": "▸", "inhibition": "⊥", "translocation": "▷",
                   "association": "●", "production": "▸", "none": "—"}.get(item.get("arrow", "activation"), "▸")
            ops.append({
                "type": "shape", "id": "lg%d" % i, "shape": "text",
                "label": "%s %s" % (sym, item.get("label", "")),
                "x": lx + 10, "y": ly + 30 + i * 24, "width": 230, "height": 20,
                "style": "text;html=1;align=left;fontSize=11;fontColor=#22303E;",
            })

    # notes: editable text rows under the graph
    for i, nt in enumerate(spec.get("notes", [])):
        ny = gy1 + 40 + i * 30
        ops.append({
            "type": "shape", "id": "note%d" % i, "shape": "text",
            "label": nt.get("text", ""),
            "x": gx0, "y": ny, "width": nt.get("w", max(420, gx1 - gx0)), "height": 26,
            "style": "text;html=1;align=left;fontSize=11;fontColor=#666666;",
        })

    ops.append({"type": "fit"})
    return ops


def cmd_live(args):
    env = dict(os.environ)
    if not env.get("DRAWIO_PATH"):
        exe = find_drawio()
        if exe:
            env["DRAWIO_PATH"] = exe
    client = McpClient(_live_server_argv(), env=env)
    try:
        client.initialize()
        if args.action == "launch":
            tool_args = {"step_delay_ms": args.step_ms,
                         "maximize": not args.no_maximize,
                         "include_screenshot": False}
            if getattr(args, "file", None):
                tool_args["file_path"] = args.file
            print(_live_text(_live_result(client, "drawio_live_launch", tool_args)))
            return
        if args.action == "status":
            print(_live_text(_live_result(client, "drawio_live_status")))
            return
        if args.action == "screenshot":
            result = _live_result(client, "drawio_live_screenshot")
            if _live_save_image(result, args.output):
                print("screenshot saved to %s" % args.output)
            print(_live_text(result))
            return
        if args.action == "save":
            result = _live_result(client, "drawio_live_save_snapshot", {
                "output_path": args.file, "overwrite": True,
                "page_name": args.page_name})
            print(_live_text(result))
            return
        if args.action == "close":
            print(_live_text(_live_result(client, "drawio_live_close_session",
                                          {"confirm": True, "force": True})))
            return
        if args.action == "draw":
            spec = load_json(args.spec)
            themes = load_themes()
            node_geo, cont_geo = build_layout(spec, themes)
            ops = _spec_ops(spec, themes, node_geo, cont_geo)
            print("launching visible draw.io ...")
            launch = _live_result(client, "drawio_live_launch", {
                "step_delay_ms": args.step_ms,
                "maximize": not args.no_maximize,
                "include_screenshot": False})
            print(_live_text(launch)[:300])
            if not args.no_clear:
                cleared = _live_result(client, "drawio_live_clear",
                                       {"confirm": True})
                print("canvas cleared (%s)" % _live_text(cleared)[:80])
            print("drawing %d operations step by step (delay %d ms) ..."
                  % (len(ops), args.step_ms))
            result = _live_result(client, "drawio_live_draw_sequence", {
                "operations": ops,
                "step_delay_ms": args.step_ms,
                "screenshot_after": bool(args.screenshot)})
            print(_live_text(result)[:600])
            if args.screenshot:
                if _live_save_image(result, args.screenshot):
                    print("screenshot saved to %s" % args.screenshot)
            if args.save:
                result = _live_result(client, "drawio_live_save_snapshot", {
                    "output_path": args.save, "overwrite": True,
                    "page_name": spec.get("name", "sci-figure")})
                print(_live_text(result))
            return
        die("unknown live action: %s" % args.action)
    finally:
        client.close()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(
        prog="sci_drawio.py",
        description="sci-drawio: deterministic scientific figure builder for draw.io")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("build", help="JSON spec -> .drawio file")
    p.add_argument("spec")
    p.add_argument("-o", "--output")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("validate", help="check .drawio XML structure")
    p.add_argument("file")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("inspect", help="summarize .drawio file")
    p.add_argument("file")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("open", help="open .drawio in draw.io desktop")
    p.add_argument("file")
    p.add_argument("--layout", help="preset: verticalFlow/horizontalFlow/verticalTree/radialTree/organic")
    p.set_defaults(func=cmd_open)

    p = sub.add_parser("export", help="export .drawio to png/svg/pdf")
    p.add_argument("file")
    p.add_argument("-f", "--format", default="png", choices=["png", "svg", "pdf", "jpg", "html", "xml"])
    p.add_argument("-o", "--output")
    p.add_argument("--border", type=int, default=16)
    p.add_argument("--scale", type=float, default=1.5)
    p.add_argument("--embed", action="store_true", help="embed diagram XML into exported file")
    p.add_argument("--transparent", action="store_true")
    p.add_argument("--page", type=int, help="page index (1-based)")
    p.add_argument("--layout", help="preset: verticalFlow/horizontalFlow/verticalTree/radialTree/organic")
    p.add_argument("--timeout", type=int, default=180)
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("url", help="print browser URL (drawio-mcp compatible)")
    p.add_argument("file")
    p.add_argument("--base-url", default="https://app.diagrams.net/")
    p.add_argument("--write")
    p.set_defaults(func=cmd_url)

    p = sub.add_parser("url-verify", help="decode a #create URL back to XML (test)")
    p.add_argument("url_file")
    p.add_argument("-o", "--output", default="decoded.xml")
    p.set_defaults(func=cmd_url_verify)

    p = sub.add_parser("mcp", help="drive the official @drawio/mcp tool server")
    subp = p.add_subparsers(dest="action", required=True)
    q = subp.add_parser("list", help="list available MCP tools")
    q.set_defaults(func=cmd_mcp)
    q = subp.add_parser("open", help="open a .drawio in draw.io via MCP (server opens your browser)")
    q.add_argument("file")
    q.add_argument("--lightbox", action="store_true", help="read-only view")
    q.add_argument("--dark", choices=["auto", "true", "false"], help="dark mode")
    q.add_argument("--routing", choices=["libavoid"], help="reroute connectors around shapes")
    q.add_argument("--write", help="also save the URL to a file")
    q.set_defaults(func=cmd_mcp)
    q = subp.add_parser("shapes", help="search draw.io shape library via MCP")
    q.add_argument("query")
    q.add_argument("--limit", type=int, default=10)
    q.set_defaults(func=cmd_mcp)

    p = sub.add_parser("live", help="step-by-step drawing on the visible draw.io canvas (drawio-live MCP)")
    subp = p.add_subparsers(dest="action", required=True)
    q = subp.add_parser("launch", help="launch/connect a visible draw.io editor")
    q.add_argument("file", nargs="?", help="optional .drawio file to open visibly")
    q.add_argument("--step-ms", type=int, default=400)
    q.add_argument("--no-maximize", action="store_true")
    q.set_defaults(func=cmd_live)
    q = subp.add_parser("draw", help="draw a JSON spec step by step on the visible canvas")
    q.add_argument("spec")
    q.add_argument("--step-ms", type=int, default=400)
    q.add_argument("--no-maximize", action="store_true")
    q.add_argument("--no-clear", action="store_true", help="append to the existing canvas instead of clearing it first")
    q.add_argument("--save", help="save snapshot .drawio after drawing")
    q.add_argument("--screenshot", help="save PNG screenshot after drawing")
    q.set_defaults(func=cmd_live)
    q = subp.add_parser("status", help="live session status")
    q.set_defaults(func=cmd_live)
    q = subp.add_parser("screenshot", help="capture the visible canvas")
    q.add_argument("-o", "--output", default="live-shot.png")
    q.set_defaults(func=cmd_live)
    q = subp.add_parser("save", help="save the visible canvas to .drawio")
    q.add_argument("file")
    q.add_argument("--page-name", default="Live drawing")
    q.set_defaults(func=cmd_live)
    q = subp.add_parser("close", help="close the MCP-launched draw.io window")
    q.set_defaults(func=cmd_live)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
