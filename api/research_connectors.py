"""research_connectors.py v2.0 - Conectores reales a APIs globales."""
import os
import requests
from datetime import datetime, timezone, timedelta

FIRMS_MAP_KEY = os.environ.get('FIRMS_MAP_KEY')
CDS_API_KEY = os.environ.get('CDS_API_KEY')
NOAA_CDO_TOKEN = os.environ.get('NOAA_CDO_TOKEN')

def _envelope(status, data=None, error=None, source_url=None, scope=None, organism=None):
    return {
        'status': status,
        'data': data or {},
        'error': error,
        'consulted_at': datetime.now(timezone.utc).isoformat(),
        'source_url': source_url,
        'scope': scope,
        'organism': organism
    }

def _safe_get(url, params=None, headers=None, timeout=15):
    r = requests.get(url, params=params or {}, headers=headers or {}, timeout=timeout)
    r.raise_for_status()
    return r

def open_meteo_forecast(lat, lon):
    url = 'https://api.open-meteo.com/v1/forecast'
    params = {
        'latitude': lat, 'longitude': lon,
        'current': 'temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code',
        'hourly': 'soil_moisture_0_to_1cm,soil_moisture_1_to_3cm',
        'daily': 'precipitation_sum,et0_fao_evapotranspiration,temperature_2m_max,temperature_2m_min',
        'timezone': 'auto', 'forecast_days': 7
    }
    try:
        r = _safe_get(url, params)
        return _envelope('recibido', r.json(), source_url=url,
                         scope='clima+ET0+humedad+viento', organism='Open-Meteo (Austria)')
    except Exception as e:
        return _envelope('sin dato', error=str(e), source_url=url, scope='clima', organism='Open-Meteo')

def soilgrids_properties(lat, lon):
    url = 'https://rest.isric.org/soilgrids/v2.0/properties/query'
    params = {
        'lat': lat, 'lon': lon,
        'property': 'nitrogen,clay,sand,silt,soc,phh2o,bdod',
        'depth': '0-5cm,5-15cm,15-30cm',
        'value': 'mean'
    }
    try:
        r = _safe_get(url, params, headers={'Accept': 'application/json'})
        return _envelope('recibido', r.json(), source_url=url,
                         scope='suelo completo', organism='ISRIC SoilGrids (Países Bajos)')
    except Exception as e:
        return _envelope('sin dato', error=str(e), source_url=url, scope='suelo', organism='ISRIC SoilGrids')

def nasa_firms(lat, lon, days=3):
    if not FIRMS_MAP_KEY:
        return _envelope('sin dato', error='requiere credencial: FIRMS_MAP_KEY',
                         source_url='https://firms.modaps.eosdis.nasa.gov/api/',
                         scope='incendios', organism='NASA FIRMS')
    url = f'https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_MAP_KEY}/VIIRS_SNPP_NRT/{lon},{lat},50/{days}'
    try:
        r = _safe_get(url, timeout=20)
        lines = [l for l in r.text.strip().split('\n') if l.strip()]
        if len(lines) < 2:
            return _envelope('recibido', {'detections': [], 'sensor': 'VIIRS', 'days': days},
                             source_url=url, scope='incendios', organism='NASA FIRMS')
        header = lines[0].split(',')
        detections = []
        for line in lines[1:]:
            fields = line.split(',')
            if len(fields) >= len(header):
                row = dict(zip(header, fields))
                detections.append({
                    'latitude': row.get('latitude'), 'longitude': row.get('longitude'),
                    'brightness': row.get('brightness'), 'acq_date': row.get('acq_date'),
                    'confidence': row.get('confidence')
                })
        return _envelope('recibido', {'detections': detections, 'sensor': 'VIIRS', 'days': days},
                         source_url=url, scope='incendios', organism='NASA FIRMS')
    except Exception as e:
        return _envelope('sin dato', error=str(e), source_url=url, scope='incendios', organism='NASA FIRMS')

def copernicus_stac_scenes(lat, lon, collection='sentinel-2-l2a', max_results=5):
    url = 'https://catalogue.dataspace.copernicus.eu/stac/search'
    bbox = [lon - 0.1, lat - 0.1, lon + 0.1, lat + 0.1]
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30)
    payload = {
        'collections': [collection],
        'bbox': bbox,
        'datetime': f'{start.isoformat()}/{end.isoformat()}',
        'limit': max_results,
        'sortby': [{'field': 'datetime', 'direction': 'desc'}]
    }
    try:
        r = requests.post(url, json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()
        for feat in data.get('features', []):
            props = feat.get('properties', {})
            if 'eo:cloud_cover' not in props and 'cloud_cover' in props:
                props['eo:cloud_cover'] = props['cloud_cover']
        return _envelope('recibido', data, source_url=url,
                         scope=f'catálogo {collection}', organism='Copernicus Data Space (UE)')
    except Exception as e:
        return _envelope('sin dato', error=str(e), source_url=url, scope='catálogo Sentinel', organism='Copernicus Data Space')

def noaa_oni():
    url = 'https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt'
    try:
        r = _safe_get(url, timeout=15)
        lines = [l for l in r.text.strip().split('\n') if l.strip() and not l.startswith(' ')]
        if not lines:
            return _envelope('sin dato', error='sin datos parseables', source_url=url)
        last = lines[-1].split()
        if len(last) < 6:
            return _envelope('sin dato', error='formato inesperado', source_url=url)
        oni = float(last[-1])
        phase = 'El Niño' if oni >= 0.5 else 'La Niña' if oni <= -0.5 else 'Neutro'
        return _envelope('recibido', {
            'oni': oni, 'phase': phase,
            'season': last[1] if len(last) > 1 else None,
            'year': last[0] if len(last) > 0 else None,
            'interpretation': f'ONI {oni:+.2f}°C → {phase}'
        }, source_url=url, scope='ENSO oficial', organism='NOAA CPC (EE.UU.)')
    except Exception as e:
        return _envelope('sin dato', error=str(e), source_url=url, scope='ENSO', organism='NOAA CPC')

def bom_soi():
    url = 'http://www.bom.gov.au/climate/current/soihtml.shtml'
    try:
        r = _safe_get(url, timeout=15)
        return _envelope('recibido', {
            'source_url': url, 'status_http': r.status_code,
            'note': 'consulta de disponibilidad'
        }, source_url=url, scope='SOI', organism='BOM Australia')
    except Exception as e:
        return _envelope('sin dato', error=str(e), source_url=url, scope='SOI', organism='BOM Australia')

def iri_enso_forecast():
    url = 'https://iridl.ldeo.columbia.edu/SOURCES/.NOAA/.NCEP/.CPC/.global/.precip/'
    try:
        r = _safe_get(url, timeout=15)
        return _envelope('recibido', {
            'source_url': url, 'note': 'IRI/Columbia - recursos ENSO',
            'raw_length': len(r.text)
        }, source_url=url, scope='pronóstico estacional ENSO', organism='IRI Columbia (EE.UU.)')
    except Exception as e:
        return _envelope('sin dato', error=str(e), source_url=url, scope='pronóstico ENSO', organism='IRI Columbia')

def usgs_flood_api(lat, lon):
    url = 'https://flood-api.open-meteo.com/v1/flood'
    params = {'latitude': lat, 'longitude': lon, 'daily': 'river_discharge', 'forecast_days': 7}
    try:
        r = _safe_get(url, params)
        return _envelope('recibido', r.json(), source_url=url,
                         scope='caudales', organism='Open-Meteo Flood')
    except Exception as e:
        return _envelope('sin dato', error=str(e), source_url=url, scope='caudales', organism='Flood API')

def research_bundle(lat, lon, ina_id=None):
    clima = open_meteo_forecast(lat, lon)
    suelo = soilgrids_properties(lat, lon)
    return {'sources': {'clima': clima, 'suelo_completo': suelo}, 'ina_id': ina_id}

def external(url, params):
    try:
        r = _safe_get(url, params, timeout=15)
        return _envelope('recibido', r.json(), source_url=url, scope='generic')
    except Exception as e:
        return _envelope('sin dato', error=str(e), source_url=url, scope='generic')

def scenes(lat, lon):
    return copernicus_stac_scenes(lat, lon)

def firms(lat, lon):
    return nasa_firms(lat, lon)

def enso_multisource():
    results = {}
    results['NOAA_ONI'] = noaa_oni()
    results['BOM_SOI'] = bom_soi()
    results['IRI_forecast'] = iri_enso_forecast()
    received = sum(1 for v in results.values() if v.get('status') == 'recibido')
    return _envelope(
        'recibido' if received > 0 else 'sin dato',
        data=results, source_url='multi', scope='enso_multisource', organism='NOAA + BOM + IRI'
    )
