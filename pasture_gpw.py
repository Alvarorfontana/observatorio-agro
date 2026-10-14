"""pasture_gpw v1.0 — productividad del pasto del lote año por año, 2000 en adelante (Global Pasture Watch, CC BY 4.0).

Fuente: Land & Carbon Lab · Global Pasture Watch, producto anual de productividad primaria bruta sin calibrar
(uGPP, gC/m²/año, 30 m, Landsat + MODIS), asset `projects/global-pasture-watch/assets/ggpp-30m/v1/ugpp_m`.
DOTS promedia los píxeles del lote para cada año (Google Earth Engine) y compara cada año con el promedio del período.
Como el producto no está calibrado, se usa para comparar años entre sí y no como kilos de pasto absolutos.

Rangos de lectura (año contra el promedio del lote): más de +15 % muy bueno · +5 a +15 % bueno ·
−5 a +5 % normal · −15 a −5 % flojo · menos de −15 % malo.
"""
import vegetation as veg
import research_connectors as c

ASSET = 'projects/global-pasture-watch/assets/ggpp-30m/v1/ugpp_m'


def _f(name, **args):
    return {'functionInvocationValue': {'functionName': name, 'arguments': args}}


def _k(v):
    return {'constantValue': v}


def expression(pts):
    ring = veg.geojson_polygon(pts)['coordinates']
    geom = _f('GeometryConstructors.Polygon', coordinates=_k(ring), geodesic=_k(False))
    img = {'argumentReference': '_MAPPING_VAR_0_0'}
    stats = _f('Image.reduceRegion', image=_f('Image.select', input=img, bandSelectors=_k(['gc_m2'])),
               reducer=_f('Reducer.mean'), geometry={'valueReference': 'g'}, scale=_k(30), maxPixels=_k(1e9))
    body = _f('Feature', geometry=_k(None), metadata={'dictionaryValue': {'values': {
        't': _f('Element.get', object=img, property=_k('system:time_start')),
        'gpp': _f('Dictionary.get', dictionary=stats, key=_k('gc_m2'))}}})
    out = _f('Collection.map', collection=_f('ImageCollection.load', id=_k(ASSET)),
             baseAlgorithm={'functionDefinitionValue': {'argumentNames': ['_MAPPING_VAR_0_0'], 'body': 'body'}})
    return {'expression': {'result': 'out', 'values': {'g': geom, 'body': body, 'out': out}}}


def classify(pct):
    if pct is None:
        return 'sin dato'
    return 'muy bueno' if pct > 15 else 'bueno' if pct > 5 else 'normal' if pct >= -5 else 'flojo' if pct >= -15 else 'malo'


def summarize(rows):
    rows = sorted([r for r in rows if r.get('gpp') is not None], key=lambda r: r['year'])
    if len(rows) < 5:
        raise ValueError('Global Pasture Watch devolvió muy pocos años para el lote')
    mean = sum(r['gpp'] for r in rows) / len(rows)
    for r in rows:
        r['gpp'] = round(r['gpp'])
        r['vs_mean_pct'] = round((r['gpp'] / mean - 1) * 100) if mean else None
        r['class'] = classify(r['vs_mean_pct'])
    last = rows[-1]
    rank = sorted(rows, key=lambda r: -r['gpp']).index(last) + 1
    best = sorted(rows, key=lambda r: -r['gpp'])[:3]
    worst = sorted(rows, key=lambda r: r['gpp'])[:3]
    half = len(rows) // 2
    trend = round((sum(r['gpp'] for r in rows[half:]) / len(rows[half:]) / (sum(r['gpp'] for r in rows[:half]) / half) - 1) * 100) if half else None
    return {'years': rows, 'mean_gc_m2': round(mean), 'last': last, 'rank_last': rank, 'n': len(rows),
            'best': best, 'worst': worst, 'trend_pct': trend,
            'ranges': [['más de +15 %', 'muy bueno'], ['+5 a +15 %', 'bueno'], ['−5 a +5 %', 'normal'], ['−15 a −5 %', 'flojo'], ['menos de −15 %', 'malo']],
            'reading': (f"{last['year']} fue un año {last['class']} para el pasto del lote ({last['vs_mean_pct']:+d} % contra su promedio "
                        f"{rows[0]['year']}-{last['year']}), el {rank}.º de {len(rows)}. "
                        + (f"La segunda mitad del período produjo {trend:+d} % que la primera." if trend is not None else ''))}


def history(polygon):
    pts = veg.require_polygon(polygon)
    proj, tok = veg.gee_token()
    url = f'{veg.GEE}/projects/{proj}/value:compute'
    r = c.SESSION.post(url, json=expression(pts), headers={'Authorization': f'Bearer {tok}'}, timeout=50)
    if r.status_code >= 400:
        try:
            msg = (r.json().get('error') or {}).get('message', '')
        except ValueError:
            msg = r.text[:200]
        return c.envelope(None, veg.GEE, 'productividad del pasto 2000-2024', 'Global Pasture Watch', 'sin dato', f'Earth Engine HTTP {r.status_code}: {msg[:200]}')
    from datetime import datetime, timezone
    rows = []
    for f in (r.json().get('result') or {}).get('features') or []:
        p = f.get('properties') or {}
        if p.get('t') is None or p.get('gpp') is None:
            continue
        rows.append({'year': datetime.fromtimestamp(p['t'] / 1000, timezone.utc).year, 'gpp': p['gpp']})
    data = summarize(rows)
    data['method'] = __doc__.split('\n\n', 1)[1].strip()
    data['unit'] = 'gC/m²/año (sin calibrar)'
    return c.envelope(data, url.replace(proj, '{PROJECT}'), 'productividad del pasto del lote desde 2000',
                      'Land & Carbon Lab · Global Pasture Watch (CC BY 4.0) vía Google Earth Engine')
