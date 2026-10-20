"""IRI Columbia ENSO bulletin: safe source discovery without invented probabilities.

The IRI public bulletin is HTML and may change its layout. This endpoint
does not scrape numeric probabilities unless an explicitly versioned machine
readable feed is added and tested. Links are live and attributed.
"""
from datetime import datetime, timezone
from flask import Blueprint, jsonify

iri_enso_api = Blueprint("iri_enso_api", __name__)
IRI_URL = "https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/"

@iri_enso_api.get("/api/enso/iri")
def iri_catalog():
    return jsonify({
        "status": "catalogado",
        "provider": "International Research Institute for Climate and Society, Columbia University",
        "source_url": IRI_URL,
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "kind": "pronóstico",
        "numeric_forecast_connected": False,
        "products": [
            {"id": "plume", "name": "Pluma multimodelo ENSO", "url": IRI_URL},
            {"id": "probabilities", "name": "Probabilidades El Niño / Neutral / La Niña", "url": IRI_URL},
            {"id": "quicklook", "name": "ENSO Quick Look", "url": IRI_URL},
        ],
        "method": "Catálogo de acceso a los pronósticos públicos IRI. No ingesta numérica validada.",
        "limitations": [
            "No se atribuyen probabilidades ni fechas de pronóstico sin verificar el producto original.",
            "Los pronósticos multimodelo no son observaciones.",
        ],
    })
