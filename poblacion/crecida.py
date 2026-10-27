"""Personas que viven cerca del río, por franja de altura sobre el agua (Google Earth Engine).

Para cada localidad ribereña de las alertas de DOTS se toma un círculo de 15 km alrededor y se suma la población
que vive a 1, 2, 3, 5 y 10 metros o menos por encima del curso de agua más cercano:
  - Altura sobre el drenaje (HAND): MERIT Hydro v1.0.1, banda `hnd`, 90 m (Yamazaki et al., 2019).
  - Población: WorldPop Global Project Population Data 2020, 100 m (personas por píxel); edades del producto
    por edad y sexo (menores de 5 años y de 65 o más).
Escenarios: si el río sube hasta el nivel de alerta o de evacuación, se aproxima la franja afectada con la diferencia
entre ese nivel y el de aguas bajas de la escala del INA. Es una aproximación de exposición, no un modelo hidráulico:
no considera defensas, terraplenes ni el tiempo que dura la crecida.
"""
import vegetation as veg
import research_connectors as c

BANDS_T = (1, 2, 3, 5, 10)
RADIUS_M = 15000
POP = 'WorldPop/GP/100m/pop'
AGE = 'WorldPop/GP/100m/pop_age_sex'
HAND = 'MERIT/Hydro/v1_0_1'
UNDER5 = ['M_0', 'F_0', 'M_1', 'F_1']
OVER65 = ['M_65', 'F_65', 'M_70', 'F_70', 'M_75', 'F_75', 'M_80', 'F_80']


def _f(name, **args):
    return {'functionInvocationValue': {'functionName': name, 'arguments': args}}


def _k(v):
    return {'constantValue': v}


def _mosaic(cid, year=2020):
    coll = _f('Collection.filter', collection=_f('ImageCollection.load', id=_k(cid)),
              filter=_f('Filter.equals', leftField=_k('year'), rightValue=_k(year)))
    return _f('ImageCollection.mosaic', collection=coll)


def expression(lat, lon, radius=RADIUS_M):
    geom = _f('Geometry.buffer', geometry=_f('GeometryConstructors.Point', coordinates=_k([lon, lat])), distance=_k(radius))
    hand = _f('Image.select', input=_f('Image.load', id=_k(HAND)), bandSelectors=_k(['hnd']))
    pop = _f('Image.select', input=_mosaic(POP), bandSelectors=_k(['population']))
    age = _mosaic(AGE)
    u5 = _f('Image.reduce', image=_f('Image.select', input=age, bandSelectors=_k(UNDER5)), reducer=_f('Reducer.sum'))
    o65 = _f('Image.reduce', image=_f('Image.select', input=age, bandSelectors=_k(OVER65)), reducer=_f('Reducer.sum'))
    img = _f('Image.rename', input=pop, names=_k(['total']))
    img = _f('Image.addBands', dstImg=img, srcImg=_f('Image.rename', input=u5, names=_k(['u5_total'])))
    img = _f('Image.addBands', dstImg=img, srcImg=_f('Image.rename', input=o65, names=_k(['o65_total'])))
    for t in BANDS_T:
        m = _f('Image.lte', image1=hand, image2=_f('Image.constant', value=_k(t)))
        for src, name in ((pop, f'pop_le{t}'), (u5, f'u5_le{t}'), (o65, f'o65_le{t}')):
            img = _f('Image.addBands', dstImg=img, srcImg=_f('Image.rename', input=_f('Image.multiply', image1=src, image2=m), names=_k([name])))
    out = _f('Image.reduceRegion', image=img, reducer=_f('Reducer.sum'), geometry=geom, scale=_k(100), maxPixels=_k(1e9))
    return {'expression': {'result': 'out', 'values': {'out': out}}}


def band_for(rise):
    """Franja de HAND más chica que cubre una subida de `rise` metros (None si no hay subida)."""
    if rise is None or rise <= 0:
        return None
    return next((t for t in BANDS_T if rise <= t), BANDS_T[-1])


def summarize(raw, levels=None):
    r = lambda k: None if raw.get(k) is None else round(raw[k])
    bands = [{'up_to_m': t, 'people': r(f'pop_le{t}'), 'under5': r(f'u5_le{t}'), 'over65': r(f'o65_le{t}')} for t in BANDS_T]
    out = {'radius_km': RADIUS_M / 1000, 'total': r('total'), 'under5_total': r('u5_total'), 'over65_total': r('o65_total'), 'bands': bands}
    scen = []
    lv = levels or {}
    low = lv.get('low')
    for key, label in (('alert', 'Nivel de alerta'), ('evac', 'Nivel de evacuación')):
        h = lv.get(key)
        if h is None or low is None:
            continue
        rise = round(h - low, 2)
        t = band_for(rise)
        b = next((x for x in bands if x['up_to_m'] == t), None)
        if b:
            scen.append({'key': key, 'label': label, 'level_m': h, 'rise_m': rise, 'band_m': t, **{k: b[k] for k in ('people', 'under5', 'over65')}})
    out['scenarios'] = scen
    return out


def at_station(sid):
    import cuenca as cc
    st = next((s for s in cc.STATIONS if s['id'] == sid), None)
    if not st:
        raise LookupError('Localidad desconocida')
    levels = None
    if sid in cc.INA_SITES:
        _, a, e, lw = cc.INA_SITES[sid]
        levels = {'alert': a, 'evac': e, 'low': lw}
    proj, tok = veg.gee_token()
    url = f'{veg.GEE}/projects/{proj}/value:compute'
    resp = c.SESSION.post(url, json=expression(st['lat'], st['lon']), headers={'Authorization': f'Bearer {tok}'}, timeout=50)
    if resp.status_code >= 400:
        try:
            msg = (resp.json().get('error') or {}).get('message', '')
        except ValueError:
            msg = resp.text[:200]
        return c.envelope(None, veg.GEE, 'población cerca del río', 'Google Earth Engine', 'sin dato', f'Earth Engine HTTP {resp.status_code}: {msg[:220]}')
    data = summarize(resp.json().get('result') or {}, levels)
    data.update(id=sid, place=st['place'], river=st['river'], lat=st['lat'], lon=st['lon'], levels=levels,
                method=__doc__.split('\n\n', 1)[1].strip(),
                sources=['MERIT Hydro (Yamazaki et al., 2019) · CC BY-NC 4.0 / ODbL', 'WorldPop 2020 · CC BY 4.0'])
    return c.envelope(data, url.replace(proj, '{PROJECT}'), f"población cerca del río en {st['place']}", 'WorldPop · MERIT Hydro vía Google Earth Engine')


# ───────────────────── Mapa de la zona baja y de la gente que vive en ella ─────────────────────
# Imagen PNG para superponer en el mapa web o pegar en el informe:
#   · azul claro: terreno a `band` metros o menos por encima del curso de agua más cercano (MERIT Hydro HAND)
#   · amarillo → rojo: personas por hectárea que viven en esa franja (WorldPop 2020, 100 m = 1 ha por píxel)
#   · con base=True se agrega un relieve sombreado (NASADEM) y el agua permanente (JRC), para el PDF
# No es una mancha de inundación modelada: es la zona baja que quedaría expuesta si el río sube hasta esa franja.
MAP_PX = 640
POP_MAX = 40          # personas por hectárea en el extremo rojo de la escala
POP_PALETTE = ['fff3b0', 'fdb863', 'e66101', '8b0000']
ZONE_COLOR = '6fa8dc'


def bounds(lat, lon, radius=RADIUS_M):
    """Caja (oeste, sur, este, norte) en grados que contiene el círculo de análisis."""
    import math
    dlat = radius / 111320
    dlon = radius / (111320 * max(math.cos(math.radians(lat)), 0.2))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat


def map_expression(lat, lon, band, base=False, radius=RADIUS_M):
    band = band if band in BANDS_T else 3
    circle = _f('Geometry.buffer', geometry=_f('GeometryConstructors.Point', coordinates=_k([lon, lat])), distance=_k(radius))
    hand = _f('Image.select', input=_f('Image.load', id=_k(HAND)), bandSelectors=_k(['hnd']))
    low = _f('Image.lte', image1=hand, image2=_f('Image.constant', value=_k(band)))
    pop = _f('Image.select', input=_mosaic(POP), bandSelectors=_k(['population']))
    zone = _f('Image.visualize', image=_f('Image.clip', input=_f('Image.selfMask', image=low), geometry=circle),
              palette=_k([ZONE_COLOR]), opacity=_k(0.55))
    people = _f('Image.updateMask', image=pop, mask=_f('Image.gt', image1=pop, image2=_f('Image.constant', value=_k(0.5))))
    people = _f('Image.updateMask', image=people, mask=low)
    people = _f('Image.visualize', image=_f('Image.clip', input=people, geometry=circle),
                min=_k(0), max=_k(POP_MAX), palette=_k(POP_PALETTE))
    layers = [zone, people]
    if base:
        dem = _f('Image.select', input=_f('Image.load', id=_k('NASA/NASADEM_HGT/001')), bandSelectors=_k(['elevation']))
        shade = _f('Image.visualize', image=_f('Terrain.hillshade', input=dem), min=_k(120), max=_k(255),
                   palette=_k(['9a9a9a', 'ffffff']))
        water = _f('Image.select', input=_f('Image.load', id=_k('JRC/GSW1_4/GlobalSurfaceWater')), bandSelectors=_k(['occurrence']))
        water = _f('Image.visualize', image=_f('Image.selfMask', image=_f('Image.gte', image1=water, image2=_f('Image.constant', value=_k(50)))),
                   palette=_k(['1f4e79']))
        layers = [shade, water] + layers
    out = _f('ImageCollection.mosaic', collection=_f('ImageCollection.fromImages', images={'arrayValue': {'values': layers}}))
    w, s, e, n = bounds(lat, lon, radius)
    grid = {'dimensions': {'width': MAP_PX, 'height': MAP_PX},
            'affineTransform': {'scaleX': (e - w) / MAP_PX, 'shearX': 0, 'translateX': w,
                                'shearY': 0, 'scaleY': -(n - s) / MAP_PX, 'translateY': n},
            'crsCode': 'EPSG:4326'}
    return {'expression': {'result': 'out', 'values': {'out': out}}, 'fileFormat': 'PNG', 'grid': grid}


def station(sid):
    import cuenca as cc
    st = next((s for s in cc.STATIONS if s['id'] == sid), None)
    if not st:
        raise LookupError('Localidad desconocida')
    return st


def map_png(sid, band, base=False):
    """PNG de la zona baja y su población para una localidad ribereña. Devuelve (bytes, caja)."""
    st = station(sid)
    proj, tok = veg.gee_token()
    resp = c.SESSION.post(f'{veg.GEE}/projects/{proj}/image:computePixels', json=map_expression(st['lat'], st['lon'], band, base),
                          headers={'Authorization': f'Bearer {tok}'}, timeout=50)
    if resp.status_code >= 400 or not resp.content.startswith(b'\x89PNG'):
        raise RuntimeError(f'Earth Engine HTTP {resp.status_code}: {resp.text[:200]}')
    return resp.content, bounds(st['lat'], st['lon'])
