"""Entrypoint para Vercel - FastAPI"""
import sys
import os

# Agregar la carpeta api al path para que encuentre los módulos
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# Importar la app FastAPI desde main
from api.main import app

# Vercel necesita 'handler' como variable de nivel superior
handler = app
