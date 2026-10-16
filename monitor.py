"""monitor v1.0 — estado en vivo de las fuentes externas de DOTS.

Hace una consulta mínima a cada servicio, en paralelo y con tiempo límite, y devuelve si respondió,
cuánto tardó y el código HTTP. No devuelve cuerpos ni URLs con claves. Sirve para el panel de
fuentes y para el control diario.
"""
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import research_connectors as c

LAT, LON = -29.0, -59.6   # punto de control en tierra firme (centro-norte de Santa Fe), no sobre agua


def _probes():
    today = c._now().date()
    a = today - timedelta(days=60)
    return {
        'Planetary Computer (Sentinel-2)': ('get', 'https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-2-l2a', None),
        'Open-Meteo pronóstico': ('get', 'https://api.open-meteo.com/v1/forecast', {'latitude': LAT, 'longitude': LON, 'current': 'temperature_2m'}),
        'Open-Meteo ERA5': ('get', 'https://archive-api.open-meteo.com/v1/archive', {'latitude': LAT, 'longitude': LON, 'start_date': f'{a}', 'end_date': f'{a}', 'daily': 'precipitation_sum'}),
        'NASA POWER': ('get', 'https://power.larc.nasa.gov/api/temporal/daily/point', {'parameters': 'T2M', 'community': 'AG', 'latitude': LAT, 'longitude': LON, 'start': a.strftime('%Y%m%d'), 'end': a.strftime('%Y%m%d'), 'format': 'JSON'}),
        'NASA ORNL MODIS': ('get', 'https://modis.ornl.gov/rst/api/v1/MOD13Q1/dates', {'latitude': LAT, 'longitude': LON}),
        'ISRIC SoilGrids': ('get', 'https://rest.isric.org/soilgrids/v2.0/properties/query', {'lat': LAT, 'lon': LON, 'property': 'ocs', 'depth': '0-30cm', 'value': 'mean'}),
        'ISRIC SoilGrids · consulta completa': ('get', 'https://rest.isric.org/soilgrids/v2.0/properties/query', {'lat': LAT, 'lon': LON, 'property': c.SOIL_PROPS, 'depth': c.SOIL_DEPTHS, 'value': 'mean'}),
        'NOAA PSL (ONI)': ('get', 'https://psl.noaa.gov/data/correlation/oni.data', None),
        'CHIRPS · ClimateSERV': ('get', 'https://climateserv.servirglobal.net/api/getClimateScenarioInfo/', None),
        'OSRM rutas': ('get', f'https://router.project-osrm.org/route/v1/driving/{LON},{LAT};-58.83,-27.47', {'overview': 'false'}),
        'Nominatim (OpenStreetMap)': ('get', 'https://nominatim.openstreetmap.org/search', {'q': 'Corrientes, Argentina', 'format': 'jsonv2', 'limit': 1}),
        'DolarAPI': ('get', 'https://dolarapi.com/v1/dolares/oficial', None),
    }


def _probe(name, spec, timeout):
    _, url, params = spec
    t0 = time.monotonic()
    try:
        r = c.SESSION.get(url, params=params or {}, timeout=timeout, headers={'Accept': 'application/json, text/plain, */*'})
        ms = round((time.monotonic() - t0) * 1000)
        ok = 200 <= r.status_code < 300
        return {'source': name, 'ok': ok, 'http': r.status_code, 'ms': ms, 'error': None if ok else f'HTTP {r.status_code}'}
    except Exception as e:
        return {'source': name, 'ok': False, 'http': None, 'ms': round((time.monotonic() - t0) * 1000), 'error': type(e).__name__}


def check(timeout=40):
    probes = _probes()
    with ThreadPoolExecutor(max_workers=len(probes)) as pool:
        rows = list(pool.map(lambda kv: _probe(kv[0], kv[1], timeout), probes.items()))
    up = sum(1 for r in rows if r['ok'])
    return c.envelope({'sources': rows, 'up': up, 'total': len(rows), 'timeout_s': timeout,
                       'slow': [r['source'] for r in rows if r['ok'] and r['ms'] > 8000]},
                      'multi', 'estado de las fuentes externas', 'DOTS · monitor',
                      'recibido' if up else 'sin dato', None if up else 'Ninguna fuente respondió')


def soil_trace(lat, lon):
    """Corre el análisis de suelo completo en un punto y devuelve tiempo, estado o el error exacto (sin claves: SoilGrids es abierta)."""
    t0 = time.monotonic()
    try:
        env = c.soil_full(lat, lon)
        d = env.get('data') or {}
        return {'ok': True, 'ms': round((time.monotonic() - t0) * 1000), 'status': env.get('status'), 'error': env.get('error'),
                'point_used': env.get('point_used'), 'rows': len((d.get('dots_summary') or {}).get('rows') or [])}
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)[-1]
        return {'ok': False, 'ms': round((time.monotonic() - t0) * 1000), 'error': type(e).__name__,
                'detail': str(e)[:240], 'at': f'{tb.name}:{tb.lineno}'}


LOT = [[-28.56, -58.71], [-28.56, -58.69], [-28.54, -58.69], [-28.54, -58.71]]   # lote de control en tierra (Corrientes)
GROUPS = {
    '1': ['variables', 'modelos', 'historico', 'escenas', 'rios', 'aire', 'elevacion'],
    '2': ['ndvi', 'indices', 'teleconexiones', 'estadistica', 'enso', 'humedad-sar', 'nivel-rio'],
    '3': ['suelo', 'serie', 'proyeccion', 'sustentabilidad', 'plataformas'],
    '4': ['smn', 'inmet', 'nasa-power-30', 'landsat', 'radar', 'copernicus-stac', 'firms'],
}


def routes(app, group):
    """Recorre las rutas del panel dentro del mismo servidor y devuelve código, tiempo y error de cada una."""
    import json as _json
    names = GROUPS.get(str(group))
    if not names:
        raise ValueError('grupo 1 a 4')
    lat = sum(p[0] for p in LOT) / 4; lon = sum(p[1] for p in LOT) / 4

    def one(name):
        t0 = time.monotonic()
        with app.test_client() as cl:
            r = cl.get(f'/api/fuentes/{name}', query_string={'lat': lat, 'lon': lon, 'polygon': _json.dumps(LOT)})
        js = r.get_json(silent=True) or {}
        return {'route': name, 'code': r.status_code, 'ms': round((time.monotonic() - t0) * 1000),
                'status': js.get('status'), 'error': (str(js.get('error'))[:160] if js.get('error') else None), 'type': js.get('type')}
    with ThreadPoolExecutor(max_workers=len(names)) as pool:
        return list(pool.map(one, names))
