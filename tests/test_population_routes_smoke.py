"""Pruebas mínimas de rutas y PDF de población sin acceso a servicios externos."""
import io
import pytest
from flask import Flask
from poblacion.routes import bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(bp)
    app.config['TESTING'] = True
    return app.test_client()


def test_population_state_route(client):
    response = client.get('/api/poblacion/estado')
    assert response.status_code == 200
    assert response.get_json()['page'] == '/poblacion'


def test_population_localities_route(client):
    response = client.get('/api/poblacion/localidades')
    assert response.status_code == 200
    assert isinstance(response.get_json()['places'], list)


def test_flood_report_rejects_missing_data(client):
    response = client.post('/api/poblacion/crecida/informe', json={})
    assert response.status_code == 400


def test_flood_report_generates_pdf(client):
    response = client.post('/api/poblacion/crecida/informe', json={'place':'Localidad de prueba','river':'Río de prueba','bands':[]})
    assert response.status_code == 200
    assert response.mimetype == 'application/pdf'
    assert response.data.startswith(b'%PDF-')
