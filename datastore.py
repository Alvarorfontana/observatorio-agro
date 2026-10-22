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
# Si el repositorio es privado, la lectura pública falla: con una clave de solo lectura se lee por la API de GitHub.
READ_TOKEN_VARS = ('DOTS_DATA_READ_TOKEN', 'DOTS_DATA_TOKEN')
BRANCH = os.environ.get('DOTS_DATA_BRANCH', 'datos')
LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
TTL = 900
_CACHE = {}


def _read_token():
    return next((os.environ[v] for v in READ_TOKEN_VARS if os.environ.get(v)), None)


def fetch_bytes(path, branch=None):
    """Archivo de la rama de datos (ruta dentro de data/). Primero por la vía pública; si falla, con la clave."""
    try:
        r = c.SESSION.get(f'https://raw.githubusercontent.com/{REPO}/{branch or BRANCH}/data/{path}', timeout=8)
        if r.status_code == 200:
            return r.content
    except Exception:
        pass
    tok = _read_token()
    if not tok:
        return None
    try:
        r = c.SESSION.get(f'https://api.github.com/repos/{REPO}/contents/data/{path}', params={'ref': branch or BRANCH},
                          headers={'Authorization': f'Bearer {tok}', 'Accept': 'application/vnd.github.raw'}, timeout=10)
        return r.content if r.status_code == 200 else None
    except Exception:
        return None


def load(name, default=None, branch=None, ttl=TTL):
    key = f'{branch or BRANCH}/{name}'
    hit = _CACHE.get(key)
    if hit and time.monotonic() - hit[0] < ttl:
        return hit[1]
    data = None
    raw = fetch_bytes(name, branch)
    if raw:
        try:
            data = json.loads(raw)
        except ValueError:
            data = None
    if data is None:
        try:
            with open(os.path.join(LOCAL, name), encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = default
    if data is not None:
        _CACHE[key] = (time.monotonic(), data)
    return data
