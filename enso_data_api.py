"""NOAA CPC ONI: official overlapping seasonal three-month index.
This adapter does not recalculate ONI from monthly SST and does not claim a
hydrological forecast. Uses short-lived caching to limit NOAA traffic.
"""
import time
import requests
from flask import Blueprint, jsonify

enso_data_api = Blueprint("enso_data_api", __name__)
_NOAA_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
_CACHE = {"at": 0.0, "data": None}
_SEASONS = ("DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ")
_CENTER_MONTH = {"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6, "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12}

def _parse_oni(text):
    points = []
    for line in text.splitlines():
        columns = line.split()
        if len(columns) < 4 or columns[0] not in _SEASONS:
            continue
        try:
            year = int(columns[1])
            anomaly = float(columns[3])
        except (ValueError, IndexError):
            continue
        if not (1950 <= year <= 2100 and -10 < anomaly < 10):
            continue
        month = _CENTER_MONTH[columns[0]]
        points.append({"month": f"{year:04d}-{month:02d}", "season": columns[0], "anomalyC": anomaly})
    points.sort(key=lambda x: x["month"])
    if len(points) < 120:
        raise ValueError("Respuesta NOAA incompleta o formato inesperado")
    return points

@enso_data_api.get("/api/enso/oni")
def oni_official():
    try:
        if _CACHE["data"] is None or time.time() - _CACHE["at"] > 21600:
            response = requests.get(_NOAA_URL, timeout=12, headers={"User-Agent": "DOTS-Campo/1.0 scientific data"})
            response.raise_for_status()
            points = _parse_oni(response.text)
            _CACHE.update({"at": time.time(), "data": points})
        return jsonify({
            "status": "recibido",
            "source": "NOAA Climate Prediction Center",
            "source_url": _NOAA_URL,
            "index": "ONI",
            "method": "Anomalía oficial trimestral móvil por estaciones superpuestas; el criterio operativo de episodios debe revisarse con la metodología NOAA vigente",
            "units": "°C",
            "points": _CACHE["data"],
            "last_month": _CACHE["data"][-1]["month"],
            "updated_from_source": True
        })
    except (requests.RequestException, ValueError) as exc:
        return jsonify({"status": "sin dato", "error": "No fue posible obtener o validar el ONI de NOAA", "detail": type(exc).__name__}), 503
