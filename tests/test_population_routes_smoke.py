"""Pruebas mínimas de rutas y PDF de población sin servicios externos."""
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
    places = response.get_json()['places']
    assert isinstance(places, list)
    assert places
    assert all({'id', 'place', 'river'} <= set(place) for place in places)


def test_flood_report_rejects_missing_data(client):
    response = client.post('/api/poblacion/crecida/informe', json={})
    assert response.status_code == 400


def test_flood_report_generates_pdf(client):
    payload = {'place': 'Localidad de prueba', 'river': 'Rio de prueba', 'radius_km': 15,
               'total': 1200, 'bands': [{'up_to_m': 1, 'people': 150, 'under5': 12, 'over65': 18}]}
    response = client.post('/api/poblacion/crecida/informe', json=payload)
    assert response.status_code == 200
    assert response.mimetype == 'application/pdf'
    assert response.data.startswith(b'%PDF-')
