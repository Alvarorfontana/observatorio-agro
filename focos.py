"""focos v1.0 — focos de calor en el sur de Sudamérica, con contexto (NASA FIRMS, cuatro satélites).

Detecciones casi en tiempo real (NRT) de NASA FIRMS / LANCE: MODIS (Terra y Aqua, 1 km) y VIIRS (Suomi NPP, NOAA-20 y
NOAA-21, 375 m), de 1 a 5 días, para Argentina, Uruguay, Paraguay, Chile, Bolivia y el sur de Brasil. Cada foco se
ubica en su país y provincia o estado (límites de Natural Earth, simplificados a ~2 km) y, cuando Earth Engine
responde, se le agrega la cobertura del suelo donde cayó (ESA WorldCover 10 m, 2021) y si está dentro de un área
protegida (WDPA, UNEP-WCMC). Un foco es una anomalía térmica: puede ser un incendio, una quema agrícola o una
fuente industrial. Los datos NRT son preliminares y pueden tener errores de detección.

Eventos de los próximos 5 días en las localidades del monitor (pronóstico de modelos globales vía Open-Meteo): peligro
de incendio (máxima de 30 °C o más, humedad mínima de 30 % o menos y viento de 25 km/h o más, sin lluvia: la regla del
30-30-30 de los brigadistas), heladas (mínima de 0 °C o menos), nevadas (1 cm o más), calor extremo (38 °C o más) y
lluvia fuerte (50 mm o más en un día).
"""
import csv
import io
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import research_connectors as c

FIRMS = 'https://firms.modaps.eosdis.nasa.gov/api/area/csv/{KEY}/{SRC}/{BBOX}/{DAYS}'
BBOX = (-76.0, -56.0, -43.0, -14.0)   # oeste, sur, este, norte
SOURCES = [('MODIS_NRT', 'MODIS (Terra/Aqua)'), ('VIIRS_SNPP_NRT', 'VIIRS Suomi NPP'),
           ('VIIRS_NOAA20_NRT', 'VIIRS NOAA-20'), ('VIIRS_NOAA21_NRT', 'VIIRS NOAA-21')]
COUNTRIES = {'ARG': 'Argentina', 'URY': 'Uruguay', 'PRY': 'Paraguay', 'BRA': 'Brasil', 'BOL': 'Bolivia', 'CHL': 'Chile'}
WORLDCOVER = {10: 'Árboles', 20: 'Arbustal', 30: 'Pastizal', 40: 'Cultivo', 50: 'Urbano', 60: 'Suelo desnudo',
              70: 'Nieve y hielo', 80: 'Agua', 90: 'Humedal', 95: 'Manglar', 100: 'Musgos y líquenes'}
PROV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'provincias_sur.json')
MAX_ENRICH = 1500
_CACHE = {}
_PROV = None


def provinces():
    global _PROV
    if _PROV is None:
        with open(PROV_PATH, encoding='utf-8') as f:
            raw = json.load(f)
        _PROV = []
        for r in raw:
            xs = [x for poly in r['p'] for x, _ in poly[0]]; ys = [y for poly in r['p'] for _, y in poly[0]]
            _PROV.append((r['c'], r['n'], r['p'], (min(xs), min(ys), max(xs), max(ys))))
    return _PROV


def _in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]; xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def locate(lat, lon):
    for code, name, polys, (w, s, e, n) in provinces():
        if not (w <= lon <= e and s <= lat <= n):
            continue
        for poly in polys:
            if _in_ring(lon, lat, poly[0]) and not any(_in_ring(lon, lat, h) for h in poly[1:]):
                return COUNTRIES.get(code, code), name
    return None, None


def parse_csv(text, source_label):
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        try:
            la, lo = float(r['latitude']), float(r['longitude'])
        except (KeyError, ValueError, TypeError):
            continue
        conf = (r.get('confidence') or '').strip()
        conf = {'l': 'baja', 'n': 'nominal', 'h': 'alta'}.get(conf.lower(), conf)
        try:
            frp = round(float(r.get('frp') or 0), 1)
        except ValueError:
            frp = None
        t = (r.get('acq_time') or '').zfill(4)
        rows.append({'lat': round(la, 4), 'lon': round(lo, 4), 'date': r.get('acq_date'), 'time': f'{t[:2]}:{t[2:]}',
                     'sat': source_label, 'conf': conf, 'frp': frp, 'dn': 'día' if r.get('daynight') == 'D' else 'noche'})
    return rows


def fetch(days):
    key = os.environ.get('FIRMS_MAP_KEY')
    if not key:
        raise PermissionError('requiere credencial: FIRMS_MAP_KEY')
    bbox = ','.join(str(v) for v in BBOX)

    def one(src):
        code, label = src
        url = FIRMS.format(KEY=key, SRC=code, BBOX=bbox, DAYS=days)
        try:
            r = c.SESSION.get(url, timeout=40)
            r.raise_for_status()
            return code, parse_csv(r.text, label), None
        except Exception as e:
            return code, [], type(e).__name__
    with ThreadPoolExecutor(max_workers=4) as pool:
        res = list(pool.map(one, SOURCES))
    rows = [x for _, rs, _ in res for x in rs]
    errors = {code: err for code, _, err in res if err}
    return rows, errors


def _f(name, **args):
    return {'functionInvocationValue': {'functionName': name, 'arguments': args}}


def _k(v):
    return {'constantValue': v}


def enrich_expression(points):
    feats = [_f('Feature', geometry=_f('GeometryConstructors.Point', coordinates=_k([p['lon'], p['lat']])), metadata=_k({'i': i}))
             for i, p in points]
    fc = _f('Collection', features={'arrayValue': {'values': feats}})
    wc = _f('Image.rename', input=_f('Image.select', input=_f('ImageCollection.mosaic', collection=_f('ImageCollection.load', id=_k('ESA/WorldCover/v200'))),
                                       bandSelectors=_k(['Map'])), names=_k(['cover']))
    wdpa = _f('Image.rename', input=_f('FeatureCollection.reduceToImage', collection=_f('FeatureCollection.load', id=_k('WCMC/WDPA/current/polygons')),
                                      properties=_k(['WDPAID']), reducer=_f('Reducer.first')), names=_k(['wdpa']))
    img = _f('Image.addBands', dstImg=wc, srcImg=wdpa)
    out = _f('Image.sampleRegions', image=img, collection=fc, properties=_k(['i']), scale=_k(30), geometries=_k(False))
    return {'expression': {'result': 'out', 'values': {'out': out}}}


def enrich(rows):
    """Cobertura y área protegida para los focos más intensos (Earth Engine). Devuelve un mensaje si no pudo."""
    import vegetation as veg
    try:
        proj, tok = veg.gee_token()
    except Exception as e:
        return f'Earth Engine no disponible ({type(e).__name__})'
    order = sorted(range(len(rows)), key=lambda i: -(rows[i]['frp'] or 0))[:MAX_ENRICH]
    body = enrich_expression([(i, rows[i]) for i in order])
    r = c.SESSION.post(f'{veg.GEE}/projects/{proj}/value:compute', json=body, headers={'Authorization': f'Bearer {tok}'}, timeout=45)
    if r.status_code >= 400:
        try:
            msg = (r.json().get('error') or {}).get('message', '')
        except ValueError:
            msg = r.text[:200]
        return f'Earth Engine HTTP {r.status_code}: {msg[:200]}'
    for f in (r.json().get('result') or {}).get('features') or []:
        p = f.get('properties') or {}
        i = p.get('i')
        if i is None or not 0 <= int(i) < len(rows):
            continue
        cv = p.get('cover')
        rows[int(i)]['cover'] = WORLDCOVER.get(int(cv)) if cv is not None else None
        rows[int(i)]['protected'] = p.get('wdpa') is not None
    return None


def danger():
    """Próximos 5 días en 80 localidades: peligro de incendio (30-30-30), heladas, nevadas, calor extremo y lluvia fuerte."""
    import enso_sa
    w, s_, e, n = BBOX
    pts = [p for p in enso_sa.PLACES if w <= p[4] <= e and s_ <= p[3] <= n]
    r = c.SESSION.get('https://api.open-meteo.com/v1/forecast', timeout=30, params={
        'latitude': ','.join(f'{p[3]:.2f}' for p in pts), 'longitude': ','.join(f'{p[4]:.2f}' for p in pts),
        'daily': 'temperature_2m_max,temperature_2m_min,relative_humidity_2m_min,wind_speed_10m_max,precipitation_sum,snowfall_sum',
        'forecast_days': 5, 'timezone': 'UTC'})
    r.raise_for_status()
    js = r.json(); js = js if isinstance(js, list) else [js]
    out = []
    for p, d in zip(pts, js):
        d = d.get('daily') or {}
        t = d.get('time') or []
        col = lambda k: d.get(k) or [None] * len(t)
        tx, tn, hn, wv, pr, sn = (col(k) for k in ('temperature_2m_max', 'temperature_2m_min', 'relative_humidity_2m_min',
                                                    'wind_speed_10m_max', 'precipitation_sum', 'snowfall_sum'))
        ev = {'incendio': [], 'helada': [], 'nevada': [], 'calor': [], 'lluvia': []}
        for i, day in enumerate(t):
            if None not in (tx[i], hn[i], wv[i]) and tx[i] >= 30 and hn[i] <= 30 and wv[i] >= 25 and (pr[i] or 0) < 1:
                ev['incendio'].append(day)
            if tn[i] is not None and tn[i] <= 0:
                ev['helada'].append(day)
            if (sn[i] or 0) >= 1:
                ev['nevada'].append(day)
            if tx[i] is not None and tx[i] >= 38:
                ev['calor'].append(day)
            if (pr[i] or 0) >= 50:
                ev['lluvia'].append(day)
        out.append({'id': p[0], 'name': p[1], 'country': p[2], 'lat': p[3], 'lon': p[4], 'days': ev['incendio'], 'events': ev,
                    'tmin': min((v for v in tn if v is not None), default=None), 'tmax': max((v for v in tx if v is not None), default=None),
                    'snow_cm': round(sum(v or 0 for v in sn), 1), 'rain_mm': round(sum(v or 0 for v in pr))})
    return out


def summarize(rows):
    by = {}
    for r in rows:
        k = (r.get('country') or 'Sin ubicar', r.get('province') or 'Sin ubicar')
        b = by.setdefault(k, {'country': k[0], 'province': k[1], 'count': 0, 'frp': 0.0, 'protected': 0, 'cover': {}})
        b['count'] += 1; b['frp'] += r['frp'] or 0
        if r.get('protected'):
            b['protected'] += 1
        if r.get('cover'):
            b['cover'][r['cover']] = b['cover'].get(r['cover'], 0) + 1
    out = sorted(by.values(), key=lambda b: -b['count'])
    for b in out:
        b['frp'] = round(b['frp'])
        b['top_cover'] = max(b['cover'], key=b['cover'].get) if b['cover'] else None
    return out


def reading(rows, prov, days):
    if not rows:
        return f'Sin focos de calor detectados en los últimos {days} días en la región.'
    top = prov[0]
    txt = f"{len(rows)} focos en los últimos {days} {'día' if days == 1 else 'días'}. La mayor concentración está en {top['province']} ({top['country']}): {top['count']} focos"
    if top.get('top_cover'):
        txt += f", sobre todo en {top['top_cover'].lower()}"
    txt += '.'
    prot = sum(1 for r in rows if r.get('protected'))
    if prot:
        txt += f' {prot} cayeron dentro de áreas protegidas.'
    return txt


def analyze(days=2):
    days = max(1, min(5, int(days)))
    hit = _CACHE.get(days)
    if hit and time.monotonic() - hit[0] < 1800:
        return hit[1]
    with ThreadPoolExecutor(max_workers=2) as pool:
        fz = pool.submit(danger)
        rows, errors = fetch(days)
        for r in rows:
            r['country'], r['province'] = locate(r['lat'], r['lon'])
        rows = [r for r in rows if r['country']]          # fuera del recorte (mar, otros países)
        ee_note = enrich(rows) if rows else None
        try:
            dz = fz.result(timeout=30)
        except Exception as e:
            dz = None; errors['peligro'] = type(e).__name__
    rows.sort(key=lambda r: (r['date'] or '', r['time']), reverse=True)
    prov = summarize(rows)
    try:
        import datastore
        hist = history_compare(datastore.load('focos_historia.json'))
    except Exception:
        hist = None
    data = {'history': hist, 'days': days, 'count': len(rows), 'points': rows, 'by_province': prov, 'danger': dz, 'reading': reading(rows, prov, days),
            'sources': [l for _, l in SOURCES], 'errors': errors, 'enrichment_note': ee_note,
            'enriched': sum(1 for r in rows if 'cover' in r), 'method': __doc__.split('\n\n', 1)[1].strip()}
    env = c.envelope(data, 'https://firms.modaps.eosdis.nasa.gov/api/area/', 'focos de calor en el sur de Sudamérica',
                     'NASA FIRMS / LANCE · ESA WorldCover · WDPA · Natural Earth', 'recibido' if rows or not errors else 'sin dato',
                     None if rows or not errors else 'FIRMS no respondió: ' + ', '.join(errors))
    _CACHE[days] = (time.monotonic(), env)
    return env


def history_compare(hist, today=None):
    """Mes anterior completo y mes en curso contra el promedio del mismo mes en años previos (desde 2001)."""
    months = (hist or {}).get('months') or {}
    if not months:
        return None
    today = today or c._now().date()
    first = today.replace(day=1)
    prev = (first - timedelta(days=1)).strftime('%Y-%m')
    cur = today.strftime('%Y-%m')
    frac = today.day / 30.4

    def table(kind, month, scale):
        mm = month[5:]
        past = [k for k in months if k[5:] == mm and k < month]
        if len(past) < 5:
            return []
        keys = set(k for p in past for k in months[p].get(kind, {})) | set(months.get(month, {}).get(kind, {}))
        rows = []
        for k in keys:
            avg = sum(months[p].get(kind, {}).get(k, 0) for p in past) / len(past) * scale
            n = months.get(month, {}).get(kind, {}).get(k, 0)
            a, b = k.split('|', 1)
            rows.append({'a': a, 'b': b, 'count': n, 'normal': round(avg, 1), 'ratio': round(n / avg, 2) if avg >= 1 else None})
        return sorted(rows, key=lambda r: -r['count'])
    return {'previous_month': prev, 'current_month': cur, 'years': len({k[:4] for k in months}),
            'provinces_prev': table('prov', prev, 1)[:40], 'provinces_cur': table('prov', cur, frac)[:40],
            'departments_prev': table('dep', prev, 1)[:60], 'updated': hist.get('updated')}


def to_csv(rows):
    buf = io.StringIO()
    cols = ['lat', 'lon', 'date', 'time', 'sat', 'conf', 'frp', 'dn', 'country', 'province', 'cover', 'protected']
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction='ignore')
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue()
