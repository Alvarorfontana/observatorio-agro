"""vitrina — modo vitrina de DOTS: el sitio se ve, pero las consultas son por invitación.

Se prende con la variable DOTS_VITRINA=1 en Vercel. Con el modo prendido:

- Las páginas, los mapas, los paneles regionales (cuenca, El Niño, ríos, temas) y las
  explicaciones siguen abiertos.
- La zona de ejemplo de Bella Vista (Corrientes) funciona completa, informes incluidos,
  para que cualquiera vea qué hace DOTS.
- Cualquier consulta sobre otro lugar, el guardado de lotes y los informes por localidad
  devuelven 403 con un aviso de acceso por invitación.
- Quedan siempre abiertos el contacto y la suscripción a avisos de crecida.

Acceso: DOTS_ACCESO_CLAVES lleva una o más claves separadas por coma. Quien escribe una clave
válida en el sitio recibe una cookie firmada (dots_acceso). Las tareas automáticas mandan la
clave en el encabezado X-DOTS-Acceso. DOTS_ACCESO_SECRETO, si está, firma la cookie; si no,
la firma sale de las propias claves (cambiar una clave invalida las cookies viejas).
"""
import hashlib
import hmac
import json
import math
import os

from flask import Blueprint, jsonify, request

COOKIE = 'dots_acceso'
HEADER = 'X-DOTS-Acceso'
COOKIE_DIAS = 90

# Zona de ejemplo: Bella Vista, Corrientes. Cubre el lote de ejemplo, el caso Bella Vista y Copernicus.
ZONA = {'nombre': 'Bella Vista, Corrientes', 'lat': -28.507, 'lon': -59.043, 'radio_km': 20}

# Abiertas siempre, con o sin modo vitrina.
LIBRES = (
    '/api/health',
    '/api/acceso',
    '/api/fuentes/contacto',            # incluye /contacto/canal
    '/api/fuentes/avisos/suscribir',    # avisos de crecida: es seguridad de la población
)
# Siempre por invitación, aunque no lleven coordenadas.
CERRADAS = (
    '/api/lotes/',
    '/api/poblacion/barrios/informe',   # PDF por localidad y regional
    '/api/poblacion/crecida',           # Earth Engine por localidad
    '/api/poblacion/resultado',
    '/api/fuentes/notificar',
)

AVISO = ('DOTS está en modo vitrina: las consultas sobre tu campo o tu localidad son por invitación. '
         'La zona de ejemplo de Bella Vista (Corrientes) funciona completa.')

api = Blueprint('vitrina_api', __name__)


def activo():
    return os.environ.get('DOTS_VITRINA', '').strip().lower() in ('1', 'si', 'sí', 'true', 'on')


def _claves():
    return [k.strip() for k in os.environ.get('DOTS_ACCESO_CLAVES', '').split(',') if k.strip()]


def _secreto(claves):
    s = os.environ.get('DOTS_ACCESO_SECRETO', '').strip()
    return (s or 'dots|' + '|'.join(sorted(claves))).encode()


def _firma(clave, claves):
    return hmac.new(_secreto(claves), clave.encode(), hashlib.sha256).hexdigest()


def clave_valida(clave):
    clave = (clave or '').strip()
    return bool(clave) and any(hmac.compare_digest(clave, k) for k in _claves())


def tiene_acceso():
    claves = _claves()
    if not claves:
        return False
    if clave_valida(request.headers.get(HEADER)):
        return True
    cookie = request.cookies.get(COOKIE, '')
    return bool(cookie) and any(hmac.compare_digest(cookie, _firma(k, claves)) for k in claves)


# ---- coordenadas ---------------------------------------------------------------------------

def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _en_zona(lat, lon):
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return False
    r = 6371.0
    p1, p2 = math.radians(lat), math.radians(ZONA['lat'])
    dp, dl = p2 - p1, math.radians(ZONA['lon'] - lon)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a)) <= ZONA['radio_km']


def _par_en_zona(a, b):
    """Un par puede venir como [lat, lon] (Leaflet) o [lon, lat] (GeoJSON)."""
    return _en_zona(a, b) or _en_zona(b, a)


LAT_KEYS = ('lat', 'latitude', 'latitud')
LON_KEYS = ('lon', 'lng', 'longitude', 'longitud')


def _pares(obj, out, depth=0):
    """Junta todos los pares de coordenadas que encuentra en un JSON."""
    if depth > 12 or len(out) > 5000:
        return
    if isinstance(obj, dict):
        lat = next((_num(obj[k]) for k in LAT_KEYS if k in obj), None)
        lon = next((_num(obj[k]) for k in LON_KEYS if k in obj), None)
        if lat is not None and lon is not None:
            out.append((lat, lon))
        for v in obj.values():
            _pares(v, out, depth + 1)
    elif isinstance(obj, (list, tuple)):
        if len(obj) in (2, 3) and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in obj):
            a, b = float(obj[0]), float(obj[1])
            # Fuera de rango no es una coordenada (por ejemplo, una lista de años): se ignora.
            if abs(a) <= 180 and abs(b) <= 180 and (abs(a) <= 90 or abs(b) <= 90):
                out.append((a, b))
            return
        for v in obj:
            _pares(v, out, depth + 1)
    elif isinstance(obj, str) and obj[:1] in '[{' and len(obj) < 500_000:
        try:
            _pares(json.loads(obj), out, depth + 1)
        except ValueError:
            pass


def _pares_query(args):
    out = []
    lat = next((_num(args.get(k)) for k in LAT_KEYS if args.get(k) is not None), None)
    lon = next((_num(args.get(k)) for k in LON_KEYS if args.get(k) is not None), None)
    if lat is not None or lon is not None:
        out.append((lat if lat is not None else 999, lon if lon is not None else 999))
    for k, v in args.items(multi=True):
        if k in LAT_KEYS or k in LON_KEYS:
            continue
        if k == 'bbox':
            n = [_num(x) for x in v.split(',')]
            if len(n) == 4 and None not in n:
                out += [(n[0], n[1]), (n[2], n[3])]
            else:
                out.append((999, 999))
            continue
        _pares(v, out)
    return out


def _todo_en_zona(pares):
    return all(_par_en_zona(a, b) for a, b in pares)


# ---- control -------------------------------------------------------------------------------

def _bloqueo():
    resp = jsonify({'status': 'vitrina', 'error': AVISO, 'zona_ejemplo': ZONA})
    resp.status_code = 403
    return resp


def check():
    if not activo() or request.method == 'OPTIONS':
        return None
    path = request.path
    if not path.startswith('/api/') or path.startswith(LIBRES):
        return None
    if tiene_acceso():
        return None
    if path.startswith(CERRADAS):
        return _bloqueo()
    pares = _pares_query(request.args)
    if request.method != 'GET':
        body = request.get_json(silent=True)
        if body is None and request.form:
            body = request.form.to_dict()
        if body is not None:
            _pares(body, pares)
        # Un POST sin coordenadas no tiene ejemplo que mostrar: se cierra.
        if not pares:
            return _bloqueo()
    return None if _todo_en_zona(pares) else _bloqueo()


@api.get('/api/acceso')
def estado():
    return jsonify({'vitrina': activo(), 'acceso': activo() and tiene_acceso(), 'zona_ejemplo': ZONA, 'aviso': AVISO if activo() else None})


@api.post('/api/acceso')
def entrar():
    body = request.get_json(silent=True) or {}
    clave = str(body.get('clave') or '')[:200]
    if not clave_valida(clave):
        return jsonify({'status': 'rechazado', 'error': 'La clave no es válida.'}), 401
    resp = jsonify({'status': 'ok', 'acceso': True})
    resp.set_cookie(COOKIE, _firma(clave.strip(), _claves()), max_age=COOKIE_DIAS * 86400,
                    httponly=True, secure=request.is_secure or request.headers.get('X-Forwarded-Proto') == 'https',
                    samesite='Lax', path='/')
    return resp


@api.delete('/api/acceso')
def salir():
    resp = jsonify({'status': 'ok', 'acceso': False})
    resp.delete_cookie(COOKIE, path='/')
    return resp


def install(app):
    app.register_blueprint(api)
    app.before_request(check)
