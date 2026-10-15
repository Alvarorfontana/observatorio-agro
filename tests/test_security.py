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
    assert 'max-age' in r.headers['Strict-Transport-Security'] and 'camera=()' in r.headers['Permissions-Policy']


def client():
    security._hits.clear()
    from api.index import app
    return app.test_client()


def test_costs_rate_limited(monkeypatch):
    monkeypatch.delenv('DOTS_DISABLE_RATE_LIMIT', raising=False)
    cl = client()
    codes = [cl.post('/api/fuentes/costos', json={'lat': 'x'}, headers={'X-Forwarded-For': '7.7.7.7'}).status_code for _ in range(21)]
    assert codes[-1] == 429 and set(codes[:20]) == {400}


def test_body_too_large_is_rejected():
    r = client().post('/api/fuentes/contacto', data=b'x' * (3 * 1024 * 1024), headers={'Content-Type': 'application/json'})
    assert r.status_code == 413


def test_image_proxy_only_allows_sentinel_previews():
    cl = client()
    for url in ('http://169.254.169.254/latest/meta-data', 'https://evil.example.com/preview.jpg',
                'https://sentinel-cogs.s3.us-west-2.amazonaws.com/otra/preview.jpg'):
        r = cl.get('/api/fuentes/foto', query_string={'lat': -28.5, 'lon': -59, 'asset': url})
        assert r.status_code == 400


def test_raster_item_ids_are_validated():
    cl = client()
    poly = '[[-28.51,-59.05],[-28.51,-59.03],[-28.49,-59.03]]'
    for name, item in (('ndvi-imagen', '../../x'), ('cobertura-imagen', 'a/b?c')):
        r = cl.get(f'/api/fuentes/{name}', query_string={'lat': -28.5, 'lon': -59, 'item': item, 'polygon': poly})
        assert r.status_code == 400


def test_pdf_routes_have_tight_limits():
    import security
    for path in ('/api/poblacion/informe', '/api/fuentes/enso-informe', '/api/fuentes/cuenca-informe'):
        rule = next(r for r in security.RULES if path.startswith(r[0]))
        assert rule[1] <= 6, path
