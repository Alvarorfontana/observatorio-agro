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


def test_carbon_and_herd(monkeypatch):
    def ext(url, params=None, **k):
        assert params['property'] == 'ocs' and params['depth'] == '0-30cm'
        return c.envelope({'properties': {'layers': [{'name': 'ocs', 'unit_measure': {'d_factor': 10},
                           'depths': [{'values': {'mean': 520, 'Q0.05': 300, 'Q0.95': 800}}]}]}}, url, 's', 'o')
    monkeypatch.setattr(c, 'external', ext)
    d = su.carbon(-28.5, -59.0, area_ha=100, heads=200)['data']
    assert d['soc_t_ha'] == 52.0 and d['soc_total_t'] == 5200 and d['soc_t_ha_range'] == [30.0, 80.0]
    assert d['herd']['ch4_t_year'] == 11.2 and d['herd']['co2e_t_year'] == 302.4
    assert d['soc_total_tco2e'] == round(5200 * 44 / 12)
