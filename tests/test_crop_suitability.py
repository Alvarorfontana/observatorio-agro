"""crop_suitability: aptitud por envolventes (OpenFarm / EcoCrop) — puntaje, factor limitante, tema y endpoint."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import research_connectors as c
import scales
import crop_suitability as cs
import temas


@pytest.fixture
def client():
    from api.index import app
    return app.test_client()


@pytest.fixture
def good(monkeypatch):
    monkeypatch.setattr(cs, '_climate', lambda lat, lon: {'t_mean': 24.0, 'p_annual': 800, 'years': 10})
    monkeypatch.setattr(cs, '_soil', lambda lat, lon: {'ph': 6.5, 'clay_frac': 0.25})


# ── puntaje de una envolvente ──
def test_score_inside_and_edges():
    env = (0.15, 0.35, 0.0, 0.55)
    assert cs.score(0.25, env) == 100.0
    assert cs.score(0.15, env) == 100.0 and cs.score(0.35, env) == 100.0
    assert cs.score(0.075, env) == pytest.approx(50.0)
    assert cs.score(-0.10, env) == 0.0 and cs.score(0.60, env) == 0.0


def test_crop_of_defaults_to_maiz():
    assert cs.crop_of('SOJA') == 'soja' and cs.crop_of('desconocido') == 'maiz'


# ── escala ──
def test_crop_suitability_scale():
    assert 'crop_suitability' in scales.ids() and scales.describe('crop_suitability')['max'] == 100.0
    assert scales.band('crop_suitability', 30)['tone'] == 'risk'
    assert scales.band('crop_suitability', 70)['tone'] == 'ok'


# ── analyze ──
def test_analyze_ideal_point(good):
    out = cs.analyze(-31.0, -60.0, 'maiz')
    assert out['status'] == 'recibido'
    d = out['data']
    assert d['overall'] == 100.0 and d['scale']['label'] == 'muy apto'
    assert set(d['factors']) == {'t', 'p', 'ph', 'tex'}
    assert 'aptitud' in d['reading']


def test_analyze_dry_point_limits_by_rain(good, monkeypatch):
    monkeypatch.setattr(cs, '_climate', lambda lat, lon: {'t_mean': 24.0, 'p_annual': 450, 'years': 10})
    out = cs.analyze(-31.0, -60.0, 'maiz')
    d = out['data']
    assert d['limiting'] == 'p' and d['overall'] == 25.0 and d['scale']['tone'] == 'risk'
    assert 'Lluvia' in d['reading'] and 'limita' in d['reading']


def test_analyze_without_climate_sin_dato(monkeypatch):
    monkeypatch.setattr(cs, '_climate', lambda lat, lon: None)
    monkeypatch.setattr(cs, '_soil', lambda lat, lon: {'ph': 6.5, 'clay_frac': 0.25})
    out = cs.analyze(-31.0, -60.0)
    assert out['status'] == 'sin dato' and 'clima' in out['error']


def test_analyze_without_soil_sin_dato(good, monkeypatch):
    monkeypatch.setattr(cs, '_soil', lambda lat, lon: None)
    out = cs.analyze(-31.0, -60.0)
    assert out['status'] == 'sin dato' and 'SoilGrids' in out['error']


# ── tema ──
def test_tema_aptitud_resolves(monkeypatch):
    monkeypatch.setattr(cs, 'analyze', lambda lat, lon, crop: c.envelope({'overall': 70}, 'u', 's', 'o'))
    out = temas.resolve('aptitud', -31.0, -60.0, {'crop': 'soja'})
    assert out['status'] == 'recibido' and out['data']['overall'] == 70
    assert out['id'] == 'aptitud' and out['group'] == 'Cultivo'


def test_tema_aptitud_needs_point():
    out = temas.resolve('aptitud', None, None, {})
    assert out['status'] == 'sin dato' and 'punto' in out['error']


# ── endpoint ──
def test_aptitud_endpoint(client, monkeypatch):
    monkeypatch.setattr(cs, 'analyze', lambda lat, lon, crop: c.envelope({'overall': 65}, 'u', 's', 'o'))
    r = client.get('/api/fuentes/aptitud?lat=-31&lon=-60&crop=soja')
    assert r.status_code == 200 and r.get_json()['data']['overall'] == 65


def test_aptitud_endpoint_bad_coords(client):
    assert client.get('/api/fuentes/aptitud').status_code == 400
