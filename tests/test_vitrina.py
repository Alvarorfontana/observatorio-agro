"""Modo vitrina: el sitio se ve, la zona de ejemplo funciona y el resto de las consultas es por invitación."""
import json

import pytest
from flask import Flask, jsonify

import vitrina

BV = (-28.507, -59.043)       # Bella Vista: zona de ejemplo
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


def test_paneles_regionales_abiertos(client):
    assert client.get('/api/fuentes/cuenca').status_code == 200


def test_zona_de_ejemplo_funciona(client):
    assert client.get(f'/api/fuentes/clima?lat={BV[0]}&lon={BV[1]}').status_code == 200
    poly = [[-28.509, -59.049], [-28.509, -59.044], [-28.505, -59.044]]
    assert client.get('/api/fuentes/ndvi?polygon=' + json.dumps(poly)).status_code == 200
    geo = {'type': 'Polygon', 'coordinates': [[[-59.049, -28.509], [-59.044, -28.509], [-59.044, -28.505], [-59.049, -28.509]]]}
    assert client.post('/api/fuentes/analizar', json={'lot': {'geometry': geo}, 'anios': [2024, 2025]}).status_code == 200


def test_fuera_de_zona_bloquea(client):
    r = client.get(f'/api/fuentes/clima?lat={CTES[0]}&lon={CTES[1]}')
    assert r.status_code == 403 and r.get_json()['status'] == 'vitrina'
    assert client.post('/api/fuentes/analizar', json={'lat': CTES[0], 'lon': CTES[1]}).status_code == 403
    # un punto adentro no habilita un polígono afuera
    poly = [[CTES[0], CTES[1]], [CTES[0] + .01, CTES[1]], [CTES[0], CTES[1] + .01]]
    assert client.post('/api/fuentes/analizar', json={'lat': BV[0], 'lon': BV[1], 'polygon': poly}).status_code == 403
    assert client.get('/api/fuentes/ndvi?bbox=-58.9,-27.5,-58.8,-27.4').status_code == 403


def test_post_sin_coordenadas_y_cerradas(client):
    assert client.post('/api/fuentes/costos', json={'heads': 100}).status_code == 403
    assert client.post('/api/lotes/sincronizar', json={'lat': BV[0], 'lon': BV[1]}).status_code == 403


def test_contacto_siempre_abierto(client):
    assert client.post('/api/fuentes/contacto', json={'msg': 'hola'}).status_code == 200


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
