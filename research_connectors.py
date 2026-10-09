"""research_connectors v3.0 — conectores DOTS reconstruidos.

Contrato (el que esperan research_routes.py, agentic_engine.py y el frontend):
  * Cada conector devuelve un 'envelope':
      {status, data, error, consulted_at, source_url, scope, organism}
    El frontend lee payload.data / payload.consulted_at / payload.source_url.
  * Si la fuente falla, el conector LANZA excepción (el Blueprint responde 502 y
    el motor Agentic marca la fuente como 'sin dato'). Nunca se inventan datos.
  * Las credenciales jamás se incluyen en source_url ni en la respuesta.
"""
import csv, io, math, os, re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import requests

UA = 'DOTS-Campo/1.6 (observatorio agroambiental; Nominatim/NWS/MET exigen User-Agent)'
TIMEOUT = 20
SESSION = requests.Session()
SESSION.headers.update({'User-Agent': UA})

AGENCIES = ['smn', 'inmet', 'dmc', 'eccc', 'nws']


# ───────────────────────────── utilidades ─────────────────────────────
def _now():
    return datetime.now(timezone.utc)


def envelope(data, url, scope, organism, status='recibido', error=None):
    return {'status': status, 'data': data, 'error': error,
            'consulted_at': _now().isoformat(), 'source_url': url,
            'scope': scope, 'organism': organism}


def _get(url, params=None, headers=None, timeout=TIMEOUT):
    r = SESSION.get(url, params=params or {}, headers=headers or {}, timeout=timeout)
    r.raise_for_status()
    return r


def _post(url, payload, timeout=TIMEOUT):
    r = SESSION.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    return r


def external(url, params=None, headers=None, scope='generic', organism=None):
    """GET JSON genérico. Lanza excepción si la fuente no responde."""
    r = _get(url, params, headers)
    return envelope(r.json(), url, scope, organism)


def coordinates(q):
    """q: {'lat':[valor], 'lon':[valor]} → (lat, lon) validados."""
    try:
        lat = float(q['lat'][0]); lon = float(q['lon'][0])
    except (KeyError, IndexError, TypeError, ValueError):
        raise ValueError('Coordenadas inválidas: se requieren lat y lon numéricos')
    if not (math.isfinite(lat) and math.isfinite(lon)) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError('Coordenadas fuera de rango')
    return lat, lon


def _poly(polygon):
    if polygon is None:
        return None
    try:
        pts = [[float(a), float(b)] for a, b in polygon]
    except (TypeError, ValueError):
        raise ValueError('Polígono inválido')
    if not 3 <= len(pts) <= 500:
        raise ValueError('El polígono debe tener entre 3 y 500 vértices')
    return pts


def polygon_bbox(polygon):
    """Polígono [[lat,lon],...] → (min_lon, min_lat, max_lon, max_lat)."""
    pts = _poly(polygon)
    lats = [p[0] for p in pts]; lons = [p[1] for p in pts]
    return (min(lons), min(lats), max(lons), max(lats))


def point_in_polygon(lat, lon, polygon):
    pts = _poly(polygon)
    inside = False
    j = len(pts) - 1
    for i in range(len(pts)):
        yi, xi = pts[i]; yj, xj = pts[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _bbox(lat, lon, polygon=None, pad=0.1):
    if polygon:
        return list(polygon_bbox(polygon))
    return [lon - pad, lat - pad, lon + pad, lat + pad]


def _km(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2 +
         math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(a))


def image_bytes(url, limit=6_000_000):
    r = SESSION.get(url, timeout=15, stream=True)
    r.raise_for_status()
    if not r.headers.get('Content-Type', '').startswith('image/'):
        raise ValueError('La respuesta no es una imagen')
    data = r.raw.read(limit + 1, decode_content=True)
    if len(data) > limit:
        raise ValueError('Imagen demasiado grande')
    return data


# ───────────────────────────── clima / suelo / agua ─────────────────────────────
def variables(lat, lon):
    url = 'https://api.open-meteo.com/v1/forecast'
    return external(url, {
        'latitude': lat, 'longitude': lon, 'timezone': 'auto', 'forecast_days': 7,
        'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,dew_point_2m,precipitation,cloud_cover,'
                   'surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m,weather_code',
        'hourly': 'soil_moisture_0_to_1cm,soil_moisture_1_to_3cm,soil_moisture_3_to_9cm,soil_moisture_9_to_27cm,'
                  'soil_moisture_27_to_81cm,soil_temperature_0cm,soil_temperature_6cm,soil_temperature_18cm,'
                  'vapour_pressure_deficit,dew_point_2m',
        'daily': 'precipitation_sum,precipitation_hours,precipitation_probability_max,et0_fao_evapotranspiration,'
                 'temperature_2m_max,temperature_2m_min,shortwave_radiation_sum,sunshine_duration,'
                 'wind_gusts_10m_max,uv_index_max'},
        scope='clima, suelo por profundidad, radiación, VPD y ET₀', organism='Open-Meteo')


SOIL_PROPS = ['nitrogen', 'soc', 'phh2o', 'clay', 'sand', 'silt', 'bdod', 'cec', 'cfvo', 'ocd', 'wv0033', 'wv1500']
SOIL_DEPTHS = ['0-5cm', '5-15cm', '15-30cm', '30-60cm']
SOIL_LABELS = {'nitrogen': 'Nitrógeno total', 'soc': 'Carbono orgánico', 'phh2o': 'pH (agua)', 'clay': 'Arcilla',
               'sand': 'Arena', 'silt': 'Limo', 'bdod': 'Densidad aparente', 'cec': 'Capacidad de intercambio (CIC)',
               'cfvo': 'Fragmentos gruesos', 'ocd': 'Densidad de carbono', 'wv0033': 'Agua a capacidad de campo',
               'wv1500': 'Agua en punto de marchitez'}


def soil_full(lat, lon):
    env = external('https://rest.isric.org/soilgrids/v2.0/properties/query',
                   {'lat': lat, 'lon': lon, 'property': SOIL_PROPS, 'depth': SOIL_DEPTHS, 'value': 'mean'},
                   scope='suelo modelado 0-60 cm (no sustituye laboratorio)', organism='ISRIC SoilGrids')
    rows, by = [], {}
    for layer in ((env['data'] or {}).get('properties') or {}).get('layers') or []:
        name = layer.get('name'); um = layer.get('unit_measure') or {}
        f = um.get('d_factor') or 1; unit = um.get('target_units') or ''
        vals = {}
        for d in layer.get('depths') or []:
            v = (d.get('values') or {}).get('mean')
            vals[d.get('label')] = None if v is None else round(v / f, 3 if f >= 100 else 2)
        by[name] = vals
        rows.append({'key': name, 'label': SOIL_LABELS.get(name, name), 'unit': unit, 'by_depth': vals})
    # agua útil = capacidad de campo − marchitez, por espesor de cada capa (unidades volumétricas)
    awc = None
    fc, wp = by.get('wv0033') or {}, by.get('wv1500') or {}
    thick = {'0-5cm': 50, '5-15cm': 100, '15-30cm': 150, '30-60cm': 300}
    parts = []
    for dpt, mm in thick.items():
        a, b = fc.get(dpt), wp.get(dpt)
        if a is None or b is None:
            parts = None; break
        frac = (a - b) / (100 if max(a, b) > 1.5 else 1)   # admite % o fracción
        parts.append(max(frac, 0) * mm)
    if parts:
        awc = round(sum(parts), 1)
    env['data']['dots_summary'] = {'rows': rows, 'depths': SOIL_DEPTHS, 'available_water_mm_0_60': awc,
                                   'note': 'SoilGrids 250 m, modelo global. Agua útil = (capacidad de campo − marchitez) × espesor, 0–60 cm.'}
    return env


def historical(lat, lon, days=60):
    """Serie diaria NASA POWER (últimos días disponibles; POWER publica con ~3 días de rezago)."""
    end = _now().date() - timedelta(days=3)
    start = end - timedelta(days=days)
    return external('https://power.larc.nasa.gov/api/temporal/daily/point', {
        'parameters': 'T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M', 'community': 'AG',
        'latitude': lat, 'longitude': lon, 'start': start.strftime('%Y%m%d'),
        'end': end.strftime('%Y%m%d'), 'format': 'JSON'},
        scope='agrometeorología diaria', organism='NASA POWER')


def nasa_power_long(lat, lon, years=30):
    years = int(years)
    if not 1 <= years <= 40:
        raise ValueError('Años fuera de rango')
    end = _now().year - 1
    return external('https://power.larc.nasa.gov/api/temporal/monthly/point', {
        'parameters': 'T2M,PRECTOTCORR,RH2M,ALLSKY_SFC_SW_DWN,WS2M', 'community': 'AG',
        'latitude': lat, 'longitude': lon, 'start': end - years + 1, 'end': end, 'format': 'JSON'},
        scope=f'agrometeorología mensual {years} años', organism='NASA POWER')


def air_quality(lat, lon):
    return external('https://air-quality-api.open-meteo.com/v1/air-quality', {
        'latitude': lat, 'longitude': lon, 'timezone': 'UTC', 'forecast_days': 3,
        'hourly': 'pm2_5,pm10,ozone,nitrogen_dioxide,carbon_monoxide,sulphur_dioxide'},
        scope='calidad de aire (pronóstico CAMS en grilla)', organism='Open-Meteo / CAMS')


def elevation(lat, lon):
    return external('https://api.open-meteo.com/v1/elevation', {'latitude': lat, 'longitude': lon},
                    scope='elevación DEM', organism='Open-Meteo / Copernicus DEM')


INA_SERIES = {'22': 'altura', '25500': 'altura mensual', '37299': 'temperatura'}


def ina_series(series, days='30', years=None):
    """INA Alerta (Bella Vista). Estación fija: no cambia al mover el mapa.
    NOTA: endpoint a verificar contra la API vigente del INA."""
    series = str(series)
    if series not in INA_SERIES:
        raise ValueError('Serie INA no habilitada')
    try:
        days = int(days)
    except (TypeError, ValueError):
        raise ValueError('Días inválidos')
    if series == '25500':
        span = int(years or 30) * 365
    else:
        span = days
    if not 1 <= span <= 40 * 366:
        raise ValueError('Período fuera de rango')
    end = _now(); start = end - timedelta(days=span)
    url = 'https://alerta.ina.gob.ar/pub/datos/datos'
    return external(url, {'timeStart': start.strftime('%Y-%m-%d'), 'timeEnd': end.strftime('%Y-%m-%d'),
                          'seriesId': series, 'siteCode': '', 'format': 'json'},
                    scope=f'serie INA {series} · {INA_SERIES[series]}', organism='INA (Argentina)')


def usgs_water(lat, lon, site=None):
    """USGS Water Data OGC API. Sin cobertura fuera de EE.UU."""
    base = 'https://api.waterdata.usgs.gov/ogcapi/v0/collections/latest-continuous/items'
    params = {'f': 'json', 'limit': 50}
    if site:
        if not re.fullmatch(r'USGS-\d{8,15}', site):
            raise ValueError('Estación USGS inválida (ej. USGS-06887000)')
        params['monitoring_location_id'] = site
    else:
        params['bbox'] = ','.join(f'{x:.5f}' for x in _bbox(lat, lon, None, 0.5))
    return external(base, params, scope='lecturas continuas USGS', organism='USGS Water Data')


# ───────────────────────────── satélite / catálogos ─────────────────────────────
def _stac(base, bbox, collections=None, limit=5, days=30, extra=None):
    end = _now(); start = end - timedelta(days=days)
    body = {'bbox': bbox, 'limit': limit,
            'datetime': f'{start.strftime("%Y-%m-%dT%H:%M:%SZ")}/{end.strftime("%Y-%m-%dT%H:%M:%SZ")}'}
    if collections:
        body['collections'] = collections
    if extra:
        body.update(extra)
    return _post(base.rstrip('/') + '/search', body).json()


def scenes(lat, lon, polygon=None):
    """Sentinel-2 L2A vía Earth Search (el único host de miniaturas que acepta /foto)."""
    pts = _poly(polygon)
    url = 'https://earth-search.aws.element84.com/v1'
    data = _stac(url, _bbox(lat, lon, pts), ['sentinel-2-l2a'], limit=8, days=45,
                 extra={'sortby': [{'field': 'properties.datetime', 'direction': 'desc'}]})
    return envelope(data, url + '/search', 'catálogo Sentinel-2 L2A (metadatos, no raster procesado)',
                    'Element84 Earth Search / ESA')


def stac_search(base, lat, lon, collection, limit=5, polygon=None, days=30):
    pts = _poly(polygon)
    data = _stac(base, _bbox(lat, lon, pts), [collection], limit=limit, days=days)
    return envelope(data, base.rstrip('/') + '/search', f'catálogo {collection}', base.split('/')[2])


def satellite_catalogue(lat, lon, radar=False):
    if radar:
        return stac_search('https://stac.dataspace.copernicus.eu/v1', lat, lon, 'sentinel-1-grd', 5, None, 30)
    return stac_search('https://planetarycomputer.microsoft.com/api/stac/v1', lat, lon,
                       'landsat-c2-l2', 5, None, 90)


def _open_stac(base, lat, lon, name):
    data = _stac(base, _bbox(lat, lon, None, 0.25), None, limit=5, days=60)
    return envelope(data, base.rstrip('/') + '/search', 'catálogo STAC', name)


def cnes_stac(lat, lon):
    return _open_stac('https://geodes-portal.cnes.fr/api/stac', lat, lon, 'CNES GEODES (Francia)')


def dlr_stac(lat, lon):
    return _open_stac('https://geoservice.dlr.de/eoc/ogc/stac/v1', lat, lon, 'DLR EOC (Alemania)')


def deafrica_stac(lat, lon):
    return _open_stac('https://explorer.digitalearth.africa/stac', lat, lon, 'Digital Earth Africa')


def nasa_catalogue(lat, lon, product='MOD13Q1'):
    if not re.fullmatch(r'[A-Za-z0-9_.]{3,20}', product or ''):
        raise ValueError('Producto NASA inválido')
    w, s, e, n = _bbox(lat, lon, None, 0.25)
    return external('https://cmr.earthdata.nasa.gov/search/granules.json', {
        'short_name': product, 'bounding_box': f'{w},{s},{e},{n}', 'page_size': 5, 'sort_key': '-start_date'},
        scope=f'granos {product} (metadatos)', organism='NASA CMR')


def nasa_gibs_capabilities():
    url = 'https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/1.0.0/WMTSCapabilities.xml'
    r = _get(url, timeout=30)
    ids = re.findall(r'<ows:Identifier>([^<]+)</ows:Identifier>', r.text)
    return envelope({'http_status': r.status_code, 'identifiers': len(ids), 'sample': ids[:12]},
                    url, 'capacidades WMTS (capas)', 'NASA GIBS')


WMS = {'inta-suelos-wms': 'https://geoservicios.inta.gob.ar/geoserver/wms'}  # URL a verificar


def ogc_capabilities(name):
    if name not in WMS:
        raise ValueError('Servicio OGC no habilitado')
    r = _get(WMS[name], {'service': 'WMS', 'request': 'GetCapabilities'}, timeout=30)
    if '<WMS_Capabilities' not in r.text and '<WMT_MS_Capabilities' not in r.text:
        raise ValueError('Respuesta WMS inválida')
    layers = re.findall(r'<Name>([^<]+)</Name>', r.text)
    return envelope({'layers': len(layers), 'sample': layers[:12]}, WMS[name], 'capacidades WMS', 'INTA')


def firms(lat, lon, polygon=None, days=3):
    key = os.environ.get('FIRMS_MAP_KEY')
    if not key:
        raise ValueError('requiere credencial: FIRMS_MAP_KEY')
    pts = _poly(polygon)
    w, s, e, n = _bbox(lat, lon, pts, 0.25)
    path = f'https://firms.modaps.eosdis.nasa.gov/api/area/csv/{{KEY}}/VIIRS_SNPP_NRT/{w:.4f},{s:.4f},{e:.4f},{n:.4f}/{int(days)}'
    r = _get(path.replace('{KEY}', key), timeout=25)
    rows = list(csv.DictReader(io.StringIO(r.text)))
    det = []
    for row in rows:
        try:
            la, lo = float(row['latitude']), float(row['longitude'])
        except (KeyError, ValueError):
            continue
        det.append({'latitude': la, 'longitude': lo, 'satellite': row.get('satellite'),
                    'acq_date': row.get('acq_date'), 'acq_time': row.get('acq_time'),
                    'frp': row.get('frp'), 'confidence': row.get('confidence'),
                    'bright_ti4': row.get('bright_ti4'),
                    'inside_lot': point_in_polygon(la, lo, pts) if pts else None})
    # la clave NUNCA se devuelve: source_url lleva el marcador
    return envelope({'detections': det, 'sensor': 'VIIRS S-NPP NRT', 'days': int(days)},
                    path.replace('{KEY}', 'MAP_KEY'), 'detecciones térmicas', 'NASA FIRMS')


# ───────────────────────────── ENSO ─────────────────────────────
def _noaa_oni():
    url = 'https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt'
    r = _get(url)
    rows = [l.split() for l in r.text.strip().splitlines()[1:] if len(l.split()) >= 4]
    seas, yr, _, anom = rows[-1][:4]
    oni = float(anom)
    phase = 'El Niño' if oni >= 0.5 else 'La Niña' if oni <= -0.5 else 'Neutro'
    return envelope({'oni': oni, 'phase': phase, 'season': seas, 'year': yr}, url, 'ENSO oficial', 'NOAA CPC')


def _bom_soi():
    url = 'http://www.bom.gov.au/climate/enso/soi.txt'
    r = _get(url)
    return envelope({'http_status': r.status_code, 'bytes': len(r.content)}, url,
                    'disponibilidad SOI (no se interpreta valor)', 'BOM Australia')


def _iri():
    url = 'https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/'
    r = _get(url)
    return envelope({'http_status': r.status_code, 'bytes': len(r.content)}, url,
                    'disponibilidad pronóstico ENSO (no se interpreta valor)', 'IRI Columbia')


def enso_multisource():
    out = {}
    def _psl():
        import climate_indices as ci
        return ci.psl_indices()
    for name, fn in (('NOAA_ONI', _noaa_oni), ('BOM_SOI', _bom_soi), ('IRI_forecast', _iri), ('NOAA_PSL', _psl)):
        try:
            out[name] = fn()
        except Exception as e:
            out[name] = envelope({}, None, 'ENSO', name, 'sin dato', f'{type(e).__name__}')
    ok = sum(1 for v in out.values() if v['status'] == 'recibido')
    return envelope(out, 'multi', 'ENSO · NOAA CPC + NOAA PSL + BOM + IRI (WMO y JMA aún no conectados)',
                    'NOAA · BOM · IRI', 'recibido' if ok else 'sin dato',
                    None if ok else 'Ninguna fuente ENSO respondió')


# ───────────────────────────── agencias nacionales ─────────────────────────────
def _obs(variable, station, dist, value, unit, when, quality=None):
    return {'variable': variable, 'station': station, 'distance_km': round(dist, 1),
            'value': value, 'unit': unit, 'observed_at': when, 'quality': quality}


def _smn(lat, lon):
    if not (-56 <= lat <= -21 and -74 <= lon <= -53):
        return envelope({'agency': 'SMN Argentina', 'scope': 'La ubicación está fuera de Argentina; no se sustituye por datos de otro país.',
                         'observations': []}, 'https://ws.smn.gob.ar/map_items/weather', 'observación', 'SMN')
    url = 'https://ws.smn.gob.ar/map_items/weather'
    rows = _get(url).json()
    near = []
    for st in rows:
        try:
            d = _km(lat, lon, float(st['lat']), float(st['lon']))
        except (KeyError, TypeError, ValueError):
            continue
        near.append((d, st))
    near.sort(key=lambda x: x[0])
    obs = []
    for d, st in near[:3]:
        w = st.get('weather') or {}
        when = st.get('updated')
        name = st.get('name')
        for var, key, unit in (('Temperatura', 'temp', '°C'), ('Humedad', 'humidity', '%'),
                               ('Viento', 'wind_speed', 'km/h'), ('Presión', 'pressure', 'hPa')):
            if w.get(key) is not None:
                obs.append(_obs(var, name, d, w[key], unit, when))
    return envelope({'agency': 'Servicio Meteorológico Nacional (Argentina)',
                     'scope': 'Observación de las 3 estaciones más cercanas', 'observations': obs},
                    url, 'observación', 'SMN Argentina')


def nws(lat, lon):
    base = 'https://api.weather.gov'
    hdr = {'Accept': 'application/geo+json'}
    try:
        pt = _get(f'{base}/points/{lat:.4f},{lon:.4f}', headers=hdr).json()
    except requests.HTTPError:
        return envelope({'agency': 'NOAA / National Weather Service',
                         'scope': 'NWS solo cubre EE.UU.; no se sustituye por datos de otro país.',
                         'observations': []}, base, 'observación', 'NWS')
    stations = _get(pt['properties']['observationStations'], headers=hdr).json().get('features', [])[:3]
    obs = []
    for st in stations:
        sp = st['properties']; c = st['geometry']['coordinates']
        d = _km(lat, lon, c[1], c[0])
        try:
            last = _get(f'{base}/stations/{sp["stationIdentifier"]}/observations/latest', headers=hdr).json()['properties']
        except Exception:
            continue
        for var, key, unit in (('Temperatura', 'temperature', '°C'), ('Humedad', 'relativeHumidity', '%'),
                               ('Viento', 'windSpeed', 'km/h')):
            v = (last.get(key) or {}).get('value')
            if v is not None:
                obs.append(_obs(var, sp.get('name'), d, round(v, 1), unit, last.get('timestamp')))
    return envelope({'agency': 'NOAA / National Weather Service', 'scope': 'Estaciones cercanas (EE.UU.)',
                     'observations': obs}, base, 'observación', 'NWS')


def met_norway(lat, lon):
    return external('https://api.met.no/weatherapi/locationforecast/2.0/compact',
                    {'lat': round(lat, 4), 'lon': round(lon, 4)},
                    scope='pronóstico modelado', organism='MET Norway (CC BY 4.0)')


def national(key, lat, lon):
    if key == 'smn':
        return _smn(lat, lon)
    if key == 'nws':
        return nws(lat, lon)
    raise ValueError(f'El conector de la agencia "{key}" todavía no está implementado; '
                     'no se sustituye por datos de otro país.')


# ───────────────────────────── credenciales / registro ─────────────────────────────
CRED = {
    'era5-cds': ['CDS_API_KEY'], 'sentinel-hub': ['CDSE_CLIENT_ID', 'CDSE_CLIENT_SECRET'],
    'noaa-cdo': ['NOAA_CDO_TOKEN'], 'usgs-m2m': ['USGS_USERNAME', 'USGS_TOKEN'],
    'nasa-earthdata': ['EARTHDATA_TOKEN'],
    'copernicus-marine': ['COPERNICUS_MARINE_USERNAME', 'COPERNICUS_MARINE_PASSWORD'],
    'gee': ['GOOGLE_CLOUD_PROJECT', 'GOOGLE_APPLICATION_CREDENTIALS_JSON'],
    'openaq': ['OPENAQ_API_KEY'], 'gfw': ['GFW_API_KEY'], 'aemet': ['AEMET_API_KEY'],
    'eumetsat': ['EUMETSAT_CONSUMER_KEY', 'EUMETSAT_CONSUMER_SECRET'],
    'jaxa': ['JAXA_USERNAME', 'JAXA_PASSWORD'], 'mosdac': ['MOSDAC_USERNAME', 'MOSDAC_PASSWORD'],
    'kma': ['KMA_AUTH_KEY'], 'fengyun': ['FENGYUN_USERNAME', 'FENGYUN_PASSWORD'],
}


def credential_status(key):
    """Una fuente protegida NO es operativa por tener la variable cargada.
    Sólo noaa-cdo y openaq hacen una consulta real de validación."""
    if key not in CRED:
        raise ValueError('Fuente protegida desconocida')
    missing = [v for v in CRED[key] if not os.environ.get(v)]
    if missing:
        return envelope({'status': 'requiere credencial', 'missing_env': missing}, None,
                        'estado de integración', key)
    if key == 'noaa-cdo':
        _get('https://www.ncei.noaa.gov/cdo-web/api/v2/datasets', {'limit': 1},
             {'token': os.environ['NOAA_CDO_TOKEN']})
        return envelope({'status': 'VALIDADA · consulta real exitosa', 'missing_env': []}, None, 'estado de integración', key)
    if key == 'openaq':
        _get('https://api.openaq.org/v3/locations', {'limit': 1}, {'X-API-Key': os.environ['OPENAQ_API_KEY']})
        return envelope({'status': 'VALIDADA · consulta real exitosa', 'missing_env': []}, None, 'estado de integración', key)
    return envelope({'status': 'credencial detectada · sin validar end-to-end', 'missing_env': []}, None,
                    'estado de integración', key)


def platform_registry():
    s = [
        ('open-meteo', 'Open-Meteo', 'REST', 'analysis', 'OPEN'),
        ('nasa-power', 'NASA POWER', 'REST', 'analysis', 'OPEN'),
        ('nasa-gibs', 'NASA GIBS', 'WMS/WMTS', 'imagery', 'OPEN'),
        ('copernicus-stac', 'Copernicus Data Space STAC', 'STAC', 'catalog', 'OPEN'),
        ('earth-search', 'Element84 Earth Search', 'STAC', 'catalog', 'OPEN'),
        ('soilgrids', 'ISRIC SoilGrids', 'REST', 'analysis', 'OPEN'),
        ('pc-ndvi', 'Planetary Computer Data API · NDVI por lote', 'STAC + TiTiler (statistics/feature)', 'raster-analysis', 'OPEN'),
        ('sentinel-hub', 'Sentinel Hub', 'OAuth2 + Process API', 'raster-analysis', 'REQUIRES_CREDENTIAL'),
        ('openeo-cdse', 'openEO Copernicus Data Space', 'OAuth2 + openEO /result', 'raster-analysis', 'REQUIRES_CREDENTIAL'),
        ('gee', 'Google Earth Engine', 'OAuth2 service account + REST value:compute', 'raster-analysis', 'REQUIRES_CREDENTIAL'),
        ('era5-cds', 'ERA5 / CDS', 'REST (cdsapi)', 'reanalysis', 'REQUIRES_CREDENTIAL'),
        ('nasa-firms', 'NASA FIRMS', 'REST', 'markers', 'REQUIRES_CREDENTIAL'),
        ('conae-saocom', 'CONAE SAOCOM', 'sin API pública certificada', 'radar', 'NOT_CERTIFIED'),
    ]
    return {'generated_at': _now().isoformat(),
            'sources': [{'id': i, 'name': n, 'protocol': p, 'capability': c, 'status': st} for i, n, p, c, st in s]}


def _src(fn):
    try:
        return {'status': 'recibido', 'payload': fn()}
    except Exception as e:
        return {'status': 'sin dato', 'error': f'{type(e).__name__}: {str(e)[:160]}'}


def research_bundle(lat, lon, ina_id=None):
    jobs = {'clima': lambda: variables(lat, lon),
            'suelo_completo': lambda: external(
                'https://rest.isric.org/soilgrids/v2.0/properties/query',
                {'lat': lat, 'lon': lon, 'property': ['nitrogen', 'clay', 'sand', 'silt', 'soc', 'phh2o', 'bdod'],
                 'depth': ['0-5cm', '5-15cm', '15-30cm'], 'value': 'mean'},
                scope='suelo modelado (no sustituye laboratorio)', organism='ISRIC SoilGrids')}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = {k: pool.submit(_src, fn) for k, fn in jobs.items()}
        return {'sources': {k: f.result() for k, f in futs.items()}, 'ina_id': ina_id}
