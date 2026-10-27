"""vitrina — modo vitrina de DOTS: el sitio se ve, pero sólo se usa con clave.

Se prende con la variable DOTS_VITRINA=1 en Vercel. Con el modo prendido las páginas se
pueden recorrer, pero toda la API (consultas, mapas calculados, informes, lotes, avisos,
contacto) devuelve 403 salvo para quien entró con una clave. Quedan abiertos sólo
/api/health y /api/acceso, que es por donde se entra.

Acceso: DOTS_ACCESO_CLAVES lleva una o más claves separadas por coma. Quien escribe una clave
válida en el sitio recibe una cookie firmada (dots_acceso). Las tareas automáticas mandan la
clave en el encabezado X-DOTS-Acceso. DOTS_ACCESO_SECRETO, si está, firma la cookie; si no,
la firma sale de las propias claves (cambiar una clave invalida las cookies viejas).
"""
import hashlib
import hmac
import os

from flask import Blueprint, jsonify, request

COOKIE = 'dots_acceso'
HEADER = 'X-DOTS-Acceso'
COOKIE_DIAS = 90

# Abiertas siempre: el chequeo de salud y la entrada con clave.
LIBRES = ('/api/health', '/api/acceso')

AVISO = 'DOTS está en modo vitrina: para consultar datos o generar informes hay que entrar con una clave de acceso.'

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


# ---- control -------------------------------------------------------------------------------

def _bloqueo():
    resp = jsonify({'status': 'vitrina', 'error': AVISO})
    resp.status_code = 403
    return resp


def check():
    if not activo() or request.method == 'OPTIONS':
        return None
    path = request.path
    if not path.startswith('/api/') or path.startswith(LIBRES) or tiene_acceso():
        return None
    return _bloqueo()


@api.get('/api/acceso')
def estado():
    return jsonify({'vitrina': activo(), 'acceso': activo() and tiene_acceso(), 'aviso': AVISO if activo() else None})


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


def sin_cache_publico(resp):
    """Con la vitrina prendida, ninguna respuesta de la API queda en el caché compartido de Vercel.

    Si una respuesta con clave se guardara como pública, el CDN se la serviría después a cualquiera
    sin pasar por el control de acceso. Se mantiene el caché sólo en el navegador de quien entró.
    """
    if not activo() or not request.path.startswith('/api/') or request.path.startswith(LIBRES):
        return resp
    cc = (resp.headers.get('Cache-Control') or '').lower()
    if resp.status_code == 403 or not cc:
        resp.headers['Cache-Control'] = 'private, no-store'
    elif 'public' in cc or 's-maxage' in cc:
        edad = next((p.split('=', 1)[1] for p in (x.strip() for x in cc.split(',')) if p.startswith('s-maxage=')), None)
        resp.headers['Cache-Control'] = f'private, max-age={min(int(edad), 86400) if edad and edad.isdigit() else 600}'
    resp.headers.add('Vary', 'Cookie')
    return resp


def install(app):
    app.register_blueprint(api)
    app.before_request(check)
    app.after_request(sin_cache_publico)
