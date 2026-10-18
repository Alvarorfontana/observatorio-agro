"""smap v1.0 — humedad del suelo medida por satélite SMAP (NASA), superficie y zona de raíces (Google Earth Engine).

SMAP (Soil Moisture Active Passive; NASA y NSIDC, L4 SPL4SMGP v008, 9 km, cada 3 h desde 2015) estima la humedad
del suelo con un radiómetro de microondas en banda L: es una medición satelital, no un modelo meteorológico. DOTS
promedia, en un radio de 12,5 km y en los últimos días publicados, la humedad de la capa superficial (0-5 cm) y de
la zona de raíces (0-100 cm), en fracción de volumen (m³/m³) y en % del volumen. Acompaña el percentil de la zona
de raíces que calcula NASA contra la serie desde 2015: deja el valor crudo en contexto, sin inventarlo.

Es la tercera opinión de humedad del suelo de DOTS —Open-Meteo es pronóstico y NASA POWER/MERRA-2 un reanálisis—
y la única que viene del satélite. Se usa la última ventana con dato publicado (SMAP tarda unos días en estar
disponible) y el conjunto v008, que reemplazó al v007 discontinuado. Si Earth Engine no devuelve datos, el tema
queda en 'sin dato' con su motivo, nunca se extrapola.
"""
from datetime import timedelta

import research_connectors as c
import vegetation as veg

GEE = veg.GEE
SMAP = 'NASA/SMAP/SPL4SMGP/008'                 # SMAP L4 SPL4SMGP v008 (NASA/NSIDC, dominio público, 9 km)
SURFACE = 'sm_surface'                          # humedad 0-5 cm (fracción de volumen)
ROOT = 'sm_rootzone'                            # humedad 0-100 cm (fracción de volumen)
ROOT_PCTL = 'sm_rootzone_pctl'                  # percentil de la zona de raíces (0-100), serie desde 2015
SURFACE_WET = 'sm_surface_wetness'              # saturación relativa de la superficie (0-1)
BANDS = [SURFACE, ROOT, ROOT_PCTL, SURFACE_WET]
RADIUS_M = 12500                                # radio del entorno: ~1 píxel de 11 km a cada lado
DAYS = 7                                         # ventana promediada
LAG_DAYS = 4                                     # latencia típica de publicación de SMAP L4


def _f(name, **args):
    return {'functionInvocationValue': {'functionName': name, 'arguments': args}}


def _k(v):
    return {'constantValue': v}


def _buffer(lat, lon, radius_m):
    return _f('Geometry.buffer', geometry=_f('GeometryConstructors.Point', coordinates=_k([lon, lat])), distance=_k(radius_m))


def window_expression(lat, lon, start, end):
    """Humedad media del entorno en una ventana de fechas: superficie, raíces, percentil y mojado superficial."""
    coll = _f('Collection.filter', collection=_f('ImageCollection.load', id=_k(SMAP)),
              filter=_f('Filter.dateRangeContains', leftValue=_f('DateRange', start=_k(start), end=_k(end)),
                        rightField=_k('system:time_start')))
    img = _f('Image.select', input=_f('ImageCollection.reduce', collection=coll, reducer=_f('Reducer.mean')),
             bandSelectors=_k(BANDS))
    out = _f('Image.reduceRegion', image=img, reducer=_f('Reducer.mean'),
             geometry={'valueReference': 'g'}, scale=_k(11000), maxPixels=_k(1e9))
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

def _num(v):
    return None if v is None else float(v)


def _r3(v):
    return None if v is None else round(v, 3)


def category(pctl):
    """Categoría a partir del percentil de humedad de la zona de raíces (serie desde 2015)."""
    if pctl is None:
        return None
    if pctl < 10:
        return 'muy seco respecto de lo normal'
    if pctl < 30:
        return 'más seco que lo normal'
    if pctl <= 70:
        return 'normal'
    if pctl <= 90:
        return 'más húmedo que lo normal'
    return 'muy húmedo respecto de lo normal'


def summarize(lat, lon, raw, start, end):
    raw = raw or {}
    s, r, p, w = (_num(raw.get(SURFACE)), _num(raw.get(ROOT)), _num(raw.get(ROOT_PCTL)), _num(raw.get(SURFACE_WET)))
    cat = category(p)
    pc = lambda v: None if v is None else round(100 * v, 1)
    if s is None and r is None:
        reading = 'SMAP no devolvió humedad de suelo para este punto y período.'
    else:
        bits = []
        if s is not None:
            bits.append(f'superficie (0-5 cm) {pc(s)} %vol')
        if r is not None:
            bits.append(f'zona de raíces (0-100 cm) {pc(r)} %vol')
        reading = f'Promedio del {start} al {end}: ' + ' y '.join(bits) + '.'
        if p is not None:
            reading += f' La zona de raíces está en el percentil {int(round(p))} ({cat} desde 2015).'
    return {'point': [round(lat, 5), round(lon, 5)], 'radius_km': RADIUS_M / 1000, 'period': [start, end],
            'surface_vwc': _r3(s), 'root_vwc': _r3(r), 'surface_pct': pc(s), 'root_pct': pc(r),
            'root_percentile': None if p is None else int(round(p)), 'surface_wetness': _r3(w),
            'category': cat, 'reading': reading,
            'sources': ['SMAP L4 SPL4SMGP v008 (NASA/NSIDC, dominio público)',
                        'Google Earth Engine'],
            'caveat': 'SMAP es una estimación satelital (banda L, 9 km) del promedio del entorno, no una medición '
                      'puntual en el suelo. Cuando el instrumento está fuera de servicio, SMAP L4 usa sólo el modelo.',
            'method': __doc__.split('\n\n', 1)[1].strip()}


def analyze(lat, lon):
    """Humedad del suelo por satélite en el punto. Si la fuente falla, queda en 'sin dato'; nunca se inventa."""
    try:
        proj, tok = veg.gee_token()
    except PermissionError as e:
        return c.envelope(None, SMAP, 'humedad del suelo por satélite (SMAP)', 'NASA · NSIDC vía Google Earth Engine',
                          'sin dato', str(e)[:200])
    end = c._now().date() - timedelta(days=LAG_DAYS)
    start = end - timedelta(days=DAYS - 1)
    try:
        raw = _compute(proj, tok, window_expression(lat, lon, start.isoformat(), end.isoformat()))
    except RuntimeError as e:
        return c.envelope(None, SMAP, 'humedad del suelo por satélite (SMAP)', 'NASA · NSIDC vía Google Earth Engine',
                          'sin dato', str(e)[:300])
    data = summarize(lat, lon, raw, start.isoformat(), end.isoformat())
    ok = data['surface_vwc'] is not None or data['root_vwc'] is not None
    return c.envelope(data, SMAP, 'humedad del suelo por satélite (SMAP): superficie y zona de raíces',
                      'NASA · NSIDC vía Google Earth Engine', 'recibido' if ok else 'sin dato',
                      None if ok else 'SMAP no trajo humedad para este punto y período (puede haber una brecha de datos).')
