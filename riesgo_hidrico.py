"""riesgo_hidrico v1.0 — lomas, planos y bajos del lote, y dónde se vio agua, con Google Earth Engine.

Relieve: modelo de elevación Copernicus GLO-30 (30 m). Dentro del lote se ordenan las alturas: el 20 % más bajo es
"bajo", el 30 % más alto es "loma" y el resto "plano". En llanuras muy chatas una diferencia de pocos decímetros
decide por dónde corre y dónde se junta el agua, por eso la comparación es dentro del mismo campo.
Agua observada: JRC Global Surface Water (Landsat, 1984-2021), porcentaje de las observaciones en que cada píxel de
30 m tuvo agua. Un bajo donde se vio agua es "bajo anegable"; si se vio agua en más del 25 % de las veces, "laguna o
bañado". También se informa la altura sobre el drenaje más cercano (MERIT Hydro HAND, 90 m).
Es una lectura del terreno y de la historia satelital, no un modelo hidrológico: no calcula cuánta lluvia hace falta
para anegar cada zona (eso requiere suelos, napa y canales). Referencia oficial en la Cuenca del Salado: GeoCuenca (INTA).
"""
import math

import research_connectors as c
import vegetation as veg

CLASSES = [('loma', 'Loma', '#c9a227'), ('plano', 'Plano', '#9ccc65'), ('bajo', 'Bajo', '#4fa3d1'),
           ('anegable', 'Bajo anegable', '#1f5fa8'), ('laguna', 'Laguna o bañado', '#0b2f6b')]
MAX_POINTS = 1800


def _f(name, **args):
    return {'functionInvocationValue': {'functionName': name, 'arguments': args}}


def _k(v):
    return {'constantValue': v}


def grid_points(pts):
    """Puntos regulares dentro del lote (vértices [lat, lon]); paso >= 30 m y no más de MAX_POINTS."""
    lats = [p[0] for p in pts]; lons = [p[1] for p in pts]
    s, n, w, e = min(lats), max(lats), min(lons), max(lons)
    area = veg.area_ha(pts) * 1e4
    step_m = max(30.0, math.sqrt(area / MAX_POINTS) * 1.03)
    dlat = step_m / 111320.0
    dlon = step_m / (111320.0 * math.cos(math.radians((s + n) / 2)))
    out = []
    lat = s + dlat / 2
    while lat < n:
        lon = w + dlon / 2
        while lon < e:
            if c.point_in_polygon(lat, lon, pts):
                out.append((round(lat, 6), round(lon, 6)))
            lon += dlon
        lat += dlat
    return out, dlat, dlon, step_m


def expression(points):
    feats = [_f('Feature', geometry=_f('GeometryConstructors.Point', coordinates=_k([lo, la])), metadata=_k({'i': i}))
             for i, (la, lo) in enumerate(points)]
    fc = _f('Collection', features={'arrayValue': {'values': feats}})
    dem = _f('Image.rename', input=_f('Image.select', input=_f('ImageCollection.mosaic', collection=_f('ImageCollection.load', id=_k('COPERNICUS/DEM/GLO30'))),
                                       bandSelectors=_k(['DEM'])), names=_k(['dem']))
    occ = _f('Image.rename', input=_f('Image.unmask', input=_f('Image.select', input=_f('Image.load', id=_k('JRC/GSW1_4/GlobalSurfaceWater')),
                                                                bandSelectors=_k(['occurrence'])), value=_f('Image.constant', value=_k(0))), names=_k(['occ']))
    hand = _f('Image.rename', input=_f('Image.select', input=_f('Image.load', id=_k('MERIT/Hydro/v1_0_1')), bandSelectors=_k(['hnd'])), names=_k(['hand']))
    img = _f('Image.addBands', dstImg=_f('Image.addBands', dstImg=dem, srcImg=occ), srcImg=hand)
    out = _f('Image.sampleRegions', image=img, collection=fc, properties=_k(['i']), scale=_k(30), geometries=_k(False))
    return {'expression': {'result': 'out', 'values': {'out': out}}}


def pct(vals, q):
    v = sorted(vals)
    k = q * (len(v) - 1); lo = int(k)
    return v[lo] + (v[min(lo + 1, len(v) - 1)] - v[lo]) * (k - lo)


def classify(samples):
    """samples: [(lat, lon, dem, occ, hand)] → [(lat, lon, clase)] y umbrales."""
    dems = [s[2] for s in samples if s[2] is not None]
    if len(dems) < 10:
        raise ValueError('El modelo de elevación no devolvió suficientes puntos dentro del lote')
    lo_cut, hi_cut = pct(dems, 0.2), pct(dems, 0.7)
    out = []
    for la, lo, dem, occ, hand in samples:
        if dem is None:
            continue
        occ = occ or 0
        if occ >= 25:
            k = 'laguna'
        elif dem <= lo_cut and occ > 0:
            k = 'anegable'
        elif dem <= lo_cut:
            k = 'bajo'
        elif dem >= hi_cut:
            k = 'loma'
        else:
            k = 'anegable' if occ >= 5 else 'plano'
        out.append((la, lo, k))
    return out, {'bajo_m': round(lo_cut, 1), 'loma_m': round(hi_cut, 1), 'min_m': round(min(dems), 1), 'max_m': round(max(dems), 1)}


def summarize(cells, area_ha, cuts, hands, occs):
    n = len(cells) or 1
    zones = []
    for key, name, color in CLASSES:
        k = sum(1 for x in cells if x[2] == key)
        zones.append({'key': key, 'name': name, 'color': color, 'pct': round(100 * k / n, 1), 'ha': round(area_ha * k / n, 1)})
    wet = sum(z['ha'] for z in zones if z['key'] in ('anegable', 'laguna'))
    relief = cuts['max_m'] - cuts['min_m']
    reading = (f"El campo tiene {relief:.1f} m de desnivel. "
               f"Bajos: {sum(z['pct'] for z in zones if z['key'] in ('bajo', 'anegable', 'laguna')):.0f} % del lote; "
               f"en {wet:.0f} ha los satélites vieron agua alguna vez desde 1984 (bajos anegables, lagunas o bañados). "
               f"Lomas: {next(z['pct'] for z in zones if z['key'] == 'loma'):.0f} %.")
    seen = [o for o in occs if o]
    return {'zones': zones, 'cuts': cuts, 'relief_m': round(relief, 1), 'water_seen_ha': round(wet, 1),
            'hand_median_m': round(sorted(hands)[len(hands) // 2], 1) if hands else None,
            'water_seen_pct_of_lot': round(100 * len(seen) / (len(occs) or 1), 1), 'reading': reading}


def analyze(polygon):
    pts = veg.require_polygon(polygon)
    area = veg.area_ha(pts)
    points, dlat, dlon, step = grid_points(pts)
    if len(points) < 10:
        raise ValueError('El lote es demasiado chico para separar lomas y bajos con datos de 30 m')
    proj, tok = veg.gee_token()
    url = f'{veg.GEE}/projects/{proj}/value:compute'
    r = c.SESSION.post(url, json=expression(points), headers={'Authorization': f'Bearer {tok}'}, timeout=55)
    if r.status_code >= 400:
        try:
            msg = (r.json().get('error') or {}).get('message', '')
        except ValueError:
            msg = r.text[:200]
        return c.envelope(None, veg.GEE, 'riesgo hídrico del lote', 'Google Earth Engine', 'sin dato', f'Earth Engine HTTP {r.status_code}: {msg[:200]}')
    by = {}
    for f in (r.json().get('result') or {}).get('features') or []:
        p = f.get('properties') or {}
        if p.get('i') is not None:
            by[int(p['i'])] = p
    samples = [(la, lo, by.get(i, {}).get('dem'), by.get(i, {}).get('occ'), by.get(i, {}).get('hand')) for i, (la, lo) in enumerate(points)]
    cells, cuts = classify(samples)
    data = summarize(cells, area, cuts, [s[4] for s in samples if s[4] is not None], [s[3] for s in samples if s[2] is not None])
    data.update(grid={'cells': [[la, lo, k] for la, lo, k in cells], 'dlat': round(dlat, 7), 'dlon': round(dlon, 7), 'step_m': round(step)},
                area_ha=area, classes=[{'key': k, 'name': n, 'color': col} for k, n, col in CLASSES],
                method=__doc__.split('\n\n', 1)[1].strip())
    return c.envelope(data, url.replace(proj, '{PROJECT}'), 'riesgo hídrico del lote: lomas, planos y bajos',
                      'Copernicus GLO-30 · JRC Global Surface Water · MERIT Hydro vía Google Earth Engine')
