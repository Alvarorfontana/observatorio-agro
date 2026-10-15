"""cobertura_ee v1.0 — cobertura reciente y cambios del lote con Google Earth Engine (REST, sin librerías pesadas).

Dynamic World (Google y World Resources Institute, CC BY 4.0): clasificación de cada escena Sentinel-2 (10 m) en
nueve clases, casi en tiempo real. Se toma la clase más frecuente de cada píxel en los últimos 90 días y en los
mismos 90 días del año anterior, y se cuenta qué parte del lote ocupa cada clase. Sirve para ver lo que pasó en
el lote en la campaña en curso, antes de que salgan los mapas anuales.

Satellite Embedding (Google DeepMind, AlphaEarth Foundations, CC BY 4.0): para cada año y cada píxel de 10 m,
un vector de 64 números que resume todo lo que los satélites vieron ese año (óptico, radar, relieve, clima).
Si el píxel no cambió, el vector de un año se parece mucho al del anterior (similitud cercana a 1). Se calcula
la similitud media del lote año contra año y la parte del lote que cambió mucho (similitud menor a 0,5).
Es un indicador de cambio, no dice qué cambió: para eso están MapBiomas y la cobertura anual.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import research_connectors as c
import vegetation as veg

GEE = veg.GEE
DW = 'GOOGLE/DYNAMICWORLD/V1'
EMB = 'GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL'
DW_CLASSES = [('water', 'Agua', '#419bdf'), ('trees', 'Árboles', '#397d49'), ('grass', 'Pastizal', '#88b053'),
              ('flooded_vegetation', 'Vegetación inundada', '#7a87c6'), ('crops', 'Cultivo', '#e49635'),
              ('shrub_and_scrub', 'Arbustal', '#dfc35a'), ('built', 'Construido', '#c4281b'),
              ('bare', 'Suelo desnudo', '#a59b8f'), ('snow_and_ice', 'Nieve y hielo', '#b39fe1')]
FIRST_EMB_YEAR = 2017
LOW = 0.5


def _f(name, **args):
    return {'functionInvocationValue': {'functionName': name, 'arguments': args}}


def _k(v):
    return {'constantValue': v}


def _geom(pts):
    return _f('GeometryConstructors.Polygon', coordinates=_k(veg.geojson_polygon(pts)['coordinates']), geodesic=_k(False))


def _filtered(cid, start, end):
    coll = _f('Collection.filter', collection=_f('ImageCollection.load', id=_k(cid)),
              filter=_f('Filter.dateRangeContains', leftValue=_f('DateRange', start=_k(start), end=_k(end)),
                        rightField=_k('system:time_start')))
    return _f('Collection.filter', collection=coll,
              filter=_f('Filter.intersects', leftField=_k('.all'), rightValue={'valueReference': 'g'}))


def dw_expression(pts, start, end):
    img = {'argumentReference': '_MAPPING_VAR_0_0'}
    labels = _f('Collection.map', collection=_filtered(DW, start, end),
                baseAlgorithm={'functionDefinitionValue': {'argumentNames': ['_MAPPING_VAR_0_0'], 'body': 'sel'}})
    mode = _f('ImageCollection.mode', collection=labels)
    out = _f('Image.reduceRegion', image=mode, reducer=_f('Reducer.frequencyHistogram'), geometry={'valueReference': 'g'},
             scale=_k(10), maxPixels=_k(1e9))
    return {'expression': {'result': 'out', 'values': {'g': _geom(pts), 'sel': _f('Image.select', input=img, bandSelectors=_k(['label'])),
                                                        'out': out}}}


def emb_expression(pts, year):
    a = _f('ImageCollection.mosaic', collection=_filtered(EMB, f'{year - 1}-01-01', f'{year}-01-01'))
    b = _f('ImageCollection.mosaic', collection=_filtered(EMB, f'{year}-01-01', f'{year + 1}-01-01'))
    dot = _f('Image.rename', input=_f('Image.reduce', image=_f('Image.multiply', image1=a, image2=b), reducer=_f('Reducer.sum')),
             names=_k(['sim']))
    low = _f('Image.rename', input=_f('Image.lt', image1=dot, image2=_f('Image.constant', value=_k(LOW))), names=_k(['low']))
    out = _f('Image.reduceRegion', image=_f('Image.addBands', dstImg=dot, srcImg=low), reducer=_f('Reducer.mean'),
             geometry={'valueReference': 'g'}, scale=_k(10), maxPixels=_k(1e9))
    return {'expression': {'result': 'out', 'values': {'g': _geom(pts), 'out': out}}}


def _compute(proj, tok, body):
    r = c.SESSION.post(f'{GEE}/projects/{proj}/value:compute', json=body, headers={'Authorization': f'Bearer {tok}'}, timeout=55)
    if r.status_code >= 400:
        try:
            msg = (r.json().get('error') or {}).get('message', '')
        except ValueError:
            msg = r.text[:200]
        raise RuntimeError(f'Earth Engine HTTP {r.status_code}: {msg[:160]}')
    return r.json().get('result')


def dw_shares(result):
    """{'label': {'4': n, ...}} → [{key, name, color, pct}] (de mayor a menor, sólo clases presentes)."""
    result = result or {}
    h = result.get('label') or next((v for v in result.values() if isinstance(v, dict)), {})
    tot = sum(h.values()) or 0
    if not tot:
        return []
    rows = []
    for code, n in h.items():
        i = int(float(code))
        if 0 <= i < len(DW_CLASSES):
            k, name, color = DW_CLASSES[i]
            rows.append({'key': k, 'name': name, 'color': color, 'pct': round(100 * n / tot, 1)})
    return sorted(rows, key=lambda r: -r['pct'])


def dynamic_world(polygon, days=90):
    pts = veg.require_polygon(polygon)
    proj, tok = veg.gee_token()
    end = c._now().date(); start = end - timedelta(days=days)
    prev_end, prev_start = end.replace(year=end.year - 1), start.replace(year=start.year - 1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        now = pool.submit(_compute, proj, tok, dw_expression(pts, start.isoformat(), end.isoformat()))
        before = pool.submit(_compute, proj, tok, dw_expression(pts, prev_start.isoformat(), prev_end.isoformat()))
        cur, prev = dw_shares(now.result()), dw_shares(before.result())
    if not cur:
        return c.envelope(None, GEE, 'cobertura reciente del lote · Dynamic World', 'Dynamic World vía Google Earth Engine',
                          'sin dato', f'No hubo escenas Sentinel-2 despejadas sobre el lote en los últimos {days} días.')
    pb = {r['key']: r['pct'] for r in prev}
    for r in cur:
        r['prev_pct'] = pb.get(r['key'])
        r['change_pp'] = None if r['prev_pct'] is None else round(r['pct'] - r['prev_pct'], 1)
    top = cur[0]
    reading = f"En los últimos {days} días predomina {top['name'].lower()} ({top['pct']:.0f} % del lote)"
    if top.get('prev_pct') is not None:
        reading += f"; hace un año, en el mismo período, era el {top['prev_pct']:.0f} %."
    else:
        reading += '.'
    return c.envelope({'period': [start.isoformat(), end.isoformat()], 'previous': [prev_start.isoformat(), prev_end.isoformat()],
                       'classes': cur, 'previous_classes': prev, 'area_ha': veg.area_ha(pts), 'reading': reading,
                       'method': __doc__.split('\n\n')[1].strip()},
                      GEE, 'cobertura reciente del lote · Dynamic World', 'Dynamic World (Google y WRI, CC BY 4.0) vía Google Earth Engine')


def change_reading(rows):
    ok = [r for r in rows if r.get('similarity') is not None]
    if len(ok) < 2:
        return None, None
    sims = sorted(r['similarity'] for r in ok)
    median = sims[len(sims) // 2]
    worst = min(ok, key=lambda r: r['similarity'])
    strong = worst['similarity'] < median - 0.1 or (worst.get('changed_pct') or 0) >= 20
    if strong:
        text = (f"El cambio más fuerte fue entre {worst['year'] - 1} y {worst['year']}: similitud {worst['similarity']:.2f} "
                f"(lo habitual en este lote es {median:.2f}) y {worst['changed_pct']:.0f} % del lote cambió mucho.")
    else:
        text = f"Sin cambios fuertes: año contra año el lote se parece a sí mismo (similitud habitual {median:.2f})."
    return text, worst['year'] if strong else None


def changes(polygon):
    pts = veg.require_polygon(polygon)
    proj, tok = veg.gee_token()
    years = list(range(FIRST_EMB_YEAR + 1, c._now().year))

    def one(y):
        try:
            res = _compute(proj, tok, emb_expression(pts, y)) or {}
        except RuntimeError as e:
            return {'year': y, 'similarity': None, 'changed_pct': None, 'error': str(e)[:120]}
        s, lo = res.get('sim'), res.get('low')
        return {'year': y, 'similarity': None if s is None else round(s, 3), 'changed_pct': None if lo is None else round(100 * lo, 1)}

    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(one, years))
    rows = [r for r in rows if r['similarity'] is not None or r['year'] < years[-1]]   # el último año puede no estar publicado
    text, year = change_reading(rows)
    if text is None:
        return c.envelope(None, GEE, 'cambios del lote año a año · Satellite Embedding', 'Google Earth Engine', 'sin dato',
                          'Earth Engine no devolvió vectores anuales para este lote. ' + '; '.join(r.get('error', '') for r in rows if r.get('error'))[:240])
    return c.envelope({'years': rows, 'reading': text, 'strongest_year': year, 'threshold': LOW, 'area_ha': veg.area_ha(pts),
                       'method': __doc__.split('\n\n')[2].strip()},
                      GEE, 'cambios del lote año a año · Satellite Embedding', 'Google DeepMind AlphaEarth (CC BY 4.0) vía Google Earth Engine')
