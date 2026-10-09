"""Entrada única para Vercel (Flask). Registra el Blueprint /api/fuentes."""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from flask import Flask, jsonify
from research_routes import research_api   # si algo falla acá, falla fuerte (no se esconde)
import security

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
app.register_blueprint(research_api)
security.install(app)


@app.get('/api/health')
def health():
    return jsonify({'status': 'ok', 'app': 'DOTS Campo API'})
