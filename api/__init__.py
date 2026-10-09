"""Paquete api. La entrada real de Vercel es api/index.py (Flask).

v1.9: se quitó el import de api/main.py (FastAPI v1.5, sin fastapi en requirements),
que rompía cualquier `import api.*` y los tests de rutas.
"""
import os
import sys

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)
