"""Entorno del lote con Overture Maps (datos abiertos: OSM, Microsoft, Google, Esri y otros).

Para cada lote calcula, una vez por versión de Overture (sale cada mes):
  - caminos: kilómetros dentro del lote y en 2 km a la redonda, separados en rutas y caminos rurales;
  - distancia desde el lote al camino y a la ruta más cercanos;
  - construcciones (casas, galpones, tinglados) dentro del lote y en 2 km;
  - departamento o partido y provincia donde cae el lote.
Lee los GeoParquet públicos de Overture en S3 con DuckDB, filtrando por recuadro: no descarga el mundo.
Gratis, sin clave. No imprime coordenadas (los registros de GitHub Actions son públicos).
"""
import math, os, re

import numpy as np

BUCKET = "overturemaps-us-west-2"
LIST_URL = f"https://{BUCKET}.s3.us-west-2.amazonaws.com/?list-type=2&prefix=release/&delimiter=/"
NEAR_M = 2000
SEARCH_M = 6000          # radio para buscar el camino más cercano
RUTAS = {"motorway", "trunk", "primary", "secondary"}
CAMINOS = {"tertiary", "unclassified", "residential", "living_street", "service", "track", "unknown"}


def latest_release():
    rel = os.environ.get("OVERTURE_RELEASE")
    if rel:
        return rel
    import requests
    xml = requests.get(LIST_URL, timeout=30).text
    rels = sorted(set(re.findall(r"<Prefix>release/([0-9]{4}-[0-9]{2}-[0-9]{2}[^/<]*)/</Prefix>", xml)))
    if not rels:
        raise RuntimeError("No se encontró la versión de Overture")
    return rels[-1]


def _bbox(geom, margin_m):
    c = geom.centroid
    dlat = margin_m / 110540; dlon = margin_m / (111320 * math.cos(math.radians(c.y)))
    x0, y0, x1, y1 = geom.bounds
    return (x0 - dlon, y0 - dlat, x1 + dlon, y1 + dlat)


def to_metres(geom, ref):
    """Proyección local equirectangular centrada en el lote (sirve para distancias de pocos km)."""
    import shapely
    k = math.cos(math.radians(ref.y))
    return shapely.transform(geom, lambda xy: (xy - np.array([ref.x, ref.y])) * np.array([111320 * k, 110540]))


class Reader:
    """Consultas DuckDB contra los GeoParquet de Overture."""

    def __init__(self, release, base=None):
        import duckdb
        self.release = release
        self.base = base or f"s3://{BUCKET}/release/{release}"
        self.db = duckdb.connect()
        if self.base.startswith("s3://"):
            for q in ("INSTALL httpfs", "LOAD httpfs", "SET s3_region='us-west-2'"):
                self.db.execute(q)
        # La geometría se pide como WKB y la procesa shapely: no hace falta la extensión spatial.

    def rows(self, theme, kind, bbox, cols, where="TRUE"):
        from shapely import wkb
        src = f"read_parquet('{self.base}/theme={theme}/type={kind}/*', hive_partitioning=1)"
        box = (f"bbox.xmin < {bbox[2]} AND bbox.xmax > {bbox[0]} AND bbox.ymin < {bbox[3]} AND bbox.ymax > {bbox[1]}")
        out = None
        for g in ("ST_AsWKB(geometry)", "geometry"):   # según la versión, geometry llega como GEOMETRY o como WKB
            try:
                out = self.db.execute(f"SELECT {g} AS g, {cols} FROM {src} WHERE {box} AND ({where})").fetchall()
                break
            except Exception:
                if g == "geometry":
                    raise
        res = []
        for r in out:
            raw = r[0]
            try:
                geom = wkb.loads(raw if isinstance(raw, str) else bytes(raw))
            except Exception:
                continue
            res.append((geom,) + tuple(r[1:]))
        return res


def summarize(lot, roads, buildings, divisions):
    """lot: polígono lon/lat. roads: [(geom, clase)]. buildings: [geom]. divisions: [(geom, subtipo, nombre)]."""
    ref = lot.centroid
    lot_m = to_metres(lot, ref)
    near_m = lot_m.buffer(NEAR_M)
    km = {"rutas_lote": 0.0, "caminos_lote": 0.0, "rutas_2km": 0.0, "caminos_2km": 0.0}
    nearest = {"ruta": None, "camino": None}
    for g, cls in roads:
        group = "rutas" if cls in RUTAS else "caminos" if cls in CAMINOS else None
        if not group:
            continue
        gm = to_metres(g, ref)
        km[f"{group}_lote"] += gm.intersection(lot_m).length / 1000
        km[f"{group}_2km"] += gm.intersection(near_m).length / 1000
        d = 0.0 if gm.intersects(lot_m) else gm.distance(lot_m)
        key = "ruta" if group == "rutas" else "camino"
        if nearest[key] is None or d < nearest[key]:
            nearest[key] = d
    any_road = [v for v in nearest.values() if v is not None]
    b_in = b_near = 0
    roof = 0.0
    for g in buildings:
        gm = to_metres(g, ref)
        if gm.intersects(lot_m):
            b_in += 1; roof += gm.area
        if gm.intersects(near_m):
            b_near += 1
    admin = {}
    for g, sub, name in divisions:
        if name and g.contains(ref):
            if sub == "county": admin["departamento"] = name
            elif sub == "region": admin["provincia"] = name
            elif sub == "locality" and "localidad" not in admin: admin["localidad"] = name
    r = lambda v: None if v is None else round(v)
    return {
        "caminos_km": {k: round(v, 2) for k, v in km.items()},
        "camino_mas_cercano_m": r(min(any_road)) if any_road else None,
        "ruta_mas_cercana_m": r(nearest["ruta"]),
        "construcciones_lote": b_in, "techo_m2_lote": round(roof),
        "construcciones_2km": b_near,
        **admin,
    }


def lot_context(lot, reader):
    big = _bbox(lot, SEARCH_M)
    near = _bbox(lot, NEAR_M)
    roads = [(g, cls) for g, cls in reader.rows("transportation", "segment", big, "class", "subtype = 'road'")]
    buildings = [row[0] for row in reader.rows("buildings", "building", near, "1 AS uno")]
    c = lot.centroid
    pt = (c.x - 1e-4, c.y - 1e-4, c.x + 1e-4, c.y + 1e-4)
    divisions = reader.rows("divisions", "division_area", pt, "subtype, names.primary",
                            "subtype IN ('region', 'county', 'locality')")
    out = summarize(lot, roads, buildings, divisions)
    out["release"] = reader.release
    return out
