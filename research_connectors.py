"""Conectores reales a APIs externas verificadas.
Respeta v1.5: fuentes protegidas marcadas como 'requiere credencial'.
"""
import os
import requests
from datetime import datetime, timezone, timedelta

FIRMS_MAP_KEY = os.environ.get('FIRMS_MAP_KEY')

def _envelope(status, data=None, error=None, source_url=None, scope=None):
    return {
        'status': status,
        'data': data or {},
        'error': error,
        'consulted_at': datetime.now(timezone.utc).isoformat(),
        'source_url': source_url,
        'scope': scope
    }

def _open_meteo(lat, lon):
    url = 'https://api.open-meteo.com/v1/forecast'
    params = {
        'latitude': lat, 'longitude': lon,
        'current': 'temperature_2m,relative_humidity_2m',
        'hourly': 'soil_moisture_0_to_1cm',
        'daily': 'precipitation_sum,et0_fao_evapotranspiration',
        'timezone': 'auto', 'forecast_days': 7
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return _envelope('recibido', r.json(), source_url=url, scope='clima+ET0+humedad')
    except Exception as e:
        return _envelope('sin dato', error=str(e), source_url=url, scope='clima')

def _soilgrids_nitrogen(lat, lon):
    url = 'https://rest.isric.org/soilgrids/v2.0/properties/query'
    params = {'lat': lat, 'lon': lon, 'property': 'nitrogen', 'depth': '0-5cm', 'value': 'mean'}
    try:
        r = requests.get(url, params=params, timeout=15, headers={'Accept': 'application/json'})
        r.raise_for_status()
        return _envelope('recibido', r.json(), source_url=url, scope='suelo-nitrogeno')
    except Exception as e:
        return _envelope('sin dato', error=str(e), source_url=url, scope='suelo-nitrogeno')

def _nasa_firms(lat, lon, days=3):
    if not FIRMS_MAP_KEY:
        return _envelope('sin dato', error='requiere credencial: FIRMS_MAP_KEY',
                         source_url='https://firms.modaps.eosdis.nasa.gov/api/', scope='incendios')
    url = f'https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_MAP_KEY}/VIIRS_SNPP_NRT/{lon},{lat},50/{days}'
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        lines = [l for l in r.text.strip().split('\n') if l.strip()]
        if len(lines) < 2:
            return _envelope('recibido', {'detections': [], 'sensor': 'VIIRS', 'days': days},
                             source_url=url, scope='incendios')
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
                         source_url=url, scope='incendios')
    except Exception as e:
        return _envelope('sin dato', error=str(e),
                         source_url='https://firms.modaps.eosdis.nasa.gov/api/', scope='incendios')

def _sentinel_scenes(lat, lon, max_results=5):
    url = 'https://catalogue.dataspace.copernicus.eu/stac/search'
    bbox = [lon - 0.1, lat - 0.1, lon + 0.1, lat + 0.1]
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30)
    payload = {
        'collections': ['sentinel-2-l2a'],
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
        return _envelope('recibido', data, source_url=url, scope='sentinel-2-catalogo')
    except Exception as e:
        return _envelope('sin dato', error=str(e), source_url=url, scope='sentinel-2-catalogo')

def _enso_multisource():
    results = {}
    try:
        url = 'https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt'
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        lines = [l for l in r.text.strip().split('\n') if l.strip()]
        last = lines[-1].split() if lines else []
        if len(last) >= 6:
            oni = float(last[-1])
            results['NOAA_ONI'] = {
                'status': 'recibido', 'oni': oni,
                'phase': 'El Niño' if oni >= 0.5 else 'La Niña' if oni <= -0.5 else 'Neutro',
                'source_url': url
            }
    except Exception as e:
        results['NOAA_ONI'] = {'status': 'sin dato', 'error': str(e)}
    return _envelope('recibido' if any(v.get('status') == 'recibido' for v in results.values()) else 'sin dato',
                     data=results, source_url='multi', scope='enso')

def _flood_api(lat, lon):
    url = 'https://flood-api.open-meteo.com/v1/flood'
    params = {'latitude': lat, 'longitude': lon, 'daily': 'river_discharge', 'forecast_days': 7}
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return _envelope('recibido', r.json(), source_url=url, scope='rios')
    except Exception as e:
        return _envelope('sin dato', error=str(e), source_url=url, scope='rios')

def research_bundle(lat, lon, ina_id=None):
    clima = _open_meteo(lat, lon)
    return {'sources': {'clima': clima}, 'ina_id': ina_id}

def external(url, params):
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return _envelope('recibido', r.json(), source_url=url, scope='generic')
    except Exception as e:
        return _envelope('sin dato', error=str(e), source_url=url, scope='generic')

def scenes(lat, lon):
    return _sentinel_scenes(lat, lon)

def firms(lat, lon):
    return _nasa_firms(lat, lon)

def enso_multisource():
    return _enso_multisource()
