"""security v2.9 — límite de pedidos y encabezados de seguridad para la API de DOTS.

Límite por IP con ventana deslizante en memoria. En Vercel cada instancia lleva su propia
cuenta, así que es una barrera contra ráfagas y abusos simples; para un límite global hace
falta un almacén compartido (Upstash/Vercel KV) o reglas del firewall de Vercel.
"""
import os, time
from collections import deque
from threading import Lock

from flask import request, jsonify

# (prefijo de ruta, pedidos permitidos, ventana en segundos) — se usa la primera regla que coincide
RULES = [
    ('/api/fuentes/contacto', 5, 600),       # 5 consultas cada 10 minutos
    ('/api/fuentes/analizar', 6, 300),       # informes PDF
    ('/api/fuentes/eudr', 10, 300),
    ('/api/fuentes/agentic', 12, 300),
    ('/api/fuentes/tile', 600, 60),          # teselas del mapa base
    ('/api/fuentes/ndvi-imagen', 60, 60),
    ('/api/fuentes/', 120, 60),              # resto de las fuentes
]
_hits = {}
_lock = Lock()


def client_ip():
    fwd = request.headers.get('X-Forwarded-For', '')
    return (fwd.split(',')[0].strip() if fwd else request.headers.get('X-Real-IP') or request.remote_addr or 'anon')[:64]


def check():
    if os.environ.get('DOTS_DISABLE_RATE_LIMIT') == '1':
        return None
    path = request.path
    rule = next((r for r in RULES if path.startswith(r[0])), None)
    if not rule:
        return None
    prefix, limit, window = rule
    key = (client_ip(), prefix)
    now = time.monotonic()
    with _lock:
        q = _hits.setdefault(key, deque())
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            retry = int(window - (now - q[0])) + 1
            resp = jsonify({'status': 'demasiados pedidos', 'error': f'Llegaste al límite de consultas. Probá de nuevo en {retry} s.'})
            resp.status_code = 429
            resp.headers['Retry-After'] = str(retry)
            return resp
        q.append(now)
        if len(_hits) > 20000:   # evita crecer sin límite
            _hits.clear()
    return None


def headers(resp):
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    resp.headers.setdefault('X-Frame-Options', 'DENY')
    if resp.mimetype == 'application/json':
        resp.headers.setdefault('Cache-Control', 'no-store')
    return resp


def install(app):
    app.before_request(check)
    app.after_request(headers)
