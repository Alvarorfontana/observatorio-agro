"""Entrypoint para Vercel - exporta la app FastAPI"""
import sys
import os

# Agregar la raíz del proyecto al path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# Importar la app desde main.py
from api.main import app

# Vercel necesita 'handler' como alias
handler = app
