"""Telemetría agrícola modelada de Open-Meteo para coordenadas elegidas.

No es medición de sensor instalado en el lote. Respuestas incluyen procedencia,
unidades y período; no se calculan prescripciones agronómicas automáticas.
"""
from flask import Blueprint, jsonify, request
import requests
import math

agro_telemetry_api = Blueprint("agro_telemetry_api", __name__)
ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"
VARIABLES = (
    "temperature_2m_mean", "relative_humidity_2m_mean", "precipitation_sum",
    "et0_fao_evapotranspiration", "shortwave_radiation_sum",
    "wind_speed_10m_max", "soil_moisture_0_to_7cm_mean",
    "soil_moisture_7_to_28cm_mean",
)

@agro_telemetry_api.get("/api/agro/telemetria")
def telemetria():
    from datetime import date, timedelta
    try:
        lat = float(request.args["lat"])
        lon = float(request.args["lon"])
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("coordenadas fuera de rango")
        end = date.fromisoformat(request.args.get("end", (date.today()-timedelta(days=7)).isoformat()))
        start = date.fromisoformat(request.args.get("start", (end-timedelta(days=29)).isoformat()))
        if end < start or (end-start).days > 366 or end >= date.today():
            raise ValueError("período inválido; máximo 367 días y sin fechas futuras")
    except (KeyError, ValueError) as exc:
        return jsonify(error="Indicar lat/lon y período válidos", detail=str(exc)), 400
    try:
        response = requests.get(ENDPOINT, params={
            "latitude": lat, "longitude": lon,
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "daily": ",".join(VARIABLES), "timezone": "auto",
        }, timeout=25)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload.get("daily"), dict) or not isinstance(payload["daily"].get("time"), list):
            raise ValueError("Respuesta sin datos diarios")
        return jsonify(
            status="ok", provider="Open-Meteo Historical Weather API",
            source=ENDPOINT, data_kind="reanálisis/modelo interpolado; no sensor de campo",
            location={"lat": lat, "lon": lon},
            period={"start": start.isoformat(), "end": end.isoformat()},
            daily=payload["daily"], daily_units=payload.get("daily_units", {}),
            limitations=["Cobertura y variables dependen del modelo y ubicación",
                         "ET0 no equivale a requerimiento de riego del cultivo",
                         "La humedad del suelo modelada no sustituye una sonda calibrada"],
        )
    except (requests.RequestException, ValueError) as exc:
        return jsonify(error="Fuente meteorológica no disponible", detail=type(exc).__name__), 503
