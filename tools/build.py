# -*- coding: utf-8 -*-
"""Сборка карты России и шаблонов регионов из одних и тех же контуров."""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import maplib as M
from maplib import BG, BLUE, HAIR, INK, SEA, Scene, Albers
from shapely.geometry import LineString, Point, Polygon, MultiPolygon, box
from shapely.ops import unary_union
import shapely

ROOT = M.ROOT
DATA = os.path.join(ROOT, "data")
OUT = ROOT
TPL = os.path.join(ROOT, "shablony")

# 1920 px исходника = 58 см на печати (лист А2). Все шаблоны — в том же масштабе,
# поэтому распечатанные на 100% детали складываются в целую карту.
MAP_W, MAP_H = 1920, 1080
CM_PER_PX = 58.0 / MAP_W
LAND = "#FFFDFA"

# ---------------------------------------------------------------------------
# 8 крупных регионов (федеральные округа; Крым и новые регионы в наборе данных
# geoBoundaries отсутствуют, поэтому их здесь нет)
# ---------------------------------------------------------------------------
DISTRICTS = [
    ("CENTR", "ЦЕНТР", "Центральный", "Центральный федеральный округ",
     "RU-BEL RU-BRY RU-VLA RU-VOR RU-IVA RU-KLU RU-KOS RU-KRS RU-LIP RU-MOS RU-MOW "
     "RU-ORL RU-RYA RU-SMO RU-TAM RU-TVE RU-TUL RU-YAR",
     (38.6, 54.9), "01_centralnyy"),
    ("SEVZAP", "СЕВЕРО-ЗАПАД", "Северо-Западный", "Северо-Западный федеральный округ",
     "RU-ARK RU-NEN RU-VLG RU-KGD RU-KR RU-KO RU-LEN RU-MUR RU-NGR RU-PSK RU-SPE",
     (45.5, 64.4), "02_severo-zapad"),
    ("YUG", "ЮГ", "Южный", "Южный федеральный округ",
     "RU-AD RU-AST RU-VGG RU-KL RU-KDA RU-ROS",
     (40.6, 47.3), "03_yug"),
    ("KAVKAZ", "СЕВЕРНЫЙ\nКАВКАЗ", "Северо-Кавказский", "Северо-Кавказский федеральный округ",
     "RU-DA RU-IN RU-KB RU-KC RU-SE RU-STA RU-CE",
     (43.6, 43.6), "04_severnyy-kavkaz"),
    ("POVOLZHE", "ПОВОЛЖЬЕ", "Приволжский", "Приволжский федеральный округ",
     "RU-BA RU-KIR RU-ME RU-MO RU-NIZ RU-ORE RU-PNZ RU-PER RU-SAM RU-SAR RU-TA RU-UD RU-ULY RU-CU",
     (49.4, 53.9), "05_povolzhe"),
    ("URAL", "УРАЛ", "Уральский", "Уральский федеральный округ",
     "RU-KGN RU-SVE RU-TYU RU-KHM RU-YAN RU-CHE",
     (63.0, 59.6), "06_ural"),
    ("SIBIR", "СИБИРЬ", "Сибирский", "Сибирский федеральный округ",
     "RU-AL RU-ALT RU-BU RU-ZAB RU-IRK RU-KEM RU-KYA RU-NVS RU-OMS RU-TOM RU-TY RU-KK",
     (95.0, 61.5), "07_sibir"),
    ("DVOSTOK", "ДАЛЬНИЙ ВОСТОК", "Дальневосточный", "Дальневосточный федеральный округ",
     "RU-AMU RU-CHU RU-YEV RU-KAM RU-KHA RU-MAG RU-PRI RU-SA RU-SAK",
     (133.0, 60.3), "08_dalniy-vostok"),
]

SEAS = [
    ("Баренцево\nморе", 35.0, 74.9),
    ("Карское\nморе", 74.5, 76.4),
    ("Море\nЛаптевых", 113.0, 78.6),
    ("Восточно-Сибирское\nморе", 159.0, 74.3),
    ("Чукотское\nморе", 185.0, 70.8),
    ("Берингово\nморе", 175.0, 59.4),
    ("Охотское\nморе", 147.5, 55.2),
    ("Японское\nморе", 133.0, 43.2),
    ("Чёрное\nморе", 33.6, 43.0),
]

RIVERS = [
    ("Волга", "Volga", (32.47, 57.25), (48.05, 45.70)),
    ("Обь", "Ob", (85.00, 52.43), (68.60, 66.70)),
    ("Енисей", "Yenisey", (92.00, 51.70), (82.60, 71.10)),
    ("Лена", "Lena", (107.60, 54.00), (126.60, 73.50)),
    ("Амур", "Amur", (121.00, 53.30), (140.70, 53.14)),
]

LAKE_NAMES = {"Lake Baikal": "Байкал", "Lake Ladoga": "Ладожское", "Lake Onega": "Онежское"}

# русские названия субъектов
RU_SUBJECTS = {
    "RU-AD": "Адыгея", "RU-AL": "Республика Алтай", "RU-ALT": "Алтайский край",
    "RU-AMU": "Амурская область", "RU-ARK": "Архангельская область",
    "RU-AST": "Астраханская область", "RU-BA": "Башкортостан",
    "RU-BEL": "Белгородская область", "RU-BRY": "Брянская область", "RU-BU": "Бурятия",
    "RU-CE": "Чечня", "RU-CHE": "Челябинская область",
    "RU-CHU": "Чукотский автономный округ", "RU-CU": "Чувашия", "RU-DA": "Дагестан",
    "RU-IN": "Ингушетия", "RU-IRK": "Иркутская область", "RU-IVA": "Ивановская область",
    "RU-KAM": "Камчатский край", "RU-KB": "Кабардино-Балкария",
    "RU-KC": "Карачаево-Черкесия", "RU-KDA": "Краснодарский край",
    "RU-KEM": "Кемеровская область", "RU-KGD": "Калининградская область",
    "RU-KGN": "Курганская область", "RU-KHA": "Хабаровский край",
    "RU-KHM": "Ханты-Мансийский АО", "RU-KIR": "Кировская область", "RU-KK": "Хакасия",
    "RU-KL": "Калмыкия", "RU-KLU": "Калужская область", "RU-KO": "Республика Коми",
    "RU-KOS": "Костромская область", "RU-KR": "Республика Карелия",
    "RU-KRS": "Курская область", "RU-KYA": "Красноярский край",
    "RU-LEN": "Ленинградская область", "RU-LIP": "Липецкая область",
    "RU-MAG": "Магаданская область", "RU-ME": "Марий Эл", "RU-MO": "Мордовия",
    "RU-MOS": "Московская область", "RU-MOW": "Москва", "RU-MUR": "Мурманская область",
    "RU-NEN": "Ненецкий АО", "RU-NGR": "Новгородская область",
    "RU-NIZ": "Нижегородская область", "RU-NVS": "Новосибирская область",
    "RU-OMS": "Омская область", "RU-ORE": "Оренбургская область",
    "RU-ORL": "Орловская область", "RU-PER": "Пермский край",
    "RU-PNZ": "Пензенская область", "RU-PRI": "Приморский край",
    "RU-PSK": "Псковская область", "RU-ROS": "Ростовская область",
    "RU-RYA": "Рязанская область", "RU-SA": "Саха (Якутия)",
    "RU-SAK": "Сахалинская область", "RU-SAM": "Самарская область",
    "RU-SAR": "Саратовская область", "RU-SE": "Северная Осетия",
    "RU-SMO": "Смоленская область", "RU-SPE": "Санкт-Петербург",
    "RU-STA": "Ставропольский край", "RU-SVE": "Свердловская область",
    "RU-TA": "Татарстан", "RU-TAM": "Тамбовская область", "RU-TOM": "Томская область",
    "RU-TUL": "Тульская область", "RU-TVE": "Тверская область", "RU-TY": "Тыва",
    "RU-TYU": "Тюменская область", "RU-UD": "Удмуртия",
    "RU-ULY": "Ульяновская область", "RU-VGG": "Волгоградская область",
    "RU-VLA": "Владимирская область", "RU-VLG": "Вологодская область",
    "RU-VOR": "Воронежская область", "RU-YAN": "Ямало-Ненецкий АО",
    "RU-YAR": "Ярославская область", "RU-YEV": "Еврейская АО",
    "RU-ZAB": "Забайкальский край",
}


# ---------------------------------------------------------------------------
def load():
    adm = M.load_adm1(os.path.join(DATA, "rus_adm1.geojson"))
    dist_geoms = {}
    for code, short, ru, full, isos, lab, fname in DISTRICTS:
        parts = [adm[i][0] for i in isos.split() if i in adm]
        missing = [i for i in isos.split() if i not in adm]
        if missing:
            print("  !! нет в данных:", missing)
        dist_geoms[code] = M.merge_geoms(parts)
    country = M.merge_geoms(list(dist_geoms.values()))
    return adm, dist_geoms, country


def load_rivers():
    import json
    data = json.load(open(os.path.join(DATA, "ne_rivers.geojson"), encoding="utf-8"))
    by_name = {}
    for f in data["features"]:
        n = f["properties"].get("name")
        if not n:
            continue
        g = f["geometry"]
        lines = [g["coordinates"]] if g["type"] == "LineString" else list(g["coordinates"])
        for ls in lines:
            if len(ls) < 2:
                continue
            pts = [(M.norm_lon(x), y) for x, y in ls]
            by_name.setdefault(n, []).append(pts)
    return by_name


def load_lakes():
    import json
    out = {}
    data = json.load(open(os.path.join(DATA, "ne_lakes.geojson"), encoding="utf-8"))
    for f in data["features"]:
        n = f["properties"].get("name")
        if n in LAKE_NAMES:
            g = M.shape(f["geometry"])
            out[n] = M._map_coords(g, lambda x, y: (M.norm_lon(x), y))
    # Каспий в наборе озёр отсутствует — берём его контур из слоя океана
    oc = json.load(open(os.path.join(DATA, "ne_ocean50.geojson"), encoding="utf-8"))
    g = M.shape(oc["features"][0]["geometry"])
    for p in g.geoms:
        b = p.bounds
        if b[0] < 47 < b[2] and b[1] < 41 < b[3]:
            out["Caspian"] = M._map_coords(p, lambda x, y: (M.norm_lon(x), y))
            break
    return out


# ---------------------------------------------------------------------------
# река: склейка кусков в один путь по графу
# ---------------------------------------------------------------------------
def river_path(segments, dst_hint, tol=0.3):
    """Склеивает куски реки в один путь от истока к устью.

    Устье задаётся подсказкой, но привязываемся не к ближайшей точке данных
    (это может быть кусок дельты), а к самому длинному связному руслу.
    Исток — самая дальняя точка этого русла.
    """
    import heapq

    ends = [(p[0], p[1]) for s in segments for p in (s[0], s[-1])]
    cluster = []
    for p in ends:
        if not any(math.dist(p, c) < tol for c in cluster):
            cluster.append(p)

    def nid(p):
        return min(range(len(cluster)), key=lambda i: math.dist(p, cluster[i]))

    adj = {}
    for s in segments:
        a, b = nid(s[0]), nid(s[-1])
        if a == b:
            continue
        L = LineString(s).length
        adj.setdefault(a, []).append((b, L, s))
        adj.setdefault(b, []).append((a, L, list(reversed(s))))

    # связные компоненты и их суммарная длина
    comp = {}
    comp_len = {}
    cid = 0
    for start in adj:
        if start in comp:
            continue
        stack = [start]
        comp[start] = cid
        total = 0.0
        while stack:
            u = stack.pop()
            for v, L, _s in adj[u]:
                total += L / 2.0
                if v not in comp:
                    comp[v] = cid
                    stack.append(v)
        comp_len[cid] = total
        cid += 1
    if not comp_len:
        return None
    best = max(comp_len, key=lambda c: comp_len[c])
    inside = [n for n in adj if comp[n] == best]
    if len(inside) < 2:
        return None
    d_node = min(inside, key=lambda n: math.dist(cluster[n], dst_hint))

    def dijkstra(start, stop=None):
        dist = {start: 0.0}
        prev = {}
        pq = [(0.0, start)]
        while pq:
            d, u = heapq.heappop(pq)
            if stop is not None and u == stop:
                break
            if d > dist.get(u, 1e18):
                continue
            for v, L, seg in adj.get(u, []):
                nd = d + L
                if nd < dist.get(v, 1e18):
                    dist[v] = nd
                    prev[v] = (u, seg)
                    heapq.heappush(pq, (nd, v))
        return dist, prev

    dist0, _ = dijkstra(d_node)
    reach = {k: v for k, v in dist0.items() if k != d_node and v > 0}
    if not reach:
        return None
    s_node = max(reach, key=lambda k: reach[k])

    _dist, prev = dijkstra(s_node, d_node)
    if d_node not in prev:
        return None
    chain = []
    cur = d_node
    while cur in prev:
        u, seg = prev[cur]
        chain.append(seg)
        cur = u
    chain.reverse()
    path = []
    for seg in chain:
        if path and math.dist(path[-1], seg[0]) < 1e-6:
            path.extend(seg[1:])
        else:
            path.extend(seg)
    return path


def densify(pts, step):
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        d = math.dist(a, b)
        n = max(1, int(d / step))
        for i in range(1, n + 1):
            t = i / n
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def ribbon(pts, w0=1.0, w1=4.8, tension=0.7):
    """Суждающаяся к истоку лента: набор буферов с меняющейся шириной."""
    if len(pts) > 6:
        pts = M.sample_segs(M.catmull(pts, closed=False, tension=tension), closed=False, step=1.5)
    pts = densify(pts, 2.0)
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + math.dist(a, b))
    total = cum[-1] or 1.0
    parts = []
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        t = cum[i] / total
        w = w0 + (w1 - w0) * (t ** 0.8)
        parts.append(LineString([a, b]).buffer(w / 2.0, cap_style="flat", join_style="round", resolution=3))
    return unary_union(parts)


# ---------------------------------------------------------------------------
def district_shapes(adm, dist_geoms, proj):
    """Проецированные и упрощённые контуры (единственный источник геометрии)."""
    out = {}
    for code, short, ru, full, isos, lab, fname in DISTRICTS:
        g = M.clean(proj.project(dist_geoms[code]), min_area=150, tol=1.4, grid=0.5)
        out[code] = g
    return out


def build_map(adm, dist_geoms, country, rivers, lakes, proj, path,
              subjects=True, labels=True, seas=True, title=True, land=True, png=True):
    sc = Scene(MAP_W, MAP_H, BG)
    shp = district_shapes(adm, dist_geoms, proj)
    proj_country = M.clean(M.unary_union(list(shp.values())), min_area=45, tol=0.5, grid=0.5)

    # рамка
    sc.rect((22, 22, MAP_W - 22, MAP_H - 22), fill=None, stroke=INK, width=2.4)

    if title:
        sc.text(70, 76, "РОССИЯ", size=40, color=INK, anchor="start", spacing=7, weight="bold")
        sc.text(72, 106, "СХЕМА КРУПНЫХ РЕГИОНОВ", size=13.5, color="#8A7E72", anchor="start", spacing=4.2)

    # суша — очень светлый тон, чтобы карта читалась, а не «висела» линиями
    if land:
        sc.poly(proj_country, fill=LAND, stroke=None, tension=0.85)

    # контуры субъектов — тонкая подложка
    if subjects:
        for iso, (g, name) in adm.items():
            pg = M.clean(proj.project(g), min_area=18, tol=0.7, grid=0.5)
            if pg.is_empty:
                continue
            sc.poly(pg, fill=None, stroke=HAIR, width=0.75, tension=0.8)

    # реки
    for ru_name, en_name, src, dst in RIVERS:
        segs = rivers.get(en_name) or []
        if not segs:
            print("  !! нет реки", en_name)
            continue
        ll = river_path(segs, dst)
        if not ll:
            print("  !! не склеилась река", en_name)
            continue
        pp = [proj(x, y) for x, y in ll]
        sc.poly(ribbon(pp, 0.9, 4.6), fill=BLUE, stroke=None, smooth=False)

    # озёра
    for en, ru in LAKE_NAMES.items():
        g = lakes.get(en)
        if g is None:
            continue
        pg = M.clean(proj.project(g), min_area=20, tol=0.4)
        sc.poly(pg, fill=BLUE, stroke=INK, width=1.6, tension=0.75)
    cap = lakes.get("Caspian")
    if cap is not None:
        pg = M.clean(proj.project(cap), min_area=50, tol=0.5)
        sc.poly(pg, fill=BLUE, stroke=INK, width=1.6, tension=0.75)

    # крупные регионы — поверх всего
    for code, short, ru, full, isos, lab, fname in DISTRICTS:
        sc.poly(shp[code], fill=None, stroke=INK, width=2.6, tension=0.85)

    if seas:
        for name, lon, lat in SEAS:
            x, y = proj(lon, lat)
            if not (60 < x < MAP_W - 60 and 120 < y < MAP_H - 60):
                continue
            for i, line in enumerate(name.split("\n")):
                sc.text(x, y + i * 19, line.upper(), size=11.5, color=SEA, spacing=2.6,
                        italic=True, halo=BG)

    if labels:
        for code, short, ru, full, isos, lab, fname in DISTRICTS:
            x, y = proj(*lab)
            n = short.count("\n") + 1
            sc.text(x, y - (n - 1) * 10, short, size=21, color=INK, spacing=2.4,
                    weight="bold", halo=LAND, lh=21)

    svg = M.to_svg(sc, width_cm=58.0)
    open(path, "w", encoding="utf-8").write(svg)
    print("  ->", os.path.basename(path), f"{len(svg)/1024:.0f} КБ")
    if png:
        M.to_png(sc, path.replace(".svg", ".png"), ss=2, dpi=(2 * 2.54 / CM_PER_PX))
    return sc


# ---------------------------------------------------------------------------
def _overlap(a, b, pad=3.0):
    return not (a[2] + pad < b[0] or b[2] + pad < a[0] or a[3] + pad < b[1] or b[3] + pad < a[1])


def short_name(s):
    s = s.replace(" область", " обл.").replace("Республика ", "Респ. ")
    s = s.replace("Чукотский автономный округ", "Чукотский АО")
    s = s.replace("Ямало-Ненецкий АО", "Ямало-Ненецкий АО")
    s = s.replace("Северная Осетия", "Сев. Осетия")
    s = s.replace("Карачаево-Черкесия", "Карачаево-Черкесия")
    return s


def place_labels(items, country_prep, W, H, avoid=None):
    """Расстановка подписей: сначала крупные; подпись стараемся уложить внутрь региона."""
    placed = []
    out = []
    for it in sorted(items, key=lambda i: -i["area"]):
        w, h = it["w"], it["h"]
        best = None
        for inside_only in (True, False):
            for rad in range(0, 250, 6):
                cands = [(0, 0)] if rad == 0 else [
                    (math.cos(2 * math.pi * k / 24) * rad, math.sin(2 * math.pi * k / 24) * rad * 0.62)
                    for k in range(24)]
                for dx, dy in cands:
                    x, y = it["x"] + dx, it["y"] + dy
                    box = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
                    if box[0] < 50 or box[2] > W - 50 or box[1] < 140 or box[3] > H - 30:
                        continue
                    if inside_only and not it["point"].contains(Point(x, y)):
                        continue
                    if avoid is not None and avoid.contains(Point(x, y)):
                        continue
                    if any(_overlap(box, b) for b in placed):
                        continue
                    best = (x, y, box)
                    break
                if best:
                    break
            if best:
                break
        if best is None:
            x, y = it["x"], it["y"]
            best = (x, y, (x - w / 2, y - h / 2, x + w / 2, y + h / 2))
        placed.append(best[2])
        out.append(dict(it, px=best[0], py=best[1]))
    return out


def build_subject_map(adm, dist_geoms, country, rivers, lakes, proj, path, png=True):
    W, H = 3200, 1800
    sc = Scene(W, H, BG)
    sc.rect((24, 24, W - 24, H - 24), fill=None, stroke=INK, width=2.8)
    sc.text(84, 100, "РОССИЯ", size=56, color=INK, anchor="start", spacing=9, weight="bold")
    sc.text(86, 140, "СУБЪЕКТЫ ФЕДЕРАЦИИ", size=17, color="#8A7E72", anchor="start", spacing=5.2)

    shp = district_shapes(adm, dist_geoms, proj)
    country_px = M.clean(M.unary_union(list(shp.values())), min_area=45, tol=0.5, grid=0.5)
    sc.poly(country_px, fill=LAND, stroke=None)

    items = []
    for iso, (g, name) in adm.items():
        pg = M.clean(proj.project(g), min_area=18, tol=0.55, grid=0.5)
        if pg.is_empty:
            continue
        sc.poly(pg, fill=None, stroke=INK, width=1.15, tension=0.8)
        rp = pg.representative_point()
        label = short_name(RU_SUBJECTS.get(iso, name))
        area = pg.area
        size = 20.0 if area > 120000 else 18.0 if area > 40000 else 16.0 if area > 12000 else 14.0
        f = M._font(size)
        items.append({"iso": iso, "name": label, "x": rp.x, "y": rp.y,
                      "w": f.getlength(label), "h": size * 1.05, "area": area, "size": size,
                      "point": pg})

    for code, short, ru, full, isos, lab, fname in DISTRICTS:
        sc.poly(shp[code], fill=None, stroke=INK, width=3.4, tension=0.85)

    for en in LAKE_NAMES:
        g = lakes.get(en)
        if g is not None:
            sc.poly(M.clean(proj.project(g), min_area=20, tol=0.4), fill=BLUE, stroke=INK,
                    width=2.0, tension=0.75)
    cap = lakes.get("Caspian")
    if cap is not None:
        sc.poly(M.clean(proj.project(cap), min_area=50, tol=0.5), fill=BLUE, stroke=INK,
                width=2.0, tension=0.75)

    from shapely.prepared import prep
    prepared = prep(country_px)
    waters = []
    for en in LAKE_NAMES:
        g = lakes.get(en)
        if g is not None:
            waters.append(M.clean(proj.project(g), min_area=20, tol=0.4))
    if cap is not None:
        waters.append(M.clean(proj.project(cap), min_area=50, tol=0.5))
    avoid = prep(M.unary_union(waters).buffer(6)) if waters else None
    # подписи рисуем после линий-выносок, поэтому собираем их списком
    labels = place_labels(items, prepared, W, H, avoid)
    label_ops = []
    for it in labels:
        dy = it["size"] * 0.35
        label_ops.append(("text", it["px"], it["py"] + dy, it))
    for it in labels:
        d = math.hypot(it["px"] - it["x"], it["py"] - it["y"])
        if d > 14:
            dy = it["size"] * 0.35
            # ближайшая точка рамки подписи
            bx = min(max(it["x"], it["px"] - it["w"] / 2), it["px"] + it["w"] / 2)
            by = min(max(it["y"], it["py"] + dy - it["h"] / 2), it["py"] + dy + it["h"] / 2)
            sc.line([(it["x"], it["y"]), (bx, by)], stroke="#6B6155", width=0.8)
            sc.ops.append({"t": "poly", "rings": [{"d": None, "hole": False,
                                                   "pts": [(it["x"] + 2.2 * math.cos(a), it["y"] + 2.2 * math.sin(a))
                                                           for a in [i * math.pi / 6 for i in range(12)]]}],
                           "fill": "#6B6155", "stroke": None, "w": 0, "opacity": None})
    for _, px, py, it in label_ops:
        sc.text(px, py, it["name"], size=it["size"], color=INK, spacing=0.3, halo="#FFFFFF")

    for name, lon, lat in SEAS:
        x, y = proj(lon, lat)
        if not (60 < x < W - 60 and 120 < y < H - 60):
            continue
        for i, line in enumerate(name.split("\n")):
            sc.text(x, y + i * 24, line.upper(), size=14, color=SEA, spacing=3.0,
                    italic=True, halo=BG)

    svg = M.to_svg(sc, width_cm=96.0)
    open(path, "w", encoding="utf-8").write(svg)
    print("  ->", os.path.basename(path), f"{len(svg)/1024:.0f} КБ")
    if png:
        M.to_png(sc, path.replace(".svg", ".png"), ss=1)
    return sc


def build_templates(adm, dist_geoms, country, rivers, lakes, proj):
    os.makedirs(TPL, exist_ok=True)
    shp = district_shapes(adm, dist_geoms, proj)
    made = []
    for code, short, ru, full, isos, lab, fname in DISTRICTS:
        g = shp[code]
        x0, y0, x1, y1 = g.bounds
        pad = 24
        bx0, by0, bx1 = x0 - pad, y0 - pad, x1 + pad
        w = bx1 - bx0

        # подпись под деталью: при необходимости в две строки и с расширением холста
        name = short.replace("\n", " ")
        csize, cspace = 13.0, 2.2
        f = M._font(csize)
        lines = [name]
        widest = f.getlength(name) + cspace * max(0, len(name) - 1)
        if widest > w - 30 and " " in name:
            words = name.split()
            half = len(words) // 2
            cand = [" ".join(words[:half]), " ".join(words[half:])]
            lines = cand
            widest = max(f.getlength(l) + cspace * max(0, len(l) - 1) for l in lines)
        if widest > w - 30:
            extra = (widest - (w - 30)) / 2
            bx0 -= extra
            bx1 += extra
            w = bx1 - bx0
        cap_top = y1 + 26
        by1 = cap_top + 18 * (len(lines) - 1) + 20
        h = by1 - by0

        path_d = "".join(r["d"] for r in M.smooth_rings(g, 0.85))
        caption = "".join(
            f'<text x="{(bx0+bx1)/2:.0f}" y="{cap_top + 13*i:.0f}" '
            f'font-family="\'PT Sans\',\'Segoe UI\',Arial,sans-serif" font-size="{csize:.0f}" '
            f'letter-spacing="{cspace}" text-anchor="middle" fill="#000000">{l}</text>'
            for i, l in enumerate(lines))
        svg = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w*CM_PER_PX:.2f}cm" '
            f'height="{h*CM_PER_PX:.2f}cm" viewBox="{bx0:.1f} {by0:.1f} {w:.1f} {h:.1f}">',
            f'<path d="{path_d}" fill="none" stroke="#000000" stroke-width="3" '
            f'stroke-linejoin="round" stroke-linecap="round" fill-rule="evenodd"/>',
            caption,
            "</svg>",
        ]
        open(os.path.join(TPL, fname + ".svg"), "w", encoding="utf-8").write("\n".join(svg))

        # png: тот же контур, прозрачный фон, физический размер как у карты
        sc2 = Scene(round(w), round(h), "none")
        for r in M.smooth_rings(g, 0.85):
            sc2.ops.append({"t": "poly",
                            "rings": [{"d": None, "hole": r["hole"],
                                       "pts": [(px - bx0, py - by0) for px, py in r["pts"]]}],
                            "fill": None, "stroke": "#000000", "w": 3.0, "opacity": None})
        for i, l in enumerate(lines):
            sc2.text(w / 2, cap_top + 13 * i - by0, l, size=csize, color="#000000", spacing=cspace)
        long_side = max(w, h)
        k = max(2, math.ceil(1000 / long_side))
        M.to_png(sc2, os.path.join(TPL, fname + ".png"), ss=k, dpi=k * 2.54 / CM_PER_PX, keep=True)
        made.append((fname, w, h, k))
        print(f"  -> {fname}.svg  {w*CM_PER_PX:.0f}x{h*CM_PER_PX:.0f} см, png x{k}")
    return made


# ---------------------------------------------------------------------------
def raw_path(geom, prec=0):
    out = []
    for ext, holes in M.rings_of(geom):
        for ring in [ext] + holes:
            if len(ring) < 3:
                continue
            out.append("M" + "L".join(f"{x:.{prec}f},{y:.{prec}f}" for x, y in ring) + "Z")
    return "".join(out)


def build_web(adm, dist_geoms, country, rivers, lakes, proj, path):
    """Данные для интерактивной страницы: те же контуры, но в JSON."""
    import json
    shp = district_shapes(adm, dist_geoms, proj)
    land = M.clean(M.unary_union(list(shp.values())), min_area=150, tol=1.4, grid=0.5)
    data = {
        "w": MAP_W, "h": MAP_H,
        "land": "".join(r["d"] for r in M.smooth_rings(land, prec=0)),
    }
    data["districts"] = [
        {"id": c, "name": short, "full": full, "d": "".join(r["d"] for r in M.smooth_rings(shp[c], 0.85, prec=0)),
         "x": round(proj(*lab)[0]), "y": round(proj(*lab)[1])}
        for c, short, ru, full, isos, lab, fname in DISTRICTS
    ]
    iso2dist = {}
    for c, short, ru, full, isos, lab, fname in DISTRICTS:
        for i in isos.split():
            iso2dist[i] = c
    subs = []
    for iso, (g, name) in adm.items():
        pg = M.clean(proj.project(g), min_area=60, tol=0.9, grid=0.5)
        if pg.is_empty:
            continue
        subs.append({"iso": iso, "name": RU_SUBJECTS.get(iso, name),
                     "district": iso2dist.get(iso), "d": raw_path(pg)})
    data["subjects"] = subs

    rv = []
    for ru_name, en_name, src, dst in RIVERS:
        ll = river_path(rivers.get(en_name) or [], dst)
        if not ll:
            continue
        pp = [proj(x, y) for x, y in ll]
        rv.append({"name": ru_name, "d": raw_path(ribbon(pp, 0.9, 4.6))})
    data["rivers"] = rv

    lk = []
    for en, ru in LAKE_NAMES.items():
        g = lakes.get(en)
        if g is not None:
            lk.append({"name": ru, "d": raw_path(M.clean(proj.project(g), min_area=20, tol=0.4))})
    if lakes.get("Caspian") is not None:
        lk.append({"name": "Каспийское море",
                   "d": raw_path(M.clean(proj.project(lakes["Caspian"]), min_area=50, tol=0.5))})
    data["lakes"] = lk
    data["seas"] = [{"name": n, "x": round(proj(lon, lat)[0]), "y": round(proj(lon, lat)[1])}
                    for n, lon, lat in SEAS]

    # кадр для сайта — по фактическому содержимому, без пустых полей плаката
    x0, y0, x1, y1 = land.bounds
    for s in data["seas"]:
        x0 = min(x0, s["x"] - 70)
        x1 = max(x1, s["x"] + 70)
        y0 = min(y0, s["y"] - 26)
        y1 = max(y1, s["y"] + 26)
    pad = 16
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(MAP_W, x1 + pad), min(MAP_H, y1 + pad)
    data["vb"] = [round(x0), round(y0), round(x1 - x0), round(y1 - y0)]

    js = "window.MAP_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    open(path, "w", encoding="utf-8").write(js)
    print(f"  -> {os.path.basename(path)} {len(js)/1024:.0f} КБ "
          f"(субъектов {len(subs)}, округов {len(data['districts'])})")
    return data


def main():
    print("читаю данные…")
    adm, dist_geoms, country = load()
    rivers = load_rivers()
    lakes = load_lakes()

    proj = Albers(lat1=50, lat2=70, lon0=100, lat0=55)
    proj.fit([country], (60, 130, MAP_W - 60, MAP_H - 46), pad=0)
    print(f"  масштаб {proj.s:.1f} px/ед, bbox {proj.bx0:.2f}..{proj.bx1:.2f}")

    print("карта…")
    build_map(adm, dist_geoms, country, rivers, lakes, proj,
              os.path.join(OUT, "karta_rossii.svg"))
    build_map(adm, dist_geoms, country, rivers, lakes, proj,
              os.path.join(OUT, "karta_rossii_chistaya.svg"),
              subjects=False, labels=False, seas=False, land=False)
    print("карта субъектов…")
    proj2 = Albers(lat1=50, lat2=70, lon0=100, lat0=55)
    proj2.fit([country], (70, 170, 3130, 1760))
    build_subject_map(adm, dist_geoms, country, rivers, lakes, proj2,
                      os.path.join(OUT, "karta_subektov.svg"))
    print("шаблоны…")
    build_templates(adm, dist_geoms, country, rivers, lakes, proj)
    print("данные для сайта…")
    os.makedirs(os.path.join(OUT, "assets"), exist_ok=True)
    build_web(adm, dist_geoms, country, rivers, lakes, proj,
              os.path.join(OUT, "assets", "data.js"))


if __name__ == "__main__":
    main()



