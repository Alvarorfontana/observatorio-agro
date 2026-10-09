"""Entrada única Vercel (Flask), compatible con rutas existentes y OpenFarm."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from flask import Flask, jsonify, request
from research_routes import research_api

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
app.register_blueprint(research_api)


@app.get('/api/health')
def health():
    return jsonify({'status': 'ok', 'app': 'DOTS Campo API'})


@app.get('/api/fuentes/openfarm/status')
def openfarm_status():
    return jsonify({'service': 'dots-openfarm-adapter', 'status': 'ready', 'satellite': 'not_configured'})


@app.get('/api/fuentes/openfarm/weather')
def openfarm_weather():
    from urllib.parse import urlencode
    from urllib.request import urlopen
    import json
    import math

    try:
        lat = float(request.args['lat'])
        lon = float(request.args['lon'])
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError('Coordinates out of range')
    except (KeyError, ValueError, TypeError):
        return jsonify({'error': 'Provide valid lat (-90..90) and lon (-180..180)'}), 422

    params = urlencode({
        'latitude': lat, 'longitude': lon,
        'current': 'temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m',
        'daily': 'precipitation_sum,temperature_2m_max,temperature_2m_min,et0_fao_evapotranspiration',
        'timezone': 'auto', 'forecast_days': 7,
    })
    try:
        with urlopen('https://api.open-meteo.com/v1/forecast?' + params, timeout=12) as response:
            payload = json.load(response)
    except Exception:
        app.logger.exception('Open-Meteo request failed')
        return jsonify({'error': 'Weather provider unavailable'}), 502
    return jsonify({'provider': 'Open-Meteo', 'coordinates': {'lat': lat, 'lon': lon}, 'data': payload})


@app.post('/api/fuentes/openfarm/polygon/validate')
def openfarm_polygon_validate():
    import math

    body = request.get_json(silent=True)
    geom = body.get('geometry') if isinstance(body, dict) else None
    if not isinstance(geom, dict) or geom.get('type') != 'Polygon':
        return jsonify({'error': 'Expected geometry of type Polygon'}), 422
    rings = geom.get('coordinates')
    if not isinstance(rings, list) or not rings:
        return jsonify({'error': 'Polygon coordinates are required'}), 422
    for ring in rings:
        if not isinstance(ring, list) or len(ring) < 4 or ring[0] != ring[-1]:
            return jsonify({'error': 'Each ring must have 4 or more positions and be closed'}), 422
        for point in ring:
            if (not isinstance(point, list) or len(point) < 2
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in point[:2])
                or not (-180 <= point[0] <= 180 and -90 <= point[1] <= 90)):
                return jsonify({'error': 'Invalid longitude/latitude pair'}), 422
    return jsonify({'valid_structure': True, 'rings': len(rings), 'note': 'Structural validation only; not cadastral or topology validation'})
