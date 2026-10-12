"""lotes_store — guarda los lotes en el repositorio PRIVADO de datos y lee los resultados semanales.

El sitio es público; los contornos de campos de productores no. Por eso:
  - los lotes se guardan en un repositorio privado de GitHub (DOTS_DATA_REPO) usando un token
    con permiso de contenido sólo sobre ese repositorio (DOTS_DATA_TOKEN);
  - escribir y leer resultados exige la clave del establecimiento (DOTS_WRITE_KEY), que el dueño
    escribe una vez en el Observatorio. Sin esas variables, todo queda desactivado y la web sigue
    guardando los lotes sólo en el navegador.
"""
import base64, hmac, json, os, re

import requests
from flask import Blueprint, jsonify, request

lotes_api = Blueprint('lotes_api', __name__, url_prefix='/api/lotes')
GH = 'https://api.github.com'
MAX_LOTS = 200
MAX_VERTICES = 600
ID_RE = re.compile(r'^lote-[A-Za-z0-9_-]{4,60}$')


def _cfg():
    return os.environ.get('DOTS_DATA_REPO', ''), os.environ.get('DOTS_DATA_TOKEN', ''), os.environ.get('DOTS_WRITE_KEY', '')


def configured():
    repo, token, key = _cfg()
    return bool(repo and token and key)


def _authorized():
    _, _, key = _cfg()
    given = request.headers.get('X-DOTS-Key', '')
    return bool(key) and hmac.compare_digest(given.encode(), key.encode())


def _headers(raw=False):
    _, token, _ = _cfg()
    return {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github.raw+json' if raw else 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'DOTS-Campo'}


def _read(path):
    """(contenido JSON o None, sha o None)."""
    repo, _, _ = _cfg()
    r = requests.get(f'{GH}/repos/{repo}/contents/{path}', headers=_headers(), timeout=15)
    if r.status_code == 404:
        return None, None
    r.raise_for_status()
    meta = r.json()
    data = json.loads(base64.b64decode(meta.get('content', '')).decode('utf-8') or 'null') if meta.get('content') else None
    if data is None and meta.get('download_url'):
        data = requests.get(f'{GH}/repos/{repo}/contents/{path}', headers=_headers(raw=True), timeout=20).json()
    return data, meta.get('sha')


def _write(path, data, sha, message):
    repo, _, _ = _cfg()
    body = {'message': message, 'content': base64.b64encode(json.dumps(data, ensure_ascii=False, indent=1).encode()).decode()}
    if sha:
        body['sha'] = sha
    r = requests.put(f'{GH}/repos/{repo}/contents/{path}', headers=_headers(), json=body, timeout=20)
    r.raise_for_status()


def clean_lot(lot):
    """Valida un lote y devuelve sólo los campos que se guardan."""
    if not isinstance(lot, dict) or not ID_RE.match(str(lot.get('id', ''))):
        raise ValueError('Lote con identificador inválido')
    vs = lot.get('vertices')
    if not isinstance(vs, list) or not 3 <= len(vs) <= MAX_VERTICES:
        raise ValueError('Lote con vértices inválidos')
    pts = []
    for p in vs:
        lat, lon = float(p[0]), float(p[1])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError('Coordenadas fuera de rango')
        pts.append([round(lat, 7), round(lon, 7)])
    name = str(lot.get('name') or 'Lote')[:120]
    area = lot.get('areaHa')
    return {'id': lot['id'], 'name': name, 'vertices': pts, 'areaHa': round(float(area), 2) if isinstance(area, (int, float)) else None}


def merge_lots(existing, incoming, remove=()):
    by = {l['id']: l for l in (existing or [])}
    for l in incoming:
        by[l['id']] = l
    for rid in remove:
        by.pop(rid, None)
    if len(by) > MAX_LOTS:
        raise ValueError(f'Máximo {MAX_LOTS} lotes por establecimiento')
    return list(by.values())


@lotes_api.get('/estado')
def estado():
    return jsonify({'configured': configured()})


@lotes_api.post('/sincronizar')
def sincronizar():
    if not configured():
        return jsonify({'error': 'El guardado en la nube todavía no está configurado'}), 503
    if not _authorized():
        return jsonify({'error': 'Clave del establecimiento incorrecta'}), 401
    d = request.get_json(silent=True) or {}
    try:
        incoming = [clean_lot(l) for l in (d.get('lotes') or [])][:MAX_LOTS]
        remove = [str(x) for x in (d.get('quitar') or []) if ID_RE.match(str(x))]
        current, sha = _read('lotes.json')
        merged = merge_lots((current or {}).get('lotes'), incoming, remove)
        _write('lotes.json', {'lotes': merged}, sha, f'Lotes: {len(merged)}')
        return jsonify({'status': 'guardado', 'lotes': len(merged)})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except requests.RequestException:
        return jsonify({'error': 'No se pudo guardar en el repositorio de datos'}), 502


@lotes_api.get('/resultado')
def resultado():
    if not configured():
        return jsonify({'error': 'El procesamiento semanal todavía no está configurado'}), 503
    if not _authorized():
        return jsonify({'error': 'Clave del establecimiento incorrecta'}), 401
    lid = request.args.get('id', '')
    if not ID_RE.match(lid):
        return jsonify({'error': 'Lote inválido'}), 400
    try:
        data, _ = _read(f'resultados/{lid}.json')
    except requests.RequestException:
        return jsonify({'error': 'No se pudo leer el repositorio de datos'}), 502
    if data is None:
        return jsonify({'status': 'pendiente', 'detail': 'Este lote todavía no pasó por el procesamiento semanal'}), 200
    return jsonify(data)
