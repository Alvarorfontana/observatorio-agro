"""hazard v1.0 — amenaza de crecida por período de retorno, exposición e historia (Google Earth Engine).

Amenaza: JRC Global River Flood Hazard Maps v2.1 (Copernicus Emergency Management Service; LISFLOOD y
LISFLOOD-FP), profundidad de inundación en metros para siete períodos de retorno (10, 20, 50, 75, 100, 200 y
500 años), a 90 m. Se informa en qué período de retorno el sitio empieza a anegarse y cuánto sube el agua.
Exposición: población WorldPop 2020 (100 m) que vive, en 10 km a la redonda, donde el modelo anega en cada
período de retorno. Es exposición estimada, no personas registradas.
Historia observada: Global Flood Database (Cloud to Street y Dartmouth Flood Observatory; MODIS 2000-2018),
cuántos eventos de crecida cubrieron la zona.

Advertencia que viaja con el dato: NO es un mapa oficial de amenaza. Es un modelo global; las cuencas menores a
500 km² pueden quedar fuera sin dato, y en ese caso DOTS responde 'sin dato' con su motivo, nunca extrapola.
"""
from concurrent.futures import ThreadPoolExecutor

import research_connectors as c
import vegetation as veg

GEE = veg.GEE
RPS = (10, 20, 50, 75, 100, 200, 500)
HAZARD = 'JRC/CEMS_GLOFAS/FloodHazard/v2_1'      # JRC Global River Flood Hazard Maps v2.1 (CC BY 4.0)
GFD = 'GLOBAL_FLOOD_DB/MODIS_EVENTS/V1'          # Global Flood Database v1 (2000-2018)
POP = 'WorldPop/GP/100m/pop'                      # WorldPop 2020 (CC BY 4.0)
POINT_M = 150                                     # radio del "sitio": ~2 píxeles de 90 m
RADIUS_M = 10000                                  # radio de la exposición y de la historia
MIN_DEPTH_M = 0.1                                 # mínimo que mapea el JRC: por debajo, no se considera agua
GFD_PERIOD = [2000, 2018]


def _f(name, **args):
    return {'functionInvocationValue': {'functionName': name, 'arguments': args}}


def _k(v):
    return {'constantValue': v}


def _buffer(lat, lon, radius_m):
    return _f('Geometry.buffer', geometry=_f('GeometryConstructors.Point', coordinates=_k([lon, lat])), distance=_k(radius_m))


def _hazard_image():
    """Mosaico de los tiles JRC con las siete bandas de profundidad por período de retorno."""
    return _f('Image.select', input=_f('ImageCollection.mosaic', collection=_f('ImageCollection.load', id=_k(HAZARD))),
              bandSelectors=_k([f'RP{r}_depth' for r in RPS]))


def _pop_image():
    coll = _f('Collection.filter', collection=_f('ImageCollection.load', id=_k(POP)),
              filter=_f('Filter.equals', leftField=_k('year'), rightValue=_k(2020)))
    return _f('Image.select', input=_f('ImageCollection.mosaic', collection=coll), bandSelectors=_k(['population']))


def site_expression(lat, lon):
    """Profundidad máxima por período de retorno en el sitio (radio de ~150 m)."""
    out = _f('Image.reduceRegion', image=_hazard_image(), reducer=_f('Reducer.max'),
             geometry={'valueReference': 'g'}, scale=_k(90), maxPixels=_k(1e9))
    return {'expression': {'result': 'out', 'values': {'g': _buffer(lat, lon, POINT_M), 'out': out}}}


def exposure_expression(lat, lon):
    """Población (WorldPop) que vive donde el modelo anega, por período de retorno, en 10 km."""
    pop = _pop_image()
    img = None
    for r in RPS:
        depth = _f('Image.select', input=_hazard_image(), bandSelectors=_k([f'RP{r}_depth']))
        wet = _f('Image.gte', image1=depth, image2=_f('Image.constant', value=_k(MIN_DEPTH_M)))
        exp = _f('Image.rename', input=_f('Image.multiply', image1=pop, image2=wet), names=_k([f'exp{r}']))
        img = exp if img is None else _f('Image.addBands', dstImg=img, srcImg=exp)
    out = _f('Image.reduceRegion', image=img, reducer=_f('Reducer.sum'),
             geometry={'valueReference': 'g'}, scale=_k(100), maxPixels=_k(1e9))
    return {'expression': {'result': 'out', 'values': {'g': _buffer(lat, lon, RADIUS_M), 'out': out}}}


def history_expression(lat, lon):
    """Número de eventos de crecida (GFD 2000-2018) que cubrieron cada píxel, el mayor en 10 km."""
    coll = _f('ImageCollection.load', id=_k(GFD))
    events = _f('Image.rename', input=_f('Image.select', input=_f('ImageCollection.reduce', collection=coll, reducer=_f('Reducer.sum')),
                                         bandSelectors=_k(['flooded'])), names=_k(['flood_events']))
    ever = _f('Image.rename', input=_f('Image.select', input=_f('ImageCollection.reduce', collection=coll, reducer=_f('Reducer.max')),
                                       bandSelectors=_k(['flooded'])), names=_k(['flood_ever']))
    img = _f('Image.addBands', dstImg=events, srcImg=ever)
    out = _f('Image.reduceRegion', image=img, reducer=_f('Reducer.max'),
             geometry={'valueReference': 'g'}, scale=_k(250), maxPixels=_k(1e9))
    return {'expression': {'result': 'out', 'values': {'g': _buffer(lat, lon, RADIUS_M), 'out': out}}}


def _compute(proj, tok, body):
    r = c.SESSION.post(f'{GEE}/projects/{proj}/value:compute', json=body, headers={'Authorization': f'Bearer {tok}'}, timeout=55)
    if r.status_code >= 400:
        try:
            msg = (r.json().get('error') or {}).get('message', '')
        except ValueError:
            msg = r.text[:200]
        raise RuntimeError(f'Earth Engine HTTP {r.status_code}: {msg[:160]}')
    return r.json().get('result') or {}


# ───────────────────────────── lectura del resultado ─────────────────────────────

def profile(raw):
    """{'RP10_depth': v, ...} → [{rp_years, depth_m}] (None donde el sitio queda fuera del mapa)."""
    out = []
    for r in RPS:
        v = (raw or {}).get(f'RP{r}_depth')
        out.append({'rp_years': r, 'depth_m': None if v is None else round(float(v), 2)})
    return out


def first_rp(prof):
    """Menor período de retorno que ya anega el sitio (profundidad >= MIN_DEPTH_M), o None."""
    hit = [p['rp_years'] for p in prof if p.get('depth_m') is not None and p['depth_m'] >= MIN_DEPTH_M]
    return min(hit) if hit else None


def exposed(raw):
    """{'exp10': n, ...} → [{rp_years, people}]."""
    out = []
    for r in RPS:
        v = (raw or {}).get(f'exp{r}')
        out.append({'rp_years': r, 'people': None if v is None else round(float(v))})
    return out


def summarize(lat, lon, depths, expo, hist):
    prof = profile(depths)
    frp = first_rp(prof)
    people = exposed(expo)
    events = (hist or {}).get('flood_events')
    ever = (hist or {}).get('flood_ever')
    history = {'events': None if events is None else int(round(float(events))),
               'ever': None if ever is None else bool(round(float(ever))), 'period': GFD_PERIOD}
    if all(p['depth_m'] is None for p in prof):
        reading = ('El sitio queda fuera de los mapas de amenaza del JRC: el modelo cubre cuencas de más de '
                   '500 km² y puede no tener dato en este punto.')
    elif frp is None:
        reading = ('Según el modelo del JRC, el sitio no se anega ni en la crecida de 500 años '
                   f'({MIN_DEPTH_M} m o más de agua).')
    else:
        depth = next(p['depth_m'] for p in prof if p['rp_years'] == frp)
        near = next((x['people'] for x in people if x['rp_years'] == frp), None)
        reading = f'El modelo anega el sitio a partir de la crecida de {frp} años ({depth} m de agua).'
        if near is not None:
            reading += f' En 10 km, quedarían expuestas ~{near} personas.'
    return {'point': [round(lat, 5), round(lon, 5)], 'radius_km': RADIUS_M / 1000, 'site_radius_m': POINT_M,
            'min_depth_m': MIN_DEPTH_M, 'return_periods': prof, 'first_rp_years': frp,
            'exposed': people, 'history': history, 'reading': reading,
            'sources': ['JRC Global River Flood Hazard Maps v2.1 (Copernicus EMS, CC BY 4.0)',
                        'WorldPop 2020 (CC BY 4.0)', 'Global Flood Database v1 (2000-2018, CC BY-NC 4.0)'],
            'caveat': 'No es un mapa oficial de amenaza: es un modelo global (cuencas >= 500 km²). '
                      'La exposición es población residente estimada, no personas registradas.',
            'method': __doc__.split('\n\n', 1)[1].strip()}


def analyze(lat, lon):
    """Amenaza, exposición e historia del punto. Cada fuente que falla deja su parte en None; nunca se inventa."""
    try:
        proj, tok = veg.gee_token()
    except PermissionError as e:
        return c.envelope(None, GEE, 'amenaza de crecida por período de retorno', 'Copernicus EMS · JRC vía Google Earth Engine',
                          'sin dato', str(e)[:200])
    errors = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        fs = pool.submit(_compute, proj, tok, site_expression(lat, lon))
        fe = pool.submit(_compute, proj, tok, exposure_expression(lat, lon))
        fh = pool.submit(_compute, proj, tok, history_expression(lat, lon))
        depths = _result(fs, errors, 'amenaza')
        expo = _result(fe, errors, 'exposición')
        hist = _result(fh, errors, 'historia')
    if all(v is None for v in (depths, expo, hist)):
        return c.envelope(None, GEE, 'amenaza de crecida por período de retorno', 'Copernicus EMS · JRC vía Google Earth Engine',
                          'sin dato', '; '.join(errors)[:300] or 'Earth Engine no devolvió datos para este punto.')
    data = summarize(lat, lon, depths, expo, hist)
    data['errors'] = errors or None
    ok = depths is not None and any(p['depth_m'] is not None for p in data['return_periods'])
    return c.envelope(data, HAZARD, 'amenaza de crecida por período de retorno (JRC) y población expuesta',
                      'Copernicus EMS · JRC · WorldPop · GFD vía Google Earth Engine', 'recibido' if ok else 'sin dato',
                      None if ok else 'El punto no tiene amenaza JRC: puede estar fuera del modelo (cuenca < 500 km²).')


def _result(future, errors, label):
    try:
        return future.result()
    except Exception as e:
        errors.append(f'{label}: {type(e).__name__}: {str(e)[:120]}')
        return None
