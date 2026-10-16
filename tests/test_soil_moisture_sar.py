"""Humedad de suelo por radar Sentinel-1: índice relativo, RVI, textura y ruta (red simulada)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import research_connectors as c
import soil_moisture_sar as sms

LOT = [[-28.51, -59.05], [-28.51, -59.03], [-28.49, -59.03], [-28.49, -59.05]]

# VV/VH lineales por pasada: la VV sube de a poco (el lote se va humedeciendo)
LIN = {f'S1_2026100{d}': (v, v * 0.18) for d, v in
       zip(range(1, 7), (0.020, 0.050, 0.090, 0.140, 0.200, 0.300))}


class R:
    def __init__(self, data=None, status=200):
        self._d, self.status_code = data, status
        self.headers = {'Content-Type': 'application/json'}
    def json(self): return self._d
    def raise_for_status(self):
        if self.status_code >= 400:
            import requests; raise requests.HTTPError(str(self.status_code))


def fake_post(url, json=None, params=None, **kw):
    if url.endswith('/search'):
        assert json['collections'] == ['sentinel-1-rtc']
        return R({'features': [{'id': f'S1_2026100{d}', 'properties': {
            'datetime': f'2026-10-0{d}T10:00:00Z', 'sat:orbit_state': 'ascending'}} for d in range(1, 7)]})
    if url.endswith('/item/statistics'):
        vv, vh = LIN[params['item']]
        val = vv if params['assets'] == 'vv' else vh
        return R({'type': 'Feature', 'properties': {'statistics': {'b': {'median': val, 'count': 4000}}}})
    return R({}, status=404)


@pytest.fixture
def sar(monkeypatch):
    monkeypatch.setattr(c.SESSION, 'post', fake_post)
    monkeypatch.setattr(c, 'soilgrids', lambda *a, **k: c.envelope(
        {'properties': {'layers': [
            {'name': 'clay', 'unit_measure': {'d_factor': 10}, 'depths': [{'label': '0-5cm', 'values': {'mean': 200}}]},
            {'name': 'sand', 'unit_measure': {'d_factor': 10}, 'depths': [{'label': '0-5cm', 'values': {'mean': 600}}]},
        ]}}, 'u', 'textura', 'ISRIC SoilGrids'))


def test_db_y_rvi():
    assert sms.db(0.0158) == -18.0
    assert sms.db(None) is None and sms.db(0) is None
    assert sms.rvi(0.2, 0.05) == 0.8 and sms.rvi(None, 0.1) is None


def test_percentil_necesita_pasadas():
    assert sms.percentile([0.1, 0.2, 0.3, 0.4], 50) is None      # <5 valores → sin referencia
    assert sms.percentile([0.1, 0.2, 0.3, 0.4, 0.5], 0) == 0.1
    assert sms.percentile([0.1, 0.2, 0.3, 0.4, 0.5], 100) == 0.5


def test_categoria_e_indice_relativo():
    assert [sms.category(i) for i in (0.1, 0.3, 0.5, 0.7, 0.9, None)] == \
        ['muy seco', 'más seco que lo normal', 'normal', 'más húmedo que lo normal', 'muy húmedo', None]
    assert sms.surface_moisture(-20, -25, -10) == 0.33
    assert sms.surface_moisture(-30, -25, -10) == 0.0     # recorta por debajo
    assert sms.surface_moisture(-5, -25, -10) == 1.0      # recorta por arriba
    assert sms.surface_moisture(-20, None, -10) is None


def test_analyze_serie_indice_y_textura(sar):
    d = sms.analyze(LOT)['data']
    assert d['capability'] == 'ANALYSIS' and d['sensor'].startswith('Sentinel-1')
    assert len(d['series']) == 6 and all(r['status'] == 'válida' for r in d['series'])
    assert d['dry_ref_db'] == -15.0 and d['wet_ref_db'] == -6.1   # percentiles 10/90 de las VV en dB
    assert d['latest']['datetime'] == '2026-10-06T10:00:00Z' and d['latest']['category'] == 'muy húmedo'
    assert d['latest']['smi'] == 1.0 and d['latest']['rvi'] == 0.61
    assert d['trend'] == 'el suelo tiende a más húmedo'
    assert d['soil_texture'] == {'clay': 20.0, 'sand': 60.0}


def test_sin_pasadas_falla(monkeypatch):
    monkeypatch.setattr(c.SESSION, 'post', lambda *a, **k: R({'features': []}))
    with pytest.raises(ValueError):
        sms.analyze(LOT)


def test_ruta_humedad_sar(sar):
    from api.index import app
    cl = app.test_client()
    q = '?lat=-28.5&lon=-59.04&polygon=' + json.dumps(LOT)
    r = cl.get('/api/fuentes/humedad-sar' + q)
    j = r.get_json()
    assert r.status_code == 200 and j['data']['latest']['category'] == 'muy húmedo'
    assert j['organism'].startswith('ESA Copernicus')
    assert cl.get('/api/fuentes/humedad-sar?lat=-28.5&lon=-59.04').status_code == 400
    assert cl.get('/api/fuentes/humedad-sar' + q + '&days=9999').status_code == 400
