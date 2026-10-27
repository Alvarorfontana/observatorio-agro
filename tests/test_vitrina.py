"""Modo vitrina: el sitio se ve, pero sin clave la API no responde nada."""
import json

import pytest
from flask import Flask, jsonify

import vitrina

BV = (-28.507, -59.043)       # Bella Vista
CTES = (-27.47, -58.83)       # Corrientes capital: fuera de la zona


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('DOTS_VITRINA', '1')
    monkeypatch.setenv('DOTS_ACCESO_CLAVES', 'clave-uno, clave-dos')
    monkeypatch.delenv('DOTS_ACCESO_SECRETO', raising=False)
    app = Flask(__name__)

    @app.route('/api/fuentes/<name>', methods=['GET', 'POST'])
    def fuente(name):
        return jsonify({'status': 'ok', 'name': name})

    @app.route('/api/lotes/sincronizar', methods=['POST'])
    def lotes():
        return jsonify({'status': 'ok'})

    @app.route('/api/fuentes/contacto', methods=['POST'])
    def contacto():
        return jsonify({'status': 'ok'})

    vitrina.install(app)
    return app.test_client()


def test_apagado_no_bloquea(client, monkeypatch):
    monkeypatch.setenv('DOTS_VITRINA', '0')
    assert client.get(f'/api/fuentes/clima?lat={CTES[0]}&lon={CTES[1]}').status_code == 200
    assert client.get('/api/acceso').get_json()['vitrina'] is False


def test_sin_clave_todo_cerrado(client):
    for r in (client.get('/api/fuentes/cuenca'),
              client.get(f'/api/fuentes/clima?lat={BV[0]}&lon={BV[1]}'),
              client.post('/api/fuentes/analizar', json={'lat': BV[0], 'lon': BV[1]}),
              client.post('/api/fuentes/contacto', json={'msg': 'hola'}),
              client.post('/api/lotes/sincronizar', json={})):
        assert r.status_code == 403 and r.get_json()['status'] == 'vitrina'


def test_entrada_siempre_abierta(client):
    assert client.get('/api/acceso').status_code == 200


def test_clave_y_cookie(client):
    assert client.post('/api/acceso', json={'clave': 'mala'}).status_code == 401
    assert client.get('/api/acceso').get_json()['acceso'] is False
    r = client.post('/api/acceso', json={'clave': 'clave-dos'})
    assert r.status_code == 200 and 'dots_acceso=' in r.headers['Set-Cookie'] and 'HttpOnly' in r.headers['Set-Cookie']
    assert 'clave-dos' not in r.headers['Set-Cookie']
    assert client.get('/api/acceso').get_json()['acceso'] is True
    assert client.get(f'/api/fuentes/clima?lat={CTES[0]}&lon={CTES[1]}').status_code == 200
    assert client.post('/api/lotes/sincronizar', json={}).status_code == 200
    client.delete('/api/acceso')
    assert client.get(f'/api/fuentes/clima?lat={CTES[0]}&lon={CTES[1]}').status_code == 403


def test_cookie_falsa_no_pasa(client):
    client.set_cookie('dots_acceso', 'clave-uno')
    assert client.get(f'/api/fuentes/clima?lat={CTES[0]}&lon={CTES[1]}').status_code == 403


def test_encabezado_para_tareas(client):
    h = {'X-DOTS-Acceso': 'clave-uno'}
    assert client.post('/api/fuentes/informe-temas', json={'temas': ['nino']}, headers=h).status_code == 200
    assert client.post('/api/fuentes/informe-temas', json={'temas': ['nino']}, headers={'X-DOTS-Acceso': 'x'}).status_code == 403


def test_sin_claves_nadie_entra(client, monkeypatch):
    monkeypatch.setenv('DOTS_ACCESO_CLAVES', '')
    assert client.post('/api/acceso', json={'clave': ''}).status_code == 401
    assert client.get(f'/api/fuentes/clima?lat={CTES[0]}&lon={CTES[1]}').status_code == 403


def test_respuestas_con_clave_no_quedan_en_cache_publico(monkeypatch):
    monkeypatch.setenv('DOTS_VITRINA', '1')
    monkeypatch.setenv('DOTS_ACCESO_CLAVES', 'clave-uno')
    app = Flask(__name__)

    @app.get('/api/cacheable')
    def cacheable():
        r = jsonify(ok=True); r.headers['Cache-Control'] = 'public, s-maxage=604800'; return r

    @app.get('/api/health')
    def health():
        r = jsonify(ok=True); r.headers['Cache-Control'] = 'public, s-maxage=60'; return r

    vitrina.install(app)
    cl = app.test_client()
    r = cl.get('/api/cacheable', headers={vitrina.HEADER: 'clave-uno'})
    assert r.status_code == 200 and r.headers['Cache-Control'] == 'private, max-age=86400' and 'Cookie' in r.headers['Vary']
    r = cl.get('/api/cacheable')
    assert r.status_code == 403 and r.headers['Cache-Control'] == 'private, no-store'
    assert cl.get('/api/health').headers['Cache-Control'] == 'public, s-maxage=60'
    monkeypatch.setenv('DOTS_VITRINA', '0')
    assert cl.get('/api/cacheable').headers['Cache-Control'] == 'public, s-maxage=604800'
