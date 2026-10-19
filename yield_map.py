"""yield_map v1.0 — mapa de rinde del lote a partir de los puntos del monitor de cosecha.

Sigue el flujo "simple" del paquete pacu (Precision Agriculture Computational Utilities, dos Santos
y Miguez): validar los puntos, limpiar los valores atípicos por desvío estándar y armar el mapa
interpolando por distancia inversa (IDW) sobre una grilla regular.

El resultado es **relativo a la media del lote** (índice de rinde, 100 = media), así el mismo mapa
sirve para cualquier cultivo y unidad y deja ver las zonas más flojas y las mejores. No inventa: sin
puntos suficientes queda en 'sin dato'.
"""
import math

import research_connectors as c
import scales

CLEAN_SD = 3.0          # se descarta lo que cae fuera de media ± 3·desvío estándar
MIN_POINTS = 5          # con menos puntos no hay mapa
MAX_POINTS = 5000
DEFAULT_CELL_M = 10.0   # lado de celda por defecto (metros)
MIN_CELL_M = 2.0
MAX_CELL_M = 100.0
MAX_CELLS = 2500        # tope de celdas: si la grilla se pasa, se agranda la celda
POWER = 2.0             # exponente del IDW
SCALE = 'yield_index'
SOURCE = 'https://github.com/cldossantos/pacu'
ORGANISM = 'DOTS · monitor de cosecha (método pacu, dos Santos y Miguez)'
METHODO = ('Método "simple" de pacu: limpieza por desvío estándar (se descarta lo que cae fuera de '
           'media ± 3σ) e interpolación por distancia inversa (IDW, p=2) sobre una grilla regular; el '
           'valor de cada celda es relativo a la media del lote (índice de rinde, 100 = media).')
CAVEAT = ('Mapa relativo al lote, no una medición absoluta ni un mapa oficial. Asume puntos del monitor '
          'en el mismo cultivo y sin corrección por humedad; la interpolación suaviza el detalle entre pasadas.')


def _num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _points(raw):
    """Lista de [lat, lon] validada (misma convención de vértices que el resto de DOTS)."""
    if not isinstance(raw, list):
        raise ValueError('Se esperan los puntos del monitor: una lista de [lat, lon]')
    pts = []
    for p in raw:
        if not isinstance(p, (list, tuple)) or len(p) < 2:
            raise ValueError('Cada punto debe ser [lat, lon]')
        lat, lon = _num(p[0]), _num(p[1])
        if lat is None or lon is None or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError('Un punto no tiene coordenadas válidas')
        pts.append((lat, lon))
    if len(pts) < MIN_POINTS:
        raise ValueError(f'Hacen falta al menos {MIN_POINTS} puntos para armar el mapa')
    if len(pts) > MAX_POINTS:
        raise ValueError(f'Demasiados puntos ({len(pts)}): el máximo es {MAX_POINTS}')
    return pts


def _values(raw, n):
    if not isinstance(raw, list) or len(raw) != n:
        raise ValueError('Cada punto necesita un valor de rinde')
    vals = []
    for v in raw:
        x = _num(v)
        if x is None:
            raise ValueError('Un valor de rinde no es numérico')
        vals.append(x)
    return vals


def clean(points, values, sd=CLEAN_SD):
    """Descarta rindes nulos (≤ 0, típicos fuera del lote) y atípicos fuera de media ± sd·desvío."""
    pairs = [(p, v) for p, v in zip(points, values) if v > 0]
    zeros = len(points) - len(pairs)
    vals = [v for _, v in pairs]
    if len(vals) >= 2:
        mean = sum(vals) / len(vals)
        s = math.sqrt(sum((v - mean) ** 2 for v in vals) / (len(vals) - 1))
        lo, hi = mean - sd * s, mean + sd * s
        keep = [(p, v) for p, v in pairs if lo <= v <= hi]
    else:
        keep = pairs
    removed = {'nulos': zeros, 'atipicos': len(pairs) - len(keep), 'total': len(points) - len(keep)}
    return [p for p, _ in keep], [v for _, v in keep], removed


def stats(values):
    srt = sorted(values)
    n = len(srt)
    mean = sum(srt) / n
    med = srt[n // 2] if n % 2 else (srt[n // 2 - 1] + srt[n // 2]) / 2
    sd = math.sqrt(sum((v - mean) ** 2 for v in srt) / (n - 1)) if n > 1 else 0.0
    return {'n': n, 'mean': mean, 'median': med, 'min': srt[0], 'max': srt[-1], 'sd': sd,
            'cv_pct': round(100 * sd / mean, 1) if mean else None}


def idw(lat, lon, points, values, power=POWER):
    """Rinde interpolado en un punto por distancia inversa. Si cae sobre un punto, devuelve su valor."""
    num = den = 0.0
    for (plat, plon), v in zip(points, values):
        d = c._km(lat, lon, plat, plon)
        if d < 0.0005:
            return v
        w = 1.0 / (d ** power)
        num += w * v
        den += w
    return (num / den) if den else None


def grid(points, values, cell_m=DEFAULT_CELL_M, boundary=None, max_cells=MAX_CELLS):
    """Grilla regular (celda en metros) interpolada por IDW; el índice es el valor sobre la media del lote."""
    lats = [p[0] for p in points] + ([p[0] for p in boundary] if boundary else [])
    lons = [p[1] for p in points] + ([p[1] for p in boundary] if boundary else [])
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    coslat = math.cos(math.radians((min_lat + max_lat) / 2)) or 1.0
    dlat = cell_m / 110540.0
    dlon = cell_m / (111320.0 * coslat)
    ny = int((max_lat - min_lat) / dlat) + 1
    nx = int((max_lon - min_lon) / dlon) + 1
    while nx * ny > max_cells:
        dlat *= 2; dlon *= 2; cell_m *= 2
        ny = int((max_lat - min_lat) / dlat) + 1
        nx = int((max_lon - min_lon) / dlon) + 1
    mean = sum(values) / len(values)
    cells = []
    for j in range(ny):
        clat = min_lat + (j + 0.5) * dlat
        for i in range(nx):
            clon = min_lon + (i + 0.5) * dlon
            if boundary and not c.point_in_polygon(clat, clon, boundary):
                continue
            v = idw(clat, clon, points, values)
            if v is None:
                continue
            cells.append({'lat': round(clat, 6), 'lon': round(clon, 6), 'value': round(v, 3),
                          'index': round(100 * v / mean, 1) if mean else None})
    return cells, round(cell_m, 1)


def _reading(d):
    r = d['removed']
    return (f"Mapa de rinde de {d['n_used']} puntos útiles sobre {d['n_points']} "
            f"({r['atipicos']} atípicos y {r['nulos']} nulos descartados). "
            f"Rinde medio del lote {d['mean']} (mediana {d['median']}), de {d['min']} a {d['max']}; "
            f"variación {d['cv_pct']} %. El índice es relativo a la media del lote (100 = media).")


def analyze(payload):
    import vegetation as veg
    payload = payload or {}
    pts = _points(payload.get('points'))
    raw_vals = payload.get('values') if payload.get('values') is not None else payload.get('yield')
    vals = _values(raw_vals, len(pts))
    boundary = c._poly(payload['boundary']) if payload.get('boundary') else None

    kept_p, kept_v, removed = clean(pts, vals)
    if len(kept_v) < MIN_POINTS:
        return c.envelope(None, SOURCE, 'mapa de rinde del lote (relativo a la media)', ORGANISM, 'sin dato',
                          f'Tras limpiar quedan {len(kept_v)} puntos: hacen falta al menos {MIN_POINTS}.')
    st = stats(kept_v)
    cell_m = _num(payload.get('cell_m')) or DEFAULT_CELL_M
    cell_m = min(max(cell_m, MIN_CELL_M), MAX_CELL_M)
    cells, cell_used = grid(kept_p, kept_v, cell_m, boundary)
    data = {'n_points': len(pts), 'n_used': st['n'], 'removed': removed,
            'mean': round(st['mean'], 3), 'median': round(st['median'], 3),
            'min': round(st['min'], 3), 'max': round(st['max'], 3), 'sd': round(st['sd'], 3),
            'cv_pct': st['cv_pct'], 'cell_m': cell_used, 'n_cells': len(cells), 'cells': cells,
            'area_ha': veg.area_ha(boundary) if boundary else None,
            'scale': scales.describe(SCALE), 'method': METHODO, 'caveat': CAVEAT}
    data['reading'] = _reading(data)
    return c.envelope(data, SOURCE, 'mapa de rinde del lote (relativo a la media)', ORGANISM)
