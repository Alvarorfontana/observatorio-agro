"""Adaptador independiente DOTS/OpenFarm: meteorología y geometría."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any
from urllib.request import urlopen
from urllib.parse import urlencode
import json

router = APIRouter()

class PolygonRequest(BaseModel):
    geometry: dict[str, Any]

@router.get('/status')
def status():
    return {'service': 'dots-openfarm-adapter', 'status': 'ready', 'satellite': 'not_configured'}

@router.get('/weather')
def weather(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180)):
    params = urlencode({'latitude': lat, 'longitude': lon, 'current': 'temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m', 'daily': 'precipitation_sum,temperature_2m_max,temperature_2m_min,et0_fao_evapotranspiration', 'timezone': 'auto', 'forecast_days': 7})
    try:
        with urlopen('https://api.open-meteo.com/v1/forecast?' + params, timeout=12) as response:
            payload = json.load(response)
        return {'provider': 'Open-Meteo', 'coordinates': {'lat': lat, 'lon': lon}, 'data': payload}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f'Weather provider unavailable: {type(exc).__name__}') from exc

@router.post('/polygon/validate')
def validate_polygon(request: PolygonRequest):
    geom = request.geometry
    if geom.get('type') != 'Polygon':
        raise HTTPException(422, 'Only GeoJSON Polygon geometry is supported')
    rings = geom.get('coordinates')
    if not isinstance(rings, list) or not rings or not isinstance(rings[0], list):
        raise HTTPException(422, 'Polygon coordinates are required')
    for ring in rings:
        if len(ring) < 4 or ring[0] != ring[-1]:
            raise HTTPException(422, 'Each ring must have at least 4 positions and be closed')
        for point in ring:
            if not isinstance(point, list) or len(point) < 2 or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in point[:2]):
                raise HTTPException(422, 'Invalid coordinate pair')
            if not (-180 <= point[0] <= 180 and -90 <= point[1] <= 90):
                raise HTTPException(422, 'Coordinates outside longitude/latitude range')
    return {'valid_structure': True, 'rings': len(rings), 'note': 'Structural validation only; does not test self-intersections, area or cadastral validity'}
