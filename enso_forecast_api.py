"""El Niño: pronósticos y productos que calculan las tareas automáticas (rama datos).

  /api/enso/pronostico  probabilidades oficiales NOAA (RONI), CCSR/IRI, MEI.v2 y pronóstico estacional por localidad
                        (scripts/enso_fuentes.py, todos los días)
  /api/enso/atmosfera   OLR y presión Tahití–Darwin de NOAA PSL (tools/build_enso_atmosphere.py, una vez por mes)
  /api/enso/iri         catálogo de los productos de Columbia (CCSR/IRI) con enlaces y gráficos del mes
Si la tarea todavía no corrió, se dice; no hay datos de ejemplo.
"""
from datetime import datetime, timezone

from flask import Blueprint, jsonify

enso_forecast_api = Blueprint("enso_forecast_api", __name__)

CCSR = "https://forecast.ccsr.columbia.edu/forecasts/enso/forecast"


def _load(name):
    import datastore
    return datastore.load(name, ttl=1800)


@enso_forecast_api.get("/api/enso/pronostico")
def forecast():
    data = _load("enso_pronostico.json")
    if not data:
        return jsonify(estado="sin dato", error="El pronóstico todavía no se calculó: correr la tarea «El Niño: pronósticos»."), 503
    r = jsonify(data)
    r.headers["Cache-Control"] = "public, s-maxage=1800"
    return r


@enso_forecast_api.get("/api/enso/atmosfera")
def atmosphere():
    data = _load("enso-atmosphere.json")
    if not data:
        return jsonify(estado="sin dato", error="Los índices atmosféricos todavía no se calcularon: correr la tarea «ENSO atmósfera NOAA»."), 503
    r = jsonify(data)
    r.headers["Cache-Control"] = "public, s-maxage=3600"
    return r


@enso_forecast_api.get("/api/enso/iri")
def iri_catalog():
    data = _load("enso_pronostico.json") or {}
    c = data.get("ccsr_iri") or {}
    return jsonify({
        "estado": c.get("estado", "catalogado"),
        "proveedor": "Center for Climate Systems Research e IRI, Universidad de Columbia",
        "url": CCSR,
        "emitido": c.get("emitido"),
        "probabilidades": c.get("probabilidades") or [],
        "graficos": c.get("graficos") or {},
        "consultado_utc": datetime.now(timezone.utc).isoformat(),
        "tipo": "pronóstico",
        "productos": [
            {"id": "pluma", "nombre": "Pluma multimodelo de Niño 3.4 (dinámicos y estadísticos)", "url": CCSR},
            {"id": "probabilidades", "nombre": "Probabilidades El Niño / Neutral / La Niña por trimestre", "url": CCSR},
            {"id": "intensidad", "nombre": "Probabilidades por intensidad", "url": CCSR},
        ],
        "limitaciones": ["Los pronósticos multimodelo no son observaciones.",
                         "Las probabilidades se toman tal cual las publica la fuente; DOTS no las recalcula."],
    })


@enso_forecast_api.get("/api/enso/tao")
def tao_section():
    """Corte del Pacífico ecuatorial con las boyas TAO (tarea «El Niño: boyas TAO»)."""
    data = _load("enso_tao.json")
    if not data:
        return jsonify(estado="sin dato", error="El corte de las boyas todavía no se calculó: correr la tarea «El Niño: boyas TAO»."), 503
    r = jsonify(data)
    r.headers["Cache-Control"] = "public, s-maxage=3600"
    return r
