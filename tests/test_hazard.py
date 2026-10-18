"""hazard: amenaza de crecida por período de retorno (JRC), exposición (WorldPop) e historia (GFD).
Lectura pura del resultado, expresiones de Earth Engine, tema y endpoint. Red simulada."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import research_connectors as c
import scales, temas, hazard


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


# ── expresiones de Earth Engine: los conjuntos y reductores correctos ──
def test_site_expression():
    b = json.dumps(hazard.site_expression(-28.5, -59.0))
    assert 'JRC/CEMS_GLOFAS/FloodHazard/v2_1' in b and 'RP100_depth' in b and 'Reducer.max' in b


def test_exposure_expression():
    e = json.dumps(hazard.exposure_expression(-28.5, -59.0))
    assert 'WorldPop/GP/100m/pop' in e and 'exp500' in e and 'Reducer.sum' in e and 'Image.gte' in e


def test_history_expression():
    h = json.dumps(hazard.history_expression(-28.5, -59.0))
    assert 'GLOBAL_FLOOD_DB/MODIS_EVENTS/V1' in h and 'flood_events' in h and 'flood_ever' in h


# ── lectura: perfil, primer anegamiento, expuestos ──
def test_profile_and_first_rp():
    depths = {'RP10_depth': None, 'RP20_depth': None, 'RP50_depth': 0.3, 'RP75_depth': 0.6,
              'RP100_depth': 1.2, 'RP200_depth': 2.0, 'RP500_depth': 3.1}
    prof = hazard.profile(depths)
    assert prof[0] == {'rp_years': 10, 'depth_m': None}
    assert prof[2] == {'rp_years': 50, 'depth_m': 0.3}
    assert hazard.first_rp(prof) == 50
    assert hazard.first_rp(hazard.profile({})) is None


def test_first_rp_ignores_depth_below_threshold():
    prof = hazard.profile({'RP10_depth': 0.05, 'RP20_depth': 0.2})
    assert hazard.first_rp(prof) == 20


def test_exposed():
    exp = hazard.exposed({'exp50': 12.6, 'exp500': 100.0})
    assert exp[2] == {'rp_years': 50, 'people': 13}
    assert exp[-1] == {'rp_years': 500, 'people': 100}
    assert hazard.exposed({})[0] == {'rp_years': 10, 'people': None}


# ── resúmenes (frases) ──
def test_summarize_with_data():
    d = hazard.summarize(-28.5, -59.0, {'RP100_depth': 1.0}, {'exp100': 250.4},
                         {'flood_events': 3.0, 'flood_ever': 1.0})
    assert d['first_rp_years'] == 100 and '100 años' in d['reading'] and 'personas' in d['reading']
    assert d['history'] == {'events': 3, 'ever': True, 'period': [2000, 2018]}
    assert d['point'] == [-28.5, -59.0] and d['caveat'] and d['sources']


def test_summarize_outside_maps():
    d = hazard.summarize(-28.5, -59.0, {}, {}, {})
    assert d['first_rp_years'] is None and 'fuera de los mapas' in d['reading']


def test_summarize_below_threshold_reads_500_years():
    d = hazard.summarize(-28.5, -59.0, {'RP10_depth': 0.05}, {}, {})
    assert d['first_rp_years'] is None and '500 años' in d['reading']


# ── escalas nuevas ──
def test_hazard_scales_present():
    assert 'flood_rp_years' in scales.ids() and 'flood_depth_m' in scales.ids()
    b = scales.band('flood_rp_years', 50)
    assert b['tone'] == 'warn' and b['max'] == 500
    assert scales.band('flood_depth_m', 2.0)['tone'] == 'risk'


# ── analyze: credenciales ausentes → sin dato; con datos → recibido ──
def test_analyze_without_credentials(monkeypatch):
    monkeypatch.delenv('GOOGLE_CLOUD_PROJECT', raising=False)
    monkeypatch.delenv('GOOGLE_APPLICATION_CREDENTIALS_JSON', raising=False)
    out = hazard.analyze(-28.5, -59.0)
    assert out['status'] == 'sin dato' and out['error']


def test_analyze_success(monkeypatch):
    monkeypatch.setattr(hazard.veg, 'gee_token', lambda: ('proj', 'tok'))

    def fake_compute(proj, tok, body):
        s = json.dumps(body)
        if 'WorldPop' in s:
            return {f'exp{r}': float(r) for r in hazard.RPS}
        if 'GLOBAL_FLOOD_DB' in s:
            return {'flood_events': 2.0, 'flood_ever': 1.0}
        return dict({f'RP{r}_depth': None for r in hazard.RPS}, RP100_depth=1.5)
    monkeypatch.setattr(hazard, '_compute', fake_compute)
    out = hazard.analyze(-28.5, -59.0)
    assert out['status'] == 'recibido' and out['data']['first_rp_years'] == 100
    assert out['data']['history']['events'] == 2


# ── tema ──
def test_tema_amenaza_needs_point():
    out = temas.resolve('amenaza', None, None, {})
    assert out['status'] == 'sin dato'
    assert 'amenaza' in temas.ids()


def test_tema_amenaza_resolves(monkeypatch):
    monkeypatch.setattr(hazard, 'analyze', lambda lat, lon: c.envelope({'first_rp_years': 50}, 'u', 's', 'o'))
    out = temas.resolve('amenaza', -31.0, -60.0, {})
    assert out['status'] == 'recibido' and out['data']['first_rp_years'] == 50
    assert out['id'] == 'amenaza' and out['how'] and out['source_url']


# ── endpoint ──
def test_amenaza_endpoint(client, monkeypatch):
    monkeypatch.setattr(hazard, 'analyze', lambda lat, lon: c.envelope({'first_rp_years': 100}, 'u', 's', 'o'))
    r = client.get('/api/fuentes/amenaza?lat=-31&lon=-60')
    assert r.status_code == 200 and r.get_json()['data']['first_rp_years'] == 100


def test_amenaza_endpoint_bad_coords(client):
    assert client.get('/api/fuentes/amenaza').status_code == 400
