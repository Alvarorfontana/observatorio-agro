"""smap: humedad del suelo por satélite (NASA SMAP L4) — expresión de Earth Engine, lectura, escala, tema y endpoint."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import research_connectors as c
import scales, temas, smap


class R:
    def __init__(self, data=None, status=200):
        self._d, self.status_code = data, status
        self.text = json.dumps(data)
        self.headers = {'Content-Type': 'application/json'}

    def json(self):
        return self._d


@pytest.fixture
def client(monkeypatch):
    from api.index import app
    return app.test_client()


# ── expresión de Earth Engine: el conjunto, el filtro de fechas y las bandas correctas ──
def test_window_expression():
    b = json.dumps(smap.window_expression(-28.5, -59.0, '2026-10-01', '2026-10-07'))
    assert 'NASA/SMAP/SPL4SMGP/008' in b and 'Filter.dateRangeContains' in b
    assert 'sm_surface' in b and 'sm_rootzone_pctl' in b and 'Reducer.mean' in b


def test_expression_uses_point_buffer():
    b = json.dumps(smap.window_expression(-28.5, -59.0, '2026-10-01', '2026-10-07'))
    assert 'Geometry.buffer' in b and str(smap.RADIUS_M) in b


# ── lectura del resultado ──
def test_summarize_with_data():
    d = smap.summarize(-28.5, -59.0, {'sm_surface': 0.302, 'sm_rootzone': 0.351, 'sm_rootzone_pctl': 62.0,
                                      'sm_surface_wetness': 0.41}, '2026-10-01', '2026-10-07')
    assert d['surface_pct'] == 30.2 and d['root_pct'] == 35.1
    assert d['root_percentile'] == 62 and d['category'] == 'normal'
    assert d['surface_vwc'] == 0.302 and d['point'] == [-28.5, -59.0]
    assert 'superficie (0-5 cm) 30.2 %vol' in d['reading'] and 'percentil 62' in d['reading']
    assert d['caveat'] and d['sources'] and d['method']


def test_summarize_without_data():
    d = smap.summarize(-28.5, -59.0, {}, '2026-10-01', '2026-10-07')
    assert d['surface_vwc'] is None and d['category'] is None
    assert 'no devolvió' in d['reading']


def test_category_bands():
    assert smap.category(5) == 'muy seco respecto de lo normal'
    assert smap.category(20) == 'más seco que lo normal'
    assert smap.category(50) == 'normal'
    assert smap.category(80) == 'más húmedo que lo normal'
    assert smap.category(95) == 'muy húmedo respecto de lo normal'
    assert smap.category(None) is None


# ── escalas nuevas ──
def test_smap_scales_present():
    assert 'soil_moisture_vwc' in scales.ids() and 'soil_moisture_pctl' in scales.ids()
    assert scales.band('soil_moisture_vwc', 0.05)['tone'] == 'risk'
    assert scales.band('soil_moisture_vwc', 0.30)['tone'] == 'ok'
    assert scales.band('soil_moisture_pctl', 95)['tone'] == 'risk'
    assert scales.describe('soil_moisture_vwc')['max'] == 0.9


# ── analyze: sin credenciales → sin dato; con datos → recibido ──
def test_analyze_without_credentials(monkeypatch):
    monkeypatch.delenv('GOOGLE_CLOUD_PROJECT', raising=False)
    monkeypatch.delenv('GOOGLE_APPLICATION_CREDENTIALS_JSON', raising=False)
    out = smap.analyze(-28.5, -59.0)
    assert out['status'] == 'sin dato' and out['error']


def test_analyze_success(monkeypatch):
    monkeypatch.setattr(smap.veg, 'gee_token', lambda: ('proj', 'tok'))
    monkeypatch.setattr(smap, '_compute', lambda proj, tok, body:
                        {'sm_surface': 0.28, 'sm_rootzone': 0.34, 'sm_rootzone_pctl': 58.0, 'sm_surface_wetness': 0.4})
    out = smap.analyze(-28.5, -59.0)
    assert out['status'] == 'recibido' and out['data']['root_percentile'] == 58


def test_analyze_no_data_marks_sin_dato(monkeypatch):
    monkeypatch.setattr(smap.veg, 'gee_token', lambda: ('proj', 'tok'))
    monkeypatch.setattr(smap, '_compute', lambda proj, tok, body: {})
    out = smap.analyze(-28.5, -59.0)
    assert out['status'] == 'sin dato' and out['error']


# ── tema ──
def test_tema_humedad_smap_needs_point():
    out = temas.resolve('humedad_smap', None, None, {})
    assert out['status'] == 'sin dato'
    assert 'humedad_smap' in temas.ids()


def test_tema_humedad_smap_resolves(monkeypatch):
    monkeypatch.setattr(smap, 'analyze', lambda lat, lon: c.envelope({'root_percentile': 58}, 'u', 's', 'o'))
    out = temas.resolve('humedad_smap', -31.0, -60.0, {})
    assert out['status'] == 'recibido' and out['data']['root_percentile'] == 58
    assert out['id'] == 'humedad_smap' and out['how'] and out['source_url']


# ── endpoint ──
def test_smap_endpoint(client, monkeypatch):
    monkeypatch.setattr(smap, 'analyze', lambda lat, lon: c.envelope({'root_percentile': 58}, 'u', 's', 'o'))
    r = client.get('/api/fuentes/smap?lat=-31&lon=-60')
    assert r.status_code == 200 and r.get_json()['data']['root_percentile'] == 58


def test_smap_endpoint_bad_coords(client):
    assert client.get('/api/fuentes/smap').status_code == 400
