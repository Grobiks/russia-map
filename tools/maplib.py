# -*- coding: utf-8 -*-
"""Небольшой картографический движок: проекция, геометрия, сцена, два рендера (SVG и PNG).

Одна и та же геометрия идёт и в SVG, и в растр, поэтому контуры на карте
и в шаблонах совпадают до последней вершины.
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "lib"))

import shapely
from shapely.geometry import (LineString, MultiLineString, MultiPolygon, Point,
                              Polygon, box, shape)
from shapely.ops import unary_union

# ----------------------------------------------------------------------------
# палитра
# ----------------------------------------------------------------------------
BG = "#F5F0EB"
INK = "#4A4A4A"
HAIR = "#BFB6A9"
BLUE = "#3B8ED7"
SEA = "#6C8798"
PAPER_WHITE = "#FFFFFF"


# ----------------------------------------------------------------------------
# проекция (коническая равновеликая Альберса)
# ----------------------------------------------------------------------------
class Albers:
    def __init__(self, lat1=50.0, lat2=70.0, lon0=100.0, lat0=55.0):
        self.lon0 = math.radians(lon0)
        p1, p2, p0 = map(math.radians, (lat1, lat2, lat0))
        self.n = 0.5 * (math.sin(p1) + math.sin(p2))
        self.C = math.cos(p1) ** 2 + 2 * self.n * math.sin(p1)
        self.rho0 = math.sqrt(self.C - 2 * self.n * math.sin(p0)) / self.n
        self.n = self.n

    def raw(self, lon, lat):
        lam = math.radians(lon) - self.lon0
        phi = math.radians(lat)
        rho = math.sqrt(max(self.C - 2 * self.n * math.sin(phi), 0.0)) / self.n
        theta = self.n * lam
        return rho * math.sin(theta), self.rho0 - rho * math.cos(theta)

    def fit(self, geoms, rect, pad=0.0):
        """Подбирает масштаб и сдвиг так, чтобы геометрии влезли в rect (y вниз)."""
        xs, ys = [], []
        for g in geoms:
            for x, y in _all_coords(g):
                X, Y = self.raw(x, y)
                xs.append(X)
                ys.append(Y)
        self.bx0, self.bx1 = min(xs), max(xs)
        self.by0, self.by1 = min(ys), max(ys)
        x0, y0, x1, y1 = rect
        w, h = x1 - x0 - 2 * pad, y1 - y0 - 2 * pad
        self.s = min(w / (self.bx1 - self.bx0), h / (self.by1 - self.by0))
        self.ox = x0 + pad + (w - (self.bx1 - self.bx0) * self.s) / 2 - self.bx0 * self.s
        self.oy = y0 + pad + (h - (self.by1 - self.by0) * self.s) / 2 + self.by1 * self.s
        return self

    def __call__(self, lon, lat):
        X, Y = self.raw(lon, lat)
        return self.ox + X * self.s, self.oy - Y * self.s

    def project(self, geom):
        return _map_coords(geom, self)


def _all_coords(geom):
    if isinstance(geom, Polygon):
        yield from geom.exterior.coords
        for r in geom.interiors:
            yield from r.coords
    elif isinstance(geom, (MultiPolygon, MultiLineString)):
        for g in geom.geoms:
            yield from _all_coords(g)
    elif geom.geom_type == "GeometryCollection":
        for g in geom.geoms:
            yield from _all_coords(g)
    else:
        yield from geom.coords


def _map_coords(geom, fn):
    def t(x, y, z=None):
        X, Y = fn(x, y)
        return (X, Y)
    return shapely.ops.transform(t, geom)


# ----------------------------------------------------------------------------
# геоданные
# ----------------------------------------------------------------------------
def norm_lon(x):
    return x + 360.0 if x < 0 else x


def load_adm1(path):
    """Возвращает {shapeISO: (shapely-геометрия, английское имя)} в долготе 19..191."""
    data = json.load(open(path, encoding="utf-8"))
    out = {}
    for f in data["features"]:
        p = f["properties"]
        g = shape(f["geometry"])
        g = _map_coords(g, lambda x, y: (norm_lon(x), y))
        # куски, разрезанные по 180-му меридиану, сшиваем обратно,
        # иначе на карте остаётся прямая «линия разреза» через Чукотку
        if g.geom_type == "MultiPolygon":
            g = unary_union(list(g.geoms))
        out[p["shapeISO"]] = (g, p["shapeName"])
    return out


def merge_geoms(geoms):
    return unary_union([g for g in geoms if g is not None and not g.is_empty])


def clean(geom, min_area=30.0, tol=0.45, grid=0.5):
    """Упрощение + отбрасывание микроостровов. Одинаково для карты и шаблонов."""
    g = shapely.set_precision(geom, grid)
    g = g.simplify(tol, preserve_topology=True) if tol else g
    polys = []
    for p in getattr(g, "geoms", [g]):
        if p.is_empty or p.area < min_area:
            continue
        polys.append(p)
    return shapely.geometry.MultiPolygon(polys) if polys else g


def rings_of(geom):
    """[[(x,y), ...], ...] — внешние кольца и дырки (дырки отдельным списком)."""
    out = []
    for p in getattr(geom, "geoms", [geom]):
        if p.is_empty:
            continue
        ext = [(c[0], c[1]) for c in p.exterior.coords]
        holes = [[(c[0], c[1]) for c in r.coords] for r in p.interiors]
        out.append((ext, holes))
    return out


# ----------------------------------------------------------------------------
# сглаживание: Catmull-Rom -> кубические Безье
# ----------------------------------------------------------------------------
def catmull(pts, closed=True, tension=0.85):
    n = len(pts)
    if n < 4:
        return []
    segs = []
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        if closed:
            p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        else:
            p0 = pts[max(i - 1, 0)]
            p1 = pts[i]
            p2 = pts[i + 1]
            p3 = pts[min(i + 2, n - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) * tension / 6.0, p1[1] + (p2[1] - p0[1]) * tension / 6.0)
        c2 = (p2[0] - (p3[0] - p1[0]) * tension / 6.0, p2[1] - (p3[1] - p1[1]) * tension / 6.0)
        segs.append((p1, c1, c2, p2))
    return segs


def _fmt(v, prec=1):
    s = f"{v:.{prec}f}"
    return s[:-2] if s.endswith(".0") else s


def segs_to_d(segs, closed=True, prec=1):
    if not segs:
        return ""
    d = [f"M{_fmt(segs[0][0][0], prec)},{_fmt(segs[0][0][1], prec)}"]
    for _p1, c1, c2, p2 in segs:
        d.append(f"C{_fmt(c1[0], prec)},{_fmt(c1[1], prec)} {_fmt(c2[0], prec)},{_fmt(c2[1], prec)} "
                 f"{_fmt(p2[0], prec)},{_fmt(p2[1], prec)}")
    if closed:
        d.append("Z")
    return "".join(d)


def sample_segs(segs, closed=True, step=2.5):
    """Дискретизация тех же безье для растра."""
    pts = [segs[0][0]]
    for p1, c1, c2, p2 in segs:
        approx = math.dist(p1, c1) + math.dist(c1, c2) + math.dist(c2, p2)
        n = max(2, min(24, int(approx / step) + 1))
        for i in range(1, n + 1):
            t = i / n
            mt = 1 - t
            x = mt ** 3 * p1[0] + 3 * mt * mt * t * c1[0] + 3 * mt * t * t * c2[0] + t ** 3 * p2[0]
            y = mt ** 3 * p1[1] + 3 * mt * mt * t * c1[1] + 3 * mt * t * t * c2[1] + t ** 3 * p2[1]
            pts.append((x, y))
    return pts


def chaikin(pts, closed=True, iters=1):
    """Срезание углов: убирает мелкую «пилу» береговой линии."""
    for _ in range(iters):
        n = len(pts)
        out = []
        last = n if closed else n - 1
        for i in range(last):
            p = pts[i]
            q = pts[(i + 1) % n]
            out.append((0.75 * p[0] + 0.25 * q[0], 0.75 * p[1] + 0.25 * q[1]))
            out.append((0.25 * p[0] + 0.75 * q[0], 0.25 * p[1] + 0.75 * q[1]))
        if not closed:
            out.insert(0, pts[0])
            out.append(pts[-1])
        pts = out
    return pts


def smooth_rings(geom, tension=0.85, closed=True, prec=1):
    """Геометрия -> список {'d': путь, 'pts': полилиния, 'hole': bool}."""
    out = []
    for ext, holes in rings_of(geom):
        for ring, is_hole in [(ext, False)] + [(h, True) for h in holes]:
            if len(ring) < 5:
                continue
            segs = catmull(chaikin(ring, closed, 1), closed=closed, tension=tension)
            if not segs:
                continue
            out.append({"d": segs_to_d(segs, closed, prec), "pts": sample_segs(segs, closed), "hole": is_hole})
    return out


# ----------------------------------------------------------------------------
# сцена
# ----------------------------------------------------------------------------
class Scene:
    def __init__(self, w, h, bg=BG):
        self.w, self.h, self.bg = w, h, bg
        self.ops = []

    def poly(self, geom_or_rings, fill=None, stroke=None, width=1.0, tension=0.85, smooth=True, opacity=None):
        if hasattr(geom_or_rings, "geom_type"):
            if smooth:
                rings = smooth_rings(geom_or_rings, tension)
            else:
                rings = []
                for ext, holes in rings_of(geom_or_rings):
                    rings.append({"d": None, "pts": ext, "hole": False})
                    for h in holes:
                        rings.append({"d": None, "pts": h, "hole": True})
        else:
            rings = geom_or_rings
        self.ops.append({"t": "poly", "rings": rings, "fill": fill, "stroke": stroke,
                         "w": width, "opacity": opacity})

    def line(self, pts, stroke=INK, width=1.0, dash=None, cap="round", smooth=False, tension=0.85):
        if smooth and len(pts) > 4:
            segs = catmull(pts, closed=False, tension=tension)
            self.ops.append({"t": "line", "segs": segs, "pts": None, "stroke": stroke,
                             "w": width, "dash": dash, "cap": cap})
        else:
            self.ops.append({"t": "line", "segs": None, "pts": pts, "stroke": stroke,
                             "w": width, "dash": dash, "cap": cap})

    def rect(self, box_, fill=None, stroke=None, width=1.0):
        x0, y0, x1, y1 = box_
        self.ops.append({"t": "rect", "box": box_, "fill": fill, "stroke": stroke, "w": width})

    def text(self, x, y, s, size=20, color=INK, weight="normal", anchor="middle",
             spacing=0.0, italic=False, family="'PT Sans','Segoe UI',Arial,sans-serif",
             rotate=None, halo=None, lh=None):
        self.ops.append({"t": "text", "x": x, "y": y, "s": s, "size": size, "color": color,
                         "weight": weight, "anchor": anchor, "spacing": spacing,
                         "italic": italic, "family": family, "rotate": rotate,
                         "halo": halo, "lh": lh if lh is not None else size * 1.18})


# ----------------------------------------------------------------------------
# SVG-рендер
# ----------------------------------------------------------------------------
def _esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def to_svg(scene, width_cm=None, extra_header=""):
    w, h = scene.w, scene.h
    size = f'width="{width_cm}cm" height="{width_cm * h / w:.2f}cm"' if width_cm else f'width="{w}" height="{h}"'
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" {size} viewBox="0 0 {w} {h}" '
        f'shape-rendering="geometricPrecision" text-rendering="geometricPrecision">',
        extra_header,
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{scene.bg}"/>',
    ]
    for op in scene.ops:
        t = op["t"]
        if t == "poly":
            d = "".join(r["d"] for r in op["rings"] if r["d"])
            if not d:
                continue
            attrs = [f'd="{d}"', f'fill="{op["fill"] or "none"}"']
            if op["stroke"]:
                attrs += [f'stroke="{op["stroke"]}"', f'stroke-width="{op["w"]}"',
                          'stroke-linejoin="round"', 'stroke-linecap="round"', 'fill-rule="evenodd"']
            if op["opacity"]:
                attrs.append(f'opacity="{op["opacity"]}"')
            out.append(f'<path {" ".join(attrs)}/>')
        elif t == "line":
            if op["segs"]:
                d = segs_to_d(op["segs"], closed=False)
            else:
                pts = op["pts"]
                d = "M" + "L".join(f"{_fmt(x)},{_fmt(y)}" for x, y in pts)
            attrs = [f'd="{d}"', f'stroke="{op["stroke"]}"', f'stroke-width="{op["w"]}"',
                     f'stroke-linecap="{op["cap"]}"', 'stroke-linejoin="round"', 'fill="none"']
            if op["dash"]:
                attrs.append(f'stroke-dasharray="{op["dash"]}"')
            out.append(f'<path {" ".join(attrs)}/>')
        elif t == "rect":
            x0, y0, x1, y1 = op["box"]
            out.append(f'<rect x="{_fmt(x0)}" y="{_fmt(y0)}" width="{_fmt(x1 - x0)}" '
                       f'height="{_fmt(y1 - y0)}" fill="{op["fill"] or "none"}" '
                       + (f'stroke="{op["stroke"]}" stroke-width="{op["w"]}"' if op["stroke"] else "") + "/>")
        elif t == "text":
            lines = op["s"].split("\n")
            style = [f'font-family="{op["family"]}"', f'font-size="{op["size"]}"',
                     f'fill="{op["color"]}"', f'text-anchor="{op["anchor"]}"']
            if op["weight"] != "normal":
                style.append(f'font-weight="{op["weight"]}"')
            if op["italic"]:
                style.append('font-style="italic"')
            if op["spacing"]:
                style.append(f'letter-spacing="{op["spacing"]}"')
            if op["halo"]:
                style += [f'stroke="{op["halo"]}"', f'stroke-width="{max(2.0, op["size"] * 0.19):.1f}"',
                          'stroke-linejoin="round"', 'paint-order="stroke fill"']
            tr = f' transform="rotate({op["rotate"]} {_fmt(op["x"])} {_fmt(op["y"])})"' if op["rotate"] else ""
            if len(lines) == 1:
                out.append(f'<text x="{_fmt(op["x"])}" y="{_fmt(op["y"])}" {" ".join(style)}{tr}>{_esc(lines[0])}</text>')
            else:
                spans = []
                for i, ln in enumerate(lines):
                    dy = 0 if i == 0 else op["lh"]
                    spans.append(f'<tspan x="{_fmt(op["x"])}" dy="{_fmt(dy)}">{_esc(ln)}</tspan>')
                out.append(f'<text x="{_fmt(op["x"])}" y="{_fmt(op["y"])}" {" ".join(style)}{tr}>'
                           + "".join(spans) + "</text>")
    out.append("</svg>")
    return "\n".join(out)


# ----------------------------------------------------------------------------
# растр (PIL), суперсэмплинг
# ----------------------------------------------------------------------------
_FONTS = {}
FONT_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


def _font(size, weight="normal", italic=False):
    key = (round(size, 2), weight, italic)
    if key in _FONTS:
        return _FONTS[key]
    from PIL import ImageFont
    if weight in ("bold", "600", "700"):
        names = ["segoeuib.ttf", "arialbd.ttf"]
    elif italic:
        names = ["segoeuii.ttf", "ariali.ttf"]
    else:
        names = ["segoeui.ttf", "arial.ttf"]
    for n in names:
        p = os.path.join(FONT_DIR, n)
        if os.path.exists(p):
            f = ImageFont.truetype(p, max(1, int(round(size))))
            _FONTS[key] = f
            return f
    f = ImageFont.load_default()
    _FONTS[key] = f
    return f


def _text_width(font, s, spacing):
    if not s:
        return 0.0
    if spacing:
        return sum(font.getlength(ch) for ch in s) + spacing * (len(s) - 1)
    return font.getlength(s)


def to_png(scene, path, ss=2, dpi=None, keep=False):
    from PIL import Image, ImageDraw
    W, H = int(scene.w * ss), int(scene.h * ss)
    base = (0, 0, 0, 0) if scene.bg == "none" else scene.bg
    img = Image.new("RGBA", (W, H), base)
    dr = ImageDraw.Draw(img)

    def col(c, a=255):
        return c

    for op in scene.ops:
        t = op["t"]
        if t == "poly":
            rings = op["rings"]
            if op["fill"]:
                for r in rings:
                    if r["hole"]:
                        continue
                    pts = [(x * ss, y * ss) for x, y in r["pts"]]
                    if len(pts) > 2:
                        dr.polygon(pts, fill=op["fill"])
            if op["stroke"]:
                for r in rings:
                    pts = [(x * ss, y * ss) for x, y in r["pts"]]
                    if len(pts) > 2:
                        dr.line(pts + [pts[0]], fill=op["stroke"], width=max(1, round(op["w"] * ss)),
                                joint="curve")
        elif t == "line":
            pts = [(x * ss, y * ss) for x, y in (op["pts"] or sample_segs(op["segs"], closed=False))]
            if len(pts) > 1:
                dr.line(pts, fill=op["stroke"], width=max(1, round(op["w"] * ss)), joint="curve")
        elif t == "rect":
            x0, y0, x1, y1 = op["box"]
            b = [x0 * ss, y0 * ss, x1 * ss, y1 * ss]
            if op["fill"]:
                dr.rectangle(b, fill=op["fill"])
            if op["stroke"]:
                dr.rectangle(b, outline=op["stroke"], width=max(1, round(op["w"] * ss)))
        elif t == "text":
            font = _font(op["size"] * ss, op["weight"], op["italic"])
            halo = max(1, round(op["size"] * 0.19 * ss)) if op["halo"] else 0
            for li, line in enumerate(op["s"].split("\n")):
                tw = _text_width(font, line, op["spacing"] * ss)
                x, y = op["x"] * ss, op["y"] * ss + li * op["lh"] * ss
                if op["anchor"] == "middle":
                    x -= tw / 2
                elif op["anchor"] == "end":
                    x -= tw
                # PIL рисует от верхней кромки, SVG — по базовой линии
                y = y - op["size"] * ss * 0.78
                if op["spacing"]:
                    for ch in line:
                        dr.text((x, y), ch, font=font, fill=op["color"],
                                stroke_width=halo, stroke_fill=op["halo"] or None)
                        x += font.getlength(ch) + op["spacing"] * ss
                else:
                    dr.text((x, y), line, font=font, fill=op["color"],
                            stroke_width=halo, stroke_fill=op["halo"] or None)
    if ss != 1 and not keep:
        img = img.resize((int(scene.w), int(scene.h)), Image.LANCZOS)
    if dpi:
        img.save(path, dpi=(dpi, dpi))
    else:
        img.save(path)
    return path


