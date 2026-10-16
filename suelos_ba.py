"""suelos_ba v1.0 — suelos del campo según las Cartas de Suelos 1:50.000 de la provincia de Buenos Aires (INTA).

Fuente: INTA, Instituto de Suelos (CIRN), "Cartas de Suelos de la República Argentina - Provincia de Buenos Aires",
mapa vectorial 1:50.000, versión 2.0 (2023), licencia CC BY 4.0 (doi:10.5281/zenodo.7837681). Una tarea automática lo
divide en recuadros de 0,25° (rama `suelos` del repositorio, scripts/suelos_ba_tiles.py) y acá se cruza cada unidad
cartográfica con el límite del campo: qué unidades hay, con qué series, capacidad de uso, paisaje y taxonomía, y qué
parte del campo ocupa cada una. Escala 1:50.000: no reemplaza un estudio de suelos a nivel de lote.
"""
import math

import research_connectors as c

SOURCE = ('INTA, Instituto de Suelos (CIRN). Cartas de Suelos de la República Argentina, provincia de Buenos Aires, '
          '1:50.000, v2.0 (2023), CC BY 4.0, doi:10.5281/zenodo.7837681.')
BBOX = (-63.4, -41.1, -56.6, -33.2)
STEP = 0.25


def tile_ids(w, s, e, n):
    out = []
    y = math.floor(s / STEP) * STEP
    while y < n:
        x = math.floor(w / STEP) * STEP
        while x < e:
            out.append(f'{y:.2f}_{x:.2f}')
            x += STEP
        y += STEP
    return out


def at_polygon(polygon):
    from poblacion import geometry as G
    pts = [[float(a), float(b)] for a, b in polygon]
    lats = [p[0] for p in pts]; lons = [p[1] for p in pts]
    w, s, e, n = min(lons), min(lats), max(lons), max(lats)
    if not (BBOX[0] <= (w + e) / 2 <= BBOX[2] and BBOX[1] <= (s + n) / 2 <= BBOX[3]):
        return None
    import datastore
    lot = G.Geom([[ [[lo, la] for la, lo in pts] + [[pts[0][1], pts[0][0]]] ]])
    total = G.area_km2(lot)
    if not total:
        return None
    units = None
    acc = {}
    for t in tile_ids(w, s, e, n):
        tile = datastore.load(f'suelos_ba/{t}.json', branch='suelos', ttl=86400)
        if not tile:
            continue
        units = units or datastore.load('suelos_ba/unidades.json', branch='suelos', ttl=86400) or {}
        for uid, bb, rings in tile.get('f') or []:
            if bb[2] < w or bb[0] > e or bb[3] < s or bb[1] > n:
                continue
            inter = G.intersection(lot, G.Geom([rings]))
            if inter.is_empty:
                continue
            acc[uid] = acc.get(uid, 0.0) + G.area_km2(inter)
    if not acc:
        return {'units': [], 'source': SOURCE, 'note': 'Sin unidades cartográficas 1:50.000 en el límite del campo.'}
    rows = []
    for uid, km2 in sorted(acc.items(), key=lambda x: -x[1]):
        u = (units or {}).get(str(uid)) or {}
        rows.append({'symbol': u.get('s') or '—', 'name': u.get('n') or '', 'composition': u.get('comp') or '—',
                     'capability': u.get('cap') or '—', 'taxonomy': u.get('tax') or '—', 'landscape': u.get('pai') or '',
                     'pct': round(100 * km2 / total, 1), 'ha': round(km2 * 100, 1)})
    rows = [r for r in rows if r['pct'] >= 0.5]
    top = rows[0]
    reading = (f"El campo está sobre {len(rows)} unidad{'es' if len(rows) != 1 else ''} de suelo. La principal es {top['symbol']} "
               f"({top['name']}, {top['pct']:.0f} % del campo), capacidad de uso {top['capability']}.")
    return {'units': rows, 'reading': reading, 'source': SOURCE, 'scale': '1:50.000'}


def analyze(polygon):
    pts = [[float(a), float(b)] for a, b in polygon]
    d = at_polygon(pts)
    if d is None:
        return c.envelope(None, 'https://doi.org/10.5281/zenodo.7837681', 'suelos 1:50.000', 'INTA', 'sin dato',
                          'La cartografía de suelos 1:50.000 está disponible para la provincia de Buenos Aires.')
    if not d['units']:
        return c.envelope(None, 'https://doi.org/10.5281/zenodo.7837681', 'suelos 1:50.000', 'INTA', 'sin dato', d['note'])
    return c.envelope(d, 'https://doi.org/10.5281/zenodo.7837681', 'suelos del campo 1:50.000', 'INTA · Instituto de Suelos')
