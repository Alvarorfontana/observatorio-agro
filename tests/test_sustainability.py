"""Deforestación y carbono con red simulada."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import research_connectors as c
import sustainability as su

LOT = [[-28.51, -59.05], [-28.51, -59.03], [-28.49, -59.03], [-28.49, -59.05]]


class R:
    def __init__(self, d): self._d = d
    def json(self): return self._d
    def raise_for_status(self): pass


def fake_post(tree_by_year):
    def post(url, json=None, params=None, timeout=None, **k):
        if url.endswith('/search'):
            coll = json['collections'][0]; y = json['datetime'][:4]
            return R({'features': [{'id': f'{coll}-{y}'}]})
        item = params['item']; y = int(item[-4:]); expr = params['expression']
        if 'esa-worldcover' in params['collection']:
            v = tree_by_year.get(y, 0.3) if '==10' in expr else 0.5
        else:
            v = tree_by_year.get(y, 0.3) if '==2,' in expr else 0.1
        return R({'type': 'Feature', 'properties': {'statistics': {'x': {'mean': v}}}})
    return post


def test_no_loss(monkeypatch):
    monkeypatch.setattr(c, '_post', lambda url, body, timeout=20: fake_post({})(url, json=body))
    monkeypatch.setattr(c.SESSION, 'post', fake_post({}))
    d = su.deforestation(LOT)['data']
    assert d['verdict'] == 'sin pérdida de cobertura arbórea detectada'
    assert d['baseline_year'] == 2020 and d['last_year'] == 2023 and len(d['series']) == 7
    assert d['worldcover_tree_2020'] == 0.3


def test_loss_detected(monkeypatch):
    trees = {2017: .4, 2018: .4, 2019: .4, 2020: .4, 2021: .3, 2022: .2, 2023: .1}
    monkeypatch.setattr(c, '_post', lambda url, body, timeout=20: fake_post(trees)(url, json=body))
    monkeypatch.setattr(c.SESSION, 'post', fake_post(trees))
    d = su.deforestation(LOT)['data']
    assert d['tree_change_pp'] == -30.0 and d['tree_loss_ha'] > 100
    assert 'requiere verificación' in d['verdict']


def _soil_js(mean):
    return {'properties': {'layers': [{'name': 'ocs', 'unit_measure': {'d_factor': 10},
            'depths': [{'values': {'mean': mean, 'Q0.05': None if mean is None else 300, 'Q0.95': None if mean is None else 800}}]}]}}


def test_carbon_and_herd(monkeypatch):
    def get(url, params=None, timeout=None, **k):
        assert params['property'] == 'ocs' and params['depth'] == '0-30cm'
        return R(_soil_js(520))
    monkeypatch.setattr(c, '_get', get)
    d = su.carbon(-28.5, -59.0, area_ha=100, heads=200)['data']
    assert d['soc_t_ha'] == 52.0 and d['soc_total_t'] == 5200 and d['soc_t_ha_range'] == [30.0, 80.0]
    assert d['herd']['ch4_t_year'] == 11.2 and d['herd']['co2e_t_year'] == 302.4
    assert d['soc_total_tco2e'] == round(5200 * 44 / 12)
    assert d['point_used']['note'] is None


def test_carbon_uses_neighbor_when_point_is_null(monkeypatch):
    calls = []
    def get(url, params=None, timeout=None, **k):
        calls.append(params['lat'])
        return R(_soil_js(None if len(calls) == 1 else 410))
    monkeypatch.setattr(c, '_get', get)
    d = su.carbon(-28.5, -59.0)['data']
    assert d['soc_t_ha'] == 41.0 and len(calls) == 2 and 'norte' in d['point_used']['note']


def test_soil_all_null_is_sin_dato(monkeypatch):
    monkeypatch.setattr(c, '_get', lambda url, params=None, timeout=None, **k: R(_soil_js(None)))
    env = c.soil_full(-28.5, -59.0)
    assert env['status'] == 'sin dato' and env['data'] is None


def test_cover_png(monkeypatch):
    import json
    seen = {}
    class P:
        headers = {'Content-Type': 'image/png'}; content = b'\x89PNG'
        def raise_for_status(self): pass
    def post(url, params=None, json=None, timeout=None):
        seen.update(params); return P()
    monkeypatch.setattr(c.SESSION, 'post', post)
    png, b = su.cover_png('io-lulc-21J-2023', LOT)
    assert png.startswith(b'\x89PNG') and seen['assets'] == 'data' and '"2"' in seen['colormap']
    import pytest
    with pytest.raises(ValueError):
        su.cover_png('../x', LOT)


def test_noisy_small_loss_is_review_not_alarm(monkeypatch):
    # caso real del lote de prueba en Chaco: 2-3 % de árboles con mucho vaivén entre años
    trees = {2017: .0293, 2018: .0213, 2019: .0358, 2020: .0311, 2021: .0285, 2022: .0151, 2023: .0107}
    monkeypatch.setattr(c, '_post', lambda url, body, timeout=20: fake_post(trees)(url, json=body))
    monkeypatch.setattr(c.SESSION, 'post', fake_post(trees))
    d = su.deforestation(LOT)['data']
    assert d['map_noise_pp'] > 0 and d['loss_persistent'] is True
    assert d['tree_change_pp'] == -2.04


def test_soil_error_on_point_then_neighbor_ok(monkeypatch):
    n = []
    def get(url, params=None, timeout=None, **k):
        n.append(1)
        if len(n) == 1: raise ConnectionError('500 en píxel de agua')
        return R(_soil_js(None if len(n) < 4 else 300))
    monkeypatch.setattr(c, '_get', get)
    d = su.carbon(-28.5, -59.04)['data']
    assert d['soc_t_ha'] == 30.0 and 'sur' in d['point_used']['note']


def test_soil_only_errors_raises(monkeypatch):
    import pytest
    monkeypatch.setattr(c, '_get', lambda *a, **k: (_ for _ in ()).throw(ConnectionError()))
    with pytest.raises(ConnectionError):
        c.soil_full(-28.5, -59.0)
