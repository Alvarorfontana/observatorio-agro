import json

import pytest
from flask import Flask, jsonify, Response

import cache_ee
import vitrina


@pytest.fixture
def app(monkeypatch):
    monkeypatch.delenv('DOTS_DATA_REPO', raising=False)
    monkeypatch.delenv('DOTS_DATA_TOKEN', raising=False)
    monkeypatch.setenv('DOTS_VITRINA', '1')
    monkeypatch.setenv('DOTS_ACCESO_CLAVES', 'clave')
    cache_ee._MEM.clear()
    a = Flask(__name__)
    a.calls = {'n': 0}

    @a.get('/api/fuentes/arboles-fuera')
    def arboles():
        a.calls['n'] += 1
        return jsonify({'status': 'recibido', 'data': {'trees_ha': a.calls['n']}})

    @a.get('/api/fuentes/arboles-fuera-imagen')
    def img():
        a.calls['n'] += 1
        return Response(b'\x89PNG fake', mimetype='image/png', headers={'X-DOTS-Bounds': '[1,2,3,4]'})

    @a.get('/api/fuentes/sustentabilidad')
    def sust():
        a.calls['n'] += 1
        return jsonify({'status': 'recibido', 'data': {'carbon': 1, 'errors': {'mapbiomas': 'Earth Engine HTTP 429'}}})

    @a.get('/api/fuentes/gee-ndvi')
    def ndvi():
        a.calls['n'] += 1
        return jsonify({'status': 'sin dato', 'data': None, 'error': 'Earth Engine HTTP 429'})

    vitrina.install(a)
    cache_ee.install(a)
    return a


H = {vitrina.HEADER: 'clave'}
P = '?lat=-28.5&lon=-59.04&polygon=' + json.dumps([[-28.5, -59.05], [-28.5, -59.03], [-28.52, -59.03]])


def test_segunda_consulta_sale_del_cache(app):
    c = app.test_client()
    r1 = c.get('/api/fuentes/arboles-fuera' + P, headers=H)
    r2 = c.get('/api/fuentes/arboles-fuera' + P.replace('-28.5&', '-28.50001&'), headers=H)
    assert app.calls['n'] == 1 and r1.get_json() == r2.get_json()
    assert r1.headers['X-DOTS-Cache'] == 'calculada' and r2.headers['X-DOTS-Cache'].startswith('guardada')
    c.get('/api/fuentes/arboles-fuera' + P + '&fresco=1', headers=H)
    assert app.calls['n'] == 2


def test_imagen_con_sus_encabezados(app):
    c = app.test_client()
    c.get('/api/fuentes/arboles-fuera-imagen' + P, headers=H)
    r = c.get('/api/fuentes/arboles-fuera-imagen' + P, headers=H)
    assert app.calls['n'] == 1 and r.data == b'\x89PNG fake' and r.headers['X-DOTS-Bounds'] == '[1,2,3,4]'


def test_no_guarda_errores_ni_resultados_incompletos(app):
    c = app.test_client()
    for _ in range(2):
        c.get('/api/fuentes/gee-ndvi' + P, headers=H)
        c.get('/api/fuentes/sustentabilidad' + P, headers=H)
    assert app.calls['n'] == 4


def test_sin_clave_no_entrega_lo_guardado(app):
    c = app.test_client()
    c.get('/api/fuentes/arboles-fuera' + P, headers=H)
    r = c.get('/api/fuentes/arboles-fuera' + P)
    assert r.status_code == 403 and 'trees_ha' not in r.get_data(as_text=True)


def test_vence(app, monkeypatch):
    c = app.test_client()
    c.get('/api/fuentes/arboles-fuera' + P, headers=H)
    t = __import__('time').time()
    monkeypatch.setattr(cache_ee.time, 'time', lambda: t + 181 * cache_ee.DIA)
    c.get('/api/fuentes/arboles-fuera' + P, headers=H)
    assert app.calls['n'] == 2


def test_guarda_en_el_repositorio_privado(app, monkeypatch):
    monkeypatch.setenv('DOTS_DATA_REPO', 'yo/privado'); monkeypatch.setenv('DOTS_DATA_TOKEN', 't')
    puestos = {}

    class R:
        def __init__(s, code, body=None): s.status_code, s._b = code, body
        def json(s): return s._b
        def raise_for_status(s): pass
    monkeypatch.setattr(cache_ee.requests, 'get', lambda url, **k: R(200, puestos[url]) if url in puestos and 'raw' in k['headers']['Accept'] else R(404))
    monkeypatch.setattr(cache_ee.requests, 'put', lambda url, **k: puestos.__setitem__(url, json.loads(__import__('base64').b64decode(k['json']['content']))) or R(201))
    c = app.test_client()
    c.get('/api/fuentes/arboles-fuera' + P, headers=H)
    assert len(puestos) == 1 and next(iter(puestos)).startswith('https://api.github.com/repos/yo/privado/contents/cache/ee/')
    cache_ee._MEM.clear()                       # otra función de Vercel, sin memoria: lee del repositorio
    r = c.get('/api/fuentes/arboles-fuera' + P, headers=H)
    assert app.calls['n'] == 1 and r.get_json()['data']['trees_ha'] == 1
