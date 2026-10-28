"""cache_ee — cada consulta a Earth Engine se calcula una sola vez.

El proyecto de Earth Engine tiene una cuota mensual de horas de cálculo. Si dos personas consultan el mismo lote,
o la misma persona vuelve a abrirlo, no hace falta volver a calcular: la respuesta se guarda y se reutiliza mientras
el dato no cambie (los mapas fijos, como bosque 2020 o población 2020, por meses; los que cambian con cada pasada
del satélite, por pocos días).

Dónde se guarda:
  · en memoria de la función mientras está activa;
  · si están DOTS_DATA_REPO y DOTS_DATA_TOKEN (el mismo repositorio PRIVADO de los lotes), en `cache/ee/` de ese
    repositorio, para que sirva entre funciones y entre días. Los contornos de los campos no quedan públicos.
Sólo se guardan respuestas correctas (200 con datos). El control de acceso de la vitrina corre antes que el caché.
"""
import base64
import hashlib
import json
import os
import time
from collections import OrderedDict

import requests
from flask import Response, request

GH = 'https://api.github.com'
DIA = 86400
# Ruta → días que vale una respuesta guardada
REGLAS = {
    '/api/fuentes/arboles-fuera': 180, '/api/fuentes/arboles-fuera-imagen': 180,
    '/api/fuentes/riesgo-hidrico': 180, '/api/fuentes/amenaza': 180,
    '/api/poblacion/crecida': 180, '/api/poblacion/crecida/mapa': 180,
    '/api/fuentes/mapbiomas': 90, '/api/fuentes/cambios-lote': 90,
    '/api/fuentes/gee-ndvi': 30, '/api/fuentes/pasto-historia': 30,
    '/api/fuentes/sustentabilidad': 7, '/api/fuentes/ndvi-anomalia': 7, '/api/fuentes/etr-lote': 7,
    '/api/fuentes/cobertura-reciente': 3, '/api/fuentes/heladas-satelite': 2, '/api/fuentes/smap': 1,
}
MEM_MAX = 300
_MEM = OrderedDict()
_STATS = {'memoria': 0, 'repositorio': 0, 'calculadas': 0, 'guardadas': 0, 'errores_guardado': 0}


def _repo():
    return os.environ.get('DOTS_DATA_REPO', ''), os.environ.get('DOTS_DATA_TOKEN', '')


def _headers():
    _, tok = _repo()
    return {'Authorization': f'Bearer {tok}', 'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'DOTS-Campo'}


def clave(path, args):
    """Huella de la consulta: ruta + parámetros ordenados (lat y lon redondeados a 4 decimales, unos 10 m)."""
    norm = []
    for k in sorted(args):
        v = str(args[k]).strip()
        if k in ('lat', 'lon'):
            try:
                v = f'{float(v):.4f}'
            except ValueError:
                pass
        if k == 'polygon':
            try:
                v = json.dumps([[round(float(a), 6), round(float(b), 6)] for a, b in json.loads(v)], separators=(',', ':'))
            except (ValueError, TypeError):
                pass
        norm.append(f'{k}={v}')
    return hashlib.sha256((path + '?' + '&'.join(norm)).encode()).hexdigest()[:40]


def _ruta(k):
    return f'cache/ee/{k[:2]}/{k}.json'


def _vigente(entrada, dias):
    return entrada and time.time() - entrada.get('t', 0) < dias * DIA


def leer(k, dias):
    e = _MEM.get(k)
    if _vigente(e, dias):
        _MEM.move_to_end(k)
        _STATS['memoria'] += 1
        return e
    repo, tok = _repo()
    if not (repo and tok):
        return None
    try:
        r = requests.get(f'{GH}/repos/{repo}/contents/{_ruta(k)}', headers={**_headers(), 'Accept': 'application/vnd.github.raw'}, timeout=6)
        if r.status_code != 200:
            return None
        e = r.json()
    except Exception:
        return None
    if not _vigente(e, dias):
        return None
    _recordar(k, e)
    _STATS['repositorio'] += 1
    return e


def _recordar(k, e):
    _MEM[k] = e
    _MEM.move_to_end(k)
    while len(_MEM) > MEM_MAX:
        _MEM.popitem(last=False)


def guardar(k, e):
    _recordar(k, e)
    repo, tok = _repo()
    if not (repo and tok):
        return
    url = f'{GH}/repos/{repo}/contents/{_ruta(k)}'
    body = {'message': f'Caché Earth Engine {e.get("path", "")}', 'content': base64.b64encode(json.dumps(e).encode()).decode()}
    try:
        prev = requests.get(url, headers=_headers(), timeout=6)
        if prev.status_code == 200:
            body['sha'] = prev.json().get('sha')
        r = requests.put(url, headers=_headers(), json=body, timeout=10)
        r.raise_for_status()
        _STATS['guardadas'] += 1
    except Exception:
        _STATS['errores_guardado'] += 1


def _entrada(resp):
    """Respuesta → entrada guardable, o None si no conviene guardarla (error, sin datos)."""
    if resp.status_code != 200 or resp.direct_passthrough:
        return None
    body = resp.get_data()
    if resp.mimetype == 'application/json':
        try:
            j = json.loads(body)
        except ValueError:
            return None
        if not isinstance(j, dict) or j.get('error') or j.get('status') in ('sin dato', 'requiere credencial', 'vitrina'):
            return None
        d = j.get('data', j)
        if d is None or (isinstance(d, dict) and d.get('errors')):      # incompleta (alguna fuente falló): no se guarda
            return None
    elif not resp.mimetype.startswith('image/'):
        return None
    hdr = {h: resp.headers[h] for h in ('X-DOTS-Bounds',) if h in resp.headers}
    return {'t': time.time(), 'path': request.path, 'mimetype': resp.mimetype, 'headers': hdr,
            'body': base64.b64encode(body).decode()}


def antes():
    if request.method != 'GET' or request.path not in REGLAS or request.args.get('fresco') == '1':
        return None
    k = clave(request.path, request.args.to_dict())
    request.environ['dots.cache_ee'] = k
    e = leer(k, REGLAS[request.path])
    if not e:
        return None
    resp = Response(base64.b64decode(e['body']), mimetype=e['mimetype'], headers=e.get('headers') or {})
    resp.headers['X-DOTS-Cache'] = 'guardada ' + time.strftime('%Y-%m-%d', time.gmtime(e['t']))
    request.environ['dots.cache_hit'] = True
    return resp


def despues(resp):
    k = request.environ.get('dots.cache_ee')
    if not k or request.environ.get('dots.cache_hit'):
        return resp
    _STATS['calculadas'] += 1
    e = _entrada(resp)
    if e:
        guardar(k, e)
        resp.headers['X-DOTS-Cache'] = 'calculada'
    return resp


def estado():
    return dict(_STATS, en_memoria=len(_MEM), repositorio=bool(all(_repo())))


def install(app):
    app.before_request(antes)
    app.after_request(despues)
