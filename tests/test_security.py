"""Límite de pedidos y encabezados de seguridad."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import security


def test_rate_limit_contact(monkeypatch):
    monkeypatch.delenv('DOTS_DISABLE_RATE_LIMIT', raising=False)
    security._hits.clear()
    from api.index import app
    cl = app.test_client()
    body = {'nombre': 'x'}
    codes = [cl.post('/api/fuentes/contacto', json=body, headers={'X-Forwarded-For': '9.9.9.9'}).status_code for _ in range(7)]
    assert codes[:5] == [400] * 5 and codes[5] == 429
    r = cl.post('/api/fuentes/contacto', json=body, headers={'X-Forwarded-For': '8.8.8.8'})
    assert r.status_code == 400   # otra IP no está limitada


def test_security_headers():
    security._hits.clear()
    from api.index import app
    r = app.test_client().get('/api/health')
    assert r.headers['X-Content-Type-Options'] == 'nosniff' and r.headers['X-Frame-Options'] == 'DENY'
