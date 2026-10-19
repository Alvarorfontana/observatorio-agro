"""temas v1.0 — catálogo único de temas/variables de DOTS.

Cada tema declara de dónde viene el dato (organismo y URL), cómo se obtiene (método y
``resolver``) y con qué escala se lee. El mismo catálogo alimenta la página, el informe PDF y
la newsletter: un tema nunca se responde con dos criterios distintos.

Un ``resolver`` recibe ``(lat, lon, params)`` y devuelve un diccionario. Si trae ``status`` se
respeta (por ejemplo ``'sin dato'``); si no, se asume ``'recibido'``. Nunca se inventa: una
fuente que falla deja el tema en ``'sin dato'`` con su motivo.
"""
from datetime import datetime, timezone

import research_connectors as c


def _env(data, url, scope, organism, status='recibido', error=None):
    return c.envelope(data, url, scope, organism, status, error)


def _coords(lat, lon, p):
    """Punto de trabajo: el lat/lon pedido o, si no, el centroide de la zona (polígono) recibida."""
    if lat is not None and lon is not None:
        return lat, lon
    poly = (p or {}).get('poligono') or (p or {}).get('polygon')
    if isinstance(poly, list) and poly:
        pts = [(float(x[0]), float(x[1])) for x in poly if isinstance(x, (list, tuple)) and len(x) >= 2]
        if pts:
            return sum(a for a, _ in pts) / len(pts), sum(b for _, b in pts) / len(pts)
    return lat, lon


def nearest_station(lat, lon):
    """Localidad ribereña más cercana a un punto (para temas que se leen por estación)."""
    import cuenca, math
    if lat is None or lon is None:
        return None
    best, bid = None, None
    for s in cuenca.STATIONS:
        d = (s['lat'] - lat) ** 2 + (s['lon'] - lon) ** 2
        if best is None or d < best:
            best, bid = d, s['id']
    return bid


# ───────────────────────────── resolvers ─────────────────────────────

def _nino(lat, lon, p):
    import enso_panel
    return enso_panel.enso_panel()


def _enso_sudamerica(lat, lon, p):
    import datastore
    d = datastore.load('enso_sudamerica.json')
    if not d:
        return _env(None, 'https://www.cpc.ncep.noaa.gov', 'El Niño en Sudamérica (referencia por localidad)',
                    'NOAA CPC · ERA5', 'sin dato', 'La referencia aún no fue calculada (rama datos).')
    return _env(d, 'https://www.cpc.ncep.noaa.gov', 'El Niño en Sudamérica: histórico y pronóstico por localidad',
                'NOAA CPC · ERA5')


def _crecidas(lat, lon, p):
    import cuenca
    lat, lon = _coords(lat, lon, p)
    d = cuenca.rivers()
    sid = (p or {}).get('localidad') or (near if (near := nearest_station(lat, lon)) else None)
    if sid:
        d = {**d, 'stations': [s for s in d.get('stations', []) if s['id'] == sid], 'focus': sid}
    return _env(d, cuenca.FLOOD, 'Crecidas: caudal GloFAS y alturas/niveles oficiales del INA',
                'Copernicus GloFAS · INA (API A5)')


def _inundaciones(lat, lon, p):
    import gfm
    d = gfm.web_layers()
    ok = bool(d)
    return _env(d, gfm.WMS, 'Inundación satelital: capas GFM (Sentinel-1) y última pasada',
                'Copernicus EMS · Global Flood Monitoring', 'recibido' if ok else 'sin dato',
                None if ok else 'No hay pasadas recientes de GFM.')


def _amenaza(lat, lon, p):
    import hazard
    lat, lon = _coords(lat, lon, p)
    if lat is None or lon is None:
        return _env(None, 'https://data.jrc.ec.europa.eu/dataset/jrc-floods-floodmapgl_rp50y-tif',
                    'Amenaza de crecida por período de retorno', 'Copernicus EMS · JRC', 'sin dato',
                    'Indicá un punto o una zona para leer la amenaza de crecida (período de retorno).')
    return hazard.analyze(lat, lon)


def _poblaciones(lat, lon, p):
    lat, lon = _coords(lat, lon, p)
    sid = (p or {}).get('localidad') or (p or {}).get('id') or nearest_station(lat, lon)
    if not sid:
        return _env(None, 'https://www.worldpop.org', 'Población expuesta por franja de altura (HAND)',
                    'WorldPop · MERIT Hydro vía Earth Engine', 'sin dato',
                    'Elegí una localidad ribereña (o una zona) para calcular la población expuesta.')
    from poblacion import crecida
    try:
        return crecida.at_station(sid)
    except Exception as e:
        return _env(None, 'https://www.worldpop.org', 'Población expuesta por franja de altura (HAND)',
                    'WorldPop · MERIT Hydro vía Earth Engine', 'sin dato',
                    f'No se pudo calcular la población expuesta ({type(e).__name__}).')


def _evacuados(lat, lon, p):
    return _env(None, 'https://www.argentina.gob.ar/sinagir', 'Evacuados y damnificados registrados',
                'SINAGIR · Defensa Civil (partes de situación)', 'sin dato',
                'No existe API pública: son partes de SINAGIR/Defensa Civil. DOTS no inventa cifras; '
                'se citan de un boletín o quedan sin dato.')


def _clima(lat, lon, p):
    lat, lon = _coords(lat, lon, p)
    return c.external('https://api.open-meteo.com/v1/forecast',
                      {'latitude': lat, 'longitude': lon, 'current': 'temperature_2m,relative_humidity_2m,precipitation',
                       'daily': 'precipitation_sum,et0_fao_evapotranspiration', 'forecast_days': 7, 'timezone': 'auto'})


def _suelo(lat, lon, p):
    lat, lon = _coords(lat, lon, p)
    return c.soil_full(lat, lon)


def _humedad_smap(lat, lon, p):
    import smap
    lat, lon = _coords(lat, lon, p)
    if lat is None or lon is None:
        return _env(None, smap.SMAP, 'Humedad del suelo satelital (SMAP)', 'NASA · NSIDC (Earth Engine)', 'sin dato',
                    'Indicá un punto o una zona para leer la humedad del suelo por satélite.')
    return smap.analyze(lat, lon)


def _rendimiento(lat, lon, p):
    import yield_forecast as yf
    lat, lon = _coords(lat, lon, p)
    p = p or {}
    org = f'{yf.FAO33} · Open-Meteo ERA5 · ISRIC SoilGrids'
    if lat is None or lon is None:
        return _env(None, yf.SOURCE, 'rendimiento esperado por agua (FAO-33)', org, 'sin dato',
                    'Indicá un punto para estimar el rendimiento por agua.')
    if not p.get('sowing'):
        return _env(None, yf.SOURCE, 'rendimiento esperado por agua (FAO-33)', org, 'sin dato',
                    'Indicá la fecha de siembra (sowing) para estimar el rendimiento.')
    return yf.analyze(lat, lon, str(p.get('crop') or 'maiz')[:20], p.get('sowing'), p.get('potencial_t_ha'))


def _aptitud(lat, lon, p):
    import crop_suitability as cs
    lat, lon = _coords(lat, lon, p)
    if lat is None or lon is None:
        return _env(None, cs.SOURCE, 'aptitud de cultivos (envolventes)', cs.ORGANISM, 'sin dato',
                    'Indicá un punto o una zona para evaluar la aptitud del cultivo.')
    return cs.analyze(lat, lon, str((p or {}).get('crop') or 'maiz')[:20])


# ───────────────────────────── catálogo ─────────────────────────────
# resolver / organism / how / source_url: la procedencia viaja con el dato.
TEMAS = {
    'nino': {
        'title': 'El Niño (ONI, RONI, Niño 3.4)', 'group': 'Clima', 'scope': 'global',
        'organism': 'NOAA CPC',
        'how': 'Series oficiales del CPC leídas en texto: ONI estacional, RONI, Niño 3.4 semanal y estado del aviso; '
               'la fase se deriva de la última anomalía.',
        'source_url': 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/',
        'scale': None, 'resolver': _nino,
    },
    'enso_sudamerica': {
        'title': 'El Niño: referencia por localidad', 'group': 'Clima', 'scope': 'global',
        'organism': 'NOAA CPC · ERA5',
        'how': 'Composites ERA5 (desde 1991) de lluvia y temperatura por fase ENSO para ~80 localidades de Sudamérica, '
               'calculados por workflow y publicados en la rama datos.',
        'source_url': 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/',
        'scale': None, 'resolver': _enso_sudamerica,
    },
    'crecidas': {
        'title': 'Crecidas de ríos', 'group': 'Agua', 'scope': 'estación',
        'organism': 'Copernicus GloFAS · INA',
        'how': 'Caudal simulado GloFAS (~5 km, 34 puertos) vía flood-api de Open-Meteo, comparado con su serie 2001-2020; '
               'alturas y niveles oficiales (alerta/evacuación) por la API A5 del INA y escalas de Prefectura. '
               'Con localidad o zona, se enfoca en la estación elegida o la más cercana.',
        'source_url': 'https://flood-api.open-meteo.com/v1/flood',
        'scale': 'caudal_percentil', 'resolver': _crecidas,
    },
    'inundaciones': {
        'title': 'Inundaciones (satélite)', 'group': 'Agua', 'scope': 'zona',
        'organism': 'Copernicus EMS · Global Flood Monitoring',
        'how': 'Extensión de agua GFM (Sentinel-1 SAR) por STAC/WMS; se informa la última pasada disponible y su cobertura.',
        'source_url': 'https://global-flood.emergency.copernicus.eu',
        'scale': None, 'resolver': _inundaciones,
    },
    'amenaza': {
        'title': 'Amenaza de crecida (período de retorno)', 'group': 'Agua', 'scope': 'punto',
        'organism': 'Copernicus EMS · JRC (LISFLOOD-FP)',
        'how': 'Profundidad de inundación modelada por el JRC (LISFLOOD y LISFLOOD-FP, 90 m) para siete períodos '
               'de retorno (10 a 500 años): en qué período el sitio empieza a anegarse y cuánto sube el agua. '
               'Se cruza con la población WorldPop 2020 expuesta en 10 km y con los eventos de la Global Flood '
               'Database (2000-2018). No es un mapa oficial; las cuencas de menos de 500 km² pueden quedar sin dato.',
        'source_url': 'https://data.jrc.ec.europa.eu/dataset/jrc-floods-floodmapgl_rp50y-tif',
        'scale': 'flood_rp_years', 'resolver': _amenaza,
    },
    'poblaciones': {
        'title': 'Poblaciones expuestas', 'group': 'Gente', 'scope': 'estación',
        'organism': 'WorldPop · MERIT Hydro (Earth Engine)',
        'how': 'Población que vive a 1, 2, 3, 5 y 10 m o menos sobre el curso de agua (HAND, 90 m) en 15 km a la redonda, '
               'con escenarios a nivel de alerta y de evacuación. Es exposición estimada, no personas registradas. '
               'Usa la localidad elegida o la más cercana a la zona.',
        'source_url': 'https://www.worldpop.org',
        'scale': None, 'resolver': _poblaciones,
    },
    'evacuados': {
        'title': 'Evacuados y damnificados', 'group': 'Gente', 'scope': 'global',
        'organism': 'SINAGIR · Defensa Civil',
        'how': 'No hay API pública: los conteos de evacuados/damnificados salen de partes de situación de '
               'SINAGIR/Defensa Civil. DOTS los cita de un boletín o los deja sin dato; nunca los estima.',
        'source_url': 'https://www.argentina.gob.ar/sinagir',
        'scale': None, 'resolver': _evacuados,
    },
    'clima': {
        'title': 'Clima actual y 7 días', 'group': 'Clima', 'scope': 'punto',
        'organism': 'Open-Meteo',
        'how': 'Pronóstico por API REST: temperatura, humedad, lluvia y ET₀ a 7 días en el punto consultado '
               '(o en el centroide de la zona).',
        'source_url': 'https://open-meteo.com',
        'scale': None, 'resolver': _clima,
    },
    'suelo': {
        'title': 'Suelo (perfil SoilGrids)', 'group': 'Suelo', 'scope': 'punto',
        'organism': 'ISRIC SoilGrids',
        'how': 'Propiedades del suelo (N, carbono, pH, arcilla, etc.) por profundidad desde la API de SoilGrids, '
               'en el punto consultado o el centroide de la zona.',
        'source_url': 'https://rest.isric.org/soilgrids/v2.0/properties/query',
        'scale': None, 'resolver': _suelo,
    },
    'humedad_smap': {
        'title': 'Humedad del suelo satelital (SMAP)', 'group': 'Suelo', 'scope': 'punto',
        'organism': 'NASA · NSIDC (SMAP L4, Earth Engine)',
        'how': 'SMAP L4 SPL4SMGP v008 (radiómetro en banda L, 9 km, cada 3 h) promediado en 12,5 km: humedad de '
               'la superficie (0-5 cm) y de la zona de raíces (0-100 cm) en m³/m³ y % del volumen, con el '
               'percentil de la zona de raíces contra la serie desde 2015. Es la única lectura directa del '
               'satélite; la ventana usada es la última publicada (SMAP tarda unos días).',
        'source_url': 'https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL4SMGP_008',
        'scale': 'soil_moisture_vwc', 'resolver': _humedad_smap,
    },
    'rendimiento': {
        'title': 'Rendimiento esperado por agua (FAO-33)', 'group': 'Cultivo', 'scope': 'punto',
        'organism': 'FAO-33 (Doorenbos y Kassam) · Open-Meteo ERA5 · ISRIC SoilGrids',
        'how': 'Rendimiento relativo de la campaña por agua: Ya/Ym = 1 − Ky·(1 − ETa/ETm) con balance hídrico '
               'FAO-56 de secano (ETm = Σ Kc·ET0, ETa = Σ Ks·Kc·ET0). ET0 y lluvia de Open-Meteo (ERA5 observado, '
               'pronóstico a 10 días y climatología ERA5 del resto de la campaña); agua útil del suelo de SoilGrids. '
               'Necesita cultivo y fecha de siembra. Es una estimación por agua, no un pronóstico de cosecha.',
        'source_url': 'https://open-meteo.com',
        'scale': 'yield_pct', 'resolver': _rendimiento,
    },
    'aptitud': {
        'title': 'Aptitud de cultivos (envolventes)', 'group': 'Cultivo', 'scope': 'punto',
        'organism': 'OpenFarm (BSD-3) · FAO EcoCrop · Open-Meteo ERA5 · ISRIC SoilGrids',
        'how': 'Puntúa el cultivo elegido por envolventes de temperatura, lluvia, pH y textura contra el clima '
               'normal (ERA5, 10 años) y el suelo (SoilGrids 0-5 cm) del punto. El puntaje global es el mínimo '
               'de los factores: manda el factor limitante. Usa lat/lon y, opcional, crop (por defecto maíz).',
        'source_url': 'https://github.com/superzero11/OpenFarm',
        'scale': 'crop_suitability', 'resolver': _aptitud,
    },
}


def ids():
    return list(TEMAS)


def catalog():
    """Catálogo sin el resolver (no es serializable): id, título, grupo, alcance, organismo, método y escala."""
    return [{'id': k, 'title': v['title'], 'group': v['group'], 'scope': v.get('scope'), 'organism': v['organism'],
             'how': v['how'], 'source_url': v['source_url'], 'scale': v.get('scale')}
            for k, v in TEMAS.items()]


def resolve(tid, lat=None, lon=None, params=None):
    """Resuelve un tema a su bloque de datos con procedencia. KeyError si el tema no existe."""
    t = TEMAS[tid]
    out = t['resolver'](lat, lon, params or {})
    if not isinstance(out, dict):
        out = _env(out, t['source_url'], t['title'], t['organism'])
    out.setdefault('organism', t['organism'])
    out.setdefault('source_url', t['source_url'])
    out['id'] = tid
    out['title'] = t['title']
    out['group'] = t['group']
    out['how'] = t['how']
    out['requested_at'] = datetime.now(timezone.utc).isoformat()
    return out
