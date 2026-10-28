"""mapbiomas v1.0 — historia del uso del suelo de un lote, año por año desde 1985 (MapBiomas, CC BY 4.0).

MapBiomas es una red de universidades, ONG y empresas de cada país que clasifica imágenes Landsat (30 m) en clases
de cobertura y uso: bosque, sabana, pastizal, pastura, agricultura, plantación forestal, humedal, agua, urbano.
Se consulta con Google Earth Engine (REST) sobre los assets públicos `projects/mapbiomas-public/assets/<país>`:
se cuentan los píxeles de cada clase dentro del lote en cada año. El asset de cada país se busca solo
(se puede fijar con la variable MAPBIOMAS_ASSET_<PAIS>, p. ej. MAPBIOMAS_ASSET_ARGENTINA).

Para la UE (EUDR): bosque en 2020 (año de corte) contra el último año, y qué pasó con lo que era bosque.
Es un mapa satelital, no una inspección: sirve como evidencia técnica para la debida diligencia.
"""
import os
import re
import time

import research_connectors as c
import vegetation as veg

GEE = veg.GEE
ROOT = 'projects/mapbiomas-public/assets'
CUTOFF = 2020

# Leyenda común de la red MapBiomas (códigos compartidos entre países; los nombres siguen las leyendas oficiales)
CLASSES = {
    1: ('Bosque', '#1f8d49', 'bosque'), 3: ('Bosque cerrado / formación forestal', '#1f8d49', 'bosque'),
    4: ('Bosque abierto / sabana', '#7dc975', 'bosque'), 5: ('Manglar', '#04381d', 'bosque'),
    6: ('Bosque inundable', '#007785', 'bosque'), 49: ('Vegetación leñosa de arenales', '#02d659', 'bosque'),
    45: ('Matorral', '#6a9c32', 'natural'), 66: ('Matorral', '#a89358', 'natural'),
    9: ('Plantación forestal', '#7a5900', 'plantacion'),
    10: ('Vegetación herbácea y arbustiva', '#d6bc74', 'natural'), 11: ('Humedal / pantano', '#519799', 'natural'),
    12: ('Pastizal natural', '#d6bc74', 'natural'), 13: ('Otra formación natural', '#d89f5c', 'natural'),
    63: ('Estepa', '#ebf8b5', 'natural'), 50: ('Vegetación herbácea de arenales', '#ad5100', 'natural'),
    14: ('Agropecuaria', '#ffefc3', 'uso'), 15: ('Pastura implantada', '#edde8e', 'uso'), 18: ('Agricultura', '#e974ed', 'uso'),
    19: ('Cultivo temporal', '#c27ba0', 'uso'), 20: ('Caña de azúcar', '#db7093', 'uso'), 21: ('Mosaico agropecuario', '#ffefc3', 'uso'),
    36: ('Cultivo perenne', '#d082de', 'uso'), 39: ('Soja', '#f5b3c8', 'uso'), 40: ('Arroz', '#c71585', 'uso'),
    41: ('Otros cultivos temporales', '#f54ca9', 'uso'), 46: ('Café', '#d68fe2', 'uso'), 47: ('Cítricos', '#9932cc', 'uso'),
    48: ('Otros cultivos perennes', '#e6ccff', 'uso'), 62: ('Algodón', '#ff69b4', 'uso'), 35: ('Palma aceitera', '#9065d0', 'uso'),
    22: ('Área sin vegetación', '#d4271e', 'otro'), 23: ('Playa y médano', '#ffa07a', 'otro'), 24: ('Área urbana', '#d4271e', 'otro'),
    25: ('Otra área sin vegetación', '#db4d4f', 'otro'), 29: ('Afloramiento rocoso', '#ffaa5f', 'otro'), 30: ('Minería', '#9c0027', 'otro'),
    61: ('Salar', '#f5d5d5', 'otro'), 68: ('Otra área natural sin vegetación', '#e97a7a', 'otro'),
    26: ('Agua', '#2532e4', 'agua'), 33: ('Río, laguna y mar', '#2532e4', 'agua'), 31: ('Acuicultura', '#091077', 'agua'),
    27: ('No observado', '#ffffff', 'otro'),
}
GROUPS = {'bosque': 'Bosque nativo', 'natural': 'Otra vegetación natural', 'plantacion': 'Plantación forestal',
          'uso': 'Agricultura y pasturas', 'agua': 'Agua', 'otro': 'Urbano y otros'}
GROUP_COLORS = {'bosque': '#1f8d49', 'natural': '#b8af4f', 'plantacion': '#7a5900', 'uso': '#e974ed', 'agua': '#2532e4', 'otro': '#d4271e'}

# países por caja aproximada (oeste, sur, este, norte); se prueba en orden y se queda con el primero que tenga píxeles
COUNTRIES = [('argentina', (-73.6, -55.1, -53.6, -21.8)), ('brazil', (-74.0, -33.8, -34.7, 5.3)),
             ('paraguay', (-62.7, -27.6, -54.2, -19.3)), ('uruguay', (-58.5, -35.0, -53.1, -30.0)),
             ('bolivia', (-69.7, -22.9, -57.4, -9.6)), ('chile', (-75.7, -56.0, -66.4, -17.5)),
             ('peru', (-81.4, -18.4, -68.6, -0.03)), ('colombia', (-79.0, -4.3, -66.8, 12.5)),
             ('ecuador', (-81.1, -5.0, -75.2, 1.5)), ('venezuela', (-73.4, 0.6, -59.8, 12.2))]

_ASSET = {}


def countries_for(lon, lat):
    return [n for n, (w, s, e, nn) in COUNTRIES if w <= lon <= e and s <= lat <= nn]


def _list(tok, parent):
    r = c.SESSION.get(f'{GEE}/{parent}:listAssets', headers={'Authorization': f'Bearer {tok}'}, params={'pageSize': 200}, timeout=20)
    if r.status_code >= 400:
        return []
    return r.json().get('assets') or []


def _score(a):
    """Elige el asset de cobertura más nuevo: prefiere 'lulc'/'coverage'/'integration' y la colección más alta."""
    name = a.get('name', '').lower()
    if a.get('type') not in ('IMAGE', 'IMAGE_COLLECTION'):
        return None
    if any(w in name for w in ('transition', 'deforest', 'loss', 'perdida', 'secondary', 'secundaria', 'fire', 'fuego', 'water', 'agua', 'quality', 'pasture_quality', 'mosaic')):
        return None
    if not any(w in name for w in ('lulc', 'coverage', 'integration', 'cobertura', 'classification')):
        return None
    nums = [int(n) for n in re.findall(r'collection[_\-]?0*(\d+)', name)] + [int(n) for n in re.findall(r'col(?:eccion)?[_\-]?0*(\d+)', name)]
    v = [int(n) for n in re.findall(r'/v(\d+)$', name)]
    return (1 if a.get('type') == 'IMAGE_COLLECTION' else 0, max(nums) if nums else 0, max(v) if v else 0, name)


def find_asset(tok, country):
    env = os.environ.get(f'MAPBIOMAS_ASSET_{country.upper()}')
    if env:
        kind = 'IMAGE_COLLECTION' if env.endswith('/v1') or '/lulc/' in env else 'IMAGE'
        return {'name': env, 'type': os.environ.get(f'MAPBIOMAS_TYPE_{country.upper()}', kind)}
    hit = _ASSET.get(country)
    if hit and time.monotonic() - hit[0] < 86400:
        return hit[1]
    found, queue, seen = [], [f'{ROOT}/{country}'], 0
    while queue and seen < 40:
        parent = queue.pop(0); seen += 1
        for a in _list(tok, parent):
            if a.get('type') == 'FOLDER':
                queue.append(a['name'])
            elif _score(a):
                found.append(a)
    best = max(found, key=_score) if found else None
    if best:                     # si Earth Engine no respondió (cuota, límite), no se recuerda el «no hay» por un día
        _ASSET[country] = (time.monotonic(), best)
    return best


def _f(name, **args):
    return {'functionInvocationValue': {'functionName': name, 'arguments': args}}


def _k(v):
    return {'constantValue': v}


def expression(asset, pts):
    ring = veg.geojson_polygon(pts)['coordinates']
    geom = _f('GeometryConstructors.Polygon', coordinates=_k(ring), geodesic=_k(False))
    if asset['type'] == 'IMAGE_COLLECTION':
        img = {'argumentReference': '_MAPPING_VAR_0_0'}
        hist = _f('Image.reduceRegion', image=_f('Image.select', input=img, bandSelectors=_k([0])),
                  reducer=_f('Reducer.frequencyHistogram'), geometry={'valueReference': 'g'}, scale=_k(30), maxPixels=_k(1e9))
        body = _f('Feature', geometry=_k(None), metadata={'dictionaryValue': {'values': {
            'props': _f('Element.toDictionary', element=img), 'hist': hist}}})
        out = _f('Collection.map', collection=_f('ImageCollection.load', id=_k(asset['name'])),
                 baseAlgorithm={'functionDefinitionValue': {'argumentNames': ['_MAPPING_VAR_0_0'], 'body': 'body'}})
        return {'expression': {'result': 'out', 'values': {'g': geom, 'body': body, 'out': out}}}
    out = _f('Image.reduceRegion', image=_f('Image.load', id=_k(asset['name'])), reducer=_f('Reducer.frequencyHistogram'),
             geometry={'valueReference': 'g'}, scale=_k(30), maxPixels=_k(1e9))
    return {'expression': {'result': 'out', 'values': {'g': geom, 'out': out}}}


def _year_of(props, band=None):
    for k in ('year', 'año', 'ano', 'YEAR'):
        if props.get(k) is not None:
            try:
                return int(props[k])
            except (TypeError, ValueError):
                pass
    m = re.search(r'(19|20)\d{2}', str(band or props.get('system:index') or ''))
    return int(m.group(0)) if m else None


def parse(result, asset):
    """→ {año: {código: píxeles}} quedándose, por año, con la colección/versión más nueva."""
    years, rank = {}, {}
    if asset['type'] == 'IMAGE_COLLECTION':
        for f in (result or {}).get('features') or []:
            p = f.get('properties') or {}
            props, hist = p.get('props') or {}, p.get('hist') or {}
            h = next(iter(hist.values()), None) if hist else None
            y = _year_of(props)
            if not y or not h:
                continue
            r = (float(props.get('collection_id') or props.get('collection') or 0), str(props.get('version') or props.get('versión') or ''))
            if y not in rank or r > rank[y]:
                rank[y] = r
                years[y] = {int(float(k)): v for k, v in h.items()}
    else:
        for band, h in (result or {}).items():
            y = _year_of({}, band)
            if y and h:
                years[y] = {int(float(k)): v for k, v in h.items()}
    return years


def summarize(years, area_ha, country, asset_name):
    rows = []
    for y in sorted(years):
        tot = sum(years[y].values()) or 1
        groups = {g: 0.0 for g in GROUPS}
        classes = {}
        for code, n in years[y].items():
            g = CLASSES.get(code, (None, None, 'otro'))[2]
            groups[g] += n / tot
            classes[code] = round(n / tot * 100, 1)
        rows.append({'year': y, 'groups_pct': {g: round(v * 100, 1) for g, v in groups.items()},
                     'groups_ha': {g: round(v * area_ha, 1) for g, v in groups.items()}, 'classes_pct': classes})
    if not rows:
        return None
    by = {r['year']: r for r in rows}
    last = rows[-1]
    base = by.get(CUTOFF)
    first = rows[0]
    out = {'country': country, 'asset': asset_name, 'area_ha': round(area_ha, 1), 'years': rows,
           'first_year': first['year'], 'last_year': last['year'],
           'legend': [{'code': k, 'name': CLASSES.get(k, (f'Clase {k}',))[0], 'color': CLASSES.get(k, (None, '#98a2b3'))[1]}
                      for k in sorted({k for r in rows for k in r['classes_pct']})],
           'groups': [{'key': g, 'name': n, 'color': GROUP_COLORS[g]} for g, n in GROUPS.items()]}
    # EUDR: bosque nativo 2020 → último año
    if base:
        b, l = base['groups_ha']['bosque'], last['groups_ha']['bosque']
        loss = round(max(0.0, b - l), 1)
        out['eudr'] = {'cutoff': CUTOFF, 'forest_cutoff_ha': b, 'forest_last_ha': l, 'forest_last_year': last['year'],
                       'loss_ha': loss, 'change_pp': round(last['groups_pct']['bosque'] - base['groups_pct']['bosque'], 1),
                       'verdict': ('sin pérdida de bosque nativo después de 2020' if loss < 0.5 or b - l < 0.01 * area_ha else
                                   f'posible pérdida de {loss:.1f} ha de bosque nativo después de 2020')}
    # historia larga
    out['since_first'] = {g: round(last['groups_ha'][g] - first['groups_ha'][g], 1) for g in GROUPS}
    fb = first['groups_ha']['bosque']
    out['reading'] = (f"Entre {first['year']} y {last['year']} el bosque nativo del lote pasó de {fb:.1f} a {last['groups_ha']['bosque']:.1f} ha "
                      f"y la agricultura y pasturas de {first['groups_ha']['uso']:.1f} a {last['groups_ha']['uso']:.1f} ha.")
    return out


def history(polygon):
    pts = veg.require_polygon(polygon)
    area = veg.area_ha(pts)
    lat = sum(p[0] for p in pts) / len(pts); lon = sum(p[1] for p in pts) / len(pts)   # vértices [lat, lon]
    proj, tok = veg.gee_token()
    tried = []
    for country in countries_for(lon, lat) or ['argentina', 'brazil']:
        asset = find_asset(tok, country)
        if not asset:
            tried.append(f'{country}: sin asset'); continue
        url = f'{GEE}/projects/{proj}/value:compute'
        r = c.SESSION.post(url, json=expression(asset, pts), headers={'Authorization': f'Bearer {tok}'}, timeout=55)
        if r.status_code >= 400:
            try:
                msg = (r.json().get('error') or {}).get('message', '')
            except ValueError:
                msg = r.text[:200]
            tried.append(f"{country}: HTTP {r.status_code} {msg[:120]}"); continue
        years = parse(r.json().get('result'), asset)
        if not years:
            tried.append(f'{country}: sin píxeles en el lote'); continue
        data = summarize(years, area, country, asset['name'])
        data['method'] = __doc__.split('\n\n', 1)[1].strip()
        return c.envelope(data, url.replace(proj, '{PROJECT}'), 'uso del suelo del lote desde 1985 · MapBiomas',
                          'MapBiomas (CC BY 4.0) vía Google Earth Engine')
    return c.envelope(None, GEE, 'uso del suelo del lote desde 1985 · MapBiomas', 'MapBiomas vía Google Earth Engine',
                      'sin dato', 'MapBiomas no devolvió datos para este lote. ' + ' · '.join(tried)[:400])
