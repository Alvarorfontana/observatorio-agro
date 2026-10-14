"""datastore — datos que actualizan las tareas automáticas, leídos sin volver a publicar la web.

Las tareas de GitHub Actions (El Niño, avisos, umbrales de calor, normales de la cuenca) guardan sus archivos en la
rama `datos` del repositorio público. La web los lee de ahí (raw.githubusercontent.com, en caché 15 minutos) y, si
no responde, usa la copia que viaja con la última publicación (carpeta data/). Así un dato nuevo no consume una
publicación de Vercel, que en el plan gratuito tiene un tope diario.
"""
import json
import os
import time

import research_connectors as c

REPO = os.environ.get('DOTS_DATA_PUBLIC_REPO', 'Alvarorfontana/observatorio-agro')
BRANCH = os.environ.get('DOTS_DATA_BRANCH', 'datos')
LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
TTL = 900
_CACHE = {}


def load(name, default=None):
    hit = _CACHE.get(name)
    if hit and time.monotonic() - hit[0] < TTL:
        return hit[1]
    data = None
    try:
        r = c.SESSION.get(f'https://raw.githubusercontent.com/{REPO}/{BRANCH}/data/{name}', timeout=8)
        if r.status_code == 200:
            data = r.json()
    except Exception:
        data = None
    if data is None:
        try:
            with open(os.path.join(LOCAL, name), encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = default
    if data is not None:
        _CACHE[name] = (time.monotonic(), data)
    return data
