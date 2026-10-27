"""Entrada única para Vercel (Flask). Registra el Blueprint /api/fuentes."""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from flask import Flask, jsonify
from research_routes import research_api   # si algo falla acá, falla fuerte (no se esconde)
from lotes_store import lotes_api
from enso_data_api import enso_data_api
from enso_forecast_api import enso_forecast_api
from agro_telemetry_api import agro_telemetry_api
try:
    from poblacion.routes import bp as population_bp
except ImportError:   # el módulo de población necesita pyclipper
    population_bp = None
import security
import vitrina
from copernicus_routes import copernicus_api

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
app.register_blueprint(research_api)
app.register_blueprint(lotes_api)
app.register_blueprint(enso_data_api)
app.register_blueprint(enso_forecast_api)
app.register_blueprint(agro_telemetry_api)
app.register_blueprint(copernicus_api)
if population_bp is not None:
    app.register_blueprint(population_bp)
security.install(app)
vitrina.install(app)   # modo vitrina (DOTS_VITRINA=1): se ve, pero las consultas son por invitación


@app.get('/api/health')
def health():
    return jsonify({'status': 'ok', 'app': 'DOTS Campo API'})
